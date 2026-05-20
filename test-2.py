"""
This is a test script
"""
from PySide6.QtWidgets import QApplication, QGroupBox, QVBoxLayout, QWidget, QLabel
from PySide6.QtCore import Qt

app = QApplication([])

# 1. Create the QGroupBox with a title
group_box = QGroupBox("Group Title")

# 2. Define the style sheet for the border
group_box.setStyleSheet("""
    QGroupBox {
        font-weight: bold;
        border: 2px solid gray;
        border-radius: 5px;
        margin-top: 10px; /* Space for the title */
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left; /* Position of the title */
        padding: 0 3px;
    }
""")

# 3. Add layout and widgets
layout = QVBoxLayout()
layout.addWidget(QLabel("Content 1"))
layout.addWidget(QLabel("Content 2"))
group_box.setLayout(layout)

group_box.show()
app.exec()