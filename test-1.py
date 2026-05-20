"""
This is a test script
"""

import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QGroupBox, QLabel

class Window(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Create the Group Box with a title
        groupBox = QGroupBox("My Named Border")
        
        # Create a layout for the group box
        groupBoxLayout = QVBoxLayout()
        groupBoxLayout.addWidget(QLabel("Content goes here"))
        
        # Set the layout on the group box
        groupBox.setLayout(groupBoxLayout)

        # Main layout for the window
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(groupBox)
        self.setLayout(mainLayout)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Window()
    w.show()
    sys.exit(app.exec())
