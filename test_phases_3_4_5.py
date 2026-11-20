"""
Test script for Phases 3, 4, and 5:
Full Ingestion -> Transcription -> AI Highlight Detection -> Clip Extraction.
Can test with any sample video file or YouTube URL.
"""

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from core_autoclip.downloader import MediaDownloader
from core_autoclip.transcriber import AudioTranscriber
from core_autoclip.highlight_detector import HighlightDetector
from core_autoclip.clip_extractor import ClipExtractor

def run_test(source: str = ""):
    print("=" * 65)
    print("AUTOCLIP PIPELINE TEST: Phases 3, 4, 5")
    print("=" * 65)

    downloader = MediaDownloader()
    transcriber = AudioTranscriber(model_size="small", device="cuda", compute_type="float16")
    detector = HighlightDetector()
    extractor = ClipExtractor(output_dir=PROJECT_ROOT / "temp" / "test_clips")

    # If no source provided, display usage
    if not source:
        print("\n[INFO] Pipeline components loaded successfully!")
        print("To run with a real video or URL:")
        print("  python test_phases_3_4_5.py \"https://www.youtube.com/watch?v=...\"")
        print("  or")
        print("  python test_phases_3_4_5.py \"D:\\path\\to\\video.mp4\"\n")
        return

    # Step 1: Ingestion
    print("\n--- STEP 1: INGESTION ---")
    media = downloader.process_input(source)
    print(f"Video: {media['video_path']}")
    print(f"Audio: {media['audio_path']}")

    # Step 2: Transcription
    print("\n--- STEP 2: TRANSCRIPTION (GTX 1650 CUDA) ---")
    transcript = transcriber.transcribe(media['audio_path'])
    transcriber.unload_model() # Immediate VRAM cleanup

    # Step 3: Highlight Detection
    print("\n--- STEP 3: AI VIRAL HIGHLIGHT DETECTION ---")
    highlights = detector.find_highlights(transcript, min_duration=30, max_duration=60, max_clips=3)

    print(f"\nFound {len(highlights)} Viral Short Candidates:")
    for h in highlights:
        print(f"  * #{h['clip_id']} [{h['start']}s -> {h['end']}s] ({h['duration']}s) - Score: {h['viral_score']}/10")
        print(f"    Title: {h['title']}")
        print(f"    Hook: \"{h['hook']}\"\n")

    # Step 4: Clip Extraction
    print("--- STEP 4: CLIP EXTRACTION ---")
    for h in highlights:
        out_clip = extractor.extract_clip(
            media['video_path'],
            start_time=h['start'],
            end_time=h['end'],
            clip_id=h['clip_id'],
            title=h['title']
        )
        clip_words = extractor.filter_words_for_clip(transcript, h['start'], h['end'])
        print(f"    Words in clip: {len(clip_words)} words synchronized.")

    print("\n" + "=" * 65)
    print("SUCCESS: Pipeline Stages 3, 4, 5 complete!")
    print("=" * 65)

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else ""
    run_test(src)
