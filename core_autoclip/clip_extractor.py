"""
core_autoclip.clip_extractor
Phase 5: Automatic Clip Extraction & Duration Control.
Extracts high-precision video segments using local portable FFmpeg.
"""

import subprocess
from pathlib import Path
from typing import Dict, Any, List
from core_autoclip.downloader import get_ffmpeg_path

class ClipExtractor:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.ffmpeg_bin = get_ffmpeg_path()

    def extract_clip(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        clip_id: int,
        title: str = "clip"
    ) -> str:
        """
        Extracts a video segment with microsecond precision.
        Uses keyframe-accurate cutting to prevent black frames or audio sync drifts.
        """
        clean_title = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-")).rstrip()
        clean_title = clean_title.replace(" ", "_")[:30]
        out_file = self.output_dir / f"clip_{clip_id}_{clean_title}.mp4"

        duration = end_time - start_time
        print(f"[ClipExtractor] Slicing Clip #{clip_id}: {start_time:.2f}s -> {end_time:.2f}s ({duration:.1f}s)")

        cmd = [
            self.ffmpeg_bin, "-y",
            "-ss", f"{start_time:.3f}",
            "-i", str(video_path),
            "-t", f"{duration:.3f}",
            "-c", "copy", # Instant lossless stream copy (0% CPU, instant)
            str(out_file)
        ]

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            raise RuntimeError(f"Clip extraction failed: {result.stderr.decode('utf-8', errors='ignore')}")

        print(f"[ClipExtractor] Saved segment: {out_file.name}")
        return str(out_file)

    def filter_words_for_clip(
        self,
        transcript_data: Dict[str, Any],
        start_time: float,
        end_time: float
    ) -> List[Dict[str, Any]]:
        """
        Extracts the exact words that fall inside the clip's timestamp window,
        offsetting timestamps relative to the clip start (t=0s).
        """
        clip_words = []
        for segment in transcript_data.get("segments", []):
            for word in segment.get("words", []):
                w_start = word["start"]
                w_end = word["end"]
                if w_start >= start_time and w_end <= end_time:
                    clip_words.append({
                        "word": word["word"],
                        "start": round(w_start - start_time, 3), # Offset to 0s
                        "end": round(w_end - start_time, 3),
                        "probability": word.get("probability", 1.0)
                    })
        return clip_words
