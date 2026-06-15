"""
Controller for initialization of the SCL (CCL+HEBT also) linac from EPICS 
"""
import sys
import time
import html
import math

from PySide6 import QtWidgets 

from PySide6.QtWidgets import (
    QFrame,
    QTableWidget,
    QTableView,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton,
    QWidget,
    QTabWidget,
    QGroupBox,
    QProgressBar,
    QMainWindow,
    QHeaderView,
    QPlainTextEdit,
    QCheckBox,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QRadioButton
    )

from PySide6.QtCore import (
    Qt,Slot,
    QRunnable, QObject, QThreadPool, Slot,
    QAbstractTableModel,
    QSize
    )

from PySide6.QtGui import (
    QStandardItemModel, QStandardItem,
    QTextDocument,
    QIcon,
    QBrush
    )

from gui_lib.borderlayout import BorderLayout, Position
from gui_lib.style_sheets_lib import StyleSheetFactory
from gui_lib.table_view_model_lib import LACE_QTableView, LACE_DataTableModel
from .wrappers_cavs_bpms_magnets import Cavity_Wrapper, BPM_Wrapper


#----------------------------------------------------------
# Custom QtWidgets
#----------------------------------------------------------

class BPMsQTableView(LACE_QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)

    def sizeHint(self):
        """
        Overrides the default sizeHint method to provide a custom recommended size.
        QSize(width,high)
        """
        return QSize(320, 150)

#----------------------------------------------------------
# Internal Sub - Controllers
#----------------------------------------------------------

class Cavs_State_Cntrl:
    """
    Controller for RF Cavities initialization.
    """
    def __init__(self,init_state_cntrl):
        self.init_state_cntrl = init_state_cntrl
        self.lace_scl_wizard = self.init_state_cntrl.lace_scl_wizard
        self.bpm_wrappers = self.init_state_cntrl.bpms_state_cntrl.getBPM_Wrappers()
        self.model_cavs = self.lace_scl_wizard.getOM().getModelCavs()
        self.cav_wrappers = []
        for cav_ind,model_cav in enumerate(self.model_cavs):
            cav_wrapper = Cavity_Wrapper(model_cav,self.bpm_wrappers)
            self.cav_wrappers.append(cav_wrapper)
        #---- main widget
        self.mainWidget = QFrame(self.init_state_cntrl.tabs)
        #---- tab name
        self.tab_name = "Cavities RF Initialization"
        #----

    def getTabName(self):
        """ Returns the tab name the controller """
        return self.tab_name
        
    def getMainWidget(self):
        """ Returns the mainWidget (window) """
        return self.mainWidget
        
    def getCavWrappers(self):
        return self.cav_wrappers
        
    def getBPM_Wrappers(self):
        return self.bpm_wrappers

    def dumpCntrlDataToDA(self,parent_da):
        """ Puts this controller data into the Data Adaptor """
        return
       
    def readCntrlDataFromDA(self,parent_da):
        """ Reads data for this controller from the Data Adaptor """
        return
        
    def stopAllThreads(self):
        """ Stops all threads of this controller """
        #self.scanStopper.setSetToStop(True)
        return
        
class BPMs_State_Cntrl:
    """
    Controller for BPMs data.
    """
    def __init__(self,init_state_cntrl):
        self.init_state_cntrl = init_state_cntrl
        self.lace_scl_wizard = self.init_state_cntrl.lace_scl_wizard
        self.model_bpms = self.lace_scl_wizard.getOM().getModelBPMs()
        self.bpm_wrappers = []
        for bpm_ind,model_bpm in enumerate(self.model_bpms):
            bpm_wrapper = BPM_Wrapper(model_bpm)
            self.bpm_wrappers.append(bpm_wrapper)
        #---- main widget
        self.mainWidget = QFrame(self.init_state_cntrl.tabs)
        #---- tab name
        self.tab_name = "BPMs Parameters Controller"

    def getTabName(self):
        """ Returns the tab name the controller """
        return self.tab_name
        
    def getMainWidget(self):
        """ Returns the mainWidget (window) """
        return self.mainWidget        

    def getBPM_Wrappers(self):
        return self.bpm_wrappers

    def dumpCntrlDataToDA(self,parent_da):
        """ Puts this controller data into the Data Adaptor """
        return
       
    def readCntrlDataFromDA(self,parent_da):
        """ Reads data for this controller from the Data Adaptor """
        return
        
    def stopAllThreads(self):
        """ Stops all threads of this controller """
        #self.scanStopper.setSetToStop(True)
        return

#----------------------------------------------------------
#  Cavities RF Data Table Model
#----------------------------------------------------------

class CavsDataTableModel(LACE_DataTableModel):
    def __init__(self,init_state_cntrl):
        super().__init__()
        self.init_state_cntrl = init_state_cntrl
        self.lace_scl_wizard = self.init_state_cntrl.lace_scl_wizard
        self.cavs_state_cntrl = self.init_state_cntrl.cavs_state_cntrl
        self.cav_wrappers = self.cavs_state_cntrl.getCavWrappers()
        #---- Sets the headers
        headers  = ["Cavity", "Pos[m]","Good","Amp-EPICS",html.unescape("&phi;-EPICS")]
        headers += ["Measured","Analyzed","Amp-Model",html.unescape("&phi;-model")]
        headers += ["Amp-Coeff",html.unescape("&phi;-Offset"),"BPM1","BPM2"]
        self.setHorizontalHeaderLabels(headers)
        for cav_ind,cav_wrapper in enumerate(self.cav_wrappers):
            name_item = QStandardItem(cav_wrapper.getAlias())
            pos_item = QStandardItem("%7.3f"%cav_wrapper.model_cav.getPosition())
            isGood_item = QStandardItem() ; isGood_item.setCheckable(True) ; isGood_item.setCheckState(Qt.Checked)
            epics_amp_item = QStandardItem()
            epics_phase_item = QStandardItem()
            measured_item = QStandardItem() ; measured_item.setCheckable(True) ; measured_item.setCheckState(Qt.Unchecked)
            analyzed_item = QStandardItem() ; analyzed_item.setCheckable(True) ; analyzed_item.setCheckState(Qt.Unchecked)
            measured_item.setEnabled(False)
            analyzed_item.setEnabled(False)
            model_amp_item = QStandardItem()
            model_phase_item = QStandardItem()
            model_coeff_amp_item = QStandardItem()
            phase_offset_item = QStandardItem()
            bpm1_item = QStandardItem()
            bpm2_item = QStandardItem()
            row  = [name_item,pos_item,isGood_item,]
            row += [epics_amp_item,epics_phase_item]
            row += [measured_item,analyzed_item]
            row += [model_amp_item,model_phase_item]
            row += [model_coeff_amp_item,phase_offset_item]
            row += [bpm1_item,bpm2_item]
            self.appendRow(row)
        self.itemChanged.connect(self.handleItemChanged)
            
    @Slot("QStandardItem*")
    def handleItemChanged(self, item):
        """ Only the Good descriptor is allowed to be changed from the Table View """
        if(item.isCheckable() and item.checkState() in (Qt.Checked, Qt.Unchecked)):
            col = item.column()
            if(col != 2): return
            self.cav_wrappers[item.row()].isGood = self._getValueOfBoolItem(item)
            self.updateDependentTables()

    def _updateItemsFromData(self):
        for cav_ind,cav_wrapper in enumerate(self.cav_wrappers):             
            #---- cavity is good
            self._updateBoolItem(cav_wrapper.isGood,self.item(cav_ind,2))
            if(not cav_wrapper.isGood):
                cav_wrapper.modelAmp = 0.
                cav_wrapper.model_cav.setModelAmp(cav_wrapper.modelAmp)
            epics_amp_item = self.item(cav_ind,3) ; epics_amp_item.setText("%7.4f"%cav_wrapper.epicsAmpInit)
            epics_phase_item = self.item(cav_ind,4) ; epics_phase_item.setText("%+6.1f"%cav_wrapper.epicsPhaseInit)
            self._updateBoolItem(cav_wrapper.isMeasured,self.item(cav_ind,5))
            self._updateBoolItem(cav_wrapper.isAnalyzed,self.item(cav_ind,6))
            model_amp_item  = self.item(cav_ind,7) ; model_amp_item.setText("%6.4f"%cav_wrapper.modelAmp)           
            model_phase_item = self.item(cav_ind,8) ; model_phase_item.setText("%+6.1f"%cav_wrapper.modelPhase) 
            model_coeff_amp_item = self.item(cav_ind,9) ; model_coeff_amp_item.setText("%6.4f"%cav_wrapper.modelCoeffToEpicsAmp)
            phase_offset_item = self.item(cav_ind,10) ; phase_offset_item.setText("%+6.1f"%cav_wrapper.model_phase_shift)
            bpm1_item = self.item(cav_ind,11) ;  bpm1_item.setText("")
            if(cav_wrapper.bpm_wrapper0 != None):
                if(cav_wrapper.bpm_wrapper0.isGood):
                    bpm1_item.setForeground(QBrush(Qt.GlobalColor.black))
                else:
                    bpm1_item.setForeground(QBrush(Qt.GlobalColor.red))
                bpm1_item.setText(cav_wrapper.bpm_wrapper0.alias)
            bpm2_item = self.item(cav_ind,12) ;  bpm2_item.setText(""); 
            if(cav_wrapper.bpm_wrapper1 != None):  
                bpm2_item.setText(cav_wrapper.bpm_wrapper1.alias)

class BPMsDataTableModel(LACE_DataTableModel):
    def __init__(self,init_state_cntrl):
        super().__init__()
        self.init_state_cntrl = init_state_cntrl
        self.lace_scl_wizard = self.init_state_cntrl.lace_scl_wizard
        self.bpm_state_cntrl = self.init_state_cntrl.bpms_state_cntrl
        self.bpm_wrappers = self.bpm_state_cntrl.getBPM_Wrappers()
        #---- Sets the headers
        headers = ["BPM", "Pos.[m]","Good","Phase Offset"]  
        self.setHorizontalHeaderLabels(headers)
        for bpm_ind,bpm_wrapper in enumerate(self.bpm_wrappers):
            bpm_name_item = QStandardItem(bpm_wrapper.getAlias())
            bpm_pos_item = QStandardItem("%7.3f"%bpm_wrapper.getPosition())
            bpm_good_item = QStandardItem()
            bpm_good_item.setCheckable(True)
            bpm_phase_offset_item = QStandardItem("0.")
            if(bpm_wrapper.isGood):
                bpm_good_item.setCheckState(Qt.Checked)
            else:
                bpm_good_item.setCheckState(Qt.Unchecked)
            bpm_name_item.setEditable(False)
            bpm_pos_item.setEditable(False)
            bpm_phase_offset_item.setEditable(False)
            row = [bpm_name_item,bpm_pos_item,bpm_good_item,bpm_phase_offset_item]
            self.appendRow(row)
        self.itemChanged.connect(self.handleItemChanged)    
            
    @Slot("QStandardItem*")
    def handleItemChanged(self, item):
        """ Only the Good descriptor is allowed to be changed from the Table View """
        if(item.isCheckable() and item.checkState() in (Qt.Checked, Qt.Unchecked)):
            self.bpm_wrappers[item.row()].isGood = self._getValueOfBoolItem(item)
            self.updateDependentTables()

    def _updateItemsFromData(self):
        for bpm_ind,bpm_wrapper in enumerate(self.bpm_wrappers):
            item = self.item(bpm_ind,2); self._updateBoolItem(bpm_wrapper.isGood,item)
            item = self.item(bpm_ind,3); item.setText("%+7.1f"%bpm_wrapper.getPhaseOffset())

class BPMsParamsTableModel(LACE_DataTableModel):
    def __init__(self,init_state_cntrl):
        super().__init__()
        self.init_state_cntrl = init_state_cntrl
        self.lace_scl_wizard = self.init_state_cntrl.lace_scl_wizard
        self.bpm_state_cntrl = self.init_state_cntrl.bpms_state_cntrl
        self.bpm_wrappers = self.bpm_state_cntrl.getBPM_Wrappers()
        #---- Sets the headers
        #---- OEDA stands for Off Energy Delay Adjustment
        headers = ["BPM", "Pos.[m]","Good","Phase Offset","OEDA Time [ms]"]  
        self.setHorizontalHeaderLabels(headers)
        for bpm_ind,bpm_wrapper in enumerate(self.bpm_wrappers):
            bpm_name_item = QStandardItem(bpm_wrapper.getAlias())
            bpm_pos_item = QStandardItem("%7.3f"%bpm_wrapper.getPosition())
            bpm_good_item = QStandardItem()
            bpm_good_item.setCheckable(True)
            bpm_phase_offset_item = QStandardItem("0.")
            bpm_oeda_item = QStandardItem("0.")
            if(bpm_wrapper.isGood):
                bpm_good_item.setCheckState(Qt.Checked)
            else:
                bpm_good_item.setCheckState(Qt.Unchecked)
            bpm_name_item.setEditable(False)
            bpm_pos_item.setEditable(False)
            bpm_phase_offset_item.setEditable(False)
            bpm_oeda_item.setEditable(False)
            row = [bpm_name_item,bpm_pos_item,bpm_good_item,bpm_phase_offset_item,bpm_oeda_item]
            self.appendRow(row)
        self.itemChanged.connect(self.handleItemChanged)    
            
    @Slot("QStandardItem*")
    def handleItemChanged(self, item):
        # Verify that the modified data is related to the Qt::CheckStateRole role
        if(item.isCheckable() and item.checkState() in (Qt.Checked, Qt.Unchecked)):
            self.bpm_wrappers[item.row()].isGood = self._getValueOfBoolItem(item)

    def _updateItemsFromData(self):
        for bpm_ind,bpm_wrapper in enumerate(self.bpm_wrappers):
            item = self.item(bpm_ind,2); self._updateBoolItem(bpm_wrapper.isGood,item)
            item = self.item(bpm_ind,3); item.setText("%+6.3f"%bpm_wrapper.getOEDA_EPICS_TimeShift())
        
#----------------------------------------------------------
# Actions on events with buttons 
#----------------------------------------------------------
class InitCavs_Action:
    """ Initialization all cavities """ 
    def __init__(self,init_state_cntrl):
        self.init_state_cntrl = init_state_cntrl
        self.cavs_state_cntrl = self.init_state_cntrl.cavs_state_cntrl
        self.cavs_table_view = self.init_state_cntrl.cavs_table_view
        self.cavs_data_table_model = self.init_state_cntrl.cavs_data_table_model
        self.bpms_data_table_model = self.init_state_cntrl.bpms_data_table_model
      
    def _performAction(self,cav_wrappers):
        """ It connects the cavity wrappers from cav_wrappers list """
        bpm_wrappers = self.cavs_state_cntrl.getBPM_Wrappers()
        sleep_time = 0.5
        n_repeat = 3
        bad_cavs = []
        bad_bpms = []
        for ind in range(n_repeat):
            bad_cavs = []
            bad_bpms = []
            for cav_wrapper in cav_wrappers:
                if(not cav_wrapper.connectPVs()): bad_cavs.append(cav_wrapper)
            for bpm_wrapper in bpm_wrappers:
                if(not bpm_wrapper.connectPVs()): bad_bpms.append(bpm_wrapper)
            time.sleep(0.5)
        for cav_wrapper in bad_cavs:
            cav_wrapper.isGood = False
            cav_wrapper.cleanAllScanData() 
        for bpm_wrapper in bad_bpms:
            bpm_wrapper.isGood = False
        #---- check real connection to EPICS
        bpm_amp_pvs = [bpm_wrapper.getAmpPV() for bpm_wrapper in bpm_wrappers]
        bpm_phase_pvs = [bpm_wrapper.getPhasePV() for bpm_wrapper in bpm_wrappers]
        amp_vals = [bpm_amp_pv.get() for bpm_amp_pv in bpm_amp_pvs]
        phase_vals = [bpm_phase_pv.get() for bpm_phase_pv in bpm_phase_pvs]        
        for bpm_ind,bpm_wrapper in enumerate(bpm_wrappers):
            if(not bpm_wrapper.isGood): continue
            if( (amp_vals[bpm_ind] is None) or (phase_vals[bpm_ind] is None) \
                or (math.isnan(amp_vals[bpm_ind])) or \
                (math.isnan(phase_vals[bpm_ind]))):
                bpm_wrapper.isGood = False
        self.cavs_data_table_model.tableChanged()
        self.bpms_data_table_model.tableChanged()
        print ("debug init all")        
      
    def performAction(self):
        cav_wrappers = self.cavs_state_cntrl.getCavWrappers()
        self._performAction(cav_wrappers)
        
    def performActionForSelected(self):
        cav_wrappers = self.cavs_state_cntrl.getCavWrappers()
        cav_selection_model = self.cavs_table_view.selectionModel()
        cav_name_column_ind = 0
        QModelIndex_list = cav_selection_model.selectedIndexes()
        cavs_list = []
        for q_model_ind in QModelIndex_list:
            if(q_model_ind.column() != cav_name_column_ind): continue
            row = q_model_ind.row()
            cav_wrapper = cav_wrappers[row]
            if(not cav_wrapper.isGood):
                cav_wrapper.cleanAllScanData()
                continue
            cavs_list.append(cav_wrapper)
        self._performAction(cavs_list)
        
class CleanCavs_Action:
    """ Clean all scan data for all cavities """ 
    def __init__(self,init_state_cntrl):
        self.init_state_cntrl = init_state_cntrl
        self.cavs_state_cntrl = self.init_state_cntrl.cavs_state_cntrl
        self.cavs_table_view = self.init_state_cntrl.cavs_table_view
        self.cavs_data_table_model = self.init_state_cntrl.cavs_data_table_model

    def _performAction(self,cav_wrappers):
        for cav_wrapper in cav_wrappers:
            cav_wrapper.cleanAllScanData()
        self.cavs_data_table_model.tableChanged()
        
    def performAction(self):
        self._performAction(self.cavs_state_cntrl.getCavWrappers())
        print ("debug clean all")
        
    def performActionForSelected(self):    
        cav_wrappers = self.cavs_state_cntrl.getCavWrappers()
        cav_selection_model = self.cavs_table_view.selectionModel()
        cav_name_column_ind = 0
        QModelIndex_list = cav_selection_model.selectedIndexes()
        cavs_list = []
        for q_model_ind in QModelIndex_list:
            if(q_model_ind.column() != cav_name_column_ind): continue
            row = q_model_ind.row()
            cav_wrapper = cav_wrappers[row]
            if(not cav_wrapper.isGood):
                cav_wrapper.cleanAllScanData()
                continue
            cavs_list.append(cav_wrapper)
        self._performAction(cavs_list)        
        print ("debug clean selected")   

class SetBPM12forAllCavs_Action:
    """ Sets BPM1 and BPM2 for all cavities """ 
    def __init__(self,init_state_cntrl):
        self.init_state_cntrl = init_state_cntrl
        self.cavs_table_view = self.init_state_cntrl.cavs_table_view
        self.cavs_data_table_model = self.init_state_cntrl.cavs_data_table_model
        self.cavs_state_cntrl = self.init_state_cntrl.cavs_state_cntrl
        self.min_dist_bpm12_spin_box = self.init_state_cntrl.min_dist_bpm12_spin_box
        
    def performAction(self):
        cav_wrappers = self.cavs_state_cntrl.getCavWrappers()
        bpm_wrappers = self.cavs_state_cntrl.getBPM_Wrappers()
        min_dist_bpm12 = self.min_dist_bpm12_spin_box.value()
        #---- Let's set BPM1 and BPM2
        for cav_wrapper in cav_wrappers:
            if(not cav_wrapper.isGood):
                cav_wrapper.bpm_wrapper0 = None
                cav_wrapper.bpm_wrapper1 = None
                continue
            cav_pos = cav_wrapper.getPosition()
            for bpm_wrapper in bpm_wrappers:
                if(not bpm_wrapper.isGood): continue
                if(bpm_wrapper.getPosition() > cav_pos):
                    cav_wrapper.bpm_wrapper0 = bpm_wrapper
                    break
            if(cav_wrapper.bpm_wrapper0 == None):
                print ("debug ERROR cav=",cav_wrapper.alias," cannot get BPM1!")
                self.cavs_data_table_model.tableChanged()                
                return
            for bpm_wrapper in bpm_wrappers:
                if(not bpm_wrapper.isGood): continue
                if(bpm_wrapper.getPosition() > cav_wrapper.bpm_wrapper0.getPosition() + min_dist_bpm12):
                    cav_wrapper.bpm_wrapper1 = bpm_wrapper
                    break
            if(cav_wrapper.bpm_wrapper0 == None):
                print ("debug ERROR cav=",cav_wrapper.alias," cannot get BPM2!")
                self.cavs_data_table_model.tableChanged()
                return
        self.cavs_data_table_model.tableChanged()
        print ("debug set BPM 1,2 for all cavs.")
        
class SetBPM12forSelectedCavs_Action:
    """ Sets BPM1 or BPM2 for selected Cavities """ 
    def __init__(self,init_state_cntrl, bpm12_ind = 1):
        #---- bpm12_ind could be 1 or 2
        self.bpm12_ind = bpm12_ind
        self.init_state_cntrl = init_state_cntrl
        self.cavs_table_view = self.init_state_cntrl.cavs_table_view
        self.bpms_table_view = self.init_state_cntrl.bpms_table_view
        self.cavs_state_cntrl = self.init_state_cntrl.cavs_state_cntrl
        self.cavs_data_table_model = self.init_state_cntrl.cavs_data_table_model
        
    def performAction(self):
        cav_wrappers = self.cavs_state_cntrl.getCavWrappers()
        bpm_wrappers = self.cavs_state_cntrl.getBPM_Wrappers()
        #-------------------------------------------------
        bpm_selection_model = self.bpms_table_view.selectionModel()
        QModelIndex_list = bpm_selection_model.selectedIndexes()
        bpm_wrapper = None
        bpm_name_column_ind = 0
        for q_model_ind in QModelIndex_list:
            if(q_model_ind.column() != bpm_name_column_ind): continue
            row = q_model_ind.row()
            bpm_wrapper = bpm_wrappers[row]
            break
        if(bpm_wrapper == None):
            print ("debug please select one BPM from the left table.")
            return
        #---- here we have bpm_wrapper to set up as BPM1 or BPM2
        cav_selection_model = self.cavs_table_view.selectionModel()
        cav_name_column_ind = 0
        QModelIndex_list = cav_selection_model.selectedIndexes()
        cav_row_list = []
        for q_model_ind in QModelIndex_list:
            if(q_model_ind.column() != cav_name_column_ind): continue
            row = q_model_ind.row()
            cav_wrapper = cav_wrappers[row]
            if(not cav_wrapper.isGood): continue
            cav_row_list.append(row)
            if(bpm_wrapper.getPosition() < cav_wrapper.getPosition()):
                print ("debug ERROR cav=",cav_wrapper.alias," cannot get BPM"+str(self.bpm12_ind)+"!")
                self.cavs_data_table_model.tableChanged()
                return
            if(bpm_wrapper == cav_wrapper.bpm_wrapper0 or bpm_wrapper == cav_wrapper.bpm_wrapper1): continue
            if(self.bpm12_ind == 1): cav_wrapper.bpm_wrapper0 = bpm_wrapper
            if(self.bpm12_ind == 2): cav_wrapper.bpm_wrapper1 = bpm_wrapper
        #---- put BPMs 1 and 2 in order according their positions
        for cav_wrapper_ind in cav_row_list:
            cav_wrapper = cav_wrappers[cav_wrapper_ind]
            if(cav_wrapper.bpm_wrapper0 == None or cav_wrapper.bpm_wrapper1 == None): continue
            if(cav_wrapper.bpm_wrapper0.getPosition() > cav_wrapper.bpm_wrapper1.getPosition()):
                bpm_wrapper0 = cav_wrapper.bpm_wrapper0
                cav_wrapper.bpm_wrapper0 = cav_wrapper.bpm_wrapper1
                cav_wrapper.bpm_wrapper1 = bpm_wrapper0 
        print ("debug set BPM1 for selected cavs.")
        self.cavs_data_table_model.tableChanged()
        
class BPMReadPhaseOffset_Action:
    """ Read BPM Phase Offsets from external .dat file """ 
    def __init__(self,init_state_cntrl):
        self.init_state_cntrl = init_state_cntrl
        
    def performAction(self):
        print ("debug read bpm phase offsets")       
        
class BPMReadOEDA_Action:
    """ Read BPM OEDA times in [ms] from external .dat file """ 
    #---- OEDA stands for Off Energy Delay Adjustment
    def __init__(self,init_state_cntrl):
        self.init_state_cntrl = init_state_cntrl
        
    def performAction(self):
        print ("debug read bpm OEDA")
        
class BPMReadBoth_Action:
    """ Read BPM Phase Offsets and OEDA times in [ms] from external .dat file """ 
    #---- OEDA stands for Off Energy Delay Adjustment
    def __init__(self,init_state_cntrl):
        self.init_state_cntrl = init_state_cntrl
        
    def performAction(self):
        print ("debug read bpm Phase Offsets and OEDA")
        
class BPMSaveBoth_Action:
    """ Save BPM Phase Offsets and OEDA times in [ms] to an external .dat file """ 
    #---- OEDA stands for Off Energy Delay Adjustment
    def __init__(self,init_state_cntrl):
        self.init_state_cntrl = init_state_cntrl
        
    def performAction(self):
        print ("debug save bpm Phase Offsets and OEDA")
        
        
#----------------------------------------------------------
# Main Controller for this library
#----------------------------------------------------------

class InitState_Cntrl:
    """
    It initialize the linac state (Cavities,BPMs, and quads) from the EPICS.
    It keeps reference to main window of the Wizard and its own main pane Widget.
    """
    def __init__(self,lace_scl_wizard):
        self.lace_scl_wizard = lace_scl_wizard
        #---- main widget
        self.mainWidget = QFrame(self.lace_scl_wizard.tabs)
        #---- tab name
        self.tab_name = "Initialization"
        
        #---- Internal tabs
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setMovable(False)
        
         #---- BPMs states controller
        self.bpms_state_cntrl = BPMs_State_Cntrl(self)

        #---- Cavities states controller
        self.cavs_state_cntrl = Cavs_State_Cntrl(self)

        self.tabs.addTab(self.cavs_state_cntrl.getMainWidget(),self.cavs_state_cntrl.getTabName())
        self.tabs.addTab(self.bpms_state_cntrl.getMainWidget(),self.bpms_state_cntrl.getTabName())
        
        #---------------------------------------------------
        #---- Let's make self.cavs_state_cntrl tab window
        #---------------------------------------------------
        self.bpms_table_view = BPMsQTableView()
        self.bpms_data_table_model = BPMsDataTableModel(self)
        self.bpms_table_view.setModel(self.bpms_data_table_model)
        self.bpms_table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.bpms_table_view.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeToContents)
        self.bpms_table_view.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeToContents)
        self.bpms_table_view.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeToContents)
        self.bpms_table_view.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeMode.Stretch)

        self.cavs_table_view = LACE_QTableView()
        self.cavs_data_table_model = CavsDataTableModel(self)
        self.cavs_table_view.setModel(self.cavs_data_table_model)
        self.cavs_table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        #self.cavs_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.cavs_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        #---- upper buttons panel
        buttons_style = StyleSheetFactory.pushButtonStyleSheet()
        init_all_button       = QPushButton(text="Init All from EPICS",parent=None)        
        init_selected_button  = QPushButton(text="Init Selected from EPICS",parent=None)
        remove_all_button     = QPushButton(text="Remove All Scan Results",parent=None)
        remove_selected_button = QPushButton(text="Remove Selected Scan Results",parent=None)
        
        min_dist_bpm12_label = QLabel("Min Dist. BPM 1-2 [m]=")
        self.min_dist_bpm12_spin_box = QDoubleSpinBox()
        self.min_dist_bpm12_spin_box.setRange(0.,100.)  # Set min/max range
        self.min_dist_bpm12_spin_box.setDecimals(0)     # Set precision to 2 decimal places
        self.min_dist_bpm12_spin_box.setSingleStep(1.0) # Set step size for arrow buttons
        self.min_dist_bpm12_spin_box.setValue(25)       # Set default value        
        set_bpm12_button = QPushButton(text="Set BPM1+BPM2 for All Cavs.",parent=None)
        set_bpm1_button = QPushButton(text="Set BPM1 for Slected Cavs.",parent=None)
        set_bpm2_button = QPushButton(text="Set BPM2 for Slected Cavs.",parent=None)
        
        init_all_button.setStyleSheet(buttons_style)
        init_selected_button.setStyleSheet(buttons_style)
        remove_all_button.setStyleSheet(buttons_style)
        remove_selected_button.setStyleSheet(buttons_style)
        
        set_bpm12_button.setStyleSheet(buttons_style)
        set_bpm1_button.setStyleSheet(buttons_style)
        set_bpm2_button.setStyleSheet(buttons_style) 
        
        #---- cavs button action assignment
        initCavs_Action = InitCavs_Action(self)
        cleanCavs_Action = CleanCavs_Action(self)
        setBPM12forAllCavs_Action = SetBPM12forAllCavs_Action(self)
        setBPM1forSelectedCavs_Action = SetBPM12forSelectedCavs_Action(self,1)
        setBPM2forSelectedCavs_Action = SetBPM12forSelectedCavs_Action(self,2)
        
        init_all_button.clicked.connect(lambda: initCavs_Action.performAction())
        init_selected_button.clicked.connect(lambda: initCavs_Action.performActionForSelected())  
        remove_all_button.clicked.connect(lambda: cleanCavs_Action.performAction())     
        remove_selected_button.clicked.connect(lambda: cleanCavs_Action.performActionForSelected())
        set_bpm12_button.clicked.connect(lambda: setBPM12forAllCavs_Action.performAction())   
        set_bpm1_button.clicked.connect(lambda: setBPM1forSelectedCavs_Action.performAction())   
        set_bpm2_button.clicked.connect(lambda: setBPM2forSelectedCavs_Action.performAction())   

        upper_view = QWidget()
        
        h_1_view = QWidget()
        hlayout_1 = QHBoxLayout()
        hlayout_1.addWidget(init_all_button)
        hlayout_1.addWidget(init_selected_button)
        hlayout_1.addWidget(remove_all_button)
        hlayout_1.addWidget(remove_selected_button)
        hlayout_1.setSpacing(0)
        hlayout_1.setContentsMargins(0, 0, 0, 0)        
        h_1_view.setLayout(hlayout_1)
       
        
        h_2_view = QWidget()
        hlayout_2 = QHBoxLayout()
        hlayout_2.addWidget(min_dist_bpm12_label)
        hlayout_2.addWidget(self.min_dist_bpm12_spin_box)
        hlayout_2.addWidget(set_bpm12_button)
        hlayout_2.addWidget(set_bpm1_button)
        hlayout_2.addWidget(set_bpm2_button)
        hlayout_2.setAlignment(Qt.AlignLeft)
        hlayout_2.setSpacing(0)
        hlayout_2.setContentsMargins(0, 0, 0, 0)         
        h_2_view.setLayout(hlayout_2)
        
        
        upper_layout = QVBoxLayout()
        upper_layout.addWidget(h_1_view)
        upper_layout.addWidget(h_2_view)
        upper_layout.setSpacing(0)
        upper_layout.setContentsMargins(0, 0, 0, 0)         
        upper_view.setLayout(upper_layout)
        
        central_view = QWidget()
        central_layout = QHBoxLayout()
        central_layout.addWidget(self.bpms_table_view)
        central_layout.addWidget(self.cavs_table_view,1)
        central_view.setLayout(central_layout)
        
        cav_init_all_layout = QVBoxLayout()
        cav_init_all_layout.addWidget(upper_view)
        cav_init_all_layout.addWidget(central_view)

        self.cavs_state_cntrl.getMainWidget().setLayout(cav_init_all_layout)

        #---------------------------------------------------
        #---- Let's make self.bpms_state_cntrl tab window
        #---------------------------------------------------
        self.bpms_params_table_view = LACE_QTableView()
        self.bpms_params_table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.bpms_params_table_model = BPMsParamsTableModel(self)
        self.bpms_params_table_view.setModel(self.bpms_params_table_model)
        #self.bpms_params_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.bpms_params_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        #---- add dependency to the bpms_data_table_model
        self.bpms_data_table_model.addDependentTableModel(self.bpms_params_table_model)
        
        #---- OEDA stands for Off Energy Delay Adjustment
        bpmReadPhaseOffset_button = QPushButton(text="Read BPMs' Phase Offsets",parent=None)        
        bpmReadOEDA_button        = QPushButton(text="Read BPMs' OEDA",parent=None)
        bpmReadBoth_button        = QPushButton(text="Read Both",parent=None)
        bpmSaveBoth_button        = QPushButton(text="Save Both",parent=None)
        
        bpmReadPhaseOffset_button.setStyleSheet(buttons_style)
        bpmReadOEDA_button.setStyleSheet(buttons_style)       
        bpmReadBoth_button.setStyleSheet(buttons_style)
        bpmSaveBoth_button.setStyleSheet(buttons_style)
        
        #---- cavs button action assignment
        bpmReadPhaseOffset_Action = BPMReadPhaseOffset_Action(self)
        bpmReadOEDA_Action = BPMReadOEDA_Action(self)
        bpmReadBoth_Action = BPMReadBoth_Action(self)
        bpmSaveBoth_Action = BPMSaveBoth_Action(self)
        bpmReadPhaseOffset_button.clicked.connect(lambda: bpmReadPhaseOffset_Action.performAction())
        bpmReadOEDA_button.clicked.connect(lambda: bpmReadOEDA_Action.performAction())  
        bpmReadBoth_button.clicked.connect(lambda: bpmReadBoth_Action.performAction())     
        bpmSaveBoth_button.clicked.connect(lambda: bpmSaveBoth_Action.performAction())
        
        upper_view = QWidget()

        hlayout = QHBoxLayout(upper_view)
        hlayout.addWidget(bpmReadPhaseOffset_button)
        hlayout.addWidget(bpmReadOEDA_button)
        hlayout.addWidget(bpmReadBoth_button)
        hlayout.addWidget(bpmSaveBoth_button)
        
        #---- Border Layout for self.bpms_state_cntrl tab window
        border_layout = BorderLayout(None)
        border_layout.addWidget(self.bpms_params_table_view, Position.Center)
        border_layout.addWidget(upper_view, Position.North)
        self.bpms_state_cntrl.getMainWidget().setLayout(border_layout)
        
        #---- Main window layout
        border_layout = BorderLayout(None, +2)
        border_layout.addWidget(self.tabs, Position.Center)

        self.mainWidget.setLayout(border_layout)

    def getTabName(self):
        """ Returns the tab name the controller """
        return self.tab_name

    def getMainWidget(self):
        """ Returns the mainWidget (window) of InitState_Cntrl """
        return self.mainWidget
        
    def getTabWidget(self,name):
        """ Returns the mainWidget of the particular 1st level tab """
        widget = None
        for ind in range(self.tabs.count()):
            if(self.tabs.tabText(ind) == name):
                return self.tabs.widget(ind)
        return widget

    def dumpCntrlDataToDA(self,parent_da):
        """ Puts this controller data into the Data Adaptor """
        return
       
    def readCntrlDataFromDA(self,parent_da):
        """ Reads data for this controller from the Data Adaptor """
        return
        
    def stopAllThreads(self):
        """ Stops all threads of this controller """
        #self.scanStopper.setSetToStop(True)
        return

