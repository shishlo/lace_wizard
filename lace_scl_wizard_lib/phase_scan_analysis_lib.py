#--------------------------------------------------------------------------
# This is a library of phase scan analysis classes.
# Analysis will be perfomed for all or selected SCL cavities
# to find cavities and their Low Level RF systems parameters. 
# Analysis can be stopped at any time. 
#---------------------------------------------------------------------------
import time
import math
import sys

from orbit.core.orbit_utils import Function
from orbit.core.orbit_utils import SplineCH

# import the utilities
from orbit.utils import phaseNearTargetPhase, phaseNearTargetPhaseDeg

from orbit.utils.fitting import Solver
from orbit.utils.fitting import Scorer
from orbit.utils.fitting import SolveStopperFactory
from orbit.utils.fitting import ScoreboardActionListener
from orbit.utils.fitting import VariableProxy
from orbit.utils.fitting import TrialPoint

from orbit.utils.fitting import SimplexSearchAlgorithm

#---- Channel access
import epics

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Slot, Signal

from statistics_lib.statistics import fitCosineFunc

#------------------------------------------------------------------------
#           Auxiliary SCAN classes and functions
#------------------------------------------------------------------------   
class AnalysisStateController:
    """ This is the analysis stopper """
    def __init__(self):
        self.isRunning = False
        self.shouldStop = False
        
    def getIsRunning(self):
        return self.isRunning
        
    def getShouldStop(self):
        return self.shouldStop

    def setIsRunning(self,val):
        self.isRunning = val
        
    def setShouldStop(self,val):
        self.shouldStop = val

class AnalysisWorkerSignals(QObject):
    """ Signals for updating tables, info-lines text, and plots """ 
    analysis_data_changed = Signal(tuple)

class Analysis_Runner(QRunnable):
    """ 
    It performs the analysis of scan data for selected or all cavities. 
    """
    def __init__(self,scan_analysis_cntrl,cav_wrappers, simplex_iter = 50):
        QRunnable.__init__(self)
        self.scan_analysis_cntrl = scan_analysis_cntrl
        self.cav_wrappers = cav_wrappers        
        self.cavs_phase_scan_cntrl = self.scan_analysis_cntrl.cavs_phase_scan_cntrl
        self.cavs_scan_cntrl = self.cavs_phase_scan_cntrl.cavs_scan_cntrl
        self.lace_scl_wizard = self.cavs_phase_scan_cntrl.lace_scl_wizard
        self.energy_meter = self.lace_scl_wizard.energy_meter
        self.signals = self.scan_analysis_cntrl.analysis_worker_signals
        #--------------------------------------
        self.cavs_table_view = self.scan_analysis_cntrl.cavs_table_view
        self.cavs_data_analysis_table_model = self.scan_analysis_cntrl.cavs_data_analysis_table_model
        #---------------------------------------
        #---- Number of steps in simplex fitting of cavity parameters
        self.simplex_iter = simplex_iter
        #---------------------------------------
        self.bpm_min_amp_spin_box = self.cavs_scan_cntrl.bottom_panel_cntrl.bpm_min_amp_spin_box
        #---------------------------------------
        self.spline = SplineCH()
        #---------------------------------------
        self.analysis_stopper = self.scan_analysis_cntrl.analysis_stopper
        self.scan_status_text = self.scan_analysis_cntrl.upper_panel_cntrl.analysis_status_text
        self.statusLabel = self.lace_scl_wizard.getStatusLabel()
        self.setAutoDelete(True)
        #self.statusLabel.setStyleSheet("color: red;")
            
    @Slot()
    def run(self):
        """ Analysis thread execution."""
        cav_start = self.cav_wrappers[0].getAlias()
        cav_stop = self.cav_wrappers[-1].getAlias()
        msg_txt = "Analysis started with cvity = " + cav_start + " to " + cav_stop
        self.signals.analysis_data_changed.emit(("status_update",msg_txt))
        ######self.cavs_table_view.clearSelection()
        min_bpm_amp = self.bpm_min_amp_spin_box.value()
        iter_count = 0
        time_start = time.time()      
        for cav_local_ind,cav_wrapper in enumerate(self.cav_wrappers):
            cav_start = cav_wrapper.getAlias()
            scav_stop = self.cav_wrappers[-1].getAlias()
            msg_txt = "Analysis cvity = " + cav_start + " to " + cav_stop
            self.signals.analysis_data_changed.emit(("status_update",msg_txt))
            #---- cav index in the table
            cav_ind = self.cavs_data_analysis_table_model.cav_wrappers.index(cav_wrapper)
            self.signals.analysis_data_changed.emit(("table_selection_clear",))
            if(cav_wrapper.isGood == False):
                cav_wrapper_previous = self.cavs_data_analysis_table_model.cav_wrappers[cav_ind-1]
                cav_wrapper.E0TL = 0.
                cav_wrapper.eKin_in = cav_wrapper_previous.eKin_out
                cav_wrapper.eKin_out = cav_wrapper_previous.eKin_out
                cav_wrapper.isAnalyzed = False
                continue
            self.signals.analysis_data_changed.emit(("table_selection_set",cav_ind))
            #------------------------------------------------------------------
            #---- Here we start analysis of full array of BPMs data to get
            #---- functions eKinOut vs. cavity phase. We will consider set of 
            #---- BPMs for each cavity phase and use the energy meter to get
            #---- eKinOut for this phase.
            #---- As the result we will get cav_wrapper.eKin_out_func function.
            #------------------------------------------------------------------
            eKin_out_guess = cav_wrapper.eKin_out
            if(cav_start.find("CCL") >= 0):
                eKin_out_guess = 185.6
            #---- calculation of cav_wrapper.eKin_out_func from BPMs' data
            self.phaseScanAnalysis(eKin_out_guess,cav_wrapper)     
            #------------------------------------------------------------------
            #---- Performing analysis - from here we assume that cav_wrapper
            #---- has eKin_out_func with data eKinOut vs cavity phase
            #---- We will use this function to get parameters of cavity model
            #---- and eKinOut for the next cavity as eKinIn.
            #------------------------------------------------------------------
            (E0TL,cav_phase_offset,eKin_in_guess) = fitCosineFunc(cav_wrapper.eKin_out_func,cav_wrapper.eKin_out_fit_func)
            #print ("debug  cav=",cav_wrapper.getAlias()," eKin_in = ",eKin_in_guess," E0TL =",E0TL," cav_phase_offset=",cav_phase_offset)
            #---- These are preliminary setting based on 1-st order harmonic of phase scan
            cav_wrapper.E0TL = E0TL
            cav_wrapper.eKin_in = eKin_in_guess
            self.spline.compile(cav_wrapper.eKin_out_fit_func)
            cav_wrapper.eKin_out = self.spline.getY(cav_wrapper.epicsPhase)
            #---- No further analysis for CCL4 cavity
            if(cav_start.find("CCL") >= 0):
                cav_wrapper.E0TL = 0.
                cav_wrapper.eKin_out = cav_wrapper.eKin_in
                cav_wrapper.setModelCavityPhaseOffset(0.)
                cav_wrapper.isAnalyzed = True
                continue
            #---- Fitting model parameters directly
            #print ("debug cav=",cav_wrapper.getAlias()," phase_offset=",cav_phase_offset)
            #---- Now we create the phase scan for the model to compare it to 
            #---- the real Cosine Fit for cav_wrapper.eKin_out_func
            cav_wrapper.setModelCavityPhaseOffset(0.)
            cav_wrapper.eKin_in = self.cavs_data_analysis_table_model.cav_wrappers[cav_ind-1].eKin_out
            scorer = CavityParamsScorer_eKinOut(cav_wrapper,cav_wrapper.eKin_in)
            #---- Let's get approximate sin-like eKinOut vs cav. phase function using the model
            #---- We will use E0TL_appr to correct cavity model amplitude according the E0TL_appr and cav_wrapper.E0TL
            scorer.calcModel_eKinOut_Arr(cav_wrapper.eKin_in)
            #---- This will rewrite the cav_wrapper.eKin_out_fit_func
            eKin_out_appr_model_func = scorer.update_eKinOutFitFunction()
            (E0TL_model,cav_phase_offset_model,eKin_in_guess_model) = fitCosineFunc(eKin_out_appr_model_func)
            #print ("debug cav=",cav_wrapper.getAlias()," phase_offset_model=",cav_phase_offset_model)
            #---- Fix the model amplitude - it will be closer to BPM data
            coeff_amp = cav_wrapper.E0TL/E0TL_model
            model_cav_amp = cav_wrapper.model_cav.getModelAmp()
            cav_wrapper.model_cav.setModelAmp(model_cav_amp*coeff_amp)
            #---- Fix the cavity phase offset - it will be closer to BPM data
            cav_phase_offset_model -= cav_phase_offset
            cav_wrapper.setModelCavityPhaseOffset(-cav_phase_offset_model)
            scorer.calcModel_eKinOut_Arr(cav_wrapper.eKin_in)
            eKin_out_appr_model_func = scorer.update_eKinOutFitFunction()
            #---- Let's fit the cavity model parameters 
            best_score, trialPoint = self.performCavityParamsFitting_eKin(scorer,cav_wrapper.eKin_in)
            [model_cav_amp,model_cav_phase_offset] = trialPoint.getVariableProxyValuesArr()
            print ("debug  cav=",cav_wrapper.getAlias()," model_cav_amp,model_cav_phase_offset=",[model_cav_amp,model_cav_phase_offset])
            #print ("debug  cav=",cav_wrapper.getAlias(), "best score = ",math.sqrt(best_score))
            #----  
            if(self.analysis_stopper.getShouldStop()):
                self.analysis_stopper.setShouldStop(False)
                self.analysis_stopper.setIsRunning(False)
                #cav_wrapper.setEPICS_CavityPhase(cav_phase_init)
                self.signals.analysis_data_changed.emit(("status_update","Analysis stopped by user's request"))
                self.signals.analysis_data_changed.emit(("table_selection_set",cav_ind))
                return
        #--------- END of SCAN
        time_scan = time.time() - time_start
        msg_txt = "Analysis finished. Time[sec] = "+"%7.1f"%time_scan
        self.signals.analysis_data_changed.emit(("status_update",msg_txt))
        self.signals.analysis_data_changed.emit(("table_selection_clear",))
        self.signals.analysis_data_changed.emit(("table_changed",))
        self.analysis_stopper.setShouldStop(False)
        self.analysis_stopper.setIsRunning(False)
        return

    def performCavityParamsFitting_eKin(self,scorer,eKinIn):
        """ Fitting is done using eKinOut(cav_phase) data from BPMs """
        trialPoint = scorer.getTrialPoint()
        sum_diff2 = scorer.getScore(trialPoint)
        
        #---- Search algorithm from PyORBIT native package
        searchAlgorithm = SimplexSearchAlgorithm()
        
        maxIter = self.simplex_iter
        solverStopper = SolveStopperFactory.maxIterationStopper(maxIter)
        
        #max_time = 0.04
        #solverStopper = SolveStopperFactory.maxTimeStopper(max_time)
        
        class BestScoreListener(ScoreboardActionListener):
            def __init__(self):
                ScoreboardActionListener.__init__(self)
                
            def performAction(self,solver):
                scoreBoard = solver.getScoreboard()
                iteration = scoreBoard.getIteration()
                trialPoint = scoreBoard.getBestTrialPoint()
                print ("============= iter=",scoreBoard.getIteration()," best score=",scoreBoard.getBestScore())
                print (trialPoint.textDesciption()) 
        
        solver = Solver()
        solver.setAlgorithm(searchAlgorithm)
        solver.setStopper(solverStopper)
        
        #---- if we want to see the progress of fitting 
        #solver.getScoreboard().addBestScoreListener(BestScoreListener())           
        
        solver.solve(scorer,trialPoint)

        #----- this will set the trial point for best score to the harmonic_data
        trialPoint = solver.getScoreboard().getBestTrialPoint()
        best_score = scorer.getScore(trialPoint)
        return (best_score,trialPoint)
        
    def phaseScanAnalysis(self,eKin_guess,cav_wrapper):
        """ 
        Performs CCL4 phase scan analysis. Really, there is no scan, only
        BPMs' phases and amplitudes measured several times. We just want to 
        extract eKin_in and eKin_out values which are the same.
        """
        min_bpm_amp = self.bpm_min_amp_spin_box.value()
        #---- bpm_amp_phase_dic[BPM_Wrapper.getAlias()] = (FunctionAmp,FunctionPhase)
        bpm_amp_phase_dict = cav_wrapper.bpm_amp_phase_dict
        #---- Collecting only BPMs with good data 
        bpm_wrappers = []
        for bpm_wrapper in cav_wrapper.bpm_wrappers:
            (bpm_amp_func,bpm_phase_func) = bpm_amp_phase_dict[bpm_wrapper.getAlias()]
            bpm_amp_min = bpm_amp_func.getMinY()
            if(bpm_wrapper.isGood and (bpm_amp_min > min_bpm_amp) and bpm_wrapper.getPosition() > cav_wrapper.getPosition()):
                bpm_wrappers.append(bpm_wrapper)
        #-----------------------------------------------
        cav_wrapper.eKin_out_func.clean()
        n_cav_phase_points = bpm_amp_phase_dict[bpm_wrappers[0].getAlias()][1].getSize()
        bpm_positions = []
        bpm_offsets = []
        for bpm_wrapper in bpm_wrappers:
            bpm_positions.append(bpm_wrapper.getPosition())
            bpm_offsets.append(bpm_wrapper.getPhaseOffset())
        #-----------------------------------------------
        for cav_phase_ind in range(n_cav_phase_points):
            bpm_phases = []
            cav_phase = bpm_amp_phase_dict[bpm_wrappers[0].getAlias()][1].x(cav_phase_ind)
            for bpm_wrapper in bpm_wrappers:
                bpm_phase = bpm_amp_phase_dict[bpm_wrapper.getAlias()][1].y(cav_phase_ind)
                bpm_phases.append(bpm_phase)
            res_arr = self.energy_meter.fitEnergyFromBPMsPhases(eKin_guess,bpm_positions,bpm_phases,bpm_offsets)
            (eKin,eKin_err,phase_pos_func,phase_pos_fit_func) = res_arr
            cav_wrapper.eKin_out_func.add(cav_phase,eKin,eKin_err)

        
            

class CavityParamsScorer_eKinOut(Scorer):
    """
    The implementation of the abstract Score class 
    as eKinOut(cav_phase) vs cavity's parameters (amp., phase offset) scorer 
    between BPMs' data and the cavity model.
    """
    def __init__(self,cav_wrapper,eKinIn):
        self.cav_wrapper = cav_wrapper      
        self.model_cav = self.cav_wrapper.model_cav
        self.eKinIn = eKinIn
        self.eKin_out_func = self.cav_wrapper.eKin_out_func
        self.eKin_out_fit_func = self.cav_wrapper.eKin_out_fit_func
        (self.cav_phase_arr,self.eKInOut_BPMs_arr,error_arr) = self.eKin_out_func.getXYErrLists()
        self.eKInOut_model_arr = []
        
    def getCavityWrapper(self):
        return self.self.cav_wrapper
        
    def getModel_eKinOut_Arr(self):
        return self.eKInOut_model_arr
        
    def update_eKinOutFitFunction(self):
        if(len(self.cav_phase_arr) == len(self.eKInOut_model_arr)):
            self.eKin_out_fit_func.initFromLists(self.cav_phase_arr,self.eKInOut_model_arr)
        return self.eKin_out_fit_func
        
    def calcModel_eKinOut_Arr(self,eKinIn):
        (eKinOut_arr,timeOut_arr) = self.model_cav.trackEmptyBunch(eKinIn,self.cav_phase_arr)
        self.eKInOut_model_arr = eKinOut_arr
        return self.eKInOut_model_arr

    def printResults(self, file_name_prefix = None):
        self.calcModel_eKinOut_Arr(self.eKinIn)
        if(len(self.eKInOut_model_arr) != len(self.cav_phase_arr)): return
        print ("================================")
        cav_name = self.cav_wrapper.getName()
        print ("Cavity=",cav_name)
        st = " CavPhase[deg]   eKinOutBPM[MeV] eKinOutModel[MeV]  Diff[MeV]"
        print (st)
        #-------------------------------------------
        fl_out = None
        if(file_name_prefix != None):
            fl_out = open(file_name_prefix+ "_"+cav_name+"_eKinOut.dat","w")
            fl_out.write(st + "\n")
        #------------------------------------------_
        for ind,cav_phase in enumerate(self.cav_phase_arr):
            eKin_out_bpm = self.eKInOut_BPMs_arr[ind]
            eKin_out_model = self.eKInOut_model_arr[ind]
            diff = eKin_out_model - eKin_out_bpm
            st  = " %+6.1f "%cav_phase
            st += " %8.3f  %8.3f   %+8.4f"%(eKin_out_bpm,eKin_out_model,diff)
            print (st)
            if(fl_out != None): fl_out.write(st + "\n")
        if(fl_out != None): fl_out.close()
    
    def getTrialPoint(self):
        """
        Returns the trial point with cavity's amplitude and phase offset.
        """
        amp = self.model_cav.getModelAmp()
        #---- This is just for protection 
        if(amp == 0.): amp = 1.0
        cav_phase_offset = self.model_cav.getCavityPhaseOffset()
        #-------------------
        variableProxy_arr = []
        variableProxy_arr.append(VariableProxy("amp",amp,0.01*amp))
        variableProxy_arr.append(VariableProxy("phaseOffset",cav_phase_offset,1.0))
        #-------------------
        trialPoint = TrialPoint()
        for variableProxy in variableProxy_arr:
            trialPoint.addVariableProxy(variableProxy)
        return trialPoint
    
    def getScore(self,trialPoint):
        """
        Returns the score as sum_diff2.
        """
        value_arr = trialPoint.getVariableProxyValuesArr()
        amp = value_arr[0]
        cav_phase_offset = value_arr[1]
        self.model_cav.setModelAmp(amp)
        self.model_cav.setCavityPhaseOffset(cav_phase_offset)
        self.calcModel_eKinOut_Arr(self.eKinIn)
        diff2 = 0.
        for ind,cav_phase in enumerate(self.cav_phase_arr):
            eKin_out_bpm = self.eKInOut_BPMs_arr[ind]
            eKin_out_model = self.eKInOut_model_arr[ind]
            diff2 += (eKin_out_model - eKin_out_bpm)**2
        if(len(self.cav_phase_arr) > 0): diff2 /= len(self.cav_phase_arr) 
        return diff2
