#------------------------------------------------------
#   Energy meter class to measure energy of the beam
#   using the BPMs phases. The energy of the beam should
#   constant constant for all BPMs involved.
#------------------------------------------------------

from orbit.utils import phaseNearTargetPhaseDeg
from orbit.utils import speed_of_light

from orbit.core.orbit_utils import Function

from orbit.utils.fitting import PolynomialFit

# import the utilities
from orbit.utils import phaseNearTargetPhase, phaseNearTargetPhaseDeg

from statistics_lib.statistics import calculateAvgErr

class EnergyMeter:
    """ It measures the energy of the beam using BPMs. """
    def __init__(self,lace_scl_wizard):
        self.lace_scl_wizard = lace_scl_wizard

    def measureEnergy(cav_wrapper,eKin_guess,n_pulses = 3,sleep_time = 1.1, min_bpm_amp = 1.0):
        """
        It calculates the energy from BPM phases.
        cav_wrapper - we measure energy before this cavity 
        eKin_guess - guess kinetic energy in MeV
        n_pulses -  measurement statistics
        sleep_time - sleep time before measurements
        min_bpm_amp - minimal BPM amplitude signal which we will use
        """
        scan_stopper = self.lace_scl_wizard.cavs_phase_scan_cntrl.cavs_scan_cntrl
        bpm_amp_phase_err_dict = {}
        eKin = 0.
        eKin_err = 0.
        phase_pos_func = Function()
        poly_fit = PolynomialFit(1)
        bpm_init_wrappers = self.lace_scl_wizard.getBPM_Wrappers()
        pos_min = cav_wrapper.getPosition()
        bpm_wrappers = []
        for bpm_wrapper in bpm_init_wrappers:
            if(bpm_wrapper.isGoog and bpm_wrapper.getPosition() > pos_min and bpm_wrapper.connectPVs()):
                bpm_wrappers.append(bpm_wrapper)
        #-------------------------------------------
        bpm_amp_pvs = [bpm_wrapper.getAmpPV() for bpm_wrapper in bpm_wrappers]
        bpm_phase_pvs = [bpm_wrapper.getPhasePV() for bpm_wrapper in bpm_wrappers]
        if(scan_stopper.getShouldStop()): return (eKin,eKin_err,phase_pos_func,poly_func,bpm_wrappers,bpm_amp_phase_err_dict)
        time.sleep(sleep_time)
        if(scan_stopper.getShouldStop()): return (eKin,eKin_err,phase_pos_func,poly_func,bpm_wrappers,bpm_amp_phase_err_dict)
        res_arr = []
        for ind in range(n_pulses):
            amp_vals = [bpm_amp_pv.get() for bpm_amp_pv in bpm_amp_pvs]
            phase_vals = [bpm_phase_pv.get() for bpm_phase_pv in bpm_phase_pvs]
            res_arr.append([amp_vals,phase_vals])
            if(scan_stopper.getShouldStop()): return (eKin,bpm_wrappers)
            time.sleep(sleep_time)
            if(scan_stopper.getShouldStop()): return (eKin,bpm_wrappers)
        for bpm_ind,bpm_wrapper in enumerate(bpm_wrappers):
            amp_arr = []
            phase_arr = []
            for pulse_ind in range(n_pulses):
                [amp_vals,phase_vals] = res_arr[pulse_ind]
                amp_arr.append(amp_vals[bpm_ind])
                phase_arr.append(phase_vals[bpm_ind])
            (amp_avg,amp_err) = calculateAvgErr(amp_arr)
            (phase_avg,phase_arr) = calculateAvgErr(phase_arr)
            if(amp_avg < min_bpm_amp): continue
            bpm_amp_phase_err_dict[bpm_wrapper.getName()] = ((amp_avg,amp_err),(phase_avg,phase_err))
        #-------------------------------------------
        bpm_wrappers = bpm_amp_phase_err_dict.keys()
        bpm_wrappers.sort(key = lambda tmp: tmp.getPostion())
        # set H- mass
        mass = 938.272089 + 2*0.511     
        c_light = speed_of_light
        #---- BPM frequency in CCL, SCL, HEBT
        bpm_freq = 402.5e+6
        coeff_init = 360.0*bpm_freq/c_light
        bpm_wrappers = []
        bpm_phases = []
        beta_guess = math.sqrt(eKin_guess*(eKin_guess+2*mass))/(eKin_guess+mass)
        #---- coeff from position difference to phase difference
        coeff_guess = coeff_init/beta_guess
        #---- by using pair of BPMs we calculate BPM phases corrected by N*360 deg
        bpm_phases = []
        for bpm_wrapper in bpm_wrappers:
            phase = bpm_amp_phase_err_dict[bpm_wrapper.getName()][1][0]
            phase_offset = bpm_wrapper.getEPICS_PhaseOffset()
            phase_corrected = phase - phase_offset
            phaseNearTargetPhaseDeg(phase_corrected,0.)
            print ("bpm=",bpm_wrapper.bpm.getName()," phase, offset, corrected = %+7.1f %+7.1f %+7.1f"%(phase,phase_offset,phase_corrected))
            bpm_phases.append(phase_corrected)
        for bpm_ind in range(1,len(bpm_wrappers)):
            bpm0 = bpm_wrappers[bpm_ind-1]
            bpm1 = bpm_wrappers[bpm_ind]
            pos_diff = bpm1.getPosition() - bpm0.getPosition()
            phase0 = bpm_phases[bpm_ind -1]
            phase1 = bpm_phases[bpm_ind]
            phase_guess = phase0 + coeff_guess*pos_diff
            phase1 = phaseNearTargetPhaseDeg(phase1,phase_guess)
            bpm_phases[bpm_ind] = phase1
        #---- make function for fitting
        phase0 = bpm_phases[0]
        pos_start = bpm_wrappers[0].getPosition()
        pos_end = bpm_wrappers[-1].getPosition()
        print ("debug pos_start = ",pos_start)
        print ("debug pos_end   = ",pos_end)
        pos_center = (pos_end + pos_start)/2
        print ("debug pos_center = ",pos_center)
        for bpm_ind in range(len(bpm_wrappers)):
            bpm_wrapper = bpm_wrappers[bpm_ind]
            phase = bpm_phases[bpm_ind]
            pos = bpm_wrapper.getPosition()
            phase_guess = phase0 + coeff_guess*(pos - pos_start)
            print ("debug pos=",pos," pos_center=",pos_center)
            pos = pos - pos_center
            phase_pos_func.add(pos,phase)
            print ("bpm=",bpm_wrapper.bpm.getName()," pos = %8.3f "%pos," phase, guess = %+7.1f %+7.1f"%(phase,phase_guess))
        poly_fit.fitFunction(phase_pos_func)
        poly_func = poly_fit.getPolynomial()
        #--- for debug printing only
        for ind in range(phase_pos_func.getSize()):
            pos = phase_pos_func.x(ind)
            phase = phase_pos_func.y(ind)
            fit_phase = poly_func.value(pos)
            #print ("debug pos[m]= %8.3f "%pos," phase= %+8.1f"%phase," fit phase = %+8.1f "%fit_phase," diff=  %+8.1f"%(phase-fit_phase))
        #------------------------------
        #------------------------------
        [coef_arr,err_arr] = poly_fit.getCoefficientsAndErr()
        print ("debug coef_arr=",coef_arr," err=",err_arr)
        coeff = coef_arr[1]
        coeff_err = err_arr[1]
        beta = coeff_init/coeff
        gamma = 1./math.sqrt(1.0 - beta**2)
        eKin = mass*(1./math.sqrt(1.0 - beta**2) - 1.0)
        beta_err = coeff_err*coeff_init/coeff**2
        eKin_err = mass*beta*beta_err*(gamma)**3
        #---- polynomial
        return (eKin,eKin_err,phase_pos_func,poly_func,bpm_wrappers,bpm_amp_phase_err_dict)
    
        