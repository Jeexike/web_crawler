import sys
import os
from PyQt5.QtWidgets import QApplication
from main_window import HabrParserApp

if __name__ == "__main__":
    os.environ["QT_QPA_PLATFORM"] = "xcb"
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = "/home/jeexike/Документы/PRAC/my_venv/lib/python3.12/site-packages/PyQt5/Qt5/plugins"
    
    app = QApplication(sys.argv)
    window = HabrParserApp()
    window.show()
    sys.exit(app.exec_())