"""
This is a collection of classes for statistics, sin-like function
fitting etc.
"""

import sys
import math
import random
import time

from orbit.core.orbit_utils import Function
from orbit.core.orbit_utils import HarmonicData

from orbit.utils import phaseNearTargetPhase, phaseNearTargetPhaseDeg
from orbit.utils.fitting import PolynomialFit
from orbit.utils import speed_of_light

from orbit.utils.fitting import Solver
from orbit.utils.fitting import Scorer
from orbit.utils.fitting import SolveStopperFactory
from orbit.utils.fitting import ScoreboardActionListener
from orbit.utils.fitting import VariableProxy
from orbit.utils.fitting import TrialPoint

from orbit.utils.fitting import SimplexSearchAlgorithm

def calculateAvgErr(val_arr):
    """
    Calculates average and statistical error of the average value 
    from the array of values.
    Please, pay attention : error = sigma_rms/sqrt(n-1)
    """
    n_vals = len(val_arr)
    if(n_vals == 0): return (0.,0.)
    if(n_vals == 1): return (val_arr[0],0.)
    avg = 0.
    avg2 = 0.
    for val in val_arr:
        avg += val
        avg2 += val*val
    avg /= n_vals
    avg2 /= n_vals
    err = math.sqrt(math.fabs(avg2 - avg*avg)/(n_vals-1))
    return (avg,err)

def getCosineEstimation(func):
    """
    It returns estimation for phase offset and amplitude for A*cos(phase - 180. + offset) + avg_val.
    because BPM phase minimum is a maximal acceleration.
    """
    if(func.getSize() < 10): return (0.,0.,0.)
    y_max = -1.0e+30
    y_max_ind = -1
    y_min = +1.0e+30
    y_min_ind = -1
    avg_val = 0.
    for ind in range(func.getSize()):
        y = func.y(ind)
        avg_val += y 
        if(y < y_min): 
            y_min = y
            y_min_ind = ind
        if(y > y_max):
            y_max = y
            y_max_ind = ind
    #---- estimation
    amp = (y_max - y_min)/2.
    phase_offset =  - phaseNearTargetPhaseDeg(func.x(y_max_ind) - 180.,0.)
    avg_val /= func.getSize()
    return (phase_offset,amp,avg_val)
    
class CosFittingScorer(Scorer):
    """
    The Scorer implementaion for A*cos(phase + offset)
    """
    def __init__(self,func):
        self.func = func
        (phase_offset,amp,avg_val) = getCosineEstimation(self.func)
        self.amp = amp
        self.phase_offset = phase_offset
        self.avg_val = avg_val
        self.amp_relative_step = 0.1
        self.phase_abs_step = 5.0

    def getTrialPoint(self):
        variableProxy_arr = []
        var = VariableProxy("A", self.amp , self.amp_relative_step*self.amp)
        variableProxy_arr.append(var)
        var = VariableProxy("phase_offset", self.phase_offset , self.phase_abs_step)
        variableProxy_arr.append(var)
        var = VariableProxy("avg_val", self.avg_val , self.phase_abs_step)
        variableProxy_arr.append(var)
        trialPoint = TrialPoint()
        for variableProxy in variableProxy_arr:
            trialPoint.addVariableProxy(variableProxy)
        return trialPoint

    def setCosFunction(self,trialPoint,model_func = None):
        param_arr = trialPoint.getVariableProxyValuesArr()
        amp = param_arr[0]
        phase_offset = param_arr[1]
        avg_val = param_arr[2]
        if(model_func != None):
            model_func.clean()
            for phase_ind in range(self.func.getSize()):
                phase = self.func.x(phase_ind)
                fit_value = amp*math.cos((phase - 180. + phase_offset)*math.pi/180.) + avg_val
                model_func.add(phase,fit_value)
        return (amp,phase_offset,avg_val)

    def getScore(self,trialPoint, print_info = False):
        if(self.func.getSize() < 10): return 0.
        param_arr = trialPoint.getVariableProxyValuesArr()
        amp = param_arr[0]
        phase_offset = param_arr[1]
        avg_val = param_arr[2]
        diff2 = 0.
        for phase_ind in range(self.func.getSize()):
            phase = self.func.x(phase_ind)
            func_value = self.func.y(phase_ind)
            fit_value = amp*math.cos((phase - 180. + phase_offset)*math.pi/180.) + avg_val
            diff2 += (func_value - fit_value)**2
            if(print_info):
                print ("debug cav_phase =",phase," (func_value,fit_value)=",(func_value,fit_value)," diff=",(func_value - fit_value))
        diff2 /= self.func.getSize()
        return diff2

def fitCosineFunc(bpm_phase_func,bpm_phase_fit_func = None):
    """
    This method fit cosine function parameters to the BPM phase scan.
    It is fast. The results will be used to guess the cavity parameters for
    the following fitting.
    If (bpm_phase_fit_func != None) the fitted results will be put into this 
    Function.
    """
    #---- Search algorithm from PyORBIT native package
    searchAlgorithm = SimplexSearchAlgorithm()

    max_time = 0.05
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


if __name__ == '__main__':
    
    #==================================================
    #    START of Test SCRIPT
    #==================================================
    
    
    print ("Stop.")
    sys.exit(0)