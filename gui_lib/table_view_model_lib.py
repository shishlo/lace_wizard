"""
Customized for LACE QtWidjets:
QTableView
QStandardItemModel
"""

from PySide6.QtWidgets import QTableView
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QStandardItemModel, QStandardItem

class LACE_QTableView(QTableView):
    """
    It will update view of the table each time is shown.
    The Table Model should implement tableChanged() method.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.verticalHeader().setDefaultSectionSize(20) 
        
    def showEvent(self, event):
        """Runs automatically when the window is shown."""
        super().showEvent(event)
        self.model().tableChanged()
        
class LACE_DataTableModel(QStandardItemModel):
    def __init__(self):
        super().__init__()
        self.dependent_tables = []
        
    def addDependentTableModel(self,dependent_table_model):
        self.dependent_tables.append(dependent_table_model)
        
    def updateDependentTables(self):
        for dependent_table_model in self.dependent_tables:
            dependent_table_model.tableChanged()

    @staticmethod
    def _updateBoolItem(bool_val,bool_item):
        """ Auxiliary function sets item to Checked or Unchecked state """
        if(bool_val):
            bool_item.setCheckState(Qt.Checked)
        else:
            bool_item.setCheckState(Qt.Unchecked)
            
    @staticmethod  
    def _getValueOfBoolItem(bool_item):
        """ Auxiliary function returns True or False for bool_item """
        if(bool_item.checkState() in (Qt.Checked,)):
            return True
        if(bool_item.checkState() in (Qt.Unchecked,)):
            return False
        return None

    def _updateItemsFromData(self):
        """
        Synchronize Items in the TableModel with external data source.
        """
        pass

    def tableChanged(self):
        self._updateItemsFromData()
        rows = self.rowCount()
        cols = self.columnCount()
        index_top_left = self.indexFromItem(self.item(0,0))
        index_bottom_right = self.indexFromItem(self.item(rows-1,cols-1))
        self.dataChanged.emit(index_top_left,index_bottom_right)
        self.updateDependentTables()

