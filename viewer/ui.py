import os
import sys
import ctypes
import re
import pythoncom
import atexit
import json
import win32gui
import win32con
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton, QLineEdit, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea, QMessageBox,
    QFileDialog, QApplication, QDialog, QDialogButtonBox, QAbstractItemView, QDesktopWidget,
    QProgressDialog
)
from PyQt5.QtGui import QPixmap, QIcon, QFont, QIntValidator
from PyQt5.QtCore import Qt, QTimer
from decryptor import decrypt_file, is_expired
from converter import convert_to_images
import psutil

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class PasswordDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Enter Password")
        self.setModal(True)
        icon_path = resource_path("viewer/assets/logo.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setMinimumSize(600, 250)
        font = QFont('Segoe UI', 10)
        self.input = QLineEdit()
        self.input.setFont(font)
        self.input.setEchoMode(QLineEdit.Password)
        self.input.setPlaceholderText("Enter decryption password")
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.setFont(font)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        label = QLabel("Decryption Password")
        label.setFont(font)
        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(self.input)
        layout.addWidget(button_box)
        self.setLayout(layout)

    def get_password(self):
        if self.exec_() == QDialog.Accepted:
            return self.input.text().strip()
        return None

class ViewerUI(QMainWindow):
    def __init__(self):
        super().__init__()

        pythoncom.CoInitialize()
        atexit.register(pythoncom.CoUninitialize)

        self.setWindowTitle("DRM File Viewer")
        self.setWindowIcon(QIcon(resource_path("viewer/assets/logo.png")))

        app = QApplication.instance() or QApplication([])
        base_font = QFont('Segoe UI', 10)
        app.setFont(base_font)
        self.setFont(base_font)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.password_cache = {} 
        self.current_folder = None
        self.current_files = []
        self.current_file_data = {} 
        self.folder_mode = True 
        self.expiry_timer = QTimer(self)
        self.expiry_timer.timeout.connect(self.check_current_folder_expiry)
        self.expiry_timer.start(5000)

        self.current_file = None
        self.current_page = 0
        self.total_pages = 1
        self.page_images = [] 
        self.current_watermark_text = "DRM PROTECTED"

        self.init_fonts(base_font)
        self.init_styles()
        self.init_ui(base_font)

        self.setStyleSheet(
            """
            QWidget { background-color: #2d2d2d; color: #f0f0f0; font-family: 'Segoe UI'; font-size:7.5pt; }
            QLineEdit, QDateTimeEdit { padding:7.5px; border:0.75px solid #666; border-radius:6px; background-color: #3a3a3a; color: #fff; font-size:7.5pt; }
            QPushButton { background-color: #0078d7; color: white; border-radius:3px; padding:3.75px 6.75px; min-height:9px; font-weight: bold; font-size:7.5pt; }
            QPushButton:hover { background-color: #005a9e; }
            QTableWidget { background-color: #232323; color: #fff; gridline-color: #444; font-size:7.5pt; }
            QTableWidget::item { background-color: #232323; color: #fff; padding:6px; }
            QTableWidget::item:selected { background-color: #90D5FF; color: #232323; }
            QHeaderView::section { background:#0078d7; color:#fff; min-height:13.5px; padding:3.375px 6.75px; border:none; font-weight:bold; font-size:7.5pt; }
            """
        )
        self.show_file_list([])
        QTimer.singleShot(100, self.enable_protections)

        screen = QDesktopWidget().availableGeometry(self)
        self.setGeometry(screen.x(), screen.y(), screen.width(), screen.height())
        self.showMaximized()

    def init_fonts(self, base_font):
        self.base_font = base_font
        self.zoom_font = QFont(base_font)

    def init_styles(self):
        pass

    def init_ui(self, base_font):
        layout = QVBoxLayout()
        layout.setContentsMargins(25, 5, 25, 0)
        layout.setSpacing(12)
        top_bar = QHBoxLayout()
        app_name_label = QLabel("DRM File Viewer")
        app_name_label.setAlignment(Qt.AlignCenter)
        app_name_label.setStyleSheet("font-size:22.5pt; font-weight:bold; color:#f0f0f0;")
        logo_label = QLabel()
        logo_path = resource_path("viewer/assets/logo.png")
        if os.path.exists(logo_path):
            logo_pixmap = QPixmap(logo_path).scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(logo_pixmap)
            logo_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        top_bar.addStretch()
        top_bar.addWidget(app_name_label)
        top_bar.addStretch()
        top_bar.addWidget(logo_label)
        layout.addLayout(top_bar)
        self.open_file_btn = QPushButton("Select File")
        self.open_file_btn.setFont(base_font)
        self.open_file_btn.clicked.connect(self.open_encrypted_file_dialog)
        layout.addWidget(self.open_file_btn)
        self.folder_table = QTableWidget()
        self.folder_table.setFont(base_font)
        self.folder_table.setColumnCount(1)
        self.folder_table.setHorizontalHeaderLabels(["Files"])
        self.folder_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.folder_table.verticalHeader().setVisible(False)
        self.folder_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.folder_table.setSelectionMode(QTableWidget.SingleSelection)
        self.folder_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.folder_table.cellDoubleClicked.connect(self.on_file_double_clicked)
        layout.addWidget(self.folder_table, stretch=1)
        self.back_btn = QPushButton("←  Back to Files")
        self.back_btn.setFont(base_font)
        self.back_btn.setVisible(False)
        self.back_btn.clicked.connect(self.on_back_to_files_clicked)
        layout.addWidget(self.back_btn)
        self.viewer_label = QLabel("")
        self.viewer_label.setAlignment(Qt.AlignCenter)
        self.viewer_label.setFont(QFont(base_font))
        self.viewer_label.setStyleSheet("color: #fff;")
        self.viewer_label.setMinimumSize(300, 300)
        self.viewer_label.setWordWrap(True)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.viewer_label)
        self.scroll_area.setWidgetResizable(False)
        layout.addWidget(self.scroll_area, stretch=1)
        nav_layout = QHBoxLayout()
        self.prev_btn = QPushButton("Previous Page")
        self.next_btn = QPushButton("Next Page")
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        self.prev_btn.clicked.connect(self.show_prev_page)
        self.next_btn.clicked.connect(self.show_next_page)
        nav_layout.addStretch()
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.next_btn)
        nav_layout.addStretch()
        layout.addLayout(nav_layout)
        zoom_layout = QHBoxLayout()
        zoom_layout.addStretch()
        zoom_label = QLabel("Zoom (%):")
        zoom_label.setFont(QFont('Segoe UI', 8))
        self.current_zoom = 100
        self.zoom_input = QLineEdit(str(self.current_zoom))
        self.zoom_input.setFont(QFont('Segoe UI', 8))
        self.zoom_input.setFixedWidth(48)
        self.zoom_input.setAlignment(Qt.AlignCenter)
        self.zoom_input.setValidator(QIntValidator(10, 1200, self))
        self.zoom_input.editingFinished.connect(self.on_zoom_input_changed)
        self.zoom_input.setStyleSheet("padding:2px 6px;")
        zoom_layout.addWidget(zoom_label)
        zoom_layout.addWidget(self.zoom_input)
        zoom_layout.addStretch()
        layout.addLayout(zoom_layout)
        self.update_viewer_page()
        container = QWidget()
        container.setLayout(layout)
        self.central_widget.setLayout(QVBoxLayout())
        self.central_widget.layout().addWidget(container)
        self.folder_table.setRowCount(0)
        self.viewer_label.setText("")

    def open_encrypted_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File", "", "Encrypted Files (*.mylock)")
        if not file_path:
            return
        if not file_path.endswith('.mylock'):
            self.show_error("Invalid!! file does not exist.")
            return
        self.current_encrypted_file = file_path
        folder_name = os.path.basename(file_path).replace(".mylock", "")
        self.unlock_and_show_files(folder_name, file_path)

    def on_back_to_files_clicked(self):
        self.page_images = []
        self.current_page = 0
        self.total_pages = 1
        self.viewer_label.setText("")
        self.update_viewer_page()
        self.back_btn.setVisible(False)
        if self.current_files:
            self.show_file_list(self.current_files)
            self.open_file_btn.setVisible(True)
            self.folder_table.setVisible(True)
        else:
            self.show_file_list([])
            self.open_file_btn.setVisible(True)
            self.folder_table.setVisible(True)

    def unlock_and_show_files(self, folder_name, filename):
        try:
            with open(filename, 'r') as f:
                file_data = json.load(f)
            if file_data.get('magic') != 'MYDRM01':
                self.show_error("Invalid!! file does not exist.")
                return
            metadata = file_data.get('metadata', {})
            allowed_macs = metadata.get('allowed_macs', [])
            if allowed_macs:
                all_macs = set()
                for iface, addrs in psutil.net_if_addrs().items():
                    for addr in addrs:
                        if addr.family == psutil.AF_LINK or getattr(addr, 'family', None) == 17:
                            mac = addr.address.replace('-', ':').upper()
                            if re.match(r'^([0-9A-F]{2}:){5}[0-9A-F]{2}$', mac):
                                all_macs.add(mac)
                allowed_macs = [m.replace('-', ':').strip().upper() for m in allowed_macs]
                if not any(mac in allowed_macs for mac in all_macs):
                    self.reset_to_initial_state()
                    self.show_error("Invalid!! file does not exist.")
                    return
            if is_expired(metadata):
                self.reset_to_initial_state()
                self.show_error(f"Invalid!! file does not exist.\n[{filename}]")
                return
            dialog = PasswordDialog()
            password = dialog.get_password()
            if not password:
                return
            
            try:
                file_paths, metadata = decrypt_file(filename, password)
                self.current_watermark_text = metadata.get("watermark_text", "DRM PROTECTED")
                self.current_folder = folder_name
                self.current_files = file_paths
                self.current_file_data = {os.path.basename(f): f for f in file_paths}
                self.show_file_list(file_paths)
            except Exception as e:
                self.show_error(f"Invalid!! file does not exist.\n[{filename}]")
                
        except Exception as e:
            self.show_error(f"Invalid!! file does not exist.\n[{filename}]")

    def show_file_list(self, file_paths):
        self.folder_mode = False
        if file_paths:
            self.folder_table.setColumnCount(1)
            self.folder_table.setHorizontalHeaderLabels(["Files (double-click to view)"])
            self.folder_table.setRowCount(len(file_paths))
            for row, f in enumerate(file_paths):
                self.folder_table.setItem(row, 0, QTableWidgetItem(os.path.basename(f)))
        else:
            self.folder_table.setColumnCount(1)
            self.folder_table.setHorizontalHeaderLabels(["Files"])
            self.folder_table.setRowCount(0)
        self.viewer_label.setText("")

    def update_viewer_page(self):
        if not self.page_images:
            self.viewer_label.setText("No content to display.")
            self.viewer_label.setAlignment(Qt.AlignCenter)
            self.viewer_label.resize(self.scroll_area.viewport().size())
            self.viewer_label.setPixmap(QPixmap())
            return
        page = self.page_images[self.current_page]
        if isinstance(page, str) and page.lower().endswith((".jpg", ".jpeg", ".png", ".bmp")):
            pixmap = QPixmap(page)
            if not pixmap.isNull():
                area_width = self.scroll_area.viewport().width()
                scale_factor = (self.current_zoom / 100) * (area_width / pixmap.width())
                w = int(pixmap.width() * scale_factor)
                h = int(pixmap.height() * scale_factor)
                scaled_pixmap = pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.viewer_label.setPixmap(scaled_pixmap)
                self.viewer_label.resize(scaled_pixmap.size())
                self.viewer_label.setAlignment(Qt.AlignCenter)
                self.viewer_label.setText("")
            else:
                self.viewer_label.setPixmap(QPixmap())
                self.viewer_label.resize(self.viewer_label.minimumSize())
                self.viewer_label.setText("Could not load image.")
        elif isinstance(page, str) and (page.lower().endswith(".txt") or page.lower().endswith(".md")):
            with open(page, "r", encoding="utf-8") as f:
                self.viewer_label.setFont(QFont("Segoe UI", 14))
                self.viewer_label.setText(f.read())
                self.viewer_label.setAlignment(Qt.AlignCenter)
                self.viewer_label.setPixmap(QPixmap())
                self.viewer_label.adjustSize()
        else:
            self.viewer_label.setPixmap(QPixmap())
            self.viewer_label.setText(f"Page {self.current_page + 1} of {self.total_pages}")
            self.viewer_label.resize(self.viewer_label.minimumSize())
        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled(self.current_page < self.total_pages - 1)

    def check_current_folder_expiry(self):
        if self.current_folder and hasattr(self, 'current_encrypted_file') and self.current_encrypted_file:
            try:
                with open(self.current_encrypted_file, 'r') as f:
                    file_data = json.load(f)
                metadata = file_data.get('metadata', {})
                if is_expired(metadata):
                    self.reset_to_initial_state()
                    self.show_error("Invalid!! File does not exist")
            except Exception:
                pass

    def show_error(self, message):
        match = re.search(r'([a-zA-Z0-9_\-]+\.mylock)', message)
        if match:
            filename = match.group(1)
            message = re.sub(r'.*?([a-zA-Z0-9_\-]+\.mylock)', filename, message)
        QMessageBox.critical(self, "Error", message)

    def enable_protections(self):
        self.enable_anti_screenshot()
        self.disable_hotkeys()
        self.start_clipboard_cleaner()

    def enable_anti_screenshot(self):
        try:
            hwnd = int(self.winId())
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 1)
            ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)
        except Exception:
            pass

    def disable_hotkeys(self):
        try:
            try:
                win32gui.UnregisterHotKey(None, 1)
                win32gui.UnregisterHotKey(None, 2)
            except:
                pass
            win32gui.RegisterHotKey(None, 1, 0, win32con.VK_SNAPSHOT)
            win32gui.RegisterHotKey(None, 2, win32con.MOD_WIN, 0x47)
        except Exception as e:
            print("Hotkey registration failed:", e)

    def start_clipboard_cleaner(self):
        def clean():
            QApplication.clipboard().clear()
            QTimer.singleShot(3000, clean)
        clean()

    def closeEvent(self, event):
        try:
            win32gui.UnregisterHotKey(None, 1)
            win32gui.UnregisterHotKey(None, 2)
        except Exception:
            pass
        super().closeEvent(event)

    def show_prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_viewer_page()

    def show_next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_viewer_page()

    def on_zoom_input_changed(self):
        try:
            value = int(self.zoom_input.text())
            if value < 10:
                value = 10
            elif value > 1200:
                value = 1200
            self.current_zoom = value
            self.zoom_input.setText(str(self.current_zoom))
            self.update_viewer_page()
        except ValueError:
            self.zoom_input.setText(str(self.current_zoom))

    def on_file_double_clicked(self, row, column):
        if not self.current_files:
            return
        file_name = self.folder_table.item(row, 0).text()
        file_path = self.current_file_data.get(file_name)
        if not file_path or not os.path.exists(file_path):
            self.show_error("Invalid!! file does not exist.")
            return
        self.open_file_btn.setVisible(False)
        self.folder_table.setVisible(False)
        self.back_btn.setVisible(True)
        if file_path.lower().endswith((".jpg", ".jpeg", ".png", ".bmp")):
            self.page_images = [file_path]
            self.current_page = 0
            self.total_pages = 1
            self.update_viewer_page()
        elif file_path.lower().endswith((".txt", ".md")):
            self.page_images = [file_path]
            self.current_page = 0
            self.total_pages = 1
            self.update_viewer_page()
        elif file_path.lower().endswith(".pdf"):
            try:
                images = convert_to_images(file_path, watermark_text=self.current_watermark_text)
                if images:
                    self.page_images = images
                    self.current_page = 0
                    self.total_pages = len(images)
                    self.update_viewer_page()
                else:
                    self.show_error("Could not render PDF file.")
            except Exception as e:
                self.show_error(f"Could not render PDF file: {e}")
        else:
            self.show_error("Unsupported file type.")

    def reset_to_initial_state(self):
        self.current_folder = None
        self.current_files = []
        self.current_file_data = {}
        self.page_images = []
        self.current_page = 0
        self.total_pages = 1
        self.viewer_label.clear()
        self.viewer_label.setText("")
        self.viewer_label.setPixmap(QPixmap())
        self.folder_table.setRowCount(0)
        self.folder_table.setColumnCount(1)
        self.folder_table.setHorizontalHeaderLabels(["Files"])
        self.folder_table.setVisible(True)
        self.scroll_area.setVisible(True)
        self.back_btn.setVisible(False)
        self.open_file_btn.setVisible(True)

