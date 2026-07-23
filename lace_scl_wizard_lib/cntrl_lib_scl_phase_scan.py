"""
Controller for SCL cavities phase scans. Next, we will analyze the data. 
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
from .phase_scan_lib import ScanStateController, PhaseScan_Runner, ScanWorkerSignals 

#----------------------------------------------------------
# Custom QtWidgets
#----------------------------------------------------------

#----------------------------------------------------------
# Internal Sub - Controller for SCL Phase Scan.
# The parent is SCL Phase Scan and Analysis.
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
        
        groupBox_style = StyleSheetFactory.groupBoxStyleSheet()

        #---- The QWidget with Cavities and BPMs tables
        self.cavs_table_view = LACE_QTableView()
        self.cavs_data_table_model = CavsScanDataTableModel(self)
        self.cavs_table_view.setModel(self.cavs_data_table_model)
        #self.cavs_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.cavs_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cavs_table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.cavs_table_view.selectionModel().selectionChanged.connect(self._cavsSelectionChanged)
        
        #--- connection to cav_table_view in the initial state controller
        init_cavs_table_model = self.lace_scl_wizard.init_state_cntrl.cavs_data_table_model
        init_cavs_table_model.addDependentTableModel(self.cavs_data_table_model)

        #---- BPMs that will be used for analysis
        self.bpms_table_view = LACE_QTableView()
        self.bpms_use_table_model = BPMsForAnalysisTableModel(self)
        self.bpms_table_view.setModel(self.bpms_use_table_model)
        self.bpms_table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.bpms_table_view.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeToContents)
        self.bpms_table_view.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        self.bpms_table_view.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
        self.bpms_table_view.selectionModel().selectionChanged.connect(self.bpmsSelectionChanged)

        #---- Tab for BPM table name
        self.bpms_tab_panel = QTabWidget()
        self.bpms_tab_panel.setTabPosition(QTabWidget.TabPosition.North)
        self.bpms_tab_panel.setMovable(False)
        self.bpms_tab_panel.addTab(self.bpms_table_view,"Cavity None")

        #---- upper panel
        self.upper_panel_cntrl = UpperScanPanelCntrl(self)

        #---- bottom panel with plots and bpm data cleaning buttons
        self.bottom_panel_cntrl = BottomScanPanelCntrl(self)
        
        central_layout = QHBoxLayout()
        central_layout.setSpacing(0)
        central_layout.setContentsMargins(0, 0, 0, 0)   
        central_layout.addWidget(self.cavs_table_view,1)
        central_layout.addWidget(self.bpms_tab_panel)
        
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
        self.bpm_phase_diff_line, self.bpm_phase_diff_fit_line = self.getLineAndFitBPM_DiffPhaseScan()
        self.setupBPM_PhaseAmpPlots()
        #---- lines Phase&Amp. vs Cav. Phase on the two bottom plots
        self.bpm_phase_amp_lines = []
        
        #---- Signals for table and plot update during the phasee scan thread execution
        self.scan_worker_signals = ScanWorkerSignals()
        
        self.getMainWidget().setLayout(main_layout)
        
        #---- Scan state controller aka Scan Stopper
        self.scan_stopper = ScanStateController()
        self.threadpool = QThreadPool()
        
    def getTabName(self):
        """ Returns the tab name the controller """
        return self.tab_name

    def getMainWidget(self):
        """ Returns the mainWidget (window) """
        return self.mainWidget

    def getCavWrappers(self):
        return self.cav_wrappers
    
    @Slot("QtCore.QItemSelection*")
    def _cavsSelectionChanged(self,selected,deselected):
        """ Updates right BPM table for particular cavity with selected index """
        #---- selected.indexes() and deselected.indexes() with index.row() and index.column()
        if(selected.isEmpty()):
            self.bpms_tab_panel.setTabText(0,"Cavity None")
            self.bpms_use_table_model.setCavWrapper(None)
            title = "Phase Scan. Cavity = None"
            self.bottom_panel_cntrl.bpm_phase_diff_plot.setTitle(title)
            self.bottom_panel_cntrl.bpmPhasePlot().setTitle(title)
            self.bottom_panel_cntrl.bpmAmpPlot().setTitle(title)            
            return
        row = selected.indexes()[0].row()
        #----
        cav_wrapper = self.cav_wrappers[row]
        self.bpms_tab_panel.setTabText(0,cav_wrapper.getAlias())
        self.bpms_use_table_model.setCavWrapper(cav_wrapper)
        #---- plot the graph of phase difference for bpm 0 and 1
        title = "Phase Scan. Cavity = " + cav_wrapper.getAlias()
        self.bottom_panel_cntrl.bpm_phase_diff_plot.setTitle(title)
        self.bottom_panel_cntrl.bpmPhasePlot().setTitle(title)
        self.bottom_panel_cntrl.bpmAmpPlot().setTitle(title)
        (x_arr,y_arr,y_err_arr) = cav_wrapper.phaseDiffBPM01_func.getXYErrLists()
        self.bpm_phase_diff_line.setData(x_arr,y_arr)
        (x_arr,y_arr,y_err_arr) = cav_wrapper.phaseDiffBPM01_fit_func.getXYErrLists()
        self.bpm_phase_diff_fit_line.setData(x_arr,y_arr)
        self.bpmsSelectionChanged(None,None)
    
    @Slot("QtCore.QItemSelection*")
    def bpmsSelectionChanged(self,selected,deselected):
        #---- clean all old lines
        bpm_phase_plot = self.bottom_panel_cntrl.bpmPhasePlot()
        bpm_amp_plot = self.bottom_panel_cntrl.bpmAmpPlot()        
        for (plot_amp_line_ref,plot_phase_line_ref) in self.bpm_phase_amp_lines:
            if(plot_amp_line_ref != None):
                bpm_amp_plot.removeItem(plot_amp_line_ref)
                plot_amp_line_ref.deleteLater()
                plot_amp_line_ref = None
            if(plot_phase_line_ref != None):
                bpm_phase_plot.removeItem(plot_phase_line_ref)
                plot_phase_line_ref.deleteLater()
                plot_phase_line_ref = None
        #---- 
        self.bpm_phase_amp_lines.clear()
        cav_wrapper = self.bpms_use_table_model.cav_wrapper
        if(cav_wrapper == None): return
        index_rows = self.bpms_table_view.selectionModel().selectedRows()
        for index_row in index_rows:
            row_ind = index_row.row()
            bpm_wrapper = self.bpm_wrappers[row_ind]
            bpm_alias = bpm_wrapper.getAlias()
            (bpm_amp_line_ref,bpm_phase_line_ref) = self.getBPM_AmpPhaseLines(cav_wrapper,bpm_wrapper)
            (funcAmp,funcPhase) = cav_wrapper.bpm_amp_phase_dict[bpm_alias]
            (x_arr,y_arr,y_err_arr) = funcAmp.getXYErrLists()
            bpm_amp_line_ref.setData(x_arr,y_arr)
            (x_arr,y_arr,y_err_arr) = funcPhase.getXYErrLists()
            bpm_phase_line_ref.setData(x_arr,y_arr)          
            self.bpm_phase_amp_lines.append((bpm_amp_line_ref,bpm_phase_line_ref))     

    def getBPM_AmpPhaseLines(self,cav_wrapper,bpm_wrapper):
        colors = ['w','r','g','b']
        color = colors[len(self.bpm_phase_amp_lines) % len(colors)]
        bpm_amp_plot = self.bottom_panel_cntrl.bpmAmpPlot()
        bpm_phase_plot = self.bottom_panel_cntrl.bpmPhasePlot()
        bpm_alias = bpm_wrapper.getAlias()
        bpm_amp_line = bpm_amp_plot.plot(pen='white', linestyle="-", symbol="o", symbolBrush=color,symbolSize=5, name=html.unescape(bpm_alias))
        bpm_phase_line = bpm_phase_plot.plot(pen='white', linestyle="-", symbol="o", symbolBrush=color,symbolSize=5, name=html.unescape(bpm_alias))
        return (bpm_amp_line,bpm_phase_line)
        
        
    def dumpCntrlDataToDA(self,parent_da):
        """ Puts this controller data into the Data Adaptor """
        return

    def readCntrlDataFromDA(self,parent_da):
        """ Reads data for this controller from the Data Adaptor """
        return

    def getLineAndFitBPM_DiffPhaseScan(self):
        """ 
        Sets up parameters of PlotWidget instance and 
        adds plot of difference BPM12 phases vs. cavity phase 
        """ 
        bpm_phase_diff_plot = self.bottom_panel_cntrl.bpmPhaseDiffPlot()
        bpm_phase_diff_plot.showGrid(True, True)
        legend = bpm_phase_diff_plot.addLegend(labelTextSize='12pt', labelTextColor="white")
        legend.anchor((0, 0), (0, 0))
        bpm_phase_diff_plot.setTitle("Phase Scan")
        bpm_phase_diff_plot.setLabel('bottom', html.unescape("Cavity EPICS &phi;"), units='deg')
        bpm_phase_diff_plot.setLabel('left', html.unescape("&Delta; &phi;<sub>12</sub>"), units='deg')
        bpm_phase_diff_plot.getAxis('left').setTextPen('white')
        bpm_phase_diff_plot.getAxis('bottom').setTextPen('white')
        #---- Now these data will be shown on the plot
        bpm_phase_diff_line = bpm_phase_diff_plot.plot(pen='white', linestyle="-", symbol="o", symbolBrush='r',symbolSize=5, name=html.unescape("&Delta; &phi;<sub>12</sub>"))
        #bpm_phase_diff_line = bpm_phase_diff_plot.plot(pen=None, symbol="o", symbolSize=5, symbolBrush='r', name=html.unescape("&Delta; &phi;<sub>12</sub>"))
        bpm_phase_diff_fit_line = bpm_phase_diff_plot.plot(pen="red",  linestyle="-", name=html.unescape("Fit &Delta; &phi;<sub>12</sub>"))        
        return (bpm_phase_diff_line,bpm_phase_diff_fit_line)
    
    def setupBPM_PhaseAmpPlots(self):
        """ Adds plot data to the PlotWidget instance for bpm  amp. and phase vs. cav. phase """
        bpm_phase_plot = self.bottom_panel_cntrl.bpmPhasePlot()
        bpm_phase_plot.showGrid(True, True)
        legend = bpm_phase_plot.addLegend(labelTextSize='12pt', labelTextColor="white")
        legend.anchor((0, 0), (0, 0))
        bpm_phase_plot.setTitle("BPM Phase")
        bpm_phase_plot.setLabel('bottom', html.unescape("Cavity EPICS &phi;"), units='deg')
        bpm_phase_plot.setLabel('left', html.unescape("&phi;<sub>BPM</sub>"), units='deg')
        bpm_phase_plot.getAxis('left').setTextPen('white')
        bpm_phase_plot.getAxis('bottom').setTextPen('white')
        #-----------------------------------------------
        bpm_amp_plot = self.bottom_panel_cntrl.bpmAmpPlot()
        bpm_amp_plot.showGrid(True, True)
        legend = bpm_amp_plot.addLegend(labelTextSize='12pt', labelTextColor="white")
        legend.anchor((0, 0), (0, 0))
        bpm_amp_plot.setTitle("BPM Amplitude")
        bpm_amp_plot.setLabel('bottom', html.unescape("Cavity EPICS &phi;"), units='deg')
        bpm_amp_plot.setLabel('left', html.unescape("Amp<sub>BPM</sub>"), units='mA')
        bpm_amp_plot.getAxis('left').setTextPen('white')
        bpm_amp_plot.getAxis('bottom').setTextPen('white')            

    @Slot(tuple)     
    def scanDataUpdate(self,tuple_input):
        """ Perfoms all actions on GUI """
        (update_type,*rest) = tuple_input
        #---- Type of message - Scan status update
        if(update_type == "status_update"):
            msg_txt = rest[0]
            self.upper_panel_cntrl.scan_status_text.setText(msg_txt)
            return
        if(update_type == "update_bpm_phases_plot"):
            cav_wrapper = rest[0]
            (x_arr,y_arr,y_err_arr) = cav_wrapper.phaseDiffBPM01_func.getXYErrLists()
            self.bpm_phase_diff_line.setData(x_arr,y_arr)
            (x_arr,y_arr,y_err_arr) = cav_wrapper.phaseDiffBPM01_fit_func.getXYErrLists()
            self.bpm_phase_diff_fit_line.setData(x_arr,y_arr)            
            self.bpmsSelectionChanged(None,None)
        #---- Type of message - Scan status update
        if(update_type == "table_selection_clear"):
            self.cavs_table_view.clearSelection()
            return
        if(update_type == "table_selection_set"):
            cav_ind = rest[0]
            self.cavs_table_view.selectRow(cav_ind)
            return
        if(update_type == "table_changed"):
            self.cavs_data_table_model.tableChanged() 
            return          
        return

    def stopAllThreads(self):
        """ Stops all threads of this controller """
        #self.scanStopper.setSetToStop(True)
        return
       
#----------------------------------------------------------
# Actions on events with buttons 
#----------------------------------------------------------
class SetSyncPhase_Action:
    """ Sets syncronous accelerating phase to the selected cavities. """
    def __init__(self,upper_panel_cntrl):
        self.upper_panel_cntrl = upper_panel_cntrl
        
    def performAction(self):
        """ Sets syncronous accelerating phase to the selected cavities. """
        synch_phase = self.upper_panel_cntrl.sync_phase_double_spin_box.value()
        self.cavs_scan_cntrl = self.upper_panel_cntrl.cavs_scan_cntrl
        cav_selection_model = self.cavs_scan_cntrl.cavs_table_view.selectionModel()
        cav_wrappers = self.cavs_scan_cntrl.cav_wrappers
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
        for cav_wrapper in cavs_list:
            cav_wrapper.synch_acc_phase = synch_phase
        #cav_selection_model.clearSelection()
        self.cavs_scan_cntrl.cavs_data_table_model.tableChanged()
        #print ("debug Sets syncronous accelerating phase.")
        

class StartScan_Action:
    """ Starts the phase scans of all or selected cavities. """ 
    def __init__(self,upper_panel_cntrl):
        self.upper_panel_cntrl = upper_panel_cntrl

    def _performAction(self,cav_wrappers):
        """ It starts the phase scan the cavities from cav_wrappers list """
        wait_time = self.upper_panel_cntrl.scan_wait_time_spin_box.value()
        max_sin_amp_err = self.upper_panel_cntrl.max_sin_amp_err_spin_box.value()
        self.cavs_scan_cntrl = self.upper_panel_cntrl.cavs_scan_cntrl
        self.cavs_phase_scan_cntrl = self.upper_panel_cntrl.cavs_phase_scan_cntrl
        self.cavs_table_view = self.cavs_scan_cntrl.cavs_table_view
        self.cavs_scan_cntrl.cavs_table_view.selectionModel().clearSelection()
        scan_worker_signals = self.cavs_scan_cntrl.scan_worker_signals
        phase_scan_runner = PhaseScan_Runner(self.cavs_scan_cntrl,cav_wrappers)
        scan_worker_signals.scan_data_changed.connect(self.cavs_scan_cntrl.scanDataUpdate)
        self.cavs_scan_cntrl.threadpool.start(phase_scan_runner)
        #print ("debug Starts the phase scans for all or selected cavities. ")
        
    def performActionForSelected(self):
        self.cavs_scan_cntrl = self.upper_panel_cntrl.cavs_scan_cntrl
        #---- We cannot start a second scan -------
        scan_stopper = self.cavs_scan_cntrl.scan_stopper
        if(scan_stopper.getIsRunning()): return
        #------------------------------------------
        cav_selection_model = self.cavs_scan_cntrl.cavs_table_view.selectionModel()
        cav_wrappers = self.cavs_scan_cntrl.cav_wrappers
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
        #print ("debug start scans for selected cavities.")   
        
    def performAction(self):
        self.cavs_scan_cntrl = self.upper_panel_cntrl.cavs_scan_cntrl
        cav_selection_model = self.cavs_scan_cntrl.cavs_table_view.selectionModel()
        QModelIndex_list = cav_selection_model.selectedIndexes()
        row = 0
        if(len(QModelIndex_list) > 0):
            row = QModelIndex_list[0].row()
        #---- We cannot start a second scan -------
        scan_stopper = self.cavs_scan_cntrl.scan_stopper
        if(scan_stopper.getIsRunning()): return
        #------------------------------------------
        cav_wrappers = self.cavs_scan_cntrl.cav_wrappers[row:]
        self._performAction(cav_wrappers)
        #print ("debug Starts the phase scans for all cavities. ")

class StopScan_Action:
    """ Stop the phase scans for all cavities. """ 
    def __init__(self,upper_panel_cntrl):
        self.upper_panel_cntrl = upper_panel_cntrl

    def performAction(self):
        """ It stops the phase scan """
        self.cavs_scan_cntrl = self.upper_panel_cntrl.cavs_scan_cntrl
        self.scan_stopper = self.cavs_scan_cntrl.scan_stopper
        self.scan_stopper.setShouldStop(True)
        #print ("debug Stops the phase scans. ")

#----------------------------------------------------------
#  Sub-panels for knobs and tables
#----------------------------------------------------------

class UpperScanPanelCntrl:
    """
    The upper panel in the SCL Phase Scan tab with parameters of the scan
    and start-stop_resume knobs.
    """
    def __init__(self,cavs_scan_cntrl):
        self.cavs_scan_cntrl = cavs_scan_cntrl
        self.cavs_phase_scan_cntrl = self.cavs_scan_cntrl.cavs_phase_scan_cntrl
        self.lace_scl_wizard = self.cavs_phase_scan_cntrl.lace_scl_wizard
        self.model_cavs = self.lace_scl_wizard.getOM().getModelCavs()
        self.cav_wrappers = self.lace_scl_wizard.getCavWrappers()
        self.bpm_wrappers = self.lace_scl_wizard.getBPM_Wrappers()
        #---- main widget
        self.mainWidget = QGroupBox()

        buttons_style = StyleSheetFactory.pushButtonStyleSheet()
        groupBox_style = StyleSheetFactory.groupBoxStyleSheet()

        #---- vertical layout
        vlayout = QVBoxLayout()
        # Set spacing between widgets to 0
        vlayout.setSpacing(0)
        # Remove margins around the layout (top, bottom, left, right)
        vlayout.setContentsMargins(0, 0, 0, 0)

        hor_view_1 = QWidget()
        hor_view_2 = QWidget()
        hor_layout_1 = QHBoxLayout()
        hor_layout_2 = QHBoxLayout()
        hor_layout_1.setSpacing(0)
        hor_layout_2.setSpacing(0)
        hor_layout_1.setContentsMargins(0, 0, 0, 0)
        hor_layout_2.setContentsMargins(0, 0, 0, 0)
        hor_layout_1.setAlignment(Qt.AlignLeft)
        hor_layout_2.setAlignment(Qt.AlignLeft)
        hor_view_1.setLayout(hor_layout_1)
        hor_view_2.setLayout(hor_layout_2)

        vlayout.addWidget(hor_view_1)
        vlayout.addWidget(hor_view_2)

        #----------------------------------------------
        #---- upp line - hor_view_1 panel
        #----------------------------------------------
        setSynchPhase_button = QPushButton(text=html.unescape("Set Sync. &phi; to Selected Cavs [deg]="),parent=None)
        setSynchPhase_button.setStyleSheet(buttons_style)

        self.sync_phase_double_spin_box = QDoubleSpinBox()
        self.sync_phase_double_spin_box.setRange(-180.0, 180.0) # Set min/max range
        self.sync_phase_double_spin_box.setDecimals(1)          # Set precision to 2 decimal places
        self.sync_phase_double_spin_box.setSingleStep(0.1)      # Set step size for arrow buttons
        self.sync_phase_double_spin_box.setValue(-15.0)         # Set default value

        scan_wait_time_label = QLabel("   Scan Wait t[sec]=")
        self.scan_wait_time_spin_box = QDoubleSpinBox()
        self.scan_wait_time_spin_box.setRange(0.,10.)    # Set min/max range
        self.scan_wait_time_spin_box.setDecimals(2)      # Set precision to 2 decimal places
        self.scan_wait_time_spin_box.setSingleStep(0.05) # Set step size for arrow buttons
        self.scan_wait_time_spin_box.setValue(0.5)       # Set default value

        max_sin_amp_err_label = QLabel("    Max Sin Amp. Err[deg]=")
        self.max_sin_amp_err_spin_box = QDoubleSpinBox()
        self.max_sin_amp_err_spin_box.setRange(0.,180.)   # Set min/max range
        self.max_sin_amp_err_spin_box.setDecimals(1)      # Set precision to 2 decimal places
        self.max_sin_amp_err_spin_box.setSingleStep(0.5)  # Set step size for arrow buttons
        self.max_sin_amp_err_spin_box.setValue(4.0)       # Set default value

        stat_for_in_enrg_label = QLabel(html.unescape("&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Statistics for E<sub>kin</sub>="))
        self.stat_for_in_enrg_spin_box = QDoubleSpinBox()
        self.stat_for_in_enrg_spin_box.setRange(1.,30.)    # Set min/max range
        self.stat_for_in_enrg_spin_box.setDecimals(0)      # Set precision to 2 decimal places
        self.stat_for_in_enrg_spin_box.setSingleStep(1)    # Set step size for arrow buttons
        self.stat_for_in_enrg_spin_box.setValue(3.0)       # Set default value
        
        self.wrap_phase_checkbox = QCheckBox("Wrap Phases")
        self.wrap_phase_checkbox.setChecked(True)
        self.keep_phases_checkbox = QCheckBox("Keep Cavs Phases")
        self.keep_phases_checkbox.setChecked(False)

        hor_layout_1.addWidget(setSynchPhase_button)
        hor_layout_1.addWidget(self.sync_phase_double_spin_box)
        hor_layout_1.addWidget(scan_wait_time_label)
        hor_layout_1.addWidget(self.scan_wait_time_spin_box)
        hor_layout_1.addWidget(max_sin_amp_err_label)
        hor_layout_1.addWidget(self.max_sin_amp_err_spin_box)
        hor_layout_1.addWidget(stat_for_in_enrg_label)
        hor_layout_1.addWidget(self.stat_for_in_enrg_spin_box)
        hor_layout_1.addWidget(QLabel("   "))
        hor_layout_1.addWidget(self.wrap_phase_checkbox)
        hor_layout_1.addWidget(self.keep_phases_checkbox)  

        #----------------------------------------------
        #---- lower line - hor_view_2 panel
        #----------------------------------------------
        phase_scan_step_label = QLabel("Phase Step[deg]=")
        self.phase_scan_step_spin_box = QDoubleSpinBox()
        self.phase_scan_step_spin_box.setRange(0.,180.)    # Set min/max range
        self.phase_scan_step_spin_box.setDecimals(0)      # Set precision to 2 decimal places
        self.phase_scan_step_spin_box.setSingleStep(1)    # Set step size for arrow buttons
        self.phase_scan_step_spin_box.setValue(20.0)      # Set default value

        start_scan_button = QPushButton(text="Start Scan",parent=None)
        start_scan_button.setStyleSheet(buttons_style)
        start_scan_button.adjustSize()

        start_scan_selected_button = QPushButton(text="Start Selected Cavs",parent=None)
        start_scan_selected_button.setStyleSheet(buttons_style)

        stop_scan_button = QPushButton(text="Stop Scan",parent=None)
        stop_scan_button.setStyleSheet(buttons_style)
        
        #---- cavs button action assignment
        setSyncPhase_Action = SetSyncPhase_Action(self) 
        startScan_Action = StartScan_Action(self)
        stopScan_Action = StopScan_Action(self)

        setSynchPhase_button.clicked.connect(lambda: setSyncPhase_Action.performAction())
        start_scan_button.clicked.connect(lambda: startScan_Action.performAction())
        start_scan_selected_button.clicked.connect(lambda: startScan_Action.performActionForSelected())
        stop_scan_button.clicked.connect(lambda: stopScan_Action.performAction())
        
        self.scan_status_text = QLineEdit("Scan status:")
        self.scan_status_text.setStyleSheet("color: blue; background-color: white;")

        hor_layout_2.addWidget(phase_scan_step_label)
        hor_layout_2.addWidget(self.phase_scan_step_spin_box)
        hor_layout_2.addWidget(start_scan_button)
        hor_layout_2.addWidget(start_scan_selected_button)
        hor_layout_2.addWidget(stop_scan_button)
        hor_layout_2.addWidget(self.scan_status_text,1)

        #---- set layout for main widget
        self.mainWidget.setLayout(vlayout)
        
        #---- Define the style sheet for the border
        self.mainWidget.setStyleSheet(groupBox_style)
        
    def getMainWidget(self):
        """ Returns the mainWidget (window) """
        return self.mainWidget

class BottomScanPanelCntrl:
    """
    The bottom panel in the SCL Phase Scan tab with BPMs phases and amplitudes
    vs. cavity's phases and BPMs data cleaning control buttons.
    """
    def __init__(self,cavs_scan_cntrl):
        self.cavs_scan_cntrl = cavs_scan_cntrl
        self.cavs_phase_scan_cntrl = self.cavs_scan_cntrl.cavs_phase_scan_cntrl        
        self.lace_scl_wizard = self.cavs_phase_scan_cntrl.lace_scl_wizard
        self.model_cavs = self.lace_scl_wizard.getOM().getModelCavs()
        self.cav_wrappers = self.lace_scl_wizard.getCavWrappers()
        self.bpm_wrappers = self.lace_scl_wizard.getBPM_Wrappers()
        #---- main widget
        self.mainWidget = QFrame()
       
        buttons_style = StyleSheetFactory.pushButtonStyleSheet()
        groupBox_style = StyleSheetFactory.groupBoxStyleSheet()

        #---- vertical layout
        vlayout = QVBoxLayout()
        # Set spacing between widgets to 0
        vlayout.setSpacing(0)
        # Remove margins around the layout (top, bottom, left, right)
        vlayout.setContentsMargins(0, 0, 0, 0)
        
        #---- Plots panels
        self.bpm_phase_plot = pg.PlotWidget()
        self.bpm_amp_plot = pg.PlotWidget()
        self.bpm_phase_diff_plot = pg.PlotWidget()
        
        right_plots_layout = QGridLayout()
        right_plots_layout.setSpacing(0)
        right_plots_layout.setContentsMargins(0, 0, 0, 0)
        
        right_plots_layout.addWidget(self.bpmPhasePlot(),0,0)
        right_plots_layout.addWidget(self.bpmAmpPlot(),1,0)
        
        right_plots_view = QWidget()
        right_plots_view.setLayout(right_plots_layout)
        
        all_plots_layout = QGridLayout()
        right_plots_layout.setSpacing(0)
        right_plots_layout.setContentsMargins(0, 0, 0, 0)        
        
        all_plots_layout.addWidget(self.bpmPhaseDiffPlot(),0,0)
        all_plots_layout.addWidget(right_plots_view,0,1)
        
        plots_view = QGroupBox("BPMs data plots")
        plots_view.setLayout(all_plots_layout)
        
        #---- Define the style sheet for the border
        plots_view.setStyleSheet(groupBox_style)
        
        vlayout.addWidget(plots_view, 1)
          
        #---- BPM amplitude limit clean up
        bpm_limit_hlayout = QHBoxLayout()
        bpm_limit_hlayout.setSpacing(0)
        bpm_limit_hlayout.setContentsMargins(0, 0, 0, 0)        
        bpm_limit_hlayout.setAlignment(Qt.AlignLeft)
        
        bpm_limit_view = QGroupBox("Post-scan Actions")
        
        #---- Define the style sheet for the border
        bpm_limit_view.setStyleSheet(groupBox_style)
        
        bpm_amp_limits_label = QLabel("Minimal BPM Amp.=")
        
        self.bpm_min_amp_spin_box = QDoubleSpinBox()
        self.bpm_min_amp_spin_box.setRange(0.,100.)  # Set min/max range
        self.bpm_min_amp_spin_box.setDecimals(1)     # Set precision to 2 decimal places
        self.bpm_min_amp_spin_box.setSingleStep(0.5) # Set step size for arrow buttons
        self.bpm_min_amp_spin_box.setValue(1.0)      # Set default value
        
        bpm_min_amp_button = QPushButton(text="Apply BPM Amp. Limit",parent=None)
        bpm_min_amp_button.setStyleSheet(buttons_style)
        bpm_min_amp_button.adjustSize()
        
        bpm_limit_hlayout.addWidget(bpm_amp_limits_label)
        bpm_limit_hlayout.addWidget(self.bpm_min_amp_spin_box)
        bpm_limit_hlayout.addWidget(bpm_min_amp_button)
        
        bpm_limit_view.setLayout(bpm_limit_hlayout)
        
        #---- final bottom panel content
        vlayout.addWidget(bpm_limit_view)

        #---- set layout for main widget
        self.mainWidget.setLayout(vlayout)

    def getMainWidget(self):
        """ Returns the mainWidget (window) """
        return self.mainWidget
        
    def bpmPhasePlot(self):
        return self.bpm_phase_plot
        
    def bpmAmpPlot(self):
        return self.bpm_amp_plot
        
    def bpmPhaseDiffPlot(self):
        return self.bpm_phase_diff_plot

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
        headers = ["Cavity","Good","Done","BPM 1","BPM 2","Old Phase","New Phase","SinAmp","SinFitErr","AccPhase"]
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
            #--------------------------------
            if(cav_ind == 0):
                for item_ind in range(3,self.columnCount()):
                    item = self.item(cav_ind,item_ind)
                    item.setText("")
                continue
            #--------------------------------
            bpm1_item = self.item(cav_ind,3)
            if(cav_wrapper.bpm_wrapper0 != None):
                bpm1_item.setText("%10s"%cav_wrapper.bpm_wrapper0.getAlias())
            else:
                 bpm1_item.setText("")
            bpm2_item = self.item(cav_ind,4)
            if(cav_wrapper.bpm_wrapper1 != None):
                bpm2_item.setText("%10s"%cav_wrapper.bpm_wrapper1.getAlias())
            else:
                 bpm2_item.setText("")
            epics_phase_old_item = self.item(cav_ind,5) ; epics_phase_old_item.setText("%+6.1f"%cav_wrapper.epicsPhaseInit)
            epics_phase_new_item = self.item(cav_ind,6) ; epics_phase_new_item.setText("%+6.1f"%cav_wrapper.epicsPhase)
            scan_phase_sinAmp_item = self.item(cav_ind,7) ; scan_phase_sinAmp_item.setText("%6.1f"%cav_wrapper.sin_phase_func_amp)
            scan_phase_errAmp_item = self.item(cav_ind,8) ; scan_phase_errAmp_item.setText("%5.1f"%cav_wrapper.sin_phase_func_amp_err)      
            synch_phase_item = self.item(cav_ind,9) ; synch_phase_item.setText("%+6.1f"%cav_wrapper.synch_acc_phase)

class BPMsForAnalysisTableModel(LACE_DataTableModel):
    def __init__(self,cavs_scan_cntrl):
        super().__init__()
        self.cavs_scan_cntrl = cavs_scan_cntrl
        self.cavs_phase_scan_cntrl = self.cavs_scan_cntrl.cavs_phase_scan_cntrl
        self.lace_scl_wizard = self.cavs_phase_scan_cntrl.lace_scl_wizard
        self.bpm_wrappers = self.lace_scl_wizard.getBPM_Wrappers()
        self.cav_wrapper = None
        #---- Sets the headers
        #---- OEDA stands for Off Energy Delay Adjustment
        headers = ["BPM","Good","Use"]
        self.setHorizontalHeaderLabels(headers)
        for bpm_ind,bpm_wrapper in enumerate(self.bpm_wrappers):
            bpm_name_item = QStandardItem(bpm_wrapper.getAlias())
            bpm_good_item = QStandardItem()
            bpm_good_item.setCheckable(False)
            bpm_use_item = QStandardItem()
            bpm_use_item.setCheckable(True)
            self._updateBoolItem(False,bpm_use_item)
            row = [bpm_name_item,bpm_good_item,bpm_use_item]
            self.appendRow(row)
        self.itemChanged.connect(self.handleItemChanged)

    def setCavWrapper(self,cav_wrapper):
        self.cav_wrapper = cav_wrapper
        self._updateItemsFromData()

    @Slot("QStandardItem*")
    def handleItemChanged(self, item):
        # Verify that the modified data is related to the Qt::CheckStateRole role
        if(item.isCheckable() and item.checkState() in (Qt.Checked, Qt.Unchecked)):
            if(self.cav_wrapper == None):
                return
            self.cav_wrapper.bpm_wrappers_useInPhaseAnalysis[item.row()] = self._getValueOfBoolItem(item)

    def _updateItemsFromData(self):
        if(self.cav_wrapper == None):
            for bpm_ind,bpm_wrapper in enumerate(self.bpm_wrappers):
                self._updateBoolItem(False,self.item(bpm_ind,1))
                self._updateBoolItem(False,self.item(bpm_ind,2))
            return
        for bpm_ind,bpm_wrapper in enumerate(self.bpm_wrappers):
            item = self.item(bpm_ind,1); self._updateBoolItem(bpm_wrapper.isGood,item)
            use = self.cav_wrapper.bpm_wrappers_useInPhaseAnalysis[bpm_ind]
            if(bpm_wrapper.isGood != True): use = False
            self.cav_wrapper.bpm_wrappers_useInPhaseAnalysis[bpm_ind] = use
            item = self.item(bpm_ind,2); self._updateBoolItem(use,item)        
            
