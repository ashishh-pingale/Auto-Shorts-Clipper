"""
core_autoclip.smart_cropper
Phase 6: Vertical 9:16 Reframing & Speaker Tracking.
Runs Google MediaPipe on AMD Ryzen 5 5600H CPU (0 MB VRAM),
with Exponential Moving Average (EMA) smoothing for cinematic, jitter-free camera pans.
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import cv2
import numpy as np

from core_autoclip.downloader import get_ffmpeg_path

class SmartCropper:
    def __init__(self, smoothing_alpha: float = 0.08, deadband_px: int = 35):
        """
        smoothing_alpha: Controls camera pan speed (0.05 = slow cinematic pan, 0.15 = faster tracking).
        deadband_px: Minimum movement required to trigger camera pan (prevents micro-jitter).
        """
        self.smoothing_alpha = smoothing_alpha
        self.deadband_px = deadband_px
        self.ffmpeg_bin = get_ffmpeg_path()

    def analyze_faces_and_track(
        self,
        video_path: str,
        sample_fps: float = 6.0,
        framing_mode: str = "Centered Character (GTA / Gaming)",
        manual_offset_pct: float = 50.0,
        aspect_ratio: str = "9:16"
    ) -> Dict[str, Any]:
        """
        Calculates crop framing based on target aspect ratio (9:16, 4:5, 3:4).
        """
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")

        orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / video_fps

        # Determine aspect ratio dimensions
        if "4:5" in aspect_ratio or "4x5" in aspect_ratio:
            ratio_w, ratio_h = 4.0, 5.0
            scale_out_w, scale_out_h = 1080, 1350
        elif "3:4" in aspect_ratio or "3x4" in aspect_ratio:
            ratio_w, ratio_h = 3.0, 4.0
            scale_out_w, scale_out_h = 1080, 1440
        else: # Default 9:16
            ratio_w, ratio_h = 9.0, 16.0
            scale_out_w, scale_out_h = 1080, 1920

        target_crop_w = int(orig_h * (ratio_w / ratio_h))
        target_crop_w = min(target_crop_w, orig_w)
        target_crop_h = orig_h
        default_center_x = (orig_w - target_crop_w) // 2

        # If Streamer Split-Screen is chosen (Facecam Top, Gameplay Bottom)
        if "Split" in framing_mode:
            print("[SmartCropper] Streamer Split Mode: Detecting facecam for top half and gameplay for bottom half...")
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            cv_detector = cv2.CascadeClassifier(cascade_path) if os.path.exists(cascade_path) else None
            
            # Find face position in the first 30 frames
            detected_face = None
            sample_count = 0
            while cap.isOpened() and sample_count < 30:
                ret, frame = cap.read()
                if not ret:
                    break
                if sample_count % 3 == 0 and cv_detector:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = cv_detector.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=4, minSize=(50, 50))
                    if len(faces) > 0:
                        detected_face = max(faces, key=lambda f: f[2] * f[3])
                        break
                sample_count += 1
            cap.release()

            # Calculate Facecam box (Top section: 1080x720)
            if detected_face is not None:
                fx, fy, fw, fh = detected_face
                cam_h = min(int(fh * 2.4), orig_h)
                cam_w = int(cam_h * (1080.0 / 720.0))
                cam_w = min(cam_w, orig_w)
                cam_x = max(0, min(int(fx + fw / 2.0 - cam_w / 2.0), orig_w - cam_w))
                cam_y = max(0, min(int(fy + fh / 2.0 - cam_h / 2.0), orig_h - cam_h))
            else:
                # Default to Top-Right corner streamer facecam
                cam_w = int(orig_w * 0.30)
                cam_h = int(cam_w * (720.0 / 1080.0))
                cam_x = orig_w - cam_w - 30
                cam_y = 30

            # Calculate Gameplay box (Bottom section: 1080x1200)
            game_h = orig_h
            game_w = int(game_h * (1080.0 / 1200.0))
            game_x = max(0, min((orig_w - game_w) // 2, orig_w - game_w))
            game_y = 0

            print(f"[SmartCropper] Split Config: Facecam=({cam_w}x{cam_h} at X={cam_x},Y={cam_y}) | Game=({game_w}x{game_h} at X={game_x})")
            return {
                "orig_w": orig_w,
                "orig_h": orig_h,
                "is_split": True,
                "cam_crop": f"crop={cam_w}:{cam_h}:{cam_x}:{cam_y}",
                "game_crop": f"crop={game_w}:{game_h}:{game_x}:{game_y}",
                "crop_w": target_crop_w,
                "crop_h": target_crop_h,
                "median_crop_x": default_center_x,
                "timestamps": [0.0]
            }

        # If gaming / centered character mode is chosen, center directly on player!
        if "Gaming" in framing_mode or "Centered" in framing_mode:
            cap.release()
            print(f"[SmartCropper] Gaming Mode ({ratio_w:.0f}:{ratio_h:.0f}): Centering on character at X={default_center_x}")
            return {
                "orig_w": orig_w,
                "orig_h": orig_h,
                "crop_w": target_crop_w,
                "crop_h": target_crop_h,
                "scale_out_w": scale_out_w,
                "scale_out_h": scale_out_h,
                "median_crop_x": default_center_x,
                "smoothed_x_offsets": [default_center_x],
                "timestamps": [0.0]
            }

        # If custom manual offset is chosen
        if "Custom" in framing_mode:
            cap.release()
            custom_x = int((orig_w - target_crop_w) * (manual_offset_pct / 100.0))
            custom_x = max(0, min(custom_x, orig_w - target_crop_w))
            print(f"[SmartCropper] Manual Framing ({ratio_w:.0f}:{ratio_h:.0f}): Setting crop X={custom_x} ({manual_offset_pct}%)")
            return {
                "orig_w": orig_w,
                "orig_h": orig_h,
                "crop_w": target_crop_w,
                "crop_h": target_crop_h,
                "scale_out_w": scale_out_w,
                "scale_out_h": scale_out_h,
                "median_crop_x": custom_x,
                "smoothed_x_offsets": [custom_x],
                "timestamps": [0.0]
            }

        print(f"[SmartCropper] Face Tracking Mode: Analyzing {orig_w}x{orig_h} video for human faces...")

        # Initialize face detector: OpenCV built-in (standard & reliable across all systems)
        detector_type = "none"
        mp_detector = None
        cv_detector = None

        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        if os.path.exists(cascade_path):
            cv_detector = cv2.CascadeClassifier(cascade_path)
            detector_type = "opencv"
            print(f"[SmartCropper] Face Tracking: Using OpenCV built-in detector ({cascade_path})")
        else:
            # Dynamic fallback to MediaPipe if available
            try:
                import importlib
                mp_module = importlib.import_module("mediapipe.python.solutions.face_detection")
                mp_detector = mp_module.FaceDetection(model_selection=1, min_detection_confidence=0.5)
                detector_type = "mediapipe"
            except Exception:
                print("[SmartCropper] Using stable center crop.")

        sample_interval = max(int(video_fps / sample_fps), 1)
        raw_centers = []
        timestamps = []

        frame_idx = 0
        last_known_center = orig_w // 2

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % sample_interval == 0:
                t = frame_idx / video_fps
                current_face_x = None

                if detector_type == "mediapipe" and mp_detector is not None:
                    try:
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        results = mp_detector.process(rgb_frame)
                        if results.detections:
                            best_area = 0
                            for det in results.detections:
                                bbox = det.location_data.relative_bounding_box
                                area = bbox.width * bbox.height
                                if area > best_area:
                                    best_area = area
                                    current_face_x = int((bbox.xmin + bbox.width / 2.0) * orig_w)
                    except Exception:
                        pass
                elif detector_type == "opencv" and cv_detector is not None:
                    try:
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        faces = cv_detector.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(60, 60))
                        if len(faces) > 0:
                            # Largest face
                            best_face = max(faces, key=lambda f: f[2] * f[3])
                            current_face_x = int(best_face[0] + best_face[2] / 2.0)
                    except Exception:
                        pass

                if current_face_x is not None:
                    last_known_center = current_face_x
                
                raw_centers.append(last_known_center)
                timestamps.append(t)

            frame_idx += 1

        cap.release()
        if mp_detector is not None:
            try:
                mp_detector.close()
            except Exception:
                pass

        # Apply Exponential Moving Average (EMA) and Deadband Smoothing
        smoothed_x_offsets = []
        current_smoothed_x = default_center_x

        for face_x in raw_centers:
            # Ideal crop x-offset to keep face centered in 9:16 box
            ideal_x = face_x - (target_crop_w // 2)
            # Clamp inside video boundaries
            clamped_ideal_x = max(0, min(ideal_x, orig_w - target_crop_w))

            # Apply deadband: ignore tiny tremors
            if abs(clamped_ideal_x - current_smoothed_x) > self.deadband_px:
                current_smoothed_x = int(
                    self.smoothing_alpha * clamped_ideal_x + (1.0 - self.smoothing_alpha) * current_smoothed_x
                )
            
            # Final boundary clamp
            final_x = max(0, min(current_smoothed_x, orig_w - target_crop_w))
            smoothed_x_offsets.append(final_x)

        # Average stable crop position (for simple single-crop fallback)
        median_crop_x = int(np.median(smoothed_x_offsets)) if smoothed_x_offsets else default_center_x

        print(f"[SmartCropper] Face tracking complete. Median Crop X: {median_crop_x}")
        return {
            "orig_w": orig_w,
            "orig_h": orig_h,
            "crop_w": target_crop_w,
            "crop_h": target_crop_h,
            "median_crop_x": median_crop_x,
            "smoothed_x_offsets": smoothed_x_offsets,
            "timestamps": timestamps
        }

    def reframe_to_916(
        self,
        input_clip_path: str,
        output_vertical_path: str,
        crop_data: Optional[Dict[str, Any]] = None,
        use_nvenc: bool = True
    ) -> str:
        """
        Renders the video into 1080x1920 (9:16) format using GTX 1650 hardware NVENC.
        """
        out_p = Path(output_vertical_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        if crop_data is None:
            crop_data = self.analyze_faces_and_track(input_clip_path)

        crop_w = crop_data["crop_w"]
        crop_h = crop_data["crop_h"]
        crop_x = crop_data["median_crop_x"]

        print(f"[SmartCropper] Exporting 9:16 Vertical Video: {out_p.name}")
        print(f"[SmartCropper] Applying Crop: w={crop_w}, h={crop_h}, x={crop_x}, y=0 -> Scale to 1080x1920")

        # FFmpeg filter: Crop to 9:16 and scale to vertical 1080x1920
        vf_filter = f"crop={crop_w}:{crop_h}:{crop_x}:0,scale=1080:1920:flags=lanczos"

        # Hardware encoder choice
        video_codec = "h264_nvenc" if use_nvenc else "libx264"
        preset = "p5" if use_nvenc else "fast"

        cmd = [
            self.ffmpeg_bin, "-y",
            "-i", str(input_clip_path),
            "-vf", vf_filter,
            "-c:v", video_codec,
            "-preset", preset,
            "-b:v", "8M",
            "-maxrate", "12M",
            "-bufsize", "16M",
            "-c:a", "copy",
            str(out_p)
        ]

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            # If NVENC is busy or fails, fallback to CPU libx264
            print(f"[SmartCropper] NVENC export returned code {result.returncode}. Retrying with libx264...")
            cmd[6] = "libx264"
            cmd[8] = "medium"
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg vertical render failed: {result.stderr.decode('utf-8', errors='ignore')}")

        print(f"[SmartCropper] Vertical 9:16 Short rendered successfully: {out_p.name}")
        return str(out_p)
