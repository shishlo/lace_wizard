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

def getCosineEstimation(func,harm_num = 1):
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
    phase_offset =  - phaseNearTargetPhaseDeg(harm_num*(func.x(y_max_ind) - 180.),0.)
    avg_val /= func.getSize()
    return (phase_offset,amp,avg_val)
    
class CosFittingScorer(Scorer):
    """
    The Scorer implementaion for A*cos(harm_num*phase + offset)
    harm_num could be 1,2,3 ...
    """
    def __init__(self,func,harm_num = 1):
        self.func = func
        (phase_offset,amp,avg_val) = getCosineEstimation(self.func,harm_num)
        self.amp = amp
        self.phase_offset = phase_offset
        self.avg_val = avg_val
        self.amp_relative_step = 0.1
        self.phase_abs_step = 5.0
        #---- harmonics number 1,2,3
        self.harm_num = harm_num

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
        amp = abs(param_arr[0])
        phase_offset = param_arr[1]
        avg_val = param_arr[2]
        if(model_func != None):
            model_func.clean()
            for phase_ind in range(self.func.getSize()):
                phase = self.func.x(phase_ind)
                fit_value = amp*math.cos((self.harm_num*(phase - 180.) + phase_offset)*math.pi/180.) + avg_val
                model_func.add(phase,fit_value)
        return (amp,phase_offset,avg_val)

    def getScore(self,trialPoint, print_info = False):
        if(self.func.getSize() < 10): return 0.
        param_arr = trialPoint.getVariableProxyValuesArr()
        amp = abs(param_arr[0])
        phase_offset = param_arr[1]
        avg_val = param_arr[2]
        diff2 = 0.
        for phase_ind in range(self.func.getSize()):
            phase = self.func.x(phase_ind)
            func_value = self.func.y(phase_ind)
            fit_value = amp*math.cos((self.harm_num*(phase - 180.) + phase_offset)*math.pi/180.) + avg_val
            diff2 += (func_value - fit_value)**2
            if(print_info):
                print ("debug cav_phase =",phase," (func_value,fit_value)=",(func_value,fit_value)," diff=",(func_value - fit_value))
        diff2 /= self.func.getSize()
        return diff2

def fitCosineFunc(bpm_phase_func,bpm_phase_fit_func = None,harm_num = 1):
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
    
    scorer = CosFittingScorer(bpm_phase_func,harm_num)
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

def fitCosineFuncTwoHarms(phase_func,phase_fit_func = None):
    """
    Fits input data with f(x) = a0 + a1*cos((x-180) + x_offset1) + a2*cos(2(x-180) + x_offset2)
    """
    phase_1st_fit_func = Function()
    (amp1,phase_offset1,avg_val1) = fitCosineFunc(phase_func,phase_1st_fit_func,harm_num = 1)
    phase2_func = Function()
    for ind in range(phase_func.getSize()):
        phase2_func.add(phase_func.x(ind),phase_func.y(ind) - phase_1st_fit_func.y(ind))
    phase_2st_fit_func = Function()
    (amp2,phase_offset2,avg_val2) = fitCosineFunc(phase2_func,phase_2st_fit_func,harm_num = 2)
    if(phase_fit_func == None):
        phase_fit_func = Function()
    phase_fit_func.clean()
    for ind in range(phase_func.getSize()):
        phase_fit_func.add(phase_func.x(ind),phase_1st_fit_func.y(ind) + phase_2st_fit_func.y(ind))
    """
    diff2 = 0.
    for ind in range(phase_func.getSize()):
        diff2 += ( phase_func.y(ind) - phase_fit_func.y(ind))**2
    diff2 /=  phase_func.getSize()
    diff = math.sqrt(diff2)
    print ("debug diff=",diff)
    """
    harmonic_data = HarmonicData(2,phase_func)
    avg_value = avg_val1+avg_val2
    harmonic_data.parameter(0,avg_val1+avg_val2)
    harmonic_data.parameter(1,amp1)
    harmonic_data.parameter(2,phase_offset1 - 180.)
    harmonic_data.parameter(3,amp2)
    harmonic_data.parameter(4,phase_offset2)
    dummy_func = Function()
    harmonic_deriv_data = HarmonicData(2,dummy_func)
    harmonic_deriv_data.parameter(0,0.)
    harmonic_deriv_data.parameter(1,-amp1)
    harmonic_deriv_data.parameter(2,phaseNearTargetPhaseDeg(phase_offset1 - 180. - 90.,0.))
    harmonic_deriv_data.parameter(3,-2*amp2)
    harmonic_deriv_data.parameter(4,phaseNearTargetPhaseDeg(phase_offset2 - 90.,0.))
    phase_min_pos = findCosLikeMinPhasePos(harmonic_data,harmonic_deriv_data,-phase_offset1)
    phase_max_pos = findCosLikeMaxPhasePos(harmonic_data,harmonic_deriv_data,180.-phase_offset1)
    phase_min_pos = phaseNearTargetPhaseDeg(phase_min_pos,0.)
    phase_max_pos = phaseNearTargetPhaseDeg(phase_max_pos,0.)
    return (amp1,avg_value,phase_min_pos,phase_max_pos,phase_fit_func)

def findCosLikeMinPhasePos(harmonic_data,harmonic_deriv_data,phase_guess):
    phase_min =  phaseNearTargetPhaseDeg(phase_guess,0.)
    count_max = 30
    phase_step = 25.
    delta = 0.01
    phase_0 = phase_min - phase_step
    phase_1 = phase_min + phase_step
    v0 = harmonic_deriv_data.fitValueY(phase_0)
    v1 = harmonic_deriv_data.fitValueY(phase_1)
    if(v1*v0 >= 0.):
        print ("debug problem with finding the min of the phase-scan. findCosLikeMinPhasePos(...)")
        phase_step = 0.01
        min_pos = 0.
        min_val = 1.0e+46
        phase = -180.
        while(phase < 180.):
            val = harmonic_data.fitValueY(phase)
            if(min_val > val):
                min_val = val
                min_pos = phase
            phase += phase_step
        return min_pos
    phase = 0.
    count = 0
    while(math.fabs(phase_0 - phase_1) > delta):
        count += 1
        phase = (phase_0 + phase_1)/2
        if(count > count_max):
            return phase        
        v = harmonic_deriv_data.fitValueY(phase)
        if(v == 0.):
            return phase
        if(v1*v < 0.):
            v0 = v
            phase_0 = phase
        else:
            v1 = v
            phase_1 = phase
    return phase            
    
def findCosLikeMaxPhasePos(harmonic_data,harmonic_deriv_data,phase_guess):
    phase_max =  phaseNearTargetPhaseDeg(phase_guess,0.)
    count_max = 30
    phase_step = 25.
    delta = 0.01
    phase_0 = phase_max - phase_step
    phase_1 = phase_max + phase_step
    v0 = harmonic_deriv_data.fitValueY(phase_0)
    v1 = harmonic_deriv_data.fitValueY(phase_1)
    if(v1*v0 >= 0.):
        print ("debug problem with finding the max of the phase-scan. findCosLikeMaxPhasePos(...)")
        phase_step = 0.1
        max_pos = 0.
        max_val = -1.0e+46
        phase = -180.
        while(phase < 180.):
            val = harmonic_data.fitValueY(phase)
            if(max_val < val):
                max_val = val
                max_pos = phase
            phase += phase_step
        return max_pos
    phase = 0.
    count = 0
    while(math.fabs(phase_0-phase_1) > delta):
        count += 1
        phase = (phase_0 + phase_1)/2
        if(count > count_max):
            return phase
        v = harmonic_deriv_data.fitValueY(phase)
        if(v == 0.):
            return phase
        if(v1*v > 0.):
            v0 = v
            phase_0 = phase
        else:
            v1 = v
            phase_1 = phase
    return phase            








if __name__ == '__main__':
    
    #==================================================
    #    START of Test SCRIPT
    #==================================================
    
    
    print ("Stop.")
    sys.exit(0)