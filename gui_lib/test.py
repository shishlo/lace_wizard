import sys

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

class Window(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.btnOne = QPushButton(
            text="Click me!", parent=self
        )
        self.btnOne.setFixedSize(100, 60)
        self.btnOne.clicked.connect(self.onClick)
        self.btnTwo = QPushButton(parent=self)
        self.btnTwo.setFixedSize(100, 60)
        self.btnTwo.setEnabled(False)
        self.btnTwo.clicked.connect(self.onClick)
        layout = QVBoxLayout()
        layout.addWidget(self.btnOne)
        layout.addWidget(self.btnTwo)
        self.setLayout(layout)

    def onClick(self):
        sender = self.sender()
        icon = sender.icon()

        if sender is self.btnOne:
            sender.setText("")
            sender.setIcon(QIcon())
            sender.setEnabled(False)
            self.btnTwo.setEnabled(True)
            self.btnTwo.setText("Click me!")
            self.btnTwo.setIcon(icon)
            self.btnTwo.setIconSize(QSize(20, 20))
        elif sender is self.btnTwo:
            sender.setText("")
            sender.setIcon(QIcon())
            sender.setEnabled(False)
            self.btnOne.setEnabled(True)
            self.btnOne.setText("Click me!")
            self.btnOne.setIcon(icon)
            self.btnOne.setIconSize(QSize(30, 30))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec())
