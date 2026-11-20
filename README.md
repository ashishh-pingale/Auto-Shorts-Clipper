# 🎬 Auto Shorts Clipper

> **High-Performance, AI-Powered YouTube & Video to Shorts / Reels / TikTok Pipeline.**  
> Optimized for fast, isolated execution with hardware NVENC 60fps export and smart VRAM management (runs smoothly on 4GB VRAM cards like the GTX 1650, while scaling up to RTX 3060/4080/4090).

---

## 🚀 Key Features

* **✂️ Dual Clipping Strategies:**
  * **🔥 AI Viral Highlights:** Uses semantic heuristics & hook scoring to extract the most engaging 30s–60s moments from podcasts, gameplays, and streams.
  * **📦 Episodic Series Slicer:** Slices 10–30 minute VODs into consecutive sequential episodes (**Part 1, Part 2, Part 3...**) snapping cleanly to natural sentence/speech boundaries without cutting off words mid-sentence.
* **🧠 Faster-Whisper with Turbo Mode:**
  * Supports models from `tiny` (~400MB VRAM) to `small` (~850MB VRAM) and `turbo`/`large-v3` (~3.5GB VRAM).
  * Hindi & Devanagari optimization with `Nirmala UI` font and automatic orphan matra fixing (zero dotted circles).
  * Greedy search decoding (`beam_size=1`) and hallucination suppression for 6× real-time transcription.
* **🎮 Smart Dynamic Framing:**
  * **Centered Character (GTA / Gaming):** Centers the in-game protagonist without needing face detection.
  * **🎙️ Streamer Split-Screen:** Stacks facecam on top and gameplay on bottom for reactions and live streams.
  * **Auto Face Tracking & Custom Horizontal Sliders.**
* **📐 Multi-Aspect Ratio Export:**
  * `9:16` (Vertical Shorts / Reels / TikTok)
  * `4:5` (Instagram Feed & Reels — 30% wider and noticeably sharper)
  * `3:4` (Balanced Portrait)
  * `16:9` (Widescreen Clips)
* **⚡ Hardware NVENC 60fps Encoding:**
  * Real-time GPU export at 16 Mbps bitrate with Lanczos resampling and gaming unsharp filters.
  * Renders a 60s short in just **15 to 30 seconds**.
* **⚡ One-Click Batch Rendering:** Render all detected clips or parts in sequence automatically.
* **💾 Zero C-Drive Bloat:** All virtual environments, Hugging Face models, temporary caches, and renders stay 100% isolated inside this folder.

---

## 🛠️ GPU VRAM & Hardware Guide

| Whisper Model | VRAM Required | Recommended GPU |
| :--- | :--- | :--- |
| **`tiny` / `base`** | ~400 MB – 500 MB | Any Intel Iris Xe, AMD Radeon iGPU, or budget GPU |
| **`small`** *(Default)* | ~850 MB | **NVIDIA GTX 1650 (4GB)**, GTX 1060, RTX 2050/3050 |
| **`medium`** | ~1.8 GB – 2.0 GB | NVIDIA RTX 3050 / 3060 (6GB) |
| **`turbo` (large-v3)** | ~1.6 GB – 2.2 GB | NVIDIA RTX 3060, 4060, 4070 |
| **`large-v3`** | ~3.2 GB – 3.8 GB | NVIDIA RTX 3070, 3080, 4080, 4090 (8GB+ VRAM) |

---

## 📥 Quick Start (Windows)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/auto-shorts-clipper.git
   cd auto-shorts-clipper
   ```
2. **Run the automated setup:**
   * Double-click `create_venv.bat` to create the isolated Python 3.11 environment.
   * Double-click `enable_gpu_cuda.bat` to install CUDA 12 and cuDNN acceleration.
3. **Launch the Web UI:**
   * Double-click `run.bat`
   * Open your browser at `http://127.0.0.1:7860`

---

## 📂 Project Architecture

```text
Auto Shorts Clipper/
├── .venv/                     # Fully isolated Python virtual environment
├── cache/                     # Hugging Face & Faster-Whisper model weights
├── temp/                      # Cached video downloads & 16kHz audio
├── outputs/                   # Rendered 60fps final Shorts
├── core_autoclip/
│   ├── downloader.py          # yt-dlp 1440p/2K/4K ingestion & mono extraction
│   ├── transcriber.py         # Faster-Whisper CUDA engine with live streaming logs
│   ├── highlight_detector.py  # Viral hook heuristics & Episodic Series Slicer
│   ├── clip_extractor.py      # Stream copy lossless slicing
│   ├── smart_cropper.py       # Centered GTA character & Facecam Split-Screen
│   ├── subtitle_generator.py  # Animated karaoke ASS captions (Nirmala UI)
│   └── renderer.py            # Hardware NVENC 60fps render engine
├── app.py                     # Modern Gradio Web Dashboard
├── run.bat                    # One-click app launcher
└── stop_all.bat               # Emergency process cleanup
```
