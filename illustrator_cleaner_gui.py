import os
import sys
import json
import time
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

class IllustratorSVGCleanerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Adobe Illustrator SVG Cleaner & Restructurer")
        self.root.geometry("750x620")
        self.root.minsize(650, 520)
        self.root.configure(bg="#1e1e2e")

        self.process = None
        self.is_running = False
        self.log_thread = None

        # Autodetect Illustrator path
        self.illustrator_path = self.find_illustrator_path()

        self.setup_styles()
        self.create_widgets()

    def find_illustrator_path(self):
        # Known installation paths for Adobe Illustrator on Windows
        candidate_paths = [
            r"C:\Program Files\Adobe\Adobe Illustrator 2021\Support Files\Contents\Windows\Illustrator.exe",
            r"C:\Program Files\Adobe\Adobe Illustrator 2022\Support Files\Contents\Windows\Illustrator.exe",
            r"C:\Program Files\Adobe\Adobe Illustrator 2023\Support Files\Contents\Windows\Illustrator.exe",
            r"C:\Program Files\Adobe\Adobe Illustrator 2024\Support Files\Contents\Windows\Illustrator.exe",
            r"C:\Program Files\Adobe\Adobe Illustrator CC 2020\Support Files\Contents\Windows\Illustrator.exe",
            r"C:\Program Files (x86)\Adobe\Adobe Illustrator 2021\Support Files\Contents\Windows\Illustrator.exe"
        ]
        for p in candidate_paths:
            if os.path.exists(p):
                return p
        return ""

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")

        self.style.configure("TFrame", background="#1e1e2e")
        self.style.configure("Card.TFrame", background="#2b2b3b", relief="flat")

        self.style.configure("TLabel", background="#1e1e2e", foreground="#cdd6f4", font=("Segoe UI", 10))
        self.style.configure("Card.TLabel", background="#2b2b3b", foreground="#cdd6f4", font=("Segoe UI", 10))
        self.style.configure("Title.TLabel", background="#1e1e2e", foreground="#89b4fa", font=("Segoe UI", 16, "bold"))
        self.style.configure("Subtitle.TLabel", background="#1e1e2e", foreground="#a6adc8", font=("Segoe UI", 9))

        self.style.configure("TEntry", fieldbackground="#181825", foreground="#cdd6f4", insertcolor="#cdd6f4", borderwidth=1)

    def create_widgets(self):
        # Header Section
        header_frame = ttk.Frame(self.root, padding=(20, 15, 20, 10))
        header_frame.pack(fill="x")

        title_label = ttk.Label(header_frame, text="🎨 Adobe Illustrator SVG Cleaner", style="Title.TLabel")
        title_label.pack(anchor="w")

        sub_label = ttk.Label(
            header_frame,
            text="Pembersih & Restrukturisasi Layer SVG Batch (Art Line, Color, Background).",
            style="Subtitle.TLabel"
        )
        sub_label.pack(anchor="w", pady=(2, 0))

        # Folder & Illustrator Path Selection (Card)
        card_frame = ttk.Frame(self.root, style="Card.TFrame", padding=15)
        card_frame.pack(fill="x", padx=20, pady=10)

        # 1. Path Illustrator.exe
        ai_label = ttk.Label(card_frame, text="Path Adobe Illustrator.exe:", style="Card.TLabel", font=("Segoe UI", 9, "bold"))
        ai_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 2))

        self.ai_entry = ttk.Entry(card_frame, font=("Segoe UI", 9))
        self.ai_entry.grid(row=1, column=0, sticky="ew", padx=(0, 10), ipady=3)
        if self.illustrator_path:
            self.ai_entry.insert(0, self.illustrator_path)

        btn_browse_ai = tk.Button(
            card_frame, text="🔍 Cari Executable", command=self.browse_illustrator,
            bg="#45475a", fg="#cdd6f4", activebackground="#585b70", activeforeground="#ffffff",
            font=("Segoe UI", 8, "bold"), bd=0, padx=10, pady=3, cursor="hand2"
        )
        btn_browse_ai.grid(row=1, column=1, sticky="e")

        ttk.Frame(card_frame, height=8, style="Card.TFrame").grid(row=2, column=0, columnspan=2)

        # 2. Input Folder
        input_label = ttk.Label(card_frame, text="Folder Input File SVG:", style="Card.TLabel", font=("Segoe UI", 10, "bold"))
        input_label.grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 2))

        self.input_entry = ttk.Entry(card_frame, font=("Segoe UI", 10))
        self.input_entry.grid(row=4, column=0, sticky="ew", padx=(0, 10), ipady=4)

        btn_browse_in = tk.Button(
            card_frame, text="📁 Pilih Folder", command=self.browse_input,
            bg="#45475a", fg="#cdd6f4", activebackground="#585b70", activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"), bd=0, padx=12, pady=4, cursor="hand2"
        )
        btn_browse_in.grid(row=4, column=1, sticky="e")

        ttk.Frame(card_frame, height=8, style="Card.TFrame").grid(row=5, column=0, columnspan=2)

        # 3. Output Folder
        output_label = ttk.Label(card_frame, text="Folder Output (Hasil EPS & JPG - Otomatis Cek Skip):", style="Card.TLabel", font=("Segoe UI", 10, "bold"))
        output_label.grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 2))

        self.output_entry = ttk.Entry(card_frame, font=("Segoe UI", 10))
        self.output_entry.grid(row=7, column=0, sticky="ew", padx=(0, 10), ipady=4)

        btn_browse_out = tk.Button(
            card_frame, text="📁 Pilih Folder", command=self.browse_output,
            bg="#45475a", fg="#cdd6f4", activebackground="#585b70", activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"), bd=0, padx=12, pady=4, cursor="hand2"
        )
        btn_browse_out.grid(row=7, column=1, sticky="e")

        card_frame.columnconfigure(0, weight=1)

        # Control Buttons Section
        btn_frame = ttk.Frame(self.root, padding=(20, 5, 20, 10))
        btn_frame.pack(fill="x")

        self.btn_run = tk.Button(
            btn_frame, text="▶ MULAI OTOMASI", command=self.start_automation,
            bg="#10b981", fg="#ffffff", activebackground="#059669", activeforeground="#ffffff",
            font=("Segoe UI", 11, "bold"), bd=0, padx=25, pady=8, cursor="hand2"
        )
        self.btn_run.pack(side="left", padx=(0, 10))

        self.btn_stop = tk.Button(
            btn_frame, text="⏹ HENTIKAN", command=self.stop_automation, state="disabled",
            bg="#f43f5e", fg="#ffffff", activebackground="#e11d48", activeforeground="#ffffff",
            font=("Segoe UI", 11, "bold"), bd=0, padx=25, pady=8, cursor="hand2"
        )
        self.btn_stop.pack(side="left")

        self.status_label = ttk.Label(btn_frame, text="Status: Ready", font=("Segoe UI", 10, "italic"), foreground="#a6adc8")
        self.status_label.pack(side="right")

        # Log Terminal Output
        log_frame = ttk.Frame(self.root, padding=(20, 5, 20, 20))
        log_frame.pack(fill="both", expand=True)

        log_title = ttk.Label(log_frame, text="Log Status Pembersihan Illustrator:", font=("Segoe UI", 10, "bold"))
        log_title.pack(anchor="w", pady=(0, 5))

        self.log_area = scrolledtext.ScrolledText(
            log_frame, bg="#11111b", fg="#a6e3a1", insertbackground="#cdd6f4",
            font=("Consolas", 10), bd=1, relief="solid"
        )
        self.log_area.pack(fill="both", expand=True)
        self.log_area.insert("end", "[SYSTEM] Siap. Silakan tentukan folder dan tekan MULAI OTOMASI.\n")

    def browse_illustrator(self):
        file_path = filedialog.askopenfilename(
            title="Pilih Executable Illustrator.exe",
            filetypes=[("Executable Files", "*.exe"), ("All Files", "*.*")]
        )
        if file_path:
            self.ai_entry.delete(0, "end")
            self.ai_entry.insert(0, os.path.normpath(file_path))

    def browse_input(self):
        folder = filedialog.askdirectory(title="Pilih Folder Input File SVG")
        if folder:
            self.input_entry.delete(0, "end")
            self.input_entry.insert(0, os.path.normpath(folder))
            if not self.output_entry.get().strip():
                self.output_entry.insert(0, os.path.normpath(folder + "_clean"))

    def browse_output(self):
        folder = filedialog.askdirectory(title="Pilih Folder Output SVG Bersih")
        if folder:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, os.path.normpath(folder))

    def log(self, text):
        def _update():
            self.log_area.insert("end", text + "\n")
            self.log_area.see("end")
        self.root.after(0, _update)

    def start_automation(self):
        ai_exe = self.ai_entry.get().strip()
        input_dir = self.input_entry.get().strip()
        output_dir = self.output_entry.get().strip()

        if not ai_exe or not os.path.exists(ai_exe):
            messagebox.showerror("Error", f"Executable Adobe Illustrator tidak ditemukan:\n{ai_exe}")
            return

        if not input_dir or not os.path.exists(input_dir):
            messagebox.showerror("Error", f"Folder Input SVG tidak valid:\n{input_dir}")
            return

        if not output_dir:
            output_dir = input_dir + "_clean"
            self.output_entry.insert(0, output_dir)

        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        jsx_path = os.path.join(script_dir, "clean_svg.jsx")
        config_path = os.path.join(script_dir, "clean_config.json")
        log_path = os.path.join(script_dir, "clean_status.log")

        if not os.path.exists(jsx_path):
            messagebox.showerror("Error", f"File skrip clean_svg.jsx tidak ditemukan di:\n{jsx_path}")
            return

        # Tulis clean_config.json
        config_data = {
            "input_folder": input_dir.replace("\\", "/"),
            "output_folder": output_dir.replace("\\", "/")
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)

        # Reset log status
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("")

        self.is_running = True
        self.btn_run.config(state="disabled", bg="#45475a")
        self.btn_stop.config(state="normal", bg="#f43f5e")
        self.status_label.config(text="Status: Memproses di Illustrator 🎨", foreground="#10b981")

        self.log_area.delete("1.0", "end")
        self.log(f"[START] Memulai pembersihan SVG di Adobe Illustrator...")
        self.log(f"[AI EXE] {ai_exe}")
        self.log(f"[INPUT]  {input_dir}")
        self.log(f"[OUTPUT] {output_dir} (Otomatis skip jika file sudah ada)\n")

        # Thread untuk memantau log file secara real-time
        self.log_thread = threading.Thread(target=self.monitor_log_file, args=(log_path,), daemon=True)
        self.log_thread.start()

        # Thread untuk menjalankan Adobe Illustrator dengan ExtendScript
        threading.Thread(target=self.run_illustrator, args=(ai_exe, jsx_path), daemon=True).start()

    def run_illustrator(self, ai_exe, jsx_path):
        cmd = [ai_exe, "-r", jsx_path]
        try:
            self.process = subprocess.Popen(cmd)
            self.process.wait()
        except Exception as e:
            self.log(f"\n[ERROR] Gagal menjalankan Adobe Illustrator: {e}")
        finally:
            self.on_process_finished()

    def monitor_log_file(self, log_path):
        last_pos = 0
        while self.is_running:
            if os.path.exists(log_path):
                try:
                    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                        f.seek(last_pos)
                        lines = f.readlines()
                        last_pos = f.tell()
                        for line in lines:
                            if line.strip():
                                self.log(line.rstrip("\r\n"))
                                if "[COMPLETE]" in line:
                                    self.is_running = False
                                    break
                except Exception:
                    pass
            time.sleep(0.5)

    def stop_automation(self):
        if self.is_running:
            self.is_running = False
            self.log("\n[STOP] Menghentikan proses...")
            if self.process:
                try:
                    self.process.terminate()
                except Exception:
                    pass
            self.on_process_finished()

    def on_process_finished(self):
        def _reset_ui():
            self.is_running = False
            self.btn_run.config(state="normal", bg="#10b981")
            self.btn_stop.config(state="disabled", bg="#45475a")
            self.status_label.config(text="Status: Selesai / Stopped", foreground="#a6adc8")
        self.root.after(0, _reset_ui)

if __name__ == "__main__":
    root = tk.Tk()
    app = IllustratorSVGCleanerGUI(root)
    root.mainloop()
