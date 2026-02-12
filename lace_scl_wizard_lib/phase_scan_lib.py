#--------------------------------------------------------------------------
# This is a library of phase scan classes that performing scan process,
# collecting bpm data, filtering them, and stop scans if necessary. 
#---------------------------------------------------------------------------
import time

from orbit.core.orbit_utils import Function

#---- Channel access
import epics

from PySide6.QtCore import QRunnable, QThreadPool, QTimer, Slot

from .energy_meter_lib import EnergyMeter

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
        #--------------------------------------
        self.cavs_table_view = self.cavs_scan_cntrl.cavs_table_view
        self.cavs_data_table_model = self.cavs_scan_cntrl.cavs_data_table_model
        #--------------------------------------
        self.scan_wait_time_spin_box = self.cavs_scan_cntrl.upper_panel_cntrl.scan_wait_time_spin_box
        self.phase_scan_step_spin_box = self.cavs_scan_cntrl.upper_panel_cntrl.phase_scan_step_spin_box
        self.max_sin_amp_err_spin_box = self.cavs_scan_cntrl.upper_panel_cntrl.max_sin_amp_err_spin_box
        self.bpm_min_amp_spin_box = self.cavs_scan_cntrl.bottom_panel_cntrl.bpm_min_amp_spin_box
        self.stat_for_in_enrg_spin_box = self.cavs_scan_cntrl.upper_panel_cntrl.stat_for_in_enrg_spin_box
        self.wrap_phase_button = self.cavs_scan_cntrl.upper_panel_cntrl.wrap_phase_button
        self.keep_phases_button = self.cavs_scan_cntrl.upper_panel_cntrl.keep_phases_button
        self.eKin_measure_button = self.cavs_scan_cntrl.upper_panel_cntrl.eKin_measure_button
        #---------------------------------------
        self.scan_stopper = self.cavs_scan_cntrl.scan_stopper
        self.scan_status_text = self.cavs_scan_cntrl.upper_panel_cntrl.scan_status_text
        self.statusLabel = self.lace_scl_wizard.getStatusLabel()
        #self.statusLabel.setStyleSheet("color: red;")
        
    def blankCavities(self,cav_ind_start):
        cav_wrappers = self.cavs_data_table_model.cav_wrappers
        for cav_ind,cav_wrapper in enumerate(cav_wrappers):
            if(cav_wrapper.isGood == False): continue
            blanking = False
            if(cav_ind >= cav_ind_start): blanking = True
            #cav_wrapper.setCavityEPICS_Blanking(blanking)
            #cav_wrapper.cav_model.setCavityModelBlanking(blanking)
            
    def initAmpPhaseFunction(self,cav_wrapper):
        cav_wrapper.bpm_amp_phase_dict = {}
        for bpm_wrapper in cav_wrapper.bpm_wrappers:
            cav_wrapper.bpm_amp_phase_dict[bpm_wrapper.getAlias()] = (Function(),Function())
            if(not bpm_wrapper.connectPVs()): bpm_wrapper.isGood = False

    def measureBPMsVsCavPhase(self,cav_wrapper,cav_phase):
        bpm_amp_phase_dict = cav_wrapper.bpm_amp_phase_dict
        bpm_wrappers = []
        for bpm_wrapper in cav_wrapper.bpm_wrappers:
            if(bpm_wrapper.isGood): bpm_wrappers.append(bpm_wrapper)
        bpm_amp_pvs = [bpm_wrapper.getAmpPV() for bpm_wrapper in bpm_wrappers]
        bpm_phase_pvs = [bpm_wrapper.getPhasePV() for bpm_wrapper in bpm_wrappers]
        amp_vals = [bpm_amp_pv.get() for bpm_amp_pv in bpm_amp_pvs]
        phase_vals = [bpm_phase_pv.get() for bpm_phase_pv in bpm_phase_pvs]
        for bpm_ind,bpm_wrapper in enumerate(bpm_wrappers):
            amp = amp_vals[bpm_ind]
            phase = phase_vals[bpm_ind]
            (amp_func,phase_func) = cav_wrapper.bpm_amp_phase_dict[bpm_wrapper.getAlias()]
            amp_func.add(cav_phase,amp)
            phase_func.add(cav_phase,phase)
   
    @Slot()
    def run(self):
        """ Phase scan thread execution."""
        cav_start = self.cav_wrappers[0].getAlias()
        cav_stop = self.cav_wrappers[-1].getAlias()
        self.scan_status_text.setText("Phase scan started with cvity = " + cav_start + " to " + cav_stop)
        self.cavs_table_view.clearSelection()
        phase_step = self.phase_scan_step_spin_box.value()
        sleep_time = self.scan_wait_time_spin_box.value()
        bpm_sleep_time = 1.1
        n_pulses = int(self.stat_for_in_enrg_spin_box.value())
        min_bpm_amp = self.bpm_min_amp_spin_box.value()
        iter_count = 0
        time_start = time.time()
        for cav_wrapper in self.cav_wrappers:
            print ("debug init cav=",cav_wrapper.getAlias()," state=",cav_wrapper.isGood)        
        for cav_wrapper in self.cav_wrappers:
            cav_start = cav_wrapper.getAlias()
            scav_stop = self.cav_wrappers[-1].getAlias()
            self.scan_status_text.setText("Phase scan cavities from = " + cav_start + " to " + cav_stop)
            #---- cav index in the table
            cav_ind = self.cavs_data_table_model.cav_wrappers.index(cav_wrapper)
            self.cavs_table_view.clearSelection()
            if(cav_wrapper.isGood == False): continue
            self.cavs_table_view.selectRow(cav_ind)
            #---- collect statistics for energy measurents
            if(self.eKin_measure_button.isChecked()):
                self.blankCavities(cav_ind)
                eKin_guess = cav_wrapper.eKin_guess
                energy_meter = self.lace_scl_wizard.getEneryMeter()
                (eKin, eKin_err, bpm_wrappers, amp_pos_func, phase_pos_func, *rest) = energy_meter.measureEnergy(cav_wrapper,eKin_guess,n_pulses,bpm_sleep_time,min_bpm_amp)
                if(self.scan_stopper.getShouldStop() or abs(eKin) < 0.1 ):
                    if(self.scan_stopper.getShouldStop()): self.scan_status_text.setText("Phase scan stopped by user request.")
                    if(abs(eKin) < 0.1): self.scan_status_text.setText("Phase scan stopped with error. Cav="+cav_start)
                    self.scan_stopper.setShouldStop(False)
                    self.scan_stopper.setIsRunning(False)
                    return
                cav_wrapper.eKin_guess = eKin
                cav_wrapper.eKin_guess_err = eKin_err
                cav_wrapper.bpm_amp_phase_in_funcions = (amp_pos_func, phase_pos_func)
                self.blankCavities(cav_ind + 1)
            #---- scan process
            self.initAmpPhaseFunction(cav_wrapper)
            cav_phase_init = cav_wrapper.getEPICS_CavityPhase()
            cav_phase = -180.
            while(cav_phase <= 180.):
                if(self.scan_stopper.getShouldStop()):
                    self.scan_stopper.setShouldStop(False)
                    self.scan_stopper.setIsRunning(False)
                    #cav_wrapper.setEPICS_CavityPhase(cav_phase_init)
                    return
                #cav_wrapper.setEPICS_CavityPhase(cav_phase)
                time.sleep(sleep_time)
                self.measureBPMsVsCavPhase(cav_wrapper,cav_phase)
                print ("debug phase =",cav_phase)
                cav_phase += phase_step
            #cav_wrapper.setEPICS_CavityPhase(cav_phase_init)
            cav_wrapper.isMeasured = True
        #--------- END of SCAN
        self.cavs_scan_cntrl.cavs_data_table_model.tableChanged()
        for cav_wrapper in self.cav_wrappers:
            print ("debug cav=",cav_wrapper.getAlias()," state=",cav_wrapper.isGood)
        time_scan = time.time() - time_start
        self.scan_status_text.setText("Phase scan finished. Time[sec] = "+"%7.1f"%time_scan)
        self.scan_stopper.setShouldStop(False)
        self.scan_stopper.setIsRunning(False)
        return
           