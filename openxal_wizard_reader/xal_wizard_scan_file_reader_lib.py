#! /usr/bin/env python

"""
This is a collection of classes to read OpenXAL SCL Wizard phase scan 
XML file and prepare the scan tables for all SCL cavities 
with data from all BPMs - phases, amplitudes, 
x and y beam center positions.
"""

import sys
import math
import random
import time

# import the XmlDataAdaptor XML parser
from orbit.utils.xml import XmlDataAdaptor
from orbit.utils import NamedObject

class XALtoSCL_TuneWizardUpdater:
    """
    This class reads the OpenXAL SCL Wizard Doc file and put the cavities
    scan data into the SCL Tune Wizard based on PyORBIT
    """
    def __init__(self,lace_scl_wizard):
        self.lace_scl_wizard = lace_scl_wizard
        self.scl_scan_reader = None
        
    def getBPM_Wrapper(self,alias):
        bpm_wrappers = self.lace_scl_wizard.getBPM_Wrappers()
        for bpm_wrapper in bpm_wrappers:
            if(bpm_wrapper.getAlias() == alias): return bpm_wrapper
        return None
        
    def updateSCL_Tune_Wizard(self,file_name):
        self.scl_scan_reader = SCL_Wizard_File_Reader()
        self.scl_scan_reader.readSCL_WizardXML(file_name)
        print ("degug file name=",file_name)
        #-----------------------------------------------------------------
        #---- Updates all cavities scan data -----------------------------
        #---- get initial energy from the the exit of the previous cavity
        #---- The out energy of the cavity is defined by BPMs data
        #-----------------------------------------------------------------
        cav_wrappers = self.lace_scl_wizard.getCavWrappers()
        for cav_wrapper in cav_wrappers:
            xal_cavity_wrapper = None
            if(cav_wrapper.getAlias() == "CCL4"):
                xal_cavity_wrapper = self.scl_scan_reader.getXAL_CavityWrapperDict()["AllOff"]
            else: 
                xal_cavity_wrapper = self.scl_scan_reader.getXAL_CavityWrapperDict()["SCL:"+cav_wrapper.getAlias()]
            cav_wrapper.isGood = xal_cavity_wrapper.isGood()
            cav_wrapper.isAnalyzed = xal_cavity_wrapper.isAnalyzed()
            #---- Technically we cannot consider this cavity analyzed
            #---- the XAL model is not PyORBIT model. But we allow the user
            #---- to see parameters in the table.
            #cav_wrapper.isAnalyzed = False
            (bpm0_name,bpm1_name) = xal_cavity_wrapper.getBPMs01()
            cav_wrapper.eKin_in = xal_cavity_wrapper.eKin_In()
            cav_wrapper.eKin_out = xal_cavity_wrapper.eKin_Out()
            cav_wrapper.eKin_model_out = xal_cavity_wrapper.eKin_Model_Out()
            if(cav_wrapper.getAlias() == "CCL4"):
                cav_wrapper.eKin_in = 185.6
                cav_wrapper.eKin_out = 185.6
            cav_wrapper.eKin_guess = cav_wrapper.eKin_out
            cav_wrapper.synch_acc_phase = xal_cavity_wrapper.realSynchPhase()
            cav_wrapper.synch_real_acc_phase = cav_wrapper.synch_acc_phase
            cav_wrapper.epicsAmp = xal_cavity_wrapper.EPICS_Amp() 
            cav_wrapper.epicsPhase = xal_cavity_wrapper.EPICS_Phase()
            cav_wrapper.epicsAmpInit = xal_cavity_wrapper.EPICS_Amp()
            cav_wrapper.epicsPhaseInit =  xal_cavity_wrapper.EPICS_Phase()
            cav_wrapper.sin_phase_func_amp = xal_cavity_wrapper.sinPhaseScanAmp()
            cav_wrapper.sin_phase_func_amp_err = xal_cavity_wrapper.sinPhaseScanAmpErr()
            cav_wrapper.bpm_wrapper0 = self.getBPM_Wrapper(bpm0_name)
            cav_wrapper.bpm_wrapper1 = self.getBPM_Wrapper(bpm1_name)
            #print ("debug cav=",cav_wrapper.getAlias()," bpm 0,1 =", (bpm0_name,bpm1_name))
            #if(cav_wrapper.bpm_wrapper0 != None and cav_wrapper.bpm_wrapper1 != None):
            #    print ("debug =========  self.bpm_wrapper 0 1 =",cav_wrapper.bpm_wrapper0.getAlias()," ",cav_wrapper.bpm_wrapper1.getAlias())
            #------ just test
            eKinIn = xal_cavity_wrapper.eKin_In()
            eKinOut = xal_cavity_wrapper.eKin_Out()
            st  = "debug cav=" + xal_cavity_wrapper.getName()
            st += " isGood = "+ str(xal_cavity_wrapper.is_good)
            st += " eKinIn[MeV] = %8.3f "%eKinIn
            st += " eKinOut[MeV] = %8.3f "%eKinOut
            #print (st)
            #----- ekin Out values vs. cav. phases 
            cav_wrapper.eKin_out_func.clean()
            cav_wrapper.eKin_out_fit_func.clean()
            cav_phase_arr = xal_cavity_wrapper.getCavity_PhaseArr()
            ekinOut_arr = xal_cavity_wrapper.eKin_Out_Arr()
            ekinOut_fit_arr = xal_cavity_wrapper.eKin_Out_Arr()
            if(len(cav_phase_arr) == len(ekinOut_arr) and len(cav_phase_arr) > 0):
                for cav_phase_ind,cav_phase in enumerate(cav_phase_arr):
                    cav_wrapper.eKin_out_func.add(cav_phase,ekinOut_arr[cav_phase_ind])
                    cav_wrapper.eKin_out_fit_func.add(cav_phase,ekinOut_fit_arr[cav_phase_ind])
                    #print ("debug cav_phase ind =",cav_phase_ind," phase=",cav_phase," eKinout=",ekinOut_arr[cav_phase_ind])
            if(cav_wrapper.isGood and cav_wrapper.eKin_out_func.getSize() > 0):
                cav_wrapper.isMeasured = True
            #---- set up BPM phases during the cavity phase scan
            for bpm_wrapper in cav_wrapper.bpm_wrappers:
                (ampFunc,phaseFunc) = cav_wrapper.bpm_amp_phase_dict[bpm_wrapper.getAlias()]
                ampFunc.clean()
                phaseFunc.clean()
                cav_phase_arr = xal_cavity_wrapper.getCavity_PhaseArr(bpm_wrapper.getAlias())
                bpm_amp_arr = xal_cavity_wrapper.getBPM_AmpArr(bpm_wrapper.getAlias())
                bpm_phase_arr = xal_cavity_wrapper.getBPM_PhaseArr(bpm_wrapper.getAlias())
                if(len(bpm_amp_arr) != len(bpm_phase_arr) or len(bpm_amp_arr) != len(cav_phase_arr)): continue
                for cav_phase_ind,cav_phase in enumerate(cav_phase_arr):
                    bpm_amp = bpm_amp_arr[cav_phase_ind]
                    bpm_phase = bpm_phase_arr[cav_phase_ind]
                    ampFunc.add(cav_phase,bpm_amp)
                    phaseFunc.add(cav_phase,bpm_phase)
                #print ("debug cav_wrapper=",cav_wrapper.getAlias()," bpm=",bpm_wrapper.getAlias()," len(phases)=",phaseFunc.getSize())
            #---- fill out BPM 0 and 1 phases difference Function from array from xal_cavity_wrapper
            bpm_diff_arr = xal_cavity_wrapper.getBPM_DifferenceArr()
            cav_wrapper.phaseDiffBPM01_func.clean()
            for [cav_phase,bpm_diff_phase] in bpm_diff_arr:
                cav_wrapper.phaseDiffBPM01_func.add(cav_phase,bpm_diff_phase)
            #---- fill out BPM 0 and 1 phases difference Function from array from xal_cavity_wrapper
            bpm_diff_fit_arr = xal_cavity_wrapper.getBPM_DifferenceFitArr()
            cav_wrapper.phaseDiffBPM01_fit_func.clean()
            for [cav_phase,bpm_diff_phase_fit] in bpm_diff_fit_arr:
                cav_wrapper.phaseDiffBPM01_fit_func.add(cav_phase,bpm_diff_phase_fit)                
        #-------------------------------------------------------------------
        #---- Updates all BPMs parameters data -----------------------------
        #-------------------------------------------------------------------
        bpm_wrappers = self.lace_scl_wizard.getBPM_Wrappers()
        for bpm_wrapper in bpm_wrappers:
            bpm_alias = bpm_wrapper.getAlias()
            xal_bpm_wrapper_dict = self.scl_scan_reader.getXAL_BPM_WrapperDict()
            if(bpm_alias in xal_bpm_wrapper_dict):
                xal_bpm_wrapper = self.scl_scan_reader.getXAL_BPM_WrapperDict()[bpm_wrapper.getAlias()]
                xal_pos = xal_bpm_wrapper.getPosition()
                xal_isGood = xal_bpm_wrapper.isGood()
                xal_phaseOffset = xal_bpm_wrapper.phaseOffset()
                xal_phaseOffsetErr = xal_bpm_wrapper.phaseOffsetErr()
                xal_oeda_time_shift = xal_bpm_wrapper.OEDA_TimeShift()
                bpm_wrapper.isGood = xal_isGood
                bpm_wrapper.setPhaseOffset(xal_phaseOffset)
                bpm_wrapper.setPhaseOffsetErr(xal_phaseOffsetErr)
                bpm_wrapper.setOEDA_EPICS_TimeShift(xal_oeda_time_shift)
            else:
                bpm_wrapper.isGood = False
                bpm_wrapper.setPhaseOffset(0.)
                bpm_wrapper.setPhaseOffsetErr(0.)
                bpm_wrapper.setOEDA_EPICS_TimeShift(0.)
        #-------------------------------------------------------------------
        self.lace_scl_wizard.init_state_cntrl.cavs_data_table_model.tableChanged()
        self.lace_scl_wizard.cavs_phase_scan_cntrl.cavs_scan_cntrl.cavs_data_table_model.tableChanged()
        
    def calibrateCavityModel(self,cav_wrapper):
        pass
    
    def initOM(self):
        pass
        
class SCL_Wizard_File_Reader:
    """
    Reads SCL Wizard scans file and creates XmlDataAdaptor structure
    """
    def __init__(self):
        self.cavs_scans_da = XmlDataAdaptor("empty")
        self.bpms_params_da = XmlDataAdaptor("empty")
        self.scl_wizard_da = XmlDataAdaptor("empty")
        self.scl_wizard_file_name = ""
        self.xal_cavity_wrapper_dict = {}
        self.quad_field_dict = {}

    def getSCL_WizardFileName(self):
        """
        Returns initial OpenXAL Wizard XML file Name
        """
        return self.scl_wizard_file_name

    def getSCL_ScansDA(self):
        """ Returns the XmlDataAdaptor with cavities scan data """
        return self.cavs_scans_da 
        
    def getBPM_ParamsDA(self):
        """ Returns the XmlDataAdaptor with BPMs paremeters data """
        return self.bpms_params_da
        
    def getSCL_WizardDA(self):
        """ Returns the XmlDataAdaptor for the whole SCL Wizard """
        return self.scl_wizard_da

    def readSCL_WizardXML(self,xml_file_name):
        """
        Reads OpenXAL SCL Wizard phase scan XML file. 
        Returns the XmlDataAdaptor with cavities scan data.
        """
        self.cavs_scans_da = XmlDataAdaptor("empty")
        self.bpms_params_da = XmlDataAdaptor("empty")
        self.scl_wizard_da = XmlDataAdaptor("empty")
        self.scl_wizard_file_name = ""
        fl_in = open(xml_file_name,"r")
        lns = fl_in.readlines()
        fl_in.close()
        if(lns[1].find("LINAC_Wizard") < 0): return
        self.scl_wizard_file_name = xml_file_name
        #----------------------------
        namespace_txt =  ' xmlns:SCL_Diag="SCL_Diag" xmlns:HEBT_Diag="HEBT_Diag" ' 
        namespace_txt += ' xmlns:SCL_Mag="SCL_Mag" xmlns:HEBT_Mag="HEBT_Mag" '
        namespace_txt += ' xmlns:SCL="SCL" xmlns:HEBT="HEBT" '
        lns[1] = lns[1].replace("LINAC_Wizard ","LINAC_Wizard " + namespace_txt)
        #----------------------------
        txt = ""
        for ln in lns:
            txt += ln
        self.scl_wizard_da = XmlDataAdaptor.adaptorForString(txt)
        self._cleanNameSpaces(self.scl_wizard_da)
        #----------------------------
        (self.cavs_scans_da, self.bpms_params_da) = self._getSCL_Scans_DA()
        self.createXAL_CavityWrapperDict()
        self.createXAL_BPM_WrapperDict()
        self.createXAL_QuadFieldDict()
        return self.scl_wizard_da
        
    def _getSCL_Scans_DA(self):
        """ Extracts scan data from the whole DA """
        scl_tuneup_data_da = self.scl_wizard_da.childAdaptors("SCL_Longitudinal_Tuneup_Data")[0]
        cavs_scans_da = scl_tuneup_data_da.childAdaptors("Cavs_Parameters_and_Data")[0]
        bpms_params_da = scl_tuneup_data_da.childAdaptors("BPMs_Parameters_and_Data")[0]
        return (cavs_scans_da,bpms_params_da)

    def _cleanNameSpaces(self,child_in_da):
        """
        This method recursively transform node names from {SCL_Diag}BPM
        to SCL_Diag:BPM etc.
        """
        child_da_arr = child_in_da.childAdaptors()
        if(len(child_da_arr) == 0): return
        for child_da in child_in_da.childAdaptors():
            name_init = child_da.getName()
            if(name_init.find("{") >= 0): 
                name = name_init.replace("{","")
                name = name.replace("}",":")
                child_da.setName(name)
                #print ("name_init = ",name_init," new = ",name)
            self._cleanNameSpaces(child_da)
            
    def createXAL_CavityWrapperDict(self):
        """ It will create a dictionary with XAL_CavityScanDataWrapper instance vs. cavity name """
        xal_cavity_wrapper_dict = {}
        cavs_scans_da = self.getSCL_ScansDA()
        for cav_scan_da in cavs_scans_da.childAdaptors():
            cav_name = cav_scan_da.stringValue("cav")
            if(cav_scan_da.getName() == "AllOff"): cav_name = "AllOff"
            cav_is_good = cav_scan_da.intValue("isGood")
            cav_isAnalyzed = cav_scan_da.intValue("isAnalyzed")
            if(cav_name == "AllOff"):
                cav_is_good = cav_scan_da.intValue("isGood")
            bpm0_name = "None"
            bpm1_name = "None"
            if(cav_is_good > 0 and cav_isAnalyzed > 0 and cav_name != "AllOff"): 
                cav_is_good = True
                bpm0_name = cav_scan_da.stringValue("bpm0")
                bpm1_name = cav_scan_da.stringValue("bpm1")
            params_da = cav_scan_da.childAdaptors("Params")[0]
            cav_epics_phase = params_da.doubleValue("livePhase")
            cav_epics_amp = params_da.doubleValue("initLiveAmp")    
            cav_xal_model_amp = params_da.doubleValue("designAmp")
            cav_xal_model_phase = params_da.doubleValue("designPhase")
            goal_synch_phase = params_da.doubleValue("scanPhaseShift")
            real_synch_phase = params_da.doubleValue("real_scanPhaseShift")
            phase_scan_harm_amp = params_da.doubleValue("phase_scan_harm_amp")
            phase_scan_harm_amp_err = params_da.doubleValue("phase_scan_harm_err")
            eKin_in = params_da.doubleValue("eKin_in")
            eKin_out = params_da.doubleValue("bpm_eKin_out")
            eKin_model_out = params_da.doubleValue("model_eKin_out")
            #print ("debug cav = ",cav_name," cav. phase = %7.2f"%cav_epics_phase)
            #print ("debug cav = ",cav_name," eKin_model_out = %8.3f"%eKin_model_out)
            #----- BPMs phase difference between bpm0 and bpm1 vs cavity phase
            bpm_phase_diff_da = cav_scan_da.childAdaptors("Phase_Diff_GD")[0]
            bpm_phase_diff_x_arr = [float(st) for st in bpm_phase_diff_da.childAdaptors("x")[0].stringValue("arr").split()]
            bpm_phase_diff_y_arr = [float(st) for st in bpm_phase_diff_da.childAdaptors("y")[0].stringValue("arr").split()]
            bpm_phase_diff_fit_da = cav_scan_da.childAdaptors("Phase_Diff_Fit_GD")[0]
            bpm_phase_diff_x_fit_arr = [float(st) for st in bpm_phase_diff_fit_da.childAdaptors("x")[0].stringValue("arr").split()]
            bpm_phase_diff_y_fit_arr = [float(st) for st in bpm_phase_diff_fit_da.childAdaptors("y")[0].stringValue("arr").split()]            
            #----------------------------------------------------------------------
            xal_cav_wrapper = XAL_CavityScanDataWrapper(cav_name)
            xal_cav_wrapper.isGood(cav_is_good)
            xal_cav_wrapper.isAnalyzed(cav_isAnalyzed)
            xal_cav_wrapper.setBPMs01(bpm0_name,bpm1_name)
            xal_cav_wrapper.EPICS_Phase(cav_epics_phase)
            xal_cav_wrapper.EPICS_Amp(cav_epics_amp)
            xal_cav_wrapper.XAL_Model_Amp(cav_xal_model_amp)
            xal_cav_wrapper.XAL_Model_Phase(cav_xal_model_phase)
            xal_cav_wrapper.goalSynchPhase(goal_synch_phase)
            xal_cav_wrapper.realSynchPhase(real_synch_phase)
            xal_cav_wrapper.sinPhaseScanAmp(phase_scan_harm_amp)
            xal_cav_wrapper.sinPhaseScanAmpErr(phase_scan_harm_amp_err)
            xal_cav_wrapper.eKin_In(eKin_in)
            xal_cav_wrapper.eKin_Out(eKin_out)
            xal_cav_wrapper.eKin_Model_Out(eKin_model_out)
            #---- eKinOut list from bpm data analysis
            xal_cav_wrapper.getCavity_PhaseArr().clear()
            xal_cav_wrapper.eKin_Out_Arr().clear()
            xal_cav_wrapper.eKin_Out_Fit_Arr().clear()
            eKin_out_da =  cav_scan_da.childAdaptors("Ekin_Out_GD")[0]
            st_x_arr = eKin_out_da.childAdaptors("x")[0].stringValue("arr").split()
            st_y_arr = eKin_out_da.childAdaptors("y")[0].stringValue("arr").split()
            eKin_out_fit_da =  cav_scan_da.childAdaptors("Ekin_Out_Fit_GD")[0]
            st_y_fit_arr = eKin_out_fit_da.childAdaptors("y")[0].stringValue("arr").split()
            for ind,st_x in enumerate(st_x_arr):
                st_y = st_y_arr[ind]
                xal_cav_wrapper.getCavity_PhaseArr().append(float(st_x))
                xal_cav_wrapper.eKin_Out_Arr().append(float(st_y))
                if(cav_name != "AllOff"):
                    st_fit_y = st_y_fit_arr[ind]
                    xal_cav_wrapper.eKin_Out_Fit_Arr().append(float(st_fit_y))
            #----------------------------------------
            scan_data_da = cav_scan_da.childAdaptors("scan_data")[0]
            for bpm_da in scan_data_da.childAdaptors():
                #--------------------------------------------
                phase_da = bpm_da.childAdaptors("phase")[0]
                cav_phase_arr = []
                st_arr = phase_da.childAdaptors("x")[0].stringValue("arr").split()
                for st in st_arr:
                    cav_phase_arr.append(float(st))
                #--------------------------------------------
                bpm_phase_arr = []
                st_arr = phase_da.childAdaptors("y")[0].stringValue("arr").split()
                for st in st_arr:
                    bpm_phase_arr.append(float(st))             
                #--------------------------------------------
                amp_da = bpm_da.childAdaptors("amplitude")[0]
                bpm_amp_arr = []
                st_arr = amp_da.childAdaptors("y")[0].stringValue("arr").split()
                for st in st_arr:
                    bpm_amp_arr.append(float(st))                   
                #--------------------------------------------
                bpm_x_arr = []
                bpm_y_arr = []
                if(len(bpm_da.childAdaptors("posX")) != 0 and len(bpm_da.childAdaptors("posY")) != 0):
                    posX_da = bpm_da.childAdaptors("posX")[0] 
                    st_arr = posX_da.childAdaptors("y")[0].stringValue("arr").split()
                    for st in st_arr:
                        bpm_x_arr.append(float(st))                 
                    posY_da = bpm_da.childAdaptors("posY")[0]
                    st_arr = posY_da.childAdaptors("y")[0].stringValue("arr").split()
                    for st in st_arr:
                        bpm_y_arr.append(float(st)) 
                else:
                    for ind in range(len(cav_phase_arr)):
                        bpm_x_arr.append(0.)
                        bpm_y_arr.append(0.)
                #--------------------------------------------
                #bpm_name = bpm_da.getName().replace(":BPM","_Diag:BPM")
                bpm_name = bpm_da.getName()
                for ind,cav_phase in enumerate(cav_phase_arr):
                    bpm_phase = bpm_phase_arr[ind]
                    bpm_amp   = bpm_amp_arr[ind]
                    bpm_x = bpm_x_arr[ind]
                    bpm_y = bpm_y_arr[ind]
                    xal_cav_wrapper.addScanPoint(bpm_name,cav_phase,bpm_phase,bpm_amp,bpm_x,bpm_y)
                """
                print ("debug cav_name=",cav_name," bpm_name=",bpm_name)
                print ("debug cav_phase_arr = ",cav_phase_arr)
                print ("debug bpm_phase_arr = ",bpm_phase_arr)
                print ("debug bpm_amp_arr = ",bpm_amp_arr)
                print ("debug bpm_x_arr = ",bpm_x_arr)
                print ("debug bpm_y_arr = ",bpm_y_arr)
                if(cav_name == "SCL_RF:Cav01a" and bpm_name == "SCL_Diag:BPM05"): sys.exit(0)
                """
            xal_cav_wrapper.setBPM_DifferenceArr(bpm_phase_diff_x_arr,bpm_phase_diff_y_arr)
            xal_cav_wrapper.setBPM_DifferenceFitArr(bpm_phase_diff_x_fit_arr,bpm_phase_diff_y_fit_arr)
            #-----------------------------------------------
            xal_cavity_wrapper_dict[cav_name.replace("_RF","")] = xal_cav_wrapper
        #-----------------------------------------------
        self.xal_cavity_wrapper_dict = xal_cavity_wrapper_dict 
        return self.xal_cavity_wrapper_dict
        
    def createXAL_BPM_WrapperDict(self):
        """ Creates the dictionary of the BPMs' XAL Wrappers """
        xal_bpm_wrapper_dict = {}
        bpms_params_da = self.getBPM_ParamsDA()
        for bpm_params_da in bpms_params_da.childAdaptors():
            bpm_name = bpm_params_da.getName()
            alias = bpm_params_da.stringValue("alias")
            pos = bpm_params_da.doubleValue("pos")
            is_good = bpm_params_da.booleanValue("isGood")
            phase_offset_da = bpm_params_da.childAdaptors("final_phase_offset")[0]
            phase_offset = phase_offset_da.doubleValue("phaseOffset_avg")
            phase_offset_err = phase_offset_da.doubleValue("phaseOffset_err")
            oeda_time_shift_da = bpm_params_da.childAdaptors("BPM_Timing_Shift")[0]
            oeda_time_shift = oeda_time_shift_da.doubleValue("prod_time_shift")
            #-------------------------------
            xal_bpm_wrapper = XAL_BPM_DataWrapper(bpm_name,alias)
            xal_bpm_wrapper.setPosition(pos)
            xal_bpm_wrapper.isGood(is_good)
            xal_bpm_wrapper.phaseOffset(phase_offset)
            xal_bpm_wrapper.phaseOffsetErr(phase_offset_err)
            xal_bpm_wrapper.OEDA_TimeShift(oeda_time_shift)
            xal_bpm_wrapper_dict[alias] = xal_bpm_wrapper
        self.xal_bpm_wrapper_dict = xal_bpm_wrapper_dict
        return self.xal_bpm_wrapper_dict
        
    def getXAL_CavityWrapperDict(self):
        """ Returns a dictionary with XAL cavity wrappers classes """
        return self.xal_cavity_wrapper_dict
        
    def getXAL_BPM_WrapperDict(self):
        """ Returns a dictionary with XAL BPM wrappers classes """
        return self.xal_bpm_wrapper_dict
        
    def createXAL_QuadFieldDict(self):
        """ Creates a dictionary for quadrupole fileds in SCL and HEBT1 """
        scl_wizard_da = self.getSCL_WizardDA()
        scl_tuneup_data_da = scl_wizard_da.childAdaptors("SCL_Longitudinal_Tuneup_Data")[0]
        quad_fields_da = scl_tuneup_data_da.childAdaptors("SCL_QUADS_FIELDS")[0]
        quad_field_dict = {}
        for quad_da in quad_fields_da.childAdaptors():
            quad_field_dict[quad_da.getName()] = quad_da.doubleValue("field")
            #print ("debug quad=",quad_da.getName()," field=",quad_field_dict[quad_da.getName()])
        self.quad_field_dict = quad_field_dict
        return quad_field_dict      
        
    def getXAL_QuadFieldDict(self):
        """ Returns a dictionary for quadrupole fileds in SCL and HEBT1 """
        return self.quad_field_dict
    
class XAL_CavityScanDataWrapper(NamedObject):
    """
    Keeps arrays of phases, amplitudes, x adn y positions as a function of 
    cavity phases.
    For cavity it keeps:
    cavity name
    cavity EPICS phase
    """
    def __init__(self, name):
        NamedObject.__init__(self, name)
        #---- self.bpm_data_dict[bpm_name] = [cav_phase_arr,bpm_phase_arr,bpm_amp_arr,bpm_x_arr,bpm_y_arr]
        self.is_good = False
        #---- if scan data analysis for this cavity has been performed 
        self.is_Analyzed = False
        #---- BPMs for Phase Difference sin-like scan data
        self.bpm0_name = "None"
        self.bpm1_name = "None"
        #-----self.bpm_phase_diff_arr[cav_phase_ind] = [cav_phase,bpm_phase_diff] for bpm0 and bpm1
        #-----self.bpm_phase_diff_fit_arr[cav_phase_ind] = [cav_phase,bpm_phase_diff_fit] for bpm0 and bpm1
        self.bpm_phase_diff_arr = []
        self.bpm_phase_diff_fit_arr = []
        self.bpm_data_dict = {}
        self.cav_epics_phase = 0.
        self.cav_epics_amp = 0.
        self.cav_xal_model_amp = 0.
        self.goal_synch_phase = 0.
        self.real_synch_phase = 0.
        self.phase_scan_harm_amp = 0.
        self.phase_scan_harm_amp_err = 0.
        self.eKin_out = 0.
        self.eKin_in = 0.
        self.eKin_model_out = 0.
        #---- eKin_out list from BPMs phase analysis in SCL Wizard
        self.cav_phase_arr = []
        self.eKin_out_arr = []
        self.eKin_out_fit_arr = []
        
    def clear(self):
        """ Removes all data"""
        self.is_good = False
        self.bpm0_name = "None"
        self.bpm1_name = "None" 
        self.bpm_phase_diff_arr.clear()
        self.bpm_phase_diff_fit_arr.clear()
        self.bpm_data_dict = {}
        self.cav_epics_phase = 0.
        self.cav_epics_amp = 0.
        self.goal_synch_phase = 0.
        self.real_synch_phase = 0.
        self.phase_scan_harm_amp = 0.
        self.phase_scan_harm_amp_err = 0.
        self.eKin_out = 0.
        self.eKin_in = 0.
        self.eKin_model_out = 0.
        #---- eKin_out list from BPMs phase analysis in SCL Wizard
        self.cav_phase_arr.clear()
        self.eKin_out_arr.clear()
        self.eKin_out_fit_arr.clear()
        
    def isGood(self,is_good = None):
        if(is_good == None): return self.is_good
        self.is_good = is_good
        return self.is_good
        
    def isAnalyzed(self,is_Analyzed = None):
        if(is_Analyzed == None): return self.is_Analyzed
        self.is_Analyzed = is_Analyzed
        return self.is_Analyzed    
        
    def setBPMs01(self,bpm0_name,bpm1_name):
        self.bpm0_name = bpm0_name
        self.bpm1_name = bpm1_name
        
    def getBPMs01(self):
        return (self.bpm0_name,self.bpm1_name)
        
    def setBPM_DifferenceArr(self,x_arr,y_arr):
        #-----self.bpm_phase_diff_arr[cav_phase_ind] = [cav_phase,bpm_phase_diff] for bpm0 and bpm1
        self.bpm_phase_diff_arr = []
        for cav_phase_ind in range(len(x_arr)):
            self.bpm_phase_diff_arr.append([x_arr[cav_phase_ind],y_arr[cav_phase_ind]])
            
    def setBPM_DifferenceFitArr(self,x_arr,y_arr):
        #-----self.bpm_phase_diff_fit_arr[cav_phase_ind] = [cav_phase,bpm_phase_diff_fit] for bpm0 and bpm1
        self.bpm_phase_diff_fit_arr = []
        for cav_phase_ind in range(len(x_arr)):
            self.bpm_phase_diff_fit_arr.append([x_arr[cav_phase_ind],y_arr[cav_phase_ind]])

    def getBPM_DifferenceArr(self):
        #-----self.bpm_phase_diff_arr[cav_phase_ind] = [cav_phase,bpm_phase_diff] for bpm0 and bpm1
        return self.bpm_phase_diff_arr
        
    def getBPM_DifferenceFitArr(self):
        #-----self.bpm_phase_diff_fit_arr[cav_phase_ind] = [cav_phase,bpm_phase_diff_fit] for bpm0 and bpm1
        return self.bpm_phase_diff_fit_arr

    def EPICS_Phase(self,cav_epics_phase = None):
        """ Sets / gets EPICS phase of the cavity in deg. """
        if(cav_epics_phase == None): return self.cav_epics_phase
        self.cav_epics_phase = cav_epics_phase
        return self.cav_epics_phase
        
    def EPICS_Amp(self,cav_epics_amp = None):
        """ Sets / gets EPICS amp of the cavity in deg. """
        if(cav_epics_amp == None): return self.cav_epics_amp
        self.cav_epics_amp = cav_epics_amp
        return self.cav_epics_amp
        
    def XAL_Model_Amp(self,cav_xal_model_amp = None):
        """ Sets / gets OpenXAL Model amp of the cavity in MV/m """
        if(cav_xal_model_amp  == None): return self.cav_xal_model_amp 
        self.cav_xal_model_amp  = cav_xal_model_amp 
        return self.cav_xal_model_amp
        
    def XAL_Model_Phase(self,cav_xal_model_phase = None):
        """ Sets / gets OpenXAL Model 1st gap phase of the cavity in deg. """
        if(cav_xal_model_phase == None): return self.cav_xal_model_phase
        self.cav_xal_model_phase = cav_xal_model_phase
        return self.cav_xal_model_phase
        
    def goalSynchPhase(self,goal_synch_phase = None):
        """ Sets/ gets the goal for cavity synchronous phase """
        if(goal_synch_phase == None): return self.goal_synch_phase
        self.goal_synch_phase = goal_synch_phase
        return self.goal_synch_phase
        
    def realSynchPhase(self,real_synch_phase = None):
        """ Sets / gets the real for cavity synchronous phase """
        if(real_synch_phase == None): return self.real_synch_phase
        self.real_synch_phase = real_synch_phase
        return self.real_synch_phase
        
    def sinPhaseScanAmp(self, phase_scan_harm_amp = None):
        """ 
        Sets / gets the 1st harmonic phase scan amplitude for difference of
        BPMs phases vs. cavity's phases
        """
        if(phase_scan_harm_amp == None): return self.phase_scan_harm_amp
        self.phase_scan_harm_amp = phase_scan_harm_amp
        return self.phase_scan_harm_amp
        
    def sinPhaseScanAmpErr(self, phase_scan_harm_amp_err = None):
        """ 
        Sets / gets the error between measured values and fitting using the 1st 
        harmonic for difference of BPMs phases vs. cavity's phases
        """
        if(phase_scan_harm_amp_err == None): return self.phase_scan_harm_amp_err
        self.phase_scan_harm_amp_err = phase_scan_harm_amp_err
        return self.phase_scan_harm_amp_err
        
    def eKin_In(self,eKin_in = None):
        """ Sets / gets the energy (defined by BPMs) before cavity """
        if(eKin_in == None): return self.eKin_in
        self.eKin_in = eKin_in
        return self.eKin_in
        
    def eKin_Out(self,eKin_out = None):
        """ Sets / gets the energy after cavity """
        if(eKin_out == None): return self.eKin_out
        self.eKin_out = eKin_out
        return self.eKin_out
        
    def eKin_Model_Out(self,eKin_model_out = None):
        """ Sets / gets the energy (calculated by model) after cavity """
        if(eKin_model_out == None): return self.eKin_model_out
        self.eKin_model_out = eKin_model_out
        return self.eKin_model_out   
        
    def eKin_Out_Arr(self):
        return self.eKin_out_arr
        
    def eKin_Out_Fit_Arr(self):
        return self.eKin_out_fit_arr        
        
    def addScanPoint(self,bpm_name,cav_phase,bpm_phase,bpm_amp,bpm_x,bpm_y):
        """ We have to add points in order according to cav_phase """
        if(not (bpm_name in self.bpm_data_dict)):
            #print ("debug  =========== bpm_name=",bpm_name)
            self.bpm_data_dict[bpm_name] = [[cav_phase,],[bpm_phase,],[bpm_amp,],[bpm_x,],[bpm_y]]
        else:
            self.bpm_data_dict[bpm_name][0].append(cav_phase)
            self.bpm_data_dict[bpm_name][1].append(bpm_phase)
            self.bpm_data_dict[bpm_name][2].append(bpm_amp)
            self.bpm_data_dict[bpm_name][3].append(bpm_x)
            self.bpm_data_dict[bpm_name][4].append(bpm_y)

    def getNumberPhasePoints(self,bpm_name):
        if(not (bpm_name in self.bpm_data_dict)): return 0
        return len(self.bpm_data_dict[bpm_name][0])

    def getValuesForIndex(self,bpm_name,index):
        """ Returns  (cav_phase,bpm_phase,bpm_amp,bpm_x,bpm_y) for cav_phase index """
        if(not (bpm_name in self.bpm_data_dict)): return None
        if(index >= self.getNumberPhasePoints(bpm_name)): return None
        cav_phase = self.bpm_data_dict[bpm_name][0][index]
        bpm_phase = self.bpm_data_dict[bpm_name][0][index]
        bpm_amp   = self.bpm_data_dict[bpm_name][0][index]
        bpm_x     = self.bpm_data_dict[bpm_name][0][index]
        bpm_y     = self.bpm_data_dict[bpm_name][0][index]
        return (cav_phase,bpm_phase,bpm_amp,bpm_x,bpm_y)

    def getCavity_PhaseArr(self,bpm_name = None):
        if(not (bpm_name in self.bpm_data_dict) or bpm_name == None): 
            return self.cav_phase_arr
        return self.bpm_data_dict[bpm_name][0]      
        
    def getBPM_PhaseArr(self,bpm_name):
        if(not (bpm_name in self.bpm_data_dict)): return []
        return self.bpm_data_dict[bpm_name][1]
        
    def getBPM_AmpArr(self,bpm_name):
        if(not (bpm_name in self.bpm_data_dict)): return []
        return self.bpm_data_dict[bpm_name][2]
        
    def getBPM_X_Arr(self,bpm_name):
        if(not (bpm_name in self.bpm_data_dict)): return []
        return self.bpm_data_dict[bpm_name][3]
        
    def getBPM_Y_Arr(self,bpm_name):
        if(not (bpm_name in self.bpm_data_dict)): return []
        return self.bpm_data_dict[bpm_name][4]

class XAL_BPM_DataWrapper(NamedObject):
    """
    Keeps BPM's data:
    alias (e.g. SCL:BPM01 instead of name SCL_Diag:BPM01)
    position; 
    state=good/bad; 
    phase offset and its error;
    OEDA time shift
    """
    def __init__(self, xal_bpm_name, alias):
        NamedObject.__init__(self, xal_bpm_name)
        self.alias = alias
        self.xal_position = 0.
        self.is_good = False
        self.phase_offset = 0.
        self.phase_offset_err = 0.
        self.oeda_time_shift = 0.
        
    def clear(self):
        """ Removes all data"""
        self.is_good = False
        self.xal_position = 0.
        self.is_good = False
        self.phase_offset = 0.
        self.phase_offset_err = 0.
        self.oeda_time_shift = 0.
        
    def getAlias(self):
        """
        Returns alias (e.g. SCL:BPM01 instead of name SCL_Diag:BPM01)
        """
        return self.alias 
        
    def getPosition(self):
        """ Returns the position of BPM from XAL SCL Wizard file """
        return self.xal_position

    def setPosition(self,xal_position):
        """ Sets the position of BPM in XAL SCL Wizard file """
        self.xal_position = xal_position
        return self.xal_position
        
    def isGood(self,is_good = None):
        """ 
        Returns/Sets the is_good parameters 
        of BPM in XAL SCL Wizard file 
        """
        if(is_good == None): return self.is_good
        self.is_good = is_good
        return self.is_good
        
    def phaseOffset(self,phase_offset = None):
        """ 
        Returns/Sets the phase_offset parameters
        of BPM in XAL SCL Wizard file 
        """
        if(phase_offset == None): return self.phase_offset
        self.phase_offset = phase_offset
        return self.phase_offset
        
    def phaseOffsetErr(self,phase_offset_err = None):
        """ 
        Returns/Sets the phase_offset_err parameters
        of BPM in XAL SCL Wizard file 
        """
        if(phase_offset_err == None): return self.phase_offset_err
        self.phase_offset_err = phase_offset_err
        return self.phase_offset_err        
        
    def OEDA_TimeShift(self,oeda_time_shift = None):
        """ 
        Returns/Sets the oeda_time_shift parameters 
        of BPM in XAL SCL Wizard file
        """
        if(oeda_time_shift == None): return self.oeda_time_shift
        self.oeda_time_shift = oeda_time_shift
        return self.oeda_time_shift       


        

