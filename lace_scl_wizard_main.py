"""
This is a main LACE SCL Wizard script
"""
import os
import sys
import math
import random
import time

from epics import PV

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget
from PySide6.QtWidgets import QLabel, QTabWidget, QMenuBar
from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog

from PySide6.QtGui import QPalette, QColor, QIcon
from PySide6.QtCore import QSize, Qt

from PySide6.QtWidgets import QPushButton

# import the XmlDataAdaptor XML parser
from orbit.utils.xml import XmlDataAdaptor

from orbit.core.orbit_utils import Function

#----------------------------------------------------------
# Local (to this Wizard) import
#----------------------------------------------------------
#sys.path.append('../gui_lib/')

from lace_om_lib.scl_online_model_lib import SCL_Online_Model
from lace_scl_wizard_lib.cntrl_lib_init_state import InitState_Cntrl
from lace_scl_wizard_lib.cntrl_lib_scl_phase_scan import CavsPhaseScan_Cntrl
from lace_scl_wizard_lib.energy_meter_lib import EnergyMeter

class LACE_SCL_Wizard:
    """
    The main PyQt6 application
    """
    def __init__(self,argv):
        self.mainQApp = QApplication(argv)
        self.mainWindow = LACE_SCL_Wizard_MainWindow(self)
        self.mainWindow.setWindowTitle("LACE SCL Wizard")
        self.mainWindow.resize(1400, 600)
        self.statusLabel = self.mainWindow.getStatusLabel()
        
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setMovable(False)

        #---- CCL4-SCL-HEBT1-HEBT2 PyORBIT online model
        xml_lattice_file_name = "./sns_lattices/sns_sts_linac.xml"
        acc_da = XmlDataAdaptor.adaptorForFile(xml_lattice_file_name)
        #seq_names = ["CCL4","SCLMed", "SCLHigh", "HEBT1", "HEBT2"]
        seq_names = ["SCLMed", "SCLHigh", "HEBT1", "HEBT2"]
        self.scl_om = SCL_Online_Model(acc_da,seq_names)

        if("EPICS" in argv):
            self.scl_om.connectAllChannnels()
            print ("The LACE SCL Online Model is connected to EPICS.")
            time.sleep(1.0)

        #---- controllers for the Wizard -------------------
        self.controllers_arr = []
        #---- Initialization from EPICS
        self.init_state_cntrl = InitState_Cntrl(self)
        self.controllers_arr.append(self.init_state_cntrl)
        self.tabs.addTab(self.init_state_cntrl.getMainWidget(),self.init_state_cntrl.getTabName())

        #---- Phase scan and analysis controller
        self.cavs_phase_scan_cntrl = CavsPhaseScan_Cntrl(self)
        self.controllers_arr.append(self.cavs_phase_scan_cntrl)
        self.tabs.addTab(self.cavs_phase_scan_cntrl.getMainWidget(),self.cavs_phase_scan_cntrl.getTabName())

        #----- energy meter 
        self.energy_meter = EnergyMeter(self)

        self.mainWindow.setCentralWidget(self.tabs) 
        #-------------------------------------------------------
        #---- data file of the wizard
        self.data_file_name = None
        
    def getOM(self):
        """ Returns the SCL Online Model instance """
        return self.scl_om
        
    def getCavWrappers(self):
        """ Returns cavity wrappers list created in InitState_Cntrl() instance """
        return self.init_state_cntrl.cavs_state_cntrl.getCavWrappers()
        
    def getBPM_Wrappers(self):
        """ Returns BPM wrappers list created in InitState_Cntrl() instance """
        return self.init_state_cntrl.bpms_state_cntrl.getBPM_Wrappers()

    def getTabWidget(self,name):
        """ Returns the mainWidget of the particular 1st level tab """
        widget = None
        for ind in range(self.tabs.count()):
            if(self.tabs.tabText(ind) == name):
                return self.tabs.widget(ind)
        return widget
        
    def getStatusLabel(self):
        return self.mainWindow.getStatusLabel()     
        
    def stopAllThreads(self):
        for controller in self.controllers_arr:
            controller.stopAllThreads()

    def show(self):
        menuBar = self.mainWindow.menuBar()
        self.mainWindow.show()
        
    def dumpWizardData(self):
        if(self.data_file_name != None):
            root_da = XmlDataAdaptor()
            wizard_da = root_da.createChild("LACE_SCL_Wizard")
            for controller in self.controllers_arr:
                controller.dumpCntrlDataToDA(wizard_da)
            root_da.writeToFile(self.data_file_name)
            self.mainWindow.setWindowTitle("LACE SCL Wizard - "+str(self.data_file_name))            
            return
        else:
            self.dumpWizardDataAs()
        
    def dumpWizardDataAs(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getSaveFileName(self.mainWindow,"QFileDialog.getSaveFileName()","","Scan Data Files (*.xml)", options=options)
        if(fileName[-4:] != ".xml"): fileName += ".xml"
        if fileName:
            self.data_file_name = fileName
            self.dumpWizardData()
        
    def readWizardData(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog  
        fileName, _ = QFileDialog.getOpenFileName(self.mainWindow,"QFileDialog.getOpenFileName()", "","Scan Data Files (*.xml)", options=options)
        if fileName:
            root_da = XmlDataAdaptor.adaptorForFile(fileName)
            wizard_da = root_da.childAdaptors("LACE_SCL_Wizard")[0]
            for controller in self.controllers_arr:
                controller.readCntrlDataFromDA(wizard_da)
            self.data_file_name = fileName
            self.mainWindow.setWindowTitle("ESS DTL Wizard - "+str(fileName))   

class LACE_SCL_Wizard_MainWindow(QMainWindow):
    def __init__(self, lace_scl_wizard):
        super().__init__(None)
        self.lace_scl_wizard = lace_scl_wizard
        self._createActions()
        self._createMenuBar()
        self._createStatusLabel()
        
    def _createMenuBar(self):       
        menuBar = QMenuBar(self)
        # Creating menus using a QMenu object
        fileMenu = QMenu("&File", self)
        menuBar.addMenu(fileMenu)
        fileMenu.addAction(self.readScanAction)
        fileMenu.addAction(self.saveScanAction)
        fileMenu.addAction(self.saveAsScanAction)       
        # Creating menus using a title
        editMenu = menuBar.addMenu("&Edit")
        helpMenu = menuBar.addMenu("&Help")     
        self.setMenuBar(menuBar)
        
    def _createActions(self):
        #---- File menu acctions
        self.readScanAction = QAction("&Open...", self)
        self.saveScanAction = QAction("&Save...", self)
        self.saveAsScanAction = QAction("&Save As...", self)
        self.readScanAction.triggered.connect(self.lace_scl_wizard.readWizardData)
        self.saveScanAction.triggered.connect(self.lace_scl_wizard.dumpWizardData)
        self.saveAsScanAction.triggered.connect(self.lace_scl_wizard.dumpWizardDataAs)
        
    def _createStatusLabel(self):
        self.statusbar = self.statusBar()
        self.statusbar.insertPermanentWidget(0,QLabel("Status:"),stretch=0)
        self.status_label = QLabel("LACE SCL Wizard is Ready")
        self.status_label.setStyleSheet("color: red;")
        self.statusbar.insertPermanentWidget(1,self.status_label,stretch=1)
        
    def getStatusLabel(self):
        return self.status_label

if __name__ == '__main__':
    
    lace_scl_wizard = LACE_SCL_Wizard(sys.argv)
    lace_scl_wizard.show()
    print ("LACE SCL Wizard Started!")
    res = lace_scl_wizard.mainQApp.exec()
    #---------------------------------------
    lace_scl_wizard.stopAllThreads()
    print ("LACE SCL Wizard Stopped!")
    sys.exit(res)
