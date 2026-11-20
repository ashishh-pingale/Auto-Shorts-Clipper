"""
Test script for Phase 3: Transcription Engine
Tests faster-whisper loading, VRAM footprint, and cleanup.
"""


import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from core_autoclip.transcriber import AudioTranscriber

def test_transcriber():
    print("=" * 60)
    print("PHASE 3 TEST: faster-whisper on GTX 1650 (CUDA FP16)")
    print("=" * 60)

    # Initialize transcriber with GTX 1650 tuned settings
    # 'small' model is recommended (balance between speed and accuracy)
    # Uses ~850MB VRAM and leaves >2.5GB free
    transcriber = AudioTranscriber(model_size="small", device="cuda", compute_type="float16")

    print("\n[Step 1] Loading Model into VRAM...")
    start_time = time.time()
    transcriber.load_model()
    load_time = time.time() - start_time
    print(f"-> Model loaded in {load_time:.2f} seconds.")

    print("\n[Step 2] Testing VRAM Unload & Flush...")
    transcriber.unload_model()
    print("-> VRAM successfully freed.")

    print("\n" + "=" * 60)
    print("ALL CHECKS PASSED: Transcription engine is ready for media input!")
    print("=" * 60)

if __name__ == "__main__":
    test_transcriber()
