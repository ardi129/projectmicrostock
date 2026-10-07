import os
import sys
import json
import time
import random
import shutil
import ctypes
from ctypes import wintypes
from datetime import datetime
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except Exception:
    HAS_PIL = False

# Setup Windows 64-bit/32-bit compatible CF_HDROP clipboard structures
class DROPFILES(ctypes.Structure):
    _fields_ = [
        ('pFiles', wintypes.DWORD),
        ('pt', wintypes.POINT),
        ('fNC', wintypes.BOOL),
        ('fWide', wintypes.BOOL),
    ]

try:
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
except Exception:
    pass

def copy_files_to_windows_clipboard(file_paths):
    """Menyalin file fisik langsung ke Windows Clipboard sehingga bisa di-paste (Ctrl+V) di File Explorer / Browser."""
    valid_paths = [os.path.abspath(p) for p in file_paths if os.path.exists(p)]
    if not valid_paths:
        return 0
    buffer = '\0'.join(valid_paths) + '\0\0'
    data = buffer.encode('utf-16le')

    dropfiles = DROPFILES()
    dropfiles.pFiles = ctypes.sizeof(DROPFILES)
    dropfiles.pt = wintypes.POINT(0, 0)
    dropfiles.fNC = False
    dropfiles.fWide = True

    header_bytes = bytes(dropfiles)
    all_bytes = header_bytes + data

    GMEM_MOVEABLE = 0x0002
    CF_HDROP = 15

    h_global = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(all_bytes))
    ptr = kernel32.GlobalLock(h_global)
    ctypes.memmove(ptr, all_bytes, len(all_bytes))
    kernel32.GlobalUnlock(h_global)

    user32.OpenClipboard(None)
    user32.EmptyClipboard()
    user32.SetClipboardData(CF_HDROP, h_global)
    user32.CloseClipboard()
    return len(valid_paths)

# Setup Windows OLE Drag & Drop for dragging files directly into browser/Explorer
try:
    import pythoncom
    from win32com.shell import shell
    import win32com.server.util
    HAS_OLE_DRAG = True
except Exception:
    HAS_OLE_DRAG = False

class OLEDropSource:
    _com_interfaces_ = [pythoncom.IID_IDropSource] if HAS_OLE_DRAG else []
    _public_methods_ = ['QueryContinueDrag', 'GiveFeedback']

    def QueryContinueDrag(self, escapePressed, keyState):
        if escapePressed:
            return 0x00040101  # DRAGDROP_S_CANCEL
        if not (keyState & 1):  # Left button released
            return 0x00040100  # DRAGDROP_S_DROP
        return 0  # S_OK

    def GiveFeedback(self, effect):
        return 0x00040102  # DRAGDROP_S_USEDEFAULTCURSORS

def do_native_drag_files(file_paths):
    """Menjalankan native Windows OLE DoDragDrop sehingga file .EPS bisa ditarik langsung ke Chrome/Explorer."""
    if not HAS_OLE_DRAG or not file_paths:
        return 0
    try:
        pythoncom.OleInitialize()
        desktop = shell.SHGetDesktopFolder()
        valid_paths = [os.path.abspath(p) for p in file_paths if os.path.exists(p)]
        if not valid_paths:
            return 0
        folder_path = os.path.dirname(valid_paths[0])
        folder_pidl = shell.SHParseDisplayName(folder_path, 0)[0]
        parent_folder = desktop.BindToObject(folder_pidl, None, shell.IID_IShellFolder)
        rel_pidls = []
        for p in valid_paths:
            fname = os.path.basename(p)
            rel_pidls.append(parent_folder.ParseDisplayName(0, None, fname)[1])
        _, data_obj = parent_folder.GetUIObjectOf(0, rel_pidls, pythoncom.IID_IDataObject, 0)
        source = win32com.server.util.wrap(OLEDropSource(), pythoncom.IID_IDropSource)
        # DROPEFFECT_COPY = 1, DROPEFFECT_MOVE = 2
    except Exception as e:
        print(f"[Drag Error] {e}")
        return 0

def select_files_in_windows_explorer(folder, file_names_or_basenames):
    """Membuka File Explorer Windows dan secara otomatis menyeleksi (highlight bersamaan) semua file yang ditentukan."""
    if not folder or not file_names_or_basenames or not os.path.isdir(folder):
        return 0

    first_fname = os.path.basename(file_names_or_basenames[0])
    first_path = os.path.join(folder, first_fname)
    if not os.path.exists(first_path) and not first_fname.lower().endswith(".eps"):
        first_path += ".eps"

    try:
        import win32com.client
        import pythoncom
        pythoncom.OleInitialize()
        shell_app = win32com.client.Dispatch("Shell.Application")
        folder_norm = os.path.normcase(os.path.normpath(folder))

        matched_window = None
        for w in shell_app.Windows():
            try:
                doc_folder = os.path.normcase(os.path.normpath(w.Document.Folder.Self.Path))
                if doc_folder == folder_norm:
                    matched_window = w
                    break
            except Exception:
                pass

        if not matched_window:
            if os.path.isfile(first_path):
                subprocess.Popen(f'explorer.exe /select,"{os.path.normpath(first_path)}"')
            else:
                os.startfile(os.path.normpath(folder))

            for _ in range(35):
                time.sleep(0.15)
                for w in shell_app.Windows():
                    try:
                        p = w.Document.Folder.Self.Path
                        if p and os.path.normcase(os.path.normpath(p)) == folder_norm:
                            matched_window = w
                            break
                    except Exception:
                        pass
                if matched_window:
                    time.sleep(0.2)
                    break

        if not matched_window:
            return 1

        try:
            hwnd = matched_window.HWND
            user32 = ctypes.windll.user32
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
            user32.SwitchToThisWindow(hwnd, True)
        except Exception:
            pass

        doc = matched_window.Document
        folder_items = doc.Folder.Items()
        first = True
        selected_count = 0

        for raw_name in file_names_or_basenames:
            fname = os.path.basename(raw_name)
            item = None
            try:
                item = folder_items.Item(fname)
            except Exception:
                pass
            if not item and not fname.lower().endswith(".eps"):
                try:
                    item = folder_items.Item(fname + ".eps")
                except Exception:
                    pass
            if not item and fname.lower().endswith(".eps"):
                try:
                    item = folder_items.Item(os.path.splitext(fname)[0])
                except Exception:
                    pass
            if item:
                if first:
                    doc.SelectItem(item, 29)  # 1(select) + 4(deselect others) + 8(ensure visible) + 16(focus)
                    first = False
                else:
                    doc.SelectItem(item, 9)   # 1(select) + 8(ensure visible)
                selected_count += 1

        # Stay on File Explorer window: pastikan tetap fokus & aktif
        try:
            hwnd = matched_window.HWND
            user32 = ctypes.windll.user32
            user32.ShowWindow(hwnd, 9)
            user32.SetForegroundWindow(hwnd)
            user32.SwitchToThisWindow(hwnd, True)
        except Exception:
            pass

        return selected_count
    except Exception:
        # Fallback jika win32com tidak tersedia: buka explorer dengan file pertama terseleksi
        try:
            if os.path.isfile(first_path):
                subprocess.Popen(f'explorer.exe /select,"{os.path.normpath(first_path)}"')
            else:
                os.startfile(os.path.normpath(folder))
            return 1
        except Exception:
            return 0

class CombinedMicrostockGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Microstock Toolkit")
        self.root.geometry("740x480")
        self.root.minsize(620, 320)
        self.root.configure(bg="#0d1117")

        self.setup_styles()

        self.pipeline_is_running = False

        # TOP BAR: RUN ALL PIPELINE (Vectorizer -> Illustrator -> Picker)
        top_bar = ttk.Frame(self.root, style="Card.TFrame", padding=(10, 6))
        top_bar.pack(fill="x", padx=6, pady=(5, 3))

        ttk.Label(
            top_bar,
            text="⚡ ALL-IN-ONE:",
            style="Card.TLabel",
            font=("Segoe UI", 9, "bold"),
            foreground="#38bdf8"
        ).pack(side="left", padx=(0, 6))

        # Main Pipeline Run Button
        self.btn_run_all = tk.Button(
            top_bar,
            text="🚀 JALANKAN SEMUA FITUR (Vectorizer ➔ Illustrator ➔ Explorer)",
            command=self.start_full_pipeline,
            bg="#059669",
            fg="#ffffff",
            activebackground="#10b981",
            activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"),
            bd=0,
            padx=14,
            pady=4,
            cursor="hand2"
        )
        self.btn_run_all.pack(side="left", padx=(0, 6))

        # Stop All Button
        self.btn_stop_all = tk.Button(
            top_bar,
            text="⏹ STOP SEMUA",
            command=self.stop_full_pipeline,
            state="disabled",
            bg="#45475a",
            fg="#ffffff",
            activebackground="#f43f5e",
            activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"),
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2"
        )
        self.btn_stop_all.pack(side="left", padx=(0, 10))

        # Pipeline Status Label
        self.pipeline_status_label = ttk.Label(
            top_bar,
            text="Status: Ready",
            style="Card.TLabel",
            font=("Segoe UI", 9, "italic"),
            foreground="#94a3b8"
        )
        self.pipeline_status_label.pack(side="right", padx=(0, 4))

        # Create Notebook (Tab Control)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=6, pady=4)

        # Tab 1: Vectorizer AI
        self.tab_vectorizer = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_vectorizer, text=" ⚡ Vectorizer ")
        self.setup_vectorizer_tab(self.tab_vectorizer)

        # Tab 2: Illustrator Cleaner
        self.tab_cleaner = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_cleaner, text=" 🎨 Cleaner ")
        self.setup_cleaner_tab(self.tab_cleaner)

        # Tab 3: Absen & Picker Upload
        self.tab_picker = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_picker, text=" 📦 Absen & Picker ")
        self.setup_picker_tab(self.tab_picker)

        # Buka langsung ke Tab Picker
        self.notebook.select(self.tab_picker)

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")

        BG_MAIN = "#0d1117"       # Sleek Modern Dark Slate
        BG_CARD = "#161b22"       # Card Dark
        BG_INPUT = "#0d1117"      # Input Field
        BORDER = "#30363d"        # Subtle Border
        TEXT_PRIMARY = "#f0f6fc"  # Crisp White
        TEXT_MUTED = "#8b949e"    # Slate 400
        ACCENT_CYAN = "#38bdf8"   # Bright Cyan Accent

        self.root.configure(bg=BG_MAIN)

        # Frames & Tabs
        self.style.configure("TFrame", background=BG_MAIN)
        self.style.configure("Card.TFrame", background=BG_CARD, relief="flat")

        self.style.configure("TNotebook", background=BG_MAIN, borderwidth=0)
        self.style.configure(
            "TNotebook.Tab",
            background="#161b22",
            foreground=TEXT_MUTED,
            font=("Segoe UI", 10, "bold"),
            padding=[20, 8]
        )
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", "#21262d"), ("active", "#1c2128")],
            foreground=[("selected", ACCENT_CYAN), ("active", "#c9d1d9")]
        )

        # Labels & Entry
        self.style.configure("TLabel", background=BG_MAIN, foreground=TEXT_PRIMARY, font=("Segoe UI", 9))
        self.style.configure("Card.TLabel", background=BG_CARD, foreground=TEXT_PRIMARY, font=("Segoe UI", 9))
        self.style.configure("Title.TLabel", background=BG_MAIN, foreground=ACCENT_CYAN, font=("Segoe UI", 14, "bold"))
        self.style.configure("Subtitle.TLabel", background=BG_MAIN, foreground=TEXT_MUTED, font=("Segoe UI", 9))

        self.style.configure(
            "TEntry",
            fieldbackground=BG_INPUT,
            foreground=TEXT_PRIMARY,
            insertcolor=TEXT_PRIMARY,
            borderwidth=1
        )
        self.style.configure(
            "TCombobox",
            fieldbackground=BG_INPUT,
            foreground=TEXT_PRIMARY,
            borderwidth=1
        )
        self.style.configure(
            "TSpinbox",
            fieldbackground=BG_INPUT,
            foreground=TEXT_PRIMARY,
            borderwidth=1
        )

        # Treeview styling (Clean & Modern)
        self.style.configure(
            "Treeview",
            background="#0d1117",
            foreground=TEXT_PRIMARY,
            fieldbackground="#0d1117",
            rowheight=28,
            font=("Segoe UI", 9),
            borderwidth=0
        )
        self.style.configure(
            "Treeview.Heading",
            background="#161b22",
            foreground=ACCENT_CYAN,
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padding=[8, 6]
        )
        self.style.map(
            "Treeview",
            background=[("selected", "#1f6feb")],
            foreground=[("selected", "#ffffff")]
        )
        self.style.map("Treeview.Heading", background=[("active", "#21262d")])

    # =========================================================================
    # ALL-IN-ONE PIPELINE: VECTORIZER -> ILLUSTRATOR -> PICKER/EXPLORER
    # =========================================================================
    def start_full_pipeline(self):
        if self.pipeline_is_running or self.vec_is_running or self.ai_is_running:
            messagebox.showinfo("Sedang Berjalan", "Sebuah proses otomasi sedang berjalan. Tunggu hingga selesai atau klik STOP terlebih dahulu.")
            return

        # 1. Validasi Folder Input Vectorizer
        vec_in = self.vec_input_entry.get().strip()
        vec_out = self.vec_output_entry.get().strip()
        if not vec_in or not os.path.isdir(vec_in):
            messagebox.showerror("Error Input", f"Folder Input Gambar (Tab Vectorizer) tidak valid atau belum dipilih:\n{vec_in}")
            self.notebook.select(self.tab_vectorizer)
            return

        if not vec_out:
            cand_svg = os.path.join(vec_in, "SVG")
            vec_out = cand_svg if os.path.isdir(cand_svg) else vec_in
            self.vec_output_entry.delete(0, tk.END)
            self.vec_output_entry.insert(0, vec_out)

        # 2. Validasi Illustrator Executable
        ai_exe = self.ai_entry.get().strip()
        if not ai_exe or not os.path.exists(ai_exe):
            messagebox.showerror("Error Illustrator", f"Executable Illustrator (Tab Cleaner) tidak ditemukan:\n{ai_exe}")
            self.notebook.select(self.tab_cleaner)
            return

        # 3. Sinkronisasi Folder Input & Output Illustrator
        ai_in = self.ai_input_entry.get().strip()
        if not ai_in or not os.path.exists(ai_in):
            ai_in = vec_out
            self.ai_input_entry.delete(0, tk.END)
            self.ai_input_entry.insert(0, ai_in)

        ai_out = self.ai_output_entry.get().strip()
        if not ai_out:
            parent_d = os.path.dirname(ai_in)
            cand_out = os.path.join(parent_d, "EPS & JPG") if os.path.isdir(parent_d) else (ai_in + "_clean")
            ai_out = os.path.normpath(cand_out)
            self.ai_output_entry.delete(0, tk.END)
            self.ai_output_entry.insert(0, ai_out)

        # 4. Sinkronisasi Folder Picker
        picker_f = self.picker_folder_entry.get().strip()
        if not picker_f:
            self.picker_folder_entry.delete(0, tk.END)
            self.picker_folder_entry.insert(0, ai_out)

        # State updates
        self.pipeline_is_running = True
        self.btn_run_all.config(state="disabled", bg="#45475a")
        self.btn_stop_all.config(state="normal", bg="#f43f5e")
        self.vec_btn_run.config(state="disabled", bg="#45475a")
        self.ai_btn_run.config(state="disabled", bg="#45475a")
        self.pipeline_status_label.config(text="Memulai Pipeline... 🚀", foreground="#38bdf8")

        threading.Thread(target=self._run_pipeline_thread, daemon=True).start()

    def _run_pipeline_thread(self):
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            vec_script = os.path.join(script_dir, "vectorize.js")
            jsx_script = os.path.join(script_dir, "clean_svg.jsx")
            config_path = os.path.join(script_dir, "clean_config.json")
            log_path = os.path.join(script_dir, "clean_status.log")

            vec_in = self.vec_input_entry.get().strip()
            vec_out = self.vec_output_entry.get().strip() or vec_in
            ai_exe = self.ai_entry.get().strip()
            ai_in = self.ai_input_entry.get().strip() or vec_out
            ai_out = self.ai_output_entry.get().strip() or (ai_in + "_clean")

            # -----------------------------------------------------------------
            # TAHAP 1: VECTORIZER AI
            # -----------------------------------------------------------------
            self.root.after(0, lambda: self.notebook.select(self.tab_vectorizer))
            self.root.after(0, lambda: self.pipeline_status_label.config(
                text="[1/3] Memproses Vektorisasi ke SVG... ⚡", foreground="#38bdf8"
            ))
            self.root.after(0, lambda: self.vec_status_label.config(
                text="Status: Berjalan (Full Pipeline) 🚀", foreground="#10b981"
            ))
            self.root.after(0, lambda: self.vec_btn_stop.config(state="normal", bg="#f43f5e"))

            self.vec_log(f"\n=======================================================")
            self.vec_log(f"🚀 [FULL PIPELINE] TAHAP 1/3: VECTORIZER AI")
            self.vec_log(f"   Input  : {vec_in}")
            self.vec_log(f"   Output : {vec_out}")
            self.vec_log(f"=======================================================")

            self.vec_is_running = True
            cmd_vec = ["node", vec_script, "--input", vec_in, "--output", vec_out]
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            self.vec_process = subprocess.Popen(
                cmd_vec,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                creationflags=flags
            )

            for line in iter(self.vec_process.stdout.readline, ''):
                if line:
                    self.vec_log(line.rstrip('\r\n'))
                if not self.pipeline_is_running:
                    break

            self.vec_process.wait()
            self.vec_is_running = False
            self.root.after(0, self.reset_vec_ui)

            if not self.pipeline_is_running:
                self.root.after(0, lambda: self.pipeline_status_label.config(text="Dihentikan oleh pengguna.", foreground="#f43f5e"))
                return

            self.vec_log(f"\n[OK] Tahap 1 Vectorizer AI Selesai! Melanjutkan ke Adobe Illustrator Cleaner...\n")
            time.sleep(1.0)

            # Sinkronisasi folder input AI jika belum sinkron
            self.root.after(0, lambda: self.ai_input_entry.delete(0, tk.END))
            self.root.after(0, lambda: self.ai_input_entry.insert(0, vec_out))

            # -----------------------------------------------------------------
            # TAHAP 2: ADOBE ILLUSTRATOR SVG CLEANER
            # -----------------------------------------------------------------
            self.root.after(0, lambda: self.notebook.select(self.tab_cleaner))
            self.root.after(0, lambda: self.pipeline_status_label.config(
                text="[2/3] Memproses Pembersihan di Illustrator... 🎨", foreground="#38bdf8"
            ))
            self.root.after(0, lambda: self.ai_status_label.config(
                text="Status: Berjalan (Full Pipeline) 🎨", foreground="#10b981"
            ))
            self.root.after(0, lambda: self.ai_btn_stop.config(state="normal", bg="#f43f5e"))

            self.ai_log(f"\n=======================================================")
            self.ai_log(f"🎨 [FULL PIPELINE] TAHAP 2/3: ADOBE ILLUSTRATOR CLEANER")
            self.ai_log(f"   Input  : {vec_out}")
            self.ai_log(f"   Output : {ai_out}")
            self.ai_log(f"=======================================================")

            os.makedirs(ai_out, exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({"input_folder": vec_out.replace("\\", "/"), "output_folder": ai_out.replace("\\", "/")}, f, indent=4)

            with open(log_path, "w", encoding="utf-8") as f:
                f.write("")

            self.ai_is_running = True
            threading.Thread(target=self.monitor_ai_log, args=(log_path,), daemon=True).start()

            cmd_ai = [ai_exe, "-r", jsx_script]
            self.ai_process = subprocess.Popen(cmd_ai)

            # Tunggu proses cleaner selesai melalui monitor log (atau ai_is_running)
            while self.ai_is_running and self.pipeline_is_running:
                time.sleep(0.5)

            if not self.pipeline_is_running:
                if self.ai_process:
                    try: self.ai_process.terminate()
                    except Exception: pass
                self.root.after(0, lambda: self.pipeline_status_label.config(text="Dihentikan oleh pengguna.", foreground="#f43f5e"))
                return

            self.root.after(0, self.reset_ai_ui)
            self.ai_log(f"\n[OK] Tahap 2 Adobe Illustrator Selesai! Melanjutkan ke Absen & Explorer...\n")
            time.sleep(1.0)

            # -----------------------------------------------------------------
            # TAHAP 3: ABSEN & PICKER UPLOAD (FILE EXPLORER)
            # -----------------------------------------------------------------
            self.root.after(0, lambda: self.notebook.select(self.tab_picker))
            self.root.after(0, lambda: self.pipeline_status_label.config(
                text="[3/3] Menyiapkan & Memilih File di Explorer... 📦", foreground="#38bdf8"
            ))

            def finalize_step():
                self.picker_folder_entry.delete(0, tk.END)
                self.picker_folder_entry.insert(0, ai_out)
                self.scan_picker_folder(auto_open=False)
                # Jalankan otomasi seleksi explorer
                self.start_explorer_automation()
                self.pipeline_status_label.config(
                    text="🎉 SEMUA ALUR SELESAI! File siap di Explorer.",
                    foreground="#34d399"
                )

            self.root.after(0, finalize_step)

        except Exception as e:
            self.root.after(0, lambda err=e: self.pipeline_status_label.config(
                text=f"Error: {err}", foreground="#f43f5e"
            ))
        finally:
            self.root.after(0, self.reset_pipeline_ui)

    def stop_full_pipeline(self):
        if not self.pipeline_is_running:
            return
        self.pipeline_is_running = False
        self.stop_vectorizer()
        self.stop_cleaner()
        self.reset_pipeline_ui()
        self.pipeline_status_label.config(text="Dihentikan oleh pengguna.", foreground="#f43f5e")

    def reset_pipeline_ui(self):
        self.pipeline_is_running = False
        self.btn_run_all.config(state="normal", bg="#059669")
        self.btn_stop_all.config(state="disabled", bg="#45475a")
        self.reset_vec_ui()
        self.reset_ai_ui()

    # =========================================================================
    # TAB 1: VECTORIZER AI AUTOMATION
    # =========================================================================
    def setup_vectorizer_tab(self, parent):
        self.vec_process = None
        self.vec_is_running = False

        header = ttk.Frame(parent, padding=(15, 10))
        header.pack(fill="x")
        ttk.Label(header, text="⚡ Vectorizer.ai Automation", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Otomatisasi vektorisasi PNG/JPG ke SVG dengan browser & preset tersimpan.", style="Subtitle.TLabel").pack(anchor="w")

        card = ttk.Frame(parent, style="Card.TFrame", padding=12)
        card.pack(fill="x", padx=15, pady=5)

        ttk.Label(card, text="Folder Input (Gambar PNG/JPG):", style="Card.TLabel", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 2))
        self.vec_input_entry = ttk.Entry(card, font=("Segoe UI", 9))
        self.vec_input_entry.grid(row=1, column=0, sticky="ew", padx=(0, 10), ipady=3)
        tk.Button(card, text="📁 Pilih Folder", command=self.browse_vec_input, bg="#21262d", fg="#f0f6fc", activebackground="#30363d", activeforeground="#ffffff", font=("Segoe UI", 9, "bold"), bd=0, padx=10, pady=3, cursor="hand2").grid(row=1, column=1, sticky="e")

        ttk.Frame(card, height=8, style="Card.TFrame").grid(row=2, column=0, columnspan=2)

        ttk.Label(card, text="Folder Output (Hasil SVG & Otomatis Cek Skip File):", style="Card.TLabel", font=("Segoe UI", 10, "bold")).grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 2))
        self.vec_output_entry = ttk.Entry(card, font=("Segoe UI", 9))
        self.vec_output_entry.grid(row=4, column=0, sticky="ew", padx=(0, 10), ipady=3)
        tk.Button(card, text="📁 Pilih Folder", command=self.browse_vec_output, bg="#21262d", fg="#f0f6fc", activebackground="#30363d", activeforeground="#ffffff", font=("Segoe UI", 9, "bold"), bd=0, padx=10, pady=3, cursor="hand2").grid(row=4, column=1, sticky="e")
        card.columnconfigure(0, weight=1)

        # Set default paths setelah kedua entry dibuat
        default_in = ""
        for cand in [r"D:\ADOBESTOCK\Part 2", r"D:\ADOBESTOCK\Part 1", r"D:\MicroStock\ADOBESTOCK\STOK READY UP\natal series\KLOTER1\PNG"]:
            if os.path.exists(cand):
                default_in = cand
                break
        if default_in:
            self.vec_input_entry.insert(0, os.path.normpath(default_in))
            cand_svg = os.path.join(default_in, "SVG")
            if os.path.exists(cand_svg):
                self.vec_output_entry.insert(0, os.path.normpath(cand_svg))
            else:
                self.vec_output_entry.insert(0, os.path.normpath(default_in))

        btn_frame = ttk.Frame(parent, padding=(15, 5))
        btn_frame.pack(fill="x")

        self.vec_btn_run = tk.Button(btn_frame, text="▶ RUN VECTORIZER", command=self.start_vectorizer, bg="#10b981", fg="#ffffff", font=("Segoe UI", 10, "bold"), bd=0, padx=20, pady=6, cursor="hand2")
        self.vec_btn_run.pack(side="left", padx=(0, 10))

        self.vec_btn_stop = tk.Button(btn_frame, text="⏹ STOP", command=self.stop_vectorizer, state="disabled", bg="#f43f5e", fg="#ffffff", font=("Segoe UI", 10, "bold"), bd=0, padx=20, pady=6, cursor="hand2")
        self.vec_btn_stop.pack(side="left")

        # Tombol tambahan: Jalankan Semua langsung dari Tab 1
        tk.Button(btn_frame, text="🚀 JALANKAN SEMUA ALUR", command=self.start_full_pipeline, bg="#0284c7", fg="#ffffff", activebackground="#0369a1", activeforeground="#ffffff", font=("Segoe UI", 9, "bold"), bd=0, padx=14, pady=6, cursor="hand2").pack(side="left", padx=(10, 0))

        self.vec_status_label = ttk.Label(btn_frame, text="Status: Ready", font=("Segoe UI", 9, "italic"), foreground="#a6adc8")
        self.vec_status_label.pack(side="right")

        log_frame = ttk.Frame(parent, padding=(15, 5, 15, 15))
        log_frame.pack(fill="both", expand=True)

        ttk.Label(log_frame, text="Log Vektorisasi:", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 2))
        self.vec_log_area = scrolledtext.ScrolledText(log_frame, bg="#11111b", fg="#a6e3a1", insertbackground="#cdd6f4", font=("Consolas", 9), bd=1)
        self.vec_log_area.pack(fill="both", expand=True)
        self.vec_log_area.insert("end", "[SYSTEM] Siap memproses vektorisasi.\n")

    def browse_vec_input(self):
        f = filedialog.askdirectory(title="Pilih Folder Input Gambar")
        if f:
            self.vec_input_entry.delete(0, "end")
            self.vec_input_entry.insert(0, os.path.normpath(f))
            cand_svg = os.path.join(f, "SVG")
            if os.path.isdir(cand_svg):
                self.vec_output_entry.delete(0, "end")
                self.vec_output_entry.insert(0, os.path.normpath(cand_svg))
            elif not self.vec_output_entry.get().strip():
                self.vec_output_entry.delete(0, "end")
                self.vec_output_entry.insert(0, os.path.normpath(f))

    def browse_vec_output(self):
        f = filedialog.askdirectory(title="Pilih Folder Output SVG")
        if f:
            self.vec_output_entry.delete(0, "end")
            self.vec_output_entry.insert(0, os.path.normpath(f))
            if hasattr(self, 'ai_input_entry') and not self.ai_input_entry.get().strip():
                self.ai_input_entry.delete(0, "end")
                self.ai_input_entry.insert(0, os.path.normpath(f))

    def vec_log(self, text):
        def _update():
            self.vec_log_area.insert("end", text + "\n")
            self.vec_log_area.see("end")
        self.root.after(0, _update)

    def start_vectorizer(self):
        if self.pipeline_is_running:
            messagebox.showinfo("Pipeline Berjalan", "Alur Lengkap sedang berjalan.")
            return

        in_dir = self.vec_input_entry.get().strip()
        out_dir = self.vec_output_entry.get().strip()
        if not in_dir or not os.path.exists(in_dir):
            messagebox.showerror("Error", f"Folder Input tidak valid:\n{in_dir}")
            return
        if not out_dir:
            out_dir = in_dir
            self.vec_output_entry.insert(0, out_dir)

        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vectorize.js")
        if not os.path.exists(script_path):
            messagebox.showerror("Error", f"Script vectorize.js tidak ditemukan!")
            return

        self.vec_is_running = True
        self.vec_btn_run.config(state="disabled", bg="#45475a")
        self.vec_btn_stop.config(state="normal", bg="#f43f5e")
        self.vec_status_label.config(text="Status: Berjalan 🚀", foreground="#10b981")

        self.vec_log_area.delete("1.0", "end")
        self.vec_log(f"[START] Memulai Vectorizer.ai...")
        self.vec_log(f"[INPUT]  {in_dir}")
        self.vec_log(f"[OUTPUT] {out_dir} (Otomatis skip jika sudah ada di folder ini)\n")
        threading.Thread(target=self.run_vec_script, args=(script_path, in_dir, out_dir), daemon=True).start()

    def run_vec_script(self, script_path, in_dir, out_dir):
        cmd = ["node", script_path, "--input", in_dir, "--output", out_dir]
        try:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            self.vec_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True, creationflags=flags)
            for line in iter(self.vec_process.stdout.readline, ''):
                if line:
                    self.vec_log(line.rstrip('\r\n'))
            self.vec_process.wait()
        except Exception as e:
            self.vec_log(f"\n[ERROR] {e}")
        finally:
            self.root.after(0, self.reset_vec_ui)

    def stop_vectorizer(self):
        if self.vec_process and self.vec_is_running:
            self.vec_is_running = False
            self.vec_log("\n[STOP] Menghentikan proses...")
            if sys.platform == "win32":
                try:
                    subprocess.call(['taskkill', '/F', '/T', '/PID', str(self.vec_process.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    subprocess.call(['powershell', '-NoProfile', '-Command', "Get-CimInstance Win32_Process -Filter \"name = 'chrome.exe'\" | Where-Object { $_.CommandLine -like '*puppeteer_chrome_profile*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass
            else:
                self.vec_process.terminate()
            self.reset_vec_ui()

    def reset_vec_ui(self):
        self.vec_is_running = False
        self.vec_btn_run.config(state="normal", bg="#10b981")
        self.vec_btn_stop.config(state="disabled", bg="#45475a")
        self.vec_status_label.config(text="Status: Ready", foreground="#a6adc8")

    # =========================================================================
    # TAB 2: ADOBE ILLUSTRATOR SVG CLEANER
    # =========================================================================
    def setup_cleaner_tab(self, parent):
        self.ai_process = None
        self.ai_is_running = False

        header = ttk.Frame(parent, padding=(15, 10))
        header.pack(fill="x")
        ttk.Label(header, text="🎨 Adobe Illustrator SVG Cleaner", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Pembersihan & Restrukturisasi 3 Layer (Art Line, Color, Background).", style="Subtitle.TLabel").pack(anchor="w")

        card = ttk.Frame(parent, style="Card.TFrame", padding=12)
        card.pack(fill="x", padx=15, pady=5)

        # AI Exe Path
        ttk.Label(card, text="Path Illustrator.exe:", style="Card.TLabel", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 2))
        self.ai_entry = ttk.Entry(card, font=("Segoe UI", 8))
        self.ai_entry.grid(row=1, column=0, sticky="ew", padx=(0, 10), ipady=2)
        ai_default = r"C:\Program Files\Adobe\Adobe Illustrator 2021\Support Files\Contents\Windows\Illustrator.exe"
        if os.path.exists(ai_default):
            self.ai_entry.insert(0, ai_default)

        tk.Button(card, text="🔍 Cari Executable", command=self.browse_ai_exe, bg="#21262d", fg="#f0f6fc", activebackground="#30363d", activeforeground="#ffffff", font=("Segoe UI", 8, "bold"), bd=0, padx=8, pady=2, cursor="hand2").grid(row=1, column=1, sticky="e")

        ttk.Frame(card, height=6, style="Card.TFrame").grid(row=2, column=0, columnspan=2)

        # Input SVG Folder
        ttk.Label(card, text="Folder Input File SVG:", style="Card.TLabel", font=("Segoe UI", 9, "bold")).grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 2))
        self.ai_input_entry = ttk.Entry(card, font=("Segoe UI", 9))
        self.ai_input_entry.grid(row=4, column=0, sticky="ew", padx=(0, 10), ipady=3)

        tk.Button(card, text="📁 Pilih Folder", command=self.browse_ai_input, bg="#21262d", fg="#f0f6fc", activebackground="#30363d", activeforeground="#ffffff", font=("Segoe UI", 9, "bold"), bd=0, padx=10, pady=3, cursor="hand2").grid(row=4, column=1, sticky="e")

        ttk.Frame(card, height=6, style="Card.TFrame").grid(row=5, column=0, columnspan=2)

        # Output SVG Folder
        ttk.Label(card, text="Folder Output (Hasil EPS + JPG & Otomatis Cek Skip File):", style="Card.TLabel", font=("Segoe UI", 9, "bold")).grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 2))
        self.ai_output_entry = ttk.Entry(card, font=("Segoe UI", 9))
        self.ai_output_entry.grid(row=7, column=0, sticky="ew", padx=(0, 10), ipady=3)

        tk.Button(card, text="📁 Pilih Folder", command=self.browse_ai_output, bg="#21262d", fg="#f0f6fc", activebackground="#30363d", activeforeground="#ffffff", font=("Segoe UI", 9, "bold"), bd=0, padx=10, pady=3, cursor="hand2").grid(row=7, column=1, sticky="e")
        card.columnconfigure(0, weight=1)

        # Load konfigurasi terakhir jika ada
        cfg_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clean_config.json")
        if os.path.exists(cfg_file):
            try:
                with open(cfg_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    cin = cfg.get("input_folder", "")
                    cout = cfg.get("output_folder", "")
                    if cin and os.path.exists(cin):
                        self.ai_input_entry.insert(0, os.path.normpath(cin))
                    if cout:
                        self.ai_output_entry.insert(0, os.path.normpath(cout))
            except Exception:
                pass

        btn_frame = ttk.Frame(parent, padding=(15, 5))
        btn_frame.pack(fill="x")

        self.ai_btn_run = tk.Button(btn_frame, text="▶ MULAI OTOMASI CLEANER", command=self.start_cleaner, bg="#10b981", fg="#ffffff", font=("Segoe UI", 10, "bold"), bd=0, padx=20, pady=6, cursor="hand2")
        self.ai_btn_run.pack(side="left", padx=(0, 10))

        self.ai_btn_stop = tk.Button(btn_frame, text="⏹ HENTIKAN", command=self.stop_cleaner, state="disabled", bg="#f43f5e", fg="#ffffff", font=("Segoe UI", 10, "bold"), bd=0, padx=20, pady=6, cursor="hand2")
        self.ai_btn_stop.pack(side="left")

        self.ai_status_label = ttk.Label(btn_frame, text="Status: Ready", font=("Segoe UI", 9, "italic"), foreground="#a6adc8")
        self.ai_status_label.pack(side="right")

        log_frame = ttk.Frame(parent, padding=(15, 5, 15, 15))
        log_frame.pack(fill="both", expand=True)

        ttk.Label(log_frame, text="Log Status Illustrator:", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 2))
        self.ai_log_area = scrolledtext.ScrolledText(log_frame, bg="#11111b", fg="#a6e3a1", insertbackground="#cdd6f4", font=("Consolas", 9), bd=1)
        self.ai_log_area.pack(fill="both", expand=True)
        self.ai_log_area.insert("end", "[SYSTEM] Siap memproses pembersihan SVG di Illustrator.\n")

    def browse_ai_exe(self):
        f = filedialog.askopenfilename(title="Pilih Executable Illustrator.exe", filetypes=[("Executable Files", "*.exe"), ("All Files", "*.*")])
        if f:
            self.ai_entry.delete(0, "end")
            self.ai_entry.insert(0, os.path.normpath(f))

    def browse_ai_input(self):
        f = filedialog.askdirectory(title="Pilih Folder Input File SVG")
        if f:
            self.ai_input_entry.delete(0, "end")
            self.ai_input_entry.insert(0, os.path.normpath(f))
            if not self.ai_output_entry.get().strip():
                self.ai_output_entry.insert(0, os.path.normpath(f + "_clean"))

    def browse_ai_output(self):
        f = filedialog.askdirectory(title="Pilih Folder Output SVG Bersih")
        if f:
            self.ai_output_entry.delete(0, "end")
            self.ai_output_entry.insert(0, os.path.normpath(f))

    def ai_log(self, text):
        def _update():
            self.ai_log_area.insert("end", text + "\n")
            self.ai_log_area.see("end")
        self.root.after(0, _update)

    def start_cleaner(self):
        if self.pipeline_is_running:
            messagebox.showinfo("Pipeline Berjalan", "Alur Lengkap sedang berjalan.")
            return

        ai_exe = self.ai_entry.get().strip()
        in_dir = self.ai_input_entry.get().strip()
        out_dir = self.ai_output_entry.get().strip()

        if not ai_exe or not os.path.exists(ai_exe):
            messagebox.showerror("Error", f"Executable Illustrator tidak ditemukan:\n{ai_exe}")
            return
        if not in_dir or not os.path.exists(in_dir):
            messagebox.showerror("Error", f"Folder Input SVG tidak valid:\n{in_dir}")
            return
        if not out_dir:
            out_dir = in_dir + "_clean"
            self.ai_output_entry.insert(0, out_dir)

        os.makedirs(out_dir, exist_ok=True)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        jsx_path = os.path.join(script_dir, "clean_svg.jsx")
        config_path = os.path.join(script_dir, "clean_config.json")
        log_path = os.path.join(script_dir, "clean_status.log")

        if not os.path.exists(jsx_path):
            messagebox.showerror("Error", f"Skrip clean_svg.jsx tidak ditemukan!")
            return

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({"input_folder": in_dir.replace("\\", "/"), "output_folder": out_dir.replace("\\", "/")}, f, indent=4)

        with open(log_path, "w", encoding="utf-8") as f:
            f.write("")

        self.ai_is_running = True
        self.ai_btn_run.config(state="disabled", bg="#45475a")
        self.ai_btn_stop.config(state="normal", bg="#f43f5e")
        self.ai_status_label.config(text="Status: Memproses di Illustrator 🎨", foreground="#10b981")

        self.ai_log_area.delete("1.0", "end")
        self.ai_log(f"[START] Memulai pembersihan SVG di Adobe Illustrator...")
        self.ai_log(f"[INPUT]  {in_dir}")
        self.ai_log(f"[OUTPUT] {out_dir} (Otomatis skip jika sudah ada file sejenis)\n")

        threading.Thread(target=self.monitor_ai_log, args=(log_path,), daemon=True).start()
        threading.Thread(target=self.run_ai_script, args=(ai_exe, jsx_path), daemon=True).start()

    def run_ai_script(self, ai_exe, jsx_path):
        cmd = [ai_exe, "-r", jsx_path]
        try:
            self.ai_process = subprocess.Popen(cmd)
            self.ai_process.wait()
        except Exception as e:
            self.ai_log(f"\n[ERROR] {e}")
        finally:
            self.root.after(0, self.reset_ai_ui)

    def monitor_ai_log(self, log_path):
        last_pos = 0
        while self.ai_is_running:
            if os.path.exists(log_path):
                try:
                    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                        f.seek(last_pos)
                        lines = f.readlines()
                        last_pos = f.tell()
                        for line in lines:
                            if line.strip():
                                self.ai_log(line.rstrip("\r\n"))
                                if "[COMPLETE]" in line:
                                    self.ai_is_running = False
                                    break
                except Exception:
                    pass
            time.sleep(0.5)

    def stop_cleaner(self):
        if self.ai_is_running:
            self.ai_is_running = False
            self.ai_log("\n[STOP] Menghentikan proses...")
            if self.ai_process:
                try:
                    self.ai_process.terminate()
                except Exception:
                    pass
            self.reset_ai_ui()

    def reset_ai_ui(self):
        self.ai_is_running = False
        self.ai_btn_run.config(state="normal", bg="#10b981")
        self.ai_btn_stop.config(state="disabled", bg="#45475a")
        self.ai_status_label.config(text="Status: Ready", foreground="#a6adc8")

    # =========================================================================
    # TAB 3: ABSEN & PENCATATAN UPLOAD (INTEGRASI FILE EXPLORER)
    # =========================================================================
    def setup_picker_tab(self, parent):
        self.memory_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "upload_memory.json")
        self.load_upload_memory()
        self.picker_items = []
        self.checked_keys = set()

        # Top Control Card (Sleek & Mini)
        card_top = ttk.Frame(parent, style="Card.TFrame", padding=(8, 6))
        card_top.pack(fill="x", padx=8, pady=(4, 4))

        # Row 1: Folder Input (Clean 1 line)
        folder_row = ttk.Frame(card_top, style="Card.TFrame")
        folder_row.pack(fill="x", pady=(0, 4))

        ttk.Label(folder_row, text="Folder:", style="Card.TLabel", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        self.picker_folder_entry = ttk.Entry(folder_row, font=("Segoe UI", 9))
        self.picker_folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 6), ipady=2)
        self.picker_folder_entry.bind("<Return>", lambda e: self.scan_picker_folder(auto_open=False))

        default_picker_dir = ""
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clean_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    cand = cfg.get("output_folder", "")
                    if os.path.exists(cand):
                        default_picker_dir = cand
            except Exception:
                pass
        if not default_picker_dir:
            for cand in [r"D:\ADOBESTOCK\Part 1\EPS JPG", r"D:\ADOBESTOCK\Part 1\SVG", r"D:\MicroStock\ADOBESTOCK\STOK READY UP\natal series\KLOTER1\SVG", r"D:\MicroStock"]:
                if os.path.exists(cand):
                    default_picker_dir = cand
                    break
        if default_picker_dir:
            self.picker_folder_entry.insert(0, os.path.normpath(default_picker_dir))

        tk.Button(
            folder_row,
            text="📁 Ganti",
            command=self.browse_picker_folder,
            bg="#21262d",
            fg="#f0f6fc",
            activebackground="#30363d",
            activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"),
            bd=0,
            padx=10,
            pady=2,
            cursor="hand2"
        ).pack(side="right")

        # Row 2: Ambil Acak & Tombol Otomasi Explorer (Single Clean Row)
        ctrl_row = ttk.Frame(card_top, style="Card.TFrame")
        ctrl_row.pack(fill="x", pady=(2, 0))

        btn_pill = {"bg": "#21262d", "fg": "#38bdf8", "activebackground": "#30363d", "activeforeground": "#ffffff", "bd": 0, "font": ("Segoe UI", 9, "bold"), "cursor": "hand2", "pady": 2}
        ttk.Label(ctrl_row, text="Ambil:", style="Card.TLabel", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 4))
        tk.Button(ctrl_row, text="5", command=lambda: self.start_explorer_automation(5), padx=8, **btn_pill).pack(side="left", padx=2)
        tk.Button(ctrl_row, text="10", command=lambda: self.start_explorer_automation(10), padx=8, **btn_pill).pack(side="left", padx=2)
        tk.Button(ctrl_row, text="20", command=lambda: self.start_explorer_automation(20), padx=8, **btn_pill).pack(side="left", padx=2)
        tk.Button(ctrl_row, text="Semua", command=lambda: self.start_explorer_automation("all"), padx=8, **btn_pill).pack(side="left", padx=2)

        self.picker_custom_spin = ttk.Spinbox(ctrl_row, from_=1, to=500, width=4)
        self.picker_custom_spin.set(15)
        self.picker_custom_spin.pack(side="left", padx=(6, 4))

        # TOMBOL UTAMA: OTOMASI EXPLORER
        self.btn_start_automation = tk.Button(
            ctrl_row,
            text="🚀 Buka & Pilih di Explorer",
            bg="#0284c7",
            fg="#ffffff",
            activebackground="#0369a1",
            activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"),
            bd=0,
            padx=12,
            pady=3,
            cursor="hand2",
            command=self.start_explorer_automation
        )
        self.btn_start_automation.pack(side="left", padx=(2, 8))

        # Filter View Dropdown (kanan)
        self.picker_filter_var = tk.StringVar(value="Belum Upload")
        filter_cb = ttk.Combobox(
            ctrl_row,
            textvariable=self.picker_filter_var,
            values=["Belum Upload", "Semua", "Sudah Upload"],
            state="readonly",
            width=13
        )
        filter_cb.pack(side="right")
        filter_cb.bind("<<ComboboxSelected>>", lambda e: self.apply_picker_filter())
        ttk.Label(ctrl_row, text="Filter:", style="Card.TLabel", font=("Segoe UI", 8)).pack(side="right", padx=(0, 4))

        # Row 3: Tombol Aksi Upload & Counter (DI ATAS - langsung terlihat tanpa scroll/full layar)
        action_row = ttk.Frame(card_top, style="Card.TFrame")
        action_row.pack(fill="x", pady=(6, 2))

        # Main Green Button: Simpan ke Ingatan
        self.btn_mark_uploaded = tk.Button(
            action_row,
            text="✅ Tandai Sudah Upload (Ingat)",
            command=self.mark_selected_as_uploaded,
            bg="#10b981",
            fg="#ffffff",
            activebackground="#059669",
            activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"),
            bd=0,
            padx=12,
            pady=4,
            cursor="hand2"
        )
        self.btn_mark_uploaded.pack(side="left", padx=(0, 6))

        # Batal Centang
        tk.Button(
            action_row,
            text="Batal Centang",
            command=self.clear_selection,
            bg="#21262d",
            fg="#8b949e",
            activebackground="#30363d",
            activeforeground="#f0f6fc",
            font=("Segoe UI", 8),
            bd=0,
            padx=8,
            pady=4,
            cursor="hand2"
        ).pack(side="left", padx=(0, 6))

        # Batalkan Status Upload (Undo jika salah klik)
        tk.Button(
            action_row,
            text="↩ Batal Upload",
            command=self.unmark_selected_as_uploaded,
            bg="#21262d",
            fg="#f87171",
            activebackground="#30363d",
            activeforeground="#fca5a5",
            font=("Segoe UI", 8),
            bd=0,
            padx=8,
            pady=4,
            cursor="hand2"
        ).pack(side="left", padx=(0, 10))

        # Counter text
        self.picker_counter_label = ttk.Label(
            action_row,
            text="Belum: 0 | Sudah: 0 | Dipilih: 0",
            style="Card.TLabel",
            font=("Segoe UI", 8)
        )
        self.picker_counter_label.pack(side="left")

        # Right status banner
        self.picker_status_banner = ttk.Label(
            action_row,
            text="🟢 Siap",
            style="Card.TLabel",
            font=("Segoe UI", 8, "bold"),
            foreground="#38bdf8"
        )
        self.picker_status_banner.pack(side="right")

        # Table Checklist Card (Treeview) - Mengisi ruang sisa di bawah
        table_card = ttk.Frame(parent, style="Card.TFrame", padding=(4, 4))
        table_card.pack(fill="both", expand=True, padx=8, pady=(4, 6))

        columns = ("check", "no", "status", "basename")
        self.picker_tree = ttk.Treeview(table_card, columns=columns, show="headings", selectmode="extended")

        self.picker_tree.heading("check", text="☑", anchor="center")
        self.picker_tree.heading("no", text="#", anchor="center")
        self.picker_tree.heading("status", text="Status", anchor="w")
        self.picker_tree.heading("basename", text="Nama File (.EPS)", anchor="w")

        self.picker_tree.column("check", width=40, anchor="center", stretch=False)
        self.picker_tree.column("no", width=36, anchor="center", stretch=False)
        self.picker_tree.column("status", width=95, anchor="w", stretch=False)
        self.picker_tree.column("basename", width=380, anchor="w", stretch=True)

        self.picker_tree.tag_configure("ready", foreground="#f0f6fc")
        self.picker_tree.tag_configure("uploaded", foreground="#64748b")
        self.picker_tree.tag_configure("checked", background="#1e3a8a", foreground="#38bdf8")

        vsb = ttk.Scrollbar(table_card, orient="vertical", command=self.picker_tree.yview)
        self.picker_tree.configure(yscrollcommand=vsb.set)

        self.picker_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.picker_tree.bind("<Button-1>", self.on_tree_click)
        self.picker_tree.bind("<Double-1>", self.on_tree_double_click)
        self.picker_tree.bind("<space>", self.on_tree_space_toggle)

        # Auto scan default folder
        if default_picker_dir and os.path.isdir(default_picker_dir):
            self.root.after(200, lambda: self.scan_picker_folder(auto_open=False))

    # -------------------------------------------------------------------------
    # CORE LOGIC & FILE EXPLORER INTEGRATION
    # -------------------------------------------------------------------------
    def load_upload_memory(self):
        self.memory_data = {"uploaded": {}}
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "uploaded" in data:
                        self.memory_data = data
            except Exception:
                pass

    def save_upload_memory(self):
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self.memory_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("Error Simpan Ingatan", f"Gagal menyimpan memory file:\n{e}")

    def browse_picker_folder(self):
        curr = self.picker_folder_entry.get().strip()
        init_dir = curr if (curr and os.path.isdir(curr)) else "D:\\"
        folder = filedialog.askdirectory(title="Pilih Folder Input Artwork (.EPS)", initialdir=init_dir)
        if folder:
            self.picker_folder_entry.delete(0, tk.END)
            self.picker_folder_entry.insert(0, os.path.normpath(folder))
            self.scan_picker_folder(auto_open=False)

    def open_current_folder_in_explorer(self):
        """Membuka folder input langsung di Windows File Explorer asli."""
        folder = self.picker_folder_entry.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Folder Tidak Ditemukan", "Pilih folder input artwork yang valid terlebih dahulu!")
            return
        try:
            os.startfile(os.path.normpath(folder))
        except Exception:
            try:
                subprocess.Popen(f'explorer.exe "{os.path.normpath(folder)}"')
            except Exception as e:
                messagebox.showerror("Error", f"Gagal membuka File Explorer:\n{e}")

    def scan_picker_folder(self, auto_open=True):
        """Scan file .EPS di folder input, cocokkan dengan ingatan upload, dan buka Explorer jika diatur."""
        folder = self.picker_folder_entry.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Folder Tidak Valid", "Silakan pilih folder input yang benar!")
            return

        eps_list = []
        try:
            for entry in os.scandir(folder):
                if entry.is_file():
                    name, ext = os.path.splitext(entry.name)
                    if ext.lower() == ".eps":
                        eps_list.append((name, entry.path))
        except Exception as e:
            messagebox.showerror("Error Scan", f"Gagal membaca folder:\n{e}")
            return

        self.picker_items = []
        uploaded_dict = self.memory_data.get("uploaded", {})

        for basename, eps_path in sorted(eps_list, key=lambda x: x[0].lower()):
            base_key = basename.lower()
            is_uploaded = base_key in uploaded_dict
            upload_date = uploaded_dict[base_key].get("date", "-") if is_uploaded else "-"

            jpg_path = None
            for cand_ext in [".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"]:
                cand_path = os.path.join(folder, basename + cand_ext)
                if os.path.exists(cand_path):
                    jpg_path = cand_path
                    break

            has_preview = "🖼️ Ada (.jpg)" if jpg_path else "❌ Tidak Ada"

            self.picker_items.append({
                "base_key": base_key,
                "basename": basename,
                "eps_path": eps_path,
                "jpg_path": jpg_path,
                "has_preview": has_preview,
                "status": "uploaded" if is_uploaded else "ready",
                "upload_date": upload_date,
                "tree_id": ""
            })

        self.checked_keys.clear()
        self.apply_picker_filter()

        # Otomatis buka File Explorer jika opsi diaktifkan
        if auto_open:
            self.open_current_folder_in_explorer()

    def apply_picker_filter(self):
        """Menampilkan data ke tabel checklist dengan status centang dan tag warna."""
        filter_mode = self.picker_filter_var.get()

        for item_id in self.picker_tree.get_children():
            self.picker_tree.delete(item_id)

        visible_count = 0
        for item in self.picker_items:
            if filter_mode in ("Belum Upload", "Belum Upload (Tersedia)") and item["status"] != "ready":
                item["tree_id"] = ""
                continue
            elif filter_mode in ("Sudah Upload", "Sudah Upload (Ingatan)") and item["status"] != "uploaded":
                item["tree_id"] = ""
                continue

            visible_count += 1
            is_checked = item["base_key"] in self.checked_keys
            chk_icon = "☑" if is_checked else "☐"

            status_text = "Sudah Upload" if item["status"] == "uploaded" else "Belum Upload"
            tags = []
            if is_checked:
                tags.append("checked")
            elif item["status"] == "uploaded":
                tags.append("uploaded")
            else:
                tags.append("ready")

            tree_id = self.picker_tree.insert(
                "",
                "end",
                values=(
                    chk_icon,
                    visible_count,
                    status_text,
                    f"{item['basename']}.eps"
                ),
                tags=tuple(tags)
            )
            item["tree_id"] = tree_id

        self.update_picker_counters()

    # -------------------------------------------------------------------------
    # INTERACTION & SELECTION (ABSEN CHECKLIST)
    # -------------------------------------------------------------------------
    def on_tree_click(self, event):
        """Klik pada baris atau kolom centang untuk men-toggle centang item."""
        region = self.picker_tree.identify_region(event.x, event.y)
        if region in ("tree", "cell"):
            item_id = self.picker_tree.identify_row(event.y)
            if item_id:
                self.toggle_check_item(item_id)

    def on_tree_space_toggle(self, event):
        """Tekan spasi untuk men-toggle centang baris yang disorot."""
        selected_ids = self.picker_tree.selection()
        for item_id in selected_ids:
            self.toggle_check_item(item_id)
        return "break"

    def toggle_check_item(self, tree_id):
        target_item = next((it for it in self.picker_items if it.get("tree_id") == tree_id), None)
        if not target_item:
            return

        base_key = target_item["base_key"]
        if base_key in self.checked_keys:
            self.checked_keys.remove(base_key)
        else:
            self.checked_keys.add(base_key)

        self.refresh_row_display(target_item)
        self.update_picker_counters()

    def refresh_row_display(self, item):
        tree_id = item.get("tree_id")
        if not tree_id or not self.picker_tree.exists(tree_id):
            return

        is_checked = item["base_key"] in self.checked_keys
        chk_icon = "☑" if is_checked else "☐"
        status_text = "Sudah Upload" if item["status"] == "uploaded" else "Belum Upload"

        current_vals = list(self.picker_tree.item(tree_id, "values"))
        if len(current_vals) >= 4:
            current_vals[0] = chk_icon
            current_vals[2] = status_text

        tags = []
        if is_checked:
            tags.append("checked")
        elif item["status"] == "uploaded":
            tags.append("uploaded")
        else:
            tags.append("ready")

        self.picker_tree.item(tree_id, values=current_vals, tags=tuple(tags))

    def on_tree_double_click(self, event):
        """Double click baris untuk menyorot file di File Explorer."""
        item_id = self.picker_tree.identify_row(event.y)
        if not item_id:
            return
        target_item = next((it for it in self.picker_items if it.get("tree_id") == item_id), None)
        if target_item and os.path.exists(target_item["eps_path"]):
            folder = self.picker_folder_entry.get().strip()
            copy_files_to_windows_clipboard([target_item["eps_path"]])
            threading.Thread(
                target=select_files_in_windows_explorer,
                args=(folder, [target_item["basename"] + ".eps"]),
                daemon=True
            ).start()

    def highlight_checked_in_explorer(self):
        """Membuka File Explorer Windows dan secara otomatis menyeleksi semua file .EPS yang tercentang."""
        self.start_explorer_automation()

    def start_explorer_automation(self, count=None):
        """
        TOMBOL MULAI:
        Sistem melakukan otomasi, pergi ke Windows File Explorer,
        langsung memilih (multi-select) semua file sesuai GUI,
        dan STAY di File Explorer dalam keadaan file terpilih siap disalin/diseret.
        """
        ready_items = [it for it in self.picker_items if it["status"] == "ready"]
        if not ready_items and not self.checked_keys:
            messagebox.showinfo("Semua Sudah Diupload", "Semua file .EPS di folder ini sudah tercatat SUDAH UPLOAD di ingatan!\nTidak ada file belum upload yang bisa dipilih.")
            return

        folder = self.picker_folder_entry.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Folder Tidak Ditemukan", "Pilih folder input artwork yang valid terlebih dahulu!")
            return

        # Jika count ditentukan (misal tombol 5, 10, 20, all) ATAU jika belum ada centang:
        if count is not None or not self.checked_keys:
            target_count = count
            if target_count is None:
                try:
                    target_count = int(self.picker_custom_spin.get())
                except Exception:
                    target_count = 10

            if target_count == "all":
                chosen = ready_items
            else:
                k = min(int(target_count), len(ready_items))
                chosen = random.sample(ready_items, k) if k > 0 else []

            if not chosen:
                messagebox.showwarning("Tidak Ada File", "Tidak ada file .EPS yang tersedia untuk dipilih.")
                return

            if self.picker_filter_var.get() in ("Sudah Upload", "Sudah Upload (Ingatan)"):
                self.picker_filter_var.set("Belum Upload")
                self.apply_picker_filter()

            self.checked_keys = {it["base_key"] for it in chosen}
            for it in self.picker_items:
                if it.get("tree_id"):
                    self.refresh_row_display(it)

            if chosen and chosen[0].get("tree_id"):
                self.picker_tree.see(chosen[0]["tree_id"])

            self.update_picker_counters()

        checked_items = [it for it in self.picker_items if it["base_key"] in self.checked_keys]
        if not checked_items:
            messagebox.showwarning("Pilih File", "Centang minimal 1 file .EPS terlebih dahulu!")
            return

        eps_names = [it["basename"] + ".eps" for it in checked_items]
        eps_paths = [it["eps_path"] for it in checked_items if os.path.exists(it["eps_path"])]

        # Otomatis salin ke clipboard Windows
        copy_files_to_windows_clipboard(eps_paths)

        if hasattr(self, "picker_status_banner"):
            self.picker_status_banner.config(
                text=f"🚀 Memilih {len(checked_items)} file...",
                foreground="#38bdf8"
            )

        def worker():
            sel_count = select_files_in_windows_explorer(folder, eps_names)
            def update_ui():
                if hasattr(self, "picker_status_banner"):
                    self.picker_status_banner.config(
                        text=f"🟢 {sel_count} terpilih!",
                        foreground="#34d399"
                    )
            self.root.after(0, update_ui)

        threading.Thread(target=worker, daemon=True).start()

    def pick_random(self, count):
        self.start_explorer_automation(count)

    def pick_custom_random(self):
        try:
            val = int(self.picker_custom_spin.get())
            if val <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Jumlah Tidak Valid", "Masukkan angka jumlah yang valid (misal: 15)!")
            return
        self.start_explorer_automation(val)

    def clear_selection(self):
        self.checked_keys.clear()
        for it in self.picker_items:
            if it.get("tree_id"):
                self.refresh_row_display(it)
        self.update_picker_counters()

    def update_picker_counters(self):
        total = len(self.picker_items)
        ready_count = sum(1 for it in self.picker_items if it["status"] == "ready")
        uploaded_count = total - ready_count
        checked_count = len(self.checked_keys)

        if hasattr(self, "picker_counter_label"):
            self.picker_counter_label.config(
                text=f"Belum: {ready_count} | Sudah: {uploaded_count} | Dipilih: {checked_count}"
            )

    # -------------------------------------------------------------------------
    # MARK AS UPLOADED / UNMARK
    # -------------------------------------------------------------------------
    def mark_selected_as_uploaded(self):
        """Menandai file yang tercentang sebagai SUDAH UPLOAD dan menyimpannya ke ingatan permanen."""
        if not self.checked_keys:
            messagebox.showwarning("Pilih File", "Centang file .EPS yang ingin ditandai sudah upload!")
            return

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        uploaded_dict = self.memory_data.setdefault("uploaded", {})
        marked_count = 0

        for it in self.picker_items:
            if it["base_key"] in self.checked_keys:
                uploaded_dict[it["base_key"]] = {
                    "date": now_str,
                    "basename": it["basename"]
                }
                it["status"] = "uploaded"
                it["upload_date"] = now_str
                marked_count += 1

        self.save_upload_memory()
        self.checked_keys.clear()
        self.apply_picker_filter()

        messagebox.showinfo(
            "Berhasil Dicatat!",
            f"✅ {marked_count} file .EPS berhasil ditandai SUDAH UPLOAD dan disimpan ke ingatan!\n\n"
            f"Sistem TIDAK AKAN merekomendasikan file-file ini lagi pada pengambilan acak berikutnya."
        )

    def unmark_selected_as_uploaded(self):
        """Membatalkan status upload file tercentang."""
        if not self.checked_keys:
            messagebox.showwarning("Pilih File", "Centang file .EPS yang ingin dibatalkan status uploadnya!")
            return

        uploaded_dict = self.memory_data.setdefault("uploaded", {})
        unmarked_count = 0

        for it in self.picker_items:
            if it["base_key"] in self.checked_keys:
                if it["base_key"] in uploaded_dict:
                    del uploaded_dict[it["base_key"]]
                    it["status"] = "ready"
                    it["upload_date"] = "-"
                    unmarked_count += 1

        self.save_upload_memory()
        self.checked_keys.clear()
        self.apply_picker_filter()
        messagebox.showinfo("Status Diperbarui", f"Berhasil mengembalikan status {unmarked_count} file .EPS menjadi 'Belum Upload'.")

    def copy_selected_to_clipboard(self):
        """Menyalin file fisik .EPS yang tercentang ke Windows Clipboard."""
        if not self.checked_keys:
            messagebox.showwarning("Pilih File", "Centang setidaknya 1 file .EPS terlebih dahulu!")
            return

        eps_files = [it["eps_path"] for it in self.picker_items if it["base_key"] in self.checked_keys and os.path.exists(it["eps_path"])]
        count = copy_files_to_windows_clipboard(eps_files)
        if count > 0:
            messagebox.showinfo(
                "Disalin ke Clipboard!",
                f"✅ Berhasil menyalin {count} file .EPS ke Windows Clipboard!\n\n"
                f"Anda bisa langsung Paste (Ctrl+V) di File Explorer atau browser."
            )
        else:
            messagebox.showerror("Gagal Menyalin", "Tidak ada file fisik .EPS yang ditemukan.")

if __name__ == "__main__":
    root = tk.Tk()
    app = CombinedMicrostockGUI(root)
    root.mainloop()
