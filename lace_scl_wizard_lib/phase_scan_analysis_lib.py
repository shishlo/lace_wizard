#--------------------------------------------------------------------------
# This is a library of phase scan analysis classes.
# Analysis will be perfomed for all or selected SCL cavities
# to find cavities and their Low Level RF systems parameters. 
# Analysis can be stopped at any time. 
#---------------------------------------------------------------------------
import time
import math

from orbit.core.orbit_utils import Function
# import the utilities
from orbit.utils import phaseNearTargetPhase, phaseNearTargetPhaseDeg

#---- Channel access
import epics

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Slot, Signal

from .energy_meter_lib import EnergyMeter

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
    def __init__(self,scan_analysis_cntrl,cav_wrappers):
        QRunnable.__init__(self)
        self.scan_analysis_cntrl = scan_analysis_cntrl
        self.cav_wrappers = cav_wrappers        
        self.cavs_phase_scan_cntrl = self.scan_analysis_cntrl.cavs_phase_scan_cntrl
        self.cavs_scan_cntrl = self.cavs_phase_scan_cntrl.cavs_scan_cntrl
        self.lace_scl_wizard = self.cavs_phase_scan_cntrl.lace_scl_wizard
        self.signals = self.scan_analysis_cntrl.analysis_worker_signals
        #--------------------------------------
        self.cavs_table_view = self.scan_analysis_cntrl.cavs_table_view
        self.cavs_data_analysis_table_model = self.scan_analysis_cntrl.cavs_data_analysis_table_model
        #---------------------------------------
        self.bpm_min_amp_spin_box = self.cavs_scan_cntrl.bottom_panel_cntrl.bpm_min_amp_spin_box
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
        for cav_wrapper in self.cav_wrappers:
            cav_start = cav_wrapper.getAlias()
            scav_stop = self.cav_wrappers[-1].getAlias()
            msg_txt = "Analysis started with cvity = " + cav_start + " to " + cav_stop
            self.signals.analysis_data_changed.emit(("status_update",msg_txt))
            #---- cav index in the table
            cav_ind = self.cavs_data_analysis_table_model.cav_wrappers.index(cav_wrapper)
            self.signals.analysis_data_changed.emit(("table_selection_clear",))
            if(cav_wrapper.isGood == False): continue
            self.signals.analysis_data_changed.emit(("table_selection_set",cav_ind))
            #---- perform analysis
            eKin_guess = cav_wrapper.eKin_guess
            time.sleep(0.5)
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
           