#----------------------------------------------------------
# Main Controller for the libraries of SCL Phase Scan and
# Analysis of scan data
#----------------------------------------------------------

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

from gui_lib.borderlayout import BorderLayout, Position
from gui_lib.style_sheets_lib import StyleSheetFactory

from .cntrl_lib_scl_phase_scan import Cavs_Scan_Cntrl
from .cntrl_lib_scl_phase_scan_analysis import Scan_Analysis_Cntrl

#----------------------------------------------------------
# Controller for sub-Controllers: Phase Scan and Analysis
#----------------------------------------------------------

class Cavs_PhaseScan_and_Analisys_Cntrl:
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
        self.tab_name = "SCL Phase Scan and Analysis"

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
        """ Returns the mainWidget (window) of Cavs_PhaseScan_and_Analisys_Cntrl """
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

