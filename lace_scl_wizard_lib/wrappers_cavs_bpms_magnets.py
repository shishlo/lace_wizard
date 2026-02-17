import time

from orbit.core.orbit_utils import Function

#---- Channel access
import epics

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
        #---------------------------------------------------------------------
        #---- bpm_amp_phase_dict and bpm_xy_dict dictionary with Function instances data
        #---- Functions are values amplutudes of phases vs cavity phase
        #---- self.bpm_amp_phase_dic[BPM_Wrapper.getAlias()] = (FunctionAmp,FunctionPhase)
        self.bpm_amp_phase_dict = {}
        #---------------------------------------------------------------------
        #---- bpm_amp_phase_in_functions - BPMs phases and amplitudes vs. BPM's position
        #---- at the entrance of the cavity to calculate the entrance energy
        #---- bpm_amp_phase_in_funcions = (FunctionAmp(),FunctionPhase())
        self.bpm_amp_phase_in_funcions = (Function(),Function())
        #---------------------------------------------------------------------
        #---- Phase difference between phases bpm_wrapper1 and bpm_wrapper0 
        #---- vs. cavity phase
        self.phaseDiffBPM01_func = Function()
        self.bpm_wrappers = bpm_wrappers
        #--- use or not in phase scan analysis: self.bpm_wrappers_useInPhaseAnalysis[bpm_wrapper,]
        self.bpm_wrappers_useInPhaseAnalysis = []
        for bpm_wrapper in self.bpm_wrappers:
            self.bpm_wrappers_useInPhaseAnalysis.append(True)
        #--- use or not in BPMs' amplitudes analysis: self.bpm_wrappers_useInAmpBPMs[bpm_wrapper,]
        self.bpm_wrappers_useInAmpBPMs = []
        for bpm_wrapper in self.bpm_wrappers:
            self.bpm_wrappers_useInAmpBPMs.append(True)
        #--- BPM wrappers for BPM0 and BPM1 during cavity phase setup after the phase scan
        self.bpm_wrapper0 = None
        self.bpm_wrapper1 = None
        #----cavity's parameters 
        self.epicsAmp = 0.
        self.epicsPhase = 0.
        self.epicsAmpInit = 0.
        self.epicsPhaseInit = 0.
        #---- average acceleration phase
        self.synch_pahse = -18.
        #-- design parameters will be defined after analysis of the phase scan data
        self.modelAmp = 0.
        self.modelPhase = 0.       
        self.modelCoeffToEpicsAmp = 0.
        #---- Results of the sin-like analysis: bpm phases vs. cav. phase, amplitude of sin in degrees 
        self.sin_phase_func_amp = 0.
        self.sin_phase_func_amp_err = 0.
        #---- accelerating phase of the cavity: self.epicsPhase shift from cav. phase for min phase of BPMs
        self.synch_acc_phase = -15.
        #---- This is a phase shift between EPICS and model phases
        self.model_phase_shift = 0.
        #---- kinetic energies in MeV
        self.eKin_in = 185.6
        self.eKin_out = 185.6
        self.eKin_guess = 185.6
        self.eKin_guess_err = 0.
        #---- EPICS connections, PV channels
        self.is_connected = False
        pv_name_start = ""
        if(self.cav.getName().find("SCL") >= 0):
            pv_name_start = "SCL_LLRF:FCM" + self.cav.getName().split(":")[1].replace("Cav","") + ":"
        if(self.cav.getName().find("CCL") >= 0):
            tank_number_str = self.cav.getName()[3]
            pv_name_start = "CCL_LLRF:FCM" + tank_number_str + ":"
        self.cav_amp_pv = epics.PV(pv_name_start + "CtlAmpSet")
        self.cav_phase_pv = epics.PV(pv_name_start + "CtlPhaseSet")
        self.cav_blankig_pv = epics.PV(pv_name_start + "BlnkBeam")       
        
    def getAlias(self):
        return self.alias 
 
    def getPosition(self):
        return self.model_cav.getPosition()
        
    def cleanAllScanData(self):
        self.isMeasured = False
        self.isAnalyzed = False
        #----cavity's parameters 
        self.epicsAmp = 0.
        self.epicsPhase = 0.
        self.epicsAmpInit = 0.
        self.epicsPhaseInit = 0.
        #---- average acceleration phase
        self.synch_pahse = -18.
        #-- design parameters will be defined after analysis of the phase scan data
        self.modelAmp = 0.
        self.modelPhase = 0.       
        self.modelCoeffToEpicsAmp = 0.
        #---- Results of the sin-like analysis: bpm phases vs. cav. phase, amplitude of sin in degrees 
        self.sin_phase_func_amp = 0.
        self.sin_phase_func_amp_err = 0.
        #---- accelerating phase of the cavity: self.epicsPhase shift from cav. phase for min phase of BPMs
        self.synch_acc_phase = -15.
        #---- This is a phase shift between EPICS and model phases
        self.model_phase_shift = 0.      
        
    def connectPVs(self):
        self.is_connected = True
        if(self.cav_amp_pv.connected and self.cav_phase_pv.connected \
            and self.cav_blankig_pv.connected):
            return self.is_connected
        self.is_connected = False
        return self.is_connected
        
    def isConnected(self):
        return self.is_connected
     
    def setCavityEPICS_Blanking(self,cav_is_blank):
        if(self.is_connected):
            self.cav_blankig_pv.put(bool(cav_is_blank))
        
    def getCavityEPICS_Blanking(self):
        if(self.is_connected):
            return bool(self.cav_blankig_pv.get())
        return False
        
    def setEPICS_CavityAmp(self,epics_cav_amp):
        if(self.is_connected):
            self.cav_amp_pv.put(epics_cav_amp)
        self.epics_cav_amp = epics_cav_amp
        
    def getEPICS_CavityAmp(self):
        if(self.is_connected):
            return self.cav_amp_pv.get()
        return self.epicsAmp

    def setEPICS_CavityPhase(self,epics_cav_phase):
        if(self.is_connected):
            self.cav_phase_pv.put(epics_cav_phase)
        
    def getEPICS_CavityPhase(self):
        if(self.is_connected):
            return self.cav_phase_pv.get()
        return self.epicsPhase

class BPM_Wrapper:
    def __init__(self,model_bpm):
        self.model_bpm = model_bpm
        #---- PyORBIT BPM
        self.bpm = self.model_bpm.bpm
        st = "SCL:"
        if(model_bpm.bpm.getName().find("HEBT") >= 0): st = "HEBT:"
        if(model_bpm.bpm.getName().find("CCL") >= 0): st = "CCL:"
        self.alias = st + model_bpm.bpm.getName().split(":")[1]
        self.isGood = True
        #---- OEDA stands for Off Energy Delay Adjustment in [ms]
        self.oeda_time_shift = 0.
        #---- PV Channels
        self.is_connected = False
        res = self.bpm.getName().split(":")[1]
        pv_name_start = "SCL_Diag:" + res + ":"
        if(self.bpm.getName().find("HEBT") >= 0): pv_name_start = "HEBT_Diag:" + res + ":"
        if(self.bpm.getName().find("CCL") >= 0): pv_name_start = "CCL_Diag:" + res + ":"
        self.bpm_amp_pv = epics.PV(pv_name_start + "amplitudeAvg")
        self.bpm_phase_pv = epics.PV(pv_name_start + "phaseAvg")
        self.bpm_oeda_pv = epics.PV(pv_name_start + "OEDA")
        
    def getAlias(self):
        return self.alias
        
    def getPosition(self):
        return self.model_bpm.getPosition()

    def connectPVs(self):
        """ It connects all BPM PVs to EPICS """
        self.is_connected = True
        if(self.bpm_amp_pv.connected and self.bpm_phase_pv.connected and self.bpm_oeda_pv.connected):
            return self.is_connected
        self.is_connected = False
        return self.is_connected
        
    def setOEDA_EPICS_TimeShift(self,oeda_time_shift):
        """ OEDA stands for Off Energy Delay Adjustment in [ms] """
        self.oeda_time_shift = oeda_time_shift
        if(self.is_connected):
            self.bpm_oeda_pv.put(oeda_time_shift)
        
    def getOEDA_EPICS_TimeShift(self):
        """ OEDA stands for Off Energy Delay Adjustment in [ms] """
        if(self.is_connected):
            return self.bpm_oeda_pv.get()
        return self.oeda_time_shift

    def getAmpPV(self):
        """ Returns BPM amplitude PV instance """
        return self.bpm_amp_pv
        
    def getPhasePV(self):
        """ Returns BPM phase PV instance """
        return self.bpm_phase_pv

    def getEPICS_Phase(self):
        """ Returns BPM EPICS phase value """
        if(self.is_connected):
            return self.bpm_phase_pv.get()
        return 0.
            
    def getEPICS_Amp(self):
        """ Returns BPM EPICS amplitude value """
        if(self.is_connected):
            return self.bpm_amp_pv.get()
        return 0.

    def getPhaseOffset(self):
        return self.model_bpm.getEPICS_PhaseOffset()
        
    def setPhaseOffset(self,bpm_phase_offset):
        return self.model_bpm.setEPICS_PhaseOffset(bpm_phase_offset)
        
    def getModelBPM(self):
        return self.model_bpm
          
    def getAlias(self):
        return self.alias 
        
    def clean(self):
        pass


    
    
