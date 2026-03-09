import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2) 
except Exception:
    pass
import sys, os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from ui import EncryptorUI


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    window = EncryptorUI()

    window.showMaximized()
    sys.exit(app.exec_())

if __name__ == "__main__":
    os.makedirs("files", exist_ok=True)
    main()
