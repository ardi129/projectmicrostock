import subprocess
import os
import time

ai_exe = r"C:\Program Files\Adobe\Adobe Illustrator 2021\Support Files\Contents\Windows\Illustrator.exe"
jsx_path = os.path.abspath("clean_svg.jsx")
log_path = os.path.abspath("clean_status.log")

print(f"Launching Illustrator with {jsx_path}...")
p = subprocess.Popen([ai_exe, "-r", jsx_path])

# Monitor clean_status.log
last_pos = 0
start_time = time.time()
while time.time() - start_time < 90:
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(last_pos)
            new_text = f.read()
            last_pos = f.tell()
            if new_text:
                print(new_text, end="", flush=True)
            if "[COMPLETE]" in new_text or "[ERROR INIT]" in new_text:
                break
    time.sleep(1)

print("\nFinished monitoring.")
