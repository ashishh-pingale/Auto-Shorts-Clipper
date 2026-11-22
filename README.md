# ⚡ AutoClipper

> **High-Performance, AI-Powered YouTube & Video to Shorts / Reels / TikTok Pipeline.**  
> Optimized for fast, isolated execution with hardware NVENC 60fps export and smart VRAM management (runs smoothly on 4GB VRAM cards like the GTX 1650, while scaling up to RTX 3060/4080/4090).

---

## 🚀 Key Features

* **✂️ Flexible Clipping Strategies:**
  * **🔥 AI Viral Highlights:** Uses semantic heuristics & hook scoring to extract the most engaging 30s–60s moments from podcasts, gameplays, and streams.
  * **⏱️ Episodic Slicing by Duration:** Cuts full VODs into consecutive sequential episodes of a target length (e.g. 60s, 90s each) snapping cleanly to natural sentence/speech boundaries without cutting off words mid-sentence.
  * **🔢 Episodic Slicing by Count:** Divides any video into an exact number of equal parts (e.g. split a 15-minute VOD into exactly 5 equal parts: Part 1/5 through Part 5/5) with seamless speech boundary snapping.
* **🎬 Universal NLE Codec Compatibility:**
  * Option to ingest in **Universal H.264** or **HEVC (H.265)**.
  * Resolves the dreaded DaVinci Resolve Free / Premiere Pro AV1 "Media Offline" bug via high-speed (120+ FPS) hardware NVENC transcoding.
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
   git clone https://github.com/ashishh-pingale/Auto-Shorts-Clipper.git
   cd Auto-Shorts-Clipper
   ```
2. **Run Step 1 (One-Click Setup):**
   * Double-click **`1_install_setup.bat`**  
     *(Automatically detects Python, creates `.venv`, installs `requirements.txt`, and configures NVIDIA CUDA 12 / cuDNN acceleration).*
3. **Run Step 2 (Optional Diagnostic):**
   * Double-click **`2_test_gpu_nvenc.bat`** to confirm your GPU and hardware NVENC 60fps encoding are operational.
4. **Run Step 3 (Launch the Dashboard):**
   * Double-click **`3_run_app.bat`** (or **`run.bat`**)
   * Open your browser at `http://127.0.0.1:7860`

---

## 📂 Project Architecture

```text
Auto-Shorts-Clipper/
├── 1_install_setup.bat        # Step 1: Automated environment & CUDA setup
├── 2_test_gpu_nvenc.bat       # Step 2: GPU diagnostic test
├── 3_run_app.bat              # Step 3: Launch Web UI dashboard
├── requirements.txt           # Declared project dependencies
├── run.bat                    # Direct launch script
├── stop_all.bat               # Clean task & process killer
├── core_autoclip/
│   ├── downloader.py          # yt-dlp 1440p/2K/4K ingestion, codec checking & NVENC transcode
│   ├── transcriber.py         # Faster-Whisper CUDA engine with live streaming logs
│   ├── highlight_detector.py  # Viral hook heuristics & Episodic Series Slicer
│   ├── clip_extractor.py      # Stream copy lossless slicing
│   ├── smart_cropper.py       # Centered GTA character & Facecam Split-Screen
│   ├── subtitle_generator.py  # Animated karaoke ASS captions (Nirmala UI)
│   └── renderer.py            # Hardware NVENC 60fps render engine
├── app.py                     # AutoClipper Modern Gradio Web Dashboard
└── README.md                  # Comprehensive documentation
```

---

## 👨‍💻 Author & Credits

Developed with ❤️ by **[Ashish Pingale](https://github.com/ashishh-pingale)**.
