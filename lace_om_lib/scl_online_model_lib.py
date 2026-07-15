#-------------------------------------------------------------------------------
# This a SNS SCL Online Model that will be used for SCL RF scans data analysis 
#-------------------------------------------------------------------------------

import sys
import math
import time

# import the XmlDataAdaptor XML parser
from orbit.utils.xml import XmlDataAdaptor

from orbit.core.orbit_utils import Function

from orbit.py_linac.linac_parsers import SNS_LinacLatticeFactory

# import general accelerator elements and lattice
from orbit.lattice import AccLattice, AccNode, AccActionsContainer

# from linac import the C++ RF gap classes
# ---- for these RF gap models parameters are defined by the synchronous particle
from orbit.core.linac import BaseRfGap, MatrixRfGap, RfGapTTF

# ---- variants of slow RF gap models which updates all RF gap parameters
# ---- individually for each particle in the bunch
from orbit.core.linac import BaseRfGap_slow, RfGapTTF_slow, RfGapThreePointTTF_slow

# import acc. nodes
from orbit.py_linac.lattice.LinacAccNodes import Quad, AbstractRF_Gap
from orbit.py_linac.lattice.LinacAccNodes import BaseLinacNode, MarkerLinacNode

# import orbit Bunch and Twiss Analysis
from orbit.core.bunch import Bunch, BunchTwissAnalysis
from orbit.bunch_generators import TwissContainer

from orbit.utils import phaseNearTargetPhaseDeg
from orbit.utils import speed_of_light

# ---- import 3D Ellipse space charge
from orbit.core.spacecharge import SpaceChargeCalcUnifEllipse
from orbit.space_charge.sc3d import setUniformEllipsesSCAccNodes

from .sns_linac_bunch_generator import SNS_Linac_BunchGenerator
from .sns_linac_bunch_generator import get_SCL_EmptyBunch

def getBPM_Position_Dict(accLattice):
    """
    Retuns bpm_list and bpm_pos_dict - ( bpm_list,bpm_pos_dict)
    """
    def getBPM(children):
        for node in children:
            if(node.getName().find("BPM") >= 0):
                return node
        return None     
    #-------------------------------------------------
    bpms = accLattice.getNodesForSubstring("BPM","drift")[:]
    node_pos_dict = accLattice.getNodePositionsDict()
    bpm_pos_dict = {}
    for bpm in bpms:
        bpm_pos_dict[bpm] = node_pos_dict[bpm][0]
        #print ("debug Node=",bpm.getName()," pos=",bpm_pos_dict[bpm])
    #---- Quads analysis if BPM is present-----------------------
    quads = accLattice.getNodesOfClass(Quad)
    for quad in quads:
        if(quad.getName().find("HEBT") < 0): continue
        quad_pos = node_pos_dict[quad][0]
        n_parts = quad.getnParts()
        pos = quad_pos
        #print ("debug quad=",quad.getName()," pos=",pos)
        for ind in range(n_parts):
            children = quad.getChildNodes(Quad.BODY,part_index = ind,place_in_part = Quad.BEFORE)
            bpm = getBPM(children)
            if(bpm != None):
                bpms.append(bpm)
                bpm_pos_dict[bpm] = pos
                #print ("Debug   Inside BPM found name=",bpm.getName(),"  quad=",quad.getName())
                break
            pos +=  quad.getLength(ind)
            children = quad.getChildNodes(Quad.BODY,part_index = ind,place_in_part = Quad.AFTER)
            bpm = getBPM(children)
            if(bpm != None):
                bpms.append(bpm)
                bpm_pos_dict[bpm] = pos
                #print ("Debug   Inside BPM found name=",bpm.getName(),"  quad=",quad.getName())
                break
    #----- sorting BPMs according to the position
    for bpm in bpms:
        bpm.setPosition(bpm_pos_dict[bpm])
    bpms = sorted(bpms, key= lambda bpm : float(bpm.getPosition()))
    return (bpms,bpm_pos_dict)
    
def setUpQuadFieldsFromFile(file_name,quads):
    """
    Reads the file with "quad_name field" data and update fields in quads.
    Returns the dictionary with name_field_dict[name] setup fields.
    """
    fl_in = open(file_name,"r")
    lns = fl_in.readlines()
    fl_in.close()
    quad_field_dict = {}
    for ln in lns:
        res_arr = ln.split()
        if(len(res_arr) == 2):
            quad_name = res_arr[0]
            field = float(res_arr[1])
            quad_field_dict[quad_name] = field
    #--------------------
    name_field_dict = {}
    for quad in quads:
        name = quad.getName()
        if(name in quad_field_dict):
            field = quad_field_dict[name]
            quad.setField(field)
            name_field_dict[name] = field
    return name_field_dict

class BunchDiagnosticNode(BaseLinacNode):
    """
    Bunch diagnistic node for beam coordinates and Twiss parameters.
    """
    def __init__(self,name,twiss_analysis = BunchTwissAnalysis(),bpm_frequency = 402.5e+6,cav_frequency = 805.0e+6):
        BaseLinacNode.__init__(self,name)
        #---- bpm and cavities frequency MHz
        self.bpm_frequency = bpm_frequency
        self.cav_frequency = cav_frequency
        self.twiss_analysis = twiss_analysis
        #---- will be in mm and mrad
        self.x = 0.
        self.y = 0.
        self.xp = 0.
        self.yp = 0.
        #---- will be in deg (bunch phase and synch particle phase) 
        self.model_phase = 0.
        self.model_synch_phase = 0.
        #---- will be in MeV
        self.eKin = 0.
        #---- BPM amplitude
        self.bpm_amp_max = 1.0
        self.bpm_amp = 0.
        self.z_rms_deg = 0.
        #---- Beam Twiss
        self.twiss_arr = (None,None,None)
        #---- arrival time 
        self.bpm_synch_part_time = 0.
        self.bpm_bunch_center_time = 0.
        #--- speed of light
        self.v_light = speed_of_light  # in [m/sec]
        self.bpm_wave_lenght = self.v_light/self.bpm_frequency
        #---- initial number of particles
        self.nParticles = 0
        self.transmission = 0.
        #---- EPICS BPM handles the connection to EPICS
        self.epics_bpm = None
        #---- BPM phase offset relative to EPICS value 
        #---- model epics_bpm_phase = model_phase + bpm_phase_offset
        self.bpm_phase_offset = 0.
        self.bpm_phase_offset_err = 0.
        #---- phase shift for the bunch as whole from synch. particle
        self.delta_phase = 0.
     
    def getFrequencyBPM(self):
        return self.bpm_frequency
        
    def getFrequencyCav(self):
        return self.cav_frequency

    def getModelPhase(self):
        return self.model_phase
        
    def setNumberParticles(self,nParticles):
        self.nParticles = nParticles
        
    def getTwissXYZ(self):
        return self.twiss_arr

    def trackDesign(self, paramsDict):
        """
        The synch. particle values will be used 
        """
        bunch = paramsDict["bunch"]
        self.x = 0.
        self.y = 0.
        self.xp = 0.
        self.yp = 0.
        self.bpm_amp = 0.
        self.z_rms_deg = 0.
        #---- rms sizes
        self.x_rms = 0.
        self.y_rms = 0.
        self.z_rms = 0.
        self.xp_rms = 0.
        self.yp_rms = 0.
        self.dE_rms = 0.
        #---- phase shift for the bunch as whole
        self.delta_phase = 0.
        #---- phase will be in deg
        self.bpm_synch_part_time = bunch.getSyncParticle().time()
        self.bpm_bunch_center_time = self.bpm_synch_part_time
        self.model_phase = phaseNearTargetPhaseDeg(self.bpm_synch_part_time*360.0*self.bpm_frequency,0.)
        self.model_synch_phase = self.model_phase
        #---- it will be in MeV
        self.eKin = bunch.getSyncParticle().kinEnergy()*1.0e+3
        self.dE_avg = 0.
        #---- self.dP_P = dP/P = (E^2/P^2)*(dE_rms/E) = (1/beta)**2 * (dE_rms/E)
        self.dP_P = 0.
        
    def track(self, paramsDict):
        """
        It is tracking the bunch through this node.
        """
        bunch = paramsDict["bunch"]
        nParts = bunch.getSize()
        self.transmission = 0.
        self.dE_avg = 0.
        if(nParts < 3):
            self.transmission = 0.
            self.x = 0.
            self.y = 0.
            self.xp = 0.
            self.yp = 0.
            self.z_rms_deg = 0.
            #---- rms sizes
            self.x_rms = 0.
            self.y_rms = 0.
            self.z_rms = 0.
            self.xp_rms = 0.
            self.yp_rms = 0.
            self.dE_rms = 0.
            self.dP_P = 0.
            #------------------
            self.bpm_amp = self.bpm_amp_max
            self.delta_phase = 0.
            self.bpm_synch_part_time = bunch.getSyncParticle().time()
            self.bpm_bunch_center_time = self.bpm_synch_part_time
            self.model_phase = phaseNearTargetPhaseDeg(self.bpm_synch_part_time*360.0*self.bpm_frequency,0.)
            self.eKin = bunch.getSyncParticle().kinEnergy()*1.0e+3
            #print ("debug name=",self.getName()," eKin=",bunch.getSyncParticle().kinEnergy()*1000.)
            return
        self.twiss_analysis.analyzeBunch(bunch)
        self.x = self.twiss_analysis.getAverage(0)
        self.y = self.twiss_analysis.getAverage(2)
        self.xp = self.twiss_analysis.getAverage(1)
        self.yp = self.twiss_analysis.getAverage(3)
        self.x_rms = math.sqrt(self.twiss_analysis.getCorrelation(0,0))*1000.
        self.y_rms = math.sqrt(self.twiss_analysis.getCorrelation(2,2))*1000.
        self.z_rms = math.sqrt(self.twiss_analysis.getCorrelation(4,4))*1000.
        self.xp_rms = math.sqrt(self.twiss_analysis.getCorrelation(1,1))*1000.
        self.yp_rms = math.sqrt(self.twiss_analysis.getCorrelation(3,3))*1000.
        self.dE_rms = math.sqrt(self.twiss_analysis.getCorrelation(5,5))*1000.
        #---- sizes x,y,z
        self.twiss_analysis.getCorrelation
        #---- Twiss parameters for x,y,z
        twa = self.twiss_analysis
        (alpha,beta,gamma,emitt) = self.twiss_analysis.getTwiss(0)
        twissX = TwissContainer(alpha,beta,emitt)
        (alpha,beta,gamma,emitt) = self.twiss_analysis.getTwiss(1)
        twissY = TwissContainer(alpha,beta,emitt)
        (alpha,beta,gamma,emitt) = self.twiss_analysis.getTwiss(2)
        twissZ = TwissContainer(alpha,beta,emitt)
        self.twiss_arr = (twissX,twissY,twissZ)
        #------------------------------------------------------------------------
        #---- calcilation of BPM amplitude as exp(-2*pi^2*(sigma_z_deg/360)^2)
        z_rms = math.sqrt(self.twiss_analysis.getTwiss(2)[1]*self.twiss_analysis.getTwiss(2)[3])
        bunch_lambda = bunch.getSyncParticle().beta()*self.bpm_wave_lenght 
        bpm_z_rms_deg = z_rms*360./bunch_lambda
        #---- BPM frequency in SCL, HEBT = cavities frequency / 2
        self.z_rms_deg = (self.cav_frequency/self.bpm_frequency)*bpm_z_rms_deg
        self.bpm_amp = self.bpm_amp_max*math.exp(-2.0*(math.pi*(bpm_z_rms_deg/360.))**2)
        #-------------------------------------------------------------------------
        #---- calculation of time center of mass bunch shift from synch. particle
        z_avg  = self.twiss_analysis.getAverage(4)
        beta = bunch.getSyncParticle().beta()
        self.bpm_synch_part_time = bunch.getSyncParticle().time()
        delta_time_avg = z_avg/(beta*self.v_light)
        self.delta_phase = -360.0*self.bpm_frequency*delta_time_avg     
        self.bpm_bunch_center_time = self.bpm_synch_part_time - delta_time_avg
        self.model_phase = phaseNearTargetPhaseDeg(self.bpm_bunch_center_time*360.0*self.bpm_frequency,0.)
        self.model_synch_phase = phaseNearTargetPhaseDeg(self.bpm_synch_part_time*360.0*self.bpm_frequency,0.)
        #---------------------------------------------------
        self.dE_avg = self.twiss_analysis.getAverage(5)*1.0e+3
        self.dP_P = (1.0/beta**2)*self.dE_rms/((bunch.getSyncParticle().kinEnergy()+bunch.mass())*1000.)
        self.eKin = bunch.getSyncParticle().kinEnergy()*1.0e+3 + self.dE_avg
        #print ("debug name=",self.getName()," eKin=",bunch.getSyncParticle().kinEnergy()*1000.," Ldeg=",self.z_rms_deg," amp=",self.bpm_amp)
        #---------------------------------------------------
        if(self.nParticles > 0):
            self.transmission = (1.0*nParts)/self.nParticles
        else:
            self.transmission = 1.0

    def getTransmission(self):
        return self.transmission

    def getBPM_Time(self):
        return self.bpm_synch_part_time
    
    def getBPM_BunchCenterTime(self):
        return self.bpm_bunch_center_time
        
    def getBPM_Phase(self):
        """ Returns average bunch phase """
        return self.model_phase
        
    def getBPM_Synch_Phase(self):
        """ Returns synchronous partcle phase """
        return self.model_synch_phase
        
    def getRMS_Sizes(self):
        """ Returns tuple of rms for x,y, and z in mm """
        return (self.x_rms,self.y_rms,self.z_rms)
        
    def getRMS_Prime_and_dE(self):
        """ Returns tuple of rms for xp,yp, and dE in (mrad,mrad,MeV) """
        return (self.xp_rms,self.yp_rms,self.dE_rms)
        
    def get_dP_P(self):
        """ dP/P """
        return self.dP_P

    def getBunchLongSize(self):
        """
        Returns long. RMS in deg for Cavity frequency
        """
        return self.z_rms_deg

    def getCoordinates(self):
        """
        returns coordinates of the bunch center
        """
        return (self.x,self.xp,self.y,self.yp,self.model_phase,self.eKin)
        
    def get_eKin(self):
        """ Returns eKin at BPM in MeV """
        return self.eKin
        
    def dE_Kin_Avg(self):
        """ Returns <dE> in MeV for the whole bunch """
        return self.dE_avg

class ModelBPM(BunchDiagnosticNode):
    """
    BPM node as Bunch diagnostic node and connector to BPM's EPICS signals. 
    """
    def __init__(self,twiss_analysis,bpm,bpm_frequency = 402.5e+6,cav_frequency = 805.0e+6):     
        BunchDiagnosticNode.__init__(self,"none",twiss_analysis,bpm_frequency,cav_frequency)
        name = bpm.getName()
        if(name.find("BPM") <= 0): name += ":BPM"
        name += "-model"   
        self.setName(name)
        #---- bpm is a usual linac lattice marker
        self.bpm = bpm
        self.bpm_phase_offset = 0.
        self.bpm_phase_offset_err = 0.

    def getBPM(self):
        """ Returns PyORBIT BPM node - marker """
        return self.bpm
        
    def setEPICS_PhaseOffset(self,bpm_phase_offset):
        """ Sets BPM EPICS phase offset value """
        self.bpm_phase_offset = bpm_phase_offset
        
    def setEPICS_PhaseOffsetErr(self,bpm_phase_offset_err):
        """ Sets BPM EPICS phase offset error """
        self.bpm_phase_offset_err = bpm_phase_offset_err   
        
    def getEPICS_PhaseOffset(self):
        """ Returns BPM EPICS phase offset value """
        return self.bpm_phase_offset
        
    def getEPICS_PhaseOffsetErr(self):
        """ Returns BPM EPICS phase offset error """
        return self.bpm_phase_offset_err      
        
    def getModelEpicsPhase(self):
        """
        Returns BPM phase for (Model - EPICS) data comparison
        """
        return phaseNearTargetPhaseDeg(self.model_phase + self.bpm_phase_offset,0.)

    def getModelAmp(self):
        """
        Returns BPM amplitude (Fourier amp at BPM frequency)
        """
        return self.bpm_amp

    def getBPM_ModelMaxAmp(self):
        """ 
        Returns BPM's model maximal amplitudes. 
        It is maximal for the longitudinal RMS size = 0. deg
        """
        return self.bpm_amp_max
        
    def setBPM_MaxAmp(self,bpm_amp_max):
        """ 
        Sets BPM's model maximal amplitudes. 
        It is maximal for the longitudinal RMS size = 0. deg
        """        
        self.bpm_amp_max = bpm_amp_max


class ModelCavity:
    """
    Model SCL cavity to control PyORBIT accLattice cavity.
    All operations with cavity phases should be performed 
    through the getModelPhase() setModelPhase(phase).
    Phases are in degrees.
    """
    def __init__(self,cav,scl_online_model, cav_phase_polarity = +1):
        #---- ca -> PyORBIT accLattice cavity
        self.cav = cav
        self.scl_online_model = scl_online_model
        #---- Let's setup model BPMs at start and end of cavity
        rf_gaps = self.cav.getRF_GapNodes()
        twiss_analysis = self.scl_online_model.twiss_analysis
        cav_frequency = self.cav.getFrequency()
        node_pos_dict = self.scl_online_model.accLattice.getNodePositionsDict()
        self.diag_node_in = BunchDiagnosticNode(self.cav.getName()+":BDN:Entr",twiss_analysis)
        self.diag_node_in.setPosition(node_pos_dict[rf_gaps[0]][0])
        self.diag_node_out = BunchDiagnosticNode(self.cav.getName()+":BDN:Exit",twiss_analysis)
        self.diag_node_out.setPosition(node_pos_dict[rf_gaps[-1]][1])       
        rf_gaps[0].addChildNode(self.diag_node_in,AccNode.ENTRANCE)
        rf_gaps[-1].addChildNode(self.diag_node_out,AccNode.EXIT)
        self.cav_rfgap_start_ind = self.scl_online_model.accLattice.getNodeIndex(rf_gaps[0])
        self.cav_rfgap_end_ind = self.scl_online_model.accLattice.getNodeIndex(rf_gaps[-1])
        self.cav_rfgap_start_pos =  node_pos_dict[rf_gaps[0]][0]
        self.cav_rfgap_end_pos =  node_pos_dict[rf_gaps[-1]][1]
        self.cav_position = (self.cav_rfgap_start_pos + self.cav_rfgap_end_pos)/2.
        #---- Model cavity phase polarity relative to PyORBIT code cavity
        self.cav_phase_polarity = cav_phase_polarity
        #---- Model cavity phase offset relative to EPICS value 
        #---- model epics_cav_phase = model_cav_phase + cav_phase_offset
        self.cav_phase_offset = 0.
        #---- Cavity EPICS amplitude
        self.epics_cav_amp = 0.
        self.epics_cav_phase = 0.
        self.modelCoeffToEpicsAmp = 15.0
        #---- Design amplitude - model and design are the same
        self.model_cav_design_amp = self.cav.getDesignAmp()
        self.pyorbit_cav_design_amp = self.model_cav_design_amp
        self.model_cav_amp = self.model_cav_design_amp
        self.pyorbit_cav_amp = self.model_cav_amp
        #---- Blankin state
        self.cav_is_blank = False
        #---- is cavity good - if not it will not be considering working
        self.is_good = True
        
    def getName(self):
        return (self.cav.getName() + "-model")
        
    def getPosition(self):
        return self.cav_position
        
    def isGood(self,is_good = None):
        if(is_good == None): return self.is_good
        self.is_good = is_good
        if(not self.is_good):
            self.model_cav_amp = 0.
            self.setModelAmp(self.model_cav_amp)
        return self.is_good

    def setCavityModelBlanking(self,cav_is_blank):
        """
        If status of blanking is changed we will change PyORBIT cavity model amplitude
        """
        tmp_blank = self.cav_is_blank
        self.cav_is_blank = cav_is_blank
        if(tmp_blank != cav_is_blank):
            self.setModelAmp(self.model_cav_amp)
            
    def getCavityModelBlanking(self):
        return self.cav_is_blank
        
    def getBunchDiagnosticNodesInOut(self):
        return (self.diag_node_in,self.diag_node_out)
        
    def get_eKinInOut(self):
        eKinIn = self.diag_node_in.getCoordinates()[-1]
        eKinOut =  self.diag_node_out.getCoordinates()[-1]
        return (eKinIn,eKinOut)
        
    def getTimeInOut(self):
        time_in = self.diag_node_in.getBPM_Time()
        time_out = self.diag_node_out.getBPM_Time()
        return (time_in,time_out)
        
    def getStartStopInds(self):
        """ 
        Returns the lattice node indexes of start and last RF gaps in the cavity 
        """
        return (self.cav_rfgap_start_ind,self.cav_rfgap_end_ind)
        
    def updateModelCoeffToEpicsAmp(self):
        if(self.model_cav_amp > 0.):
            self.modelCoeffToEpicsAmp = self.epics_cav_amp/self.model_cav_amp
        else:
            self.modelCoeffToEpicsAmp = 15.0
        
    def getModelCoeffToEpicsAmp(self):
        return self.modelCoeffToEpicsAmp
        
    def setEPICS_CavityModelPhase(self,epics_cav_phase):
        self.epics_cav_phase = epics_cav_phase
        self.setModelPhase(phaseNearTargetPhaseDeg(self.epics_cav_phase + self.cav_phase_offset,0.))
        
    def getEPICS_CavityModelPhase(self):
        return self.epics_cav_phase

    def setCavityPhaseOffset(self,cav_phase_offset):
        self.cav_phase_offset = cav_phase_offset
        
    def getCavityPhaseOffset(self):
        return self.cav_phase_offset
        
    def getModelDesignPhase(self):
        return self.cav.getDesignPhase()*180./math.pi
        
    def getModelDesignAmp(self):
        return self.model_cav_design_amp
        
    def setModelPhase(self,phase):
        model_cav_phase = phaseNearTargetPhaseDeg(phase,0.)
        model_cav_phase *= self.cav_phase_polarity
        self.cav.setPhase(model_cav_phase*math.pi/180.)
        
    def getModelPhase(self):
        phase = self.cav.getPhase()
        phase *= self.cav_phase_polarity
        phase = phaseNearTargetPhaseDeg(phase*180./math.pi,0.)
        return phase
        
    def setModelAmp(self,model_cav_amp):
        self.model_cav_amp = model_cav_amp
        if(self.cav_is_blank):
            self.cav.setAmp(0.)
            return
        self.cav.setAmp(model_cav_amp)
        
    def getModelAmp(self):
        if(self.cav_is_blank):
            self.cav.setAmp(0.)
            return 0.       
        if(abs(self.cav.getAmp() - self.model_cav_amp) > 0.00001):
            self.model_cav_amp = self.cav.getAmp()
        return self.cav.getAmp()        

    def getPyOrbitCavity(self):
        return self.cav 
        
    def getCavityExitPosition(self):
        return self.cav_rfgap_end_pos
        
    def trackEmptyBunch(self,eKinIn, cavEPICS_PhaseArr):
        """
        It returns (eKinOut_arr,timeOut_arr) 
        for each cavity phase in cavEPICS_PhaseArr.
        eKin in MeV, phases in degrees
        """
        bunch_in = get_SCL_EmptyBunch(eKinIn)
        eKinOut_arr = []
        timeOut_arr = []
        epics_model_cav_phase_init = self.getEPICS_CavityModelPhase()
        for cav_epics_phase in cavEPICS_PhaseArr:
            self.setEPICS_CavityModelPhase(cav_epics_phase)
            ind_start = self.cav_rfgap_start_ind
            ind_stop = self.cav_rfgap_end_ind
            bunch = self.scl_online_model.trackDesignBunch(bunch_in,ind_start,ind_stop)
            eKinOut = bunch.getSyncParticle().kinEnergy()*1000.
            tm = bunch.getSyncParticle().time()
            eKinOut_arr.append(eKinOut)
            timeOut_arr.append(tm)
        #---- Restore the EPICS model cavity phase after scan
        self.setEPICS_CavityModelPhase(epics_model_cav_phase_init)
        return (eKinOut_arr,timeOut_arr)
        
class TrackingResults:
    """
    It keeps the results of bunch tracking through the accelerator lattice.
    """
    def __init__(self,accLattice,start_node_ind,end_node_ind,twiss_analysis):
        self.accLattice = accLattice
        self.start_node_ind = start_node_ind
        self.end_node_ind = end_node_ind
        self.twiss_analysis = twiss_analysis
        #---- resulting functions of postions along the lattice
        #---- RMS sizes [x,y,z] - x,y in mm , z in deg for 805 MHz
        self.rms_size_arr = [Function(),Function(),Function()]
        #---- Twiss params [alpha, beta, emitt] x,y - mm, mm*mrad, z - deg,deg*MeV 
        self.x_twiss_params = [Function(),Function(),Function()]
        self.y_twiss_params = [Function(),Function(),Function()]
        self.z_twiss_params = [Function(),Function(),Function()]
        self.twiss_params_arr = [self.x_twiss_params,self.y_twiss_params,self.z_twiss_params]
        #---- Synchrotron phase advances in deg
        self.phase_adv_arr = [Function(),Function(),Function()]
        #---- energy 
        self.energy_func = Function()
        #---- N parts
        self.nparticles_func = Function()
        #---- RF frequency Hz
        self.rf_frequency = 805.0e+6
        
    def addPoint(self,pos,bunch):
        pos_old = pos
        n_points = self.energy_func.getSize()
        if(n_points > 1):
            pos_old = self.energy_func.x(n_points - 2)
        self.twiss_analysis.analyzeBunch(bunch)
        gamma = bunch.getSyncParticle().gamma()
        beta = bunch.getSyncParticle().beta()
        eKin = bunch.getSyncParticle().kinEnergy()
        self.energy_func.add(pos,eKin*1.0e+3)
        twa = self.twiss_analysis
        nParts = twa.getGlobalCount()
        self.nparticles_func.add(pos,nParts*1.0)
        #------------------------------
        (alphaX, betaX, gammaX, emittX) = twa.getTwiss(0)
        (alphaY, betaY, gammaY, emittY) = twa.getTwiss(1)
        (alphaZ, betaZ, gammaZ, emittZ) = twa.getTwiss(2)
        self.x_twiss_params[0].add(pos,alphaX)      
        self.x_twiss_params[1].add(pos,betaX)
        self.x_twiss_params[2].add(pos,emittX*1.0e+6)
        self.y_twiss_params[0].add(pos,alphaY)      
        self.y_twiss_params[1].add(pos,betaY)
        self.y_twiss_params[2].add(pos,emittY*1.0e+6)
        self.z_twiss_params[0].add(pos,alphaZ)      
        self.z_twiss_params[1].add(pos,betaZ)
        self.z_twiss_params[2].add(pos,emittZ*1.0e+6)
        #-------------------------------
        rms_x = math.sqrt(twa.getCorrelation(0,0))*1000.
        rms_y = math.sqrt(twa.getCorrelation(2,2))*1000.
        rms_z = math.sqrt(twa.getCorrelation(4,4))
        rms_deg_z = 360.0*rms_z/((speed_of_light*beta)/self.rf_frequency)
        self.rms_size_arr[0].add(pos,rms_x)
        self.rms_size_arr[1].add(pos,rms_y)
        self.rms_size_arr[2].add(pos,rms_deg_z)
        #---------------------------------
        delta_s = pos - pos_old
        for dir_ind in range(3):
            beta_val = betaX
            if(dir_ind == 1): beta_val = betaY
            if(dir_ind == 2): beta_val = betaZ
            ind_last = self.phase_adv_arr[dir_ind].getSize() - 1
            val0 = self.phase_adv_arr[dir_ind].y(ind_last)
            val1 = val0 + (180./math.pi)*delta_s/beta_val
            val1 = phaseNearTargetPhaseDeg(val1,0.)
            self.phase_adv_arr[dir_ind].add(pos,val1)
        
    def getTwissFunc(self,ind):
        """ ind = 0,1,2 for x,y,z  Values (alph,beta,emitt) """
        return self.twiss_params_arr[ind]
        
    def getRMS_Func(self,ind):
        """ ind = 0,1,2 for x,y,z """
        return self.rms_size_arr[ind]
        
    def getPhaseAdvFunc(self,ind):
        """ ind = 0,1,2 for x,y,z """
        return self.phase_adv_arr[ind]

class SCL_Online_Model:
    """
    This is a front end of the SNS SCL Linac PyORBIT model. This will be used
    for analysis of SCL phase scan data.
    """
    def __init__(self,acc_da, seq_names = ["SCLMed","SCLHigh","HEBT1","HEBT2"], z_step = 0.01):
        self.acc_da = acc_da
        self._seq_names = seq_names
        self.z_step = z_step
        # ---- create the factory instance
        self.sns_linac_factory = SNS_LinacLatticeFactory()
        self.sns_linac_factory.setMaxDriftLength(z_step)        
        self.accLattice = self.sns_linac_factory.getLinacAccLatticeFromDA(self._seq_names,self.acc_da)
        #---- Twiss Analysis for BPMs
        self.twiss_analysis = BunchTwissAnalysis()
        self.bpm_twiss_analysis = BunchTwissAnalysis()
        #---- Let's make LWs nodes
        lw_nodes = self.accLattice.getNodesForSubstring("LW","drift")
        lw_nodes += self.accLattice.getNodesForSubstring("HEBT_Diag:EMS_X","drift")
        self.lw_diag_node_arr = []
        for node in lw_nodes:
            name = node.getName().replace("_Diag","")
            if(name.find("HEBT") >= 0): name = "HEBT:LW10"
            node.setName(name)
            model_diag_node = BunchDiagnosticNode(node.getName()+":BDN",self.bpm_twiss_analysis)
            pos = self.accLattice.getNodePositionsDict()[node][0]
            model_diag_node.setPosition(pos)
            self.lw_diag_node_arr.append(model_diag_node)
            node.addChildNode(model_diag_node,AccNode.ENTRANCE)
            #print ("debug lw node =",name," pos=",pos)
        #---- Let's get BPMs
        (self.bpms,self.bpm_pos_dict) = getBPM_Position_Dict(self.accLattice)
        self.model_bpms = []
        self.bpm_name_dict = {}
        for bpm in self.bpms:
            model_bpm = ModelBPM(self.bpm_twiss_analysis,bpm)
            model_bpm.setPosition(bpm.getPosition())
            bpm.addChildNode(model_bpm,AccNode.ENTRANCE)
            self.model_bpms.append(model_bpm)
            self.bpm_name_dict[bpm.getName()] = model_bpm
            #print ("debug bpm =",model_bpm.getName()," pos=",model_bpm.getPosition())
        #---- Lets get quads
        self.quads = self.accLattice.getNodesOfClass(Quad)
        #---------------------------------------------------------------
        # ----set up RF Gap Model -------------
        # ---- There are three available models at this moment
        # ---- BaseRfGap  uses only E0TL*cos(phi)*J0(kr) with E0TL = const
        # ---- MatrixRfGap uses a matrix approach like envelope codes
        # ---- RfGapTTF uses Transit Time Factors (TTF) like PARMILA
        # cppGapModel = BaseRfGap_slow
        # cppGapModel = MatrixRfGap_slow
        # cppGapModel = RfGapTTF_slow
        # cppGapModel = BaseRfGap
        # cppGapModel = MatrixRfGap
        cppGapModel = RfGapTTF
        self.rf_gaps = self.accLattice.getRF_Gaps()
        for rf_gap in self.rf_gaps:
                rf_gap.setCppGapModel(cppGapModel())
        #---- RF Cavities
        self.cavs = self.accLattice.getRF_Cavities()
        self.model_cavs = []
        self.cav_name_dict = {}
        for cav in self.cavs:
            model_cav = ModelCavity(cav,self,cav_phase_polarity = +1)
            self.model_cavs.append(model_cav)
            self.cav_name_dict[cav.getName()] = model_cav
        #---- Set up Space Charge Acc Nodes as niformly charged ellipses 
        sc_path_length_min = 0.05
        nEllipses = 1
        calcUnifEllips = SpaceChargeCalcUnifEllipse(nEllipses)
        self.space_charge_nodes = setUniformEllipsesSCAccNodes(self.accLattice, sc_path_length_min, calcUnifEllips)
        self.sc_switcherOn = False
        for sc_node in self.space_charge_nodes:
            sc_node.setCalculationOn(self.sc_switcherOn)
        #---------------------------------------------------------------
        #---- twiss = (alpha, beta, emitt) - all values are approximate
        twissX = TwissContainer(-1.68 , 7.14, 0.4686e-6)
        twissY = TwissContainer(0.1734, 8.69, 0.3050e-6)
        twissZ = TwissContainer(0.2315,10.57, 0.3943e-6)
        self.twissArr = (twissX,twissY,twissZ)
        self.eKinIn = 185.629289
    
    def filterOutBadBPMs(self,bad_bpm_names = []):
        """
        Clean up bad BPMs that we are sure about.
        """
        if(len(bad_bpm_names) == 0): return
        if(len(self.bpms) != len(self.model_bpms)):
            print ("========== SCL_Online_Model class method : filterOutBadBPMs() ")
            print ("Number of BPMs and Model_BPMs are different!")
            print ("N BPMs   = ",self.bpms)
            print ("N Models = ",len(self.model_bpms))
            print ("Stop.")
            sys.exit(1)
        #----------------------------------------
        bpms = []
        model_bpms = []
        for bpm_ind,bpm in enumerate(self.bpms):
            if(not bpm.getName() in bad_bpm_names):
                bpms.append(bpm)
                model_bpms.append(self.model_bpms[bpm_ind])
        self.bpms = bpms
        self.model_bpms = model_bpms

    def getCopyOM(self):
        scl_om = SCL_Online_Model(self.getCopyLatticeDA(),self.getSeqNames(),self.z_step)
        return scl_om
        
    def getSeqNames(self):
        """ Returns the list of sequence names in the OM. """
        return self._seq_names[:]
        
    def getCopyLatticeDA(self):
        """ 
        Returns a copy of XML Data Adaptor instance with 
        the accelerator lattice.
        """
        return self.acc_da.getDeepCopy()
        
    def setSpaceChargeOn(self,sc_switcherOn):
        """ Use or not Space Charge effects """
        self.sc_switcherOn = sc_switcherOn
        for sc_node in self.space_charge_nodes:
            sc_node.setCalculationOn(sc_switcherOn)
            
    def getSpaceChargeOn(self):
        return self.sc_switcherOn
        
    def getBunchTwissAnalysis(self):
        return self.twiss_analysis
        
    def getBunch(self, twissArr, nParticles = 1000, peakCurr = 0., eKin = 185.629289, cav_frequency = 805.0e+6):
        """
        Returns bunch instance.
        twissArr = (twissX,twissY,twissZ) , peakCurr in [mA], eKin in [MeV], cav_frequency in [MHz]
        twiss = TwissContainer(alpha,beta,emitt)
        """
        bunch_generator = SNS_Linac_BunchGenerator(twissArr[0],twissArr[1],twissArr[2],cav_frequency,cav_frequency)
        bunch_generator.setKinEnergy(eKin/1000.)
        bunch_generator.setBeamCurrent(peakCurr)
        bunch = bunch_generator.getBunch(nParticles)
        return bunch
        
    def eKin_In(self):
        return self.eKinIn
        
    def getTwissArr(self):
        return self.twissArr
        
    def getLW_DiagNodes(self):
        return self.lw_diag_node_arr
        
    def getModelBPMs(self):
        return self.model_bpms
        
    def getModelCavs(self):
        return self.model_cavs
        
    def getPyOrbitQuads(self):
        return self.quads
        
    def getPyOrbitRF_Gaps(self):
        return self.rf_gaps 
        
    def getModelCavity(self,pyorbit_cav_name):
        """ Returns model-cavity for PyOrbit name """
        if(pyorbit_cav_name not in self.cav_name_dict): return None
        return self.cav_name_dict[pyorbit_cav_name]
        
    def getModelBPM(self,pyorbit_bpm_name):
        """ Returns model-bpm for PyOrbit name """
        if(pyorbit_bpm_name not in self.bpm_name_dict): return None
        return self.bpm_name_dict[pyorbit_bpm_name]
        
    def trackBunch(self,bunch,node_start_ind = -1,node_stop_ind = -1):
        self.accLattice.trackBunch(bunch,None,None,node_start_ind,node_stop_ind)
        return bunch
        
    def trackDesignBunch(self,bunch,node_start_ind = -1,node_stop_ind = -1):
        bunch = self.accLattice.trackDesignBunch(bunch,None,None,node_start_ind,node_stop_ind)
        return bunch
        
    def trackSizeAndTwiss(self,bunch,node_start_ind = -1,node_stop_ind = -1, step = 0.01):
        """ Calculates beam rms sizes, Twiss, and synchrotron phase advances """
        trackingRes = TrackingResults(self.accLattice,node_start_ind,node_stop_ind,self.twiss_analysis)
        pos_start = 0.
        if(node_start_ind >= 0):
            node = self.accLattice.getNodes()[node_start_ind]
            pos_start = pos = self.accLattice.getNodePositionsDict()[node][0]
        paramsDict = {"old_pos": -1.0, "count": 0, "pos_step":step, "pos_start_tracking":pos_start}
        actionContainer = AccActionsContainer("Sizes & Twiss of Bunch Tracking")
        #-------------
        def action_entrance(paramsDict):
            node = paramsDict["node"]
            bunch = paramsDict["bunch"]
            pos = paramsDict["path_length"]
            if paramsDict["old_pos"] == pos:
                return
            if paramsDict["old_pos"] + paramsDict["pos_step"] > pos:
                return
            paramsDict["old_pos"] = pos
            trackingRes.addPoint(pos+paramsDict["pos_start_tracking"],bunch)
        #-------------
        def action_exit(paramsDict):
            action_entrance(paramsDict)
        #-------------
        actionContainer.addAction(action_entrance, AccActionsContainer.ENTRANCE)
        actionContainer.addAction(action_exit, AccActionsContainer.EXIT)    
        #-------------
        self.accLattice.trackBunch(bunch,paramsDict,actionContainer,node_start_ind,node_stop_ind)
        return trackingRes
                
    def setUpSynchPhases(self,bunch_start,model_cavs,cav_synch_phase_dict):
        """
        It will setup synchronous phase of selected cavities 
        to the values in the dictionary.
        cav_synch_phase_dict[model_cav.cav.getName()] = synch_phase
        It returns the new caviies synchronous phases.
        """
        bunch = Bunch()
        bunch_start.copyBunchTo(bunch)
        bunch.deleteAllParticles()
        bunch_tmp = bunch
        if(len(model_cavs) == 0): return
        model_cavs = sorted(model_cavs, key=lambda  model_cav: model_cav.getPosition())
        cav_start_ind = self.model_cavs.index(model_cavs[0])
        cav_stop_ind = self.model_cavs.index(model_cavs[-1])
        cav_synch_phase_dict = dict(cav_synch_phase_dict)
        for model_cav_ind in range(cav_start_ind,cav_stop_ind+1):
            model_cav = self.model_cavs[model_cav_ind]
            (latt_ind_start,latt_ind_stop) = model_cav.getStartStopInds()
            if(model_cav_ind != cav_stop_ind):
                latt_ind_stop = self.model_cavs[model_cav_ind+1].getStartStopInds()[0] - 1
            bunch = Bunch()
            bunch_tmp.copyBunchTo(bunch)
            #print ("debug eKin_in =",bunch.getSyncParticle().kinEnergy()*1.0e+3)
            self.trackBunch(bunch,latt_ind_start,latt_ind_stop)
            cav_epics_phase = model_cav.getEPICS_CavityModelPhase()
            synch_phase = phaseNearTargetPhaseDeg(model_cav.cav.getAvgGapPhase()*180./math.pi - 180,0.)
            (eKinIn_tmp,eKinout) = model_cav.get_eKinInOut()
            #print ("debug =============== cav = ",model_cav.cav.getName())
            #st  = "debug "
            #st += " phase (epics,synch)=(%+7.2f,%+7.2f)"%(cav_epics_phase,synch_phase)
            #st += " eKin(In,Out)=(%8.3f,%8.3f)"%(eKinIn_tmp,eKinout)
            #print (st)     
            if(not model_cav.cav.getName() in cav_synch_phase_dict):
                cav_synch_phase_dict[model_cav.cav.getName()] = synch_phase
            #---- calculate difference between target synch. phase and existing one and fix EPICS phase
            diff = phaseNearTargetPhaseDeg(cav_epics_phase - synch_phase,0.)
            synch_phase_target = cav_synch_phase_dict[model_cav.cav.getName()]
            cav_epics_phase = phaseNearTargetPhaseDeg(synch_phase_target + diff,0.)
            model_cav.setEPICS_CavityModelPhase(cav_epics_phase)
            bunch = Bunch()
            bunch_tmp.copyBunchTo(bunch)
            self.trackBunch(bunch,latt_ind_start,latt_ind_stop)
            (eKinIn_tmp,eKinout) = model_cav.get_eKinInOut()
            synch_phase = phaseNearTargetPhaseDeg(model_cav.cav.getAvgGapPhase()*180./math.pi - 180,0.)
            #st  = "debug "
            #st += " phase (epics,synch)=(%+7.2f,%+7.2f)"%(cav_epics_phase,synch_phase)
            #st += " eKin(In,Out)=(%8.3f,%8.3f)"%(eKinIn_tmp,eKinout)
            #print (st)
            #print ("debug ===============")
            #---- now the bunch will be the input bunch for the next cavity
            bunch_tmp = bunch
        #---- after we set all cavities we can collect new synch phases
        for model_cav_ind in range(cav_start_ind,cav_stop_ind+1):
            model_cav = self.model_cavs[model_cav_ind]
            synch_phase = phaseNearTargetPhaseDeg(model_cav.cav.getAvgGapPhase()*180./math.pi -180.,0.)
            cav_synch_phase_dict[model_cav.cav.getName()] = synch_phase
            #print ("debug ==== cav = ",model_cav.cav.getName()," synch phase= %+8.3f"%synch_phase)
        #---- new synch. phases dict
        return cav_synch_phase_dict             

        
if __name__ == '__main__':
    
    #==================================================
    #    START of Test SCRIPT
    #==================================================
    
    print("============================== START ==============================")
    #---- Let's read the SNS Linac lattice XML file
    xml_lattice_file_name = "./../sns_lattices/sns_sts_linac.xml"
    acc_da = XmlDataAdaptor.adaptorForFile(xml_lattice_file_name)
    
    seq_names = ["CCL4","SCLMed", "SCLHigh", "HEBT1", "HEBT2"]
    
    #---- Test is we can create Online Model
    model = SCL_Online_Model(acc_da,seq_names)
    
    print ("Stop.")
    sys.exit(0)