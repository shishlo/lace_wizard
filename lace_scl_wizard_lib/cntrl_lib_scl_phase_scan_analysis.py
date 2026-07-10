"""
Controller for analysis of SCL cavities phase scans data. After analysis we
will have the calibrated Online Model for SCL.
"""

import sys
import html

from PySide6 import QtWidgets 

from PySide6.QtWidgets import (
    QFrame,
    QTableWidget,
    QTableView,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton,
    QWidget,
    QTabWidget,
    QGroupBox,
    QProgressBar,
    QMainWindow,
    QHeaderView,
    QPlainTextEdit,
    QCheckBox,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QRadioButton,
    QButtonGroup
    )

from PySide6.QtCore import (
    Qt, Slot,
    QRunnable, QObject, QThreadPool, Signal,
    QAbstractTableModel,
    QSize
    )

from PySide6.QtGui import (
    QStandardItemModel, QStandardItem,
    QTextDocument,
    QIcon,
    QPalette, QColor
    )

import pyqtgraph as pg

"""
from pyqtgraph import (
    mkPen, PlotWidget, 
    InfiniteLine, InfLineLabel, 
    TextItem, AxisItem, 
    ViewBox, 
    PlotDataItem, 
    ErrorBarItem
    )
"""

from gui_lib.borderlayout import BorderLayout, Position
from gui_lib.style_sheets_lib import StyleSheetFactory
from gui_lib.table_view_model_lib import LACE_QTableView, LACE_DataTableModel
from .wrappers_cavs_bpms_magnets import Cavity_Wrapper, BPM_Wrapper

#---------------------------------------------------------------------
# Internal Sub - Controller for Analysis of the SCL Phase Scan data.
# The parent is SCL Phase Scan and Analysis.
#---------------------------------------------------------------------

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
        
        groupBox_style = StyleSheetFactory.groupBoxStyleSheet()
        
        #---- The QWidget with Cavities and analysis results table
        self.cavs_analysis_table_view = LACE_QTableView()
        self.cavs_data_analysis_table_model = CavsScanDataAnalysisTableModel(self)
        self.cavs_analysis_table_view.setModel(self.cavs_data_analysis_table_model)
        self.cavs_analysis_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cavs_analysis_table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.cavs_analysis_table_view.selectionModel().selectionChanged.connect(self._cavsSelectionChanged)
        
        #--- connection to cav_table_view in the initial state controller
        init_cavs_table_model = self.lace_scl_wizard.init_state_cntrl.cavs_data_table_model
        init_cavs_table_model.addDependentTableModel(self.cavs_data_analysis_table_model)
        
       #---- upper panel
        self.upper_panel_cntrl = UpperAnalysisPanelCntrl(self)

        #---- bottom panel with plots and bpm data cleaning buttons
        self.bottom_panel_cntrl = BottomAnalysisPanelCntrl(self)
        
        central_layout = QHBoxLayout()
        central_layout.setSpacing(0)
        central_layout.setContentsMargins(0, 0, 0, 0)   
        central_layout.addWidget(self.cavs_analysis_table_view,1)
        
        central_view = QGroupBox()
        central_view.setLayout(central_layout)
        
        #---- Define the style sheet for the border
        central_view.setStyleSheet(groupBox_style)

        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)          
        main_layout.addWidget(self.upper_panel_cntrl.getMainWidget())
        main_layout.addWidget(central_view,1)
        main_layout.addWidget(self.bottom_panel_cntrl.getMainWidget(),1)
        
        #---- Set up plots. Plots themselves are belongs to self.bottom_panel_cntrl
        self.eKinOut_line, self.eKinOut_line_fit_line = self.bottom_panel_cntrl.getLine_eKinOut_BPM_and_Model()        
        
        self.getMainWidget().setLayout(main_layout)
        

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
        
    @Slot("QtCore.QItemSelection*")
    def _cavsSelectionChanged(self,selected,deselected):
        """ Updates right BPM table for particular cavity with selected index """
        #---- selected.indexes() and deselected.indexes() with index.row() and index.column()
        if(selected.isEmpty()):
            title = "eKinOut for Cavity = None"
            self.bottom_panel_cntrl.eKin_out_plot.setTitle(title)                    
            return
        row = selected.indexes()[0].row()
        #----
        cav_wrapper = self.cav_wrappers[row]
        print ("debug cavity selected in analysis =",cav_wrapper.alias)
        #---- plot the graph of eKinOut for acvity
        title = "eKinOut vs. Phase for Cavity = " + cav_wrapper.getAlias()
        self.bottom_panel_cntrl.eKin_out_plot.setTitle(title)
        #---------------------
        (x_arr,y_arr,y_err_arr) = cav_wrapper.eKin_out_func.getXYErrLists()
        self.eKinOut_line.setData(x_arr,y_arr)        
        (x_arr,y_arr,y_err_arr) = cav_wrapper.eKin_out_fit_func.getXYErrLists()
        self.eKinOut_line_fit_line.setData(x_arr,y_arr)
        
#----------------------------------------------------------
#  Sub-panels for knobs and tables
#----------------------------------------------------------

class UpperAnalysisPanelCntrl:
    """
    The upper panel in the Scan Analysis tab with start-stop analysis knobs.
    """
    def __init__(self,scan_analysis_cntrl):
        self.scan_analysis_cntrl = scan_analysis_cntrl
        self.cavs_phase_scan_cntrl = self.scan_analysis_cntrl.cavs_phase_scan_cntrl
        self.lace_scl_wizard = self.cavs_phase_scan_cntrl.lace_scl_wizard
        self.model_cavs = self.lace_scl_wizard.getOM().getModelCavs()
        self.cav_wrappers = self.lace_scl_wizard.getCavWrappers()
        self.bpm_wrappers = self.lace_scl_wizard.getBPM_Wrappers()
        #---- main widget
        self.mainWidget = QGroupBox()

        buttons_style = StyleSheetFactory.pushButtonStyleSheet()
        groupBox_style = StyleSheetFactory.groupBoxStyleSheet()

        #---- vertical layout
        hlayout = QHBoxLayout()
        #---- Set spacing between widgets to 0
        hlayout.setSpacing(0)
        #---- Remove margins around the layout (top, bottom, left, right)
        hlayout.setContentsMargins(0, 0, 0, 0)
        #---- Set up alignment to the left
        hlayout.setAlignment(Qt.AlignLeft)

        #----------------------------------------------
        #---- upp line - hor_view_1 panel
        #----------------------------------------------
        startAnalysis_button = QPushButton(text=html.unescape("Start Analysis"),parent=None)
        startAnalysis_button.setStyleSheet(buttons_style)
        startAnalysis_button.adjustSize()

        startSelectedAnalysis_button = QPushButton(text=html.unescape("Start Selected Cavs."),parent=None)
        startSelectedAnalysis_button.setStyleSheet(buttons_style)
        startSelectedAnalysis_button.adjustSize()
        
        stopAnalysis_button = QPushButton(text=html.unescape("Stop Analysis"),parent=None)
        stopAnalysis_button.setStyleSheet(buttons_style)
        stopAnalysis_button.adjustSize()
        
        """
        #---- cavs button action assignment
        setSyncPhase_Action = SetSyncPhase_Action(self) 
        startScan_Action = StartScan_Action(self)
        stopScan_Action = StopScan_Action(self)

        setSynchPhase_button.clicked.connect(lambda: setSyncPhase_Action.performAction())
        start_scan_button.clicked.connect(lambda: startScan_Action.performAction())
        start_scan_selected_button.clicked.connect(lambda: startScan_Action.performActionForSelected())
        stop_scan_button.clicked.connect(lambda: stopScan_Action.performAction())
        """
        
        self.analysis_status_text = QLineEdit("Analysis Status:")
        self.analysis_status_text.setStyleSheet("color: blue; background-color: white;")

        hlayout.addWidget(startAnalysis_button)
        hlayout.addWidget(startSelectedAnalysis_button)
        hlayout.addWidget(stopAnalysis_button)
        hlayout.addWidget(self.analysis_status_text,1)
        
        #---- set layout for main widget
        self.mainWidget.setLayout(hlayout)
        
        #---- Define the style sheet for the border
        self.mainWidget.setStyleSheet(groupBox_style)
        
    def getMainWidget(self):
        """ Returns the mainWidget (window) """
        return self.mainWidget

class BottomAnalysisPanelCntrl:
    """
    The Bottom panel in the Scan Analysis tab with output energy vs. 
    cavity phase plots showing the result of analysis.
    """
    def __init__(self,scan_analysis_cntrl):
        self.scan_analysis_cntrl = scan_analysis_cntrl
        self.cavs_phase_scan_cntrl = self.scan_analysis_cntrl.cavs_phase_scan_cntrl
        self.lace_scl_wizard = self.cavs_phase_scan_cntrl.lace_scl_wizard
        self.model_cavs = self.lace_scl_wizard.getOM().getModelCavs()
        self.cav_wrappers = self.lace_scl_wizard.getCavWrappers()
        self.bpm_wrappers = self.lace_scl_wizard.getBPM_Wrappers()
        #---- main widget
        self.mainWidget = QFrame()
        
        buttons_style = StyleSheetFactory.pushButtonStyleSheet()
        groupBox_style = StyleSheetFactory.groupBoxStyleSheet()
        
        self.eKin_out_plot = pg.PlotWidget()
        
        central_layout = QHBoxLayout()
        central_layout.setSpacing(0)
        central_layout.setContentsMargins(0, 0, 0, 0)   
        central_layout.addWidget(self.eKin_out_plot,1)
        
        self.getMainWidget().setLayout(central_layout)
        
    def getMainWidget(self):
        """ Returns the mainWidget (window) """
        return self.mainWidget
        
    def get_eKinOutPlot(self):
        """ 
        Returns the PlotWidget for plot of eKinOut for BPMs' data 
        and Model vs. cavity phase.
        """
        return self.eKin_out_plot

    def getLine_eKinOut_BPM_and_Model(self):
        """ 
        Sets up parameters of PlotWidget instance and 
        adds plot of eKinOut for BPMs' data and Model vs. cavity phase.
        """
        self.eKin_out_plot.showGrid(True, True)
        legend = self.eKin_out_plot.addLegend(labelTextSize='12pt', labelTextColor="white")
        legend.anchor((0, 0), (0, 0))
        self.eKin_out_plot.setTitle("eKinOut vs. Cavity Phase")
        self.eKin_out_plot.setLabel('bottom', html.unescape("Cavity EPICS &phi;"), units='deg')
        self.eKin_out_plot.setLabel('left', html.unescape("eKin Out"), units='MeV')
        self.eKin_out_plot.getAxis('left').setTextPen('white')
        self.eKin_out_plot.getAxis('bottom').setTextPen('white')
        #---- Now these data will be shown on the plot
        #bpm_phase_diff_line = self.eKin_out_plot.plot(pen='white', linestyle="-", symbol="o", symbolBrush='r',marker_size=5, name=html.unescape("&Delta; &phi;<sub>12</sub>"))
        eKinOut_line = self.eKin_out_plot.plot(pen=None, symbol="o", symbolSize=5, symbolBrush='r', name=html.unescape("eKinOut <sub>BPM</sub>"))
        eKinOut_line_fit_line = self.eKin_out_plot.plot(pen="white",  linestyle="-", name=html.unescape("Model Fit"))        
        return (eKinOut_line,eKinOut_line_fit_line)

#----------------------------------------------------------
#  Data Table Model
#----------------------------------------------------------  

class CavsScanDataAnalysisTableModel(LACE_DataTableModel):
    def __init__(self,scan_analysis_cntrl):
        super().__init__()
        self.scan_analysis_cntrl = scan_analysis_cntrl
        self.cavs_phase_scan_cntrl = self.scan_analysis_cntrl.cavs_phase_scan_cntrl
        self.lace_scl_wizard = self.cavs_phase_scan_cntrl.lace_scl_wizard
        self.cav_wrappers = self.lace_scl_wizard.getCavWrappers()
        #---- Sets the headers
        headers  = ["Cavity","Good","Done"]
        headers += ["E-In(MeV)","E-Out(MeV)",html.unescape("&delta;E(k/k-1)(keV)")]
        headers += ["Model-E-In","Model-E-Out","CavAmp(MV)","CavAmp(%)"]
        headers += [html.unescape("&phi;-1stGap"),html.unescape("&delta;&phi;-synch")]
        self.setHorizontalHeaderLabels(headers)
        for cav_ind,cav_wrapper in enumerate(self.cav_wrappers):
            name_item = QStandardItem(cav_wrapper.getAlias())
            isGood_item = QStandardItem() ; isGood_item.setCheckable(True) ; isGood_item.setCheckState(Qt.Checked)
            isDone_item = QStandardItem() ; isDone_item.setCheckable(True) ;  isDone_item.setCheckState(Qt.Unchecked)
            name_item.setEditable(False)
            isGood_item.setEnabled(False)
            isDone_item.setEnabled(False)
            eKinIn_item = QStandardItem();
            eKinOut_item = QStandardItem();
            delta_eKin_item = QStandardItem();
            model_eKinIn_item = QStandardItem();
            model_eKinOut_item = QStandardItem();
            cav_amp_epics_item = QStandardItem();
            cav_amp_model_item = QStandardItem();
            phase_1st_gap_item = QStandardItem();
            synch_phase_item = QStandardItem();
            row  = [name_item,isGood_item,isDone_item]
            row += [eKinIn_item,eKinOut_item,delta_eKin_item]
            row += [model_eKinIn_item,model_eKinOut_item]
            row += [cav_amp_epics_item,cav_amp_model_item]
            row += [phase_1st_gap_item,synch_phase_item]
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
            #---- update eKinIn eKinOut and deltaE(k/k-1)
            eKinIn = cav_wrapper.eKin_in
            eKinOut = cav_wrapper.eKin_out
            deltaE = 0.
            if(cav_ind > 1):
                deltaE = eKinIn - self.cav_wrappers[cav_ind-1].eKin_out
            eKinIn_item = self.item(cav_ind,3);
            eKinOut_item = self.item(cav_ind,4);
            delta_eKin_item = self.item(cav_ind,5);
            eKinIn_item.setText("%8.3f"%eKinIn)
            eKinOut_item.setText("%8.3f"%eKinOut)
            delta_eKin_item.setText("%8.3f"%deltaE)

#----------------------------------------------------------
# Actions on events with buttons
#----------------------------------------------------------
