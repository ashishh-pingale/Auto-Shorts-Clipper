"""
Tests GTX 1650 hardware NVENC encoding with local portable FFmpeg.
"""

import subprocess
from pathlib import Path
from core_autoclip.downloader import get_ffmpeg_path

ffmpeg_bin = get_ffmpeg_path()
test_out = Path(__file__).resolve().parent / "temp" / "nvenc_test.mp4"
test_out.parent.mkdir(parents=True, exist_ok=True)

print(f"Testing local FFmpeg: {ffmpeg_bin}")
print("Testing h264_nvenc encoding on NVIDIA GeForce GTX 1650...")

# Generate 5-second test video with NVENC
cmd = [
    ffmpeg_bin, "-y",
    "-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=60",
    "-t", "5",
    "-c:v", "h264_nvenc",
    "-preset", "p5",
    "-b:v", "8M",
    str(test_out)
]

res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
if res.returncode == 0:
    print(f"\n[SUCCESS] GTX 1650 NVENC is WORKING at peak hardware acceleration! (Output: {test_out.name})")
else:
    print(f"\n[ERROR] NVENC returned code {res.returncode}:\n{res.stderr.decode('utf-8', errors='ignore')}")
