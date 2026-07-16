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

def normilizeToOneFunction(func):
    """ Returns the Function instance data normalized to 1.0 """
    y_max = abs(func.getMaxY())
    if(y_max == 0.): return
    for ind in range(func.getSize()):
        (y,err) = (func.y(ind)/y_max,func.err(ind)/y_max)
        func.updatePoint(ind,y,err) 

def unWrapPhasesFunction(func):
    """
    This function will un-wrap phases in Function around -180 - +180 deg.
    Phases in func should be in degrees.
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
        
        