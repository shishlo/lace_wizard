"""
This is a collection of auxiliary functions LACE SCL Wizard
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

def FunctionToArr(func):
    """ Returns the Function instance data as two lists x_arr and y_arr """
    (x_arr,y_arr,y_err_arr) = func.getXYErrLists()
    return (x_arr,y_arr,y_err_arr)

def normilizeToOneFunction(func):
    """ Returns the Function instance data normalized to 1.0 """
    y_max = abs(func.getMaxY())
    if(y_max == 0.): return
    for ind in range(func.getSize()):
        (y,err) = (func.y(ind)/y_max,func.err(ind)/y_max)
        func.updatePoint(ind,y,err) 

def unWrapPhasesFunction(func):
    """
    This function will un-wrap phases in Function around -180 - +180 deg 
    """
    if(func.getSize() == 0): return
    y0 = func.y(0)
    for ind in range(1,func.getSize()):
        (y,err) = (func.y(ind),func.err(ind))
        y = phaseNearTargetPhaseDeg(y,y0)
        y0 = y
        func.updatePoint(ind,y,err)

def unWrapPhasesToFunction(func, func_target):
    """
    unWraps phase scan function to get closer to the target fuction.
    Phases in degrees.
    """
    for ind in range(func.getSize()):
        (x,y,err) = (func.x(ind),func.y(ind),func.err(ind))
        y = phaseNearTargetPhaseDeg(y,func_target.getY(x)))
        func.updatePoint(ind,y,err)
        
def EstimateBPM_PhaseOffset(bpm_phase_model_func,bpm_phase_epics_func,bpm_amp_epics_func, bpm_amp_cutoff = 0.5):
    """
    Estimates BPM phase offset model relative to the epics function
    and apples the estimation to the model phase function.
    It is assumed that x_arr is the same for both functions.
    """
    unWrapPhasesToFunction(bpm_phase_model_func,bpm_phase_epics_func)
    normilizeToOneFunction(bpm_amp_epics_func)
    bpm_offset = 0.
    count = 0
    for ind in range(bpm_phase_epics_func.getSize()):
        bpm_amp = bpm_amp_epics_func.y(ind)
        if(bpm_amp > bpm_amp_cutoff):
            bpm_offset += bpm_phase_epics_func.y(ind) - bpm_phase_model_func.y(ind)
            count += 1
    if(count > 0):
        bpm_offset /= count
    #---- applying the estimation
    func = bpm_phase_model_func
    for ind in range(func.getSize()):
        (y,err) = (func.y(ind),func.err(ind))
        y += bpm_offset
        func.updatePoint(ind,y,err)
    return bpm_offset
    
def getCosineEstimation(func):
    """
    It returns estimation for phase offset and amplitude for A*cos(phase - 180. + offset) + avg_val.
    because BPM phase minimum is a maximal acceleration.
    """
    if(func.getSize() < 10): return (0.,0.)
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

def dumpFunctionToDA(func,func_da,name_da,py_x_format = "%12.5g",py_y_format = "%12.5g",use_err = False):
    txt_x_arr = ""
    txt_y_arr = ""
    txt_err_arr = ""
    for i in range(func.getSize()):
        txt_x_arr += " "+py_x_format%func.x(i)
        txt_y_arr += " "+py_y_format%func.y(i)
        txt_err_arr += " "+py_y_format%func.err(i)
    xy_da = func_da.createChild(name_da)
    x_arr_da = xy_da.createChild("x")
    x_arr_da.setValue("arr",txt_x_arr)
    y_arr_da = xy_da.createChild("y")
    y_arr_da.setValue("arr",txt_y_arr)
    if(use_err):
        err_arr_da = xy_da.createChild("err")
        err_arr_da.setValue("err",txt_err_arr)
    
def readFunctionFromDA(func,func_root_da,name_da,use_err = False):
    """ 
    Returns the func with x,y,err data generated from the XML Data Adaptor 
    """
    x_arr = []
    y_arr = []
    err_arr = None
    if(use_err):
       err_arr = [] 
    func.clean()
    func_da_arr = func_root_da.childAdaptors(name_da)
    if(len(func_da_arr) <= 0): return (x_arr,y_arr)
    func_da = func_da_arr[0]
    func_x_da = func_da.childAdaptors("x")[0]
    txt_x_arr = func_x_da.stringValue("arr")
    func_y_da = func_da.childAdaptors("y")[0]
    txt_y_arr = func_y_da.stringValue("arr")
    func_err_da = None
    txt_err_arr = None 
    if(use_err):
        func_err_da = func_da.childAdaptors("err")
        if(func_err_da != None):
            func_err_da =  func_err_da[0]
            txt_err_arr = func_y_da.stringValue("err")
    res_x_arr = txt_x_arr.split()
    res_y_arr = txt_y_arr.split()
    res_err_arr = None
    if(txt_err_arr != None):
        res_err_arr = txt_err_arr.split()
    for i in range(len(res_x_arr)):
        x_arr.append(float(res_x_arr[i]))
        y_arr.append(float(res_y_arr[i]))
        if(res_err_arr != None):
            err_arr.append(float(res_err_arr[i]))
    #---- this addition will eleminate the same x-points
    x_arr_tmp = x_arr[:]
    y_arr_tmp = y_arr[:]
    err_arr_tmp = None
    if(err_arr != None):
       err_arr_tmp = err_arr[:]
    if(len(x_arr_tmp) > 0):
        x_arr = [x_arr_tmp[0],]
        y_arr = [y_arr_tmp[0],]
        if(err_arr != None):
            err_arr = [err_arr_tmp[0],]
    for ix in range(1,len(x_arr_tmp)):
        if(x_arr_tmp[ix] !=  x_arr_tmp[ix-1]):
            x_arr.append(x_arr_tmp[ix])
            y_arr.append(y_arr_tmp[ix])
            if(err_arr != None):
               err_arr.append(err_arr_tmp[ix]) 
    #---------------------------------------------------
    for ind,x in enumerate(x_arr):
        func.add(x,y_arr[ind],err_arr[ind])
    if(err_arr != None):
        return (x_arr,y_arr,err_arr)
    return (x_arr,y_arr)

#------------------------------------------------------
#  SCL Online Model parameter fitting classes
#------------------------------------------------------

class FittingScoreListener(ScoreboardActionListener):
    def __init__(self,scan_controller):
        ScoreboardActionListener.__init__(self)
        self.scan_controller = scan_controller
        self.fitProgressBar = self.scan_controller.fitProgressBar
            
    def performAction(self,solver):
        scoreBoard = solver.getScoreboard()
        iteration = scoreBoard.getIteration()
        trialPoint = scoreBoard.getBestTrialPoint()
        self.scan_controller.fitProgressBar.setValue(iteration)
        
        