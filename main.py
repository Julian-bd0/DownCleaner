import os
import shutil
import hashlib
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.core.window import Window
from kivy.utils import platform

# Android Permission Request
if platform == 'android':
    from android.permissions import request_permissions, Permission
    request_permissions([
        Permission.READ_EXTERNAL_STORAGE,
        Permission.WRITE_EXTERNAL_STORAGE
    ])

DOWNLOAD_PATH = "/storage/emulated/0/Download"

EXTENSIONS_MAP = {
    "JPG_JPEG": [".jpg", ".jpeg"],
    "PNG": [".png"],
    "Other_Images": [".webp", ".gif", ".svg", ".bmp", ".ico"],
    "APKs": [".apk", ".xapk", ".apks"],
    "PDFs": [".pdf"],
    "Videos": [".mp4", ".mkv", ".mov", ".avi", ".webm", ".3gp"],
    "Audio": [".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"],
    "Documents": [".docx", ".doc", ".txt", ".xlsx", ".xls", ".pptx", ".ppt", ".csv"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"]
}

TARGET_FOLDERS = set(EXTENSIONS_MAP.keys())
TARGET_FOLDERS.add("Others")

def get_file_hash(filepath):
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return None

class CleanerApp(App):
    def build(self):
        self.title = "Download Cleaner"
        layout = BoxLayout(orientation='vertical', padding=20, spacing=15)

        self.status_label = Label(
            text="Tap 'Scan & Organize' to clean Download folder.",
            size_hint_y=None,
            height=80,
            halign='center'
        )
        layout.add_widget(self.status_label)

        self.log_label = Label(
            text="",
            size_hint_y=None,
            halign='left',
            valign='top'
        )
        self.log_label.bind(size=self.log_label.setter('text_size'))

        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(self.log_label)
        layout.add_widget(scroll)

        self.scan_btn = Button(
            text="Scan & Organize",
            size_hint_y=None,
            height=120,
            background_color=(0.1, 0.6, 0.9, 1)
        )
        self.scan_btn.bind(on_press=self.start_process)
        layout.add_widget(self.scan_btn)

        return layout

    def log(self, msg):
        self.log_label.text += msg + "\n"
        self.log_label.height = max(len(self.log_label.text.split("\n")) * 30, 200)

    def start_process(self, instance):
        self.log_label.text = ""
        self.scan_btn.disabled = True
        self.log("🔍 Scanning Download folder...")

        if not os.path.exists(DOWNLOAD_PATH):
            self.log(f"❌ Path not found: {DOWNLOAD_PATH}")
            self.scan_btn.disabled = False
            return

        all_files = []
        for root, dirs, files in os.walk(DOWNLOAD_PATH):
            for file in files:
                if not file.startswith("."):
                    all_files.append(os.path.join(root, file))

        if not all_files:
            self.log("⚠️ No files found!")
            self.scan_btn.disabled = False
            return

        self.log(f"Total files found: {len(all_files)}")

        # Duplicate checking
        hash_to_files = {}
        for f_path in all_files:
            h = get_file_hash(f_path)
            if h:
                hash_to_files.setdefault(h, []).append(f_path)

        self.duplicates_to_delete = []
        for h, f_list in hash_to_files.items():
            if len(f_list) > 1:
                f_list.sort(key=lambda p: (
                    0 if os.path.relpath(p, DOWNLOAD_PATH).split(os.sep)[0] in TARGET_FOLDERS else 1,
                    len(p)
                ))
                original = f_list[0]
                for dup in f_list[1:]:
                    self.duplicates_to_delete.append((dup, original))

        self.all_files = all_files

        if self.duplicates_to_delete:
            self.show_duplicate_popup()
        else:
            self.log("✨ No duplicates found.")
            self.organize_files(set())

    def show_duplicate_popup(self):
        box = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        info_text = f"Found {len(self.duplicates_to_delete)} duplicate files:\n\n"
        for idx, (dup, orig) in enumerate(self.duplicates_to_delete, 1):
            info_text += f"{idx}. {os.path.basename(dup)}\n   Original: {os.path.basename(orig)}\n"

        lbl = Label(text=info_text, halign='left', valign='top')
        lbl.bind(size=lbl.setter('text_size'))
        scroll = ScrollView(size_hint=(1, 0.7))
        scroll.add_widget(lbl)
        box.add_widget(scroll)

        btn_box = BoxLayout(size_hint_y=0.3, spacing=10)
        
        btn_yes = Button(text="Delete Duplicates", background_color=(0.9, 0.2, 0.2, 1))
        btn_no = Button(text="Keep All", background_color=(0.4, 0.4, 0.4, 1))
        
        btn_box.add_widget(btn_yes)
        btn_box.add_widget(btn_no)
        box.add_widget(btn_box)

        popup = Popup(title="Duplicate Files Preview", content=box, size_hint=(0.9, 0.8), auto_dismiss=False)

        def on_delete(ins):
            popup.dismiss()
            deleted = set()
            for dup, _ in self.duplicates_to_delete:
                try:
                    os.remove(dup)
                    deleted.add(dup)
                    self.log(f"🗑️ Deleted: {os.path.basename(dup)}")
                except Exception as e:
                    self.log(f"Failed to delete {os.path.basename(dup)}")
            self.organize_files(deleted)

        def on_keep(ins):
            popup.dismiss()
            self.log("Keeping all duplicates.")
            self.organize_files(set())

        btn_yes.bind(on_press=on_delete)
        btn_no.bind(on_press=on_keep)
        popup.open()

    def organize_files(self, ignore_deleted):
        self.log("\n📦 Organizing into category folders...")
        moved_count = 0

        for f_path in self.all_files:
            if f_path in ignore_deleted or not os.path.exists(f_path):
                continue

            rel_path = os.path.relpath(f_path, DOWNLOAD_PATH)
            parts = rel_path.split(os.sep)

            filename = os.path.basename(f_path)
            _, ext = os.path.splitext(filename)
            ext = ext.lower()

            dest_folder = "Others"
            for folder_name, extensions in EXTENSIONS_MAP.items():
                if ext in extensions:
                    dest_folder = folder_name
                    break

            if len(parts) == 2 and parts[0] == dest_folder:
                continue

            dest_dir = os.path.join(DOWNLOAD_PATH, dest_folder)
            os.makedirs(dest_dir, exist_ok=True)

            dest_filepath = os.path.join(dest_dir, filename)
            base_name, file_ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(dest_filepath):
                if os.path.abspath(dest_filepath) == os.path.abspath(f_path):
                    break
                dest_filepath = os.path.join(dest_dir, f"{base_name}_{counter}{file_ext}")
                counter += 1

            if os.path.abspath(f_path) != os.path.abspath(dest_filepath):
                try:
                    shutil.move(f_path, dest_filepath)
                    self.log(f"✓ [{dest_folder}] -> {filename}")
                    moved_count += 1
                except Exception:
                    pass

        self.log(f"\n🎉 Done! Moved {moved_count} files.")
        self.scan_btn.disabled = False

if __name__ == "__main__":
    CleanerApp().run()
      
