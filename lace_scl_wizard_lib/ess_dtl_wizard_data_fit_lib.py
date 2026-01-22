#! /usr/bin/env python3

"""
There are Scan Data analysis classes. They will analize the cavity phase scan 
data and will extract the cavity amplitude and the phase offset from RF line.
"""

import os
import sys
import math
import random
import time

from orbit_utils import Function
from orbit.utils import phaseNearTargetPhaseDeg


from orbit.utils.fitting import Solver
from orbit.utils.fitting import Scorer
from orbit.utils.fitting import SolveStopperFactory
from orbit.utils.fitting import ScoreboardActionListener
from orbit.utils.fitting import VariableProxy
from orbit.utils.fitting import TrialPoint

from orbit.utils.fitting import SimplexSearchAlgorithm

from ess_dtl_wizard_auxiliary_lib import FunctionToArr
from ess_dtl_wizard_auxiliary_lib import normilizeToOneFunction
from ess_dtl_wizard_auxiliary_lib import wrapPhasesFunction
from ess_dtl_wizard_auxiliary_lib import wrapPhasesFunction2
from ess_dtl_wizard_auxiliary_lib import dumpFunctionToDA
from ess_dtl_wizard_auxiliary_lib import readFunctionFromDA
from ess_dtl_wizard_auxiliary_lib import CosFittingScorer
from ess_dtl_wizard_auxiliary_lib import CavParamScorerForBPM1
from ess_dtl_wizard_auxiliary_lib import CavParamScorerForBPM1_and_BPM2
from ess_dtl_wizard_auxiliary_lib import FittingScoreListener
from ess_dtl_wizard_auxiliary_lib import EstimateBPM_PhaseOffset


class BPM_Phase_Fitter:
	"""
	Performs the fit of the BPMs data for the cavity phase scan.
	"""
	def __init__(self,dtl_scan_controller):
		self.dtl_scan_controller = dtl_scan_controller
		self.ess_dtl_wizard =  self.dtl_scan_controller.ess_dtl_wizard
		self.ess_dtl_olm = self.ess_dtl_wizard.ess_dtl_olm
		self.bpm1_phase_model_func = Function()
		self.bpm2_phase_model_func = Function()
		self.bpm1_amp_model_func = Function()
		self.bpm2_amp_model_func = Function()
		#---- fitting parameters
		self.cav_amp = 1.0
		self.cav_amp_step = 0.01
		self.cav_phase_offset = 0.
		bunch_init = self.ess_dtl_olm.getInitialBunch(self.dtl_scan_controller.dtl_index)
		self.eKIn_in = bunch_init.getSyncParticle().kinEnergy()*1.0e+3
		self.eKIn_in_step = 0.01*self.eKIn_in
		self.bpm1_phase_offset = 0.
		self.bpm2_phase_offset = 0.
		self.phase_offset_step = 2.0
		self.bpm_amp_cutoff  = 0.5 
		#---- weights of BPM's phases for fitting together
		self.weightBPM1 = 0.01
		self.weightBPM2 = 1.0
		self.maxIter = 250
		self.fittingScoreListener = FittingScoreListener(self.dtl_scan_controller)
		
	def clean(self):
		self.bpm1_phase_model_func.clean()
		self.bpm2_phase_model_func.clean()
		self.bpm1_amp_model_func.clean()
		self.bpm2_amp_model_func.clean()
		
	def getBPM_Model_Funcs(self,bpm_index):
		"""
		Here bpm_index is 0 or 1 for BPM1 and BPM2 in the cavity. It is different
		from global bpm_index in Online Model.
		"""
		if(bpm_index == 0):
			return (self.bpm1_phase_model_func,self.bpm1_amp_model_func)
		return (self.bpm2_phase_model_func,self.bpm2_amp_model_func)
		
	def fitModel_BPM1(self):

		plot_scan_controllers_arr = self.dtl_scan_controller.plot_scan_controllers_arr
		
		#---- memorize initial amplitude and phase of the cavity in OLM
		cav_amp_init = self.ess_dtl_olm.getCavityAmp(self.dtl_scan_controller.dtl_index)
		cav_phase_init = self.ess_dtl_olm.getCavityPhase(self.dtl_scan_controller.dtl_index)
		
		(trialPoint,cavParamScorerBPM1) = self.preliminaryTrialPointFromBPM1()
		
		plot_scan_controllers_arr = self.dtl_scan_controller.plot_scan_controllers_arr
		
		#-------------------------------------------
		#---- Simplex fitting one BPM data
		#-------------------------------------------
		
		#---- Search algorithm from PyORBIT native package
		searchAlgorithm = SimplexSearchAlgorithm()

		#max_time = 5.0
		#solverStopper = SolveStopperFactory.maxTimeStopper(max_time)
		
		maxIter = self.maxIter
		solverStopper = SolveStopperFactory.maxIterationStopper(maxIter)
		
		self.dtl_scan_controller.fitProgressBar.setRange(0,maxIter)
		
		solver = Solver()
		solver.setAlgorithm(searchAlgorithm)
		solver.setStopper(solverStopper)
		
		#---- if we want to see the progress of fitting 
		scorer = cavParamScorerBPM1
		solver.getScoreboard().addBestScoreListener(self.fittingScoreListener)
		solver.solve(scorer,trialPoint)	
		trialPoint = solver.getScoreboard().getBestTrialPoint()
		
		cavParamScorerBPM1.getBPM_Model_PhaseFunc(trialPoint,self.bpm1_phase_model_func,self.bpm1_amp_model_func,\
			self.bpm2_phase_model_func,self.bpm2_amp_model_func)
		wrapPhasesFunction(self.bpm1_phase_model_func)
		
		#---- now we can estimate the BPM2 phase offset using bpm2_amp_epics_func, bpm2_phase_epics_func, and 
		#---- self.bpm2_phase_model_func
		phase_scanner = self.dtl_scan_controller.phase_scanner
		(bpm2_phase_epics_func,bpm2_amp_epics_func) = phase_scanner.getBPM_EPICS_Funcs(bpm_index = 1)
		self.bpm2_phase_offset = EstimateBPM_PhaseOffset(self.bpm2_phase_model_func,bpm2_phase_epics_func,bpm2_amp_epics_func,self.bpm_amp_cutoff)		
		
		#---- remember the best parameters
		param_arr = trialPoint.getVariableProxyValuesArr()
		self.cav_amp = param_arr[0]
		self.cav_phase_offset = param_arr[1]
		self.bpm1_phase_offset = param_arr[2]
		
		cavity_params_tab = self.dtl_scan_controller.cavity_params_tab
		cav_synch_phase = cavity_params_tab.cav_epics_phase + self.cav_phase_offset
		(eKin_entrance, eKin_exit) = cavParamScorerBPM1.getEntranceAndExitEnergy(trialPoint,cav_synch_phase)
		cavity_params_tab.cav_new_epics_amp = cavity_params_tab.cav_epics_amp/self.cav_amp
		cavity_params_tab.cav_new_epics_phase = cavity_params_tab.cav_synch_phase_design - self.cav_phase_offset
		cavity_params_tab.cav_amp_model = self.cav_amp
		cavity_params_tab.cav_synch_phase_real = cav_synch_phase
		cavity_params_tab.cav_phase_offset = self.cav_phase_offset
		cavity_params_tab.bpm1_phase_offset = self.bpm1_phase_offset
		cavity_params_tab.bpm2_phase_offset = self.bpm2_phase_offset
		cavity_params_tab.eKin_entrance_model = eKin_entrance
		cavity_params_tab.eKin_exit_model = eKin_exit

		#---- Let's replot phase scan functions
		for plot_scan_controller in plot_scan_controllers_arr:
			plot_scan_controller.updatePlots()
			time.sleep(0.5)

		#---- restoration of the initial OLM parameters
		self.ess_dtl_olm.setCavityAmp(self.dtl_scan_controller.dtl_index,cav_amp_init)
		self.ess_dtl_olm.setCavityPhase(self.dtl_scan_controller.dtl_index,cav_phase_init)
		
		self.dtl_scan_controller.fitProgressBar.reset()
		
	def preliminaryTrialPointFromBPM1(self):
		"""
		This is fast estimation of the preliminary parameters of cavity's amplitude and phase 
		"""
		
		phase_scanner = self.dtl_scan_controller.phase_scanner
		(bpm_phase_epics_func,bpm_amp_epics_func) = phase_scanner.getBPM_EPICS_Funcs(bpm_index = 0)
		wrapPhasesFunction(bpm_phase_epics_func)
		normilizeToOneFunction(bpm_amp_epics_func)		
		
		#---- phase amplitude and phase offsets for 1st bpm phase scan - fast cosine fitting 
		(bpm1_phase_amp,cav_phase_offset,bpm1_phase_offset) = self.fitCosineFunc(bpm_phase_epics_func,self.bpm1_phase_model_func)
		
		"""
		#---- Let's replot phase scan functions
		plot_scan_controllers_arr = self.dtl_scan_controller.plot_scan_controllers_arr
		for plot_scan_controller in plot_scan_controllers_arr:
			plot_scan_controller.updatePlots()
			time.sleep(0.5)
		"""
		
		#---- Now we want to get cosine function from the model to compare amplitudes
		#---- of the cosine functions from EPICS and model and fix the model amplitude
		#---- to get initial value of the cavity amplitude for the model-based fitting
		cav_amp_init = self.ess_dtl_olm.getCavityAmp(self.dtl_scan_controller.dtl_index)
		cav_phase_init = self.ess_dtl_olm.getCavityPhase(self.dtl_scan_controller.dtl_index)
		cavParamScorerBPM1 = CavParamScorerForBPM1(self.ess_dtl_olm,bpm_phase_epics_func,self.dtl_scan_controller.dtl_index)
		
		trialPoint = TrialPoint()
		variableProxy = VariableProxy("cav_amp",cav_amp_init,self.cav_amp_step*cav_amp_init)
		trialPoint.addVariableProxy(variableProxy)
		variableProxy = VariableProxy("cav_phase_offset",cav_phase_offset,self.phase_offset_step)
		trialPoint.addVariableProxy(variableProxy)
		variableProxy = VariableProxy("bpm_phase_offset",0.,self.phase_offset_step)
		trialPoint.addVariableProxy(variableProxy)		
		
		cavParamScorerBPM1.getBPM_Model_PhaseFunc(trialPoint,self.bpm1_phase_model_func,self.bpm1_amp_model_func,\
			self.bpm2_phase_model_func,self.bpm2_amp_model_func)
		wrapPhasesFunction(self.bpm1_phase_model_func)
		
		(bpm1_phase_model_amp,cav_phase_model_offset,bpm1_phase_model_offset) = self.fitCosineFunc(self.bpm1_phase_model_func)
		
		#---- Now we translate cosine fitting parameters to the OLM model parameters
		#---- The model amplitude is fixed now
		cav_amp = cav_amp_init*bpm1_phase_amp/bpm1_phase_model_amp
		cav_phase_offset = cav_phase_model_offset
		bpm1_phase_offset = bpm1_phase_offset - bpm1_phase_model_offset
		
		trialPoint = TrialPoint()
		variableProxy = VariableProxy("cav_amp",cav_amp,self.cav_amp_step*cav_amp_init)
		trialPoint.addVariableProxy(variableProxy)
		variableProxy = VariableProxy("cav_phase_offset",cav_phase_offset,self.phase_offset_step)
		trialPoint.addVariableProxy(variableProxy)
		variableProxy = VariableProxy("bpm_phase_offset",bpm1_phase_offset,self.phase_offset_step)
		trialPoint.addVariableProxy(variableProxy)
		
		#print ("debug preliminaryTrialPointFromBPM1 end trialPoint = \n",trialPoint.textDesciption())
		
		#---- this call puts the model BPM phase and amplitude into the model function 
		cavParamScorerBPM1.getBPM_Model_PhaseFunc(trialPoint,self.bpm1_phase_model_func,self.bpm1_amp_model_func,\
			self.bpm2_phase_model_func,self.bpm2_amp_model_func)
		
		#---- now we can estimate the BPM2 phase offset using bpm2_amp_epics_func, bpm2_phase_epics_func, and 
		#---- self.bpm2_phase_model_func
		(bpm2_phase_epics_func,bpm2_amp_epics_func) = phase_scanner.getBPM_EPICS_Funcs(bpm_index = 1)
		self.bpm2_phase_offset = EstimateBPM_PhaseOffset(self.bpm2_phase_model_func,bpm2_phase_epics_func,bpm2_amp_epics_func,self.bpm_amp_cutoff)
				
		self.ess_dtl_olm.setCavityAmp(self.dtl_scan_controller.dtl_index,cav_amp_init)
		self.ess_dtl_olm.setCavityPhase(self.dtl_scan_controller.dtl_index,cav_phase_init)
		return (trialPoint,cavParamScorerBPM1)

	def fitModel_BPM1_BPM2(self):

		plot_scan_controllers_arr = self.dtl_scan_controller.plot_scan_controllers_arr
		
		#---- memorize initial amplitude and phase of the cavity in OLM
		cav_amp_init = self.ess_dtl_olm.getCavityAmp(self.dtl_scan_controller.dtl_index)
		cav_phase_init = self.ess_dtl_olm.getCavityPhase(self.dtl_scan_controller.dtl_index)
		#---- initial energy
		bunch_init = self.ess_dtl_olm.getInitialBunch(self.dtl_scan_controller.dtl_index)
		eKin_init = bunch_init.getSyncParticle().kinEnergy()*1.0e+3
		
		self.eKIn_in = eKin_init
		
		trialPoint  = self.preliminaryTrialPointFromBPM1()[0]
		
		#---- add additional variables for fitting for the case BPM1 and BPM2 together
		variableProxy = VariableProxy("bpm2_phase_offset",self.bpm2_phase_offset,self.phase_offset_step)
		trialPoint.addVariableProxy(variableProxy)
		variableProxy = VariableProxy("eKinIn",self.eKIn_in,self.eKIn_in_step)
		trialPoint.addVariableProxy(variableProxy)
		
		#print ("debug initial trialPoint = \n",trialPoint.textDesciption())
		
		plot_scan_controllers_arr = self.dtl_scan_controller.plot_scan_controllers_arr
		
		cavParamScorer_BPM1_BPM2 =  CavParamScorerForBPM1_and_BPM2(self.dtl_scan_controller,self.bpm_amp_cutoff)
		cavParamScorer_BPM1_BPM2.setFittingWeightBPMs(self.weightBPM1,self.weightBPM2)
		
		#-------------------------------------------
		#---- Simplex fitting two BPM data
		#-------------------------------------------
		
		#---- Search algorithm from PyORBIT native package
		searchAlgorithm = SimplexSearchAlgorithm()

		#max_time = 5.0
		#solverStopper = SolveStopperFactory.maxTimeStopper(max_time)
		
		maxIter = self.maxIter
		solverStopper = SolveStopperFactory.maxIterationStopper(maxIter)
		
		self.dtl_scan_controller.fitProgressBar.setRange(0,maxIter)
		
		solver = Solver()
		solver.setAlgorithm(searchAlgorithm)
		solver.setStopper(solverStopper)
		
		#---- if we want to see the progress of fitting 
		scorer = cavParamScorer_BPM1_BPM2
		solver.getScoreboard().addBestScoreListener(self.fittingScoreListener)
		solver.solve(scorer,trialPoint)	
		trialPoint = solver.getScoreboard().getBestTrialPoint()
		
		cavParamScorer_BPM1_BPM2.getBPM_Model_PhaseFunc(trialPoint,self.bpm1_phase_model_func,self.bpm1_amp_model_func,\
			self.bpm2_phase_model_func,self.bpm2_amp_model_func)
		wrapPhasesFunction(self.bpm1_phase_model_func)
		
		#---- now we can estimate the BPM2 phase offset using bpm2_amp_epics_func, bpm2_phase_epics_func, and 
		#---- self.bpm2_phase_model_func
		phase_scanner = self.dtl_scan_controller.phase_scanner
		(bpm1_phase_epics_func,bpm1_amp_epics_func) = phase_scanner.getBPM_EPICS_Funcs(bpm_index = 0)
		self.bpm1_phase_offset = EstimateBPM_PhaseOffset(self.bpm1_phase_model_func,bpm1_phase_epics_func,bpm1_amp_epics_func,bpm_amp_cutoff = 0.)		
		
		#---- remember the best parameters
		param_arr = trialPoint.getVariableProxyValuesArr()
		self.cav_amp = param_arr[0]
		self.cav_phase_offset = param_arr[1]
		self.bpm1_phase_offset = param_arr[2]
		self.bpm2_phase_offset = param_arr[3]
		self.eKIn_in = param_arr[4]
		
		#print ("debug fitting final trialPoint = \n",trialPoint.textDesciption())
		
		cavity_params_tab = self.dtl_scan_controller.cavity_params_tab
		cav_synch_phase = cavity_params_tab.cav_epics_phase + self.cav_phase_offset
		(eKin_entrance, eKin_exit) = cavParamScorer_BPM1_BPM2.getEntranceAndExitEnergy(trialPoint,cav_synch_phase)
		cavity_params_tab.cav_new_epics_amp = cavity_params_tab.cav_epics_amp/self.cav_amp
		cavity_params_tab.cav_new_epics_phase = cavity_params_tab.cav_synch_phase_design - self.cav_phase_offset
		cavity_params_tab.cav_amp_model = self.cav_amp
		cavity_params_tab.cav_synch_phase_real = cav_synch_phase
		cavity_params_tab.cav_phase_offset = self.cav_phase_offset
		cavity_params_tab.bpm1_phase_offset = self.bpm1_phase_offset
		cavity_params_tab.bpm2_phase_offset = self.bpm2_phase_offset
		cavity_params_tab.eKin_entrance_model = eKin_entrance
		cavity_params_tab.eKin_exit_model = eKin_exit
		
		#---- Let's replot phase scan functions
		for plot_scan_controller in plot_scan_controllers_arr:
			plot_scan_controller.updatePlots()
			time.sleep(0.5)

		#---- restoration of the initial OLM parameters
		self.ess_dtl_olm.setCavityAmp(self.dtl_scan_controller.dtl_index,cav_amp_init)
		self.ess_dtl_olm.setCavityPhase(self.dtl_scan_controller.dtl_index,cav_phase_init)
		
		#---- restore the initial energy at the entrance
		bunch_init.getSyncParticle().kinEnergy(eKin_init/1.0e+3)
		
		self.dtl_scan_controller.fitProgressBar.reset()

	def fitCosineFunc(self,bpm_phase_func,bpm_phase_fit_func = None):
		"""
		This method fit cosine function parameters to the BPM phase scan.
		It is fast. The results will be used to guess the cavity parameters for
		the following fitting.
		"""
		#---- Search algorithm from PyORBIT native package
		searchAlgorithm = SimplexSearchAlgorithm()

		max_time = 0.03
		solverStopper = SolveStopperFactory.maxTimeStopper(max_time)
	
		solver = Solver()
		solver.setAlgorithm(searchAlgorithm)
		solver.setStopper(solverStopper)
		
		scorer = CosFittingScorer(bpm_phase_func)
		trialPoint = scorer.getTrialPoint()
	
		class BestScoreListener(ScoreboardActionListener):
			def __init__(self):
				ScoreboardActionListener.__init__(self)
				
			def performAction(self,solver):
				scoreBoard = solver.getScoreboard()
				iteration = scoreBoard.getIteration()
				trialPoint = scoreBoard.getBestTrialPoint()
				print ("============= iter=",scoreBoard.getIteration()," best score=",scoreBoard.getBestScore())
				print (trialPoint.textDesciption())
		
		#---- if we want to see the progress of fitting 
		#solver.getScoreboard().addBestScoreListener(BestScoreListener())
		solver.solve(scorer,trialPoint)	
	
		#---- the fitting process ended, now we see results
		#print ("===== best score ========== fitting time =",solver.getScoreboard().getRunTime())
		#bestScore = solver.getScoreboard().getBestScore()	
		#print ("best score=",bestScore," iteration=",solver.getScoreboard().getIteration())
		trialPoint = solver.getScoreboard().getBestTrialPoint()
		#print (trialPoint.textDesciption())
		
		#---- Let's put fitting results into bpm_phase_fit_func
		(amp,phase_offset,avg_val) = scorer.setCosFunction(trialPoint,bpm_phase_fit_func)
		return (amp,phase_offset,avg_val)

	def dumpBPM_ModelFunctions(self, dtl_cntrl_da):
		bpm_model_data = dtl_cntrl_da.createChild("BPM_Model_Functions")
		dumpFunctionToDA(self.bpm1_phase_model_func,bpm_model_data,"BPM1_Model_Phase")
		dumpFunctionToDA(self.bpm1_amp_model_func,bpm_model_data,"BPM1_Model_Amp")
		dumpFunctionToDA(self.bpm2_phase_model_func,bpm_model_data,"BPM2_Model_Phase")
		dumpFunctionToDA(self.bpm2_amp_model_func,bpm_model_data,"BPM2_Model_Amp")
		
	def readBPM_ModelFunctions(self, dtl_cntrl_da):
		bpm_model_data = dtl_cntrl_da.childAdaptors("BPM_Model_Functions")[0]
		readFunctionFromDA(self.bpm1_phase_model_func,bpm_model_data,"BPM1_Model_Phase")
		readFunctionFromDA(self.bpm1_amp_model_func,bpm_model_data,"BPM1_Model_Amp")
		readFunctionFromDA(self.bpm2_phase_model_func,bpm_model_data,"BPM2_Model_Phase")
		readFunctionFromDA(self.bpm2_amp_model_func,bpm_model_data,"BPM2_Model_Amp")

