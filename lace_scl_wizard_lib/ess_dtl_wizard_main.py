#! /usr/bin/env python3

"""
This is a main ESS DTL Wizard script 
"""

from epics import PV

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget
from PyQt6.QtWidgets import QLabel, QTabWidget, QMenuBar
from PyQt6.QtWidgets import QMenu
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QFileDialog

from PyQt6.QtGui import QPalette, QColor, QIcon
from PyQt6.QtCore import QSize, Qt


from PyQt6.QtWidgets import QPushButton

from functools import partial

import os
import sys
import math
import random
import time

import orbit3

from orbit_utils import Function

# import the XmlDataAdaptor XML parser
from orbit.utils.xml import XmlDataAdaptor

from pyorbit_ess_dtl_online_model_lib import ESS_DTL_OnlineModel, wrapPhasesFunction

#---- Local import
from ess_dtl_wizard_lib import DTL_Tank_Phase_Scan_Controller
from ess_dtl_wizard_lib import DTL_Wizard_Parameters_Controller

class ESS_DTL_Wizard:
	"""
	The main PyQt6 application
	"""
	def __init__(self,argv):
		self.mainPyQt6app = QApplication(argv)
		self.mainWindow = ESS_DTL_Wizard_MainWindow(self)
		self.mainWindow.setWindowTitle("ESS DTL Wizard")
		#---- after setFixedSize you cannot change the size on the screen
		#self.mainWindow.setFixedSize(QSize(800, 400))
		self.statusBar = self.mainWindow.getStatusBar()
		
		self.tabs = QTabWidget()
		self.tabs.setTabPosition(QTabWidget.TabPosition.North)
		self.tabs.setMovable(False)
		
		#---- ESS PyORBIT dtl online model
		self.ess_dtl_olm = ESS_DTL_OnlineModel(nParticles = 1000, peack_current = 0.)
		
		if("PCAS" in argv):
			#---- This method will add "PCAS:" prefix for each PV because:
			#---- 1. to  avoid confusion with real EPICS
			#---- 2. PCAS-py itself support only different names after prefixes
			self.ess_dtl_olm.useWithPCAS()
			self.ess_dtl_olm.connectAllChannnels()
			print ("The ESS DTL OLM connected to PCAS EPICS.")
			time.sleep(1.0)

		if("EPICS" in argv):
			self.ess_dtl_olm.connectAllChannnels()
			print ("The ESS DTL OLM connected to EPICS.")
			time.sleep(1.0)
		
		
		#---- controllers for the Wizard
		self.controllers_arr = []
		self.scan_controllers_arr = []
		
		#---- add to the tabs the main widgets of controllers
		for ind in range(4):
			dtl_scan_controller = DTL_Tank_Phase_Scan_Controller(self,ind)
			self.controllers_arr.append(dtl_scan_controller)
			self.scan_controllers_arr.append(dtl_scan_controller)
			self.tabs.addTab(dtl_scan_controller.getMianWidget(),"DTL" + str(ind+1) +" Scan")
		
		self.params_controller = DTL_Wizard_Parameters_Controller(self)
		self.controllers_arr.append(self.params_controller)
		self.tabs.addTab(self.params_controller.getMianWidget(),"Parameters")
		self.mainWindow.setCentralWidget(self.tabs)	
		#-------------------------------------------------------
		#---- data file of the wizard
		self.data_file_name = None

	def getTabWidget(self,name):
		widget = None
		for ind in range(self.tabs.count()):
			if(self.tabs.tabText(ind) == name):
				return self.tabs.widget(ind)
		return widget

	"""
		button = QPushButton("Start Scan")
		button.setCheckable(True)
		button.clicked.connect(partial(self.the_button_was_clicked,["test","args"]))
		self.mainWindow.setCentralWidget(button)
		
	def the_button_was_clicked(self,arr,checked):
		print("checked = ",checked," arr=",arr)
	"""
		
	def stopAllThreads(self):
		for controller in self.controllers_arr:
			controller.stopAllThreads()

	def show(self):
		menuBar = self.mainWindow.menuBar()
		self.mainWindow.show()
		
	def dumpScanData(self):
		if(self.data_file_name != None):
			root_da = XmlDataAdaptor()
			wizard_da = root_da.createChild("ESS_DTL_Wizard")
			for dtl_scan_controller in self.scan_controllers_arr:
				dtl_scan_controller.dumpScanData(wizard_da)
			root_da.writeToFile(self.data_file_name)
			self.mainWindow.setWindowTitle("ESS DTL Wizard - "+str(self.data_file_name))			
			return
		else:
			self.dumpScanDataAs()
		
	def dumpScanDataAs(self):
		options = QFileDialog.Options()
		options |= QFileDialog.DontUseNativeDialog
		fileName, _ = QFileDialog.getSaveFileName(self.mainWindow,"QFileDialog.getSaveFileName()","","Scan Data Files (*.xml)", options=options)
		if(fileName[-4:] != ".xml"): fileName += ".xml"
		if fileName:
			self.data_file_name = fileName
			self.dumpScanData()
		
	def readScanData(self):
		options = QFileDialog.Options()
		options |= QFileDialog.DontUseNativeDialog	
		fileName, _ = QFileDialog.getOpenFileName(self.mainWindow,"QFileDialog.getOpenFileName()", "","Scan Data Files (*.xml)", options=options)
		if fileName:
			root_da = XmlDataAdaptor.adaptorForFile(fileName)
			wizard_da = root_da.childAdaptors("ESS_DTL_Wizard")[0]
			for dtl_scan_controller in self.scan_controllers_arr:
				dtl_scan_controller.readScanData(wizard_da)
			self.data_file_name = fileName
			self.mainWindow.setWindowTitle("ESS DTL Wizard - "+str(fileName))	

class ESS_DTL_Wizard_MainWindow(QMainWindow):
	def __init__(self, ess_dtl_wizard):
		super().__init__(None)
		self.ess_dtl_wizard = ess_dtl_wizard
		self._createActions()
		self._createMenuBar()
		self._createStatusBar()
		
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
		self.readScanAction = QAction("&Open...", self)
		self.saveScanAction = QAction("&Save...", self)
		self.saveAsScanAction = QAction("&Save As...", self)
		self.readScanAction.triggered.connect(self.ess_dtl_wizard.readScanData)
		self.saveScanAction.triggered.connect(self.ess_dtl_wizard.dumpScanData)
		self.saveAsScanAction.triggered.connect(self.ess_dtl_wizard.dumpScanDataAs)
		
	def _createStatusBar(self):
		self.statusbar = self.statusBar()
		self.statusbar.showMessage("ESS DTL Wizard is Ready")
		#self.statusbar.clearMessage()
		
	def getStatusBar(self):
		return self.statusbar

if __name__ == '__main__':
	
	#ess_dtl_olm = ESS_DTL_OnlineModel(nParticles = 1000, peack_current = 62.5)
	
	ess_dtl_wizard = ESS_DTL_Wizard(sys.argv)
	ess_dtl_wizard.show()

	res = ess_dtl_wizard.mainPyQt6app.exec()
	#---------------------------------------
	ess_dtl_wizard.stopAllThreads()
	print ("ESS DTL Wizard Stopped!")
	sys.exit(res)
