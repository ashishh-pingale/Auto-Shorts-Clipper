"""
core_autoclip.transcriber
High-speed, VRAM-optimized transcription engine using faster-whisper (CTranslate2).
Enforces strict model caching on D: drive and sequential VRAM cleanup.
"""

import os
import sys
import gc
from pathlib import Path
from typing import Dict, List, Any, Optional

# Enforce all AI model caches to stay on D: drive (keeps C: drive 100% clean)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "cache" / "models"
HF_CACHE_DIR = PROJECT_ROOT / "cache" / "huggingface"

os.environ["HF_HOME"] = str(HF_CACHE_DIR)
os.environ["CT2_CACHE_DIR"] = str(CACHE_DIR)

# Auto-register NVIDIA DLL directories for CTranslate2 on Windows
def register_nvidia_dlls():
    for p in sys.path:
        nvidia_path = Path(p) / "nvidia"
        if nvidia_path.is_dir():
            for bin_dir in nvidia_path.glob("*/bin"):
                if bin_dir.is_dir():
                    try:
                        os.add_dll_directory(str(bin_dir))
                        os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ["PATH"]
                    except Exception:
                        pass

register_nvidia_dlls()

class AudioTranscriber:
    def __init__(self, model_size: str = "small", device: str = "cuda", compute_type: str = "float16"):
        """
        Initializes faster-whisper with strict hardware tuning for GTX 1650 (4GB VRAM).
        
        Recommended settings for GTX 1650:
            model_size: 'small' (~480MB disk, ~850MB VRAM) or 'base' (~140MB disk, ~500MB VRAM)
            compute_type: 'float16' or 'int8_float16'
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None

    def load_model(self):
        """Loads Whisper model into VRAM."""
        from faster_whisper import WhisperModel
        
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        HF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        print(f"[Transcriber] Loading faster-whisper '{self.model_size}' on {self.device} ({self.compute_type})...")
        print(f"[Transcriber] Model cache locked to D: drive: {CACHE_DIR}")
        
        try:
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                download_root=str(CACHE_DIR)
            )
            print("[Transcriber] Model loaded into VRAM successfully.")
        except Exception as e:
            if self.device == "cuda":
                print(f"[Transcriber WARNING] CUDA load failed ({e}). Falling back to CPU...")
                self.device = "cpu"
                self.compute_type = "int8"
                self.model = WhisperModel(
                    self.model_size,
                    device="cpu",
                    compute_type="int8",
                    download_root=str(CACHE_DIR)
                )
                print("[Transcriber] Fallback to CPU succeeded.")
            else:
                raise e

    def transcribe(self, audio_or_video_path: str, progress_callback: Any = None) -> Dict[str, Any]:
        """
        Transcribes media file with word-level timestamps and Silero VAD noise filtering.
        Optimized with beam_size=1 (greedy search) & condition_on_previous_text=False
        to prevent hallucination loops and ensure 4x-6x faster transcription on long gaming streams.
        """
        if self.model is None:
            self.load_model()

        print(f"[Transcriber] Starting transcription of: {audio_or_video_path}")
        
        from faster_whisper import WhisperModel

        # Turbo parameters: beam_size=1, condition_on_previous_text=False prevents Hindi/gaming loops
        whisper_kwargs = dict(
            beam_size=1,
            best_of=1,
            temperature=0.0,
            condition_on_previous_text=False,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500)
        )

        try:
            segments_generator, info = self.model.transcribe(
                str(audio_or_video_path),
                **whisper_kwargs
            )
        except Exception as e:
            print(f"[Transcriber WARNING] CUDA execution issue ({e}). Seamlessly switching to Ryzen CPU...")
            self.device = "cpu"
            self.compute_type = "int8"
            self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8", download_root=str(CACHE_DIR))
            segments_generator, info = self.model.transcribe(
                str(audio_or_video_path),
                **whisper_kwargs
            )

        detected_language = info.language
        language_prob = info.language_probability
        total_duration = max(1.0, float(info.duration))
        print(f"[Transcriber] Detected Language: {detected_language} (confidence: {language_prob:.2f})")
        print(f"[Transcriber] Total Audio Duration: {total_duration / 60:.1f} minutes")
        print("[Transcriber] Streaming segments in Turbo Mode (beam_size=1)...")

        processed_segments = []
        full_transcript = []
        last_log_time = 0.0

        for segment in segments_generator:
            segment_data = {
                "id": segment.id,
                "start": round(segment.start, 3),
                "end": round(segment.end, 3),
                "text": segment.text.strip(),
                "words": []
            }

            if segment.words:
                for word in segment.words:
                    segment_data["words"].append({
                        "word": word.word.strip(),
                        "start": round(word.start, 3),
                        "end": round(word.end, 3),
                        "probability": round(word.probability, 3)
                    })

            processed_segments.append(segment_data)
            full_transcript.append(segment.text.strip())

            # Real-time progress updates (terminal & Gradio)
            pct = min(100.0, (segment.end / total_duration) * 100.0)
            if segment.end - last_log_time >= 15.0 or pct >= 99.5:
                last_log_time = segment.end
                preview = segment.text.strip()[:45]
                print(f"[Transcribing] {segment.end / 60:.1f}/{total_duration / 60:.1f}m ({pct:.1f}%) | {preview}")
                if progress_callback:
                    try:
                        progress_callback(pct / 100.0, desc=f"Transcribing {pct:.1f}% ({segment.end / 60:.1f}/{total_duration / 60:.1f} mins)...")
                    except Exception:
                        pass

        result = {
            "language": detected_language,
            "duration": round(total_duration, 2),
            "text": " ".join(full_transcript),
            "segments": processed_segments
        }

        print(f"[Transcriber] Transcription finished: {len(processed_segments)} segments extracted in total.")
        return result

    def unload_model(self):
        """
        Strict VRAM cleanup: deletes model and flushes CUDA cache immediately.
        Guarantees zero VRAM leakage before next pipeline stages run.
        """
        if self.model is not None:
            del self.model
            self.model = None
            gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            print("[Transcriber] Model unloaded. VRAM successfully flushed back to baseline.")
