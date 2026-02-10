#------------------------------------------------------
#   Energy meter class to measure energy of the beam
#   using the BPMs phases. The energy of the beam should
#   constant constant for all BPMs involved.
#------------------------------------------------------

from orbit.utils import phaseNearTargetPhaseDeg
from orbit.utils import speed_of_light

class EnergyMeter:
    """ It measures the energy of the beam using BPMs. """
    def __init__(self,lace_scl_wizard):
        self.lace_scl_wizard

    def measureEnergy(cav_wrapper,eKin_guess,n_pulses = 3,sleep_time = 1.1, min_bpm_amp = 1.0):
        """
        It calculates the energy from BPM phases.
        cav_wrapper - we measure energy before this cavity 
        eKin_guess - guess kinetic energy in MeV
        n_pulses -  measurement statistics
        sleep_time - sleep time before measurements
        min_bpm_amp - minimal BPM amplitude signal which we will use
        """
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
        for model_bpm in model_bpms:
            phase = bpm_amp_phase_err_dict[model_bpm.getName()][1][0]
            phase_offset = model_bpm.getEPICS_PhaseOffset()
            phase_corrected = phase - phase_offset
            phaseNearTargetPhaseDeg(phase_corrected,0.)
            print ("bpm=",model_bpm.bpm.getName()," phase, offset, corrected = %+7.1f %+7.1f %+7.1f"%(phase,phase_offset,phase_corrected))
            bpm_phases.append(phase_corrected)
        for bpm_ind in range(1,len(model_bpms)):
            bpm0 = model_bpms[bpm_ind-1]
            bpm1 = model_bpms[bpm_ind]
            pos_diff = bpm1.getPosition() - bpm0.getPosition()
            phase0 = bpm_phases[bpm_ind -1]
            phase1 = bpm_phases[bpm_ind]
            phase_guess = phase0 + coeff_guess*pos_diff
            phase1 = phaseNearTargetPhaseDeg(phase1,phase_guess)
            bpm_phases[bpm_ind] = phase1
        #---- make function for fitting
        phase0 = bpm_phases[0]
        pos_start = model_bpms[0].getPosition()
        pos_end = model_bpms[-1].getPosition()
        print ("debug pos_start = ",pos_start)
        print ("debug pos_end   = ",pos_end)
        pos_center = (pos_end + pos_start)/2
        print ("debug pos_center = ",pos_center)
        phase_pos_func = Function()
        for bpm_ind in range(len(model_bpms)):
            model_bpm = model_bpms[bpm_ind]
            phase = bpm_phases[bpm_ind]
            pos = model_bpm.getPosition()
            phase_guess = phase0 + coeff_guess*(pos - pos_start)
            print ("debug pos=",pos," pos_center=",pos_center)
            pos = pos - pos_center
            phase_pos_func.add(pos,phase)
            print ("bpm=",model_bpm.bpm.getName()," pos = %8.3f "%pos," phase, guess = %+7.1f %+7.1f"%(phase,phase_guess))
        poly_fit = PolynomialFit(1)
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
        return (eKin,eKin_err,phase_pos_func,poly_func)
    
        