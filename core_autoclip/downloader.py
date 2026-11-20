"""
core_autoclip.downloader
Handles video downloading via yt-dlp and audio extraction using local FFmpeg.
Stores all media in D:\\Ai Softwares\\Auto Shorts Clipper\\temp\\ (0 bytes on C: drive).
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMP_DIR = PROJECT_ROOT / "temp"

def get_ffmpeg_path() -> str:
    """Finds the local portable FFmpeg installed in the project."""
    # Check project directories
    candidates = [
        PROJECT_ROOT / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe",
        PROJECT_ROOT / "ffmpeg" / "bin" / "ffmpeg.exe",
    ]
    # Check any extracted folder matching ffmpeg-*
    for extracted in PROJECT_ROOT.glob("ffmpeg*"):
        candidates.append(extracted / "bin" / "ffmpeg.exe")
        for nested in extracted.glob("ffmpeg*"):
            candidates.append(nested / "bin" / "ffmpeg.exe")

    for c in candidates:
        if c.is_file():
            return str(c)

    # Fallback to system PATH
    return "ffmpeg"

class MediaDownloader:
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or TEMP_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.ffmpeg_bin = get_ffmpeg_path()

    def process_input(self, source: str, target_resolution: str = "1440p") -> Dict[str, str]:
        """
        Accepts either a YouTube URL or a local video file path.
        Returns a dict with paths to the video file and extracted 16kHz mono audio.
        """
        if source.startswith(("http://", "https://", "www.")):
            return self.download_youtube(source, target_resolution=target_resolution)
        else:
            return self.process_local_file(source)

    def download_youtube(self, url: str, target_resolution: str = "1440p") -> Dict[str, str]:
        """Downloads best video (up to 1440p, 1080p, or 4K) + best audio merged with yt-dlp."""
        import yt_dlp

        # Determine target height limit
        if "2160" in target_resolution or "4K" in target_resolution:
            h_limit = 2160
            quality_tag = "4k"
        elif "1080" in target_resolution:
            h_limit = 1080
            quality_tag = "1080p"
        else:
            h_limit = 1440
            quality_tag = "1440p"

        print(f"[Downloader] Downloading YouTube video at {quality_tag} (max {h_limit}p) from: {url}")
        out_template = str(self.output_dir / f"%(id)s_{quality_tag}_%(title).50s.%(ext)s")

        ydl_opts = {
            'format': f'bestvideo[height<={h_limit}][ext=mp4]+bestaudio[ext=m4a]/best[height<={h_limit}][ext=mp4]/best[height<={h_limit}]/best',
            'outtmpl': out_template,
            'merge_output_format': 'mp4',
            'ffmpeg_location': self.ffmpeg_bin,
            'quiet': False,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # First extract metadata to check duration
            info = ydl.extract_info(url, download=False)
            duration = info.get("duration", 0) or 0
            video_id = info.get("id", "")
            
            if duration:
                print(f"[Downloader] Video duration: {duration/3600:.1f} hours ({duration/60:.0f} mins) - Unlimited download mode active.")

            # Check if video was already downloaded in temp/
            if video_id:
                existing_matches = list(self.output_dir.glob(f"{video_id}_*.mp4"))
                if existing_matches and existing_matches[0].stat().st_size > 500000:
                    print(f"[Downloader] Reusing already downloaded video: {existing_matches[0].name}")
                    video_path = str(existing_matches[0])
                    audio_path = self.extract_audio(video_path)
                    return {
                        "title": info.get("title", "YouTube Video"),
                        "video_path": video_path,
                        "audio_path": audio_path
                    }

            # Proceed with download if not cached
            info = ydl.extract_info(url, download=True)
            video_path = ydl.prepare_filename(info)
            if not video_path.endswith('.mp4'):
                video_path = os.path.splitext(video_path)[0] + '.mp4'

        audio_path = self.extract_audio(video_path)
        return {
            "title": info.get("title", "YouTube Video"),
            "video_path": video_path,
            "audio_path": audio_path
        }

    def process_local_file(self, local_path: str) -> Dict[str, str]:
        """Validates local file and extracts its 16kHz mono audio."""
        path = Path(local_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Local video file not found: {local_path}")

        print(f"[Downloader] Using local video: {path.name}")
        audio_path = self.extract_audio(str(path))
        return {
            "title": path.stem,
            "video_path": str(path),
            "audio_path": audio_path
        }

    def extract_audio(self, video_path: str) -> str:
        """
        Extracts 16kHz 16-bit mono WAV audio (optimal format for faster-whisper).
        """
        video_p = Path(video_path)
        audio_p = self.output_dir / f"{video_p.stem}_audio16k.wav"

        if audio_p.is_file() and audio_p.stat().st_size > 0:
            print(f"[Downloader] Cached audio found: {audio_p.name}")
            return str(audio_p)

        print(f"[Downloader] Extracting 16kHz mono audio using FFmpeg...")
        cmd = [
            self.ffmpeg_bin, "-y",
            "-i", str(video_path),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            str(audio_p)
        ]

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg audio extraction failed: {result.stderr.decode('utf-8', errors='ignore')}")

        print(f"[Downloader] Audio ready: {audio_p.name}")
        return str(audio_p)
