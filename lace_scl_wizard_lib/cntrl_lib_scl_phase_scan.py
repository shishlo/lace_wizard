"""
Controller for SCL cavities phase scans and analysis. After analysis we 
will have the calibrated Online Model for SCL.
"""
import sys

from PySide6.QtWidgets import (
    QFrame,
    QTableWidget,
    QTableView,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton,
    QWidget,
    QTabWidget,
    QProgressBar,
    QMainWindow,
    QHeaderView,
    QPlainTextEdit,
    QCheckBox
    )

from PySide6.QtCore import (
    Qt,Slot,
    QRunnable, QObject, QThreadPool, Slot,
    QAbstractTableModel,
    QSize
    )

from PySide6.QtGui import (
    QStandardItemModel, QStandardItem,
    QTextDocument,
    QIcon
    )

from gui_lib.borderlayout import BorderLayout, Position
from gui_lib.style_sheets_lib import StyleSheetFactory
from gui_lib.table_view_model_lib import LACE_QTableView, LACE_DataTableModel
from .wrappers_cavs_bpms_magnets import Cavity_Wrapper, BPM_Wrapper

#----------------------------------------------------------
# Custom QtWidgets
#----------------------------------------------------------

#----------------------------------------------------------
# Internal Sub - Controllers
#----------------------------------------------------------

class Cavs_Scan_Cntrl:
    """
    Controller for RF Cavities phase scan.
    """
    def __init__(self,cavs_phase_scan_cntrl):
        self.cavs_phase_scan_cntrl = cavs_phase_scan_cntrl
        self.lace_scl_wizard = self.cavs_phase_scan_cntrl.lace_scl_wizard
        self.model_cavs = self.lace_scl_wizard.getOM().getModelCavs()
        self.cav_wrappers = self.lace_scl_wizard.getCavWrappers()
        self.bpm_wrappers = self.lace_scl_wizard.getBPM_Wrappers()
        #---- main widget
        self.mainWidget = QFrame(self.cavs_phase_scan_cntrl.tabs)
        #---- tab name
        self.tab_name = "SCL Phase Scan"
        #---- 
        
        #---- The QWidget with Cavities and BPMs tables
        self.cavs_table_view = LACE_QTableView()
        self.cavs_data_table_model = CavsScanDataTableModel(self)
        self.cavs_table_view.setModel(self.cavs_data_table_model)
        #self.cavs_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.cavs_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        #---- upper panel 
        upper_panel = UpperScanPanel(self.cavs_phase_scan_cntrl)
        
        #---- Border Layout for self.cavs_scan_cntrl
        border_layout = BorderLayout(None)

        border_layout.addWidget(self.cavs_table_view , Position.Center)
        #border_layout.addWidget(self.???, Position.West)
        border_layout.addWidget(upper_panel.getMainWidget(), Position.North)
        self.getMainWidget().setLayout(border_layout)        

    def getTabName(self):
        """ Returns the tab name the controller """
        return self.tab_name
        
    def getMainWidget(self):
        """ Returns the mainWidget (window) """
        return self.mainWidget
        
    def getCavWrappers(self):
        return self.cav_wrappers

    def dumpCntrlDataToDA(self,parent_da):
        """ Puts this controller data into the Data Adaptor """
        return
       
    def readCntrlDataFromDA(self,parent_da):
        """ Reads data for this controller from the Data Adaptor """
        return
        
    def stopAllThreads(self):
        """ Stops all threads of this controller """
        #self.scanStopper.setSetToStop(True)
        return

class Scan_Analysis_Cntrl:
    """
    Controller for SCL cavities scan data analysis.
    """
    def __init__(self,cavs_phase_scan_cntrl):
        self.cavs_phase_scan_cntrl = cavs_phase_scan_cntrl
        self.lace_scl_wizard = self.cavs_phase_scan_cntrl.lace_scl_wizard
        self.model_cavs = self.lace_scl_wizard.getOM().getModelCavs()
        self.cav_wrappers = self.lace_scl_wizard.getCavWrappers()
        self.bpm_wrappers = self.lace_scl_wizard.getBPM_Wrappers()
        #---- main widget
        self.mainWidget = QFrame(self.cavs_phase_scan_cntrl.tabs)
        #---- tab name
        self.tab_name = "Phase Scan Analysis"
        #----

    def getTabName(self):
        """ Returns the tab name the controller """
        return self.tab_name
        
    def getMainWidget(self):
        """ Returns the mainWidget (window) """
        return self.mainWidget
        
    def getCavWrappers(self):
        return self.cav_wrappers

    def dumpCntrlDataToDA(self,parent_da):
        """ Puts this controller data into the Data Adaptor """
        return
       
    def readCntrlDataFromDA(self,parent_da):
        """ Reads data for this controller from the Data Adaptor """
        return
        
    def stopAllThreads(self):
        """ Stops all threads of this controller """
        #self.scanStopper.setSetToStop(True)
        return


#----------------------------------------------------------
#  Subpanels for knobs and tables
#----------------------------------------------------------
class UpperScanPanel:
    """
    The upper panel in the SCL Phase Scan tab with parameters of the scan
    and start-stop_resume knobs.
    """
    def __init__(self,cavs_phase_scan_cntrl):
        self.cavs_phase_scan_cntrl = cavs_phase_scan_cntrl
        self.lace_scl_wizard = self.cavs_phase_scan_cntrl.lace_scl_wizard
        self.model_cavs = self.lace_scl_wizard.getOM().getModelCavs()
        self.cav_wrappers = self.lace_scl_wizard.getCavWrappers()
        self.bpm_wrappers = self.lace_scl_wizard.getBPM_Wrappers()
        #---- main widget
        self.mainWidget = QFrame(self.cavs_phase_scan_cntrl.tabs)
        
        buttons_style = StyleSheetFactory.pushButtonStyleSheet()
        
        #---- vertical layout 
        vlayout = QVBoxLayout()
        
        hor_view_1 = QWidget()
        hor_view_2 = QWidget()
        hor_layout_1 = QHBoxLayout()
        hor_layout_2 = QHBoxLayout()
        hor_view_1.setLayout(hor_layout_1)
        hor_view_2.setLayout(hor_layout_2)
        
        vlayout.addWidget(hor_view_1)
        vlayout.addWidget(hor_view_2)

        #---- upp line
        setSynchPhase_button = QPushButton(text="Set Synch. Phase to Selected Cavs",parent=None)
        setSynchPhase_button.setStyleSheet(buttons_style)
        hor_layout_1.addWidget(setSynchPhase_button)
        
        self.mainWidget.setLayout(vlayout)

    def getMainWidget(self):
        """ Returns the mainWidget (window) """
        return self.mainWidget       

#----------------------------------------------------------
#  Data Table Model
#----------------------------------------------------------

class CavsScanDataTableModel(LACE_DataTableModel):
    def __init__(self,cavs_scan_cntrl):
        super().__init__()
        self.cavs_scan_cntrl = cavs_scan_cntrl
        self.cavs_phase_scan_cntrl = self.cavs_scan_cntrl.cavs_phase_scan_cntrl
        self.lace_scl_wizard = self.cavs_phase_scan_cntrl.lace_scl_wizard
        #self.cavs_state_cntrl = self.cavs_phase_scan_cntrl.cavs_state_cntrl
        self.cav_wrappers = self.lace_scl_wizard.getCavWrappers()
        #---- Sets the headers
        headers = ["Cavity","Good","Done","BPM 1","BPM 2","Old Phase","New Phase","SinAmp","SinAmpErr","AccPhase"]     
        self.setHorizontalHeaderLabels(headers)
        for cav_ind,cav_wrapper in enumerate(self.cav_wrappers):
            name_item = QStandardItem(cav_wrapper.getAlias())
            isGood_item = QStandardItem() ; isGood_item.setCheckable(True) ; isGood_item.setCheckState(Qt.Checked)
            isDone_item = QStandardItem() ; isDone_item.setCheckable(True) ;  isDone_item.setCheckState(Qt.Unchecked)
            name_item.setEditable(False)
            isGood_item.setEnabled(False)
            isDone_item.setEnabled(False)
            bpm1_item = QStandardItem();
            bpm2_item = QStandardItem();
            epics_phase_old_item = QStandardItem();
            epics_phase_new_item = QStandardItem();
            scan_phase_sinAmp_item = QStandardItem();
            scan_phase_errAmp_item = QStandardItem();
            synch_phase_item = QStandardItem();
            row  = [name_item,isGood_item,isDone_item]
            row += [bpm1_item,bpm2_item]
            row += [epics_phase_old_item,epics_phase_new_item]
            row += [scan_phase_sinAmp_item,scan_phase_errAmp_item]
            row += [synch_phase_item,]
            #print ("debug n item=",len(row))
            self.appendRow(row)
        self.itemChanged.connect(self.handleItemChanged)
            
    @Slot("QStandardItem*")
    def handleItemChanged(self, item):
        pass

    def _updateItemsFromData(self):
        for cav_ind,cav_wrapper in enumerate(self.cav_wrappers):
            #---- cavity is good
            self._updateBoolItem(cav_wrapper.isGood,self.item(cav_ind,1))
            if(not cav_wrapper.isGood):
                cav_wrapper.modelAmp = 0.
                cav_wrapper.model_cav.setModelAmp(cav_wrapper.modelAmp)
                cav_wrapper.isMeasured = False
                self._updateBoolItem(cav_wrapper.isMeasured,self.item(cav_ind,2))
                for ind in range(3,10):
                    self.item(cav_ind,ind).setText("")
                continue
            self._updateBoolItem(cav_wrapper.isMeasured,self.item(cav_ind,2))
            bpm1_item = self.item(cav_ind,3)
            if(cav_wrapper.bpm_wrapper0 != None):
                bpm1_item.setText("%10s"%cav_wrapper.bpm_wrapper0.bpm.getName())
            else:
                 bpm1_item.setText("")
            bpm2_item = self.item(cav_ind,4)
            if(cav_wrapper.bpm_wrapper1 != None): 
                bpm2_item.setText("%10s"%cav_wrapper.bpm_wrapper1.bpm.getName())
            else:
                 bpm2_item.setText("")
            epics_phase_old_item = self.item(cav_ind,5) ; epics_phase_old_item.setText("%+6.1f"%cav_wrapper.epicsPhaseInit)
            epics_phase_new_item = self.item(cav_ind,6) ; epics_phase_new_item.setText("%+6.1f"%cav_wrapper.epicsPhase)
            scan_phase_sinAmp_item = self.item(cav_ind,7) ; scan_phase_sinAmp_item.setText("%6.1f"%(cav_wrapper.sin_phase_func_amp))
            scan_phase_errAmp_item = self.item(cav_ind,8) ; scan_phase_errAmp_item.setText("%5.1f"%(cav_wrapper.sin_phase_func_amp_err))
            synch_phase_item = self.item(cav_ind,9) ;synch_phase_item.setText("%+6.1f"%(cav_wrapper.synch_acc_phase))

#----------------------------------------------------------
# Actions on events with buttons 
#----------------------------------------------------------
        
#----------------------------------------------------------
# Main Controller for this library
#----------------------------------------------------------

class CavsPhaseScan_Cntrl:
    """
    It organizes the SCL cavities' phase scans and analysis to get 
    the initial SCL energy, energies before and after each cavity, and 
    each cavity 1st gap phase of the model. These data allows to create
    a calibrated SCL model for the bunch center acceleration.
    """
    def __init__(self,lace_scl_wizard):
        self.lace_scl_wizard = lace_scl_wizard
        #---- main widget
        self.mainWidget = QFrame(self.lace_scl_wizard.tabs)
        #---- tab name
        self.tab_name = "SCL Phase Scan & Analysis"
        
        #---- Internal tabs
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setMovable(False)

        #---- Cavities' scan controller
        self.cavs_scan_cntrl = Cavs_Scan_Cntrl(self)
        
        #---- Scan analysis controller
        self.scan_analysis_cntrl = Scan_Analysis_Cntrl(self)        

        self.tabs.addTab(self.cavs_scan_cntrl.getMainWidget(),self.cavs_scan_cntrl.getTabName())
        self.tabs.addTab(self.scan_analysis_cntrl.getMainWidget(),self.scan_analysis_cntrl.getTabName())
        
        #---- Main window layout
        border_layout = BorderLayout(None, +2)
        border_layout.addWidget(self.tabs, Position.Center)

        self.mainWidget.setLayout(border_layout)

    def getTabName(self):
        """ Returns the tab name the controller """
        return self.tab_name

    def getMainWidget(self):
        """ Returns the mainWidget (window) of CavsPhaseScan_Cntrl """
        return self.mainWidget
        
    def getTabWidget(self,name):
        """ Returns the mainWidget of the particular 1st level tab """
        widget = None
        for ind in range(self.tabs.count()):
            if(self.tabs.tabText(ind) == name):
                return self.tabs.widget(ind)
        return widget

    def dumpCntrlDataToDA(self,parent_da):
        """ Puts this controller data into the Data Adaptor """
        return
       
    def readCntrlDataFromDA(self,parent_da):
        """ Reads data for this controller from the Data Adaptor """
        return
        
    def stopAllThreads(self):
        """ Stops all threads of this controller """
        #self.scanStopper.setSetToStop(True)
        return

