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
        """
        self.cavs_data_table_model = CavsScanDataTableModel(self)
        self.cavs_table_view.setModel(self.cavs_data_table_model)
        self.cavs_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        """

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
#  Data Table Model
#----------------------------------------------------------

class CavsScanDataTableModel(LACE_DataTableModel):
    def __init__(self,cavs_scan_cntrl):
        super().__init__()
        self.cavs_scan_cntrl = cavs_scan_cntrl
        self.cavs_phase_scan_cntrl = self.cavs_scan_cntrl.cavs_phase_scan_cntrl
        self.lace_scl_wizard = self.cavs_phase_scan_cntrl.lace_scl_wizard
        self.cavs_state_cntrl = self.cavs_phase_scan_cntrl.cavs_state_cntrl
        self.cav_wrappers = self.cavs_state_cntrl.getCavWrappers()
        #---- Sets the headers
        headers = ["Cavity", "Pos[m]","Good","EPICS_Amp","Epics_Phase","Measured","Analyzed","ModelAmp","ModelPhase","CoeffAmp","PhaseOffset"]     
        self.setHorizontalHeaderLabels(headers)
        for cav_ind,cav_wrapper in enumerate(self.cav_wrappers):
            name_item = QStandardItem(cav_wrapper.getAlias())
            pos_item = QStandardItem("%7.3f"%cav_wrapper.model_cav.getPosition())
            isGood_item = QStandardItem() ; isGood_item.setCheckable(True) ; isGood_item.setCheckState(Qt.Checked)
            epics_amp_item = QStandardItem()
            epics_phase_item = QStandardItem()
            measured_item = QStandardItem() ; measured_item.setCheckable(True) ; measured_item.setCheckState(Qt.Unchecked)
            analyzed_item = QStandardItem() ; analyzed_item.setCheckable(True) ; analyzed_item.setCheckState(Qt.Unchecked)
            measured_item.setEnabled(False)
            analyzed_item.setEnabled(False)
            model_amp_item = QStandardItem()
            model_phase_item = QStandardItem()
            model_coeff_amp_item = QStandardItem()
            phase_offset_item = QStandardItem()
            row  = [name_item,pos_item,isGood_item,]
            row += [epics_amp_item,epics_phase_item]
            row += [measured_item,analyzed_item]
            row += [model_amp_item,model_phase_item]
            row += [model_coeff_amp_item,phase_offset_item]
            self.appendRow(row)
        self.itemChanged.connect(self.handleItemChanged)
            
    @Slot("QStandardItem*")
    def handleItemChanged(self, item):
        """ Only the Good descriptor is allowed to be changed from the Table View """
        if(item.isCheckable() and item.checkState() in (Qt.Checked, Qt.Unchecked)):
            current_state = item.checkState()
            row = item.row()
            col = item.column()
            if(col != 2): return
            if current_state == Qt.Checked:
                self.cav_wrappers[row].isGood = True
            elif current_state == Qt.Unchecked:
                self.cav_wrappers[row].isGood = False       

    def _updateItemsFromData(self):
        for cav_ind,cav_wrapper in enumerate(self.cav_wrappers):             
            #---- cavity is good
            self._updateBoolItem(cav_wrapper.isGood,self.item(cav_ind,2))
            if(not cav_wrapper.isGood):
                cav_wrapper.modelAmp = 0.
                cav_wrapper.model_cav.setModelAmp(cav_wrapper.modelAmp)
            epics_amp_item = self.item(cav_ind,3) ; epics_amp_item.setText("%7.4f"%cav_wrapper.epicsAmp)
            epics_phase_item = self.item(cav_ind,4) ; epics_phase_item.setText("%+6.1f"%cav_wrapper.epicsPhase)
            self._updateBoolItem(cav_wrapper.isMeasured,self.item(cav_ind,5))
            self._updateBoolItem(cav_wrapper.isAnalyzed,self.item(cav_ind,6))
            model_amp_item  = self.item(cav_ind,7) ; model_amp_item.setText("%6.4f"%cav_wrapper.modelAmp)           
            model_phase_item = self.item(cav_ind,8) ; model_phase_item.setText("%+7.1f"%cav_wrapper.modelPhase) 
            model_coeff_amp_item = self.item(cav_ind,9) ; model_coeff_amp_item.setText("%6.4f"%cav_wrapper.modelCoeffToEpicsAmp)
            phase_offset_item = self.item(cav_ind,10) ; phase_offset_item.setText("%7.4f"%cav_wrapper.model_phase_shift)

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

