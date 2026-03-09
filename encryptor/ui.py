from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QLineEdit, QVBoxLayout, QHBoxLayout, QDateTimeEdit, 
    QMainWindow, QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, 
    QAbstractItemView, QListWidget, QListWidgetItem, QSizePolicy, QApplication, QAbstractSpinBox, QInputDialog, QDesktopWidget,
    QProgressDialog, QProgressBar
)
from PyQt5.QtGui import QPixmap, QIcon, QFont
from PyQt5.QtCore import QDateTime, Qt, QTimer, pyqtSignal, QThread
import os
import re
import json
from datetime import datetime
import sys

from encryptor import encrypt_files

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class EncryptorUI(QMainWindow):
    """DRM Encryptor main window"""
    def __init__(self):
        super().__init__()

        self.setWindowTitle("DRM File Encryptor")
        self.setWindowIcon(QIcon(resource_path("encryptor/assets/logo.png")))

        app = QApplication.instance() or QApplication([])
        base_font = QFont('Segoe UI', 10)
        app.setFont(base_font)

        self.setStyleSheet(
            """
            QWidget { background:#2d2d2d; color:#f0f0f0; font-family:'Segoe UI'; font-size:7.5pt; }
            QLineEdit, QDateTimeEdit { padding:7.5px; border:0.75px solid #666; border-radius:6px; background:#3a3a3a; color:#fff; font-size:7.5pt; }
            QPushButton { background:#0078d7; color:#fff; border-radius:3px; padding:3.75px 6.75px; min-height:9px; font-weight:bold; font-size:7.5pt; }
            QPushButton:hover { background:#005a9e; }
            QTableWidget { background-color: #232323; color: #fff; gridline-color: #444; font-size:7.5pt; }
            QTableWidget::item { background-color: #232323; color: #fff; padding:6px; }
            QTableWidget::item:selected { background-color: #90D5FF; color: #232323; }
            QHeaderView::section { background:#0078d7; color:#fff; min-height:13.5px; padding:3.375px 6.75px; border:none; font-weight:bold; font-size:7.5pt; }
            """
        )

        self.current_package_files = []
        self.current_package_name = ""
        self.encrypting_now = False

        logo = QLabel()
        pix = QPixmap(resource_path("encryptor/assets/logo.png"))
        if not pix.isNull():
            logo.setPixmap(pix.scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        app_label = QLabel("DRM File Encryptor")
        app_label.setStyleSheet("font-size:22.5pt; font-weight:bold;")
        top_bar = QHBoxLayout()
        top_bar.addStretch()
        top_bar.addWidget(app_label)
        top_bar.addStretch()
        top_bar.addWidget(logo)

        self.select_files_btn = QPushButton("Select File")
        self.select_files_btn.clicked.connect(self.select_files)

        self.delete_file_btn = QPushButton("Delete File")
        self.delete_file_btn.clicked.connect(self.delete_selected_file)
        self.delete_file_btn.setEnabled(False)

        self.done_btn = QPushButton("Done")
        self.done_btn.clicked.connect(self.finalize_package)
        self.done_btn.setEnabled(False)

        self.file_list_widget = QListWidget()
        self.file_list_widget.setFont(base_font)
        self.file_list_widget.itemSelectionChanged.connect(
            lambda: self.delete_file_btn.setEnabled(self.file_list_widget.currentRow() >= 0)
        )

        self.package_name_input = QLineEdit()
        self.package_name_input.setPlaceholderText("Folder name")
        self.package_name_input.setFont(base_font)
        self.package_name_input.textChanged.connect(self.update_encrypt_btn_state)

        self.password_input = QLineEdit()
        self.password_input.setFont(base_font)
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Encryption password")
        self.password_input.setEnabled(False)
        self.password_input.textChanged.connect(self.update_encrypt_btn_state)

        self.mac_input = QLineEdit()
        self.mac_input.setFont(base_font)
        self.mac_input.setPlaceholderText("MAC ID(s), separate multiple with ';'")
        self.mac_input.setEnabled(False)
        self.mac_input.textChanged.connect(self.update_encrypt_btn_state)

        self.start_time = QDateTimeEdit(QDateTime.currentDateTime())
        self.start_time.setDisplayFormat("dd-MM-yyyy HH:mm")
        self.start_time.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.start_time.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.start_time.setFont(base_font)
        self.start_time.setEnabled(False)
        self.start_time.dateTimeChanged.connect(self.update_encrypt_btn_state)
        self.start_time.setMinimumWidth(0)
        self.start_time.setMaximumWidth(self.start_time.maximumWidth())

        self.end_time = QDateTimeEdit(QDateTime.currentDateTime().addDays(7))
        self.end_time.setDisplayFormat("dd-MM-yyyy HH:mm")
        self.end_time.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.end_time.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.end_time.setFont(base_font)
        self.end_time.setEnabled(False)
        self.end_time.dateTimeChanged.connect(self.update_encrypt_btn_state)
        self.end_time.setMinimumWidth(0)
        self.end_time.setMaximumWidth(self.end_time.maximumWidth())

        start_time_row = QHBoxLayout()
        start_time_row.addWidget(self.start_time)

        end_time_row = QHBoxLayout()
        end_time_row.addWidget(self.end_time)

        self.watermark_text_input = QLineEdit()
        self.watermark_text_input.setFont(base_font)
        self.watermark_text_input.setPlaceholderText("Watermark text (default: DRM PROTECTED)")
        self.watermark_text_input.setEnabled(False)
        self.watermark_text_input.textChanged.connect(self.update_encrypt_btn_state)

        self.encrypt_btn = QPushButton("Upload Folder")
        self.encrypt_btn.setEnabled(False)
        self.encrypt_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.encrypt_btn.clicked.connect(self.encrypt_selected_package)

        self.rename_folder_btn = QPushButton("Rename Folder")
        self.rename_folder_btn.clicked.connect(self.rename_selected_folder)
        self.rename_folder_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.delete_folder_btn = QPushButton("Delete Folder")
        self.delete_folder_btn.clicked.connect(self.delete_selected_folder)
        self.delete_folder_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.folders_table = QTableWidget()
        self.folders_table.setColumnCount(2)
        self.folders_table.setHorizontalHeaderLabels(["Name", "Status"])
        self.folders_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.folders_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.folders_table.setColumnWidth(1, 180)
        self.folders_table.verticalHeader().setVisible(False)
        self.folders_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.folders_table.setFont(base_font)
        self.folders_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.folders_table.setMinimumHeight(425)

        file_btn_row = QHBoxLayout()
        file_btn_row.addWidget(self.select_files_btn)
        file_btn_row.addWidget(self.delete_file_btn)
        file_btn_row.addWidget(self.done_btn)

        folder_btn_row = QHBoxLayout()
        folder_btn_row.addWidget(self.encrypt_btn)
        folder_btn_row.addWidget(self.rename_folder_btn)
        folder_btn_row.addWidget(self.delete_folder_btn)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(25, 5, 25, 0)
        main_layout.setSpacing(12)
        main_layout.addSpacing(10)
        main_layout.addLayout(top_bar)
        main_layout.addLayout(file_btn_row)
        main_layout.addWidget(self.file_list_widget)
        main_layout.addWidget(self.package_name_input)
        main_layout.addWidget(self.password_input)
        main_layout.addWidget(self.mac_input)
        main_layout.addLayout(start_time_row)
        main_layout.addLayout(end_time_row)
        main_layout.addWidget(self.watermark_text_input)
        main_layout.addLayout(folder_btn_row)
        main_layout.addWidget(self.folders_table)
        main_layout.addStretch(1)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.file_list_widget.setVisible(False)
        self.load_encrypted_folders()

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.load_encrypted_folders)
        self.status_timer.start(5000)

        screen = QDesktopWidget().availableGeometry(self)
        self.setGeometry(screen.x(), screen.y(), screen.width(), screen.height())
        self.showMaximized()

    def update_encrypt_btn_state(self):
        """Update the encrypt button state based on form completion"""
        has_files = bool(self.current_package_files)
        has_folder = bool(self.package_name_input.text().strip())
        has_password = bool(self.password_input.text())
        has_time = self.start_time.dateTime() < self.end_time.dateTime()
        self.encrypt_btn.setEnabled(has_files and has_folder and has_password and has_time)

    def delete_selected_folder(self):
        """Delete the selected folder from the table"""
        row = self.folders_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a folder to delete.")
            return
        filename = self.folders_table.item(row, 0).text()
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        files_dir = os.path.join(base_dir, "files")
        file_path = os.path.join(files_dir, filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                QMessageBox.information(self, "Folder Deleted", f"The folder '{filename}' has been deleted.")
            except Exception as e:
                QMessageBox.warning(self, "Delete Failed", f"Could not delete '{filename}': {e}")
        else:
            QMessageBox.warning(self, "Not Found", f"Could not find the folder '{filename}' to delete.")
        self.load_encrypted_folders()

    def rename_selected_folder(self):
        """Rename the selected folder"""
        row = self.folders_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a folder to rename.")
            return
        old_filename = self.folders_table.item(row, 0).text()
        new_folder_name, ok = QInputDialog.getText(self, "Rename Folder", "Enter new folder name:")
        if not ok or not new_folder_name.strip():
            return
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        files_dir = os.path.join(base_dir, "files")
        old_file_path = os.path.join(files_dir, old_filename)
        new_file_path = os.path.join(files_dir, new_folder_name + ".mylock")
        if os.path.exists(new_file_path):
            QMessageBox.warning(self, "Rename Failed", f"A folder named '{new_folder_name}' already exists.")
            return
        try:
            with open(old_file_path, 'r') as f:
                file_data = f.read()
            with open(new_file_path, 'w') as f:
                f.write(file_data)
            os.remove(old_file_path)
            QMessageBox.information(self, "Folder Renamed", f"The folder has been renamed to '{new_folder_name}'.")
        except Exception as e:
            QMessageBox.warning(self, "Rename Failed", f"Could not rename folder: {e}")
        self.load_encrypted_folders()

    def load_encrypted_folders(self):
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        files_dir = os.path.join(base_dir, "files")
        if not os.path.exists(files_dir):
            os.makedirs(files_dir)
        encrypted_folders = []
        for filename in os.listdir(files_dir):
            if filename.endswith(".mylock"):
                encrypted_folders.append(filename)
        self.folders_table.setColumnCount(2)
        self.folders_table.setHorizontalHeaderLabels(["Name", "Status"])
        self.folders_table.setRowCount(len(encrypted_folders))
        for row, filename in enumerate(sorted(encrypted_folders)):
            name_item = QTableWidgetItem(filename)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.folders_table.setItem(row, 0, name_item)
            file_path = os.path.join(files_dir, filename)
            status_item = QTableWidgetItem()
            try:
                with open(file_path, 'r') as f:
                    file_data = json.load(f)
                metadata = file_data.get('metadata', {})
                start = metadata.get('start')
                end = metadata.get('end')
                expired = False
                if start and end:
                    try:
                        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                        now = datetime.now(end_dt.tzinfo) if end_dt.tzinfo else datetime.now()
                        expired = now > end_dt
                    except Exception:
                        expired = False
                else:
                    expired = True
                if expired:
                    status_item.setText("Expired")
                    status_item.setForeground(Qt.red)
                    font = status_item.font()
                    font.setBold(True)
                    status_item.setFont(font)
                else:
                    status_item.setText("")
            except Exception:
                status_item.setText("")
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            self.folders_table.setItem(row, 1, status_item)
        for row in range(self.folders_table.rowCount()):
            self.folders_table.setRowHeight(row, 24)
        self.folders_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.folders_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.folders_table.setColumnWidth(1, 180)
        self.folders_table.verticalHeader().setVisible(False)
        font = self.folders_table.font()
        

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files to Add")
        if not files:
            return
        added = False
        for f in files:
            if f not in self.current_package_files:
                self.current_package_files.append(f)
                self.file_list_widget.addItem(QListWidgetItem(os.path.basename(f)))
                added = True
        if added:
            self.file_list_widget.setVisible(True)
            self.done_btn.setEnabled(True)
            self.select_files_btn.setEnabled(True)
            self.package_name_input.setEnabled(False)
            self.password_input.setEnabled(False)
            self.mac_input.setEnabled(False)
            self.start_time.setEnabled(False)
            self.end_time.setEnabled(False)
            self.watermark_text_input.setEnabled(False)
        self.update_encrypt_btn_state()

    def delete_selected_file(self):
        row = self.file_list_widget.currentRow()
        if row >= 0:
            reply = QMessageBox.question(self, "Confirm Delete", "Are you sure you want to delete this file?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.current_package_files.pop(row)
                self.file_list_widget.takeItem(row)
                if not self.current_package_files:
                    self.file_list_widget.setVisible(False)
                    self.delete_file_btn.setEnabled(False)
                    self.done_btn.setEnabled(False)
        self.update_encrypt_btn_state()

    def finalize_package(self):
        reply = QMessageBox.question(self, "Confirm Done", "Selected all files?", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self.select_files_btn.setEnabled(False)
        self.done_btn.setEnabled(False)
        self.package_name_input.setEnabled(True)
        self.password_input.setEnabled(True)
        self.mac_input.setEnabled(True)
        self.start_time.setEnabled(True)
        self.end_time.setEnabled(True)
        self.watermark_text_input.setEnabled(True)
        self.file_list_widget.setVisible(False)
        self.update_encrypt_btn_state()

    def encrypt_selected_package(self):
        if self.encrypting_now:
            return
        self.encrypting_now = True
        
        if not self.current_package_files:
            QMessageBox.critical(self, "No Files", "Please select files to encrypt.")
            self.encrypting_now = False
            return
        if not self.package_name_input.text().strip():
            QMessageBox.critical(self, "No Folder Name", "Please enter the folder name.")
            self.encrypting_now = False
            return
        password = self.password_input.text().strip()
        if not password:
            QMessageBox.critical(self, "No Password", "Please enter the password.")
            self.encrypting_now = False
            return
        if not self.start_time.dateTime():
            QMessageBox.critical(self, "No Start Time", "Please enter the start date & time.")
            self.encrypting_now = False
            return
        if not self.end_time.dateTime():
            QMessageBox.critical(self, "No End Time", "Please enter the end date & time.")
            self.encrypting_now = False
            return
        if self.end_time.dateTime() < QDateTime.currentDateTime():
            QMessageBox.critical(self, "Invalid End Time", "End date & time cannot be in the past.")
            self.encrypting_now = False
            return
        if self.start_time.dateTime() >= self.end_time.dateTime():
            QMessageBox.critical(self, "Invalid Time", "Start date & time must be before end date & time.")
            self.encrypting_now = False
            return
        macs = self.mac_input.text().strip()
        allowed_macs = [m.replace('-', ':').strip().upper() for m in macs.split(';') if m.strip()]
        for mac in allowed_macs:
            if not re.match(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$', mac):
                QMessageBox.critical(self, "Invalid MAC", f"Invalid MAC address: {mac}\nPlease use format AA:BB:CC:DD:EE:FF or AA-BB-CC-DD-EE-FF")
                self.encrypting_now = False
                return
                
        start_time = self.start_time.dateTime().toString(Qt.ISODate)
        end_time = self.end_time.dateTime().toString(Qt.ISODate)
        watermark_text = self.watermark_text_input.text().strip() or "DRM PROTECTED"
        metadata = {
            "start": start_time,
            "end": end_time,
            "watermark_text": watermark_text,
            "folder_name": self.package_name_input.text().strip(),
            "original_names": [os.path.basename(f) for f in self.current_package_files],
        }
        if allowed_macs:
            metadata["allowed_macs"] = allowed_macs
        folder_name = self.package_name_input.text().strip()
        
        try:
            out_path = encrypt_files(self.current_package_files, password, metadata, folder_name)
            QMessageBox.information(self, "Success", f"Folder encrypted and saved as:\n{out_path}")
            
            # Reset UI
            self.load_encrypted_folders()
            self.folders_table.setVisible(True)
            QApplication.processEvents()
            self.folders_table.setVisible(True)
            self.folders_table.clearSelection()
            self.current_package_files = []
            self.current_package_name = ""
            self.package_name_input.clear()
            self.package_name_input.setEnabled(False)
            self.file_list_widget.clear()
            self.file_list_widget.setVisible(False)
            self.password_input.clear()
            self.password_input.setEnabled(False)
            self.mac_input.clear()
            self.mac_input.setEnabled(False)
            self.start_time.setEnabled(False)
            self.end_time.setEnabled(False)
            self.watermark_text_input.clear()
            self.watermark_text_input.setEnabled(False)
            self.encrypt_btn.setEnabled(False)
            self.select_files_btn.setEnabled(True)
            self.done_btn.setEnabled(False)
            self.delete_file_btn.setEnabled(False)
            self.update_encrypt_btn_state()
            
        except Exception as e:
            QMessageBox.critical(self, "Encryption Error", f"An error occurred during encryption:\n{str(e)}")
        
        self.encrypting_now = False
        



