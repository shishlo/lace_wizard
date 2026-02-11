#--------------------------------------------------------------------------
# This is a library of phase scan classes that performing scan process,
# collecting bpm data, filtering them, and stop scans if necessary. 
#---------------------------------------------------------------------------

import time

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
            cav_wrapper.setCavityEPICS_Blanking(blanking)
            #cav_wrapper.cav_model.setCavityModelBlanking(blanking)
            
    @Slot()
    def run(self):
        """ Phase scan thread execution."""
        cav_start = self.cav_wrappers[0].getAlias()
        cav_stop = self.cav_wrappers[-1].getAlias()
        self.scan_status_text.setText("Phase scan started with cvity = " + cav_start + " to " + cav_stop)
        self.cavs_table_view.clearSelection()
        phase_step = self.phase_scan_step_spin_box.value()
        sleep_time = self.scan_wait_time_spin_box.value()
        n_pulses = int(self.stat_for_in_enrg_spin_box.value())
        min_bpm_amp = self.bpm_min_amp_spin_box.value()
        iter_count = 0
        time_start = time.time()
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
                (eKin, eKin_err, *rest) = energy_meter.measureEnergy(cav_wrapper,eKin_guess,n_pulses,1.1,min_bpm_amp)
                if(self.scan_stopper.getShouldStop() or abs(eKin) < 0.1 ):
                    self.scan_status_text.setText("Phase scan stopped with error.")
                    self.scan_stopper.setShouldStop(False)
                    self.scan_stopper.setIsRunning(False)
                    return
                cav_wrapper.eKin_guess = eKin
                self.blankCavities(cav_ind + 1)
            #---- scan process
            cav_phase = -180.
            while(cav_phase <= 180.):
                if(self.scan_stopper.getShouldStop()):
                    self.scan_stopper.setShouldStop(False)
                    self.scan_stopper.setIsRunning(False)
                    return
                time.sleep(sleep_time)
                print ("debug phase =",cav_phase)
                cav_phase += phase_step
            time.sleep(1.0)
