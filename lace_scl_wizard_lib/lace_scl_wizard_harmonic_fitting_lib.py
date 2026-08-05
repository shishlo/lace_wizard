"""
This is a collection of classes for fitting sin-like and harmonic function.
"""

import sys
import math
import random
import time

from orbit.core.orbit_utils import Function
from orbit.core.orbit_utils import SplineCH
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

    max_time = 0.03
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

def fitHarmonicData(phase_func,phase_fit_func = None):
    """
    Fits input data with f(x) = a0 + a1*cos((x-180) + x_offset1) + a2*cos(2(x-180) + x_offset2)
    """
    #--------------------------------------
    if(phase_fit_func == None):
        phase_fit_func = Function()
    else:
        phase_fit_func.clean()
    #--------------------------------------
    
    phase_1st_fit_func = Function()
    (amp1,phase_offset1,avg_val1) = fitCosineFunc(phase_func,phase_1st_fit_func,harm_num = 1)
    phase2_func = Function()
    for ind in range(phase_func.getSize()):
        phase2_func.add(phase_func.x(ind),phase_func.y(ind) - phase_1st_fit_func.y(ind))
    phase_2st_fit_func = Function()
    (amp2,phase_offset2,avg_val2) = fitCosineFunc(phase2_func,phase_2st_fit_func,harm_num = 2)
    phase3_func = Function()
    for ind in range(phase_func.getSize()):
        phase3_func.add(phase_func.x(ind),phase2_func.y(ind) - phase_2st_fit_func.y(ind))
        
    harmonic_data = HarmonicData(2,phase_func)
    avg_value = avg_val1+avg_val2
    harmonic_data.parameter(0,avg_value)
    harmonic_data.parameter(1,amp1)
    harmonic_data.parameter(2,phase_offset1-180.)
    harmonic_data.parameter(3,amp2)
    harmonic_data.parameter(4,phase_offset2)        
    """
    #---- debug printing     
    print ("======= fitting quality two harmonics ================")
    print (" phase y0  y1_fit y_delta y_delta_fit err err2")
    for ind in range(phase_func.getSize()):
        x = phase_func.x(ind)
        y = phase_func.y(ind)
        y1_fit = phase_1st_fit_func.y(ind)
        y2 = phase2_func.y(ind)
        y2_fit = phase_2st_fit_func.y(ind)
        err = phase3_func.y(ind)
        y_sum_fit = phase_1st_fit_func.y(ind) + phase_2st_fit_func.y(ind)
        harm_val = harmonic_data.fitValueY(x)
        err2 = y - harm_val
        st = "%+8.2f"%x + " %+10.3f "%y + " %+10.3f "%y1_fit + " %+10.5f "%y2 + " %+10.5f "%y2_fit + " %+10.5f "%err +  " %+10.5f "%err2
        print (st)
    print ("=======================================================")
    """
    
    #---- Initial point initilization 
    variableProxy_arr = []
    name_arr = ["amp0","amp1","pha1","amp2","pha2"]
    for ind, name in enumerate(name_arr):
        val = harmonic_data.parameter(ind)
        val_step = abs(0.01*val)
        if(ind == 2 or ind == 4):
            val_step = 0.5         
        variableProxy_arr.append(VariableProxy(name,val,val_step))

    trialPoint = TrialPoint()
    for variableProxy in variableProxy_arr:
        trialPoint.addVariableProxy(variableProxy)  
    
    #print ("debug =============================")
    #print (trialPoint.textDesciption())
    
    #---- class to provide difference between data and fit function
    class HarmonicScorer(Scorer):
        """
        The implementation of the abstract Score class 
        as harmonic function score
        """
        def __init__(self,harmonic_data):
            self.harmonic_data = harmonic_data
        
        def getScore(self,trialPoint):
            x_arr = trialPoint.getVariableProxyValuesArr()
            for x_ind in range(len(x_arr)):
                self.harmonic_data.parameter(x_ind,x_arr[x_ind])
            return harmonic_data.sumDiff2()
                
    #---- Search algorithm from PyORBIT native package
    searchAlgorithm = SimplexSearchAlgorithm()
    
    #maxIter = 1000
    #solverStopper = SolveStopperFactory.maxIterationStopper(maxIter)
    
    max_time = 0.03
    solverStopper = SolveStopperFactory.maxTimeStopper(max_time)
    
    solver = Solver()
    solver.setAlgorithm(searchAlgorithm)
    solver.setStopper(solverStopper)
    
    scorer =  HarmonicScorer(harmonic_data)
    
    solver.solve(scorer,trialPoint)	
    
    #---- the fitting process ended, now about results
    #print ("==============================================================")
    #print ("??????????????????????????????????????????????????????????????")
    #solver.getScoreboard().printScoreBoard()
    #print ("===== fitting time =",solver.getScoreboard().getRunTime())
    #bestScore = solver.getScoreboard().getBestScore()	
    #print ("best score=",bestScore)

    #----- this will set the trial point for best score to the harmonic_data
    trialPoint = solver.getScoreboard().getBestTrialPoint()
    best_score = scorer.getScore(trialPoint)
    #print (trialPoint.textDesciption())
    #print ("best score=",bestScore," iteration=",solver.getScoreboard().getIteration())
    
    """
    #---- debug printing     
    print ("======= fitting quality ================")
    print (" cav_phase y y-fit  err ")
    for ind in range(phase_func.getSize()):
        x = phase_func.x(ind)
        y = phase_func.y(ind)
        y_fit = harmonic_data.fitValueY(x)
        y_err = y - y_fit
        st = "%+8.2f"%x + " %+10.3f "%y + " %+10.3f "%y_fit + " %+10.5f "%y_err
        print (st)
    """
    
    dummy_func = Function()
    coeff_grad_to_radians = math.pi/180.
    harmonic_deriv_data = HarmonicData(2,dummy_func)
    harmonic_deriv_data.parameter(0,0.)
    harmonic_deriv_data.parameter(1,-coeff_grad_to_radians*harmonic_data.parameter(1))
    harmonic_deriv_data.parameter(2,phaseNearTargetPhaseDeg(harmonic_data.parameter(2) - 90.,0.))
    harmonic_deriv_data.parameter(3,-2*coeff_grad_to_radians*harmonic_data.parameter(3))
    harmonic_deriv_data.parameter(4,phaseNearTargetPhaseDeg(harmonic_data.parameter(4) - 90.,0.))
    
    """
    #---- debug printing 
    print ("======= derivative ================")
    print (" cav_phase derY ")
    for ind in range(phase_func.getSize()):
        x = phase_func.x(ind)
        y_der = harmonic_deriv_data.fitValueY(x)
        st = "%+8.2f"%x + " %+10.3f "%y_der
        print (st)
    """
    
    avg_value = harmonic_data.parameter(0)
    amp1 = harmonic_data.parameter(1)
    
    start_ind = -200
    stop_ind  = 200
    step_ind  = 5
    deriv_0 = harmonic_deriv_data.fitValueY(1.0*(start_ind - step_ind))
    deriv_1 = harmonic_deriv_data.fitValueY(1.0*start_ind)
    phase_min_pos = None
    phase_max_pos = None
    for ind in range(start_ind,stop_ind,step_ind):
        phase0 = 1.0*(ind - step_ind)
        phase1 = 1.0*ind
        deriv_1 = harmonic_deriv_data.fitValueY(phase1)
        if(deriv_1*deriv_0 < 0.):
            if(deriv_0 < 0. and phase_min_pos == None):
                #---- we found min
                phase_min_pos = (phase0 + phase1)/2.
            if(deriv_0 > 0. and phase_max_pos == None):
                #---- we found max
                phase_max_pos = (phase0 + phase1)/2.
        if(deriv_1*deriv_0 == 0.):
            if(deriv_0 == 0. and deriv_1 > 0 and phase_min_pos == None):
                #---- we found min
                phase_min_pos = phase0
            if(deriv_1 == 0. and deriv_0 < 0 and phase_min_pos == None):
                #---- we found min
                phase_min_pos = phase1
            if(deriv_0 == 0. and deriv_1 < 0 and phase_max_pos == None):
                #---- we found max
                phase_max_pos = phase0
            if(deriv_1 == 0. and deriv_0 > 0 and phase_max_pos == None):
                #---- we found max
                phase_max_pos = phase1                
        #----------------
        deriv_0 = deriv_1
        
    if(phase_min_pos == None): phase_min_pos = 0.
    if(phase_max_pos == None): phase_max_pos = 0.

    phase_min_pos = phaseNearTargetPhaseDeg(phase_min_pos,0.)
    phase_max_pos = phaseNearTargetPhaseDeg(phase_max_pos,0.)
    phase_min_pos = findCosLikeMinPhasePos(harmonic_data,harmonic_deriv_data,phase_min_pos)
    phase_max_pos = findCosLikeMaxPhasePos(harmonic_data,harmonic_deriv_data,phase_max_pos)
    phase_min_pos = phaseNearTargetPhaseDeg(phase_min_pos,0.)
    phase_max_pos = phaseNearTargetPhaseDeg(phase_max_pos,0.)
    
    for ind in range(phase_func.getSize()):
        x = phase_func.x(ind)
        y = phase_func.y(ind)
        y_fit = harmonic_data.fitValueY(x)
        phase_fit_func.add(x,y_fit,abs(y-y_fit))
    
    return (amp1,avg_value,phase_min_pos,phase_max_pos,phase_fit_func)

def findCosLikeMinPhasePos(harmonic_data,harmonic_deriv_data,phase_guess):
    phase_min =  phaseNearTargetPhaseDeg(phase_guess,0.)
    count_max = 30
    phase_step = 10.
    delta = 0.01
    phase_0 = phase_min - phase_step
    phase_1 = phase_min + phase_step
    v0 = harmonic_deriv_data.fitValueY(phase_0)
    v1 = harmonic_deriv_data.fitValueY(phase_1)
    if(v1*v0 >= 0.):
        #print ("debug problem with finding the min of the phase-scan. findCosLikeMinPhasePos(...)")
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
    phase_step = 10.
    delta = 0.01
    phase_0 = phase_max - phase_step
    phase_1 = phase_max + phase_step
    v0 = harmonic_deriv_data.fitValueY(phase_0)
    v1 = harmonic_deriv_data.fitValueY(phase_1)
    if(v1*v0 >= 0.):
        #print ("debug problem with finding the max of the phase-scan. findCosLikeMaxPhasePos(...)")
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
            v1 = v
            phase_1 = phase
        else:
            v0 = v
            phase_0 = phase
    return phase            
