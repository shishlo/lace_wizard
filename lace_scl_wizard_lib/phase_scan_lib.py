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
        self.cavs_table_view = self.cavs_scan_cntrl.cavs_table_view
        self.cavs_data_table_model = self.cavs_scan_cntrl.cavs_data_table_model
        self.scan_wait_time_spin_box = self.cavs_scan_cntrl.upper_panel_cntrl.scan_wait_time_spin_box
        self.max_sin_amp_err_spin_box = self.cavs_scan_cntrl.upper_panel_cntrl.max_sin_amp_err_spin_box
        self.bpm_min_amp_spin_box = self.cavs_scan_cntrl.bottom_panel_cntrl.bpm_min_amp_spin_box
        self.stat_for_in_enrg_spin_box = self.cavs_scan_cntrl.upper_panel_cntrl.stat_for_in_enrg_spin_box
        self.wrap_phase_button = self.cavs_scan_cntrl.upper_panel_cntrl.wrap_phase_button
        self.keep_phases_button = self.cavs_scan_cntrl.upper_panel_cntrl.keep_phases_button
        self.scan_stopper = self.cavs_scan_cntrl.scan_stopper
    
    @Slot()
    def run(self):
        """ Phase scan thread execution."""
        while(1 < 2):
            print ("debug start scan")
            time.sleep(1.0)
            if(self.scan_stopper.getShouldStop()):
                break
        self.scan_stopper.setShouldStop(False)
