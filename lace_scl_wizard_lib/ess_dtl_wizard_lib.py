#! /usr/bin/env python3

"""
This is a collection of PyORBIt3 classes for ESS DTL Wizard
"""

from PyQt6.QtWidgets import QFrame
from PyQt6.QtWidgets import QTableWidget
from PyQt6.QtWidgets import QTableView
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QWidget
from PyQt6.QtWidgets import QTabWidget
from PyQt6.QtWidgets import QProgressBar
from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtWidgets import QHeaderView
from PyQt6.QtWidgets import QPlainTextEdit

from PyQt6.QtCore import Qt
from PyQt6.QtCore import QRunnable, QObject, QThreadPool, pyqtSlot
from PyQt6.QtCore import QAbstractTableModel

from pyqtgraph import PlotWidget, plot
import pyqtgraph as pg

from functools import partial

import os
import sys
import math
import random
import time

from orbit_utils import Function
from orbit.utils import phaseNearTargetPhaseDeg

from ess_dtl_wizard_auxiliary_lib import FunctionToArr
from ess_dtl_wizard_auxiliary_lib import normilizeToOneFunction
from ess_dtl_wizard_auxiliary_lib import wrapPhasesFunction
from ess_dtl_wizard_auxiliary_lib import wrapPhasesFunction2
from ess_dtl_wizard_auxiliary_lib import dumpFunctionToDA
from ess_dtl_wizard_auxiliary_lib import readFunctionFromDA

from ess_dtl_wizard_data_fit_lib import BPM_Phase_Fitter

class ScanStopper:
	def __init__(self):
		self.setToStop = False
		self.isRunning = False
		
	def getSetToStop(self):
		return self.setToStop
		
	def setSetToStop(self,setToStop):
		self.setToStop = setToStop
		
	def setIsRunning(self,isRunning):
		self.isRunning = isRunning
		
	def getIsRunning(self):
		return self.isRunning

class Worker(QRunnable):
	"""
	Worker thread
	"""
	def __init__(self, dtl_scan_controller):
		super(Worker, self).__init__()
		self.dtl_scan_controller = dtl_scan_controller
		self.scanStopper = self.dtl_scan_controller.scanStopper
		self.max_scan_time = 100.
		self.count = 0

	@pyqtSlot()
	def run(self):
		start_text = self.dtl_scan_controller.start_scan_button.text()
		self.dtl_scan_controller.start_scan_button.setText("Stop Scan")
		phase_scanner = self.dtl_scan_controller.phase_scanner
		start_time = time.time()
		(success_info, want_to_stop_info) = (True, False)
		while(1 < 2):
			self.count += 1
			self.scanStopper.setIsRunning(True)
			if(self.scanStopper.getSetToStop()):
				break
			#print("debug thread running count=",self.count)
			(success_info, want_to_stop_info) = phase_scanner.makeStep()
			if(self.scanStopper.getSetToStop() and want_to_stop_info):
				phase_scanner.restoreInitialPhase()
				break
			if((not success_info) and (not want_to_stop_info)):
				phase_scanner.restoreInitialPhase()
				print("Cannot read fresh BPM data. Probably beam is out. Scan count=",self.count)
				break				
			if((time.time() - start_time) > self.max_scan_time):
				phase_scanner.restoreInitialPhase()
				break
			if(self.scanStopper.getSetToStop()):
				break
			if(success_info and want_to_stop_info):
				phase_scanner.resetScan()
				break
		phase_scanner.restoreInitialPhase()
		self.scanStopper.setSetToStop(True)
		self.scanStopper.setIsRunning(False)
		#print("debug thread stopped")
		self.dtl_scan_controller.start_scan_button.setText(start_text)
		self.dtl_scan_controller.start_scan_button.setChecked(False)

class FitBPM_ScanData_Worker(QRunnable):
	"""
	Worker thread for fitting BPM1 data 
	"""
	def __init__(self, dtl_scan_controller, fittingFuncion):
		super(FitBPM_ScanData_Worker, self).__init__()
		self.dtl_scan_controller = dtl_scan_controller
		self.fittingFuncion = fittingFuncion

	def __del__(self):
		self.dtl_scan_controller.fit_bpm1_button.setEnabled(True)
		self.dtl_scan_controller.fit_bpm1_and_bpm2_button.setEnabled(True)
		#print ("debug FitBPM_ScanData_Worker is done")

	@pyqtSlot()
	def run(self):
		bpm_phase_fitter = self.dtl_scan_controller.bpm_phase_fitter
		self.fittingFuncion()

class PlotScanController:
	def __init__(self, dtl_scan_controller,bpm_index):
		"""
		bpm_index = 0, 1 for BPM1 or BPM2
		"""
		self.dtl_scan_controller = dtl_scan_controller
		self.bpm_index = bpm_index
		self.dtl_index = self.dtl_scan_controller.dtl_index
		self.graphWidget = pg.PlotWidget()
		self.graphWidget.setBackground('w')
		self.graphWidget.setTitle("BPM Phases DTL"+str(self.dtl_index+1), color="b", size="10pt")
		self.constructGraphWidget1()
		
	def constructGraphWidget1(self):
		styles = {'color':'black', 'font-size':'20px'}
		self.graphWidget.setLabel('left', "BPM <font>&phi;</font>, deg", **styles)
		self.graphWidget.setLabel('bottom', "Cavity <font>&phi;</font>, deg", **styles)
		legend = self.graphWidget.addLegend()
		self.graphWidget.showGrid(x=True, y=True)
		
		p1 = self.graphWidget.plotItem
		styles = {'color':'red', 'font-size':'20px'}
		#p1.setLabels(right='BPM Amplitude, arb. units')
		p1.getAxis('right').setLabel('BPM Amplitude, arb. units',**styles)

		## create a new ViewBox, link the right axis to its coordinate system
		p2 = pg.ViewBox()
		p1.showAxis('right')
		p1.scene().addItem(p2)
		p1.getAxis('right').linkToView(p2)
		p2.setXLink(p1)
		#p1.getAxis('right').setLabel('axis2', color='#0000ff')
		
		## Handle view resizing 
		def updateViews():
			## view has resized; update auxiliary views to match
			p2.setGeometry(p1.vb.sceneBoundingRect())
		## need to re-update linked axes since this was called
		## incorrectly while views had different shapes.
		## (probably this should be handled in ViewBox.resizeEvent)
		p2.linkedViewChanged(p1.vb, p2.XAxis)
		
		updateViews()
		p1.vb.sigResized.connect(updateViews)
		
		x_arr = []
		y_arr = []		
		# plot data: x, y values
		#---- Qt.SolidLine, Qt.DashLine, Qt.DotLine, Qt.DashDotLine and Qt.DashDotDotLine
		#pen = pg.mkPen(color=(255, 0, 0), width=1, style=Qt.DashDotLine)
		#pen = pg.mkPen(color="black", width=3, style=Qt.DashDotLine)
		pen = pg.mkPen(color="black", width=3)
		self.bpm_phase_plot = p1.plot(x_arr,y_arr, name = 'BPM Phase', pen = pen, symbol='o', symbolSize=8, symbolBrush=('black'))	

		pen = pg.mkPen(color="black", width=3)#, style=Qt.DashDotLine)
		self.bpm_phase_model_plot = p1.plot(x_arr,y_arr, name = 'BPM Phase Model', pen = pen)

		x_arr = []
		y_arr = []
		pen = pg.mkPen(color="red", width=3)
		self.bpm_amp_plot = pg.PlotCurveItem(x_arr,y_arr, name = 'BPM Amp', pen = pen, symbol='o', symbolSize=8, symbolBrush=('red'))
		p2.addItem(self.bpm_amp_plot)
		
		x_arr = []
		y_arr = []
		pen = pg.mkPen(color="red", width=3)#, style=Qt.DashDotLine)
		self.bpm_amp_model_plot = pg.PlotCurveItem(x_arr,y_arr, name = 'BPM Amp Model', pen = pen)
		p2.addItem(self.bpm_amp_model_plot)	
		
		legend.addItem(self.bpm_amp_plot, self.bpm_amp_plot.name())
		legend.addItem(self.bpm_amp_model_plot, self.bpm_amp_model_plot.name())
		
	def constructGraphWidget(self):
		styles = {'color':'black', 'font-size':'20px'}
		self.graphWidget.setLabel('left', "BPM <font>&phi;</font>, deg", **styles)
		self.graphWidget.setLabel('bottom', "Cavity <font>&phi;</font>, deg", **styles)	
		#self.graphWidget.setLabel('left', "<span style=\"color:red;font-size:20px\">Temperature (°C)</span>")
		#self.graphWidget.setLabel('bottom', "<span style=\"color:red;font-size:20px\">Hour (H)</span>")
		
		self.graphWidget.showGrid(x=True, y=True)
		self.graphWidget.addLegend()		
		
		self.graphWidget.setXRange(-180., 180., padding=0)
		#self.graphWidget.setYRange(30, 40, padding=0)		

		x_arr = [-180.,180]
		y_arr = [0.,0.]
		# plot data: x, y values
		#---- Qt.SolidLine, Qt.DashLine, Qt.DotLine, Qt.DashDotLine and Qt.DashDotDotLine
		#pen = pg.mkPen(color=(255, 0, 0), width=1, style=Qt.DashDotLine)
		pen = pg.mkPen(color="black", width=3, style=Qt.DashDotLine)
		self.bpm_phase_plot = self.graphWidget.plot(x_arr,y_arr, name = 'BPM1 Phase', pen = pen, symbol='o', symbolSize=8, symbolBrush=('black'))
		
		x_arr = [-180.,180]
		y_arr = [0.,0.]		
		pen = pg.mkPen(color="red", width=3, style=Qt.DashDotLine)
		self.bpm_amp_plot = self.graphWidget.plot(x_arr,y_arr, name = 'BPM1 Amp', pen = pen, symbol='o', symbolSize=8, symbolBrush=('red'))

	def updatePlots(self):
		phase_scanner = self.dtl_scan_controller.phase_scanner
		(bpm_phase_epics_func,bpm_amp_epics_func) = phase_scanner.getBPM_EPICS_Funcs(self.bpm_index)
		
		bpm_phase_fitter = self.dtl_scan_controller.bpm_phase_fitter
		(bpm_phase_model_func,bpm_amp_model_func) = bpm_phase_fitter.getBPM_Model_Funcs(self.bpm_index)
		
		(x_arr,y_arr) = FunctionToArr(bpm_phase_epics_func)
		self.bpm_phase_plot.setData(x_arr,y_arr)
		
		(x_arr,y_arr) = FunctionToArr(bpm_phase_model_func)
		self.bpm_phase_model_plot.setData(x_arr,y_arr)		

		(x_arr,y_arr) = FunctionToArr(bpm_amp_epics_func)
		self.bpm_amp_plot.setData(x_arr,y_arr)
		
		(x_arr,y_arr) = FunctionToArr(bpm_amp_model_func)
		self.bpm_amp_model_plot.setData(x_arr,y_arr)		

	def getWidget(self):
		return self.graphWidget
		
class Phase_Scanner:
	"""
	Performs real scan of cavity phase and collecting the BPMs data.
	"""
	def __init__(self,dtl_scan_controller):
		self.dtl_scan_controller = dtl_scan_controller
		self.ess_dtl_wizard =  self.dtl_scan_controller.ess_dtl_wizard
		self.ess_dtl_olm = self.ess_dtl_wizard.ess_dtl_olm
		self.cav_amp_epics_value = 0.
		self.bpm1_phase_epics_func = Function()
		self.bpm2_phase_epics_func = Function()
		self.bpm1_amp_epics_func = Function()
		self.bpm2_amp_epics_func = Function()
		self.initial_cav_phase = 0.
		self.scan_start_value = -180.
		self.scan_stop_value = +180.
		self.scan_step_value = 10.0
		self.scan_time_sleep = 1.1
		self.max_attempts = 30
		#---- scan_index defines were we stopped 
		#---- cav_phase = scan_start_value + scan_index*scan_step_value
		self.scan_index = 0
		
	def resetScan(self):
		self.scan_index = 0
		
	def restoreInitialPhase(self):
		dtl_index = self.dtl_scan_controller.dtl_index
		epics_cavity = self.ess_dtl_olm.getEpicsCavity(dtl_index)
		epics_cavity.setPhase(self.initial_cav_phase)
		
	def clean(self):
		self.cav_amp_epics_value = 0.
		self.bpm1_phase_epics_func.clean()
		self.bpm2_phase_epics_func.clean()
		self.bpm1_amp_epics_func.clean()
		self.bpm2_amp_epics_func.clean()
		
	def getBPM_EPICS_Funcs(self,bpm_index):
		if(bpm_index == 0):
			return (self.bpm1_phase_epics_func,self.bpm1_amp_epics_func)
		return (self.bpm2_phase_epics_func,self.bpm2_amp_epics_func)
		
	def makeStep(self):
		"""
		Returns (success or not, we stop or not)
		Returns (true,false) if step was successful and we want to continue.
		Returns (true,true) if step was successful and we want to stop.
		Returns (false,true) if step was not successful and we want to stop.
		Returns (false,false) if step was not successful and we want to continue.
		"""
		dtl_index = self.dtl_scan_controller.dtl_index
		epics_cavity = self.ess_dtl_olm.getEpicsCavity(dtl_index)
		scanStopper = self.dtl_scan_controller.scanStopper
		#print ("debug makeStep  self.scan_index = ",self.scan_index)
		if(self.scan_index == 0):
			self.clean()
			self.dtl_scan_controller.bpm_phase_fitter.clean()
			self.initial_cav_phase = epics_cavity.getPhase()
			self.dtl_scan_controller.cavity_params_tab.cav_epics_amp = epics_cavity.getAmplitude()
			self.dtl_scan_controller.cavity_params_tab.cav_epics_phase = self.initial_cav_phase
			#print ("debug init cav phase=",self.initial_cav_phase)
		#----------------------------------
		bpm1_phase_old = self.ess_dtl_olm.getModelBPMs(dtl_index)[0].getEPICS_BPM().getPhase()
		#print ("debug old bpm1 phase=",bpm1_phase_old)
		cav_phase = self.scan_start_value + self.scan_index*self.scan_step_value
		bpm1_phase = bpm1_phase_old
		bpm1_amp = 0.
		bpm2_phase = 0.
		bpm2_amp = 0.	
		attempts_count = 0
		time_sleep_between_attempts = self.scan_time_sleep
		while(bpm1_phase == bpm1_phase_old and attempts_count < self.max_attempts):
			if(cav_phase >= self.scan_stop_value):
				return (True,True)
			epics_cavity.setPhase(cav_phase)
			time.sleep(self.scan_time_sleep)
			bpm1_phase = 0.
			bpm1_amp = 0.
			bpm2_phase = 0.
			bpm2_amp = 0.
			bpm1_phase = self.ess_dtl_olm.getModelBPMs(dtl_index)[0].getEPICS_BPM().getPhase()
			#print ("debug new bpm1 phase=",bpm1_phase)
			bpm1_amp = self.ess_dtl_olm.getModelBPMs(dtl_index)[0].getEPICS_BPM().getAmplitude()
			#print ("debug new bpm1 amp=",bpm1_amp)
			bpm2_phase = self.ess_dtl_olm.getModelBPMs(dtl_index)[1].getEPICS_BPM().getPhase()
			#print ("debug new bpm2 phase=",bpm2_phase)
			bpm2_amp = self.ess_dtl_olm.getModelBPMs(dtl_index)[1].getEPICS_BPM().getAmplitude()
			#print ("debug new bpm2 amp=",bpm2_amp)
			#print ("=================== attempts_count=",attempts_count," scanStopper.getSetToStop()=",scanStopper.getSetToStop())
			if(attempts_count > 0):
				print("Cannot read fresh BPM data. Attempts count=",attempts_count," out of ",self.max_attempts)
				time.sleep(time_sleep_between_attempts)
				if(scanStopper.getSetToStop()):
					return (False, False)
			time_sleep_between_attempts += self.scan_time_sleep
			attempts_count += 1
			#print (" debug attempts_count=",attempts_count," val(bpm1_phase == bpm1_phase_old) =",(bpm1_phase == bpm1_phase_old))
			#---- too many attempts
			if(attempts_count >= self.max_attempts):
				return (False, False)
		#---- we got the new point
		self.bpm1_phase_epics_func.add(cav_phase,bpm1_phase)
		self.bpm2_phase_epics_func.add(cav_phase,bpm2_phase)
		self.bpm1_amp_epics_func.add(cav_phase,bpm1_amp)
		self.bpm2_amp_epics_func.add(cav_phase,bpm2_amp)
		self.scan_index += 1
		#---- update plots
		plot_scan_controllers_arr = self.dtl_scan_controller.plot_scan_controllers_arr
		for plot_scan_controller in plot_scan_controllers_arr:		
			plot_scan_controller.updatePlots()
		return (True,False)
		
	def dumpBPM_EPICSFunctions(self, dtl_cntrl_da):
		bpm_epics_data_da = dtl_cntrl_da.createChild("BPM_Scan_EPICS_Functions")
		dumpFunctionToDA(self.bpm1_phase_epics_func,bpm_epics_data_da,"BPM1_EPICS_Phase")
		dumpFunctionToDA(self.bpm1_amp_epics_func,bpm_epics_data_da,"BPM1_EPICS_Amp")
		dumpFunctionToDA(self.bpm2_phase_epics_func,bpm_epics_data_da,"BPM2_EPICS_Phase")
		dumpFunctionToDA(self.bpm2_amp_epics_func,bpm_epics_data_da,"BPM2_EPICS_Amp")
		
	def readBPM_EPICSFunctions(self, dtl_cntrl_da):
		bpm_epics_data_da = dtl_cntrl_da.childAdaptors("BPM_Scan_EPICS_Functions")[0]
		readFunctionFromDA(self.bpm1_phase_epics_func,bpm_epics_data_da,"BPM1_EPICS_Phase")
		readFunctionFromDA(self.bpm1_amp_epics_func,bpm_epics_data_da,"BPM1_EPICS_Amp")
		readFunctionFromDA(self.bpm2_phase_epics_func,bpm_epics_data_da,"BPM2_EPICS_Phase")
		readFunctionFromDA(self.bpm2_amp_epics_func,bpm_epics_data_da,"BPM2_EPICS_Amp")		

class DTL_Tank_Phase_Scan_Controller:
	"""
	It controls the pahse scan one of the DTL tank.
	It keeps reference to main window of the Wizard and its on main pane Widget.
	"""
	def __init__(self,ESS_DTL_Wizard,dtl_index):
		self.ess_dtl_wizard = ESS_DTL_Wizard
		self.dtl_index = dtl_index
		#---- main widget
		self.mainWidget = QFrame(self.ess_dtl_wizard.tabs)
		
		self.start_scan_button = QPushButton("Start Scan")
		self.start_scan_button.setStyleSheet("border: 2px solid blue; background-color : #3cbaa2")
		#---- each second click will uncheck
		self.start_scan_button.setCheckable(True)
		
		self.resume_scan_button = QPushButton("Resume Scan")
		self.resume_scan_button.setStyleSheet("border: 2px solid blue; background-color : #3cbaa2")
		self.resume_scan_button.setCheckable(False)
		
		self.fit_bpm1_button = QPushButton("Fit BPM1 Scan Data")
		self.fit_bpm1_button.setStyleSheet("border: 2px solid black; background-color :  #95BFDD")
		self.fit_bpm1_button.setCheckable(False)
			
		self.fit_bpm1_and_bpm2_button = QPushButton("Fit BPM1 + BPM2 Scan Data")
		self.fit_bpm1_and_bpm2_button.setStyleSheet("border: 2px solid black; background-color : #95BFDD")
		self.fit_bpm1_and_bpm2_button.setCheckable(False)
		
		self.set_cav_phase_button = QPushButton("Set Cavity New Phase to EPICS")
		self.set_cav_phase_button.setStyleSheet("border: 2px solid black; background-color : #E3EFF7")
		self.set_cav_phase_button.setCheckable(False)
		
		self.set_cav_amp_button = QPushButton("Set Cavity New Amp. to EPICS")
		self.set_cav_amp_button.setStyleSheet("border: 2px solid black; background-color : #E3EFF7")
		self.set_cav_amp_button.setCheckable(False)		
		
		layout1 = QHBoxLayout()
		layout1.addWidget(self.start_scan_button)
		layout1.addWidget(self.resume_scan_button)
		
		layout2 = QHBoxLayout()
		layout2.addWidget(self.fit_bpm1_button)
		layout2.addWidget(self.fit_bpm1_and_bpm2_button)
		
		layout3 = QHBoxLayout()
		layout3.addWidget(self.set_cav_phase_button)
		layout3.addWidget(self.set_cav_amp_button)		
		
		layout = QVBoxLayout()
		layout.addLayout(layout1)
		layout.addLayout(layout2)
		layout.addLayout(layout3)
		
		widget = QWidget()
		widget.setLayout(layout)
		
		layout = QVBoxLayout()
		layout.addWidget(widget)
		layout.addStretch()
				
		self.cavity_params_tab = DTL_Cavity_Parameters_Tab(self)
		
		self.fitProgressBar = QProgressBar()
		
		self.phase_scanner = Phase_Scanner(self)
		self.bpm_phase_fitter = BPM_Phase_Fitter(self)		

		self.start_scan_button.clicked.connect(partial(self.startScan,["scan","start"]))
		self.resume_scan_button.clicked.connect(self.resumeScan)
		
		self.fit_bpm1_button.clicked.connect(self.startFitting_BPM1_ScanData)
		self.fit_bpm1_and_bpm2_button.clicked.connect(self.startFitting_BPM1_BPM2_ScanData)
		self.set_cav_amp_button.clicked.connect(self.setNewCavityEPICS_Amp)
		self.set_cav_phase_button.clicked.connect(self.setNewCavityEPICS_Phase)

		bpm_tabs = QTabWidget()
		bpm_tabs.setTabPosition(QTabWidget.TabPosition.North)
		bpm_tabs.setMovable(False)
		
		#---- bpm_index = 0 for BPM1 in the tank and 1 for BPM2
		self.plot_scan_controllers_arr = []
		plot_scan_controller = PlotScanController(self,bpm_index = 0)
		self.plot_scan_controllers_arr.append(plot_scan_controller)
		plot_scan_controller = PlotScanController(self,bpm_index = 1)
		self.plot_scan_controllers_arr.append(plot_scan_controller)
		for bpm_index,plot_scan_controller in enumerate(self.plot_scan_controllers_arr):
			bpm_tabs.addTab(plot_scan_controller.getWidget(),"BPM" + str(bpm_index+1))
			
		bpm_tabs.addTab(self.cavity_params_tab.getWidget(),"Parameters")
		
		#layout.addWidget(self.plot_scan_controller.getWidget())
		layout.addWidget(bpm_tabs)
		
		fit_bpm1_progress_layout = QVBoxLayout()
		fit_bpm1_progress_layout.addWidget(self.fitProgressBar)
		layout.addLayout(fit_bpm1_progress_layout)
		
		self.mainWidget.setLayout(layout)
		
		self.threadpool = QThreadPool()
		#print("Multithreading with maximum %d threads" % self.threadpool.maxThreadCount())
				
		self.scanStopper = ScanStopper()
 
	def getMianWidget(self):
		return self.mainWidget
		
	def dumpScanData(self,parent_da):
		name_da = "DTL"+str(self.dtl_index+1)+"_Controller_Data"
		cntrl_da = parent_da.createChild(name_da)
		self.phase_scanner.dumpBPM_EPICSFunctions(cntrl_da)
		self.bpm_phase_fitter.dumpBPM_ModelFunctions(cntrl_da)
		self.cavity_params_tab.dumpParameters(cntrl_da)
		
	def readScanData(self,parent_da):
		name_da = "DTL"+str(self.dtl_index+1)+"_Controller_Data"
		cntrl_da = parent_da.childAdaptors(name_da)[0]
		self.phase_scanner.readBPM_EPICSFunctions(cntrl_da)
		self.bpm_phase_fitter.readBPM_ModelFunctions(cntrl_da)
		self.cavity_params_tab.readParameters(cntrl_da)
		plot_scan_controllers_arr = self.plot_scan_controllers_arr
		for plot_scan_controller in plot_scan_controllers_arr:		
			plot_scan_controller.updatePlots()

	def startScan(self,arr,checked):
		#print("checked = ",checked," arr=",arr)
		if(checked):
			self.scanStopper.setSetToStop(False)
			self.phase_scanner.resetScan()
			worker = Worker(self)
			self.threadpool.start(worker)
		else:
			self.scanStopper.setSetToStop(True)
			
	def resumeScan(self):
		if(self.scanStopper.getIsRunning()): return
		self.scanStopper.setSetToStop(False)
		self.start_scan_button.setChecked(True)
		worker = Worker(self)
		self.threadpool.start(worker)
		
	def startFitting_BPM1_ScanData(self):
		#---- we are not fitting if the number of points is too small
		(bpm_phase_epics_func,bpm_amp_epics_func) = self.phase_scanner.getBPM_EPICS_Funcs(bpm_index = 0)
		if(bpm_phase_epics_func.getSize() < 10): return
		bpm_phase_fitter = self.bpm_phase_fitter
		worker = FitBPM_ScanData_Worker(self,bpm_phase_fitter.fitModel_BPM1)
		self.fitProgressBar.reset()
		self.threadpool.start(worker)
		self.fit_bpm1_button.setEnabled(False)
		self.fit_bpm1_and_bpm2_button.setEnabled(False)
		
	def startFitting_BPM1_BPM2_ScanData(self):
		#---- we are not fitting if the number of points is too small
		(bpm_phase_epics_func,bpm_amp_epics_func) = self.phase_scanner.getBPM_EPICS_Funcs(bpm_index = 0)
		if(bpm_phase_epics_func.getSize() < 10): return
		bpm_phase_fitter = self.bpm_phase_fitter
		worker = FitBPM_ScanData_Worker(self,bpm_phase_fitter.fitModel_BPM1_BPM2)
		self.fitProgressBar.reset()
		self.threadpool.start(worker)
		self.fit_bpm1_button.setEnabled(False)
		self.fit_bpm1_and_bpm2_button.setEnabled(False)	
		
	def setNewCavityEPICS_Amp(self):
		dtl_index = self.dtl_index
		ess_dtl_olm = self.ess_dtl_wizard.ess_dtl_olm
		epics_cavity = ess_dtl_olm.getEpicsCavity(dtl_index)
		cav_new_epics_amp = self.cavity_params_tab.cav_new_epics_amp
		if(cav_new_epics_amp == 0.):
			return		
		epics_cavity.setAmplitude(cav_new_epics_amp)
		
	def setNewCavityEPICS_Phase(self):
		dtl_index = self.dtl_index
		ess_dtl_olm = self.ess_dtl_wizard.ess_dtl_olm
		epics_cavity = ess_dtl_olm.getEpicsCavity(dtl_index)
		cav_new_epics_phase = self.cavity_params_tab.cav_new_epics_phase
		epics_cavity.setPhase(cav_new_epics_phase)		

	def stopAllThreads(self):
		self.scanStopper.setSetToStop(True)
	
class DTL_Cavity_Parameters_Tab:
	"""
	Parameters of the cavity - phase, amplitude, initial energy etc.
	"""
	def __init__(self,dtl_scan_controller):
		self.dtl_scan_controller = dtl_scan_controller
		#---- widget for parameter table
		self.widget = QMainWindow(self.dtl_scan_controller.getMianWidget())
		
		self.read_epics_button = QPushButton("Read Cavity's EPICS Amplitude and Phase")
		self.read_epics_button.setStyleSheet("border: 2px solid black; background-color :  #95BFDD")
		self.read_epics_button.setCheckable(False)
		
		self.restore_epics_button = QPushButton("Restore Cavity's EPICS Amplitude and Phase")
		self.restore_epics_button.setStyleSheet("border: 2px solid black; background-color :  #95BFDD")
		self.restore_epics_button.setCheckable(False)
		
		layout1 = QHBoxLayout()
		layout1.addWidget(self.read_epics_button)
		layout1.addWidget(self.restore_epics_button)

		self.table = QTableView()
		self.model = ParametersTableModel(self.dtl_scan_controller)
		self.table.setModel(self.model)
		
		header = self.table.horizontalHeader()       
		header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
		header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
				
		layout = QVBoxLayout()
		layout.addLayout(layout1)
		layout.addWidget(self.table)
		
		widget = QWidget()
		widget.setLayout(layout)
		
		self.widget.setCentralWidget(widget)
		
		#---- cavity parameters: amplitude and phase
		self.cav_epics_amp = 0.
		self.cav_epics_phase = 0.
		
		#---- these values will be calculated after the phase scan and analysis 
		self.cav_new_epics_amp = 0.
		self.cav_new_epics_phase = 0.
		
		ess_dtl_olm = self.dtl_scan_controller.ess_dtl_wizard.ess_dtl_olm
		dtl_index = self.dtl_scan_controller.dtl_index		
		
		#---- cavity amplitude relative to the design
		self.cav_amp_model = ess_dtl_olm.getCavityAmp(dtl_index)
		
		self.cav_synch_phase_design = ess_dtl_olm.getCavityPhase(dtl_index)
		self.cav_synch_phase_real = self.cav_synch_phase_design
		
		#---- cavity and BPMs phase offsets
		self.cav_phase_offset = 0.
		self.bpm1_phase_offset = 0.
		self.bpm2_phase_offset = 0.
		
		#---- energies at the entrance and exit of cavity	
		self.eKin_entrance_design = ess_dtl_olm.get_eKin_Entrance(dtl_index)
		self.eKin_entrance_model = self.eKin_entrance_design 
		self.eKin_exit_design = ess_dtl_olm.get_eKin_Exit(dtl_index)
		self.eKin_exit_model = self.eKin_exit_design

		#---- buttons action 
		self.read_epics_button.clicked.connect(self.getCavityAmpAndPhaseFromEPICS)
		self.restore_epics_button.clicked.connect(self.restoreCavityAmpAndPhaseFromEPICS)
		
	def getCavityAmpAndPhaseFromEPICS(self):		
		dtl_index = self.dtl_scan_controller.dtl_index
		ess_dtl_olm = self.dtl_scan_controller.ess_dtl_wizard.ess_dtl_olm
		epics_cavity = ess_dtl_olm.getEpicsCavity(dtl_index)
		self.cav_epics_amp = epics_cavity.getAmplitude()
		self.cav_epics_phase = epics_cavity.getPhase()
		self.model.layoutChanged.emit()	
		
	def restoreCavityAmpAndPhaseFromEPICS(self):
		dtl_index = self.dtl_scan_controller.dtl_index
		ess_dtl_olm = self.dtl_scan_controller.ess_dtl_wizard.ess_dtl_olm
		epics_cavity = ess_dtl_olm.getEpicsCavity(dtl_index)
		if(self.cav_epics_amp == 0.):
			return		
		epics_cavity.setAmplitude(self.cav_epics_amp)
		epics_cavity.setPhase(self.cav_epics_phase)

	def getWidget(self):
		return self.widget
		
	def dumpParameters(self,parent_da):
		params_tab_da = parent_da.createChild("parameters_tab_data")
		#---- EPICS related data
		epics_data = params_tab_da.createChild("epics_data")
		epics_data.setValue("cav_epics_amp","%10.5f"%self.cav_epics_amp)
		epics_data.setValue("cav_epics_phase","%+8.2f"%self.cav_epics_phase)
		epics_data.setValue("cav_new_epics_amp","%10.5f"%self.cav_new_epics_amp)
		epics_data.setValue("cav_new_epics_phase","%+8.2f"%self.cav_new_epics_phase)
		#---- model data 
		model_da = params_tab_da.createChild("model_data")
		model_da.setValue("cav_amp_model","%8.5f"%self.cav_amp_model)
		model_da.setValue("cav_synch_phase_design","%+8.2f"%self.cav_synch_phase_design)
		model_da.setValue("cav_synch_phase_real","%+8.2f"%self.cav_synch_phase_real)
		#---- phase offsets for cavity and BPMs
		phase_offsets_da = params_tab_da.createChild("phase_offsets_data")
		phase_offsets_da.setValue("cav_phase_offset","%+8.2f"%self.cav_phase_offset)
		phase_offsets_da.setValue("bpm1_phase_offset","%+8.2f"%self.bpm1_phase_offset)
		phase_offsets_da.setValue("bpm2_phase_offset","%+8.2f"%self.bpm2_phase_offset)
		#---- energy data at entrance and exit
		energy_da = params_tab_da.createChild("energy_data")
		energy_da.setValue("eKin_entrance_design","%8.3f"%self.eKin_entrance_design)
		energy_da.setValue("eKin_entrance_model","%8.3f"%self.eKin_entrance_model)
		energy_da.setValue("eKin_exit_design","%8.3f"%self.eKin_exit_design)
		energy_da.setValue("eKin_exit_model","%8.3f"%self.eKin_exit_model)
		#---- fitting procedure parameters
		bpm_phase_fitter = self.dtl_scan_controller.bpm_phase_fitter
		fitting_param_da = params_tab_da.createChild("fitting_params_data")
		fitting_param_da.setValue("bpm_cutoff_amp","%6.3f"%bpm_phase_fitter.bpm_amp_cutoff)
		fitting_param_da.setValue("phase_offset_step","%6.3f"%bpm_phase_fitter.phase_offset_step)
		#---- phase scan -180 - +180 parameters
		phase_scanner = self.dtl_scan_controller.phase_scanner
		scan_param_da = params_tab_da.createChild("scan_params_data")
		scan_param_da.setValue("scan_step_value","%6.2f"%phase_scanner.scan_step_value)
		scan_param_da.setValue("scan_time_sleep","%6.2f"%phase_scanner.scan_time_sleep)
		
	def readParameters(self,parent_da):
		if(len(parent_da.childAdaptors("parameters_tab_data")) <= 0): return
		params_tab_da = parent_da.childAdaptors("parameters_tab_data")[0]
		#---- EPICS related data
		epics_data = params_tab_da.childAdaptors("epics_data")[0]
		self.cav_epics_amp = epics_data.doubleValue("cav_epics_amp")
		self.cav_epics_phase = epics_data.doubleValue("cav_epics_phase")
		self.cav_new_epics_amp = epics_data.doubleValue("cav_new_epics_amp")
		self.cav_new_epics_phase = epics_data.doubleValue("cav_new_epics_phase")
		#---- model data
		model_da = params_tab_da.childAdaptors("model_data")[0]
		self.cav_amp_model = model_da.doubleValue("cav_amp_model")
		self.cav_synch_phase_design = model_da.doubleValue("cav_synch_phase_design")
		self.cav_synch_phase_real = model_da.doubleValue("cav_synch_phase_real")
		#---- phase offsets for cavity and BPMs
		phase_offsets_da = params_tab_da.childAdaptors("phase_offsets_data")[0]
		self.cav_phase_offset = phase_offsets_da.doubleValue("cav_phase_offset")
		self.bpm1_phase_offset = phase_offsets_da.doubleValue("bpm1_phase_offset")
		self.bpm2_phase_offset = phase_offsets_da.doubleValue("bpm2_phase_offset")
		#---- energy data at entrance and exit
		energy_da = params_tab_da.childAdaptors("energy_data")[0]
		self.eKin_entrance_design = energy_da.doubleValue("eKin_entrance_design")
		self.eKin_entrance_model = energy_da.doubleValue("eKin_entrance_model")
		self.eKin_exit_design = energy_da.doubleValue("eKin_exit_design")
		self.eKin_exit_model = energy_da.doubleValue("eKin_exit_model")
		#---- fitting procedure parameters
		bpm_phase_fitter = self.dtl_scan_controller.bpm_phase_fitter
		fitting_param_da = params_tab_da.childAdaptors("fitting_params_data")[0]
		bpm_phase_fitter.bpm_amp_cutoff = fitting_param_da.doubleValue("bpm_cutoff_amp")
		bpm_phase_fitter.phase_offset_step = fitting_param_da.doubleValue("phase_offset_step")
		#---- phase scan -180 - +180 parameters
		phase_scanner = self.dtl_scan_controller.phase_scanner
		scan_param_da = params_tab_da.childAdaptors("scan_params_data")[0]
		phase_scanner.scan_step_value = scan_param_da.doubleValue("scan_step_value")
		phase_scanner.scan_time_sleep = scan_param_da.doubleValue("scan_time_sleep")
		
		
class ParametersTableModel(QAbstractTableModel):

	def __init__(self, dtl_scan_controller):
		super(ParametersTableModel, self).__init__()
		self.dtl_scan_controller = dtl_scan_controller
		self.h_header_list = ["Parameter Name", "Value"]
		self.v_header_list = []
		self.param_names_arr = []
		self.param_names_arr.append("Cav. EPICS Ampl. Init. [MV/m]")
		self.param_names_arr.append("Cav. EPICS Phase Init.[deg]")
		self.param_names_arr.append("Cav. EPICS Ampl. New  [MV/m]")
		self.param_names_arr.append("Cav. EPICS Phase New  [deg]")		
		self.param_names_arr.append("======================")
		self.param_names_arr.append("Cav.Ampl. % to Design")
		self.param_names_arr.append("Synch.Phase Design/EPICS [deg]")
		self.param_names_arr.append("Cav. Phase Offset vs. RF [deg]")		
		self.param_names_arr.append("BPM1/BPM2 Phase Offset vs. RF [deg]")	
		self.param_names_arr.append("eKin at Entrance Design/Model [MeV]")		
		self.param_names_arr.append("eKin at Exit Design/Model [MeV]")
		self.param_names_arr.append("Fitting: BPM amp. cutoff param.")
		self.param_names_arr.append("Fitting: initial phase step")
		self.param_names_arr.append("Fitting: maximal iterations")
		self.param_names_arr.append("Phase Scan: phase_step [deg]")
		self.param_names_arr.append("Phase Scan: sleep time [sec]")		
		
	def headerData(self, id, orientation, role):
		if orientation == Qt.Orientation.Horizontal:
			if role == Qt.ItemDataRole.DisplayRole:
				return self.h_header_list[id]
		#if orientation == Qt.Vertical:
		#	if role == Qt.DisplayRole:
		#		return self.v_header_list[id]
		return None
		
	def data(self, index, role):
		cavity_params_tab = self.dtl_scan_controller.cavity_params_tab
		bpm_phase_fitter = self.dtl_scan_controller.bpm_phase_fitter
		phase_scanner = self.dtl_scan_controller.phase_scanner
		row = index.row()
		column = index.column()		
		if role == Qt.ItemDataRole.DisplayRole:
			if(column == 0):
				return self.param_names_arr[row]
			if(row == 0 and column == 1):
				return "%8.5f"%cavity_params_tab.cav_epics_amp
			if(row == 1 and column == 1):
				return "%+8.2f"%cavity_params_tab.cav_epics_phase
			if(row == 2 and column == 1):
				return "%8.5f"%cavity_params_tab.cav_new_epics_amp
			if(row == 3 and column == 1):
				return "%+8.2f"%cavity_params_tab.cav_new_epics_phase	
			if(row == 5 and column == 1):
				return "%6.1f"%(100*cavity_params_tab.cav_amp_model)
			if(row == 6 and column == 1):
				return "%+8.2f / %+8.2f "%(cavity_params_tab.cav_synch_phase_design,cavity_params_tab.cav_synch_phase_real)
			if(row == 7 and column == 1):
				return "%+8.2f"%cavity_params_tab.cav_phase_offset
			if(row == 8 and column == 1):
				return "%+8.2f / %+8.2f"%(cavity_params_tab.bpm1_phase_offset,cavity_params_tab.bpm2_phase_offset)
			if(row == 9 and column == 1):
				return "%8.3f / %8.3f "%(cavity_params_tab.eKin_entrance_design,cavity_params_tab.eKin_entrance_model)			
			if(row == 10 and column == 1):
				return "%8.3f / %8.3f "%(cavity_params_tab.eKin_exit_design,cavity_params_tab.eKin_exit_model)
			if(row == 11 and column == 1):
				return "%6.3f"%bpm_phase_fitter.bpm_amp_cutoff
			if(row == 12 and column == 1):
				return "%6.1f"%bpm_phase_fitter.phase_offset_step
			if(row == 13 and column == 1):
				return "%6d"%bpm_phase_fitter.maxIter
			if(row == 14 and column == 1):
				return "%6.1f"%phase_scanner.scan_step_value
			if(row == 15 and column == 1):
				return "%6.1f"%phase_scanner.scan_time_sleep			
			return ""
			
	def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
		cavity_params_tab = self.dtl_scan_controller.cavity_params_tab	
		phase_scanner = self.dtl_scan_controller.phase_scanner
		row = index.row()
		column = index.column()
		if role == Qt.EditRole:
			if(row == 2 and column == 1):
				cavity_params_tab.cav_new_epics_amp = float(value)
			if(row == 3 and column == 1):
				cavity_params_tab.cav_new_epics_phase = float(value)
			if(row == 11 and column == 1):
				bpm_phase_fitter = self.dtl_scan_controller.bpm_phase_fitter
				bpm_phase_fitter.bpm_amp_cutoff = float(value)
			if(row == 12 and column == 1):
				bpm_phase_fitter = self.dtl_scan_controller.bpm_phase_fitter
				bpm_phase_fitter.phase_offset_step = float(value)
			if(row == 13 and column == 1):
				bpm_phase_fitter = self.dtl_scan_controller.bpm_phase_fitter
				bpm_phase_fitter.maxIter = int(value)
			if(row == 14 and column == 1):
				phase_scanner.scan_step_value = float(value)
			if(row == 15 and column == 1):
				phase_scanner.scan_time_sleep = float(value)
				
			self.dataChanged.emit(index, index)
			return True
		return False
		
	def flags(self, index):
		#return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable
		if( (index.row() == 2 or index.row() == 3) and index.column() == 1):
			#---- cavity amplitude and phase can be set from table
			return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable
		if( (index.row() == 11 or index.row() == 12 or index.row() == 13) and index.column() == 1):
			#---- fitting parameters can be set from table
			return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable
		if( (index.row() == 14 or index.row() == 15) and index.column() == 1):
			#---- fitting parameters can be set from table
			return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable
		return Qt.ItemFlag.NoItemFlags
		
	def get_data(self, index):
		row = index.row()
		column = index.column()
		value = "new_text_"+str(index.row())+"_"+str(index.column())
		#value  = float(self._weight_data[row][column])
		return value		

	def rowCount(self, index):
		# The length of the outer list.
		return len(self.param_names_arr)

	def columnCount(self, index):
		# The following takes the first sub-list, and returns
		# the length (only works if all rows are an equal length)
		return len(self.h_header_list)

class DTL_Wizard_Parameters_Controller:
	"""
	It controls the parameters for the DTL Wizard as a whole.
	It keeps reference to main window of the Wizard and its on main pane Widget.
	"""
	def __init__(self,ESS_DTL_Wizard):
		self.ess_dtl_wizard = ESS_DTL_Wizard
		#---- main widget
		self.mainWidget = QMainWindow(self.ess_dtl_wizard.tabs)
		
		self.show_pvs_button = QPushButton("Show all PV channels")
		self.show_pvs_button.setStyleSheet("border: 2px solid black; background-color :  #95BFDD")
		self.show_pvs_button.setCheckable(False)
		
		#---- button action 
		self.show_pvs_button.clicked.connect(self.showAllPVs)		
		
		layout1 = QHBoxLayout()
		layout1.addWidget(self.show_pvs_button)

		layout = QVBoxLayout()
		layout.addLayout(layout1)

		self.text_area = QPlainTextEdit(self.mainWidget)
		layout.addWidget(self.text_area)
		
		widget = QWidget()
		widget.setLayout(layout)
		
		self.mainWidget.setCentralWidget(widget)	
		
	def showAllPVs(self):
		txt = ""
		for dtl_scan_controller in self.ess_dtl_wizard.scan_controllers_arr:
			dtl_index = dtl_scan_controller.dtl_index
			epics_cavity = self.ess_dtl_wizard.ess_dtl_olm.getEpicsCavity(dtl_index)
			channel_name_dict = epics_cavity.getChannelNamesDict()
			txt += "======== cavity DTL"+str(dtl_index+1) + "\n"
			for handle in channel_name_dict:
				txt += "  cavity handle = %15s "%handle + "  pv_name= %40s"%channel_name_dict[handle] + "\n"
			txt += "     ======= BPMs =========  " + "\n"
			for bpm_ind in range(2):
				epics_bpm = self.ess_dtl_wizard.ess_dtl_olm.getModelBPMs(dtl_index)[bpm_ind].getEPICS_BPM()
				channel_name_dict = epics_bpm.getChannelNamesDict()
				for handle in channel_name_dict:
					txt += "  "+ epics_bpm.getName()  + " handle=%15s "%handle + "  pv_name= %40s"%channel_name_dict[handle] + "\n"		
		self.text_area.insertPlainText(txt)
				
	def getMianWidget(self):
		return self.mainWidget
		
	def stopAllThreads(self):
		pass