"""
Helper script to see if transcript or clips exist in temp/
"""
from pathlib import Path

temp_dir = Path(r"D:\Ai Softwares\Auto Shorts Clipper\temp")
for f in temp_dir.glob("*"):
    print(f"{f.name} ({f.stat().st_size} bytes)")
