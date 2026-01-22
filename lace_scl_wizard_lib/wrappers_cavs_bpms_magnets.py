class Cavity_Wrapper:
    def __init__(self,model_cav,bpm_wrappers):
        #---- Online Model Cavity
        self.model_cav = model_cav
        #---- PyORBIT cavity - cav
        self.cav = self.model_cav.cav
        res_name_arr = self.model_cav.cav.getName().split(":")
        self.alias = self.model_cav.cav.getName()
        if(len(res_name_arr) > 1): self.alias = self.model_cav.cav.getName().split(":")[1]       
        self.isGood = True
        self.isMeasured = False
        self.isAnalyzed = False
        #---- bpm_amp_phase_dict and bpm_xy_dict dictionary with BasicGraph data
        #---- self.bpm_amp_phase_dic[BPM_Wrapper] = (FunctionAmp,FunctionPhase)
        self.bpm_amp_phase_dict = {}
        self.bpm_wrappers = bpm_wrappers
        #--- use or not in phase scan analysis: self.bpm_wrappers_useInPhaseAnalysis[bpm_wrapper,]
        self.bpm_wrappers_useInPhaseAnalysis = []
        #--- use or not in BPMs' amplitudes analysis: self.bpm_wrappers_useInAmpBPMs[bpm_wrapper,]
        self.bpm_wrappers_useInAmpBPMs = []
        #--- BPM wrappers for BPM0 and BPM1 during cavity phase setup after the phase scan
        self.bpm_wrapper0 = "None"
        self.bpm_wrapper1 = "None"
        #----cavity's parameters 
        self.epicsAmp = 0.
        self.epicsPhase = 0.
        #-- design parameters will be defined after analysis of the phase scan data
        self.modelAmp = 0.
        self.modelPhase = 0.
        self.modelCoeffToEpicsAmp = 0.
        #---- This is a phase shift between EPICS and model phases
        self.model_phase_shift = 0.
        #---- kinetic energies in MeV
        self.eKin_in = 185.6
        self.eKin_out = 185.6
        self.eKin_guess = 185.6
        
    def getAlias(self):
        return self.alias 
        
class BPM_Wrapper:
    def __init__(self,model_bpm):
        self.model_bpm = model_bpm
        st = "SCL:"
        if(model_bpm.bpm.getName().find("HEBT") >= 0): st = "HEBT:"
        if(model_bpm.bpm.getName().find("CCL") >= 0): st = "CCL:"
        self.alias = st + model_bpm.bpm.getName().split(":")[1]
        self.isGood = True
        #---- OEDA stands for Off Energy Delay Adjustment in [ms]
        self.oeda_time_shift = 0.
        
    def getPosition(self):
        return self.model_bpm.getPosition()
        
    def setOEDA_TimeShift(self,oeda_time_shift):
        """ OEDA stands for Off Energy Delay Adjustment in [ms] """
        self.oeda_time_shift = oeda_time_shift
        
    def getOEDA_TimeShift(self):
        """ OEDA stands for Off Energy Delay Adjustment in [ms] """
        return self.oeda_time_shift
        
    def getPhaseOffset(self):
        return self.model_bpm.getEPICS_PhaseOffset()
        
    def getModelBPM(self):
        return self.model_bpm
          
    def getAlias(self):
        return self.alias 
        
    def clean(self):
        pass
