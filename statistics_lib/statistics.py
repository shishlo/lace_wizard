"""
This is a collection of classes for statistics
"""

import sys
import math
import random
import time

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