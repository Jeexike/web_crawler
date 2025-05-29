from PyQt5.QtWidgets import (QTableWidgetItem, QDialog, QDialogButtonBox, 
                            QCalendarWidget, QVBoxLayout)
from PyQt5.QtCore import Qt
import webbrowser

class DatePickerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Выберите дату")
        self.setModal(True)
        self.setFixedSize(400, 300)
        
        layout = QVBoxLayout()
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        layout.addWidget(self.calendar)
        layout.addWidget(buttons)
        self.setLayout(layout)
    
    def selected_date(self):
        return self.calendar.selectedDate()

class ClickableTableWidgetItem(QTableWidgetItem):
    def __init__(self, text, link):
        super().__init__(text)
        self.link = link
        self.setForeground(Qt.blue)
        self.setFlags(self.flags() | Qt.ItemIsEnabled)

    def open_link(self):
        webbrowser.open(self.link)