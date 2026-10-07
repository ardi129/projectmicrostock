import subprocess
import os

ai_exe = r"C:\Program Files\Adobe\Adobe Illustrator 2021\Support Files\Contents\Windows\Illustrator.exe"
jsx_path = os.path.abspath("debug_test.jsx")

print(f"Launching {ai_exe} with {jsx_path}")
p = subprocess.Popen([ai_exe, "-r", jsx_path])
p.wait()
print("Illustrator finished execution.")
