"""
core_autoclip.downloader
Handles video downloading via yt-dlp, codec detection, hardware NVENC transcoding,
and audio extraction using local FFmpeg.
Stores all media in D:\\Ai Softwares\\Auto Shorts Clipper\\temp\\ ().
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
    candidates = [
        PROJECT_ROOT / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe",
        PROJECT_ROOT / "ffmpeg" / "bin" / "ffmpeg.exe",
    ]
    for extracted in PROJECT_ROOT.glob("ffmpeg*"):
        candidates.append(extracted / "bin" / "ffmpeg.exe")
        for nested in extracted.glob("ffmpeg*"):
            candidates.append(nested / "bin" / "ffmpeg.exe")

    for c in candidates:
        if c.is_file():
            return str(c)

    return "ffmpeg"

def get_ffprobe_path() -> str:
    """Finds the local portable FFprobe installed in the project."""
    candidates = [
        PROJECT_ROOT / "tools" / "ffmpeg" / "bin" / "ffprobe.exe",
        PROJECT_ROOT / "ffmpeg" / "bin" / "ffprobe.exe",
    ]
    for extracted in PROJECT_ROOT.glob("ffmpeg*"):
        candidates.append(extracted / "bin" / "ffprobe.exe")
        for nested in extracted.glob("ffmpeg*"):
            candidates.append(nested / "bin" / "ffprobe.exe")

    for c in candidates:
        if c.is_file():
            return str(c)

    return "ffprobe"

def detect_video_codec(video_path: str, ffprobe_bin: Optional[str] = None) -> str:
    """Uses ffprobe to detect the exact video stream codec (e.g. h264, hevc, av1, vp9)."""
    bin_path = ffprobe_bin or get_ffprobe_path()
    try:
        cmd = [
            bin_path,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
        codec = res.stdout.strip().lower()
        return codec if codec else "unknown"
    except Exception as e:
        print(f"[Downloader] Warning: ffprobe codec check failed: {e}")
        return "unknown"

class MediaDownloader:
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or TEMP_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.ffmpeg_bin = get_ffmpeg_path()
        self.ffprobe_bin = get_ffprobe_path()

    def process_input(self, source: str, target_resolution: str = "1440p", target_codec: str = "h264") -> Dict[str, str]:
        """
        Accepts either a YouTube URL or a local video file path.
        Returns a dict with paths to the video file and extracted 16kHz mono audio.
        """
        if source.startswith(("http://", "https://", "www.")):
            return self.download_youtube(source, target_resolution=target_resolution, target_codec=target_codec)
        else:
            return self.process_local_file(source, target_codec=target_codec)

    def download_youtube(self, url: str, target_resolution: str = "1440p", target_codec: str = "h264") -> Dict[str, str]:
        """Downloads best video (up to 1440p, 1080p, or 4K) + best audio merged with yt-dlp, and ensures NLE codec compatibility."""
        import yt_dlp

        # Normalize target codec tag
        codec_lower = target_codec.lower()
        if "hevc" in codec_lower or "h.265" in codec_lower or "h265" in codec_lower:
            desired_codec = "hevc"
        elif "native" in codec_lower or "av1" in codec_lower or "vp9" in codec_lower:
            desired_codec = "native"
        else:
            desired_codec = "h264"

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

        print(f"[Downloader] Downloading YouTube video at {quality_tag} (max {h_limit}p, desired codec: {desired_codec}) from: {url}")
        out_template = str(self.output_dir / f"%(id)s_{quality_tag}_%(title).50s.%(ext)s")

        # Format selector: if 1080p and H.264 requested, prefer native AVC stream
        if desired_codec == "h264" and h_limit <= 1080:
            format_selector = (
                f'bestvideo[height<={h_limit}][vcodec^=avc]+bestaudio[ext=m4a]/'
                f'bestvideo[height<={h_limit}][ext=mp4]+bestaudio[ext=m4a]/'
                f'best[height<={h_limit}][ext=mp4]/best'
            )
        else:
            format_selector = (
                f'bestvideo[height<={h_limit}][ext=mp4]+bestaudio[ext=m4a]/'
                f'bestvideo[height<={h_limit}]+bestaudio/'
                f'best[height<={h_limit}][ext=mp4]/best'
            )

        ydl_opts = {
            'format': format_selector,
            'outtmpl': out_template,
            'merge_output_format': 'mp4',
            'ffmpeg_location': self.ffmpeg_bin,
            'quiet': False,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # First extract metadata to check duration and video ID
            info = ydl.extract_info(url, download=False)
            duration = info.get("duration", 0) or 0
            video_id = info.get("id", "")

            if duration:
                print(f"[Downloader] Video duration: {duration/3600:.1f} hours ({duration/60:.0f} mins).")

            # Check if video was already downloaded and transcoded in temp/
            if video_id:
                # Check for already-transcoded file
                if desired_codec in ("h264", "hevc"):
                    transcoded_matches = list(self.output_dir.glob(f"{video_id}_*{desired_codec}*.mp4"))
                    if transcoded_matches and transcoded_matches[0].stat().st_size > 500000:
                        print(f"[Downloader] Reusing cached {desired_codec.upper()} video: {transcoded_matches[0].name}")
                        video_path = str(transcoded_matches[0])
                        audio_path = self.extract_audio(video_path)
                        return {
                            "title": info.get("title", "YouTube Video"),
                            "video_path": video_path,
                            "audio_path": audio_path
                        }

                # Check for existing raw download
                existing_matches = list(self.output_dir.glob(f"{video_id}_*.mp4"))
                if existing_matches and existing_matches[0].stat().st_size > 500000:
                    raw_video_path = str(existing_matches[0])
                    print(f"[Downloader] Reusing already downloaded video: {existing_matches[0].name}")
                    video_path = self._ensure_target_codec(raw_video_path, desired_codec)
                    audio_path = self.extract_audio(video_path)
                    return {
                        "title": info.get("title", "YouTube Video"),
                        "video_path": video_path,
                        "audio_path": audio_path
                    }

            # Download video
            info = ydl.extract_info(url, download=True)
            raw_video_path = ydl.prepare_filename(info)
            if not raw_video_path.endswith('.mp4'):
                raw_video_path = os.path.splitext(raw_video_path)[0] + '.mp4'

        video_path = self._ensure_target_codec(raw_video_path, desired_codec)
        audio_path = self.extract_audio(video_path)
        return {
            "title": info.get("title", "YouTube Video"),
            "video_path": video_path,
            "audio_path": audio_path
        }

    def process_local_file(self, local_path: str, target_codec: str = "h264") -> Dict[str, str]:
        """Validates local file, verifies/transcodes codec if needed, and extracts its 16kHz mono audio."""
        path = Path(local_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Local video file not found: {local_path}")

        print(f"[Downloader] Using local video: {path.name}")
        codec_lower = target_codec.lower()
        desired_codec = "native" if "native" in codec_lower else ("hevc" if "hevc" in codec_lower else "h264")

        video_path = self._ensure_target_codec(str(path), desired_codec)
        audio_path = self.extract_audio(video_path)
        return {
            "title": path.stem,
            "video_path": video_path,
            "audio_path": audio_path
        }

    def _ensure_target_codec(self, video_path: str, desired_codec: str) -> str:
        """
        Detects video codec. If the user requested H.264 or HEVC and the stream is AV1/VP9,
        transcodes using hardware NVENC on NVIDIA GTX 1650 for flawless editing in DaVinci Resolve & Premiere Pro.
        """
        if desired_codec == "native":
            return video_path

        current_codec = detect_video_codec(video_path, self.ffprobe_bin)
        print(f"[Downloader] Detected stream codec: '{current_codec}' (Target: '{desired_codec}')")

        # If already matching target codec, keep as is
        if desired_codec == "h264" and current_codec in ("h264", "avc1"):
            print(f"[Downloader] Video is already H.264/AVC. Ready for DaVinci Resolve & Premiere Pro.")
            return video_path
        if desired_codec == "hevc" and current_codec in ("hevc", "h265", "hev1"):
            print(f"[Downloader] Video is already HEVC/H.265.")
            return video_path

        # Codec mismatch (e.g. av01/vp9 when h264 requested)
        video_p = Path(video_path)
        out_p = self.output_dir / f"{video_p.stem}_{desired_codec}.mp4"

        if out_p.is_file() and out_p.stat().st_size > 500000:
            print(f"[Downloader] Found cached transcoded {desired_codec.upper()} video: {out_p.name}")
            return str(out_p)

        print(f"[Downloader] Video stream is {current_codec.upper()}. Transcoding to {desired_codec.upper()} via NVIDIA GTX 1650 NVENC...")

        nvenc_encoder = "h264_nvenc" if desired_codec == "h264" else "hevc_nvenc"
        fallback_encoder = "libx264" if desired_codec == "h264" else "libx265"
        bitrate = "20M" if desired_codec == "h264" else "16M"

        # Hardware NVENC Transcode Command
        cmd_nvenc = [
            self.ffmpeg_bin, "-y",
            "-hwaccel", "cuda",
            "-i", str(video_path),
            "-c:v", nvenc_encoder,
            "-preset", "p4",
            "-b:v", bitrate,
            "-c:a", "copy",
            str(out_p)
        ]

        print(f"[Downloader] Running NVENC hardware transcode (120+ FPS)...")
        res = subprocess.run(cmd_nvenc, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if res.returncode == 0 and out_p.is_file() and out_p.stat().st_size > 0:
            print(f"[Downloader] Transcode successful: {out_p.name} ({desired_codec.upper()} NLE-ready)")
            return str(out_p)

        # Fallback to CPU encoding if NVENC fails
        print(f"[Downloader] NVENC transcode notice: falling back to CPU {fallback_encoder}...")
        cmd_cpu = [
            self.ffmpeg_bin, "-y",
            "-i", str(video_path),
            "-c:v", fallback_encoder,
            "-crf", "18",
            "-preset", "fast",
            "-c:a", "copy",
            str(out_p)
        ]
        res_cpu = subprocess.run(cmd_cpu, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res_cpu.returncode == 0 and out_p.is_file() and out_p.stat().st_size > 0:
            print(f"[Downloader] CPU transcode successful: {out_p.name}")
            return str(out_p)

        print(f"[Downloader] Warning: transcode failed, falling back to original file.")
        return video_path

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
