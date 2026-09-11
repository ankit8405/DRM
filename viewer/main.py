import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from ui import ViewerUI
import sys
import atexit

try:
    import pythoncom
    pythoncom.CoInitialize()
    atexit.register(pythoncom.CoUninitialize)
except ImportError:
    print("Warning: pywin32 is not installed. Clipboard-related features may not work properly.")

def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    viewer = ViewerUI()
    viewer.showMaximized()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()