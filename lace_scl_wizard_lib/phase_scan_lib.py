#--------------------------------------------------------------------------
# This is a library of phase scan classes that performing scan process,
# collecting bpm data, filtering them, and stop scans if necessary. 
#---------------------------------------------------------------------------

import time

#---- Channel access
import epics

from PySide6.QtCore import QRunnable, QThreadPool, QTimer, Slot

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
        self.max_sin_amp_err_spin_box = self.cavs_scan_cntrl.upper_panel_cntrl.max_sin_amp_err_spin_box
        self.bpm_min_amp_spin_box = self.cavs_scan_cntrl.bottom_panel_cntrl.bpm_min_amp_spin_box
        self.stat_for_in_enrg_spin_box = self.cavs_scan_cntrl.upper_panel_cntrl.stat_for_in_enrg_spin_box
        self.wrap_phase_button = self.cavs_scan_cntrl.upper_panel_cntrl.wrap_phase_button
        self.keep_phases_button = self.cavs_scan_cntrl.upper_panel_cntrl.keep_phases_button
        #---------------------------------------
        self.scan_stopper = self.cavs_scan_cntrl.scan_stopper
        self.statusLabel = self.lace_scl_wizard.getStatusLabel()
        
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
        self.cavs_table_view.clearSelection()
        sleep_time = self.scan_wait_time_spin_box.value()
        iter_count = 0
        time_start = time.time()
        for cav_wrapper in self.cav_wrappers:
            #---- cav index in the table
            cav_ind = self.cavs_data_table_model.cav_wrappers.index(cav_wrapper)
            self.cavs_table_view.clearSelection()
            if(cav_wrapper.isGood == False): continue
            self.cavs_table_view.selectRow(cav_ind)
            #---- collect statistics for energy measurents
            self.blankCavities(cav_ind)
            n_energy_iters = int(self.stat_for_in_enrg_spin_box.value())
            for it_ind in range(n_energy_iters):
                pass   
            #---- scan process
            cav_phase = -180.
            while( cav_phase <= 180.):
                pass
            time.sleep(1.0)
            
        
        
        count = 0
        while(1 < 2):
            print ("debug start scan")
            self.statusLabel.setText("Wizard is running. Count="+str(count))
            time.sleep(1.0)
            if(count % 2 == 0):
                self.statusLabel.setStyleSheet("color: red;")
            else:
                self.statusLabel.setStyleSheet("color: black;")
            count += 1
            if(self.scan_stopper.getShouldStop()):
                break
        self.scan_stopper.setShouldStop(False)
