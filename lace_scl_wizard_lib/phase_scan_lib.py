#--------------------------------------------------------------------------
# This is a library of phase scan classes that performing scan process,
# collecting bpm data, filtering them, and stop scans if necessary. 
#---------------------------------------------------------------------------
import time
import math

from orbit.core.orbit_utils import Function
# import the utilities
from orbit.utils import phaseNearTargetPhase, phaseNearTargetPhaseDeg

#---- Channel access
import epics

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Slot, Signal

from statistics_lib.statistics import fitCosineFunc, calculateAvgErr
from statistics_lib.statistics import fitHarmonicData

#------------------------------------------------------------------------
#           Auxiliary SCAN classes and functions
#------------------------------------------------------------------------   
class ScanStateController:
    """ This is the scan stopper """
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

class ScanWorkerSignals(QObject):
    """ Signals for updating tables, info-lines text, and plots """ 
    scan_data_changed = Signal(tuple)  

class PhaseScan_Runner(QRunnable):
    """ 
    It performs the phase scan selected or all cavities.
    It makes the preliminary analysis of the sin-like phase scans
    and sets the EPICS cavities phases according the requested 
    synchronous(accelerating) phase assigned to the cavity. 
    """
    def __init__(self,cavs_scan_cntrl,cav_wrappers):
        QRunnable.__init__(self)
        self.cavs_scan_cntrl = cavs_scan_cntrl
        self.cav_wrappers = cav_wrappers        
        self.cavs_phase_scan_cntrl = self.cavs_scan_cntrl.cavs_phase_scan_cntrl
        self.lace_scl_wizard = self.cavs_phase_scan_cntrl.lace_scl_wizard
        self.signals = self.cavs_scan_cntrl.scan_worker_signals
        #--------------------------------------
        self.cavs_table_view = self.cavs_scan_cntrl.cavs_table_view
        self.cavs_data_table_model = self.cavs_scan_cntrl.cavs_data_table_model
        #--------------------------------------
        self.scan_wait_time_spin_box = self.cavs_scan_cntrl.upper_panel_cntrl.scan_wait_time_spin_box
        self.phase_scan_step_spin_box = self.cavs_scan_cntrl.upper_panel_cntrl.phase_scan_step_spin_box
        self.max_sin_amp_err_spin_box = self.cavs_scan_cntrl.upper_panel_cntrl.max_sin_amp_err_spin_box
        self.bpm_min_amp_spin_box = self.cavs_scan_cntrl.bottom_panel_cntrl.bpm_min_amp_spin_box
        self.keep_phases_checkbox = self.cavs_scan_cntrl.upper_panel_cntrl.keep_phases_checkbox
        #---------------------------------------
        self.scan_stopper = self.cavs_scan_cntrl.scan_stopper
        self.scan_status_text = self.cavs_scan_cntrl.upper_panel_cntrl.scan_status_text
        self.statusLabel = self.lace_scl_wizard.getStatusLabel()
        self.setAutoDelete(True)
        #self.statusLabel.setStyleSheet("color: red;")
        
    def blankCavities(self,cav_ind_start):
        cav_wrappers = self.cavs_data_table_model.cav_wrappers
        for cav_ind,cav_wrapper in enumerate(cav_wrappers):
            if(cav_wrapper.isGood == False): continue
            blanking = False
            if(cav_ind > cav_ind_start): blanking = True
            if(cav_wrapper.getAlias() != "CCL4"):
                cav_wrapper.setCavityEPICS_Blanking(blanking)
                cav_wrapper.model_cav.setCavityModelBlanking(blanking)
            
    def initAmpPhaseFunctions(self,cav_wrapper):
        #cav_wrapper.bpm_amp_phase_dict = {}
        for bpm_wrapper in cav_wrapper.bpm_wrappers:
            (bpm_amp_func,bpm_amp_func) = cav_wrapper.bpm_amp_phase_dict[bpm_wrapper.getAlias()]
            bpm_amp_func.clean()
            bpm_amp_func.clean()
            #cav_wrapper.bpm_amp_phase_dict[bpm_wrapper.getAlias()] = (Function(),Function())

    def measureBPMsVsCavPhase(self,cav_wrapper,cav_phase):
        #---- fake phase scan function -------------------------
        def fakeAmpPhaseBPM(cav_phase, bpm_pos):
            bpm_amp = 30.
            bpm_phase = (bpm_pos/50.)*math.sin(cav_phase*math.pi/180.)
            return (bpm_amp,bpm_phase)
        #--------------------------------------------------------    
        bpm_amp_phase_dict = cav_wrapper.bpm_amp_phase_dict
        bpm_wrappers = []
        for bpm_wrapper in cav_wrapper.bpm_wrappers:
            if(bpm_wrapper.isGood): bpm_wrappers.append(bpm_wrapper)
        bpm_amp_pvs = [bpm_wrapper.getAmpPV() for bpm_wrapper in bpm_wrappers]
        bpm_phase_pvs = [bpm_wrapper.getPhasePV() for bpm_wrapper in bpm_wrappers]
        amp_vals = [bpm_amp_pv.get() for bpm_amp_pv in bpm_amp_pvs]
        phase_vals = [bpm_phase_pv.get() for bpm_phase_pv in bpm_phase_pvs]
        bpm_phase0 = 0.
        bpm_phase1 = 0.
        for bpm_ind,bpm_wrapper in enumerate(bpm_wrappers):
            amp = amp_vals[bpm_ind]
            phase = phase_vals[bpm_ind]
            #---- Fake phases for BPMs
            #(amp,phase) = fakeAmpPhaseBPM(cav_phase,bpm_wrapper.getPosition())
            (amp_func,phase_func) = cav_wrapper.bpm_amp_phase_dict[bpm_wrapper.getAlias()]
            amp_func.add(cav_phase,amp)
            phase_func.add(cav_phase,phase)
            if(cav_wrapper.bpm_wrapper0 == bpm_wrapper): bpm_phase0 = phase
            if(cav_wrapper.bpm_wrapper1 == bpm_wrapper): bpm_phase1 = phase
            #print ("debug bpm=",bpm_wrapper.getAlias()," phase=",phase," amp",amp)
        #---------------------------------------
        phase_diff = phaseNearTargetPhaseDeg(bpm_phase1,bpm_phase0) - bpm_phase0
        cav_wrapper.phaseDiffBPM01_func.add(cav_phase,phase_diff)
        
    def recalculatePhaseDiffData(self,cav_wrapper):
        bpm_wrapper0 = cav_wrapper.bpm_wrapper0
        bpm_wrapper1 = cav_wrapper.bpm_wrapper1
        (amp_func0,phase_func0) = cav_wrapper.bpm_amp_phase_dict[bpm_wrapper0.getAlias()]
        (amp_func1,phase_func1) = cav_wrapper.bpm_amp_phase_dict[bpm_wrapper1.getAlias()]
        cav_wrapper.phaseDiffBPM01_func.clean()
        for cav_phase_ind in range(phase_func0.getSize()):
            cav_phase = phase_func0.x(cav_phase_ind)
            phase0 = phase_func0.y(cav_phase_ind)
            phase1 = phase_func1.y(cav_phase_ind)
            cav_wrapper.phaseDiffBPM01_func.add(cav_phase,phase1 - phase0)
        
    def wrappAllPhasesForBPMs(self,cav_wrapper):
        if(cav_wrapper.getAlias() == "CCL4"):
            return True
        # it will wrap all BPM phases for the cvity by iteration from the BPM closest to cavity
        cav_pos = cav_wrapper.getPosition()
        min_bpm_amp = self.bpm_min_amp_spin_box.value()
        #---- (amp_func,phase_func) = cav_wrapper.bpm_amp_phase_dict[bpm_wrapper.getAlias()]
        bpm_amp_phase_dict = cav_wrapper.bpm_amp_phase_dict
        bpm_wrappers = []
        for bpm_wrapper in cav_wrapper.bpm_wrappers:
            if(bpm_wrapper.isGood and bpm_wrapper.getPosition() > cav_pos):
                (amp_func,phase_func) = cav_wrapper.bpm_amp_phase_dict[bpm_wrapper.getAlias()]
                if(amp_func.getMinY() < min_bpm_amp): continue
                bpm_wrappers.append(bpm_wrapper)
        for bpm_ind in range(len(bpm_wrappers)-1):
            (amp_func0,phase_func0) = cav_wrapper.bpm_amp_phase_dict[bpm_wrappers[bpm_ind].getAlias()]
            (amp_func1,phase_func1) = cav_wrapper.bpm_amp_phase_dict[bpm_wrappers[bpm_ind+1].getAlias()]
            if(amp_func0.getSize() != amp_func1.getSize()): return False
            (x_arr,y_arr,err_arr) = phase_func1.getXYErrLists()
            base_phase_diff = y_arr[0] - phase_func0.y(0)
            for ip in range(1,phase_func0.getSize()):
                y0 = phase_func0.y(ip)
                y_arr[ip] = phaseNearTargetPhaseDeg(y_arr[ip],y0+base_phase_diff)
                base_phase_diff = y_arr[ip] - y0
            #move all data by 360. to make the avg close to 0.
            y_avg = 0.
            for y in y_arr:
                y_avg += y
            if(len(y_arr) > 1): y_avg /= len(y_arr)
            y_shift = int(y_avg/360.)*360.
            for ip in range(len(y_arr)):
                y_arr[ip] -= y_shift
            #--- update all bpm phases
            phase_func1.initFromLists(x_arr,y_arr,err_arr)   
        # recreate phase difference
        self.recalculatePhaseDiffData(cav_wrapper)
        return True
        
    def setNewEPICS_CavityPhase(self,cav_wrapper):
        """
        Performs analysis of cav_wrapper.phaseDiffBPM01_func to set a new
        EPICS phase of the cavity to get the requested synchronous 
        (acceleration) phase.
        """
        if(cav_wrapper.getAlias() == "CCL4"):
            return True
        phaseDiffBPM01_func = cav_wrapper.phaseDiffBPM01_func
        phaseDiffBPM01_fit_func = cav_wrapper.phaseDiffBPM01_fit_func
        (sin_amp,avg_value,phase_min_pos,phase_max_pos,func_tmp) = fitHarmonicData(phaseDiffBPM01_func,phaseDiffBPM01_fit_func)
        cav_wrapper.sin_phase_func_amp = sin_amp
        max_err = 0.
        for ind in range(phaseDiffBPM01_func.getSize()):
            diff = abs(phaseDiffBPM01_func.y(ind) - phaseDiffBPM01_fit_func.y(ind))
            if(diff > max_err): max_err = diff
        cav_wrapper.sin_phase_func_amp_err = max_err
        max_sin_amp_err = self.max_sin_amp_err_spin_box.value()
        if(max_err > max_sin_amp_err):
            return False
        #---- Set epics phase
        keep_phases = self.keep_phases_checkbox.isChecked()
        epicsPhase = 0.
        if(keep_phases):
            epicsPhase = cav_wrapper.epicsPhaseInit
            cav_wrapper.synch_acc_phase = phaseNearTargetPhaseDeg(epicsPhase - phase_min_pos,0.)
        else:
            epicsPhase = phaseNearTargetPhaseDeg(cav_wrapper.synch_acc_phase + phase_min_pos,0.)
            #print ("cav=",cav_wrapper.getAlias(),"phase_offset = ",phase_offset," new_phase=",epicsPhase)
        cav_wrapper.setEPICS_CavityPhase(epicsPhase)
        return True
            
    @Slot()
    def run(self):
        """ Phase scan thread execution."""
        self.scan_stopper.setIsRunning(True)
        #-------------------------------------------
        cav_start = self.cav_wrappers[0].getAlias()
        cav_stop = self.cav_wrappers[-1].getAlias()
        msg_txt = "Phase scan started with cvity = " + cav_start + " to " + cav_stop
        self.signals.scan_data_changed.emit(("status_update",msg_txt))
        phase_step = self.phase_scan_step_spin_box.value()
        sleep_time = self.scan_wait_time_spin_box.value()
        min_bpm_amp = self.bpm_min_amp_spin_box.value()
        iter_count = 0
        time_start = time.time()
        cavs_count = 0
        self.signals.scan_data_changed.emit(("table_selection_clear",))
        for cav_wrapper in self.cav_wrappers:
             #---- cav index in the table
            cav_ind = self.cavs_data_table_model.cav_wrappers.index(cav_wrapper)           
            self.signals.scan_data_changed.emit(("clean_bpm_phases_plot",cav_wrapper))
            self.signals.scan_data_changed.emit(("update_bpm_phases_plot",cav_wrapper))
            cav_start = cav_wrapper.getAlias()
            scav_stop = self.cav_wrappers[-1].getAlias()
            msg_txt = "Phase scan started with cavity = " + cav_start + " to " + cav_stop
            if(cavs_count > 0):
                time_scan = time.time() - time_start
                one_cav_time = time_scan/cavs_count
                eta_time = one_cav_time*(len(self.cav_wrappers) - cavs_count)
                msg_txt += "    Run time[sec] = %7.1f    "%time_scan
                msg_txt += " ETA = %7.1f"%eta_time            
            self.signals.scan_data_changed.emit(("status_update",msg_txt))
            if(cav_wrapper.isGood == False): 
                cav_wrapper.isMeasured = False
                cav_wrapper.isAnalyzed = False               
                continue
            #---- clean all plots and data for scan
            self.initAmpPhaseFunctions(cav_wrapper)
            self.signals.scan_data_changed.emit(("table_selection_set",cav_ind))
            #---- Check if cavity not fully up to the goal amplitude
            cav_amp = cav_wrapper.getEPICS_CavityAmp()
            cav_amp_goal = cav_wrapper.getEPICS_CavityAmp()
            if(abs(cav_amp-cav_amp_goal) > 0.01):
                time_scan = time.time() - time_start          
                self.scan_stopper.setShouldStop(False)
                self.scan_stopper.setIsRunning(False)
                msg_txt  = "Scan stopped. Cavity="
                msg_txt += cav_wrapper.getAlias()
                msg_txt += " Amp != AmpGoal   "
                msg_txt += " %6.3f != %6.3f "%(cav_amp,cav_amp_goal)
                msg_txt += "  Run time[sec] = %7.1f"%time_scan                     
                self.signals.scan_data_changed.emit(("status_update",msg_txt))
                self.signals.scan_data_changed.emit(("table_selection_set",cav_ind))
                self.signals.scan_data_changed.emit(("table_changed",)) 
                return
            #---- Set all downstream cavities blanked
            self.blankCavities(cav_ind)
            #---- start phase scan process for this cavity
            cav_phase_init = cav_wrapper.getEPICS_CavityPhase()
            cav_phase = -180.
            while(cav_phase <= 180.):
                if(self.scan_stopper.getShouldStop()):
                    time_scan = time.time() - time_start
                    self.scan_stopper.setShouldStop(False)
                    self.scan_stopper.setIsRunning(False)
                    if(cav_wrapper.getAlias() != "CCL4"):
                        cav_wrapper.setEPICS_CavityPhase(cav_phase_init)
                    time.sleep(sleep_time)
                    msg_txt = "Stopped by user's request at cavity = "
                    msg_txt += cav_wrapper.getAlias()
                    msg_txt += " phase= %+6.1f"%cav_phase
                    msg_txt += " Run time[sec] = %7.1f"%time_scan
                    self.signals.scan_data_changed.emit(("status_update",msg_txt))
                    self.signals.scan_data_changed.emit(("table_selection_set",cav_ind))
                    return
                #------------------------------------------
                if(cav_wrapper.getAlias() != "CCL4"):
                    cav_wrapper.setEPICS_CavityPhase(cav_phase)
                time.sleep(sleep_time)
                self.measureBPMsVsCavPhase(cav_wrapper,cav_phase)
                self.signals.scan_data_changed.emit(("update_bpm_phases_plot",cav_wrapper))
                cav_phase += phase_step
            if(cav_wrapper.getAlias() != "CCL4"):
                cav_wrapper.setEPICS_CavityPhase(cav_phase_init)
            result = self.wrappAllPhasesForBPMs(cav_wrapper)
            result_err_bool = self.setNewEPICS_CavityPhase(cav_wrapper)
            self.signals.scan_data_changed.emit(("update_bpm_phases_plot",cav_wrapper))         
            cav_wrapper.isMeasured = True
            self.signals.scan_data_changed.emit(("table_cavity_data_cahnged",cav_wrapper))
            time.sleep(sleep_time)
            if(not result_err_bool):
                time_scan = time.time() - time_start          
                self.scan_stopper.setShouldStop(False)
                self.scan_stopper.setIsRunning(False)
                msg_txt  = "Scan stopped. Cavity="
                msg_txt += cav_wrapper.getAlias()
                msg_txt += " Errors for sin-fiiting are too big! "
                msg_txt += " Run time[sec] = %7.1f"%time_scan                     
                self.signals.scan_data_changed.emit(("status_update",msg_txt))
                self.signals.scan_data_changed.emit(("table_selection_set",cav_ind))
                self.signals.scan_data_changed.emit(("table_changed",)) 
                return                
            #--------------
            cavs_count += 1
        #--------- END of SCAN
        time_scan = time.time() - time_start
        msg_txt = "Phase scan finished. Time[sec] = "+"%7.1f"%time_scan
        self.signals.scan_data_changed.emit(("status_update",msg_txt))
        self.signals.scan_data_changed.emit(("table_changed"))
        self.scan_stopper.setShouldStop(False)
        self.scan_stopper.setIsRunning(False)
        return
           