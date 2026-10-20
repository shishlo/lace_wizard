"""
The classes for calculating BPMs' phase offsets using SCL scan data.
Phase Offset is property of BPM electronics describing the time delay
of this particular BPM relative to the base BPM which is the origin.
BPMs measure the time of beam arrival relative to the base BPM. 
Each BPM phase offset could be changed by the same value simultaneously, and 
all physical results using these offsets will be the same.
BPMs measure time in degrees, so you can always add or subtract any number
of 360 deg.
You can use two possible ways to get Phase Offsets:
1. Start from the low energy end (start) of SCL (end of CCL4). 
   The energy from CCL4 is an unkown value which we assume 185.6 MeV.
2. Start from the HEBT1 BPMs which were initialized using SNS ring energy.
"""

import sys


from orbit.utils import speed_of_light
from orbit.utils import mass_proton
from orbit.utils import mass_electron

class BPMs_Offsets_from_CCL4_Calculator:
    # It calculates the BPM offsets starting from the CCL4 end   
    def __init__(self,lace_scl_wizard):
        self.lace_scl_wizard = lace_scl_wizard
        
    def calculateOffSets(self, eKin_in = 185.6, bpm_freq = 402.5e+6):
        init_state_cntrl = self.lace_scl_wizard.init_state_cntrl
        bpms_state_cntrl = init_state_cntrl.bpms_state_cntrl
        bpm_wrappers = bpms_state_cntrl.getBPM_Wrappers()
        cav_wrappers = self.lace_scl_wizard.getCavWrappers()
        #---- set text in the main label
        self.lace_scl_wizard.getStatusLabel().setText("")
        #--- transform GeV to MeV
        mass = (mass_proton+2*mass_electron)/1.0e+3         
        c_light = speed_of_light
        gamma = (mass+eKin_in)/mass
        beta = math.sqrt(1.0-1.0/(gamma*gamma))
        #--- initial parameters 
        for bpm_wrapper in bpm_wrappers:
            bpm_wrapper.left_phase_offset.phaseOffset_avg = 0.
            bpm_wrapper.left_phase_offset.phaseOffset_err = 0.
            bpm_wrapper.left_phase_offset.isReady = false
            bpm_wrapper.left_phase_offset.phaseOffset_arr = []
        #---- analysis of the "CCL4 Scan" case
        cav0_wrapper = cav_wrappers[0]
        if(cav0_wrapper.isGood and cav0_wrapper.isMeasured):
            bpm_local_wrappers = []
            for bpm_ind in range(len(cav0_wrapper.bpm_wrappers)):
                bpm_wrapper = cav0_wrapper.bpm_wrappers[bpm_ind]
                if(cav0_wrapper.bpm_wrappers_useInPhaseAnalysis[bpm_ind]):
                    bpm_local_wrappers.append(bpm_wrapper)
                    (graphDataAmp,graphDataPhase) = cav0_wrapper.bpm_amp_phase_dict[bpm_wrapper]
                    (funcAmp,funcPhase) = cav_wrapper.bpm_amp_phase_dict[bpm_wrapper.alias]
                    (x_arr,y_arr,y_err_arr) = funcAmp.getXYErrLists()                 
                    phase_offset_obj = bpm_wrapper.left_phase_offset
                    phase_arr= []
                    for ip in range(graphDataPhase.getNumbOfPoints()):
                        phase_arr.append(graphDataPhase.getY(ip))
                    ????????
                    (phase_avg, err) = calculateAvgErr(phase_arr)
                    phase_offset_obj.phase_val_tmp = phase_avg
                    phase_offset_obj.phase_val_err_tmp = err
            if(len(bpm_local_wrappers) < 3):
                txt = "Cavity "+cav0_wrapper.alias+" all data are bad! Cannot do anything!"
                self.scl_long_tuneup_controller.getMessageTextField().setText(txt)
                return
            #---- the average BPM phases for all cavities off are ready here ------- 
            bpm_phase_coef = 360.0*bpm_freq/(c_light*beta)
            base_bpm_wrapper = bpm_local_wrappers[0]
            base_pos = base_bpm_wrapper.pos
            base_bpm_phase = base_bpm_wrapper.left_phase_offset.phase_val_tmp
            base_bpm_phase_err = base_bpm_wrapper.left_phase_offset.phaseOffset_err
            for bpm_wrapper in bpm_local_wrappers:
                pos_delta = bpm_wrapper.pos - base_pos
                bpm_phase_th = base_bpm_phase + bpm_phase_coef*pos_delta
                phase_offset = makePhaseNear(bpm_wrapper.left_phase_offset.phase_val_tmp - bpm_phase_th,0.)
                err = math.sqrt(base_bpm_phase_err**2 + bpm_wrapper.left_phase_offset.phase_val_err_tmp**2)
                bpm_wrapper.left_phase_offset.phaseOffset_avg = phase_offset
                bpm_wrapper.left_phase_offset.phaseOffset_err = err
                bpm_wrapper.left_phase_offset.isReady = true
                bpm_wrapper.left_phase_offset.phase_val_tmp = 0.
                bpm_wrapper.left_phase_offset.phase_val_err_tmp = 0.
                #print "debug cav=",cav0_wrapper.alias," BPM=",bpm_wrapper.alias," offset= %4.1f +- %4.1f"%(phase_offset,err)
        else:
            txt = "Cavity "+cav0_wrapper.alias+" - data is not ready! Cannot do anything!"
            self.scl_long_tuneup_controller.getMessageTextField().setText(txt)
            return          
        #------ start moving along cavities -------------------
        cav_wrapper = self.scl_long_tuneup_controller.cav_wrappers[0]
        cav_wrapper.eKin_in_guess = eKin_in
        n_cavs = len(self.scl_long_tuneup_controller.cav_wrappers)
        for cav_ind in range(n_cavs):
            cav_wrapper = self.scl_long_tuneup_controller.cav_wrappers[cav_ind]
            if(cav_wrapper.isGood and (not cav_wrapper.isMeasured)): break
            if(cav_ind > 0):
                cav_wrapper.eKin_in_guess = self.scl_long_tuneup_controller.cav_wrappers[cav_ind-1].eKin_out_guess      
            if(not cav_wrapper.isGood):
                cav_wrapper.eKin_out_guess = cav_wrapper.eKin_in_guess
                continue
            # make array of BPMs already having offsets and not having ones
            bpm_wrappers_good_arr = []
            bpm_wrappers_not_done_arr = []
            for bpm_ind in range(len(cav_wrapper.bpm_wrappers)):
                bpm_wrapper = cav_wrapper.bpm_wrappers[bpm_ind]
                is_wanted = bpm_wrapper.isGood and bpm_wrapper.pos > cav_wrapper.pos
                is_wanted = is_wanted and cav_wrapper.bpm_wrappers_useInPhaseAnalysis[bpm_ind]
                if(is_wanted):
                    if(bpm_wrapper.left_phase_offset.isReady):
                        bpm_wrappers_good_arr.append(bpm_wrapper)
                    else:
                        bpm_wrappers_not_done_arr.append(bpm_wrapper)
            initEnergyInGuessHarmFunc(cav_wrapper,self.scl_long_tuneup_controller)
            if(len(bpm_wrappers_good_arr) < 2):
                txt = "Cavity "+cav_wrapper.alias+" does not have enough good BPMs! Cannot do anything!"
                self.scl_long_tuneup_controller.getMessageTextField().setText(txt)
                return              
            self.calculateOffsetsForNotDoneBPMsLeft(cav_wrapper,bpm_wrappers_good_arr,bpm_wrappers_not_done_arr)
            #print "debug cav=",cav_wrapper.alias," n_bad=",len(bpm_wrappers_not_done_arr)
        #----set all BPMs that do not have offsets as not good for phase analysis
        for bpm_wrapper in self.scl_long_tuneup_controller.bpm_wrappers:
            if(bpm_wrapper.isGood):
                if(not bpm_wrapper.left_phase_offset.isReady):
                    cav0_wrapper = self.scl_long_tuneup_controller.cav0_wrapper
                    bpm_ind = cav0_wrapper.bpm_wrappers.index(bpm_wrapper)
                    if(bpm_ind >= 0):
                        cav0_wrapper.bpm_wrappers_useInPhaseAnalysis[bpm_ind] = false
                        cav0_wrapper.bpm_wrappers_useInAmpBPMs[bpm_ind] = true
                    for cav_wrapper in self.scl_long_tuneup_controller.cav_wrappers:
                        bpm_ind = cav_wrapper.bpm_wrappers.index(bpm_wrapper)
                        if(bpm_ind >= 0):
                            cav_wrapper.bpm_wrappers_useInPhaseAnalysis[bpm_ind] = false
                            cav_wrapper.bpm_wrappers_useInAmpBPMs[bpm_ind] = true
        #---- re-calculate phase offesets to the base BPM which is the first BPM after
        #---- the last cavity
        cav_wrapper = self.scl_long_tuneup_controller.cav_wrappers[n_cavs-1]
        base_bpm_wrapper = null
        for bpm_wrapper in self.scl_long_tuneup_controller.bpm_wrappers:
            if(bpm_wrapper.isGood):
                if(bpm_wrapper.left_phase_offset.isReady):
                    if(bpm_wrapper.pos > cav_wrapper.pos):
                        base_bpm_wrapper = bpm_wrapper
                        break
        if(base_bpm_wrapper != null):
            base_bpm_phase_offset = base_bpm_wrapper.left_phase_offset.phaseOffset_avg
            for bpm_wrapper in self.scl_long_tuneup_controller.bpm_wrappers:
                if(bpm_wrapper.isGood):
                    if(bpm_wrapper.left_phase_offset.isReady):
                        phase_offset = bpm_wrapper.left_phase_offset.phaseOffset_avg
                        phase_offset = makePhaseNear(phase_offset - base_bpm_phase_offset,0.)
                        bpm_wrapper.left_phase_offset.phaseOffset_avg = phase_offset 
        #---- set the final energy after the last cavity
        cav_wrapper = self.scl_long_tuneup_controller.cav_wrappers[n_cavs-1]
        bpms_offsets_from_hebt1_panel = scl_long_tuneup_bpm_offsets_controller.bpms_offsets_from_hebt1_panel
        bpms_offsets_from_hebt1_panel.ring_energy_text.setValue(scl_long_tuneup_bpm_offsets_controller.energyScaler.eKin_Hm_to_P(cav_wrapper.eKin_out_guess*1.0e+6)/1.0e+6)
        self.scl_long_tuneup_controller.updateAllTables()
            
    def calculateOffsetsForNotDoneBPMsLeft(self,cav_wrapper,bpm_wrappers_good_arr,bpm_wrappers_not_done_arr):
        scl_long_tuneup_controller = self.scl_long_tuneup_controller
        # this function will calculate offsets for "left" offsets of 
        # "Not yet Done" BPMs by using "good" (already done) BPMs
        eKin_in = cav_wrapper.eKin_in_guess
        mass = scl_long_tuneup_controller.mass/1.0e+6           
        c_light = scl_long_tuneup_controller.c_light    
        bpm_freq = scl_long_tuneup_controller.bpm_freq
        coeff_init = 360.0*bpm_freq/c_light
        for bpm_wrapper in bpm_wrappers_not_done_arr:
            bpm_wrapper.left_phase_offset.phaseOffset_arr = []
        phaseDiffPlot = cav_wrapper.phaseDiffPlot
        cav_wrapper.eKinOutPlot.removeAllPoints()
        cav_wrapper.eKinOutPlotTh.removeAllPoints()
        for ip in range(phaseDiffPlot.getNumbOfPoints()):
            cav_phase = phaseDiffPlot.getX(ip)
            ekin_guess =  cav_wrapper.energy_guess_harm_funcion.getValue(cav_phase)
            beta_guess = math.sqrt(ekin_guess*(ekin_guess+2*mass))/(ekin_guess+mass)
            coeff = coeff_init/beta_guess
            # let's make bpm_phase(z) points for good BPMs
            gd = BasicGraphData()
            base_bpm_wrapper = bpm_wrappers_good_arr[0]
            (graphDataAmp,graphDataPhase) = cav_wrapper.bpm_amp_phase_dict[base_bpm_wrapper]
            base_bpm_offset = base_bpm_wrapper.left_phase_offset.phaseOffset_avg    
            base_bpm_phase = graphDataPhase.getY(ip) - base_bpm_offset
            #print "debug ==== ip=",ip," cav_phase=",cav_phase," eKin_guess=",ekin_guess    
            gd.addPoint(base_bpm_wrapper.pos,base_bpm_phase)
            for bpm_ind in range(1,len(bpm_wrappers_good_arr)):
                bpm_wrapper = bpm_wrappers_good_arr[bpm_ind]
                (graphDataAmp,graphDataPhase) = cav_wrapper.bpm_amp_phase_dict[bpm_wrapper]
                bpm_phase = graphDataPhase.getY(ip) - bpm_wrapper.left_phase_offset.phaseOffset_avg
                bpm_pos = bpm_wrapper.pos
                bpm_phase_guess = gd.getY(bpm_ind-1) + coeff*(bpm_pos-gd.getX(bpm_ind-1))
                bpm_phase = makePhaseNear(bpm_phase,bpm_phase_guess)
                gd.addPoint(bpm_pos,bpm_phase)
                #print "debug bpm=",bpm_wrapper.alias," pos=",bpm_pos," phase=",bpm_phase
            res_arr = GraphDataOperations.polynomialFit(gd,-1.e+36,+1.e+36,1)
            slope = res_arr[0][1]
            slope_err = res_arr[1][1]
            init_phase = res_arr[0][0]
            init_phase_err = res_arr[1][0]
            beta = coeff_init/slope
            gamma = 1./math.sqrt(1.0-beta*beta)
            eKin = mass*(gamma-1.0) 
            delta_eKin = mass*gamma**3*beta**3*slope_err/coeff_init
            cav_wrapper.eKinOutPlot.addPoint(cav_phase,eKin,delta_eKin)
            #print "debug cav_phase=",cav_phase,"eKin_guess=",ekin_guess," eKin=",eKin," delta_E=",delta_eKin
            # let's go over the bad BPMs and calculate offsets for particular cavity phase
            for bpm_wrapper in bpm_wrappers_not_done_arr:
                bpm_pos = bpm_wrapper.pos
                bpm_phase_th = init_phase + slope*bpm_pos
                (graphDataAmp,graphDataPhase) = cav_wrapper.bpm_amp_phase_dict[bpm_wrapper]
                bpm_phase = graphDataPhase.getY(ip)
                bpm_offset = makePhaseNear(bpm_phase - bpm_phase_th,0.)
                bpm_wrapper.left_phase_offset.phaseOffset_arr.append(bpm_offset)
        #----set up the output energy guess
        cav_wrapper.eKin_out_guess = cav_wrapper.eKinOutPlot.getValueY(cav_wrapper.livePhase)
        # let's calculate statistics for "not done" BPMs' offsets
        for bpm_wrapper in bpm_wrappers_not_done_arr:
            phase_arr = bpm_wrapper.left_phase_offset.phaseOffset_arr
            (phase0_avg, phase0_err) = calculateAvgErr(phase_arr)
            phase_arr = []
            for phase in bpm_wrapper.left_phase_offset.phaseOffset_arr:
                phase_arr.append(makePhaseNear(phase-180.,0.))
            (phase1_avg, phase1_err) = calculateAvgErr(phase_arr)
            phase1_avg = makePhaseNear(phase1_avg+180.,0.)
            if(phase1_err < phase0_err):
                bpm_wrapper.left_phase_offset.phaseOffset_avg = phase1_avg
                bpm_wrapper.left_phase_offset.phaseOffset_err = phase1_err
            else:
                bpm_wrapper.left_phase_offset.phaseOffset_avg = phase0_avg
                bpm_wrapper.left_phase_offset.phaseOffset_err = phase0_err
            bpm_wrapper.left_phase_offset.isReady = true
        
class BPMs_Offsets_from_HEBT1_Calculator:
    # It calculates the BPM offsets starting from the HEBT1 end of the SCL  
    def __init__(self,scl_long_tuneup_controller):
        self.scl_long_tuneup_controller = scl_long_tuneup_controller
        
    def calculateOffSets(self):
        scl_long_tuneup_bpm_offsets_controller = self.scl_long_tuneup_controller.scl_long_tuneup_bpm_offsets_controller         
        bpms_offsets_from_hebt1_panel = scl_long_tuneup_bpm_offsets_controller.bpms_offsets_from_hebt1_panel
        self.scl_long_tuneup_controller.getMessageTextField().setText("")
        #--- transform eV to MeV
        mass = self.scl_long_tuneup_controller.mass/1.0e+6          
        c_light = self.scl_long_tuneup_controller.c_light
        #----- eKin_out from ring_energy_text is a proton energy
        eKin_out = bpms_offsets_from_hebt1_panel.ring_energy_text.getValue()
        #----- here we transform it to H- linac energy
        eKin_out = scl_long_tuneup_bpm_offsets_controller.energyScaler.eKin_P_to_Hm(eKin_out*1.0e+6)/1.0e+6
        if(eKin_out == 0.):
            self.scl_long_tuneup_controller.getMessageTextField().setText("The Ring Energy is 0 GeV! Cannot calculate BPM phase offsets!")
            return      
        bpm_freq = self.scl_long_tuneup_controller.bpm_freq 
        n_cavs = len(self.scl_long_tuneup_controller.cav_wrappers)
        cav_wrapper = self.scl_long_tuneup_controller.cav_wrappers[n_cavs-1]
        #--- initial parameters 
        for bpm_wrapper in self.scl_long_tuneup_controller.bpm_wrappers:
            if(bpm_wrapper.pos < cav_wrapper.pos):
                bpm_wrapper.right_phase_offset.phaseOffset_avg = 0.
                bpm_wrapper.right_phase_offset.phaseOffset_err = 0.
                bpm_wrapper.right_phase_offset.isReady = false
                bpm_wrapper.right_phase_offset.phaseOffset_arr = []
        cav_wrapper.eKin_out_guess = eKin_out
        #------ start moving along cavities -------------------
        for cav_ind in range(n_cavs-1,-1,-1):
            cav_wrapper = self.scl_long_tuneup_controller.cav_wrappers[cav_ind]
            if(cav_wrapper.isGood and (not cav_wrapper.isMeasured)): break
            if(cav_ind != n_cavs-1):
                cav_wrapper.eKin_out_guess = self.scl_long_tuneup_controller.cav_wrappers[cav_ind+1].eKin_in_guess
            if(not cav_wrapper.isGood):
                cav_wrapper.eKin_in_guess = cav_wrapper.eKin_out_guess
                continue                
            # make array of BPMs already having offsets and not having ones
            bpm_wrappers_good_arr = []
            bpm_wrappers_not_done_arr = []
            for bpm_ind in range(len(cav_wrapper.bpm_wrappers)):
                bpm_wrapper = cav_wrapper.bpm_wrappers[bpm_ind]
                is_wanted = bpm_wrapper.isGood and bpm_wrapper.pos > cav_wrapper.pos
                is_wanted = is_wanted and cav_wrapper.bpm_wrappers_useInPhaseAnalysis[bpm_ind]
                if(is_wanted):
                    if(bpm_wrapper.right_phase_offset.isReady):
                        bpm_wrappers_good_arr.append(bpm_wrapper)
                    else:
                        bpm_wrappers_not_done_arr.append(bpm_wrapper)
            initEnergyOutGuessHarmFunc(cav_wrapper,self.scl_long_tuneup_controller)
            if(len(bpm_wrappers_good_arr) < 2):
                txt = "Cavity "+cav_wrapper.alias+" does not have enough good BPMs! Cannot do anything!"
                self.scl_long_tuneup_controller.getMessageTextField().setText(txt)
                return              
            calculateOffsetsForNotDoneBPMsRight(cav_wrapper,self.scl_long_tuneup_controller,bpm_wrappers_good_arr,bpm_wrappers_not_done_arr)
            #print "debug cav=",cav_wrapper.alias," n_bad=",len(bpm_wrappers_not_done_arr)," eKin_in=",cav_wrapper.eKin_in_guess," eKin_out=",cav_wrapper.eKin_out_guess
        #---- analysis of the "All Cavities Off" case
        cav_wrapper = self.scl_long_tuneup_controller.cav_wrappers[0]
        cav0_wrapper = self.scl_long_tuneup_controller.cav0_wrapper
        param_arr = [cav_wrapper.eKin_in_guess,]
        cav0_wrapper.energy_guess_harm_funcion.setParamArr(param_arr)
        cav0_wrapper.eKin_in_guess = cav_wrapper.eKin_in_guess
        cav0_wrapper.eKin_out_guess = cav_wrapper.eKin_in_guess
        if(cav0_wrapper.isGood and cav0_wrapper.isMeasured):
            # make array of BPMs already having offsets and not having ones
            bpm_wrappers_good_arr = []
            bpm_wrappers_not_done_arr = []
            for bpm_ind in range(len(cav0_wrapper.bpm_wrappers)):
                bpm_wrapper = cav0_wrapper.bpm_wrappers[bpm_ind]
                is_wanted = bpm_wrapper.isGood
                is_wanted = is_wanted and cav0_wrapper.bpm_wrappers_useInPhaseAnalysis[bpm_ind]
                if(is_wanted):
                    if(bpm_wrapper.right_phase_offset.isReady):
                        bpm_wrappers_good_arr.append(bpm_wrapper)
                    else:
                        bpm_wrappers_not_done_arr.append(bpm_wrapper)
            if(len(bpm_wrappers_good_arr) < 2):
                txt = "Cavity "+cav_wrapper.alias+" does not have enough good BPMs! Cannot do anything!"
                self.scl_long_tuneup_controller.getMessageTextField().setText(txt)
                return
            calculateOffsetsForNotDoneBPMsRight(cav0_wrapper,self.scl_long_tuneup_controller,bpm_wrappers_good_arr,bpm_wrappers_not_done_arr)
            #print "debug cav=",cav0_wrapper.alias," n_bad=",len(bpm_wrappers_not_done_arr)," eKin_in=",cav0_wrapper.eKin_in_guess," eKin_out=",cav0_wrapper.eKin_out_guess
        else:
            txt = "All cavities Off Case does not have the measured data!"
            self.scl_long_tuneup_controller.getMessageTextField().setText(txt)
        #---- set the calculated energy at CCL4 exit
        bpms_offsets_from_hebt1_panel.init_energy_text.setValue(cav0_wrapper.eKin_out_guess)
        #----set all BPMs that do not have offsets as not good for phase analysis
        for bpm_wrapper in self.scl_long_tuneup_controller.bpm_wrappers:
            if(bpm_wrapper.isGood):
                if(not bpm_wrapper.right_phase_offset.isReady):
                    cav0_wrapper = self.scl_long_tuneup_controller.cav0_wrapper
                    bpm_ind = cav0_wrapper.bpm_wrappers.index(bpm_wrapper)
                    if(bpm_ind >= 0):
                        cav0_wrapper.bpm_wrappers_useInPhaseAnalysis[bpm_ind] = false
                        cav0_wrapper.bpm_wrappers_useInAmpBPMs[bpm_ind] = true
                    for cav_wrapper in self.scl_long_tuneup_controller.cav_wrappers:
                        bpm_ind = cav_wrapper.bpm_wrappers.index(bpm_wrapper)
                        if(bpm_ind >= 0):
                            cav_wrapper.bpm_wrappers_useInPhaseAnalysis[bpm_ind] = false
                            cav_wrapper.bpm_wrappers_useInAmpBPMs[bpm_ind] = true
        #---- recalculate phase offesets to the base BPM which is the first BPM after
        #---- the last cavity
        cav_wrapper = self.scl_long_tuneup_controller.cav_wrappers[n_cavs-1]
        base_bpm_wrapper = null
        for bpm_wrapper in self.scl_long_tuneup_controller.bpm_wrappers:
            if(bpm_wrapper.isGood):
                if(bpm_wrapper.right_phase_offset.isReady):
                    if(bpm_wrapper.pos > cav_wrapper.pos):
                        base_bpm_wrapper = bpm_wrapper
                        break
        if(base_bpm_wrapper != null):
            base_bpm_phase_offset = base_bpm_wrapper.right_phase_offset.phaseOffset_avg
            for bpm_wrapper in self.scl_long_tuneup_controller.bpm_wrappers:
                if(bpm_wrapper.isGood):
                    if(bpm_wrapper.right_phase_offset.isReady):
                        phase_offset = bpm_wrapper.right_phase_offset.phaseOffset_avg
                        phase_offset = makePhaseNear(phase_offset - base_bpm_phase_offset,0.)
                        bpm_wrapper.right_phase_offset.phaseOffset_avg = phase_offset 
        self.scl_long_tuneup_controller.updateAllTables()       
