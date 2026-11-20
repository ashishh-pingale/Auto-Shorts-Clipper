"""
core_autoclip.renderer
Phase 9 / Core Compositor:
Combines 9:16 Crop, Animated Subtitles (.ass), and Audio Loudness Normalization (-14 LUFS)
into a final production-ready vertical Short using GTX 1650 hardware NVENC.
"""

import subprocess
from pathlib import Path
from typing import Optional
from core_autoclip.downloader import get_ffmpeg_path

class VideoRenderer:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.ffmpeg_bin = get_ffmpeg_path()

    def render_final_short(
        self,
        input_video_path: str,
        subtitle_ass_path: Optional[str] = None,
        crop_data: Optional[dict] = None,
        output_filename: str = "final_short.mp4",
        use_nvenc: bool = True,
        aspect_ratio: str = "Vertical 9:16 (Shorts/TikTok)"
    ) -> str:
        """
        Executes hardware-accelerated composite render:
        1. Aspect ratio handling (Vertical 9:16 crop OR Horizontal 16:9 widescreen)
        2. Burns in animated karaoke subtitles (if provided)
        3. Normalizes audio to YouTube Shorts -14 LUFS standard
        4. Encodes via GTX 1650 NVENC (h264_nvenc) at 60 FPS
        """
        out_path = self.output_dir / output_filename

        # Filter string construction
        filters = []

        is_split = crop_data and crop_data.get("is_split", False)
        sub_working_dir = None
        clean_sub_filter = ""
        if subtitle_ass_path and Path(subtitle_ass_path).is_file():
            sub_p = Path(subtitle_ass_path).resolve()
            sub_working_dir = str(sub_p.parent)
            clean_sub_filter = f",ass={sub_p.name}"

        # Audio loudness normalization for YouTube Shorts standard
        audio_filter = "loudnorm=I=-14:TP=-1.5:LRA=11"
        codec = "h264_nvenc" if use_nvenc else "libx264"
        preset = "p6" if use_nvenc else "medium"

        if is_split:
            cam_crop = crop_data["cam_crop"]
            game_crop = crop_data["game_crop"]
            print(f"[Renderer] Stacking Streamer Split-Screen (Facecam + Gameplay)...")
            filter_str = (
                f"[0:v]{cam_crop},scale=1080:720:flags=lanczos+accurate_rnd[cam];"
                f"[0:v]{game_crop},scale=1080:1200:flags=lanczos+accurate_rnd,unsharp=5:5:0.8:5:5:0.3[game];"
                f"[cam][game]vstack=inputs=2{clean_sub_filter}[v_out]"
            )
            filter_args = ["-filter_complex", filter_str, "-map", "[v_out]", "-map", "0:a?"]
        else:
            # 1. Framing / Aspect Ratio with Lanczos & Gaming Unsharp Filter
            is_horizontal = "Horizontal" in aspect_ratio or "16:9" in aspect_ratio

            # Determine target output resolution
            if "4:5" in aspect_ratio:
                target_out_w, target_out_h = 1080, 1350
            elif "3:4" in aspect_ratio:
                target_out_w, target_out_h = 1080, 1440
            elif is_horizontal:
                target_out_w, target_out_h = 1920, 1080
            else: # Default 9:16
                target_out_w, target_out_h = 1080, 1920

            if is_horizontal:
                filters.append(f"scale={target_out_w}:{target_out_h}:flags=lanczos+accurate_rnd:force_original_aspect_ratio=decrease,pad={target_out_w}:{target_out_h}:(ow-iw)/2:(oh-ih)/2")
            elif crop_data:
                w = crop_data["crop_w"]
                h = crop_data["crop_h"]
                x = crop_data["median_crop_x"]
                filters.append(f"crop={w}:{h}:{x}:0,scale={target_out_w}:{target_out_h}:flags=lanczos+accurate_rnd,unsharp=5:5:0.8:5:5:0.3")
            else:
                filters.append(f"crop=ih*({target_out_w}/{target_out_h}):ih,scale={target_out_w}:{target_out_h}:flags=lanczos+accurate_rnd,unsharp=5:5:0.8:5:5:0.3")

            if subtitle_ass_path and Path(subtitle_ass_path).is_file():
                filters.append(f"ass={sub_p.name}")

            video_filter_chain = ",".join(filters)
            filter_args = ["-vf", video_filter_chain]

        print(f"[Renderer] Exporting high-fidelity short using {codec} NVENC (16 Mbps) -> {out_path.name}...")

        cmd = [
            self.ffmpeg_bin, "-y",
            "-i", str(Path(input_video_path).resolve())
        ] + filter_args + [
            "-af", audio_filter,
            "-c:v", codec,
            "-preset", preset,
            "-b:v", "16M",
            "-maxrate", "24M",
            "-bufsize", "32M",
            "-r", "60",
            "-c:a", "aac",
            "-b:a", "192k",
            str(out_path.resolve())
        ]

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=sub_working_dir)
        if result.returncode != 0:
            err_msg = result.stderr.decode('utf-8', errors='ignore')
            print(f"[Renderer WARNING] NVENC/Filter returned error ({err_msg[:200]}). Retrying with libx264...")
            cmd[8] = "libx264"
            cmd[10] = "fast"
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=sub_working_dir)
            if result.returncode != 0:
                # If ass filter specifically failed, fallback without subtitle filter
                print("[Renderer WARNING] Retrying without subtitle filter...")
                crop_only_filter = f"crop={w}:{h}:{x}:0,scale=1080:1920:flags=lanczos" if crop_data else "crop=ih*(9/16):ih,scale=1080:1920:flags=lanczos"
                cmd[4] = crop_only_filter
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if result.returncode != 0:
                    raise RuntimeError(f"FFmpeg composite render failed: {result.stderr.decode('utf-8', errors='ignore')}")

        print(f"[Renderer] Render complete! Saved: {out_path}")
        return str(out_path)
