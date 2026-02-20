#--------------------------------------------
class BPMsScanDataSet:
    """
    This class keeps measured, during phase scan of particular SCL cavity,
    BPMs' phase and amplitude, and x_avg and y_avg beam parameters as
    functions of the cavity phase.
    """
    def __init__(self,scl_cavity_scan_data,om_model,scl_wizard_scan_reader):
        self.scl_cavity_scan_data = scl_cavity_scan_data
        self.model_cav = self.scl_cavity_scan_data.model_cav
        self.om_model = om_model
        #---- BPMs
        self.model_bpms = []
        for model_bpm in self.om_model.getModelBPMs():
            if(model_bpm.getPosition() > self.model_cav.getPosition()):
                self.model_bpms.append(model_bpm)
        self.bpm_epics_phases = []
        self.bpm_epics_fit_phases = []
        self.bpm_fit_phases_err = []
        self.bpm_epics_amps = []
        self.bpm_epics_Xs = []
        self.bpm_epics_Ys = []
        self.bpms_status = []
        self.bpm_name_to_ind_dict = {}
        for bpm_ind,model_bpm in enumerate(self.model_bpms):
            self.bpms_status.append(False)
            self.bpm_epics_phases.append(Function())
            self.bpm_epics_fit_phases.append(Function())
            self.bpm_fit_phases_err.append(0.)
            self.bpm_epics_amps.append(Function())
            self.bpm_epics_Xs.append(Function())
            self.bpm_epics_Ys.append(Function())
            self.bpm_name_to_ind_dict[model_bpm.bpm.getName()] = bpm_ind
        #-----------------------------------------
        #---- cav_wrapper keeps SCL Wizard data about scan
        pyorbit_cav_name = self.model_cav.getPyOrbitCavity().getName()
        self.cav_wrapper = scl_wizard_scan_reader.getCavityWrapperDict()[pyorbit_cav_name]
        self.n_good_bpms = 0
        for bpm_ind,model_bpm in enumerate(self.model_bpms):
            nPoints = self.cav_wrapper.getNumberPhasePoints(model_bpm.bpm.getName())
            if(nPoints == 0):
                self.bpms_status[bpm_ind] = False
                continue
            else:
                self.bpms_status[bpm_ind] = True
                self.n_good_bpms += 1
            cav_phase_arr = self.cav_wrapper.getCavity_PhaseArr(model_bpm.bpm.getName())
            bpm_phase_arr = self.cav_wrapper.getBPM_PhaseArr(model_bpm.bpm.getName())
            bpm_amp_arr   = self.cav_wrapper.getBPM_AmpArr(model_bpm.bpm.getName())
            bpm_x_arr     = self.cav_wrapper.getBPM_X_Arr(model_bpm.bpm.getName())
            bpm_y_arr     = self.cav_wrapper.getBPM_Y_Arr(model_bpm.bpm.getName())
            self.bpm_epics_phases[bpm_ind].initFromLists(cav_phase_arr,bpm_phase_arr)
            self.bpm_epics_amps[bpm_ind].initFromLists(cav_phase_arr,bpm_amp_arr)
            self.bpm_epics_Xs[bpm_ind].initFromLists(cav_phase_arr,bpm_x_arr)
            self.bpm_epics_Ys[bpm_ind].initFromLists(cav_phase_arr,bpm_y_arr)
        #----------------------------------------
        if(self.n_good_bpms == 0):
            scl_cavity_scan_data.cavitySatus(False)
        #----------------------------------------
        #---- self.cos_fit_bpm_amp - has amplitudes of cos fitting of BPMs' data
        self.bpm_amp_fit_func = Function()
        #---- The slope and zero-crosssing position for bpm_amp_fit_func
        #---- bpm_amp_slope in [deg/meter] zero_cross_pos in [meters]
        self.bpm_amp_slope = 0.
        self.zero_cross_pos = 0.
        self.bpm_amp_slope_err = 0.
        self.zero_cross_pos_err = 0.        
        #---- bpm_phase_avg as avg_phase in cos analysis
        self.bpm_phase_avg = []
        for model_bpm in self.model_bpms:
            self.bpm_phase_avg.append(0.)
        #---- average and error cavity phase offset in 
        #---- math.cos(phase - 180 + cav_phase_offset)
        self.cos_fit_cav_phase_offset = 0.
        self.cos_fit_cav_phase_offset_err = 0.

    def cleanBPMsMinAmp(self,min_amp = 1.0):
        """ 
        This method put status of BPM data in False if the BPM amplitude
        is too small.
        """
        self.n_good_bpms = 0
        for bpm_ind,model_bpm in enumerate(self.model_bpms):
            if(not self.bpms_status[bpm_ind]): continue
            min_amp_in_epics = self.bpm_epics_amps[bpm_ind].getMinY()
            if(min_amp_in_epics < min_amp):
                self.bpms_status[bpm_ind] = False
                self.bpm_epics_phases[bpm_ind].clean()
                self.bpm_epics_amps[bpm_ind].clean()
                self.bpm_epics_Xs[bpm_ind].clean()
                self.bpm_epics_Ys[bpm_ind].clean()
            else:
                self.n_good_bpms += 1
        if(self.n_good_bpms == 0):
                self.scl_cavity_scan_data.cavitySatus(False)
                
    def getListOfGoodBPMs(self):
        good_model_bpms = []
        if(not self.scl_cavity_scan_data.cavitySatus()): return good_model_bpms
        for bpm_ind,model_bpm in enumerate(self.model_bpms):
            if(not self.bpms_status[bpm_ind]): continue
            good_model_bpms.append(model_bpm)
        return good_model_bpms              
        
    def getNumberOfPoints(self,pyorbit_bpm_name):
        """ Phase scan points for particular BPM """
        bpm_ind = self.bpm_name_to_ind_dict[pyorbit_bpm_name]
        function = self.bpm_epics_phases[bpm_ind]
        return function.getSize()       

    def cosAnalysisAllBPms(self, print_info = False):
        self.bpm_amp_fit_func.clean()
        cav_phase_offset_arr = []
        cav_pos = self.model_cav.getPosition()
        if(print_info):
            st  = "bpm             pos[m]    bpm_phase_amp[deg]  cav.offset[deg]"
            st += "   bpm_avg_phase[deg]  fit_err[%]"
            print (st)
        for bpm_ind,model_bpm in enumerate(self.model_bpms):
            if(not self.bpms_status[bpm_ind]): continue
            func_in = self.bpm_epics_phases[bpm_ind]
            func_fit = self.bpm_epics_fit_phases[bpm_ind]
            (bpm_phase_amp,cav_phase_offset,avg_bpm_phase_val) = fitCosineFunc(func_in,func_fit)
            avg_bpm_phase_val = phaseNearTargetPhaseDeg(avg_bpm_phase_val,0.)
            bpm_pos = model_bpm.getPosition()
            #---- Let's calculate average cos fit error 
            avg_err2 = 0.
            for cav_phase_ind in range(func_in.getSize()):
                avg_err2 += (func_in.y(cav_phase_ind) -func_fit.y(cav_phase_ind))**2
            if(func_in.getSize() > 0): avg_err2/func_in.getSize()
            self.bpm_fit_phases_err[bpm_ind] = 100.*math.sqrt(avg_err2)/bpm_phase_amp
            #------------------------------------------
            if(bpm_pos < cav_pos): continue
            self.bpm_amp_fit_func.add(bpm_pos,bpm_phase_amp)
            self.bpm_phase_avg[bpm_ind] = avg_bpm_phase_val
            cav_phase_offset_arr.append(phaseNearTargetPhaseDeg(cav_phase_offset,0.))
            if(print_info):
                st  = " %+10s "%(model_bpm.getBPM().getName().replace("_Diag","")) + " "
                st += " %8.3f "%bpm_pos + " "
                st += " %8.2f "%bpm_phase_amp + " "
                st += " %+7.2f "%cav_phase_offset + " "
                st += " %+8.2f "%avg_bpm_phase_val
                st += "   %4.2f "%self.bpm_fit_phases_err[bpm_ind]
                print (st)
        (cav_phase_offset,cav_phase_offset_err) = calculateAvgErr(cav_phase_offset_arr)
        self.cos_fit_cav_phase_offset = cav_phase_offset
        self.cos_fit_cav_phase_offset_err = cav_phase_offset_err
        if(print_info):
            st  = "Cavity phase offset[deg] = "
            st += "%8.3f +- %8.3f"%(cav_phase_offset,cav_phase_offset_err)
            print (st)
        polyFit = PolynomialFit(1)
        polyFit.fitFunction(self.bpm_amp_fit_func)
        [coef_arr, err_arr] = polyFit.getCoefficientsAndErr()
        #print ("debug (base , coeff*pos) = ",[coef_arr, err_arr])
        coef_arr[0] /= -coef_arr[1]
        err_arr[0]  /= abs(coef_arr[1])
        self.bpm_amp_slope = coef_arr[1]
        self.zero_cross_pos = coef_arr[0]
        self.bpm_amp_slope_err = err_arr[1]
        self.zero_cross_pos_err = err_arr[0]            
        #print ("debug (pos -pos0)*coeff = ",[coef_arr, err_arr])
        if(print_info):
            st  = "=== BPM Amplitude vs. Position Linear Fit ==="
            st += "\n"
            st += "Slope  deg/m]= %+10.6f +- %10.6f "%(self.bpm_amp_slope,self.bpm_amp_slope_err)
            st += "\n"
            st += "Cross.Pos.[m]= %+10.6f +- %10.6f "%(self.zero_cross_pos,self.zero_cross_pos_err)
            st += "\n"
            st += "Cav. Pos. [m]= %+10.6f"%cav_pos
            print (st)
            
    def getCosBPM_PhaseAmp(self, position):
        """ 
        Returns A_Phase parameter for A_Phase*cos(cav_pahse + offset) 
        for different BPM positions.
        """
        return self.bpm_amp_fit_func.getY(position)
            
    def cavityParamsGuess(self,eKinIn,goodBPM_ind = -1):
        """
        Let's estimate E0TL and phase offset of the cavity 
        based only on one BPM phases.
        """
        mass = 939.294   #---- H- mass
        Etotal = eKinIn + mass
        momentum = math.sqrt(Etotal**2 - mass**2)
        beta = momentum/Etotal
        gamma = Etotal/mass
        model_bpm = self.getListOfGoodBPMs()[goodBPM_ind]
        bpm_frequency = model_bpm.getFrequencyBPM()
        c = speed_of_light
        bpm_amp_slope_radian = self.bpm_amp_slope*math.pi/180.
        E0TL = mass*beta**3*gamma**3*(c/(2*math.pi*bpm_frequency))*bpm_amp_slope_radian
        #print ("debug eKinIn   [MeV]= %+10.6f "%eKinIn)
        #print ("debug E0TL     [MeV]= %+10.6f "%E0TL)
        #print ("debug model cav_offset = ",self.model_cav.getCavityPhaseOffset())
        #---- Let's estimate PyORBIT cavity amplitude using E0TL and input energy
        bpm_ind = self.bpm_name_to_ind_dict[model_bpm.bpm.getName()]
        bpm_phase_func = self.bpm_epics_phases[bpm_ind]         
        bpm_pos = model_bpm.getPosition() 
        (cav_phase_arr,bpm_phase_arr,err_arr) = bpm_phase_func.getXYErrLists()
        (eKinOut_arr,timeOut_arr) = self.model_cav.trackEmptyBunch(eKinIn,cav_phase_arr)
        eKin_scan_func = Function()
        eKin_scan_func.initFromLists(cav_phase_arr,eKinOut_arr)
        func_fit = Function()
        (eKin_amp,eKin_min_phase_offset,avg_eKin_val) = fitCosineFunc(eKin_scan_func,func_fit)
        eKin_max_phase_offset = phaseNearTargetPhaseDeg(eKin_min_phase_offset + 180.,0.)
        
        """
        print ("debug eKin min phase offset=",eKin_min_phase_offset)
        print ("debug eKin max phase offset=",eKin_max_phase_offset)
        print ("debug eKin_amp=",eKin_amp)
        print (" CavPhaseEPICS BPM_Phase  eKinOutGuess eKinOutCosFit eKinDiff ")
        for ind in range(func_fit.getSize()):
            st  = " %+6.1f  "%func_fit.x(ind)
            st += " %8.3f   "%bpm_phase_func.y(ind)
            st += " %8.3f   %8.3f "%(eKin_scan_func.y(ind),func_fit.y(ind))
            st += " %8.5f "%(eKin_scan_func.y(ind) - func_fit.y(ind))
            print (st)
        """
        
        cav_amp_coeff = E0TL/eKin_amp
        self.model_cav.setModelAmp(self.model_cav.getModelAmp()*cav_amp_coeff)
        model_cav_phase_offset = phaseNearTargetPhaseDeg(self.cos_fit_cav_phase_offset - eKin_max_phase_offset,0.)
        self.model_cav.setCavityPhaseOffset(model_cav_phase_offset)

        """
        print ("debug model_cav_phase_offset=",model_cav_phase_offset)
        #---- let's check how we are doing
        print ("debug ----- Let's see how good we are after guessing ------------")
        (eKinOut_arr,timeOut_arr) = self.model_cav.trackEmptyBunch(eKinIn,cav_phase_arr)
        eKin_scan_func = Function()
        eKin_scan_func.initFromLists(cav_phase_arr,eKinOut_arr)
        func_fit = Function()
        (eKin_amp,eKin_min_phase_offset,avg_eKin_val) = fitCosineFunc(eKin_scan_func,func_fit)
        eKin_max_phase_offset = phaseNearTargetPhaseDeg(eKin_min_phase_offset + 180.,0.)
        print ("debug eKin min phase offset=",eKin_min_phase_offset)
        print ("debug eKin max phase offset=",eKin_max_phase_offset)
        print ("debug eKin_amp=",eKin_amp)
        print (" CavPhaseEPICS BPM_Phase  eKinOutGuess eKinOutCosFit eKinDiff ")
        for ind in range(func_fit.getSize()):
            st  = " %+6.1f  "%func_fit.x(ind)
            st += " %8.3f   "%bpm_phase_func.y(ind)
            st += " %8.3f   %8.3f "%(eKin_scan_func.y(ind),func_fit.y(ind))
            st += " %8.5f "%(eKin_scan_func.y(ind) - func_fit.y(ind))
            print (st)
        print ("============== now compare bpm phases =============")
        self.makeModelBPM_Phases(eKinIn,model_bpm)
        """
        
    def makeModelBPM_Phases(self,eKinIn,model_bpm):
        """
        eKinOut_arr - model eKinOut vs. cavity phase
        timeOut_arr - model exit time out of cavity vs. cavity phase
        """
        mass = 939.294   #---- H- mass
        c = speed_of_light
        cav_exit_pos = self.model_cav.getCavityExitPosition()
        bpm_pos = model_bpm.getPosition()
        bpm_frequency = model_bpm.getFrequencyBPM()
        dist = bpm_pos - cav_exit_pos
        #-------------------
        bpm_ind = self.bpm_name_to_ind_dict[model_bpm.bpm.getName()]
        bpm_phase_func = self.bpm_epics_phases[bpm_ind]         
        (cav_phase_arr,bpm_phase_arr,err_arr) = bpm_phase_func.getXYErrLists()
        (eKinOut_arr,timeOut_arr) = self.model_cav.trackEmptyBunch(eKinIn,cav_phase_arr)    
        #--------------------
        model_bpm_phase_arr = []
        avg_bpm_phase_diff = 0.
        n_cav_phases = len(cav_phase_arr)
        for ind in range(n_cav_phases):
            eKin = eKinOut_arr[ind] 
            Etotal = eKin + mass
            momentum = math.sqrt(Etotal**2 - mass**2)
            beta = momentum/Etotal
            tm_bpm = timeOut_arr[ind]  + dist/(beta*c)
            bpm_phase = bpm_phase_arr[ind]
            model_bpm_phase = 360*tm_bpm*bpm_frequency
            model_bpm_phase_arr.append(model_bpm_phase)
            #print ("debug 1st cav. phase= %+6.1f "%cav_phase_arr[ind]," bpm model epics =  %+8.1f  %+8.1f "%(model_bpm_phase,bpm_phase))
            avg_bpm_phase_diff += model_bpm_phase - bpm_phase
        if(n_cav_phases > 0): avg_bpm_phase_diff /= n_cav_phases
        #print ("debug avg_bpm_phase_diff = ",avg_bpm_phase_diff)
        sum_diff2 = 0.
        for ind in range(n_cav_phases):
            bpm_phase = bpm_phase_arr[ind]
            model_bpm_phase = model_bpm_phase_arr[ind]
            model_bpm_phase = model_bpm_phase - avg_bpm_phase_diff
            model_bpm_phase_arr[ind] = model_bpm_phase
            #print ("debug 2nd cav. phase= %+6.1f "%cav_phase_arr[ind]," bpm model epics =  %+8.1f  %+8.1f "%(model_bpm_phase,bpm_phase))
            sum_diff2 += ( model_bpm_phase - bpm_phase)**2
        if(n_cav_phases > 0): sum_diff2 /= n_cav_phases
        #print ("debug avg diff = %10.3g"%math.sqrt(sum_diff2))
        #print ("debug cav_exit_pos=",cav_exit_pos," bpm_pos=",bpm_pos)
        #print ("debug eKinOut_arr=",eKinOut_arr)
        #print ("debug timeOut_arr=",timeOut_arr)
        #sys.exit(0)
        return (sum_diff2,model_bpm_phase_arr)

    def cavityParamsFitting(self,eKinIn,goodBPM_ind = -1):
        scorer = CavityParamsScorer(self,eKinIn,goodBPM_ind)
        trialPoint = scorer.getTrialPoint()
        sum_diff2 = scorer.getScore(trialPoint)
        
        #---- Search algorithm from PyORBIT native package
        searchAlgorithm = SimplexSearchAlgorithm()
        
        maxIter = 200
        solverStopper = SolveStopperFactory.maxIterationStopper(maxIter)
        
        #max_time = 0.04
        #solverStopper = SolveStopperFactory.maxTimeStopper(max_time)
        
        solver = Solver()
        solver.setAlgorithm(searchAlgorithm)
        solver.setStopper(solverStopper)
        
        solver.solve(scorer,trialPoint)
        
        """
        #---- the fitting process ended, now about results
        print ("==============================================================")
        print ("??????????????????????????????????????????????????????????????")
        solver.getScoreboard().printScoreBoard()
        print ("===== best score ========== fitting time =",solver.getScoreboard().getRunTime())
        bestScore = solver.getScoreboard().getBestScore()   
        print ("best score=",bestScore," iteration=",solver.getScoreboard().getIteration())
        trialPoint = solver.getScoreboard().getBestTrialPoint()
        print (trialPoint.textDesciption())
        """
        #----- this will set the trial point for best score to the harmonic_data
        trialPoint = solver.getScoreboard().getBestTrialPoint()
        best_score = scorer.getScore(trialPoint)
        return (best_score,scorer)

class CavityParamsScorer(Scorer):
    """
    The implementation of the abstract Score class 
    as BPM phases vs cavity's parameters (amp., phase offset) scorer.
    """
    def __init__(self,bpms_scan_dataset, eKinIn, goodBPM_ind = -1):
        self.bpms_scan_dataset = bpms_scan_dataset
        self.eKinIn = eKinIn
        self.model_bpm = self.bpms_scan_dataset.getListOfGoodBPMs()[goodBPM_ind]
        bpm_ind = self.bpms_scan_dataset.bpm_name_to_ind_dict[self.model_bpm.bpm.getName()]
        bpm_phase_func = self.bpms_scan_dataset.bpm_epics_phases[bpm_ind]           
        self.bpm_pos = self.model_bpm.getPosition() 
        (cav_phase_arr,bpm_phase_arr,err_arr) = bpm_phase_func.getXYErrLists()
        self.cav_phase_arr = cav_phase_arr
        self.bpm_phase_arr = bpm_phase_arr
        #---------------------
        self.cav_exit_pos = 0.
        self.model_bpm_phase_arr = []
        
    def getModelBPM(self):
        return self.model_bpm
        
    def getModelBPM_PhaseArr(self):
        return self.model_bpm_phase_arr
        
    def getBPM_PhaseArr(self):
        return self.bpm_phase_arr
        
    def printResults(self, file_name_prefix = None):
        print ("================================")
        cav_name = self.bpms_scan_dataset.model_cav.cav.getName()
        bpm_name = self.model_bpm.bpm.getName().replace("_Diag","")
        print ("Cavity=",cav_name," BPM = ",bpm_name)
        st = " CavPhase[deg]   BPM_Model_Phase[deg]   BPM_EPICS_Phase[deg]  Diff[deg]"
        print (st)
        #-------------------------------------------
        fl_out = None
        if(file_name_prefix != None):
            fl_out = open(file_name_prefix+ "_"+cav_name+"_"+bpm_name+".dat","w")
            fl_out.write(st + "\n")
        #------------------------------------------_
        for ind,cav_phase in enumerate(self.cav_phase_arr):
            model_bpm_phase = self.model_bpm_phase_arr[ind]
            bpm_phase = self.bpm_phase_arr[ind]
            phase_diff = phaseNearTargetPhaseDeg(model_bpm_phase - bpm_phase,0.)
            st  = " %+6.1f "%cav_phase
            st += " %+8.1f  %+8.1f   %+8.1f"%(model_bpm_phase,bpm_phase,phase_diff)
            print (st)
            if(fl_out != None): fl_out.write(st + "\n")
        if(fl_out != None): fl_out.close()
    
    def getTrialPoint(self):
        """
        Returns the trial point with cavity's amplitude and phase offset.
        """
        amp = self.bpms_scan_dataset.model_cav.getModelAmp()
        cav_phase_offset = self.bpms_scan_dataset.model_cav.getCavityPhaseOffset()
        #-------------------
        variableProxy_arr = []
        variableProxy_arr.append(VariableProxy("amp",amp,0.01*amp))
        variableProxy_arr.append(VariableProxy("phaseOffset",cav_phase_offset,1.0))
        #-------------------
        trialPoint = TrialPoint()
        for variableProxy in variableProxy_arr:
            trialPoint.addVariableProxy(variableProxy)
        return trialPoint
    
    def getScore(self,trialPoint):
        """
        Returns the score as sum_diff2.
        """
        value_arr = trialPoint.getVariableProxyValuesArr()
        amp = value_arr[0]
        cav_phase_offset = value_arr[1]
        model_cav = self.bpms_scan_dataset.model_cav
        model_cav.setModelAmp(amp)
        model_cav.setCavityPhaseOffset(cav_phase_offset)
        (sum_diff2,self.model_bpm_phase_arr) = self.bpms_scan_dataset.makeModelBPM_Phases(self.eKinIn,self.model_bpm)
        return sum_diff2
        
class CavityParamsScorer_eKinOut(Scorer):
    """
    The implementation of the abstract Score class 
    as eKinOut(cav_phase) vs cavity's parameters (amp., phase offset) 
    scorer between BPMs data and model.
    """
    def __init__(self,cav_wrapper,om_model,eKinIn):
        self.cav_wrapper = cav_wrapper
        self.om_model = om_model        
        self.model_cav = self.om_model.getModelCavity(self.cav_wrapper.getName().replace("_RF",""))
        self.eKinIn = eKinIn
        self.cav_phase_arr = self.cav_wrapper.getCavity_PhaseArr() 
        self.eKInOut_BPMs_arr = self.cav_wrapper.eKin_Out_Arr()
        self.eKInOut_Model_arr = []
        
    def getCavityWrapper(self):
        return self.self.cav_wrapper
        
    def getModel_eKinOut_Arr(self):
        return self.eKInOut_Model_arr
        
    def calcModel_eKinOut_Arr(self,eKinIn):
        (eKinOut_arr,timeOut_arr) = self.model_cav.trackEmptyBunch(eKinIn,self.cav_phase_arr)
        self.eKInOut_Model_arr = eKinOut_arr
        return self.eKInOut_Model_arr

    def printResults(self, file_name_prefix = None):
        self.calcModel_eKinOut_Arr(self.eKinIn)
        if(len(self.eKInOut_Model_arr) != len(self.cav_phase_arr)): return
        print ("================================")
        cav_name = self.cav_wrapper.getName()
        print ("Cavity=",cav_name)
        st = " CavPhase[deg]   eKinOutBPM[MeV] eKinOutModel[MeV]  Diff[MeV]"
        print (st)
        #-------------------------------------------
        fl_out = None
        if(file_name_prefix != None):
            fl_out = open(file_name_prefix+ "_"+cav_name+"_eKinOut.dat","w")
            fl_out.write(st + "\n")
        #------------------------------------------_
        for ind,cav_phase in enumerate(self.cav_phase_arr):
            eKin_out_bpm = self.eKInOut_BPMs_arr[ind]
            eKin_out_model = self.eKInOut_Model_arr[ind]
            diff = eKin_out_model - eKin_out_bpm
            st  = " %+6.1f "%cav_phase
            st += " %8.3f  %8.3f   %+8.4f"%(eKin_out_bpm,eKin_out_model,diff)
            print (st)
            if(fl_out != None): fl_out.write(st + "\n")
        if(fl_out != None): fl_out.close()
    
    def getTrialPoint(self):
        """
        Returns the trial point with cavity's amplitude and phase offset.
        """
        amp = self.model_cav.getModelAmp()
        cav_phase_offset = self.model_cav.getCavityPhaseOffset()
        #-------------------
        variableProxy_arr = []
        variableProxy_arr.append(VariableProxy("amp",amp,0.01*amp))
        variableProxy_arr.append(VariableProxy("phaseOffset",cav_phase_offset,1.0))
        #-------------------
        trialPoint = TrialPoint()
        for variableProxy in variableProxy_arr:
            trialPoint.addVariableProxy(variableProxy)
        return trialPoint
    
    def getScore(self,trialPoint):
        """
        Returns the score as sum_diff2.
        """
        value_arr = trialPoint.getVariableProxyValuesArr()
        amp = value_arr[0]
        cav_phase_offset = value_arr[1]
        self.model_cav.setModelAmp(amp)
        self.model_cav.setCavityPhaseOffset(cav_phase_offset)
        self.calcModel_eKinOut_Arr(self.eKinIn)
        diff2 = 0.
        for ind,cav_phase in enumerate(self.cav_phase_arr):
            eKin_out_bpm = self.eKInOut_BPMs_arr[ind]
            eKin_out_model = self.eKInOut_Model_arr[ind]
            diff2 += (eKin_out_model - eKin_out_bpm)**2
        if(len(self.cav_phase_arr) > 0): diff2 /= len(self.cav_phase_arr) 
        return diff2

class SCL_CavityScanData:
    """
    It keeps the BPM scan data and performes analysis for cavity parameters 
    such as synchronous phase and amplitude.
    """
    def __init__(self,pyorbit_cav_name,om_model,scl_wizard_scan_reader):
        self.epics_cav_name = pyorbit_cav_name.replace("SCL","SCL_RF")
        self.om_model = om_model
        self.model_cav = self.om_model.getModelCavity(pyorbit_cav_name)
        self.cavity_status = True
        self.pyorbit_cav_name = pyorbit_cav_name
        self.bpms_scan_data_set = None
        if(not self.pyorbit_cav_name in scl_wizard_scan_reader.getCavityWrapperDict()):
            self.cavity_status = False
            return
        #-----------------------------------------
        self.bpms_scan_data_set = BPMsScanDataSet(self,self.om_model,scl_wizard_scan_reader)
        #-----------------------------------------
        #---- cav_wrapper keeps SCL Wizard data about scan
        self.cav_wrapper = scl_wizard_scan_reader.getCavityWrapperDict()[self.pyorbit_cav_name]
        #print ("debug cav_wrapper =",self.cav_wrapper.getName())
        #print ("debug self.cav_wrapper.bpm_data_dict.keys() = ",self.cav_wrapper.bpm_data_dict.keys())
        self.model_cav.isGood(self.cav_wrapper.isGood())
        self.cavity_status = self.cav_wrapper.isGood()
        self.cav_phase_epics = self.cav_wrapper.EPICS_Phase()
        self.cav_amp_epics = self.cav_wrapper.EPICS_Amp()
        #---- these synchronous phases are from OpenXAL SCL Wizard analysis
        self.cavSynchPhaseGoal = self.cav_wrapper.goalSynchPhase()
        self.cavSynchPhaseReal = self.cav_wrapper.realSynchPhase()

    def getCavityWrapper(self):
        return self.cav_wrapper
        
    def getCavityPhaseEPICS(self):
        return self.cav_phase_epics
        
    def getCavityAmpEPICS(self):
        return self.cav_amp_epics
        
    def setModelCavityPhaseEPICS(self, cav_phase_epics):
        self.model_cav.setEPICS_CavityModelPhase(cav_phase_epics)
        
    def get_eKinOut(self,eKinIn,cav_phase_epics):
        cav_phase_arr = [self.cav_phase_epics,]
        (eKinOut_arr,timeOut_arr) = self.model_cav.trackEmptyBunch(eKinIn,cav_phase_arr)
        eKinOut = eKinOut_arr[0]
        return eKinOut

    def cavitySatus(self,cavity_status = None):
        """ It could be False (no BPM data) or True (BPM data is there) """
        if(cavity_status == None):return self.cavity_status
        self.cavity_status = cavity_status
        return self.cavity_status
        
    def getBPMsScanDataSet(self):
        return self.bpms_scan_data_set
        
    def performAnalysis(self,min_amp = 1.0, print_info = False, goodBPM_ind = -1):  
        self.bpms_scan_data_set.cleanBPMsMinAmp(min_amp)
        self.bpms_scan_data_set.cosAnalysisAllBPms(print_info)
        eKinIn = self.get_eKinIn_Guess()
        self.bpms_scan_data_set.cavityParamsGuess(eKinIn,goodBPM_ind)
        
    def get_eKinIn_Guess(self):
        eKin_in = self.cav_wrapper.eKin_In()
        return eKin_in
        
    def get_eKinOut_Guess(self):
        eKin_in = self.cav_wrapper.eKin_Out()
        return eKin_in      
        
    def performCavityParamsFitting(self,eKinIn,goodBPM_ind = -1):
        (diff2,scorer) = self.bpms_scan_data_set.cavityParamsFitting(eKinIn,goodBPM_ind)
        return (diff2,scorer)

    def performCavityParamsFitting_eKin(self,eKinIn):
        """ Fitting is done using eKinOut(cav_phase) data from BPMs """
        scorer = CavityParamsScorer_eKinOut(self.cav_wrapper,self.om_model,eKinIn)
        trialPoint = scorer.getTrialPoint()
        sum_diff2 = scorer.getScore(trialPoint)
        
        #---- Search algorithm from PyORBIT native package
        searchAlgorithm = SimplexSearchAlgorithm()
        
        maxIter = 200
        solverStopper = SolveStopperFactory.maxIterationStopper(maxIter)
        
        #max_time = 0.04
        #solverStopper = SolveStopperFactory.maxTimeStopper(max_time)
        
        class BestScoreListener(ScoreboardActionListener):
            def __init__(self):
                ScoreboardActionListener.__init__(self)
                
            def performAction(self,solver):
                scoreBoard = solver.getScoreboard()
                iteration = scoreBoard.getIteration()
                trialPoint = scoreBoard.getBestTrialPoint()
                print ("============= iter=",scoreBoard.getIteration()," best score=",scoreBoard.getBestScore())
                print (trialPoint.textDesciption()) 
        
        solver = Solver()
        solver.setAlgorithm(searchAlgorithm)
        solver.setStopper(solverStopper)
        
        #---- if we want to see the progress of fitting 
        #solver.getScoreboard().addBestScoreListener(BestScoreListener())           
        
        solver.solve(scorer,trialPoint)

        #----- this will set the trial point for best score to the harmonic_data
        trialPoint = solver.getScoreboard().getBestTrialPoint()
        best_score = scorer.getScore(trialPoint)
        return (best_score,scorer)
