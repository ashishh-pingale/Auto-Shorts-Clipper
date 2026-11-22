"""
Auto Shorts Clipper - Desktop Web UI (Phase 8)
Hardware Accelerated for NVIDIA GTX 1650 (4GB) & AMD Ryzen 5 5600H.
"""

import os
import sys
import json
import tempfile
from pathlib import Path

# 1. Lock PROJECT_ROOT to D: drive
PROJECT_ROOT = Path(__file__).resolve().parent
TEMP_DIR = PROJECT_ROOT / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
GRADIO_TEMP = TEMP_DIR / "gradio"
GRADIO_TEMP.mkdir(parents=True, exist_ok=True)

# 2. STRICTLY FORCE all temp files, Gradio staging, and AI models to D: drive
# (Guarantees zero bytes are written to C: drive!)
os.environ["TEMP"] = str(TEMP_DIR)
os.environ["TMP"] = str(TEMP_DIR)
os.environ["TMPDIR"] = str(TEMP_DIR)
os.environ["GRADIO_TEMP_DIR"] = str(GRADIO_TEMP)
os.environ["HF_HOME"] = str(PROJECT_ROOT / "cache" / "huggingface")
os.environ["TORCH_HOME"] = str(PROJECT_ROOT / "cache" / "torch")
tempfile.tempdir = str(TEMP_DIR)

# Add project root to path
sys.path.insert(0, str(PROJECT_ROOT))

import gradio as gr
try:
    import gradio.processing_utils
    gradio.processing_utils.GRADIO_TEMP_DIR = str(GRADIO_TEMP)
except Exception:
    pass

from core_autoclip.downloader import MediaDownloader
from core_autoclip.transcriber import AudioTranscriber
from core_autoclip.highlight_detector import HighlightDetector
from core_autoclip.clip_extractor import ClipExtractor
from core_autoclip.smart_cropper import SmartCropper
from core_autoclip.subtitle_generator import SubtitleGenerator
from core_autoclip.renderer import VideoRenderer

# Global State for session
CURRENT_SESSION = {
    "media": None,
    "transcript": None,
    "highlights": [],
    "selected_clip": None
}

downloader = MediaDownloader()
transcriber = AudioTranscriber(model_size="small", device="cuda", compute_type="float16")
detector = HighlightDetector()
extractor = ClipExtractor(output_dir=PROJECT_ROOT / "temp" / "clips")
cropper = SmartCropper()
renderer = VideoRenderer(output_dir=PROJECT_ROOT / "outputs")

def analyze_video(url_or_file, quality_choice="🌟 1440p 2K (Crisp Quality - Recommended)", model_size="small", clipping_strategy="🔥 AI Viral Highlights (Hook & Moment Scoring)", duration_choice="60 Seconds (1-Minute Short - Recommended)", parts_count_choice="5 Equal Parts (Recommended)", progress=gr.Progress()):
    if not url_or_file:
        return "⚠️ Please enter a YouTube URL or select a video file.", None, [], gr.update()

    # Parse whisper model name (e.g. "small (Recommended..." -> "small")
    chosen_model = model_size.split()[0].strip()

    # Parse duration in seconds (e.g. "60 Seconds..." -> 60.0)
    try:
        target_duration = float(duration_choice.split()[0].replace("s", "").replace("Seconds", ""))
    except Exception:
        target_duration = 60.0

    # Parse parts count (e.g. "5 Equal Parts" -> 5)
    try:
        target_parts = int(parts_count_choice.split()[0])
    except Exception:
        target_parts = 5

    progress(0.05, desc="Ingesting media & extracting 16kHz audio...")
    try:
        media = downloader.process_input(url_or_file, target_resolution=quality_choice)
        CURRENT_SESSION["media"] = media
    except Exception as e:
        return f"❌ Ingestion Error: {str(e)}", None, [], gr.update()

    # Check if transcript was already cached on D: drive
    transcription_cache = PROJECT_ROOT / "temp" / f"{Path(media['video_path']).stem}_transcript.json"
    if transcription_cache.is_file() and transcription_cache.stat().st_size > 100:
        progress(0.4, desc="Loading cached transcript from D: drive (instant)...")
        print(f"[UI] Found cached transcript: {transcription_cache.name}")
        with open(transcription_cache, "r", encoding="utf-8") as f:
            transcript = json.load(f)
        CURRENT_SESSION["transcript"] = transcript
    else:
        progress(0.20, desc=f"Transcribing audio with faster-whisper ({chosen_model})...")
        transcriber.model_size = chosen_model

        def whisper_progress(pct, desc=""):
            gradio_val = 0.20 + (pct * 0.45)
            progress(gradio_val, desc=desc)

        try:
            transcript = transcriber.transcribe(media["audio_path"], progress_callback=whisper_progress)
            transcriber.unload_model() # Flush VRAM immediately
            CURRENT_SESSION["transcript"] = transcript
            with open(transcription_cache, "w", encoding="utf-8") as f:
                json.dump(transcript, f, ensure_ascii=False)
            print(f"[UI] Saved transcript cache to: {transcription_cache.name}")
        except Exception as e:
            return f"❌ Transcription Error: {str(e)}", None, [], gr.update()

    is_episodic = "Episodic" in clipping_strategy or "Part" in clipping_strategy
    if is_episodic:
        is_count = "count" in clipping_strategy.lower() or "number" in clipping_strategy.lower()
        mode_desc = f"Slicing VOD into {target_parts} parts..." if is_count else f"Slicing VOD into {target_duration:.0f}s parts..."
        progress(0.65, desc=mode_desc)
        try:
            split_mode = "count" if is_count else "duration"
            highlights = detector.generate_sequential_chunks(
                transcript,
                split_mode=split_mode,
                target_chunk_duration=target_duration,
                target_num_parts=target_parts,
                max_chunks=150
            )
            CURRENT_SESSION["highlights"] = highlights
        except Exception as e:
            return f"❌ Episodic Slicing Error: {str(e)}", None, [], gr.update()
    else:
        progress(0.65, desc="Analyzing transcript for viral hooks & moments...")
        try:
            min_dur = max(15.0, target_duration - 25.0)
            highlights = detector.find_highlights(
                transcript,
                min_duration=min_dur,
                max_duration=target_duration,
                max_clips=target_parts
            )
            CURRENT_SESSION["highlights"] = highlights
        except Exception as e:
            return f"❌ Highlight Detection Error: {str(e)}", None, [], gr.update()

    progress(1.0, desc="Complete!")

    # Format table data
    table_rows = []
    for h in highlights:
        score_val = str(h['viral_score'])
        if not score_val.startswith("Part") and "/" not in score_val:
            score_val = f"{score_val}/10"
        table_rows.append([
            f"#{h['clip_id']}",
            h['title'],
            f"{h['duration']}s",
            f"{h['start']}s -> {h['end']}s",
            score_val,
            h['hook']
        ])

    mode_label = "episodic serial parts" if is_episodic else "viral candidate clips"
    status_msg = f"✅ Success! Extracted {len(highlights)} {mode_label} from '{media['title']}'."
    clip_choices = [str(h['clip_id']) for h in highlights] if highlights else [str(i) for i in range(1, 101)]
    dropdown_update = gr.update(choices=clip_choices, value=clip_choices[0] if clip_choices else "1")
    return status_msg, media["video_path"], table_rows, dropdown_update

def batch_render_all_clips(style_choice, framing_mode="Centered Character (GTA / Gaming)", manual_offset_pct=50, aspect_choice="📱 Vertical 9:16 (Shorts/Reels/TikTok)", font_choice="Nirmala UI (Native Hindi & Clean English)", progress=gr.Progress()):
    highlights = CURRENT_SESSION.get("highlights", [])
    if not highlights:
        return None, "⚠️ Please analyze a video first!"

    total = len(highlights)
    rendered_files = []
    last_rendered_path = None

    for i, clip in enumerate(highlights):
        c_id = clip["clip_id"]
        progress((i / total), desc=f"Rendering {i+1}/{total}: Clip #{c_id} ({clip['duration']}s)...")
        try:
            path, _ = render_short_clip(
                clip_index=c_id,
                style_choice=style_choice,
                framing_mode=framing_mode,
                manual_offset_pct=manual_offset_pct,
                aspect_choice=aspect_choice,
                font_choice=font_choice
            )
            if path:
                rendered_files.append(Path(path).name)
                last_rendered_path = path
        except Exception as e:
            print(f"[Batch Render Error on #{c_id}]: {e}")

    summary_msg = f"🎉 Batch Render Complete! Exported {len(rendered_files)}/{total} clips to D:\\Ai Softwares\\Auto Shorts Clipper\\outputs\\"
    return last_rendered_path, summary_msg

def render_short_clip(clip_index, style_choice, framing_mode="Centered Character (GTA / Gaming)", manual_offset_pct=50, aspect_choice="📱 Vertical 9:16 (Shorts/Reels/TikTok)", font_choice="Nirmala UI (Native Hindi & Clean English)", progress=gr.Progress()):
    highlights = CURRENT_SESSION.get("highlights", [])
    media = CURRENT_SESSION.get("media")
    transcript = CURRENT_SESSION.get("transcript")

    if not highlights or not media or not transcript:
        return None, "⚠️ Please analyze a video first!"

    try:
        idx = int(clip_index) - 1
        clip = highlights[idx]
    except Exception:
        return None, "⚠️ Invalid Clip Number selected."

    try:
        progress(0.1, desc=f"Slicing Clip #{clip['clip_id']} ({clip['start']}s -> {clip['end']}s)...")
        raw_clip_path = extractor.extract_clip(
            media["video_path"],
            start_time=clip["start"],
            end_time=clip["end"],
            clip_id=clip["clip_id"],
            title=clip["title"]
        )

        is_horizontal = "Horizontal" in aspect_choice or "16:9" in aspect_choice

        if not is_horizontal:
            progress(0.3, desc=f"Framing {framing_mode} ({aspect_choice})...")
            crop_data = cropper.analyze_faces_and_track(
                raw_clip_path,
                framing_mode=framing_mode,
                manual_offset_pct=float(manual_offset_pct),
                aspect_ratio=aspect_choice
            )
        else:
            crop_data = None

        progress(0.6, desc="Generating animated karaoke subtitles...")
        clip_words = extractor.filter_words_for_clip(transcript, clip["start"], clip["end"])

        highlight_hex = "&H0000D7FF" # Electric Yellow (default)
        if "Green" in style_choice:
            highlight_hex = "&H0000FF00"
        elif "White" in style_choice:
            highlight_hex = "&H00FFFFFF"

        if "4:5" in aspect_choice:
            sub_w, sub_h = 1080, 1350
            prefix = "Short_4x5"
        elif "3:4" in aspect_choice:
            sub_w, sub_h = 1080, 1440
            prefix = "Short_3x4"
        elif is_horizontal:
            sub_w, sub_h = 1920, 1080
            prefix = "Clip_16x9"
        else:
            sub_w, sub_h = 1080, 1920
            prefix = "Short_9x16"

        # Determine font
        chosen_font = "Nirmala UI"
        if "Arial Black" in font_choice:
            chosen_font = "Arial Black"
        elif "Segoe UI" in font_choice:
            chosen_font = "Segoe UI"
        elif "Impact" in font_choice:
            chosen_font = "Impact"

        # Generate subtitles only if words exist in this clip/part
        ass_path = None
        if clip_words:
            sub_gen = SubtitleGenerator(font_name=chosen_font, highlight_color=highlight_hex)
            ass_file = PROJECT_ROOT / "temp" / f"sub_{clip['clip_id']}.ass"
            sub_gen.generate_karaoke_ass(clip_words, str(ass_file), screen_w=sub_w, screen_h=sub_h)
            ass_path = str(ass_file)

        progress(0.8, desc="Hardware NVENC 60fps rendering (GTX 1650)...")

        # Sanitize title for Windows NTFS compatibility (remove : ? / \ * < > |)
        clean_title = "".join(c for c in clip.get('title', '') if c.isalnum() or c in (" ", "_", "-")).strip()
        clean_title = clean_title.replace(" ", "_")[:20]
        if not clean_title:
            clean_title = f"part_{clip['clip_id']}"
        out_filename = f"{prefix}_{clip['clip_id']}_{clean_title}.mp4"

        final_path = renderer.render_final_short(
            input_video_path=raw_clip_path,
            subtitle_ass_path=ass_path,
            crop_data=crop_data,
            output_filename=out_filename,
            use_nvenc=True,
            aspect_ratio=aspect_choice
        )

        progress(1.0, desc="Render Complete!")
        return str(final_path), f"🎉 Exported successfully to:\n{final_path}"
    except Exception as e:
        import traceback
        err_details = traceback.format_exc()
        print(f"[Render Error]\n{err_details}")
        return None, f"❌ Render Error: {str(e)}"

# Build Gradio Dark Theme UI
custom_css = """
body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
.gradio-container { max-width: 1200px !important; }
"""

def get_recent_temp_videos():
    """Lists already downloaded mp4 videos in temp/ folder."""
    temp_dir = PROJECT_ROOT / "temp"
    if not temp_dir.exists():
        return []
    videos = sorted(temp_dir.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)
    return [str(v) for v in videos if "clip_" not in v.name]

with gr.Blocks(title="Auto YouTube to Shorts Clipper", theme=gr.themes.Soft(primary_hue="blue")) as demo:
    gr.Markdown("""
    # 🎬 Auto YouTube to Shorts Clipper
    ### Optimized for NVIDIA GeForce GTX 1650 (4GB) & AMD Ryzen 5 5600H
    """)

    with gr.Row():
        with gr.Column(scale=5):
            video_input = gr.Textbox(
                label="🔗 YouTube URL or Local File Path",
                placeholder="https://www.youtube.com/watch?v=... or D:\\Videos\\sample.mp4",
                lines=1
            )
            cached_dropdown = gr.Dropdown(
                label="📂 Or Pick From Already Downloaded Videos in temp/",
                choices=get_recent_temp_videos(),
                value=None,
                info="If you refreshed the page, select your previously downloaded video here!"
            )
            with gr.Row():
                quality_dropdown = gr.Dropdown(
                    label="📥 Download Resolution",
                    choices=[
                        "🌟 1440p 2K (Crisp Quality - Recommended)",
                        "⚡ 1080p Full HD (Fastest Download)",
                        "🎬 4K 2160p (Maximum Quality - Large File)"
                    ],
                    value="🌟 1440p 2K (Crisp Quality - Recommended)",
                    info="1440p gives razor-sharp 9:16 crops with only ~4 mins extra download!"
                )
                model_dropdown = gr.Dropdown(
                    label="🧠 Faster-Whisper Model (Hardware Tuned)",
                    choices=[
                        "small (Recommended / ~850MB VRAM - GTX 1650/4GB)",
                        "base (Fast / ~500MB VRAM)",
                        "tiny (Ultra-light / ~400MB VRAM / iGPU)",
                        "medium (High Accuracy / ~2GB VRAM / 6GB+ GPU)",
                        "turbo (large-v3-turbo / ~1.6GB VRAM / 6GB+ GPU)",
                        "large-v3 (Maximum Accuracy / ~3.5GB VRAM / 8GB+ GPU)"
                    ],
                    value="small (Recommended / ~850MB VRAM - GTX 1650/4GB)",
                    info="Choose based on your GPU VRAM. 'small' runs in ~850MB VRAM; 'turbo' & 'medium' for 6GB+ cards."
                )

            clipping_mode = gr.Radio(
                label="✂️ Clipping Strategy",
                choices=[
                    "🔥 AI Viral Highlights (Hook & Moment Scoring)",
                    "⏱️ Episodic Series: By Duration per Part (e.g. 60s each)",
                    "🔢 Episodic Series: By Total Number of Parts (e.g. Split into 5 equal parts)"
                ],
                value="🔥 AI Viral Highlights (Hook & Moment Scoring)",
                info="Choose AI Viral Moments, or systematically cut the VOD into sequential serial episodes!"
            )

            with gr.Row():
                duration_dropdown = gr.Dropdown(
                    label="⏱️ Duration of Each Part",
                    choices=[
                        "30 Seconds (Fast Short / TikTok)",
                        "45 Seconds (Standard Reel)",
                        "60 Seconds (1-Minute Short - Recommended)",
                        "90 Seconds (Extended Episode)",
                        "120 Seconds (2-Minute Episode)",
                        "180 Seconds (3-Minute Part)"
                    ],
                    value="60 Seconds (1-Minute Short - Recommended)",
                    info="Used when 'By Duration' or 'AI Viral Highlights' is chosen"
                )
                parts_count_dropdown = gr.Dropdown(
                    label="🔢 Total Number of Parts to Split Into",
                    choices=[
                        "2 Equal Parts",
                        "3 Equal Parts",
                        "4 Equal Parts",
                        "5 Equal Parts (Recommended)",
                        "6 Equal Parts",
                        "8 Equal Parts",
                        "10 Equal Parts",
                        "12 Equal Parts",
                        "15 Equal Parts",
                        "20 Equal Parts",
                        "25 Equal Parts",
                        "30 Equal Parts",
                        "50 Equal Parts",
                        "100 Equal Parts (Full Stream)"
                    ],
                    value="5 Equal Parts (Recommended)",
                    info="Used when 'By Total Number of Parts' is chosen"
                )

            analyze_btn = gr.Button("⚡ Analyze Video & Generate Clips", variant="primary", size="lg")
            status_output = gr.Textbox(label="Status", lines=1)

        with gr.Column(scale=4):
            source_video_preview = gr.Video(label="Input Video Preview")

    gr.Markdown("---")
    gr.Markdown("### 🔥 Candidate Clips / Episodic Parts")

    highlight_table = gr.Dataframe(
        headers=["ID", "Title", "Duration", "Timestamps", "Viral Score / Part", "Opening Hook"],
        datatype=["str", "str", "str", "str", "str", "str"],
        interactive=False,
        label="Ranked Candidate Shorts"
    )

    with gr.Row():
        with gr.Column(scale=4):
            gr.Markdown("### 📱 Export & Styling Controls")
            clip_select = gr.Dropdown(
                label="Select Clip Number to Render",
                choices=[str(i) for i in range(1, 101)],
                value="1",
                info="Automatically syncs with all clips / parts found during analysis"
            )
            aspect_dropdown = gr.Dropdown(
                label="📐 Output Aspect Ratio",
                choices=[
                    "📱 Vertical 9:16 (Shorts / Reels / TikTok)",
                    "📸 Portrait 4:5 (Instagram / Reels - Much Sharper & Wider)",
                    "📐 Portrait 3:4 (Classic Portrait - Sharp & Balanced)",
                    "🖥️ Original Horizontal 16:9 (Landscape / Widescreen)"
                ],
                value="📱 Vertical 9:16 (Shorts / Reels / TikTok)",
                info="4:5 and 3:4 keep 30-40% more horizontal pixels, resulting in much higher sharpness!"
            )
            framing_dropdown = gr.Dropdown(
                label="🎮 Vertical Framing Mode (GTA / Gaming / Face)",
                choices=[
                    "Centered Character (GTA / Gaming)",
                    "🎙️ Streamer Split-Screen (Facecam Top, Game Bottom)",
                    "Custom Horizontal Offset",
                    "Auto Face Tracking (Podcasts / Real Faces)"
                ],
                value="Centered Character (GTA / Gaming)",
                info="Choose 'Centered Character' for pure gameplay, or 'Streamer Split-Screen' to show both webcam & game!"
            )
            manual_offset_slider = gr.Slider(
                minimum=0,
                maximum=100,
                value=50,
                step=1,
                label="Manual Horizontal Position (0% Left, 50% Center, 100% Right)",
                info="Fine-tune character positioning if over-the-shoulder"
            )
            with gr.Row():
                style_dropdown = gr.Dropdown(
                    label="Caption Style",
                    choices=["Electric Yellow (MrBeast)", "Neon Green (TikTok)", "Clean White (Minimal)"],
                    value="Electric Yellow (MrBeast)"
                )
                font_dropdown = gr.Dropdown(
                    label="Subtitle Font",
                    choices=[
                        "Nirmala UI (Native Hindi & Clean English)",
                        "Segoe UI (Modern Crisp Sans)",
                        "Impact (Classic Viral Punch)",
                        "Arial Black (Bold English)"
                    ],
                    value="Nirmala UI (Native Hindi & Clean English)",
                    info="Nirmala UI fixes Hindi matras/dotted circles completely!"
                )
            with gr.Row():
                render_btn = gr.Button("🚀 Render Selected Short (NVENC 60fps)", variant="primary", scale=2)
                batch_render_btn = gr.Button("⚡ Batch Render All Clips / Parts", variant="secondary", scale=2)
            export_status = gr.Textbox(label="Export Log", lines=2)

        with gr.Column(scale=5):
            gr.Markdown("### 📱 Rendered Short / Clip Preview")
            rendered_video_preview = gr.Video(label="Final Rendered Video")

    # Event Bindings
    cached_dropdown.change(
        fn=lambda choice: choice or "",
        inputs=[cached_dropdown],
        outputs=[video_input]
    )

    analyze_btn.click(
        fn=analyze_video,
        inputs=[video_input, quality_dropdown, model_dropdown, clipping_mode, duration_dropdown, parts_count_dropdown],
        outputs=[status_output, source_video_preview, highlight_table, clip_select]
    )

    render_btn.click(
        fn=render_short_clip,
        inputs=[clip_select, style_dropdown, framing_dropdown, manual_offset_slider, aspect_dropdown, font_dropdown],
        outputs=[rendered_video_preview, export_status]
    )

    batch_render_btn.click(
        fn=batch_render_all_clips,
        inputs=[style_dropdown, framing_dropdown, manual_offset_slider, aspect_dropdown, font_dropdown],
        outputs=[rendered_video_preview, export_status]
    )

if __name__ == "__main__":
    print("[UI] Launching Auto Shorts Clipper on http://localhost:7860...")
    try:
        demo.launch(server_name="127.0.0.1", server_port=7860, inbrowser=True, allowed_paths=[str(PROJECT_ROOT)])
    except OSError:
        print("[UI] Port 7860 is already in use. Launching on the next available open port...")
        demo.launch(server_name="127.0.0.1", inbrowser=True, allowed_paths=[str(PROJECT_ROOT)])
