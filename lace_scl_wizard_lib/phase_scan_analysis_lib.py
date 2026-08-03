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

from statistics_lib.statistics import fitCosineFunc, calculateAvgErr

from statistics_lib.statistics import fitHarmonicData

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
    def __init__(self,scan_analysis_cntrl,cav_wrappers, simplex_iter = 100):
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
        """ Scan analysis thread execution."""
        #---- Start analysis
        self.analysis_stopper.setIsRunning(True)
        #-------------------------------------------------
        if(len(self.cav_wrappers) == 0):
            msg_txt = "Please select cavity/cavities for analysis!"
            self.signals.analysis_data_changed.emit(("status_update",msg_txt))            
            self.analysis_stopper.setShouldStop(False)
            self.analysis_stopper.setIsRunning(False)
            return
        #--------------------------------------------------
        cav_start = self.cav_wrappers[0].getAlias()
        cav_stop = self.cav_wrappers[-1].getAlias()
        msg_txt = "Analysis started with cvity = " + cav_start + " to " + cav_stop
        self.signals.analysis_data_changed.emit(("status_update",msg_txt))
        iter_count = 0
        time_start = time.time()
        cavs_count = 0
        #self.signals.analysis_data_changed.emit(("table_selection_clear",))
        for cav_local_ind,cav_wrapper in enumerate(self.cav_wrappers):
            #---- cav index in the global table
            cav_ind = self.cavs_data_analysis_table_model.cav_wrappers.index(cav_wrapper)
            #---- 
            #---- May be we want to stop
            if(self.analysis_stopper.getShouldStop()):
                time_scan = time.time() - time_start
                self.analysis_stopper.setShouldStop(False)
                self.analysis_stopper.setIsRunning(False)
                self.cleanAllDownstreamCavities(cav_wrapper)
                msg_txt  = "Analysis stopped by user's request at cavity="
                msg_txt += cav_wrapper.getAlias()
                msg_txt += "    Run time[sec] = %7.0f    "%time_scan
                self.signals.analysis_data_changed.emit(("status_update",msg_txt))
                self.signals.analysis_data_changed.emit(("table_selection_set",cav_ind))
                self.signals.analysis_data_changed.emit(("table_changed",))
                return
            self.signals.analysis_data_changed.emit(("table_selection_set",cav_ind))
            #----------------------------------------------
            cav_start = cav_wrapper.getAlias()
            cav_stop = self.cav_wrappers[-1].getAlias()
            msg_txt = "Analysis cavity = " + cav_start + " to " + cav_stop
            if(cavs_count > 0):
                time_scan = time.time() - time_start
                one_cav_time = time_scan/cavs_count
                eta_time = one_cav_time*(len(self.cav_wrappers) - cavs_count)
                msg_txt += "    Run time[sec] = %7.0f    "%time_scan
                msg_txt += " ETA = %7.0f"%eta_time
            self.signals.analysis_data_changed.emit(("status_update",msg_txt))
            if(cav_wrapper.isGood == False):
                cav_wrapper_previous = self.cavs_data_analysis_table_model.cav_wrappers[cav_ind-1]
                cav_wrapper.E0TL = 15.0
                cav_wrapper.eKin_in = cav_wrapper_previous.eKin_out
                cav_wrapper.eKin_out = cav_wrapper_previous.eKin_out
                cav_wrapper.eKin_model_in = cav_wrapper_previous.eKin_model_out
                cav_wrapper.eKin_model_out = cav_wrapper_previous.eKin_model_out
                if((cav_ind + 1) != len(self.cavs_data_analysis_table_model.cav_wrappers)):
                    cav_wrapper_next = self.cavs_data_analysis_table_model.cav_wrappers[cav_ind+1]
                    cav_wrapper_next.eKin_in = cav_wrapper.eKin_out
                    cav_wrapper_next.eKin_model_in = cav_wrapper.eKin_model_out
                cav_wrapper.isAnalyzed = False
                continue
            #----------------------------------------------
            #---- we will skip cavity without measured data
            if(not cav_wrapper.isMeasured):
                time_scan = time.time() - time_start          
                self.analysis_stopper.setShouldStop(False)
                self.analysis_stopper.setIsRunning(False)
                self.cleanAllDownstreamCavities(cav_wrapper)
                msg_txt  = "Analysis stopped. No scan data for cavity="
                msg_txt += cav_wrapper.getAlias()
                msg_txt += " Cannot continue."
                msg_txt += " Run time[sec] = %7.0f"%time_scan                     
                self.signals.analysis_data_changed.emit(("status_update",msg_txt))
                self.signals.analysis_data_changed.emit(("table_selection_set",cav_ind))
                self.signals.analysis_data_changed.emit(("table_changed",)) 
                return
            #------------------------------------------------------------------
            #---- Here we start analysis of full array of BPMs data to get
            #---- functions eKinOut vs. cavity phase. We will consider set of 
            #---- BPMs for each cavity phase and use the energy meter to get
            #---- eKinOut for this phase.
            #---- As the result we will get cav_wrapper.eKin_out_func function.
            #------------------------------------------------------------------ 
            eKin_in_guess = cav_wrapper.eKin_in
            if(cav_start.find("CCL") >= 0):
                eKin_in_guess = 185.6
            #---- calculation of cav_wrapper.eKin_out_func from BPMs' data
            self.phaseScanAnalysis(eKin_in_guess,cav_wrapper,cav_wrapper.eKin_out_func)
            #------------------------------------------------------------------
            #---- Performing analysis - from here we assume that cav_wrapper
            #---- has eKin_out_func with data eKinOut vs cavity phase
            #---- We will use this function to get parameters of cavity model
            #---- and eKinOut for the next cavity as eKinIn.
            #------------------------------------------------------------------
            (amp1,avg_value,phase_min_pos,phase_max_pos,phase_fit_func_tmp) = fitHarmonicData(cav_wrapper.eKin_out_func,cav_wrapper.eKin_out_fit_func)
            E0TL = amp1
            cav_phase_offset = phaseNearTargetPhaseDeg(180.-phase_max_pos,0.)
            eKin_in_guess = avg_value
            cav_wrapper.synch_real_acc_phase = phaseNearTargetPhaseDeg(cav_wrapper.epicsPhase - phase_max_pos,0.)
            
            #---- ========== debug printing ============= START
            """
            st  = "debug  cav=" + cav_wrapper.getAlias()
            st += "  eKin_in=%8.3f"%eKin_in_guess
            st += " E0TL=%8.3f"%E0TL
            st += " cav_phase_offset=%+9.3f"%cav_phase_offset
            st += " synch_real_acc_phase=%+9.3f"%cav_wrapper.synch_real_acc_phase
            print (st)
            """
            #---- ========== debug printing ============= STOP
            
            #---- These are preliminary setting based on 1-st order harmonic of phase scan
            cav_wrapper.E0TL = E0TL
            cav_wrapper.eKin_in = eKin_in_guess
            self.spline.compile(cav_wrapper.eKin_out_fit_func)
            cav_wrapper.eKin_out = self.spline.getY(cav_wrapper.epicsPhase)
            #---- No further analysis for CCL4 cavity
            if(cav_start.find("CCL") >= 0):
                cav_wrapper.E0TL = 0.
                cav_wrapper.eKin_out = cav_wrapper.eKin_in
                cav_wrapper.eKin_model_out = cav_wrapper.eKin_in
                cav_wrapper.setModelCavityPhaseOffset(0.)
                cav_wrapper.isAnalyzed = True
                #---- Update information in the table for the cavity
                self.signals.analysis_data_changed.emit(("table_cavity_data_cahnged",cav_wrapper))
                continue
            #---- Fitting model parameters directly
            #---- Now we create the phase scan for the model to compare it to 
            #---- the real Cosine Fit for cav_wrapper.eKin_out_func
            cav_wrapper.setModelCavityPhaseOffset(0.)
            cav_wrapper.eKin_in = self.cavs_data_analysis_table_model.cav_wrappers[cav_ind-1].eKin_out
            scorer = CavityParamsScorer_eKinOut(cav_wrapper)
            #---- Let's get approximate sin-like eKinOut vs cav. phase function using the model
            #---- We will use E0TL_appr to correct cavity model amplitude according the E0TL_appr and cav_wrapper.E0TL
            scorer.calcModel_eKinOut_Arr(cav_wrapper.eKin_in)
            #---- This will rewrite the cav_wrapper.eKin_out_fit_func
            eKin_out_appr_model_func = scorer.update_eKinOutFitFunction()
            (E0TL_model,cav_phase_offset_model,eKin_in_guess_model) = fitCosineFunc(eKin_out_appr_model_func)
            #---- Fix the model amplitude - it will be closer to BPM data
            coeff_amp = cav_wrapper.E0TL/E0TL_model
            model_cav_amp = cav_wrapper.model_cav.getModelAmp()
            cav_wrapper.model_cav.setModelAmp(model_cav_amp*coeff_amp)
            #---- Fix the cavity phase offset - it will be closer to BPM data
            cav_phase_offset_model -= cav_phase_offset
            cav_wrapper.setModelCavityPhaseOffset(-cav_phase_offset_model)
            scorer.calcModel_eKinOut_Arr(cav_wrapper.eKin_in)
            scorer.update_eKinOutFitFunction()
            #---- Let's fit the cavity model parameters and put them into the model of cavity
            best_score, trialPoint = self.performCavityParamsFitting_eKin(scorer,cav_wrapper.eKin_in)
            [model_cav_amp,model_cav_phase_offset,eKin_in_fitted] = trialPoint.getVariableProxyValuesArr()
            cav_wrapper.eKin_in = eKin_in_fitted
            cav_wrapper.eKin_out_fit_delta_rms = math.sqrt(abs(best_score))
            #---- Let's update cav_wrapper.eKin_out_fit_func
            scorer.calcModel_eKinOut_Arr(cav_wrapper.eKin_in)
            scorer.update_eKinOutFitFunction()
            cav_wrapper.isAnalyzed = True
            cav_wrapper.modelAmp = cav_wrapper.model_cav.getModelAmp()
            cav_wrapper.model_cav.setEPICS_CavityModelPhase(cav_wrapper.epicsPhase)
            cav_wrapper.modelPhase =  phaseNearTargetPhaseDeg(cav_wrapper.model_cav.getModelPhase(),0.)     
            cav_wrapper.modelCoeffToEpicsAmp =  cav_wrapper.model_cav.getModelCoeffToEpicsAmp()
            #---- Tracking the synchronous particle through the model cavity
            cav_wrapper_previous = self.cavs_data_analysis_table_model.cav_wrappers[cav_ind-1]
            cav_wrapper.eKin_model_in = cav_wrapper_previous.eKin_model_out
            cav_wrapper.eKin_model_out = self.trackBunchThroughModel(cav_wrapper.eKin_model_in,cav_wrapper.epicsPhase,cav_wrapper)
            #---------------------------------------------------------------
            if( (cav_ind + 1) != len(self.cavs_data_analysis_table_model.cav_wrappers)):
                cav_wrapper_next = self.cavs_data_analysis_table_model.cav_wrappers[cav_ind+1]
                cav_wrapper_next.eKin_in = cav_wrapper.eKin_out
                cav_wrapper_next.eKin_model_in = cav_wrapper.eKin_model_out
            #---- Update information in the table for the cavity
            self.signals.analysis_data_changed.emit(("table_cavity_data_cahnged",cav_wrapper))
            cavs_count += 1
            #---- Stop scan analysis if requested
            if(self.analysis_stopper.getShouldStop()):
                time_scan = time.time() - time_start
                self.analysis_stopper.setShouldStop(False)
                self.analysis_stopper.setIsRunning(False)
                self.cleanAllDownstreamCavities(cav_wrapper)
                msg_txt  = "Analysis stopped by user's request at cavity="
                msg_txt += cav_wrapper.getAlias()
                msg_txt += "   Run time[sec] = %7.0f"%time_scan 
                self.signals.analysis_data_changed.emit(("status_update",msg_txt))
                self.signals.analysis_data_changed.emit(("table_selection_set",cav_ind))
                self.signals.analysis_data_changed.emit(("table_changed",))
                return
        #--------- END of SCAN
        time_scan = time.time() - time_start
        msg_txt  = "Analysis finished at cavity = "
        msg_txt += self.cav_wrappers[-1].getAlias() + ". "
        msg_txt += " Execution time[sec] = "+"%7.0f"%time_scan
        self.signals.analysis_data_changed.emit(("status_update",msg_txt))
        self.signals.analysis_data_changed.emit(("table_selection_clear",))
        cav_ind = self.cavs_data_analysis_table_model.cav_wrappers.index(self.cav_wrappers[-1])
        self.signals.analysis_data_changed.emit(("table_selection_set",cav_ind))
        self.signals.analysis_data_changed.emit(("table_changed",))       
        self.cleanAllDownstreamCavities(self.cav_wrappers[-1])
        self.analysis_stopper.setShouldStop(False)
        self.analysis_stopper.setIsRunning(False)
        return
        
    def cleanAllDownstreamCavities(self,cav_wrapper):
        """
        All downstream cavities analysis are invalid after 
        you change something at the top.
        """
        cav_ind = self.cavs_data_analysis_table_model.cav_wrappers.index(cav_wrapper)
        if(cav_ind >= (len(self.cavs_data_analysis_table_model.cav_wrappers) -1)):
            return
        for cav_wrapper_next in self.cavs_data_analysis_table_model.cav_wrappers[cav_ind+1:]:
            cav_wrapper_next.isAnalyzed = False
            cav_wrapper_next.eKin_out_func.clean()
            cav_wrapper_next.eKin_out_fit_func.clean()
            cav_wrapper_next.eKin_out_fit_delta_rms = 0.
            
    def trackBunchThroughModel(self,eKinIn,epicsPhase,cav_wrapper):
        """ 
        Tracking synchronous particle through the cavity to calculate output energy 
        """
        (eKinOut_arr,timeOut_arr) = cav_wrapper.model_cav.trackEmptyBunch(eKinIn,[epicsPhase,])
        return eKinOut_arr[0]

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

        #---- this will set the trial point for best score to 
        #---- the eKin_out vs cavity phase function from BPMs' data
        trialPoint = solver.getScoreboard().getBestTrialPoint()
        best_score = scorer.getScore(trialPoint)
        return (best_score,trialPoint)
        
    def phaseScanAnalysis(self,eKin_guess,cav_wrapper,eKin_out_local_func = None):
        """ 
        Performs phase scan analysis of BPMs phase for each phase of the cavity.
        It analyzes BPMs' phases and amplitudes created by freely moving beam.
        All downstream cavities are blanked. For each phase of active cavity 
        calculate the energy as this phase.
        """
        #---- bpm_amp_phase_dic[BPM_Wrapper.getAlias()] = (FunctionAmp,FunctionPhase)
        bpm_amp_phase_dict = cav_wrapper.bpm_amp_phase_dict
        #---- Collecting only BPMs with good data 
        bpm_wrappers = []
        bpm_wrappers_useInPhaseAnalysis = cav_wrapper.bpm_wrappers_useInPhaseAnalysis
        for bpm_wrapper_ind, bpm_wrapper in enumerate(cav_wrapper.bpm_wrappers):          
            (bpm_amp_func,bpm_phase_func) = bpm_amp_phase_dict[bpm_wrapper.getAlias()]
            bpm_amp_min = bpm_amp_func.getMinY()
            """
            #---- User should eliminate BPMs with small amplitudes in Phase Scan screen
            #---- by using the button "Apply BPM Amp. Limit", so we do not need this part here.
            min_bpm_amp = self.bpm_min_amp_spin_box.value()
            bpm_wrappers_useInPhaseAnalysis[bpm_wrapper_ind] = False
            if(bpm_wrapper.isGood and (bpm_amp_min > min_bpm_amp) and bpm_wrapper.getPosition() > cav_wrapper.getPosition()):
                bpm_wrappers.append(bpm_wrapper)
                bpm_wrappers_useInPhaseAnalysis[bpm_wrapper_ind] = True
            """
            if(bpm_wrappers_useInPhaseAnalysis[bpm_wrapper_ind]):
                bpm_wrappers.append(bpm_wrapper)
        #-----------------------------------------------
        if(eKin_out_local_func == None):
            eKin_out_local_func = Function()
        else:
            eKin_out_local_func.clean()
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
            #---- energy meter calculates the energy and error
            res_arr = self.energy_meter.fitEnergyFromBPMsPhases(eKin_guess,bpm_positions,bpm_phases,bpm_offsets)
            (eKin,eKin_err,phase_pos_func,phase_pos_fit_func) = res_arr
            eKin_out_local_func.add(cav_phase,eKin,eKin_err)
        return eKin_out_local_func

class CavityParamsScorer_eKinOut(Scorer):
    """
    The implementation of the abstract Score class 
    as eKinOut(cav_phase) vs cavity's parameters (amp., phase offset) scorer 
    between BPMs' data and the cavity model.
    """
    def __init__(self,cav_wrapper):
        self.cav_wrapper = cav_wrapper      
        self.model_cav = self.cav_wrapper.model_cav
        self.eKin_out_func = self.cav_wrapper.eKin_out_func
        self.eKin_out_fit_func = self.cav_wrapper.eKin_out_fit_func
        (self.cav_phase_arr,self.eKInOut_BPMs_arr,error_arr) = self.eKin_out_func.getXYErrLists()
        self.eKinIn = calculateAvgErr(self.eKInOut_BPMs_arr)[0]
        self.eKInOut_model_arr = []
        
    def getCavityWrapper(self):
        return self.self.cav_wrapper
        
    def getModel_eKinOut_Arr(self):
        return self.eKInOut_model_arr
        
    def get_eKinInFitted(self):
        return self.eKinIn 
        
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
        variableProxy_arr.append(VariableProxy("eKinIn",self.eKinIn,0.2))
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
        self.eKinIn = value_arr[2]
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
