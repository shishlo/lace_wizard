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
from PySide6.QtWidgets import QFileDialog

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

# import the utilities
from orbit.utils import phaseNearTargetPhase, phaseNearTargetPhaseDeg

from gui_lib.borderlayout import BorderLayout, Position
from gui_lib.style_sheets_lib import StyleSheetFactory
from gui_lib.table_view_model_lib import LACE_QTableView, LACE_DataTableModel
from lace_om_lib.sns_linac_bunch_generator import get_SCL_EmptyBunch

from .wrappers_cavs_bpms_magnets import Cavity_Wrapper, BPM_Wrapper
from .phase_scan_analysis_lib import AnalysisStateController, Analysis_Runner, AnalysisWorkerSignals

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
        self.cavs_table_view = LACE_QTableView()
        self.cavs_data_analysis_table_model = CavsScanDataAnalysisTableModel(self)
        self.cavs_table_view.setModel(self.cavs_data_analysis_table_model)
        self.cavs_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cavs_table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.cavs_table_view.selectionModel().selectionChanged.connect(self._cavsSelectionChanged)
        
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
        central_layout.addWidget(self.cavs_table_view,1)
        
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
        
        #---- Signals for table and plot update during the analysis thread execution
        self.analysis_worker_signals = AnalysisWorkerSignals()
        
        self.getMainWidget().setLayout(main_layout)
        
        #---- Analysis state controller aka Analysis Stopper
        self.analysis_stopper = AnalysisStateController()
        self.threadpool = QThreadPool()        

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
        #print ("debug cavity selected in analysis =",cav_wrapper.alias)
        #---- plot the graph of eKinOut for acvity
        title = "eKinOut vs. Phase for Cavity = " + cav_wrapper.getAlias()
        self.bottom_panel_cntrl.eKin_out_plot.setTitle(title)
        #---------------------
        (x_arr,y_arr,y_err_arr) = cav_wrapper.eKin_out_func.getXYErrLists()
        self.eKinOut_line.setData(x_arr,y_arr)        
        (x_arr,y_arr,y_err_arr) = cav_wrapper.eKin_out_fit_func.getXYErrLists()
        self.eKinOut_line_fit_line.setData(x_arr,y_arr)

    @Slot(tuple)     
    def scanDataUpdate(self,tuple_input):
        """ Perfoms all actions on GUI """
        (update_type,*rest) = tuple_input
        #---- Type of message - Analysis status update
        if(update_type == "status_update"):
            msg_txt = rest[0]
            self.upper_panel_cntrl.analysis_status_text.setText(msg_txt)
            return
        #---- Type of message - Scan status update
        if(update_type == "table_selection_clear"):
            self.cavs_table_view.clearSelection()
            return
        if(update_type == "table_selection_set"):
            cav_ind = rest[0]
            self.cavs_table_view.selectRow(cav_ind)
            return
        if(update_type == "table_changed"):
            self.cavs_data_analysis_table_model.tableChanged()
            return          
        if(update_type == "table_cavity_data_cahnged"):
            cav_wrapper = rest[0]
            self.cavs_data_analysis_table_model._updateItemsFromData(cav_wrapper)
            return          
        return
        
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
        
        startAnalysis_Action = StartAnalysis_Action(self)
        startAnalysis_button.clicked.connect(lambda: startAnalysis_Action.performAction())
        startSelectedAnalysis_button.clicked.connect(lambda: startAnalysis_Action.performActionForSelected())
        
        stopAnalysis_Action = StopAnalysis_Action(self)
        stopAnalysis_button.clicked.connect(lambda: stopAnalysis_Action.performAction())
        
        #------------------------------------------------------------
        
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

        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.West)
        self.tabs.setMovable(False)        

        buttons_style = StyleSheetFactory.pushButtonStyleSheet()
        groupBox_style = StyleSheetFactory.groupBoxStyleSheet()
        
        #---- Widget with eKin out and fitted model plots
        self.eKin_out_plot = pg.PlotWidget()
        
        self.saveParamsOM_Widget = SaveParametersOnlineModelPanelCntrl(self)

        self.tabs.addTab(self.eKin_out_plot,"eKin Out Plot")
        self.tabs.addTab(self.saveParamsOM_Widget.getMainWidget(),"Save OM Parameters")
        
        central_layout = QHBoxLayout()
        central_layout.setSpacing(0)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.addWidget(self.tabs,1)
        
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

class SaveParametersOnlineModelPanelCntrl:
    """
    The tab at the Bottom panel in the Scan Analysis with buttons to 
    save the Online Model initialization parameters.
    """
    def __init__(self,bottom_panel_cntrl):
        self.bottom_panel_cntrl = bottom_panel_cntrl
        self.scan_analysis_cntrl = self.bottom_panel_cntrl.scan_analysis_cntrl
        self.cavs_phase_scan_cntrl = self.scan_analysis_cntrl.cavs_phase_scan_cntrl
        self.lace_scl_wizard = self.cavs_phase_scan_cntrl.lace_scl_wizard
        self.scl_om = self.lace_scl_wizard.scl_om
        self.model_cavs = self.lace_scl_wizard.getOM().getModelCavs()
        self.cav_wrappers = self.lace_scl_wizard.getCavWrappers()
        self.bpm_wrappers = self.lace_scl_wizard.getBPM_Wrappers()
        #---- main widget
        self.mainWidget = QFrame()
        
        buttons_style = StyleSheetFactory.pushButtonStyleSheet()
        groupBox_style = StyleSheetFactory.groupBoxStyleSheet()

        #-----------------------------------------------------------
        #---- buttons to write to ASCII Online Model paramaters 
        #-----------------------------------------------------------
        saveOM_Action = SaveOM_Action(self)
        saveAllCavs_button = QPushButton("Save Online Model Parameters",parent=None)
        saveAllCavs_button.setStyleSheet(buttons_style)
        saveAllCavs_button.clicked.connect(lambda: saveOM_Action.performAction())
        
        saveSlectedCavs_button = QPushButton("Save for Selected Cavities",parent=None)
        saveSlectedCavs_button.setStyleSheet(buttons_style)
        saveSlectedCavs_button.clicked.connect(lambda: saveOM_Action.performActionForSelected())
        
        save_status_0_text = QLineEdit("Status:")
        save_status_0_text.setStyleSheet("color: blue; background-color: white;")
        
        self.save_status_text = QLineEdit("")
        self.save_status_text.setStyleSheet("color: red; background-color: white;")       

        hor_view_1 = QWidget()
        hor_view_2 = QWidget()
        
        hor_layout_1 = QHBoxLayout()
        hor_layout_1.setSpacing(0)
        hor_layout_1.setContentsMargins(0, 0, 0, 0)
        hor_layout_1.setAlignment(Qt.AlignLeft)        
        hor_layout_1.addWidget(saveAllCavs_button)
        hor_layout_1.addWidget(saveSlectedCavs_button)
        
        hor_view_1.setLayout(hor_layout_1)
        
        hor_layout_2 = QHBoxLayout()
        hor_layout_2.setSpacing(0)
        hor_layout_2.setContentsMargins(0, 0, 0, 0)
        hor_layout_2.setAlignment(Qt.AlignLeft)        
        hor_layout_2.addWidget(save_status_0_text)
        hor_layout_2.addWidget(self.save_status_text,1) 
        
        hor_view_2.setLayout(hor_layout_2)
        
        ver_layout = QVBoxLayout()
        ver_layout.setSpacing(0)
        ver_layout.setContentsMargins(0, 0, 0, 0)
        ver_layout.setAlignment(Qt.AlignTop)
        ver_layout.addWidget(hor_view_1)
        ver_layout.addWidget(hor_view_2)
        
        self.getMainWidget().setLayout(ver_layout)
        
        
    def getMainWidget(self):
        """ Returns the mainWidget (window) """
        return self.mainWidget

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
        headers += [html.unescape("&delta;E-fit(keV)"),]
        headers += ["E0TL[MeV]","Model-E-Out","CavAmp(MV)","CavAmp(%)"]
        headers += [html.unescape("&phi;-1stGap"),html.unescape("&phi;-Accel.")]
        self.setHorizontalHeaderLabels(headers)
        for cav_ind,cav_wrapper in enumerate(self.cav_wrappers):
            name_item = QStandardItem(cav_wrapper.getAlias())
            isGood_item = QStandardItem() ; isGood_item.setCheckable(True) ; isGood_item.setCheckState(Qt.Checked)
            isDone_item = QStandardItem() ; isDone_item.setCheckable(True) ;  isDone_item.setCheckState(Qt.Unchecked)
            name_item.setEditable(False)
            isGood_item.setEnabled(False)
            isDone_item.setEnabled(False)
            eKinIn_item = QStandardItem()
            eKinOut_item = QStandardItem()
            delta_eKin_item = QStandardItem()
            eKinIn_item.setTextAlignment(Qt.AlignmentFlag.AlignJustify)
            eKinOut_item.setTextAlignment(Qt.AlignmentFlag.AlignJustify)
            delta_eKin_item.setTextAlignment(Qt.AlignmentFlag.AlignJustify)
            delta_fit_eKinOut_rms_item = QStandardItem()
            delta_fit_eKinOut_rms_item.setTextAlignment(Qt.AlignmentFlag.AlignJustify)
            e0tl_item = QStandardItem()
            model_eKinOut_item = QStandardItem()
            cav_amp_epics_item = QStandardItem()
            cav_amp_model_item = QStandardItem()
            phase_1st_gap_item = QStandardItem()
            synch_phase_item = QStandardItem()
            row  = [name_item,isGood_item,isDone_item]
            row += [eKinIn_item,eKinOut_item,delta_eKin_item]
            row += [delta_fit_eKinOut_rms_item,]
            row += [e0tl_item,model_eKinOut_item]
            row += [cav_amp_epics_item,cav_amp_model_item]
            row += [phase_1st_gap_item,synch_phase_item]
            #print ("debug n item=",len(row))
            self.appendRow(row)
        self.itemChanged.connect(self.handleItemChanged)

    @Slot("QStandardItem*")
    def handleItemChanged(self, item):
        col = item.column()
        if(col != 3): return
        cav_ind = item.row()
        txt = item.text()
        if(txt != ""):
            self.cav_wrappers[cav_ind].eKin_in = float(txt)

    def _updateItemsFromData(self,cav_wrapper = None):
        if(cav_wrapper == None):
            for cav_ind,cav_wrapper in enumerate(self.cav_wrappers):
              self._updateItemsFromDataForCavity(cav_ind,cav_wrapper)  
        else:
            cav_ind = self.cav_wrappers.index(cav_wrapper)
            self._updateItemsFromDataForCavity(cav_ind,cav_wrapper)
            
    def _updateItemsFromDataForCavity(self,cav_ind,cav_wrapper):
            #---- cavity is good
            self._updateBoolItem(cav_wrapper.isGood,self.item(cav_ind,1))
            self._updateBoolItem(cav_wrapper.isAnalyzed,self.item(cav_ind,2))
            if(not cav_wrapper.isGood or (not cav_wrapper.isAnalyzed)):
                for item_ind in range(3,self.columnCount()):
                    item = self.item(cav_ind,item_ind)
                    item.setText("")
                return
            #---- update eKinIn eKinOut and deltaE(k/k-1)
            eKinIn = cav_wrapper.eKin_in
            eKinOut = cav_wrapper.eKin_out
            eKinIn_item = self.item(cav_ind,3)
            eKinOut_item = self.item(cav_ind,4)
            eKinIn_item.setText("%8.3f"%eKinIn)
            eKinOut_item.setText("%8.3f"%eKinOut)
            #------------------------------------------------
            if(cav_wrapper.getAlias().find("CCL4") >= 0):
                for item_ind in range(5,self.columnCount()):
                    item = self.item(cav_ind,item_ind)
                    item.setText("")
                return
            #------------------------------------------------
            deltaE = 0.
            if(cav_ind >= 1):
                deltaE = eKinIn - self.cav_wrappers[cav_ind-1].eKin_out
            delta_eKin_item = self.item(cav_ind,5)
            delta_eKin_item.setText("%8.3f"%(deltaE*1000))
            #------------------------------------------------
            eKin_out_fit_delta_rms = cav_wrapper.eKin_out_fit_delta_rms
            delta_fit_eKinOut_rms_item = self.item(cav_ind,6)
            delta_fit_eKinOut_rms_item.setText("%8.3f"%(eKin_out_fit_delta_rms*1000))
            #------------------------------------------------
            E0TL = cav_wrapper.E0TL
            e0tl_item = self.item(cav_ind,7)
            e0tl_item.setText("%8.3f"%(E0TL))
            #------------------------------------------------
            eKin_model_out = cav_wrapper.eKin_model_out
            eKin_model_out_item =self.item(cav_ind,8)
            eKin_model_out_item.setText("%8.3f"%eKin_model_out)
            #------------------------------------------------
            #---- It is not real EPICS amplitude - it is 
            #---- from cavity model after analysis
            epics_amp = cav_wrapper.modelAmp*cav_wrapper.modelCoeffToEpicsAmp 
            epics_amp_item = self.item(cav_ind,9)
            epics_amp_item.setText("%8.3f"%(epics_amp))
            #------------------------------------------------
            model_amp = cav_wrapper.modelAmp
            model_amp_item = self.item(cav_ind,10)
            model_amp_item.setText("%8.3f"%(model_amp*100))
            #------------------------------------------------
            model_phase = cav_wrapper.modelPhase
            model_phase_item = self.item(cav_ind,11)
            model_phase_item.setText("%8.3f"%(model_phase))
            #------------------------------------------------
            acc_phase = cav_wrapper.synch_real_acc_phase
            acc_phase_item = self.item(cav_ind,12)
            acc_phase_item.setText("%8.3f"%(acc_phase))
            
#----------------------------------------------------------
# Actions on events with buttons
#----------------------------------------------------------

class StartAnalysis_Action:
    """ Starts phase scan analysis of all or selected cavities. """ 
    def __init__(self,upper_panel_cntrl):
        self.upper_panel_cntrl = upper_panel_cntrl

    def _performAction(self,cav_wrappers):
        """ It starts the phase scan analysis of the cavities from cav_wrappers list """
        self.scan_analysis_cntrl = self.upper_panel_cntrl.scan_analysis_cntrl
        self.cavs_phase_scan_cntrl = self.upper_panel_cntrl.cavs_phase_scan_cntrl
        self.cavs_table_view = self.scan_analysis_cntrl.cavs_table_view
        self.scan_analysis_cntrl.cavs_table_view.selectionModel().clearSelection()
        analysis_worker_signals = self.scan_analysis_cntrl.analysis_worker_signals
        analysis_runner = Analysis_Runner(self.scan_analysis_cntrl,cav_wrappers)
        analysis_worker_signals.analysis_data_changed.connect(self.scan_analysis_cntrl.scanDataUpdate)
        self.scan_analysis_cntrl.threadpool.start(analysis_runner)
        #---- ????????????????
        #print ("debug Starts the analysis for all or selected cavities. ")
        
    def performActionForSelected(self):
        self.scan_analysis_cntrl = self.upper_panel_cntrl.scan_analysis_cntrl
        #---- We cannot start a second scan -------
        analysis_stopper = self.scan_analysis_cntrl.analysis_stopper
        if(analysis_stopper.getIsRunning()): return
        #------------------------------------------
        cav_selection_model = self.scan_analysis_cntrl.cavs_table_view.selectionModel()
        cav_wrappers = self.scan_analysis_cntrl.cav_wrappers
        cav_name_column_ind = 0
        QModelIndex_list = cav_selection_model.selectedIndexes()
        cavs_list = []
        for q_model_ind in QModelIndex_list:
            if(q_model_ind.column() != cav_name_column_ind): continue
            row = q_model_ind.row()
            cav_wrapper = cav_wrappers[row]
            if(not cav_wrapper.isGood):
                cav_wrapper.cleanAllScanData()
                continue
            cavs_list.append(cav_wrapper)
        self._performAction(cavs_list)  
        
    def performAction(self):
        self.scan_analysis_cntrl = self.upper_panel_cntrl.scan_analysis_cntrl
        cav_selection_model = self.scan_analysis_cntrl.cavs_table_view.selectionModel()
        QModelIndex_list = cav_selection_model.selectedIndexes()
        row = 0
        if(len(QModelIndex_list) > 0):
            row = QModelIndex_list[0].row()
        #---- We cannot start a second scan analysis-------
        analysis_stopper = self.scan_analysis_cntrl.analysis_stopper
        if(analysis_stopper.getIsRunning()): return
        #------------------------------------------
        cav_wrappers = self.scan_analysis_cntrl.cav_wrappers[row:]
        self._performAction(cav_wrappers)

class StopAnalysis_Action:
    """ Stop the analysis for all cavities. """ 
    def __init__(self,upper_panel_cntrl):
        self.upper_panel_cntrl = upper_panel_cntrl

    def performAction(self):
        """ It stops the analysis """
        self.scan_analysis_cntrl = self.upper_panel_cntrl.scan_analysis_cntrl
        self.analysis_stopper = self.scan_analysis_cntrl.analysis_stopper
        self.analysis_stopper.setShouldStop(True)
        
class SaveOM_Action:
    """ 
    Saves the Online Model parameters into the ASCII file for future use.
    """
    def __init__(self,saveParamsOM_Widget):
        self.saveParamsOM_Widget = saveParamsOM_Widget
        self.bottom_panel_cntrl = self.saveParamsOM_Widget.bottom_panel_cntrl
        self.scan_analysis_cntrl = self.bottom_panel_cntrl.scan_analysis_cntrl
        self.cavs_phase_scan_cntrl = self.scan_analysis_cntrl.cavs_phase_scan_cntrl
        self.lace_scl_wizard = self.cavs_phase_scan_cntrl.lace_scl_wizard
        self.scl_om = self.lace_scl_wizard.scl_om
        self.model_cavs = self.lace_scl_wizard.getOM().getModelCavs()
        self.cav_wrappers = self.lace_scl_wizard.getCavWrappers()
        self.bpm_wrappers = self.lace_scl_wizard.getBPM_Wrappers()        
    
    def performAction(self):
        """ Saves OM parameters """
        self.saveParamsOM_Widget.save_status_text.setText("")
        cav_wrappers = self.scan_analysis_cntrl.cav_wrappers[1:]
        cav_wrappers_bad = []
        for cav_wrapper in cav_wrappers:
            if(not cav_wrapper.isGood): continue
            if(not cav_wrapper.isAnalyzed):
                cav_wrappers_bad.append(cav_wrapper)
        if(len(cav_wrappers_bad) > 0):
            txt = "Cannot create OM. Some cavities were not been analyzed. "
            txt += "Starts with cav.="+cav_wrappers_bad[0].getAlias()
            self.saveParamsOM_Widget.save_status_text.setText(txt)
            return
        self._performAction(cav_wrappers)

    def performActionForSelected(self):
        """ Saves OM parameters for selected cavities """
        self.saveParamsOM_Widget.save_status_text.setText("")
        cav_selection_model = self.scan_analysis_cntrl.cavs_table_view.selectionModel()
        cav_wrappers = self.scan_analysis_cntrl.cav_wrappers
        cav_name_column_ind = 0
        QModelIndex_list = cav_selection_model.selectedIndexes()
        cavs_list = []
        for q_model_ind in QModelIndex_list:
            if(q_model_ind.column() != cav_name_column_ind): continue
            row = q_model_ind.row()
            cav_wrapper = cav_wrappers[row]
            if(not cav_wrapper.isGood):
                cav_wrapper.cleanAllScanData()
                #continue
            if(cav_wrapper.getAlias() == "CCL4"): continue
            cavs_list.append(cav_wrapper)
        self._performAction(cavs_list)        
        
    def _performAction(self,cav_wrappers):
        """ 
        Saves OM parameters for selected cavities.
        The relation between model and EPICS phases:
        model_cav_phase = epics_cav_phase + cav_phase_offset
        cav_phase_offset = model_cav_phase - epics_cav_phase
        """
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getSaveFileName(
            self.lace_scl_wizard.getMainWindow(),
            "Save Online Model Params. to ASCII File",
            "",
            "OM Models Parameters (*.omf)", 
            options=options)
        if(fileName[-4:] != ".omf"): fileName += ".omf"
        if fileName == None:
            return
        fl_out = open(fileName,"w")
        st = "#  cav_name  model_cav_amp   cav_phase_offset  cav_phase_EPICS eKinIn eKinOut eKinOutBPMs cav_amp_EPICS"
        fl_out.write(st + "\n")
        for cav_wrapper in cav_wrappers:
            cav_name = cav_wrapper.getAlias()
            model_cav_amp = cav_wrapper.model_cav.getModelAmp()
            #model_cav_phase = cav_wrapper.model_cav.getModelPhase()
            cav_phase_offset = cav_wrapper.getModelCavityPhaseOffset()
            cav_phase_EPICS = cav_wrapper.epicsPhase
            eKin_model_in = cav_wrapper.eKin_model_in
            eKin_model_out = cav_wrapper.eKin_model_out
            eKin_BPM_out = cav_wrapper.eKin_out
            cav_amp_EPICS = cav_wrapper.epicsAmp
            st = cav_name + " %6.4f "%model_cav_amp + " %+7.2f "%cav_phase_offset
            st += " %+7.2f "%cav_phase_EPICS + " %9.3f "%eKin_model_in + " %9.3f "%eKin_model_out + " %9.3f "%eKin_BPM_out
            st += " %8.4f "%cav_amp_EPICS
            fl_out.write(st + "\n")
        #---------------------------------
        self.testOnlineModel(cav_wrappers)
        fl_out.close()

    def testOnlineModel(self,cav_wrappers):
        """
        This test will track bunch through the part of the lattice 
        after initialization to the found model parameters.
        """
        #---- Let's create a copy of the Online Model and use it
        scl_om = self.scl_om.getNewOM()
        model_cavs = scl_om.getModelCavs()
        for cav_wrapper in cav_wrappers:
            cav_ind = self.scan_analysis_cntrl.cav_wrappers.index(cav_wrapper)
            model_cav = model_cavs[cav_ind]
            model_cav.setCavityPhaseOffset(cav_wrapper.getModelCavityPhaseOffset())
            model_cav.setModelAmp(cav_wrapper.model_cav.getModelAmp())
            model_cav.setModelPhase(cav_wrapper.model_cav.getModelPhase())
            #model_cav.setEPICS_CavityModelPhase(cav_wrapper.epicsPhase)
        #----------------------
        bunch = get_SCL_EmptyBunch(cav_wrappers[0].eKin_model_in)
        cav_ind_start = self.scan_analysis_cntrl.cav_wrappers.index(cav_wrappers[0])
        cav_ind_stop  = self.scan_analysis_cntrl.cav_wrappers.index(cav_wrappers[-1])
        model_cav_start = model_cavs[cav_ind_start]
        model_cav_stop  = model_cavs[cav_ind_stop]
        (elem_ind_start, tmp_ind) = model_cav_start.getStartStopInds()
        (tmp_ind, elem_ind_stop) = model_cav_stop.getStartStopInds()
        scl_om.trackDesignBunch(bunch,elem_ind_start,elem_ind_stop)
        scl_om.trackBunch(bunch,elem_ind_start,elem_ind_stop)
        for model_cav in model_cavs[cav_ind_start:cav_ind_stop+1]:
            (eKin_in,eKin_out) = model_cav.get_eKinInOut()
            print ("debug cav=",model_cav.getName()," (eKin_in,eKin_out) = %8.3f  %8.3f "%(eKin_in,eKin_out))
            
            
        