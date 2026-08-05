import time

from orbit.core.orbit_utils import Function

from .lace_scl_wizard_auxiliary_lib import dumpFunctionToDA
from .lace_scl_wizard_auxiliary_lib import readFunctionFromDA

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
        self.bpm_wrappers = bpm_wrappers       
        #---------------------------------------------------------------------
        #---- bpm_amp_phase_dict and bpm_xy_dict dictionary with Function instances data
        #---- Functions are values amplutudes of phases vs cavity phase
        #---- self.bpm_amp_phase_dic[BPM_Wrapper.getAlias()] = (FunctionAmp,FunctionPhase)
        #---- FunctionAmp,FunctionPhase are functions of cavity phases during the scan
        self.bpm_amp_phase_dict = {}
        for bpm_wrapper in self.bpm_wrappers:
            self.bpm_amp_phase_dict[bpm_wrapper.getAlias()] = (Function(),Function())
        #---------------------------------------------------------------------
        #---- bpm_amp_phase_in_functions - BPMs phases and amplitudes vs. BPM's position
        #---- at the entrance of the cavity to calculate the entrance energy
        #---- bpm_amp_phase_entrance_funcions = (FunctionAmp(vs. BPM position),FunctionPhase(vs. BPM position))
        self.bpm_amp_phase_entrance_funcions = (Function(),Function())
        #---------------------------------------------------------------------
        #---- Phase difference between phases bpm_wrapper1 and bpm_wrapper0 
        #---- vs. cavity phase - measured and 1st harmonic fitting
        self.phaseDiffBPM01_func = Function()
        self.phaseDiffBPM01_fit_func = Function()
        #---- Function eKin_Out and its fit ( cavity phase) for analysis
        self.eKin_out_func = Function()
        self.eKin_out_fit_func = Function()
        self.eKin_out_fit_delta_rms = 0.
        #--- use or not in phase scan analysis: self.bpm_wrappers_useInPhaseAnalysis[True,...]
        self.bpm_wrappers_useInPhaseAnalysis = []
        for bpm_wrapper in self.bpm_wrappers:
            self.bpm_wrappers_useInPhaseAnalysis.append(True)
        #--- use or not in BPMs' amplitudes analysis: self.bpm_wrappers_useInAmpBPMs[True,...]
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
        self.epicsAmpGoal = 0.
        #-- design parameters will be defined after analysis of the phase scan data
        self.modelAmp = 0.
        self.modelPhase = 0.       
        self.modelCoeffToEpicsAmp = 0.
        #---- Results of the sin-like analysis: bpm phases vs. cav. phase, amplitude of sin in degrees 
        self.sin_phase_func_amp = 0.
        self.sin_phase_func_amp_err = 0.
        #---- kinetic energies in MeV after analysis of BPMs data based eKinOut vs. cavity EPICS phase
        self.eKin_in = 185.6
        self.eKin_out = 185.6
        self.eKin_guess = 185.6
        self.eKin_guess_err = 0.
        #---- beam energy for tracking through the whole model from CCL4 -> Cav32d
        self.eKin_model_in = 185.6
        self.eKin_model_out = 185.6       
        #---- E0TL parameter of simplified model
        self.E0TL = 0.
        #---- accelerating phase of the cavity: self.epicsPhase shift from cav. phase for minimal phase of BPMs
        #---- synch_acc_phase - accelaration phase from/for BPMs
        #---- synch_real_acc_phase - from eKinOut vs. Cavity Phase analysis
        self.synch_acc_phase = -15.0
        self.synch_real_acc_phase = -15.0
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
        #---- Amplitude Set Goal value PV
        self.cav_ampl_goal_pv = epics.PV(pv_name_start + "cavAmpGoal")   
        
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
        self.epicsAmpGoal = 0.
        #---- scan results cleaning
        for bpm_wrapper in self.bpm_wrappers:
            self.bpm_amp_phase_dict[bpm_wrapper.getAlias()][0].clean()
            self.bpm_amp_phase_dict[bpm_wrapper.getAlias()][1].clean()
        self.bpm_amp_phase_entrance_funcions[0].clean()
        self.bpm_amp_phase_entrance_funcions[1].clean()
        #-------------------------------------------------------
        self.bpm_wrappers_useInPhaseAnalysis = []
        for bpm_wrapper in self.bpm_wrappers:
            self.bpm_wrappers_useInPhaseAnalysis.append(True)
        self.bpm_wrappers_useInAmpBPMs = []
        for bpm_wrapper in self.bpm_wrappers:
            self.bpm_wrappers_useInAmpBPMs.append(True)
        #-------------------------------------------------------
        self.phaseDiffBPM01_func.clean()
        self.phaseDiffBPM01_fit_func.clean()
        self.eKin_out_func.clean()
        self.eKin_out_fit_func.clean()
        self.eKin_out_fit_delta_rms = 0.
        #-- design parameters will be defined after analysis of the phase scan data
        self.modelAmp = 0.
        self.modelPhase = 0.       
        self.modelCoeffToEpicsAmp = 0.
        #---- Results of the sin-like analysis: bpm phases vs. cav. phase, amplitude of sin in degrees 
        self.sin_phase_func_amp = 0.
        self.sin_phase_func_amp_err = 0.
        #---- kinetic energies in MeV after analysis of BPMs data based eKinOut vs. cavity EPICS phase
        self.eKin_in = 185.6
        self.eKin_out = 185.6
        self.eKin_guess = 185.6
        self.eKin_guess_err = 0.
        #---- accelerating phase of the cavity: self.epicsPhase shift from cav. phase for min phase of BPMs
        self.synch_acc_phase = -15.
        self.synch_real_acc_phase = -15.0
        #---- beam energy for tracking through the whole model from CCL4 -> Cav32d
        self.eKin_model_in = 185.6
        self.eKin_model_out = 185.6           
        
        
    def connectPVs(self):
        self.is_connected = True
        if(self.cav_amp_pv.connected and self.cav_phase_pv.connected \
            and self.cav_blankig_pv.connected and self.cav_ampl_goal_pv.connected):
            return self.is_connected
        self.is_connected = False
        return self.is_connected
        
    def isConnected(self):
        return self.is_connected
    
    def setModelCavityPhaseOffset(self,model_phase_shift):
        self.model_cav.setCavityPhaseOffset(model_phase_shift)
        
    def getModelCavityPhaseOffset(self):
        return self.model_cav.getCavityPhaseOffset()
    
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
        
    def getEPICS_CavityAmpGoal(self):
        if(self.is_connected):
            self.epicsAmpGoal = self.cav_amp_goal_pv.get()
        return self.epicsAmpGoal

    def setEPICS_CavityPhase(self,epics_cav_phase):
        if(self.is_connected):
            self.cav_phase_pv.put(epics_cav_phase)
        self.epicsPhase = epics_cav_phase
        
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
        #--- phase Offsets parameters
        #--- left - for the start from CCL4
        #--- right - for the start from HEBT1
        #--- final - will be used in analysis
        self.left_phase_offset = BPM_Phase_Offset(self)
        self.right_phase_offset = BPM_Phase_Offset(self)
        self.final_phase_offset = BPM_Phase_Offset(self)
        #---- PV Channels
        self.is_connected = False
        res = self.bpm.getName().split(":")[1]
        pv_name_start = "SCL_Diag:" + res + ":"
        if(self.bpm.getName().find("HEBT") >= 0): pv_name_start = "HEBT_Diag:" + res + ":"
        if(self.bpm.getName().find("CCL") >= 0): pv_name_start = "CCL_Diag:" + res + ":"
        self.bpm_amp_pv = epics.PV(pv_name_start + "amplitudeAvg")
        self.bpm_phase_pv = epics.PV(pv_name_start + "phaseAvg")
        self.bpm_oeda_pv = epics.PV(pv_name_start + "OEDA")
        #---- BPM OEDA - Off Energy Delay Adjustment in [ms]
        self.bpm_timing_bucket = BPM_OEDA_Timing_Bucket(self,self.bpm_oeda_pv)
        
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
        
    def getOEDA_TimeShift(self):
        return self.bpm_timing_bucket.getProductionTimeShift()
        
    def getBPM_TimingBucket(self):
        return self.bpm_timing_bucket

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
       
    def getPhaseOffsetErr(self):
        return self.model_bpm.getEPICS_PhaseOffsetErr()
        
    def setPhaseOffset(self,bpm_phase_offset):
        return self.model_bpm.setEPICS_PhaseOffset(bpm_phase_offset)
        
    def setPhaseOffsetErr(self,bpm_phase_offset_err):
        return self.model_bpm.setEPICS_PhaseOffsetErr(bpm_phase_offset_err)    
        
    def getModelBPM(self):
        return self.model_bpm
          
    def getAlias(self):
        return self.alias 
        
    def clean(self):
        pass

class BPM_Phase_Offset:
    """
    Keeps information about a BPM phase offset.
    It is used for the offset calculated from CCL4 (aka left offset)
    and HEBT1 (aka right offset).
    """
    def __init__(self,bpm_wrapper):
        self.bpm_wrapper = bpm_wrapper
        self.phaseOffset_avg = 0.
        self.phaseOffset_err = 0.
        self.phaseOffset_arr = []
        self.isReady = False
        #--- the base bpm with zero phase offset 
        self.base_bpm_wrapper = None
        #----- temp values for convenience 
        self.phase_val_tmp = 0.
        self.phase_val_err_tmp = 0.
        
    def setBaseBPM_Wrapper(self,base_bpm_wrapper):
        self.base_bpm_wrapper = base_bpm_wrapper
    
    def getBaseBPM_Wrapper(self):
        return self.base_bpm_wrapper
            
    def isReady(self,isReady = None):
        if(isReady == None):
            return isReady
        self.isReady = isReady
        return self.isReady
        
    def clean(self):
        self.isReady = False
        self.base_bpm_wrapper = None
        self.phaseOffset_avg = 0.
        self.phaseOffset_err = 0.
        self.phaseOffset_arr = []
        self.base_bpm_wrapper = None
    
class BPM_OEDA_Timing_Bucket:
    def __init__(self,bpm_wrapper,pv_oeda):
        """
        PV name = SCL_Diag:BPM??:OEDA
        OEDA stands for Off Energy Delay Adjustment.
        """
        self.bpm_wrapper = bpm_wrapper
        self.pv_oeda = pv_oeda
        #---- production time shift is defined by time shift scan for production setup
        self.production_time_shift = 0.
        #---- memorized production time shift used to restore prodiction time shift if it is not 0
        self.memorized_time_shift = 0.
        #---- tuning time shift is defined by online model run with some cavities blanked
        self.tuning_time_shift = 0.
        #---- test timing shift for testing and debugging. No need to save/restore
        self.test_time_shift = 0.
        #---- graph data -------------------------
        self.amp_timing_data_func = Function()
        self.phase_timing_data_func = Function()
        
    def clean(self):
        self.amp_timing_data_func.clean()
        self.phase_timing_data_func.clean()                 
                           
    def getGraphDataFuncArr(self):
        return [self.amp_timing_data_func,self.phase_timing_data_func]
        
    def getTuningTimeShift(self):
        return self.tuning_time_shift
        
    def setTuningTimeShift(self,tuning_time_shift):
        self.tuning_time_shift = tuning_time_shift
        
    def getTestTimeShift(self):
        return self.test_time_shift
        
    def setTestTimeShift(self,tuning_time_shift):
        self.test_time_shift = tuning_time_shift        
        
    def getProductionTimeShift(self):
        return self.production_time_shift

    def updateProductionTimeShift(self):
        self.production_time_shift = 0.
        if(self.pv_oeda.connected):
            self.production_time_shift = self.pv_oeda.get()*1.0e+6
            
    def externalUpdateProductionTimeShift(self, production_time_shift):
        """
        This method should be used only if we know the self.pv_oeda.getValDbl() 
        value already from extrenal PV reading. 
        """
        self.production_time_shift = production_time_shift

    def setProductionTimeShift(self,production_time_shift):
        if(self.pv_oeda.connected):
            self.pv_oeda.put(production_time_shift/1.0e+6)
        self.production_time_shift = production_time_shift
        
    def getMemorizedTimeShift(self):
        return self.memorized_time_shift
        
    def setMemorizedTimeShift(self,memorized_time_shift):
        self.memorized_time_shift = memorized_time_shift

    def writeDataToXML(self,root_da):
        #------ write data for BPM timing shift to the XML stucture
        timing_wrapper_da = root_da.createChild("BPM_Timing_Shift")
        timing_wrapper_da.setValue("BPM",self.bpm_wrapper.alias)
        timing_wrapper_da.setValue("prod_time_shift",self.production_time_shift)
        timing_wrapper_da.setValue("memorized_time_shift",self.memorized_time_shift)        
        timing_wrapper_da.setValue("tuning_time_shift",self.tuning_time_shift)
        scan_data_da = timing_wrapper_da.createChild("timing_shift_scan_data")
        dumpFunctionToDA(self.amp_timing_data_func,scan_data_da,"amp","%8.6f","%8.6f")
        dumpFunctionToDA(self.phase_timing_data_func,scan_data_da,"phase","%8.6f","%10.3g")
        
    def readDataFromXML(self,root_da):      
        #------ read data for BPM timing shift from the XML stucture
        timing_wrapper_da = root_da.childAdaptor("BPM_Timing_Shift")
        if(timing_wrapper_da == null): return
        self.production_time_shift = timing_wrapper_da.doubleValue("prod_time_shift")
        self.tuning_time_shift = timing_wrapper_da.doubleValue("tuning_time_shift")
        if(timing_wrapper_da.hasAttribute("memorized_time_shift")):
            self.memorized_time_shift = timing_wrapper_da.doubleValue("memorized_time_shift")
        else:
            self.memorized_time_shift = 0.
        scan_data_da = timing_wrapper_da.childAdaptor("timing_shift_scan_data")
        if(scan_data_da == null): return
        readFunctionFromDA(self.amp_timing_data_func,scan_data_da,"amp")
        readFunctionFromDA(self.phase_timing_data_func,scan_data_da,"phase")