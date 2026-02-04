"""
This is a collection of GUI StyleSheet for LACE Wizard
"""

class StyleSheetFactory:
    
    @staticmethod
    def pushButtonStyleSheet():
        """ Qt StyleSheet for QPushButton used inside LACE Wizard """
        buttons_style = """
            QPushButton {
                background-color: lightblue;
                border-style: outset;
                border-width: 2px;
                border-radius: 10px;
                border-color: beige;
                font: bold 14px;
                min-width: 4em;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: lightcyan;
            }
            QPushButton:pressed {
                background-color: red; /* Color when pressed */
                border-style: inset;   /* Visual effect when pressed */
            }"""
        return buttons_style
        
        
    @staticmethod
    def groupBoxStyleSheet():
        groupBox_style = """
            QGroupBox {
                font-weight: bold;
                border: 3px solid lightblue;
                border-radius: 5px;
                margin-top: 10px; /* Space for the title */
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left; /* Position of the title */
                padding: 0 3px;
            }
        """
        return groupBox_style