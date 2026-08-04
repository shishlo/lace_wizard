"""
Controller for BPM Phase Offsets. Next, we will analyze scan the data. 
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

#----------------------------------------------------------
# Internal Sub - Controller for BPM Offsets calculations 
# and measurements.
# The parent is SCL Phase Scan and Analysis.
#----------------------------------------------------------

class BPM_Offsets_Cntrl:
    """
    Controller for BPM Offsets calculations and measurements.
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
        self.tab_name = "BPM Offsets"
        #----
        
        groupBox_style = StyleSheetFactory.groupBoxStyleSheet()

        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.getMainWidget().setLayout(main_layout)
        
    def getTabName(self):
        """ Returns the tab name the controller """
        return self.tab_name

    def getMainWidget(self):
        """ Returns the mainWidget (window) """
        return self.mainWidget

    def getCavWrappers(self):
        return self.cav_wrappers
        
    def getBPM_Wrappers(self):
        return self.bpm_wrappers