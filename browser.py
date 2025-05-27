import os
import json
import sys
from datetime import datetime
import shutil
import re
import hashlib
import zipfile

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLineEdit, QLabel, QTabWidget, QScrollArea, QDockWidget, QListWidget,
                             QProgressBar, QMenu, QMessageBox, QListWidgetItem, QFileDialog, QCompleter,
                             QStyleFactory, QDialog, QFormLayout, QComboBox, QSpinBox, QToolButton,
                             QCheckBox, QInputDialog, QGroupBox, QSizePolicy, QFontComboBox)
from PyQt6.QtGui import QIcon, QKeySequence, QShortcut, QCursor, QDesktopServices, QAction, QFont
from PyQt6.QtCore import Qt, QPoint, QUrl, QTimer, QRect, pyqtSignal, QSize, QDateTime, QStandardPaths
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (QWebEnginePage, QWebEngineProfile, QWebEngineSettings,
                                   QWebEngineScript, QWebEngineScriptCollection, QWebEngineUrlRequestInterceptor,
                                   QWebEngineDownloadRequest, QWebEngineUrlRequestInfo)

# Import constants and DataManager from new files
from config import (APP_NAME, DATA_DIR, ICONS_DIR, STYLES_DIR, EXTENSIONS_DIR, CLOUD_DATA_DIR,
                    CACHE_DIR, STORAGE_DIR, SEARCH_ENGINE_URLS,
                    TAB_BUTTON_WIDTH, TAB_BUTTON_HEIGHT, SUSPEND_CHECK_INTERVAL, RESIZE_BORDER)
from data_manager import DataManager

# Helper function for icons (can stay here or move to a utils file)
def find_icon(button_name):
    """
    Finds the path to an icon based on its logical name.
    Returns a default icon path if the specific icon is not found.
    """
    icon_mapping = {
        "block": "block.svg", "minimize": "minimize.svg", "maximize": "maximize.svg",
        "close": "close_24.svg", "sidebar": "side_navigation.svg", "back": "arrow_back.svg",
        "forward": "arrow_forward.svg", "refresh": "refresh.svg", "home": "home.svg",
        "share": "share.svg", "bookmark": "bookmark.svg", "bookmarks_menu": "accessible_menu.svg",
        "settings": "settings.svg", "save_pdf": "file_export.svg", "reading_mode": "menu_book.svg",
        "zoom": "pinch.svg", "history": "clock_arrow_down.svg", "downloads": "download.svg",
        "fullscreen": "fullscreen.svg", "new_tab": "new_window.svg", "search": "search.svg",
        "extensions": "extension.svg", "sync": "sync.svg", "devtools": "code.svg",
        "site_permissions": "security.svg"
    }
    icon_name = icon_mapping.get(button_name, "block.svg")
    icon_path = os.path.join(ICONS_DIR, icon_name)
    if os.path.exists(icon_path):
        return icon_path
    print(f"Icon for {button_name} not found at {icon_path}, using default: block.svg")
    default_icon_path = os.path.join(ICONS_DIR, "block.svg")
    if not os.path.exists(default_icon_path):
        try:
            with open(default_icon_path, "w") as f:
                f.write('<svg width="24" height="24" viewBox="0 0 24 24" fill="#FF0000" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="2" width="20" height="20" rx="2"/></svg>')
        except IOError:
            print("Could not create default icon file. Using in-memory SVG.")
            return QIcon('<svg width="24" height="24" viewBox="0 0 24 24" fill="#FF0000" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="2" width="20" height="20" rx="2"/></svg>')
    return default_icon_path

class HomePage(QWidget):
    """
    A custom home page widget for the browser, featuring a logo and a search bar.
    Emits a signal when a search is triggered.
    """
    search_triggered = pyqtSignal(str)

    def __init__(self, history_data, bookmarks_data):
        super().__init__()
        self.history = history_data
        self.bookmarks = bookmarks_data
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        self.logo = QLabel("Doors Browser")
        self.logo.setObjectName("logo")
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.logo)

        self.search_bar = QLineEdit()
        self.search_bar.setObjectName("searchBar")
        self.search_bar.setPlaceholderText("Search with Doors...")
        self.search_bar.setFixedWidth(600)
        self.search_bar.setFixedHeight(40)
        self.search_bar.returnPressed.connect(self.trigger_search)
        layout.addWidget(self.search_bar)

        layout.addStretch()
        self.setup_completer()
        self.setLayout(layout)
        self.setObjectName("homePage")

    def setup_completer(self):
        """Sets up the completer for the search bar based on history and bookmarks."""
        suggestions = list(set([entry["url"] for entry in self.history] +
                               [entry["url"] for entry in self.bookmarks] +
                               ["Search Google for...", "Wikipedia", "YouTube"]))
        self.completer = QCompleter(suggestions, self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.search_bar.setCompleter(self.completer)

    def trigger_search(self):
        """Emits the search_triggered signal with the current query."""
        query = self.search_bar.text().strip()
        if query:
            self.search_triggered.emit(query)

class SettingsDialog(QDialog):
    """
    A dialog for managing browser settings.
    """
    settings_updated = pyqtSignal(dict)
    clear_history_requested = pyqtSignal()
    clear_cache_requested = pyqtSignal()
    clear_cookies_requested = pyqtSignal()
    sync_upload_requested = pyqtSignal()
    sync_download_requested = pyqtSignal()
    bookmark_import_json_requested = pyqtSignal()
    bookmark_export_json_requested = pyqtSignal()
    bookmark_import_html_requested = pyqtSignal()
    bookmark_export_html_requested = pyqtSignal()
    manage_site_permissions_requested = pyqtSignal()

    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Doors Browser Settings")
        self.setMinimumSize(600, 500)
        self.settings = current_settings
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()
        
        self.tab_widget.addTab(self.create_general_tab(), "General")
        self.tab_widget.addTab(self.create_privacy_tab(), "Privacy & Security")
        self.tab_widget.addTab(self.create_downloads_tab(), "Downloads")
        self.tab_widget.addTab(self.create_appearance_tab(), "Appearance")
        self.tab_widget.addTab(self.create_advanced_tab(), "Advanced")
        
        main_layout.addWidget(self.tab_widget)

        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_settings)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)

        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

    def create_general_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)

        self.startup_behavior_combo = QComboBox()
        self.startup_behavior_combo.addItems(["Open Homepage", "Open New Tab", "Restore Last Session"])
        self.startup_behavior_combo.setCurrentText(self.settings.get("startup_behavior", "Open Homepage"))
        layout.addRow("On Startup:", self.startup_behavior_combo)

        self.homepage_url_edit = QLineEdit(self.settings.get("homepage_url", "about:home"))
        layout.addRow("Homepage URL:", self.homepage_url_edit)

        self.search_engine_combo = QComboBox()
        self.search_engine_combo.addItems(list(SEARCH_ENGINE_URLS.keys()))
        self.search_engine_combo.setCurrentText(self.settings.get("default_search_engine", "yahoo"))
        layout.addRow("Default Search Engine:", self.search_engine_combo)

        self.max_tabs_spinbox = QSpinBox()
        self.max_tabs_spinbox.setRange(5, 100)
        self.max_tabs_spinbox.setValue(self.settings.get("max_tabs", 30))
        layout.addRow("Maximum Tabs:", self.max_tabs_spinbox)

        self.suspend_tabs_checkbox = QCheckBox("Suspend inactive tabs")
        self.suspend_tabs_checkbox.setChecked(self.settings.get("suspend_inactive_tabs", True))
        layout.addRow("Memory Optimization:", self.suspend_tabs_checkbox)

        self.suspend_timeout_spinbox = QSpinBox()
        self.suspend_timeout_spinbox.setRange(1, 60)
        self.suspend_timeout_spinbox.setSuffix(" minutes")
        self.suspend_timeout_spinbox.setValue(self.settings.get("suspend_timeout_minutes", 5))
        layout.addRow("Suspend Timeout:", self.suspend_timeout_spinbox)

        return widget

    def create_privacy_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)

        self.adblock_checkbox = QCheckBox("Enable Adblock")
        self.adblock_checkbox.setChecked(self.settings.get("adblock_enabled", True))
        layout.addRow("Ad Blocker:", self.adblock_checkbox)

        self.dnt_checkbox = QCheckBox("Send 'Do Not Track' request")
        self.dnt_checkbox.setChecked(self.settings.get("send_dnt_header", False))
        layout.addRow("Tracking Protection:", self.dnt_checkbox)

        self.block_third_party_cookies_checkbox = QCheckBox("Block third-party cookies")
        self.block_third_party_cookies_checkbox.setChecked(self.settings.get("block_third_party_cookies", False))
        layout.addRow("Cookies:", self.block_third_party_cookies_checkbox)

        self.clear_cookies_on_exit_checkbox = QCheckBox("Clear cookies on exit")
        self.clear_cookies_on_exit_checkbox.setChecked(self.settings.get("clear_cookies_on_exit", False))
        layout.addRow("Cookies:", self.clear_cookies_on_exit_checkbox)

        clear_data_layout = QHBoxLayout()
        clear_history_btn = QPushButton("Clear History")
        clear_history_btn.clicked.connect(lambda: self.clear_browsing_data("history"))
        clear_cache_btn = QPushButton("Clear Cache")
        clear_cache_btn.clicked.connect(lambda: self.clear_browsing_data("cache"))
        clear_cookies_btn = QPushButton("Clear Cookies")
        clear_cookies_btn.clicked.connect(lambda: self.clear_browsing_data("cookies"))
        clear_data_layout.addWidget(clear_history_btn)
        clear_data_layout.addWidget(clear_cache_btn)
        clear_data_layout.addWidget(clear_cookies_btn)
        layout.addRow("Clear Browsing Data:", clear_data_layout)
        
        manage_permissions_btn = QPushButton("Manage Site Permissions...")
        manage_permissions_btn.clicked.connect(self.manage_site_permissions_requested.emit)
        layout.addRow("Site Permissions:", manage_permissions_btn)

        return widget

    def create_downloads_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)

        self.download_path_edit = QLineEdit(self.settings.get("download_path", QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)))
        download_path_btn = QPushButton("Browse...")
        download_path_btn.clicked.connect(self.browse_download_path)
        download_path_layout = QHBoxLayout()
        download_path_layout.addWidget(self.download_path_edit)
        download_path_layout.addWidget(download_path_btn)
        layout.addRow("Default Download Path:", download_path_layout)

        self.ask_save_location_checkbox = QCheckBox("Always ask where to save files")
        self.ask_save_location_checkbox.setChecked(self.settings.get("ask_save_location", True))
        layout.addRow("Download Behavior:", self.ask_save_location_checkbox)

        return widget

    def browse_download_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select Download Directory", self.download_path_edit.text())
        if path:
            self.download_path_edit.setText(path)

    def create_appearance_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["light", "dark"])
        self.theme_combo.setCurrentText(self.settings.get("theme", "light"))
        layout.addRow("Theme:", self.theme_combo)

        self.auto_night_mode_checkbox = QCheckBox("Enable Auto Night Mode (6 PM - 6 AM)")
        self.auto_night_mode_checkbox.setChecked(self.settings.get("auto_night_mode", False))
        layout.addRow("Auto Theme:", self.auto_night_mode_checkbox)

        self.default_font_family_combo = QFontComboBox()
        self.default_font_family_combo.setCurrentFont(QFont(self.settings.get("default_font_family", "Arial")))
        layout.addRow("Default Font Family:", self.default_font_family_combo)

        self.default_font_size_spinbox = QSpinBox()
        self.default_font_size_spinbox.setRange(8, 72)
        self.default_font_size_spinbox.setValue(self.settings.get("default_font_size", 16))
        layout.addRow("Default Font Size:", self.default_font_size_spinbox)

        self.preferred_web_languages_edit = QLineEdit(self.settings.get("preferred_web_languages", "en-US,en;q=0.9"))
        self.preferred_web_languages_edit.setPlaceholderText("e.g., en-US,en;q=0.9,fa;q=0.8")
        layout.addRow("Preferred Web Languages (Accept-Language):", self.preferred_web_languages_edit)

        return widget

    def create_advanced_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)

        bookmark_io_layout = QHBoxLayout()
        import_json_btn = QPushButton("Import JSON")
        import_json_btn.clicked.connect(self.bookmark_import_json_requested.emit)
        export_json_btn = QPushButton("Export JSON")
        export_json_btn.clicked.connect(self.bookmark_export_json_requested.emit)
        import_html_btn = QPushButton("Import HTML")
        import_html_btn.clicked.connect(self.bookmark_import_html_requested.emit)
        export_html_btn = QPushButton("Export HTML")
        export_html_btn.clicked.connect(self.bookmark_export_html_requested.emit)
        bookmark_io_layout.addWidget(import_json_btn)
        bookmark_io_layout.addWidget(export_json_btn)
        bookmark_io_layout.addWidget(import_html_btn)
        bookmark_io_layout.addWidget(export_html_btn)
        layout.addRow("Bookmarks:", bookmark_io_layout)

        sync_layout = QHBoxLayout()
        sync_upload_btn = QPushButton("Sync (Upload)")
        sync_upload_btn.clicked.connect(self.sync_upload_requested.emit)
        sync_download_btn = QPushButton("Sync (Download)")
        sync_download_btn.clicked.connect(self.sync_download_requested.emit)
        sync_layout.addWidget(sync_upload_btn)
        sync_layout.addWidget(sync_download_btn)
        layout.addRow("Synchronization:", sync_layout)
        
        reset_settings_btn = QPushButton("Reset All Settings to Default")
        reset_settings_btn.clicked.connect(self.reset_settings_to_default)
        layout.addRow("Reset:", reset_settings_btn)

        return widget

    def clear_browsing_data(self, data_type):
        """Emits signal to clear specified browsing data."""
        reply = QMessageBox.question(self, "Confirm", f"Are you sure you want to clear {data_type}?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if data_type == "history":
                self.clear_history_requested.emit()
            elif data_type == "cache":
                self.clear_cache_requested.emit()
            elif data_type == "cookies":
                self.clear_cookies_requested.emit()
            QMessageBox.information(self, "Clear Data", f"{data_type} marked for clearing.")

    def reset_settings_to_default(self):
        reply = QMessageBox.question(self, "Confirm Reset", 
                                     "Are you sure you want to reset all settings to their default values?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            # Load default settings structure from config
            default_settings = DEFAULT_JSON_STRUCTURES["settings.json"].copy()
            self.settings_updated.emit(default_settings)
            self.accept()
            QMessageBox.information(self, "Settings Reset", "All settings have been reset to default.")

    def save_settings(self):
        """Saves the settings and emits the settings_updated signal."""
        new_settings = {
            "startup_behavior": self.startup_behavior_combo.currentText(),
            "homepage_url": self.homepage_url_edit.text().strip(),
            "default_search_engine": self.search_engine_combo.currentText(),
            "max_tabs": self.max_tabs_spinbox.value(),
            "suspend_inactive_tabs": self.suspend_tabs_checkbox.isChecked(),
            "suspend_timeout_minutes": self.suspend_timeout_spinbox.value(),
            "adblock_enabled": self.adblock_checkbox.isChecked(),
            "send_dnt_header": self.dnt_checkbox.isChecked(),
            "block_third_party_cookies": self.block_third_party_cookies_checkbox.isChecked(),
            "clear_cookies_on_exit": self.clear_cookies_on_exit_checkbox.isChecked(),
            "download_path": self.download_path_edit.text().strip(),
            "ask_save_location": self.ask_save_location_checkbox.isChecked(),
            "theme": self.theme_combo.currentText(),
            "auto_night_mode": self.auto_night_mode_checkbox.isChecked(),
            "default_font_family": self.default_font_family_combo.currentFont().family(),
            "default_font_size": self.default_font_size_spinbox.value(),
            "preferred_web_languages": self.preferred_web_languages_edit.text().strip()
        }
        self.settings_updated.emit(new_settings)
        self.accept() # This will close the dialog and trigger the "Settings saved successfully" message in DoorsBrowser

class SitePermissionsDialog(QDialog):
    """A dialog to manage site-specific permissions (e.g., camera, microphone, geolocation)."""
    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Site Permissions")
        self.setMinimumSize(500, 400)
        self.data_manager = data_manager
        self.permissions_data = self.data_manager.load_data()["site_permissions"]
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        main_layout.addWidget(self.list_widget)

        button_layout = QHBoxLayout()
        add_btn = QPushButton("Add/Edit Permission...")
        add_btn.clicked.connect(self.add_edit_permission)
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self.remove_permission)
        button_layout.addWidget(add_btn)
        button_layout.addWidget(remove_btn)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        self.load_permissions_list()

    def load_permissions_list(self):
        self.list_widget.clear()
        for perm in self.permissions_data:
            item_text = f"{perm['origin']} - {perm['feature']}: {'Allowed' if perm['allowed'] else 'Blocked'}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, perm)
            self.list_widget.addItem(item)

    def add_edit_permission(self):
        origin, ok = QInputDialog.getText(self, "Origin", "Enter origin (e.g., https://example.com):")
        if not ok or not origin: return

        feature, ok = QInputDialog.getItem(self, "Feature", "Select feature:", 
                                           ["Camera", "Microphone", "Geolocation", "Notifications"], 0, False)
        if not ok or not feature: return

        allowed, ok = QInputDialog.getItem(self, "Permission", "Allow or Block:", ["Allow", "Block"], 0, False)
        if not ok: return
        
        allowed_bool = (allowed == "Allow")

        found = False
        for perm in self.permissions_data:
            if perm['origin'] == origin and perm['feature'] == feature:
                perm['allowed'] = allowed_bool
                found = True
                break
        if not found:
            self.permissions_data.append({"origin": origin, "feature": feature, "allowed": allowed_bool})
        
        self.save_permissions()
        self.load_permissions_list()

    def remove_permission(self):
        selected_item = self.list_widget.currentItem()
        if selected_item:
            perm_to_remove = selected_item.data(Qt.ItemDataRole.UserRole)
            self.permissions_data.remove(perm_to_remove)
            self.save_permissions()
            self.load_permissions_list()
        else:
            QMessageBox.warning(self, "Remove Permission", "Please select a permission to remove.")

    def save_permissions(self):
        self.data_manager.save_site_permissions(self.permissions_data)
        QMessageBox.information(self, "Site Permissions", "Permissions saved. Restart browser for full effect on existing tabs.")

class AdBlockInterceptor(QWebEngineUrlRequestInterceptor):
    """
    Intercepts web requests to block known ad domains and third-party cookies.
    Also handles Do Not Track header.
    """
    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.ad_domains = set()
        self.adblock_enabled = True # Controlled by settings
        self.block_third_party_cookies_enabled = False
        self.send_dnt_header_enabled = False
        self.load_ad_domains()

    def load_ad_domains(self):
        """Loads ad domains from a text file."""
        self.ad_domains = self.data_manager.load_data()["ad_domains"]
        # print(f"Loaded {len(self.ad_domains)} ad domains.") # Keep print, remove QMessageBox

    def set_adblock_enabled(self, enabled):
        self.adblock_enabled = enabled
        print(f"Adblock enabled: {enabled}.")

    def set_block_third_party_cookies(self, enabled):
        self.block_third_party_cookies_enabled = enabled
        print(f"Third-party cookies blocking: {'Enabled' if enabled else 'Disabled'}.")

    def set_send_dnt_header(self, enabled):
        self.send_dnt_header_enabled = enabled
        print(f"Do Not Track header: {'Enabled' if enabled else 'Disabled'}.")

    def interceptRequest(self, info):
        """Blocks requests if their URL contains a known ad domain or if it's a third-party cookie request."""
        url = info.requestUrl().toString()
    
        if self.adblock_enabled:
            for domain in self.ad_domains:
                if domain in url:
                    info.block(True)
                    return

        if self.block_third_party_cookies_enabled:
            first_party_url = info.firstPartyUrl()
            request_url = info.requestUrl()

            if first_party_url.isValid() and request_url.isValid():
                first_party_host = first_party_url.host()
                request_host = request_url.host()

                is_same_party = (first_party_host == request_host or
                                request_host.endswith("." + first_party_host) or
                                first_party_host.endswith("." + request_host))

                # نام صحیح در PyQt6:
                if not is_same_party and info.resourceType() != QWebEngineUrlRequestInfo.ResourceType.ResourceTypeMainFrame:
                    info.block(True)
                    return

        
        pass

class ExtensionManager:
    """
    Manages browser extensions.
    Loads extensions from manifests and injects content scripts.
    Supports .json manifests and basic .crx (zip) extraction.
    """
    def __init__(self, profile, data_manager):
        super().__init__() # Call QObject.__init__ if inheriting from QObject
        self.profile = profile
        self.data_manager = data_manager
        self.extensions = {} # {extension_id: {manifest_data, is_enabled, path_to_files}}
        self.load_extensions()

    def load_extensions(self):
        """Loads extension manifests from the extensions directory."""
        self.extensions = {}
        if not os.path.exists(EXTENSIONS_DIR):
            os.makedirs(EXTENSIONS_DIR)
            return

        saved_states = self.data_manager.load_data()["extensions_state"]
        saved_states_map = {state["id"]: state["enabled"] for state in saved_states}

        for ext_id in os.listdir(EXTENSIONS_DIR):
            ext_path = os.path.join(EXTENSIONS_DIR, ext_id)
            manifest_path = os.path.join(ext_path, "manifest.json")

            if os.path.isdir(ext_path) and os.path.exists(manifest_path):
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                        
                        self.extensions[ext_id] = {
                            "manifest": manifest,
                            "is_enabled": saved_states_map.get(ext_id, True),
                            "path_to_files": ext_path
                        }
                        print(f"Loaded extension: {ext_id} (Enabled: {self.extensions[ext_id]['is_enabled']})")
                except Exception as e:
                    print(f"Error loading extension manifest {ext_id}: {e}")
        self.save_extension_states()

    def save_extension_states(self):
        """Saves the enabled/disabled state of extensions."""
        states = [{"id": ext_id, "enabled": data["is_enabled"]} for ext_id, data in self.extensions.items()]
        self.data_manager.save_extensions_state(states)

    def get_extension_states(self):
        """Returns a list of (name, is_enabled, id) for all loaded extensions."""
        return [(data["manifest"].get("name", ext_id), data["is_enabled"], ext_id) for ext_id, data in self.extensions.items()]

    def set_extension_enabled(self, ext_id, enabled):
        """Enables or disables an extension by its ID."""
        if ext_id in self.extensions:
            self.extensions[ext_id]["is_enabled"] = enabled
            self.save_extension_states()
            print(f"Extension '{self.extensions[ext_id]['manifest'].get('name', ext_id)}' {'enabled' if enabled else 'disabled'}.")
            return True
        return False

    def apply_content_scripts(self, page: QWebEnginePage):
        """
        Injects content scripts for enabled extensions into the given QWebEnginePage.
        This should be called when a new page loads.
        """
        scripts = page.scripts()
        for ext_id, ext_data in self.extensions.items():
            if not ext_data["is_enabled"]:
                continue

            manifest = ext_data["manifest"]
            content_scripts = manifest.get("content_scripts", [])

            for script_data in content_scripts:
                matches = script_data.get("matches", [])
                js_file = script_data.get("js")

                if js_file and any(self._matches_url(page.url().toString(), pattern) for pattern in matches):
                    script_path = os.path.join(ext_data["path_to_files"], js_file)
                    if os.path.exists(script_path):
                        try:
                            with open(script_path, "r", encoding="utf-8") as f:
                                js_code = f.read()
                                script = QWebEngineScript()
                                script.setSourceCode(js_code)
                                script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
                                script.setRunsOnSubFrames(True)
                                script.setWorldId(QWebEngineScript.ScriptWorldId.ApplicationWorld)
                                scripts.insert(script)
                        except Exception as e:
                            print(f"Error reading content script {script_path} for {ext_id}: {e}")
                    else:
                        print(f"Content script file not found: {script_path} for extension {ext_id}")

    def _matches_url(self, url, pattern):
        """Simple wildcard matching for URLs (e.g., *://*.example.com/*)."""
        pattern = pattern.replace('.', '\\.').replace('*', '.*')
        return re.match(pattern, url) is not None

    def install_extension_from_file(self, file_path):
        """Installs an extension from a .json manifest or .crx file."""
        try:
            ext_name = os.path.basename(file_path)
            ext_id = ext_name.replace(".json", "").replace(".crx", "")

            dest_dir = os.path.join(EXTENSIONS_DIR, ext_id)
            if os.path.exists(dest_dir):
                QMessageBox.warning(None, "Install Extension", f"Extension '{ext_id}' already exists. Please uninstall first.")
                return False

            os.makedirs(dest_dir)

            if file_path.endswith(".json"):
                shutil.copy(file_path, os.path.join(dest_dir, "manifest.json"))
            elif file_path.endswith(".crx"):
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(dest_dir)
                if not os.path.exists(os.path.join(dest_dir, "manifest.json")):
                    QMessageBox.critical(None, "Installation Error", "CRX file does not contain manifest.json.")
                    shutil.rmtree(dest_dir)
                    return False
            else:
                QMessageBox.critical(None, "Installation Error", "Unsupported extension file type. Only .json or .crx are supported.")
                shutil.rmtree(dest_dir)
                return False

            self.load_extensions()
            QMessageBox.information(None, "Install Extension", f"Extension '{ext_id}' installed successfully.")
            return True
        except Exception as e:
            QMessageBox.critical(None, "Installation Error", f"Error installing extension: {e}")
            return False

    def uninstall_extension(self, ext_id):
        """Uninstalls an extension by its ID."""
        if ext_id in self.extensions:
            reply = QMessageBox.question(None, "Uninstall Extension", 
                                         f"Are you sure you want to uninstall '{self.extensions[ext_id]['manifest'].get('name', ext_id)}'?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    shutil.rmtree(self.extensions[ext_id]["path_to_files"])
                    del self.extensions[ext_id]
                    self.save_extension_states()
                    QMessageBox.information(None, "Uninstall Extension", "Extension uninstalled successfully.")
                    return True
                except Exception as e:
                    QMessageBox.critical(None, "Uninstall Error", f"Error uninstalling extension: {e}")
                    return False
        return False

class ExtensionsDialog(QDialog):
    """Dialog to manage installed extensions."""
    def __init__(self, extension_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Extensions Manager")
        self.extension_manager = extension_manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.list_widget = QListWidget()
        self.list_widget.itemChanged.connect(self.on_item_changed)
        layout.addWidget(self.list_widget)

        button_layout = QHBoxLayout()
        install_btn = QPushButton("Install Extension...")
        install_btn.clicked.connect(self.install_extension)
        uninstall_btn = QPushButton("Uninstall Selected")
        uninstall_btn.clicked.connect(self.uninstall_selected_extension)
        
        button_layout.addWidget(install_btn)
        button_layout.addWidget(uninstall_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)
        self.setLayout(layout)
        self.load_extensions_list()

    def load_extensions_list(self):
        self.list_widget.clear()
        for name, enabled, ext_id in self.extension_manager.get_extension_states():
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, ext_id)
            self.list_widget.addItem(item)

    def on_item_changed(self, item):
        ext_id = item.data(Qt.ItemDataRole.UserRole)
        enabled = item.checkState() == Qt.CheckState.Checked
        self.extension_manager.set_extension_enabled(ext_id, enabled)
        if self.parent() and hasattr(self.parent(), 'reapply_extension_scripts'):
            self.parent().reapply_extension_scripts()

    def install_extension(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Extension File", "", "Extension Files (*.json *.crx)")
        if file_path:
            if self.extension_manager.install_extension_from_file(file_path):
                self.load_extensions_list()
                if self.parent() and hasattr(self.parent(), 'reapply_extension_scripts'):
                    self.parent().reapply_extension_scripts()

    def uninstall_selected_extension(self):
        selected_item = self.list_widget.currentItem()
        if selected_item:
            ext_id = selected_item.data(Qt.ItemDataRole.UserRole)
            if self.extension_manager.uninstall_extension(ext_id):
                self.load_extensions_list()
                if self.parent() and hasattr(self.parent(), 'reapply_extension_scripts'):
                    self.parent().reapply_extension_scripts()
        else:
            QMessageBox.warning(self, "Uninstall Extension", "Please select an extension to uninstall.")

class DownloadItem(QWidget):
    """A widget to display a single download's progress and controls."""
    def __init__(self, download: QWebEngineDownloadRequest, parent=None):
        super().__init__(parent)
        self.download = download
        self.init_ui()
        self.connect_signals()
        self.update_ui()

    def init_ui(self):
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(10)

        self.filename_label = QLabel(os.path.basename(self.download.path()))
        self.layout.addWidget(self.filename_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Pending...")
        self.layout.addWidget(self.status_label)

        self.speed_label = QLabel("")
        self.layout.addWidget(self.speed_label)

        self.pause_resume_btn = QPushButton("Pause")
        self.pause_resume_btn.clicked.connect(self.toggle_pause_resume)
        self.layout.addWidget(self.pause_resume_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_download)
        self.layout.addWidget(self.cancel_btn)

        self.open_folder_btn = QPushButton("Open Folder")
        self.open_folder_btn.clicked.connect(self.open_download_folder)
        self.open_folder_btn.setEnabled(False)
        self.layout.addWidget(self.open_folder_btn)

    def connect_signals(self):
        self.download.stateChanged.connect(self.on_state_changed)
        self.download.receivedBytesChanged.connect(self.on_progress_changed)
        self.download.totalBytesChanged.connect(self.on_progress_changed)

    def update_ui(self):
        filename = os.path.basename(self.download.path())
        self.filename_label.setText(filename)

        if self.download.totalBytes() > 0:
            progress_percent = int((self.download.receivedBytes() / self.download.totalBytes()) * 100)
            self.progress_bar.setValue(progress_percent)
            self.progress_bar.setFormat(f"{progress_percent}% ({self.format_bytes(self.download.receivedBytes())}/{self.format_bytes(self.download.totalBytes())})")
        else:
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat(f"{self.format_bytes(self.download.receivedBytes())} / Unknown")

        if self.download.totalBytes() > 0 and self.download.receivedBytes() > 0 and self.download.downloadTime() > 0:
            speed = self.download.receivedBytes() / self.download.downloadTime()
            self.speed_label.setText(f"{self.format_bytes(speed)}/s")
        else:
            self.speed_label.setText("")

        self.on_state_changed(self.download.state())

    def on_state_changed(self, state):
        if state == QWebEngineDownloadRequest.DownloadState.DownloadRequested:
            self.status_label.setText("Pending...")
            self.pause_resume_btn.setEnabled(False)
            self.cancel_btn.setEnabled(True)
        elif state == QWebEngineDownloadRequest.DownloadState.DownloadInProgress:
            self.status_label.setText("Downloading")
            self.pause_resume_btn.setText("Pause")
            self.pause_resume_btn.setEnabled(True)
            self.cancel_btn.setEnabled(True)
            self.open_folder_btn.setEnabled(False)
        elif state == QWebEngineDownloadRequest.DownloadState.DownloadInterrupted:
            self.status_label.setText("Interrupted")
            self.pause_resume_btn.setText("Resume")
            self.pause_resume_btn.setEnabled(True)
            self.cancel_btn.setEnabled(True)
            self.open_folder_btn.setEnabled(False)
        elif state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            self.status_label.setText("Completed")
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat("100% (Completed)")
            self.pause_resume_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)
            self.open_folder_btn.setEnabled(True)
            self.speed_label.setText("")
        elif state == QWebEngineDownloadRequest.DownloadState.DownloadCancelled:
            self.status_label.setText("Cancelled")
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Cancelled")
            self.pause_resume_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)
            self.open_folder_btn.setEnabled(False)
            self.speed_label.setText("")

    def on_progress_changed(self):
        self.update_ui()

    def toggle_pause_resume(self):
        if self.download.state() == QWebEngineDownloadRequest.DownloadState.DownloadInProgress:
            self.download.pause()
        elif self.download.state() == QWebEngineDownloadRequest.DownloadState.DownloadInterrupted:
            self.download.resume()

    def cancel_download(self):
        self.download.cancel()

    def open_download_folder(self):
        if self.download.state() == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            file_path = self.download.path()
            if os.path.exists(file_path):
                QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(file_path)))
            else:
                QMessageBox.warning(self, "Error", "Downloaded file not found.")

    def format_bytes(self, bytes_val):
        if bytes_val < 1024:
            return f"{bytes_val} B"
        elif bytes_val < 1024**2:
            return f"{bytes_val / 1024:.2f} KB"
        elif bytes_val < 1024**3:
            return f"{bytes_val / (1024**2):.2f} MB"
        else:
            return f"{bytes_val / (1024**3):.2f} GB"

class DownloadsDialog(QDialog):
    """A dialog to manage and display active and completed downloads."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Downloads")
        self.setMinimumSize(600, 400)
        self.downloads_list = []
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.downloads_layout = QVBoxLayout(self.scroll_content)
        self.downloads_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.downloads_layout.addStretch(1)
        self.scroll_content.setLayout(self.downloads_layout)
        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area)

    def add_download_item(self, download_item: QWebEngineDownloadRequest):
        item_widget = DownloadItem(download_item)
        self.downloads_list.append(item_widget)
        self.downloads_layout.insertWidget(0, item_widget)

class DoorsBrowser(QMainWindow):
    """
    The main browser window class.
    Handles UI, tab management, navigation, settings, and frameless window behavior.
    """
    def __init__(self):
        super().__init__()
        self.data_manager = DataManager()
        self.data_manager.initialize_project_structure() # Ensure data structure exists

        self.setWindowTitle(APP_NAME)
        self.setGeometry(100, 100, 1200, 800)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)

        self.profile = QWebEngineProfile("DoorsBrowserProfile", self)
        self.profile.setCachePath(CACHE_DIR)
        self.profile.setPersistentStoragePath(STORAGE_DIR)
        self.profile.downloadRequested.connect(self.handle_download_request)

        self.adblock_interceptor = AdBlockInterceptor(self.data_manager, self)
        self.profile.setUrlRequestInterceptor(self.adblock_interceptor)

        self.extension_manager = ExtensionManager(self.profile, self.data_manager)

        # Load initial data
        initial_data = self.data_manager.load_data()
        self.history = initial_data["history"]
        self.bookmarks = initial_data["bookmarks"]
        self.content = initial_data["content"] # Not used in this snippet, but kept for consistency
        self.settings = initial_data["settings"]
        self.site_permissions = initial_data["site_permissions"]

        self.reading_mode = False
        self.is_fullscreen = False
        self.sidebar_visible = False

        # Frameless window drag/resize state
        self.resizing = False
        self.resize_direction = None
        self.resize_start_pos = None
        self.resize_start_geometry = None

        self.dragging = False
        self.drag_position = QPoint()

        self.custom_tab_buttons_map = {}
        self.tab_last_active_time = {}
        self.suspended_tabs_data = {}
        self.devtools_windows = []

        self.downloads_dialog = DownloadsDialog(self)

        self.init_ui()

        # Apply initial settings (without showing pop-ups)
        self._apply_initial_settings(self.settings)
        self.setup_shortcuts()

        # Timer for suspending inactive tabs
        self.suspend_timer = QTimer(self)
        self.suspend_timer.timeout.connect(self.check_and_suspend_inactive_tabs)
        self.suspend_timer.start(SUSPEND_CHECK_INTERVAL)

        # Load initial tab based on startup behavior
        startup_behavior = self.settings.get("startup_behavior", "Open Homepage")
        if startup_behavior == "Open New Tab":
            self.add_new_tab(url="about:blank")
        elif startup_behavior == "Restore Last Session":
            self.restore_last_session()
        else:
            # Use go_to_homepage to respect the actual homepage_url setting
            self.go_to_homepage()

    def init_ui(self):
        """Initializes the main user interface components."""
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header (Custom Title Bar)
        self.header = QWidget()
        self.header.setFixedHeight(40)
        self.header.setObjectName("header")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(5, 0, 5, 0)
        header_layout.setSpacing(0)

        self.title_label = QLabel(APP_NAME)
        self.title_label.setObjectName("windowTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        control_box = QWidget()
        control_box.setFixedSize(90, 30)
        control_layout = QHBoxLayout(control_box)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(0)

        self.minimize_btn = QPushButton()
        self.minimize_btn.setIcon(QIcon(find_icon("minimize")))
        self.minimize_btn.setFixedSize(30, 30)
        self.minimize_btn.clicked.connect(self.showMinimized)
        self.maximize_btn = QPushButton()
        self.maximize_btn.setIcon(QIcon(find_icon("maximize")))
        self.maximize_btn.setFixedSize(30, 30)
        self.maximize_btn.clicked.connect(self.toggle_maximize)
        self.close_btn = QPushButton()
        self.close_btn.setIcon(QIcon(find_icon("close")))
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.clicked.connect(self.close)

        control_layout.addWidget(self.minimize_btn)
        control_layout.addWidget(self.maximize_btn)
        control_layout.addWidget(self.close_btn)
        header_layout.addWidget(control_box)

        # Toolbar
        toolbar = QWidget()
        toolbar.setFixedHeight(50)
        toolbar.setObjectName("toolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(10, 5, 10, 5)
        toolbar_layout.setSpacing(5)

        self.sidebar_btn = QPushButton()
        self.sidebar_btn.setIcon(QIcon(find_icon("sidebar")))
        self.sidebar_btn.setFixedSize(30, 30)
        self.sidebar_btn.clicked.connect(self.toggle_sidebar)

        self.back_btn = QPushButton()
        self.back_btn.setIcon(QIcon(find_icon("back")))
        self.back_btn.setFixedSize(30, 30)
        self.back_btn.clicked.connect(self.navigate_back)
        self.back_btn.setEnabled(False)

        self.forward_btn = QPushButton()
        self.forward_btn.setIcon(QIcon(find_icon("forward")))
        self.forward_btn.setFixedSize(30, 30)
        self.forward_btn.clicked.connect(self.navigate_forward)
        self.forward_btn.setEnabled(False)

        self.refresh_btn = QPushButton()
        self.refresh_btn.setIcon(QIcon(find_icon("refresh")))
        self.refresh_btn.setFixedSize(30, 30)
        self.refresh_btn.clicked.connect(self.refresh_current_tab)
        self.refresh_btn.setEnabled(False)

        self.home_btn = QPushButton()
        self.home_btn.setIcon(QIcon(find_icon("home")))
        self.home_btn.setFixedSize(30, 30)
        # Changed: Connect to new go_to_homepage method
        self.home_btn.clicked.connect(self.go_to_homepage)

        self.address_bar = QLineEdit()
        self.address_bar.setObjectName("addressBar")
        self.address_bar.setPlaceholderText("Address or search...")
        self.address_bar.returnPressed.connect(self.load_url_from_address_bar)
        self.setup_completer()

        self.search_btn = QPushButton()
        self.search_btn.setIcon(QIcon(find_icon("search")))
        self.search_btn.setFixedSize(30, 30)
        self.search_btn.clicked.connect(self.handle_search_from_address_bar)

        self.share_btn = QPushButton()
        self.share_btn.setIcon(QIcon(find_icon("share")))
        self.share_btn.setFixedSize(30, 30)
        self.share_btn.clicked.connect(self.share_url)

        self.bookmark_btn = QPushButton()
        self.bookmark_btn.setIcon(QIcon(find_icon("bookmark")))
        self.bookmark_btn.setFixedSize(30, 30)
        self.bookmark_btn.clicked.connect(self.add_bookmark)

        self.bookmarks_menu_btn = QPushButton()
        self.bookmarks_menu_btn.setIcon(QIcon(find_icon("bookmarks_menu")))
        self.bookmarks_menu_btn.setFixedSize(30, 30)
        self.bookmarks_menu_btn.clicked.connect(self.show_bookmarks_menu)

        self.settings_btn = QPushButton()
        self.settings_btn.setIcon(QIcon(find_icon("settings")))
        self.settings_btn.setFixedSize(30, 30)
        self.settings_btn.clicked.connect(self.show_settings)

        self.save_pdf_btn = QPushButton()
        self.save_pdf_btn.setIcon(QIcon(find_icon("save_pdf")))
        self.save_pdf_btn.setFixedSize(30, 30)
        self.save_pdf_btn.clicked.connect(self.save_to_pdf)

        self.reading_mode_btn = QPushButton()
        self.reading_mode_btn.setIcon(QIcon(find_icon("reading_mode")))
        self.reading_mode_btn.setFixedSize(30, 30)
        self.reading_mode_btn.clicked.connect(self.toggle_reading_mode)

        self.zoom_btn = QPushButton()
        self.zoom_btn.setIcon(QIcon(find_icon("zoom")))
        self.zoom_btn.setFixedSize(30, 30)
        self.zoom_btn.clicked.connect(self.show_zoom_menu)

        self.history_btn = QPushButton()
        self.history_btn.setIcon(QIcon(find_icon("history")))
        self.history_btn.setFixedSize(30, 30)
        self.history_btn.clicked.connect(self.show_history)

        self.downloads_btn = QPushButton()
        self.downloads_btn.setIcon(QIcon(find_icon("downloads")))
        self.downloads_btn.setFixedSize(30, 30)
        self.downloads_btn.clicked.connect(self.show_downloads_manager)

        self.fullscreen_btn = QPushButton()
        self.fullscreen_btn.setIcon(QIcon(find_icon("fullscreen")))
        self.fullscreen_btn.setFixedSize(30, 30)
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)

        self.new_tab_btn = QPushButton()
        self.new_tab_btn.setIcon(QIcon(find_icon("new_tab")))
        self.new_tab_btn.setFixedSize(30, 30)
        self.new_tab_btn.clicked.connect(lambda: self.add_new_tab())

        self.extensions_btn = QPushButton()
        self.extensions_btn.setIcon(QIcon(find_icon("extensions")))
        self.extensions_btn.setFixedSize(30, 30)
        self.extensions_btn.clicked.connect(self.show_extensions_manager)

        self.devtools_btn = QPushButton()
        self.devtools_btn.setIcon(QIcon(find_icon("devtools")))
        self.devtools_btn.setFixedSize(30, 30)
        self.devtools_btn.clicked.connect(self.show_devtools)


        toolbar_layout.addWidget(self.sidebar_btn)
        toolbar_layout.addWidget(self.back_btn)
        toolbar_layout.addWidget(self.forward_btn)
        toolbar_layout.addWidget(self.refresh_btn)
        toolbar_layout.addWidget(self.home_btn)
        toolbar_layout.addWidget(self.address_bar)
        toolbar_layout.addWidget(self.search_btn)
        toolbar_layout.addWidget(self.share_btn)
        toolbar_layout.addWidget(self.bookmark_btn)
        toolbar_layout.addWidget(self.bookmarks_menu_btn)
        toolbar_layout.addWidget(self.settings_btn)
        toolbar_layout.addWidget(self.save_pdf_btn)
        toolbar_layout.addWidget(self.reading_mode_btn)
        toolbar_layout.addWidget(self.zoom_btn)
        toolbar_layout.addWidget(self.history_btn)
        toolbar_layout.addWidget(self.downloads_btn)
        toolbar_layout.addWidget(self.fullscreen_btn)
        toolbar_layout.addWidget(self.extensions_btn)
        toolbar_layout.addWidget(self.devtools_btn)
        toolbar_layout.addWidget(self.new_tab_btn)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(3)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        self.progress_bar.setObjectName("progressBar")

        # Custom Tab Bar Container
        self.custom_tab_bar_container = QWidget()
        self.custom_tab_bar_container.setFixedHeight(TAB_BUTTON_HEIGHT + 15)
        self.custom_tab_bar_container.setObjectName("customTabBarContainer")
        custom_tab_bar_layout = QHBoxLayout(self.custom_tab_bar_container)
        custom_tab_bar_layout.setContentsMargins(0, 0, 0, 0)
        custom_tab_bar_layout.setSpacing(0)

        # Fixed Home Tab Button
        self.home_tab_button = QPushButton("Home")
        self.home_tab_button.setObjectName("homeTabButton")
        self.home_tab_button.setFixedSize(TAB_BUTTON_WIDTH, TAB_BUTTON_HEIGHT)
        self.home_tab_button.clicked.connect(lambda: self.switch_to_custom_tab(0))
        custom_tab_bar_layout.addWidget(self.home_tab_button)

        # Scroll Area for Dynamic Tab Buttons
        self.tab_scroll_area = QScrollArea()
        self.tab_scroll_area.setObjectName("tabScrollArea")
        self.tab_scroll_area.setWidgetResizable(False)
        self.tab_scroll_area.setFixedHeight(TAB_BUTTON_HEIGHT + 10)
        self.tab_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.tab_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tab_scroll_area.setFixedWidth(TAB_BUTTON_WIDTH * 5 + 10) 

        self.tab_bar_widget = QWidget()
        self.tab_bar_widget.setObjectName("tabBarWidget")
        self.tab_bar_layout = QHBoxLayout(self.tab_bar_widget)
        self.tab_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.tab_bar_layout.setSpacing(2)
        self.tab_bar_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.tab_bar_widget.setLayout(self.tab_bar_layout)

        self.tab_scroll_area.setWidget(self.tab_bar_widget)
        custom_tab_bar_layout.addWidget(self.tab_scroll_area)

        # Tab Counter Label
        self.tab_counter_label = QLabel("Tabs: 0/0")
        self.tab_counter_label.setObjectName("tabCounterLabel")
        custom_tab_bar_layout.addWidget(self.tab_counter_label)
        custom_tab_bar_layout.addStretch()

        # QTabWidget (for content management, its tab bar is hidden)
        self.tab_widget = QTabWidget()
        self.tab_widget.setMovable(True)
        self.tab_widget.setTabsClosable(False)
        self.tab_widget.setElideMode(Qt.TextElideMode.ElideRight)
        self.tab_widget.setObjectName("tabWidget")
        self.tab_widget.tabBar().hide()
        self.tab_widget.currentChanged.connect(self.activate_tab)

        # Sidebar (Dock Widget)
        self.sidebar = QDockWidget("Bookmarks", self)
        self.sidebar.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        sidebar_widget = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_widget)
        self.bookmarks_list = QListWidget()
        self.bookmarks_list.setObjectName("bookmarksList")
        self.update_bookmarks_list()
        self.bookmarks_list.itemClicked.connect(self.load_url_from_bookmark_item)
        sidebar_layout.addWidget(self.bookmarks_list)
        self.sidebar.setWidget(sidebar_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.sidebar)
        self.sidebar.hide()

        # Add components to main layout
        main_layout.addWidget(self.header)
        main_layout.addWidget(toolbar)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.custom_tab_bar_container)
        main_layout.addWidget(self.tab_widget)

        # Initialize HomePage instance
        self.home_page = HomePage(self.history, self.bookmarks)
        self.home_page.search_triggered.connect(self.handle_search)

    def setup_completer(self):
        """Sets up the completer for the address bar based on history and bookmarks."""
        suggestions = list(set([entry["url"] for entry in self.history] +
                               [entry["url"] for entry in self.bookmarks] +
                               ["Search Google for...", "Wikipedia", "YouTube"]))
        self.completer = QCompleter(suggestions, self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.address_bar.setCompleter(self.completer)

    def setup_shortcuts(self):
        """Sets up global keyboard shortcuts for browser actions."""
        QShortcut(QKeySequence("Ctrl+T"), self, lambda: self.add_new_tab())
        QShortcut(QKeySequence("Ctrl+W"), self, lambda: self.close_tab(self.tab_widget.currentIndex()))
        QShortcut(QKeySequence("Ctrl+R"), self, self.refresh_current_tab)
        QShortcut(QKeySequence("Ctrl+H"), self, self.show_history)
        QShortcut(QKeySequence("Ctrl+B"), self, self.show_bookmarks_menu)
        QShortcut(QKeySequence("F11"), self, self.toggle_fullscreen)
        QShortcut(QKeySequence("Ctrl+L"), self, self.address_bar.setFocus)
        QShortcut(QKeySequence("Ctrl+Shift+T"), self, self.reopen_last_closed_tab)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, self.suspend_current_tab_manual)

    def reopen_last_closed_tab(self):
        """Reopens the last closed tab (basic implementation, could be improved)."""
        QMessageBox.information(self, "Feature In Progress", "Reopening last closed tab is not yet implemented.")

    def suspend_current_tab_manual(self):
        """Suspends the currently active tab manually."""
        current_index = self.tab_widget.currentIndex()
        if current_index == -1: return
        
        current_widget = self.tab_widget.widget(current_index)
        if isinstance(current_widget, QWebEngineView):
            if current_widget == self.home_page:
                QMessageBox.warning(self, "Suspend Tab", "Cannot suspend the Home tab.")
                return
            if current_widget in self.suspended_tabs_data:
                QMessageBox.information(self, "Suspend Tab", "This tab is already suspended.")
                return
            
            self.suspend_tab(current_index, current_widget)
            QMessageBox.information(self, "Suspend Tab", "Current tab suspended to save memory.")
        else:
            QMessageBox.warning(self, "Suspend Tab", "Only web pages can be suspended.")

    def get_current_web_view(self):
        """Returns the QWebEngineView of the currently active tab, or None."""
        current_widget = self.tab_widget.currentWidget()
        if isinstance(current_widget, QWebEngineView):
            return current_widget
        return None

    def navigate_back(self):
        """Navigates back in the current tab's history."""
        web_view = self.get_current_web_view()
        if web_view:
            web_view.back()

    def navigate_forward(self):
        """Navigates forward in the current tab's history."""
        web_view = self.get_current_web_view()
        if web_view:
            web_view.forward()

    def refresh_current_tab(self):
        """Refreshes the current tab."""
        web_view = self.get_current_web_view()
        if web_view:
            web_view.reload()

def go_to_homepage(self):
    """Navigates to the configured homepage URL."""
    homepage_url_setting = self.settings.get("homepage_url", "about:home")
    
    if homepage_url_setting == "about:home":
        # If the setting is "about:home", try to find the HomePage widget
        home_page_index = self.tab_widget.indexOf(self.home_page)
        if home_page_index != -1:
            # If HomePage is already open, switch to it
            self.tab_widget.setCurrentIndex(home_page_index)
            self.activate_tab(home_page_index)
        else:
            # If HomePage is not open, add it at index 0
            self.add_new_tab(url="about:home", is_home=True)
    else:
        # For a regular URL homepage, try to find if it's already open
        homepage_url_normalized = homepage_url_setting
        if not (homepage_url_normalized.startswith("http://") or homepage_url_normalized.startswith("https://")):
            homepage_url_normalized = "https://" + homepage_url_normalized
            
        # Check all tabs for matching URL
        found_index = -1
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if isinstance(widget, QWebEngineView) and widget.url().toString() == homepage_url_normalized:
                found_index = i
                break
                
        if found_index != -1:
            # If homepage URL is already open in a tab, switch to it
            self.tab_widget.setCurrentIndex(found_index)
            self.activate_tab(found_index)
        else:
            # Open a new tab with the homepage URL
            self.add_new_tab(url=homepage_url_setting)


    def add_new_tab(self, url="", is_home=False):
        """
        Adds a new tab to the browser.
        If is_home is True, adds the HomePage widget.
        Otherwise, adds a QWebEngineView and loads the specified URL or a default.
        """
        max_tabs = self.settings.get("max_tabs", 30)
        
        current_dynamic_tabs = self.tab_widget.count() - (1 if self.tab_widget.indexOf(self.home_page) != -1 else 0)
        if not is_home and current_dynamic_tabs >= max_tabs:
            QMessageBox.warning(self, "Warning", f"Maximum number of tabs ({max_tabs}) reached!")
            return

        widget = None
        tab_title = "New Tab"
        suspended_data = None

        if is_home:
            # This block is specifically for the internal HomePage widget
            # The go_to_homepage method already handles checking if it's open.
            # This ensures it's always the HomePage widget, not a QWebEngineView loading "about:home"
            widget = self.home_page
            tab_title = "Home"
            self.home_page.history = self.history
            self.home_page.bookmarks = self.bookmarks
            self.home_page.setup_completer()
        elif url.startswith("about:suspended_"):
            placeholder_id_str = url.split("about:suspended_")[1]
            found_placeholder = None
            for ph_widget, data in self.suspended_tabs_data.items():
                if str(id(ph_widget)) == placeholder_id_str:
                    found_placeholder = ph_widget
                    suspended_data = data
                    break
            
            if suspended_data and found_placeholder:
                url = suspended_data['url']
                tab_title = suspended_data['title']
                original_index = self.tab_widget.indexOf(found_placeholder)
                if original_index != -1:
                    self.tab_widget.removeTab(original_index)
                    self.custom_tab_buttons_map.pop(found_placeholder, None)
                    found_placeholder.deleteLater()
                self.suspended_tabs_data.pop(found_placeholder, None)
            else:
                url = "about:blank"

        if not widget: # If not a special home page or suspended page, create a QWebEngineView
            web_view = QWebEngineView()
            page = QWebEnginePage(self.profile, web_view)
            page.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            page.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            web_view.setPage(page)
            web_view.setCursor(Qt.CursorShape.ArrowCursor)

            page.featurePermissionRequested.connect(self.handle_feature_permission_request)

            web_view.titleChanged.connect(lambda title: self.update_tab_title(web_view, title))
            web_view.urlChanged.connect(lambda url: self.update_address_bar_and_history(web_view, url))
            web_view.loadStarted.connect(self.show_progress)
            web_view.loadProgress.connect(self.update_progress)
            web_view.loadFinished.connect(lambda ok: self.hide_progress_and_handle_error(ok, web_view))
            web_view.page().linkHovered.connect(self.show_link_status)
            web_view.page().fullScreenRequested.connect(self.handle_fullscreen_request)
            
            web_view.page().loadFinished.connect(lambda ok: self.extension_manager.apply_content_scripts(web_view.page()))

            if not url:
                url = "about:blank"
            if not (url.startswith('http://') or url.startswith('https://') or url.startswith('about:')):
                url = 'https://' + url
            web_view.load(QUrl(url))
            widget = web_view
            if not is_home and not suspended_data:
                tab_title = "New Tab"

        if is_home:
            index = self.tab_widget.insertTab(0, widget, tab_title)
        else:
            index = self.tab_widget.addTab(widget, tab_title)

        self.tab_widget.setCurrentIndex(index)
        self.create_custom_tab_button(widget, tab_title, index)
        self.activate_tab(index)
        self.update_tab_bar_scroll()
        self.update_tab_counter()
        self.tab_last_active_time[widget] = datetime.now()

    def create_custom_tab_button(self, widget, title, index):
        """Creates a custom tab button (QWidget with QPushButton and QToolButton) for the given widget."""
        tab_button_container = QWidget()
        tab_button_container.setObjectName("CustomTabButton")
        tab_button_layout = QHBoxLayout(tab_button_container)
        tab_button_layout.setContentsMargins(5, 0, 0, 0)
        tab_button_layout.setSpacing(0)

        tab_button = QPushButton(title)
        tab_button.setToolTip(title)
        tab_button.setFlat(True)
        tab_button.clicked.connect(lambda: self.switch_to_custom_tab(index))
        tab_button_layout.addWidget(tab_button)

        if widget != self.home_page:
            close_button = QToolButton()
            close_button.setIcon(QIcon(find_icon("close")))
            close_button.setFixedSize(20, 20)
            close_button.clicked.connect(lambda: self.close_tab(index))
            tab_button_layout.addWidget(close_button)

        tab_button_container.setFixedSize(TAB_BUTTON_WIDTH, TAB_BUTTON_HEIGHT)
        
        if widget == self.home_page:
            self.home_tab_button.setText(title)
            self.home_tab_button.setToolTip(title)
            self.custom_tab_buttons_map[widget] = self.home_tab_button
        else:
            self.tab_bar_layout.addWidget(tab_button_container)
            self.custom_tab_buttons_map[widget] = tab_button_container
        
        self.update_tab_bar_scroll()

    def update_tab_title(self, web_view, title):
        """Updates the title of the tab associated with the given web_view."""
        index = self.tab_widget.indexOf(web_view)
        if index != -1:
            self.tab_widget.setTabText(index, title[:20] or "New Tab")
            custom_button_container = self.custom_tab_buttons_map.get(web_view)
            if custom_button_container:
                for item in custom_button_container.children():
                    if isinstance(item, QPushButton):
                        item.setText(title[:20] or "New Tab")
                        item.setToolTip(title)
                        break

    def update_address_bar_and_history(self, web_view, url):
        """Updates the address bar and adds the URL to history for the current tab."""
        if self.tab_widget.currentWidget() == web_view:
            self.address_bar.setText(url.toString())
            self.add_to_history(url)
            self.back_btn.setEnabled(web_view.page().history().canGoBack())
            self.forward_btn.setEnabled(web_view.page().history().canGoForward())
            self.refresh_btn.setEnabled(True)

    def switch_to_custom_tab(self, index):
        """Switches to the tab at the given index when a custom tab button is clicked."""
        if 0 <= index < self.tab_widget.count():
            if self.tab_widget.currentIndex() != index:
                self.tab_widget.setCurrentIndex(index)

    def activate_tab(self, index):
        """
        Called when the current tab changes.
        Updates the address bar, button states, and highlights the custom tab button.
        """
        for btn_widget in self.custom_tab_buttons_map.values():
            btn_widget.setProperty("active", False)
            btn_widget.style().polish(btn_widget)

        if index < 0:
            self.address_bar.setText("")
            self.back_btn.setEnabled(False)
            self.forward_btn.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            self.share_btn.setEnabled(False)
            self.update_tab_counter()
            return

        current_widget = self.tab_widget.widget(index)
        if current_widget:
            self.tab_last_active_time[current_widget] = datetime.now()

            custom_button_container = self.custom_tab_buttons_map.get(current_widget)
            if custom_button_container:
                custom_button_container.setProperty("active", True)
                custom_button_container.style().polish(custom_button_container)

                if custom_button_container != self.home_tab_button:
                    scroll_bar = self.tab_scroll_area.horizontalScrollBar()
                    tab_x = custom_button_container.x()
                    tab_width = custom_button_container.width()
                    scroll_view_width = self.tab_scroll_area.viewport().width()

                    if tab_x < scroll_bar.value():
                        scroll_bar.setValue(tab_x)
                    elif tab_x + tab_width > scroll_bar.value() + scroll_view_width:
                        scroll_bar.setValue(tab_x + tab_width - scroll_view_width)

            if isinstance(current_widget, QWebEngineView):
                self.address_bar.setText(current_widget.url().toString())
                self.back_btn.setEnabled(current_widget.page().history().canGoBack())
                self.forward_btn.setEnabled(current_widget.page().history().canGoForward())
                self.refresh_btn.setEnabled(True)
                self.share_btn.setEnabled(True)
                if self.reading_mode:
                    self.toggle_reading_mode(force_on=True)
            elif isinstance(current_widget, HomePage):
                self.address_bar.setText("")
                self.back_btn.setEnabled(False)
                self.forward_btn.setEnabled(False)
                self.refresh_btn.setEnabled(False)
                self.share_btn.setEnabled(False)
                if self.reading_mode:
                    self.toggle_reading_mode(force_off=True)

        self.update_tab_counter()

    def close_tab(self, index):
        """Closes the tab at the given index and cleans up the widget and custom button."""
        if self.tab_widget.widget(index) == self.home_page:
            QMessageBox.warning(self, "Cannot Close Tab", "The Home tab cannot be closed directly.")
            return

        if self.tab_widget.count() <= 1: 
            QMessageBox.warning(self, "Cannot Close Last Tab", "Cannot close the last browsing tab. Open a new one first.")
            return

        self._do_close_tab(index)

    def _do_close_tab(self, index):
        """Internal method to perform the tab closing."""
        widget_to_close = self.tab_widget.widget(index)
        if widget_to_close:
            self.tab_last_active_time.pop(widget_to_close, None)
            self.suspended_tabs_data.pop(widget_to_close, None)

            custom_button_container = self.custom_tab_buttons_map.pop(widget_to_close, None)
            if custom_button_container:
                self.tab_bar_layout.removeWidget(custom_button_container)
                custom_button_container.deleteLater()

            self.tab_widget.removeTab(index)

            if isinstance(widget_to_close, QWebEngineView):
                widget_to_close.setParent(None)
                widget_to_close.deleteLater()
            elif isinstance(widget_to_close, HomePage):
                pass

            self.update_tab_bar_scroll()
            self.update_tab_counter()

    def update_tab_bar_scroll(self):
        """Adjusts the minimum width of the tab bar widget to enable/disable scrolling."""
        num_dynamic_tabs = self.tab_widget.count() - (1 if self.tab_widget.indexOf(self.home_page) != -1 else 0)
        
        if num_dynamic_tabs > 0:
            total_width = num_dynamic_tabs * TAB_BUTTON_WIDTH + (num_dynamic_tabs - 1) * self.tab_bar_layout.spacing()
        else:
            total_width = 0
        
        self.tab_bar_widget.setMinimumWidth(max(0, total_width))
        self.tab_bar_widget.adjustSize()
        
        scroll_content_width = self.tab_bar_widget.width()
        scroll_area_viewport_width = self.tab_scroll_area.viewport().width()
        self.tab_scroll_area.horizontalScrollBar().setMaximum(max(0, scroll_content_width - scroll_area_viewport_width))

    def update_tab_counter(self):
        """Updates the tab counter label."""
        total_tabs = self.tab_widget.count()
        current_index = self.tab_widget.currentIndex()
        
        is_home_tab_at_zero = (total_tabs > 0 and self.tab_widget.widget(0) == self.home_page)

        display_current_index = 0
        display_total_tabs = 0

        if total_tabs > 0:
            if is_home_tab_at_zero:
                display_total_tabs = total_tabs - 1
                if current_index == 0:
                    display_current_index = 0
                else:
                    display_current_index = current_index
            else:
                display_total_tabs = total_tabs
                display_current_index = current_index + 1
        
        self.tab_counter_label.setText(f"Tabs: {display_current_index}/{display_total_tabs}")

    def load_url_from_address_bar(self):
        """Loads the URL from the address bar or performs a search."""
        url_or_query = self.address_bar.text().strip()
        if not url_or_query:
            return

        search_engine = self.settings.get("default_search_engine", "yahoo")
        base_search_url = SEARCH_ENGINE_URLS.get(search_engine, SEARCH_ENGINE_URLS["yahoo"])

        if url_or_query.lower().startswith("wikipedia"):
            query = url_or_query.replace("wikipedia", "").strip()
            self.add_new_tab(f"https://en.wikipedia.org/wiki/{query.replace(' ', '_')}")
        elif url_or_query.lower().startswith("youtube"):
            query = url_or_query.replace("youtube", "").strip()
            self.add_new_tab(f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}")
        elif url_or_query.lower() == "about:home":
            self.go_to_homepage() # Use the dedicated method
        else:
            if '.' in url_or_query and not ' ' in url_or_query:
                if not (url_or_query.startswith('http://') or url_or_query.startswith('https://')):
                    url_or_query = 'https://' + url_or_query
                self.add_new_tab(url_or_query)
            else:
                self.add_new_tab(base_search_url + QUrl.toPercentEncoding(url_or_query).data().decode())

    def handle_search(self, query):
        """Performs a search for the given query in a new tab using the default search engine."""
        if not query:
            return
        search_engine = self.settings.get("default_search_engine", "yahoo")
        base_search_url = SEARCH_ENGINE_URLS.get(search_engine, SEARCH_ENGINE_URLS["yahoo"])
        search_url = base_search_url + QUrl.toPercentEncoding(query).data().decode()
        self.add_new_tab(search_url)

    def handle_search_from_address_bar(self):
        """Triggers a search using the text in the address bar."""
        self.load_url_from_address_bar()

    def add_to_history(self, url):
        """Adds the given URL to the browser's history."""
        url_str = url.toString()
        if not url_str or url_str == "about:blank" or url_str == "https://www.example.com/" or url_str.startswith("about:error") or url_str.startswith("about:suspended"):
            return

        if self.history and self.history[-1]["url"] == url_str:
            return

        entry = {
            "url": url_str,
            "title": self.tab_widget.tabText(self.tab_widget.currentIndex()),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.history.append(entry)
        if len(self.history) > 1000:
            self.history = self.history[-1000:]
        self.data_manager.save_history(self.history)
        self.home_page.history = self.history
        self.home_page.setup_completer()
        self.setup_completer()

    def show_progress(self):
        """Shows the progress bar."""
        self.progress_bar.setVisible(True)

    def update_progress(self, progress):
        """Updates the progress bar value."""
        self.progress_bar.setValue(progress)

    def hide_progress_and_handle_error(self, ok, web_view):
        """Hides the progress bar and displays an error page if loading failed."""
        self.progress_bar.setVisible(False)
        if not ok:
            error_html = """
            <div style="text-align: center; font-family: Arial, sans-serif; margin-top: 50px;">
                <h1 style="color: #e74c3c;">Page Load Error</h1>
                <p style="font-size: 1.2em;">Unfortunately, the page could not be loaded.</p>
                <p>Please check the following:</p>
                <ul style="list-style-type: none; padding: 0;">
                    <li>Check your <strong style="color: #3498db;">internet connection</strong>.</li>
                    <li>Double-check the <strong style="color: #3498db;">URL</strong>.</li>
                    <li>The website server might be unavailable.</li>
                </ul>
                <p style="font-size: 0.9em; color: #7f8c8d;">Doors Browser</p>
            </div>
            """
            web_view.setHtml(error_html, QUrl("about:error"))

    def add_bookmark(self):
        """Adds the current page to bookmarks."""
        current_web_view = self.get_current_web_view()
        if current_web_view:
            url = current_web_view.url().toString()
            title = self.tab_widget.tabText(self.tab_widget.currentIndex())
            entry = {"url": url, "title": title}
            if entry not in self.bookmarks:
                self.bookmarks.append(entry)
                self.data_manager.save_bookmarks(self.bookmarks)
                self.home_page.bookmarks = self.bookmarks
                self.home_page.setup_completer()
                self.setup_completer()
                self.update_bookmarks_list()
                QMessageBox.information(self, "Bookmark", f"Page '{title}' added to bookmarks.")
            else:
                QMessageBox.information(self.tab_widget, "Bookmark", "This page is already bookmarked.")
        else:
            QMessageBox.warning(self, "Bookmark", "No web page is active to bookmark.")

    def update_bookmarks_list(self):
        """Updates the bookmarks list in the sidebar."""
        self.bookmarks_list.clear()
        for bookmark in self.bookmarks:
            item = QListWidgetItem(bookmark["title"])
            item.setData(Qt.ItemDataRole.UserRole, bookmark["url"])
            self.bookmarks_list.addItem(item)

    def load_url_from_bookmark_item(self, item):
        """Loads the URL from a clicked bookmark item in a new tab."""
        url = item.data(Qt.ItemDataRole.UserRole)
        self.add_new_tab(url)

    def show_bookmarks_menu(self):
        """Displays a context menu with bookmarks."""
        menu = QMenu(self)
        if not self.bookmarks:
            menu.addAction("No bookmarks available.").setEnabled(False)
        else:
            for entry in reversed(self.bookmarks): # Show newest first
                action = QAction(entry["title"], self)
                action.triggered.connect(lambda checked, url=entry["url"]: self.add_new_tab(url))
                menu.addAction(action)
        menu.exec(self.bookmarks_menu_btn.mapToGlobal(self.bookmarks_menu_btn.rect().bottomLeft()))

    def show_settings(self):
        """Displays the settings dialog."""
        self.settings_dialog = SettingsDialog(self.settings, self)
        self.settings_dialog.settings_updated.connect(self.apply_settings)
        self.settings_dialog.clear_history_requested.connect(self.clear_history)
        self.settings_dialog.clear_cache_requested.connect(self.clear_cache)
        self.settings_dialog.clear_cookies_requested.connect(self.clear_cookies)
        self.settings_dialog.sync_upload_requested.connect(self.data_manager.sync_data_to_cloud)
        self.settings_dialog.sync_download_requested.connect(self.sync_data_from_cloud_and_reload)
        self.settings_dialog.bookmark_import_json_requested.connect(self.import_bookmarks_json)
        self.settings_dialog.bookmark_export_json_requested.connect(self.export_bookmarks_json)
        self.settings_dialog.bookmark_import_html_requested.connect(self.import_bookmarks_html)
        self.settings_dialog.bookmark_export_html_requested.connect(self.export_bookmarks_html)
        self.settings_dialog.manage_site_permissions_requested.connect(self.show_site_permissions_manager)
        # Connect accepted signal to show success message
        self.settings_dialog.accepted.connect(lambda: QMessageBox.information(self, "Settings", "Settings saved successfully."))
        self.settings_dialog.exec()

    def _apply_initial_settings(self, new_settings):
        """Applies settings on startup without showing pop-up messages."""
        self.settings.update(new_settings)
        # No data_manager.save_settings here, as it's assumed to be loaded from disk already

        self.apply_theme(self.settings.get("theme", "light")) # This will save settings internally
        self.check_auto_night_mode()

        self.max_tabs = self.settings.get("max_tabs", 30)

        self.adblock_interceptor.set_adblock_enabled(self.settings.get("adblock_enabled", True))
        self.adblock_interceptor.set_block_third_party_cookies(self.settings.get("block_third_party_cookies", False))
        self.adblock_interceptor.set_send_dnt_header(self.settings.get("send_dnt_header", False))

        self.default_download_path = self.settings.get("download_path", QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation))

        self.apply_font_settings(self.settings.get("default_font_family", "Arial"), self.settings.get("default_font_size", 16))

        self.apply_preferred_web_languages(self.settings.get("preferred_web_languages", "en-US,en;q=0.9"))

    def apply_settings(self, new_settings):
        """Applies settings received from the SettingsDialog (shows pop-ups if needed)."""
        self.settings.update(new_settings)
        self.data_manager.save_settings(self.settings)

        self.apply_theme(self.settings.get("theme", "light"))
        self.check_auto_night_mode()

        self.max_tabs = self.settings.get("max_tabs", 30)

        self.adblock_interceptor.set_adblock_enabled(self.settings.get("adblock_enabled", True))
        self.adblock_interceptor.set_block_third_party_cookies(self.settings.get("block_third_party_cookies", False))
        self.adblock_interceptor.set_send_dnt_header(self.settings.get("send_dnt_header", False))

        self.default_download_path = self.settings.get("download_path", QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation))

        self.apply_font_settings(self.settings.get("default_font_family", "Arial"), self.settings.get("default_font_size", 16))

        self.apply_preferred_web_languages(self.settings.get("preferred_web_languages", "en-US,en;q=0.9"))

    def clear_history(self):
        self.history = []
        self.data_manager.save_history(self.history)
        self.home_page.history = self.history
        self.home_page.setup_completer()
        self.setup_completer()
        QMessageBox.information(self, "History", "Browser history cleared.")

    def clear_cache(self):
        self.profile.clearHttpCache()
        QMessageBox.information(self, "Cache", "Browser cache cleared.")

    def clear_cookies(self):
        self.profile.cookieStore().deleteAllCookies()
        QMessageBox.information(self, "Cookies", "Browser cookies cleared.")

    def apply_font_settings(self, font_family, font_size):
        """Applies default font family and size to QWebEngineSettings."""
        web_settings = self.profile.settings()
        web_settings.setFontFamily(QWebEngineSettings.FontFamily.StandardFont, font_family)
        web_settings.setFontSize(QWebEngineSettings.FontSize.DefaultFontSize, font_size)
        web_settings.setFontFamily(QWebEngineSettings.FontFamily.SerifFont, font_family)
        web_settings.setFontFamily(QWebEngineSettings.FontFamily.SansSerifFont, font_family)
        web_settings.setFontFamily(QWebEngineSettings.FontFamily.FixedFont, "monospace")
        print(f"Applied default font: {font_family}, size: {font_size}")

    def apply_preferred_web_languages(self, languages_string):
        """Sets the Accept-Language header for web requests."""
        self.profile.setHttpAcceptLanguage(languages_string)
        print(f"Preferred web languages set to: {languages_string}")

    def show_site_permissions_manager(self):
        site_perm_dialog = SitePermissionsDialog(self.data_manager, self)
        site_perm_dialog.exec()
        self.site_permissions = self.data_manager.load_data()["site_permissions"]

    def restore_last_session(self):
        QMessageBox.information(self, "Restore Session", "Restoring last session is not yet implemented.")

    def import_bookmarks_json(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Bookmarks from JSON", "", "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    imported_data = json.load(f)
                if "entries" in imported_data and isinstance(imported_data["entries"], list):
                    new_bookmarks = []
                    for entry in imported_data["entries"]:
                        if "url" in entry and "title" in entry:
                            if {"url": entry["url"], "title": entry["title"]} not in self.bookmarks:
                                new_bookmarks.append({"url": entry["url"], "title": entry["title"]})
                    self.bookmarks.extend(new_bookmarks)
                    self.data_manager.save_bookmarks(self.bookmarks)
                    self.update_bookmarks_list()
                    self.home_page.bookmarks = self.bookmarks
                    self.home_page.setup_completer()
                    self.setup_completer()
                    QMessageBox.information(self, "Import Bookmarks", f"{len(new_bookmarks)} new bookmarks imported.")
                else:
                    QMessageBox.warning(self, "Error", "Invalid bookmark JSON file format.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error importing bookmarks: {e}")

    def export_bookmarks_json(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Bookmarks to JSON", "bookmarks.json", "JSON Files (*.json)")
        if file_path:
            try:
                self.data_manager.save_bookmarks(self.bookmarks) # Ensure latest data is saved
                shutil.copy(os.path.join(DATA_DIR, "bookmarks.json"), file_path)
                QMessageBox.information(self, "Export Bookmarks", f"Bookmarks successfully exported to '{file_path}'.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error exporting bookmarks: {e}")

    def import_bookmarks_html(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Bookmarks from HTML", "", "HTML Files (*.html *.htm)")
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    html_content = f.read()
                
                new_bookmarks = []
                pattern = re.compile(r'<A HREF="([^"]+)"[^>]*>(.*?)</A>', re.IGNORECASE | re.DOTALL)
                for match in pattern.finditer(html_content):
                    url = match.group(1)
                    title = match.group(2).strip()
                    title = re.sub(r'<[^>]+>', '', title)
                    if url and title:
                        if {"url": url, "title": title} not in self.bookmarks:
                            new_bookmarks.append({"url": url, "title": title})

                self.bookmarks.extend(new_bookmarks)
                self.data_manager.save_bookmarks(self.bookmarks)
                self.update_bookmarks_list()
                self.home_page.bookmarks = self.bookmarks
                self.home_page.setup_completer()
                self.setup_completer()
                QMessageBox.information(self, "Import Bookmarks", f"{len(new_bookmarks)} new bookmarks imported.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error importing bookmarks: {e}")

    def export_bookmarks_html(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Bookmarks to HTML", "bookmarks.html", "HTML Files (*.html *.htm)")
        if file_path:
            try:
                html_content = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
                <META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
                <TITLE>Bookmarks</TITLE>
                <H1>Bookmarks</H1>
                <DL><p>
                """
                for bookmark in self.bookmarks:
                    html_content += f'    <DT><A HREF="{bookmark["url"]}">{bookmark["title"]}</A>\n'
                html_content += """</DL><p>"""

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                QMessageBox.information(self, "Export Bookmarks", f"Bookmarks successfully exported to '{file_path}'.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error exporting bookmarks: {e}")

    def apply_theme(self, theme):
        """Applies the specified theme (light/dark) using QSS files."""
        self.settings["theme"] = theme
        self.data_manager.save_settings(self.settings) # Save theme setting
        style_path = os.path.join(STYLES_DIR, f"{theme}.qss")
        if os.path.exists(style_path):
            try:
                with open(style_path, "r", encoding="utf-8") as f:
                    self.setStyleSheet(f.read())
            except Exception as e:
                print(f"Error loading QSS from {style_path}: {e}")
                self.set_default_stylesheet(theme)
        else:
            print(f"QSS file for theme '{theme}' not found at {style_path}. Applying default styles.")
            self.set_default_stylesheet(theme)

    def set_default_stylesheet(self, theme):
        """Applies a basic hardcoded stylesheet if QSS file is missing."""
        if theme == "light":
            self.setStyleSheet(f"""
                QMainWindow {{ background-color: #f0f0f0; color: #333333; }}
                #header {{ background-color: #e0e0e0; border-bottom: 1px solid #cccccc; }}
                #toolbar {{ background-color: #e8e8e8; border-bottom: 1px solid #cccccc; }}
                #addressBar {{ background-color: white; border: 1px solid #cccccc; padding: 3px; border-radius: 5px; }}
                QPushButton {{ background-color: #f5f5f5; border: 1px solid #cccccc; border-radius: 3px; padding: 5px; }}
                QPushButton:hover {{ background-color: #e0e0e0; }}
                QPushButton:pressed {{ background-color: #d0d0d0; }}
                #homeTabButton {{
                    background-color: #c0c0c0;
                    border: 1px solid #b0b0b0;
                    border-bottom: none;
                    border-top-left-radius: 5px;
                    border-top-right-radius: 5px;
                    margin-right: 2px;
                    padding: 5px;
                }}
                #homeTabButton.active {{
                    background-color: white;
                    border-bottom: 1px solid white;
                }}
                .CustomTabButton {{ 
                    background-color: #c0c0c0; 
                    border: 1px solid #b0b0b0; 
                    border-bottom: none; 
                    border-top-left-radius: 5px; 
                    border-top-right-radius: 5px; 
                    margin-right: 2px;
                }}
                .CustomTabButton:hover {{ background-color: #b0b0b0; }}
                .CustomTabButton.active {{ 
                    background-color: white; 
                    border-bottom: 1px solid white; 
                }}
                .CustomTabButton QPushButton {{
                    background-color: transparent;
                    border: none;
                    padding: 0px 5px;
                    min-width: {TAB_BUTTON_WIDTH - 30}px;
                    max-width: {TAB_BUTTON_WIDTH - 30}px;
                    text-align: left;
                    color: #333333;
                }}
                .CustomTabButton QToolButton {{
                    background-color: transparent;
                    border: none;
                    padding: 0 5px;
                    margin-left: 5px;
                }}
                #tabCounterLabel {{ color: #555555; }}
                QDialog {{ background-color: #f0f0f0; color: #333333; }}
                QDialog QLabel {{ color: #333333; }}
                QDialog QLineEdit, QDialog QComboBox, QDialog QSpinBox, QDialog QFontComboBox {{ background-color: white; border: 1px solid #cccccc; padding: 5px; border-radius: 3px; }}
                QDialog QPushButton {{ background-color: #4CAF50; color: white; border: none; padding: 8px 15px; border-radius: 5px; }}
                QProgressBar {{ background-color: #e0e0e0; border: none; text-align: center; }}
                QProgressBar::chunk {{ background-color: #4CAF50; }}
            """)
        else:
            self.setStyleSheet(f"""
                QMainWindow {{ background-color: #2e2e2e; color: #e0e0e0; }}
                #header {{ background-color: #3a3a3a; border-bottom: 1px solid #555555; }}
                #toolbar {{ background-color: #4a4a4a; border-bottom: 1px solid #555555; }}
                #addressBar {{ background-color: #5a5a5a; border: 1px solid #666666; padding: 3px; border-radius: 5px; color: #e0e0e0; }}
                QPushButton {{ background-color: #5a5a5a; border: 1px solid #666666; border-radius: 3px; padding: 5px; color: #e0e0e0; }}
                QPushButton:hover {{ background-color: #6a6a6a; }}
                QPushButton:pressed {{ background-color: #7a7a7a; }}
                #homeTabButton {{
                    background-color: #4a4a4a;
                    border: 1px solid #666666;
                    border-bottom: none;
                    border-top-left-radius: 5px;
                    border-top-right-radius: 5px;
                    margin-right: 2px;
                    padding: 5px;
                    color: #e0e0e0;
                }}
                #homeTabButton.active {{
                    background-color: #3e3e3e;
                    border-bottom: 1px solid #3e3e3e;
                }}
                .CustomTabButton {{ 
                    background-color: #5a5a5a; 
                    border: 1px solid #666666; 
                    border-bottom: none; 
                    border-top-left-radius: 5px; 
                    border-top-right-radius: 5px; 
                    margin-right: 2px;
                }}
                .CustomTabButton:hover {{ background-color: #6a6a6a; }}
                .CustomTabButton.active {{ 
                    background-color: #3e3e3e; 
                    border-bottom: 1px solid #3e3e3e; 
                }}
                .CustomTabButton QPushButton {{
                    background-color: transparent;
                    border: none;
                    padding: 0px 5px;
                    min-width: {TAB_BUTTON_WIDTH - 30}px;
                    max-width: {TAB_BUTTON_WIDTH - 30}px;
                    text-align: left;
                    color: #e0e0e0;
                }}
                .CustomTabButton QToolButton {{
                    background-color: transparent;
                    border: none;
                    padding: 0 5px;
                    margin-left: 5px;
                    color: #e0e0e0;
                }}
                #tabCounterLabel {{ color: #aaaaaa; }}
                QDialog {{ background-color: #3e3e3e; color: #e0e0e0; }}
                QDialog QLabel {{ color: #e0e0e0; }}
                QDialog QLineEdit, QDialog QComboBox, QDialog QSpinBox, QDialog QFontComboBox {{ background-color: #5a5a5a; border: 1px solid #666666; padding: 5px; border-radius: 3px; color: #e0e0e0; }}
                QDialog QPushButton {{ background-color: #27ae60; color: white; border: none; padding: 8px 15px; border-radius: 5px; }}
                QProgressBar {{ background-color: #4a4a4a; border: none; text-align: center; }}
                QProgressBar::chunk {{ background-color: #27ae60; }}
            """)

    def check_auto_night_mode(self):
        """Checks if auto night mode should be applied based on time."""
        if self.settings.get("auto_night_mode", False):
            current_hour = datetime.now().hour
            if 18 <= current_hour or current_hour < 6:
                if self.settings.get("theme") != "dark":
                    self.apply_theme("dark")
            else:
                if self.settings.get("theme") != "light":
                    self.apply_theme("light")

    def handle_feature_permission_request(self, url, feature):
        """Handles requests for features like camera, microphone, geolocation."""
        origin = url.url().toString().split('/')[0] + '//' + url.url().host()
        feature_name = feature.name

        for perm in self.site_permissions:
            if perm['origin'] == origin and perm['feature'] == feature_name:
                if perm['allowed']:
                    url.grantFeaturePermission(feature)
                    print(f"Granted {feature_name} permission for {origin} (pre-approved).")
                else:
                    url.denyFeaturePermission(feature)
                    print(f"Denied {feature_name} permission for {origin} (pre-blocked).")
                return

        reply = QMessageBox.question(self, "Permission Request",
                                     f"The website '{origin}' is requesting access to your {feature_name}. Do you want to allow it?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
        
        if reply == QMessageBox.StandardButton.Yes:
            url.grantFeaturePermission(feature)
            self.site_permissions.append({"origin": origin, "feature": feature_name, "allowed": True})
            self.data_manager.save_site_permissions(self.site_permissions)
            print(f"Granted {feature_name} permission for {origin}.")
        elif reply == QMessageBox.StandardButton.No:
            url.denyFeaturePermission(feature)
            self.site_permissions.append({"origin": origin, "feature": feature_name, "allowed": False})
            self.data_manager.save_site_permissions(self.site_permissions)
            print(f"Denied {feature_name} permission for {origin}.")
        else:
            url.denyFeaturePermission(feature)
            print(f"Permission request for {feature_name} from {origin} cancelled by user.")

    def check_and_suspend_inactive_tabs(self):
        """Periodically checks for inactive tabs and suspends them."""
        if not self.settings.get("suspend_inactive_tabs", True):
            return

        suspend_timeout_seconds = self.settings.get("suspend_timeout_minutes", 5) * 60
        current_time = datetime.now()
        current_active_widget = self.tab_widget.currentWidget()

        widgets_to_suspend = []
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if widget == current_active_widget or isinstance(widget, HomePage) or widget in self.suspended_tabs_data:
                continue

            if isinstance(widget, QWebEngineView):
                last_active = self.tab_last_active_time.get(widget)
                if last_active and (current_time - last_active).total_seconds() > suspend_timeout_seconds:
                    widgets_to_suspend.append((i, widget))

        for index, web_view in widgets_to_suspend:
            self.suspend_tab(index, web_view)

    def suspend_tab(self, index, web_view):
        """Suspends a QWebEngineView tab, replacing it with a placeholder."""
        url = web_view.url().toString()
        title = self.tab_widget.tabText(index)

        placeholder_widget = QWidget()
        placeholder_layout = QVBoxLayout(placeholder_widget)
        placeholder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_layout.addWidget(QLabel("This tab is suspended to save memory."))
        reload_btn = QPushButton("Reload")
        suspended_url_key = f"about:suspended_{id(placeholder_widget)}"
        reload_btn.clicked.connect(lambda: self.add_new_tab(url=suspended_url_key))
        placeholder_layout.addWidget(reload_btn)
        placeholder_widget.setStyleSheet("background-color: #f0f0f0; color: #555; border: 1px dashed #ccc;")
        placeholder_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.suspended_tabs_data[placeholder_widget] = {
            'url': url,
            'title': title,
            'original_index': index
        }

        self.tab_widget.removeTab(index)
        self.tab_widget.insertTab(index, placeholder_widget, title)
        self.tab_widget.setTabText(index, f"Suspended: {title[:10]}...")

        old_custom_button = self.custom_tab_buttons_map.pop(web_view, None)
        if old_custom_button:
            self.tab_bar_layout.removeWidget(old_custom_button)
            old_custom_button.deleteLater()
            self.create_custom_tab_button(placeholder_widget, f"Suspended: {title[:10]}...", index)

        web_view.setParent(None)
        web_view.deleteLater()
        self.tab_last_active_time.pop(web_view, None)

        print(f"Tab '{title}' suspended.")
        self.update_tab_counter()

    def save_to_pdf(self):
        """Saves the current web page as a PDF."""
        current_web_view = self.get_current_web_view()
        if isinstance(current_web_view, QWebEngineView):
            default_path = os.path.join(self.settings.get("download_path", QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)), "page.pdf")
            file_path, _ = QFileDialog.getSaveFileName(self, "Save as PDF", default_path, "PDF Files (*.pdf)")
            if file_path:
                current_web_view.page().printToPdf(file_path)
                QMessageBox.information(self, "Save PDF", f"Page saved as PDF to '{file_path}'.")
        else:
            QMessageBox.warning(self, "Save PDF", "No web page is active to save as PDF.")

    def toggle_reading_mode(self, force_on=False, force_off=False):
        """
        Toggles reading mode for the current web page.
        force_on/force_off can be used to explicitly set the mode.
        """
        current_web_view = self.get_current_web_view()
        if not isinstance(current_web_view, QWebEngineView):
            if not force_off:
                QMessageBox.warning(self, "Reading Mode", "Reading mode is only applicable to web pages.")
            self.reading_mode = False
            self.reading_mode_btn.setStyleSheet("")
            return

        if force_on:
            self.reading_mode = True
        elif force_off:
            self.reading_mode = False
        else:
            self.reading_mode = not self.reading_mode

        if self.reading_mode:
            current_web_view.page().runJavaScript("""
                (function() {
                    var style = document.createElement('style');
                    style.id = 'doors-reading-mode-style';
                    style.innerHTML = `
                        body {
                            background-color: #f5f5d5 !important;
                            color: #000000 !important;
                            font-family: 'Georgia', serif !important;
                            font-size: 18px !important;
                            line-height: 1.6 !important;
                            max-width: 800px !important;
                            margin: 40px auto !important;
                            padding: 20px !important;
                            box-shadow: 0 0 10px rgba(0,0,0,0.1);
                        }
                        img, video, iframe, .ad, .sidebar, .header, .footer, nav, aside {
                            display: none !important;
                        }
                        p, h1, h2, h3, h4, h5, h6, li {
                            max-width: 100% !important;
                        }
                    `;
                    document.head.appendChild(style);
                })();
            """)
            self.reading_mode_btn.setStyleSheet("background-color: #a0a0a0;")
        else:
            current_web_view.page().runJavaScript("""
                var style = document.getElementById('doors-reading-mode-style');
                if (style) { style.remove(); }
            """)
            self.reading_mode_btn.setStyleSheet("")

    def show_zoom_menu(self):
        """Displays a menu for zoom options."""
        menu = QMenu(self)
        menu.addAction("Zoom In (125%)", lambda: self.set_zoom(1.25))
        menu.addAction("Zoom In (150%)", lambda: self.set_zoom(1.50))
        menu.addAction("Zoom Out (75%)", lambda: self.set_zoom(0.75))
        menu.addAction("Zoom Out (50%)", lambda: self.set_zoom(0.50))
        menu.addAction("Reset (100%)", lambda: self.set_zoom(1.0))
        menu.exec(self.zoom_btn.mapToGlobal(self.zoom_btn.rect().bottomLeft()))

    def set_zoom(self, factor):
        """Sets the zoom factor for the current web page."""
        current_web_view = self.get_current_web_view()
        if current_web_view:
            current_web_view.setZoomFactor(factor)

    def show_history(self):
        """Displays a menu with recent history entries."""
        menu = QMenu(self)
        if not self.history:
            menu.addAction("No history available.").setEnabled(False)
        else:
            for entry in reversed(self.history[-20:]):
                action_text = f"{entry['timestamp']} - {entry['title'] or entry['url']}"
                action = QAction(action_text, self)
                action.triggered.connect(lambda checked, url=entry["url"]: self.add_new_tab(url))
                menu.addAction(action)
        menu.exec(self.history_btn.mapToGlobal(self.history_btn.rect().bottomLeft()))

    def show_downloads_manager(self):
        """Shows the Downloads Manager dialog."""
        self.downloads_dialog.show()
        self.downloads_dialog.raise_()
        self.downloads_dialog.activateWindow()

    def handle_download_request(self, download_item: QWebEngineDownloadRequest):
        """Handles a download request from the web engine."""
        file_name = download_item.url().fileName()
        if not file_name:
            file_name = "downloaded_file"
        
        default_downloads_path = os.path.join(self.settings.get("download_path", QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)), file_name)
        
        path = None
        if self.settings.get("ask_save_location", True):
            path, _ = QFileDialog.getSaveFileName(self, "Save File", default_downloads_path)
        else:
            path = default_downloads_path

        if path:
            download_item.setPath(path)
            download_item.accept()
            self.downloads_dialog.add_download_item(download_item)
            QMessageBox.information(self, "Download", f"Download of '{os.path.basename(path)}' started.")
        else:
            download_item.cancel()
            QMessageBox.warning(self, "Download", "Download cancelled.")

    def handle_fullscreen_request(self, request):
        """Handles fullscreen requests from web content."""
        request.accept()
        if request.toggleOn():
            self.showFullScreen()
            self.is_fullscreen = True
        else:
            self.showNormal()
            self.is_fullscreen = False

    def toggle_fullscreen(self):
        """Toggles the browser window between normal and fullscreen mode."""
        self.is_fullscreen = not self.is_fullscreen
        if self.is_fullscreen:
            self.showFullScreen()
        else:
            self.showNormal()

    def toggle_maximize(self):
        """Toggles the browser window between normal and maximized mode."""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def toggle_sidebar(self):
        """Toggles the visibility of the sidebar."""
        self.sidebar_visible = not self.sidebar_visible
        if self.sidebar_visible:
            self.sidebar.show()
        else:
            self.sidebar.hide()

    def share_url(self):
        """Shares the current page's URL (e.g., via Telegram)."""
        current_web_view = self.get_current_web_view()
        if current_web_view:
            url = current_web_view.url().toString()
            if url and url != "about:blank":
                QDesktopServices.openUrl(QUrl(f"https://t.me/share/url?url={url}"))
            else:
                QMessageBox.warning(self, "Share", "Current page cannot be shared.")
        else:
            QMessageBox.warning(self, "Share", "No web page is active to share.")

    def show_extensions_manager(self):
        """Opens the Extensions Manager dialog."""
        ext_dialog = ExtensionsDialog(self.extension_manager, self)
        ext_dialog.exec()

    def reapply_extension_scripts(self):
        """Reapplies content scripts to all active web views (e.g., after extension changes)."""
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if isinstance(widget, QWebEngineView):
                self.extension_manager.apply_content_scripts(widget.page())
        QMessageBox.information(self, "Extensions", "Extension scripts reapplied. You may need to refresh tabs.")

    def show_devtools(self):
        """Opens DevTools for the current web view."""
        current_web_view = self.get_current_web_view()
        if current_web_view:
            dev_tools_page = QWebEnginePage(self.profile)
            dev_tools_page.setDevToolsPage(current_web_view.page())

            dev_tools_window = QMainWindow(self)
            dev_tools_window.setWindowTitle(f"DevTools - {self.tab_widget.tabText(self.tab_widget.currentIndex())}")
            dev_tools_view = QWebEngineView()
            dev_tools_view.setPage(dev_tools_page)
            dev_tools_window.setCentralWidget(dev_tools_view)
            dev_tools_window.resize(800, 600)
            dev_tools_window.show()
            self.devtools_windows.append(dev_tools_window)
            dev_tools_window.destroyed.connect(lambda: self.devtools_windows.remove(dev_tools_window))
        else:
            QMessageBox.warning(self, "Developer Tools", "No active web page to open DevTools for.")

    def sync_data_from_cloud_and_reload(self):
        """Downloads data from cloud and reloads browser state."""
        self.data_manager.sync_data_from_cloud()
        # Reload all data after sync
        initial_data = self.data_manager.load_data()
        self.history = initial_data["history"]
        self.bookmarks = initial_data["bookmarks"]
        self.settings = initial_data["settings"]
        self.site_permissions = initial_data["site_permissions"]
        
        self.home_page.history = self.history
        self.home_page.bookmarks = self.bookmarks
        self.home_page.setup_completer()
        self.setup_completer()
        self.update_bookmarks_list()
        self.extension_manager.load_extensions()
        self.adblock_interceptor.load_ad_domains()
        
        # Reapply settings that affect live browser state
        self._apply_initial_settings(self.settings) # Use initial settings apply to avoid pop-ups


    # --- Frameless Window Drag and Resize Logic ---
    def mousePressEvent(self, event):
        """Handles mouse press events for dragging and resizing."""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            if self.header.geometry().contains(pos) and not self.isMaximized() and not self.isFullScreen():
                self.dragging = True
                self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            elif not self.isMaximized() and not self.isFullScreen() and self.is_on_border(pos):
                self.resizing = True
                self.resize_start_pos = event.globalPosition().toPoint()
                self.resize_start_geometry = self.geometry()
                self.set_resize_direction(pos)

    def mouseMoveEvent(self, event):
        """Handles mouse move events for dragging and resizing."""
        pos = event.pos()
        if self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_position)
        elif self.resizing:
            delta = event.globalPosition().toPoint() - self.resize_start_pos
            new_geometry = QRect(self.resize_start_geometry)

            if "left" in self.resize_direction:
                new_geometry.setLeft(self.resize_start_geometry.left() + delta.x())
            if "right" in self.resize_direction:
                new_geometry.setRight(self.resize_start_geometry.right() + delta.x())
            if "top" in self.resize_direction:
                new_geometry.setTop(self.resize_start_geometry.top() + delta.y())
            if "bottom" in self.resize_direction:
                new_geometry.setBottom(self.resize_start_geometry.bottom() + delta.y())

            min_width = self.minimumWidth() if self.minimumWidth() > 0 else 400
            min_height = self.minimumHeight() if self.minimumHeight() > 0 else 300

            if new_geometry.width() < min_width:
                if "left" in self.resize_direction:
                    new_geometry.setLeft(self.resize_start_geometry.right() - min_width)
                else:
                    new_geometry.setWidth(min_width)
            if new_geometry.height() < min_height:
                if "top" in self.resize_direction:
                    new_geometry.setTop(self.resize_start_geometry.bottom() - min_height)
                else:
                    new_geometry.setHeight(min_height)

            self.setGeometry(new_geometry)
        else:
            if not self.isMaximized() and not self.isFullScreen():
                self.set_resize_cursor(pos)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event):
        """Handles mouse release events."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.resizing = False
            self.resize_direction = None
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def is_on_border(self, pos):
        """Checks if the mouse position is on the resize border."""
        rect = self.rect()
        return (pos.x() <= RESIZE_BORDER or pos.x() >= rect.width() - RESIZE_BORDER or
                pos.y() <= RESIZE_BORDER or pos.y() >= rect.height() - RESIZE_BORDER)

    def set_resize_direction(self, pos):
        """Determines the resize direction based on mouse position."""
        rect = self.rect()
        self.resize_direction = []
        if pos.x() <= RESIZE_BORDER:
            self.resize_direction.append("left")
        elif pos.x() >= rect.width() - RESIZE_BORDER:
            self.resize_direction.append("right")

        if pos.y() <= RESIZE_BORDER:
            self.resize_direction.append("top")
        elif pos.y() >= rect.height() - RESIZE_BORDER:
            self.resize_direction.append("bottom")

    def set_resize_cursor(self, pos):
        """Sets the appropriate resize cursor based on mouse position."""
        rect = self.rect()
        on_left = pos.x() <= RESIZE_BORDER
        on_right = pos.x() >= rect.width() - RESIZE_BORDER
        on_top = pos.y() <= RESIZE_BORDER
        on_bottom = pos.y() >= rect.height() - RESIZE_BORDER

        if on_left and on_top:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif on_right and on_bottom:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif on_left and on_bottom:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif on_right and on_top:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif on_left or on_right:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif on_top or on_bottom:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def show_link_status(self, url):
        """
        (Optional) Displays the hovered link URL in a status bar.
        Requires a QStatusBar to be added to the QMainWindow.
        Example: self.statusBar().showMessage(url)
        """
        pass

    def closeEvent(self, event):
        """
        Overrides the close event to ensure all QWebEngineView instances are properly
        deleted before the application exits, preventing memory leaks and warnings.
        Also handles clearing cookies on exit.
        """
        if self.settings.get("clear_cookies_on_exit", False):
            self.profile.cookieStore().deleteAllCookies()
            print("Cleared all cookies on exit.")

        for i in range(self.tab_widget.count()):
            widget_to_close = self.tab_widget.widget(i)
            if isinstance(widget_to_close, QWebEngineView):
                widget_to_close.setParent(None)
                widget_to_close.deleteLater()
            elif widget_to_close in self.suspended_tabs_data:
                widget_to_close.setParent(None)
                widget_to_close.deleteLater()

        self.tab_widget.clear()
        for i in reversed(range(self.tab_bar_layout.count())):
            widget = self.tab_bar_layout.itemAt(i).widget()
            if widget:
                self.tab_bar_layout.removeWidget(widget)
                widget.deleteLater()
        self.custom_tab_buttons_map.clear()
        self.tab_last_active_time.clear()
        self.suspended_tabs_data.clear()

        for dev_window in list(self.devtools_windows):
            if dev_window:
                dev_window.close()
                dev_window.deleteLater()
        self.devtools_windows.clear()

        if self.downloads_dialog:
            self.downloads_dialog.close()
            self.downloads_dialog.deleteLater()
            self.downloads_dialog = None

        event.accept()


if __name__ == "__main__":
    QApplication.setStyle(QStyleFactory.create("Fusion"))

    app = QApplication(sys.argv)
    try:
        browser = DoorsBrowser()
        browser.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"An unhandled error occurred: {e}")
        sys.exit(1)

