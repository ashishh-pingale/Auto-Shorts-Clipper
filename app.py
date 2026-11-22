"""
AutoClipper - Professional Video Slicing & Vertical Reframing Engine
Interface Architecture: DaVinci Resolve & Premiere Pro Studio Layout.
Hardware Accelerated for NVIDIA GTX 1650 (4GB) & AMD Ryzen 5 5600H.
Zero-footprint: Strictly 0 bytes written to C: drive.
Developed by Ashish Pingale (https://github.com/ashishh-pingale).
"""

import os
import sys
import json
import tempfile
from pathlib import Path

# 1. Lock PROJECT_ROOT strictly to D: drive
PROJECT_ROOT = Path(__file__).resolve().parent
TEMP_DIR = PROJECT_ROOT / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
GRADIO_TEMP = TEMP_DIR / "gradio"
GRADIO_TEMP.mkdir(parents=True, exist_ok=True)

# 2. STRICTLY FORCE all temp files, Gradio staging, and AI models to D: drive
os.environ["TEMP"] = str(TEMP_DIR)
os.environ["TMP"] = str(TEMP_DIR)
os.environ["TMPDIR"] = str(TEMP_DIR)
os.environ["GRADIO_TEMP_DIR"] = str(GRADIO_TEMP)
os.environ["HF_HOME"] = str(PROJECT_ROOT / "cache" / "huggingface")
os.environ["TORCH_HOME"] = str(PROJECT_ROOT / "cache" / "torch")
tempfile.tempdir = str(TEMP_DIR)

# Add project root to sys.path
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

# Global Session State
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

def get_recent_temp_videos():
    """Lists already downloaded mp4 videos in temp/ folder."""
    temp_dir = PROJECT_ROOT / "temp"
    if not temp_dir.exists():
        return []
    videos = sorted(temp_dir.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)
    return [str(v) for v in videos if "clip_" not in v.name]

def analyze_video(url_or_file, quality_choice="1440p QHD (Recommended)", codec_choice="H.264 / AVC (DaVinci & Premiere)", model_size="small (~850 MB - Recommended)", clipping_strategy="AI Viral Highlights (Hook & Engagement Scoring)", duration_choice="60 Seconds (Recommended)", parts_count_choice="5 Parts (Recommended)", progress=gr.Progress()):
    if not url_or_file:
        return "Notice: Please enter a YouTube URL or select an existing video file.", None, [], gr.update()

    # Parse whisper model name (e.g. "small (~850 MB..." -> "small")
    chosen_model = model_size.split()[0].strip()

    # Parse duration in seconds (e.g. "60 Seconds (Recommended)" -> 60.0)
    try:
        duration_token = duration_choice.split()[0].replace("s", "").replace("Seconds", "")
        target_duration = float(duration_token)
    except Exception:
        target_duration = 60.0

    # Parse parts count (e.g. "5 Parts (Recommended)" -> 5)
    try:
        parts_token = parts_count_choice.split()[0]
        target_parts = int(parts_token)
    except Exception:
        target_parts = 5

    progress(0.05, desc="Ingesting media and verifying NLE codec compatibility...")
    try:
        media = downloader.process_input(url_or_file, target_resolution=quality_choice, target_codec=codec_choice)
        CURRENT_SESSION["media"] = media
    except Exception as e:
        return f"Error [Ingestion]: {str(e)}", None, [], gr.update()

    # Check if transcript was already cached on D: drive
    transcription_cache = PROJECT_ROOT / "temp" / f"{Path(media['video_path']).stem}_transcript.json"
    if transcription_cache.is_file() and transcription_cache.stat().st_size > 100:
        progress(0.4, desc="Loading cached transcript from storage...")
        print(f"[AutoClipper] Found cached transcript: {transcription_cache.name}")
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
            transcriber.unload_model() # Flush VRAM immediately for NVENC rendering
            CURRENT_SESSION["transcript"] = transcript
            with open(transcription_cache, "w", encoding="utf-8") as f:
                json.dump(transcript, f, ensure_ascii=False)
            print(f"[AutoClipper] Saved transcript cache: {transcription_cache.name}")
        except Exception as e:
            return f"Error [Transcription]: {str(e)}", None, [], gr.update()

    is_episodic = "Episodic" in clipping_strategy or "Part" in clipping_strategy
    if is_episodic:
        is_count = "count" in clipping_strategy.lower() or "number" in clipping_strategy.lower() or "parts" in clipping_strategy.lower()
        mode_desc = f"Slicing timeline into {target_parts} parts..." if is_count else f"Slicing timeline into {target_duration:.0f}s parts..."
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
            return f"Error [Episodic Slicing]: {str(e)}", None, [], gr.update()
    else:
        progress(0.65, desc="Analyzing transcript for viral hooks and engagement points...")
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
            return f"Error [Highlight Detection]: {str(e)}", None, [], gr.update()

    progress(1.0, desc="Ready")

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

    mode_label = "episodic serial parts" if is_episodic else "candidate highlights"
    status_msg = f"Ready: Extracted {len(highlights)} {mode_label} from '{media['title']}'."
    clip_choices = [str(h['clip_id']) for h in highlights] if highlights else [str(i) for i in range(1, 101)]
    dropdown_update = gr.update(choices=clip_choices, value=clip_choices[0] if clip_choices else "1")
    return status_msg, media["video_path"], table_rows, dropdown_update

def render_short_clip(clip_index, style_choice, framing_mode="Centered Subject (Gaming & Gameplay)", manual_offset_pct=50, aspect_choice="Vertical 9:16 (Shorts / Reels / TikTok)", font_choice="Poppins (Modern Geometric Sans)", progress=gr.Progress()):
    highlights = CURRENT_SESSION.get("highlights", [])
    media = CURRENT_SESSION.get("media")
    transcript = CURRENT_SESSION.get("transcript")

    if not highlights or not media or not transcript:
        return None, "Notice: Please analyze a video first before rendering."

    try:
        idx = int(clip_index) - 1
        clip = highlights[idx]
    except Exception:
        return None, "Notice: Invalid Clip Number selected."

    try:
        progress(0.1, desc=f"Extracting Clip #{clip['clip_id']} ({clip['start']}s -> {clip['end']}s)...")
        raw_clip_path = extractor.extract_clip(
            media["video_path"],
            start_time=clip["start"],
            end_time=clip["end"],
            clip_id=clip["clip_id"],
            title=clip["title"]
        )

        is_horizontal = "Horizontal" in aspect_choice or "16:9" in aspect_choice

        if not is_horizontal:
            progress(0.3, desc=f"Calculating reframing ({framing_mode})...")
            crop_data = cropper.analyze_faces_and_track(
                raw_clip_path,
                framing_mode=framing_mode,
                manual_offset_pct=float(manual_offset_pct),
                aspect_ratio=aspect_choice
            )
        else:
            crop_data = None

        progress(0.6, desc="Synthesizing animated karaoke subtitles...")
        clip_words = extractor.filter_words_for_clip(transcript, clip["start"], clip["end"])

        highlight_hex = "&H0000D7FF" # Electric Yellow
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

        chosen_font = "Poppins"
        if "Nirmala UI" in font_choice:
            chosen_font = "Nirmala UI"
        elif "Segoe UI" in font_choice:
            chosen_font = "Segoe UI"
        elif "Impact" in font_choice:
            chosen_font = "Impact"
        elif "Arial Black" in font_choice:
            chosen_font = "Arial Black"

        ass_path = None
        if clip_words:
            sub_gen = SubtitleGenerator(font_name=chosen_font, highlight_color=highlight_hex)
            ass_file = PROJECT_ROOT / "temp" / f"sub_{clip['clip_id']}.ass"
            sub_gen.generate_karaoke_ass(clip_words, str(ass_file), screen_w=sub_w, screen_h=sub_h)
            ass_path = str(ass_file)

        progress(0.8, desc="Hardware NVENC 60 FPS rendering...")

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

        progress(1.0, desc="Render Complete")
        return str(final_path), f"Export Complete: Saved to {final_path}"
    except Exception as e:
        import traceback
        err_details = traceback.format_exc()
        print(f"[Render Error]\n{err_details}")
        return None, f"Error [Render]: {str(e)}"

def batch_render_all_clips(style_choice, framing_mode="Centered Subject (Gaming & Gameplay)", manual_offset_pct=50, aspect_choice="Vertical 9:16 (Shorts / Reels / TikTok)", font_choice="Poppins (Modern Geometric Sans)", progress=gr.Progress()):
    highlights = CURRENT_SESSION.get("highlights", [])
    if not highlights:
        return None, "Notice: Please analyze a video first before starting batch render."

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

    summary_msg = f"Batch Render Complete: Exported {len(rendered_files)}/{total} clips to outputs directory."
    return last_rendered_path, summary_msg

# ==============================================================================
# Professional Video Editor CSS Theme (DaVinci Resolve / Premiere Pro Inspired)
# Non-neon, full-screen width, industrial matte dark workspace, Poppins typography.
# Clean, seamless dropdowns without dark text patches or blue pills.
# ==============================================================================
custom_css = """
@import url('https://fonts.googleapis.com/css2?family=Poppins:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&display=swap');

:root {
    --nle-root-bg: #111317;
    --nle-panel-bg: #1a1e24;
    --nle-panel-header: #202630;
    --nle-input-bg: #14171d;
    --nle-border: #2c333f;
    --nle-border-subtle: #242933;
    --nle-border-focus: #3b82f6;
    --nle-accent-blue: #2563eb;
    --nle-accent-blue-hover: #1d4ed8;
    --nle-text-primary: #eceff4;
    --nle-text-secondary: #9aa5b6;
    --nle-text-muted: #677488;
    --nle-indicator-green: #10b981;
}

* {
    font-family: 'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
}

/* Utilize 100% Full-Screen Space */
body, .gradio-container {
    background-color: var(--nle-root-bg) !important;
    color: var(--nle-text-primary) !important;
    max-width: 100% !important;
    width: 100% !important;
    margin: 0 !important;
    padding: 10px 18px 24px 18px !important;
    box-sizing: border-box !important;
}

/* NLE Top Navigation Bar */
.nle-app-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 18px;
    background: var(--nle-panel-bg);
    border: 1px solid var(--nle-border);
    border-radius: 6px;
    margin-bottom: 12px;
}
.nle-brand-section {
    display: flex;
    align-items: center;
    gap: 14px;
}
.nle-logo-icon {
    width: 32px;
    height: 32px;
    background: #2563eb;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #ffffff;
}
.nle-brand-title {
    font-size: 1.15rem;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.01em;
}
.nle-version-tag {
    font-size: 0.68rem;
    font-weight: 600;
    background: #202630;
    color: #9aa5b6;
    border: 1px solid var(--nle-border);
    padding: 1px 6px;
    border-radius: 3px;
    letter-spacing: 0.05em;
    margin-left: 8px;
}
.nle-workspace-indicator {
    display: flex;
    align-items: center;
    gap: 6px;
    background: #14171d;
    border: 1px solid var(--nle-border-subtle);
    border-radius: 4px;
    padding: 3px 10px;
    font-size: 0.74rem;
    color: var(--nle-text-secondary);
    font-weight: 500;
}
.nle-system-telemetry {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}
.nle-telemetry-tag {
    display: flex;
    align-items: center;
    gap: 6px;
    background: #14171d;
    border: 1px solid var(--nle-border-subtle);
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 0.72rem;
    font-weight: 500;
    color: var(--nle-text-secondary);
}
.nle-status-bullet {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--nle-indicator-green);
}

/* NLE Modular Docked Panels */
.nle-panel {
    background: var(--nle-panel-bg) !important;
    border: 1px solid var(--nle-border) !important;
    border-radius: 6px !important;
    padding: 14px 16px !important;
    margin-bottom: 12px !important;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25) !important;
}

/* Panel Header */
.nle-panel-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.82rem;
    font-weight: 600;
    color: #d8dee9;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding-bottom: 8px;
    margin-bottom: 12px;
    border-bottom: 1px solid var(--nle-border);
}
.nle-panel-icon {
    display: flex;
    align-items: center;
    color: #60a5fa;
}

/* Clean, transparent NLE Form Labels (Removes bright blue background pills) */
label, label span, .block-title, .gr-form label span, [data-testid="block-label"], .label-container {
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    padding: 0 !important;
    margin-bottom: 4px !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    color: var(--nle-text-secondary) !important;
    letter-spacing: 0.01em !important;
}

/* Standalone Textboxes & Inputs */
input[type="text"], input[type="number"], textarea, .gr-textbox input, .gr-textbox textarea {
    background: var(--nle-input-bg) !important;
    border: 1px solid var(--nle-border) !important;
    border-radius: 4px !important;
    color: var(--nle-text-primary) !important;
    font-size: 0.84rem !important;
    padding: 8px 12px !important;
}
input[type="text"]:focus, textarea:focus {
    border-color: var(--nle-border-focus) !important;
    box-shadow: 0 0 0 1px var(--nle-border-focus) !important;
}

/* Seamless Dropdowns: Entire Container */
.gr-dropdown, [data-testid="dropdown"] {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}

/* Dropdown Outer Input Wrapper */
.gr-dropdown .wrap,
.gr-dropdown .secondary-wrap,
[data-testid="dropdown"] .wrap,
[data-testid="dropdown"] .secondary-wrap {
    background: var(--nle-input-bg) !important;
    border: 1px solid var(--nle-border) !important;
    border-radius: 4px !important;
    min-height: 36px !important;
    padding: 3px 8px !important;
    box-shadow: none !important;
    display: flex !important;
    align-items: center !important;
}

/* Dropdown Inner Elements: ELIMINATE the inner black patch box and borders */
.gr-dropdown input,
.gr-dropdown .wrap-inner,
.gr-dropdown .single-select,
.gr-dropdown .value-default,
.gr-dropdown .value-default span,
.gr-dropdown span,
[data-testid="dropdown"] input,
[data-testid="dropdown"] .wrap-inner,
[data-testid="dropdown"] .single-select,
[data-testid="dropdown"] span {
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    outline: none !important;
    color: var(--nle-text-primary) !important;
    font-size: 0.84rem !important;
    line-height: 1.4 !important;
    padding: 0 !important;
    margin: 0 !important;
    width: 100% !important;
    min-width: 0 !important;
}

/* Dropdown Options Popup Menu */
.gr-dropdown ul.options,
[data-testid="dropdown"] ul.options,
.options {
    background: var(--nle-panel-bg) !important;
    border: 1px solid var(--nle-border) !important;
    border-radius: 4px !important;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4) !important;
}
.options li, .options .item {
    background: transparent !important;
    color: var(--nle-text-primary) !important;
    font-size: 0.82rem !important;
    padding: 7px 12px !important;
}
.options li:hover, .options .item:hover, .options li.selected {
    background: var(--nle-accent-blue) !important;
    color: #ffffff !important;
}

/* NLE Action Buttons */
.nle-btn-primary {
    background: var(--nle-accent-blue) !important;
    border: 1px solid #3b82f6 !important;
    border-radius: 4px !important;
    color: #ffffff !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    padding: 9px 16px !important;
    cursor: pointer !important;
    transition: background-color 0.15s ease !important;
}
.nle-btn-primary:hover {
    background: var(--nle-accent-blue-hover) !important;
}

.nle-btn-secondary {
    background: #202630 !important;
    border: 1px solid var(--nle-border) !important;
    border-radius: 4px !important;
    color: var(--nle-text-primary) !important;
    font-weight: 500 !important;
    font-size: 0.88rem !important;
    padding: 9px 16px !important;
    transition: background-color 0.15s ease !important;
}
.nle-btn-secondary:hover {
    background: #2c333f !important;
}

/* Program Monitor / Video Viewers */
.gr-video {
    background: #0d0f12 !important;
    border: 1px solid var(--nle-border) !important;
    border-radius: 4px !important;
}

/* Timeline & Clips Pool Dataframe */
.gr-dataframe {
    border: 1px solid var(--nle-border) !important;
    border-radius: 4px !important;
    background: var(--nle-input-bg) !important;
}
.gr-dataframe th {
    background: var(--nle-panel-header) !important;
    font-weight: 600 !important;
    font-size: 0.76rem !important;
    color: #cbd5e1 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    padding: 7px 10px !important;
    border-bottom: 1px solid var(--nle-border) !important;
}
.gr-dataframe td {
    font-size: 0.80rem !important;
    padding: 7px 10px !important;
    color: #e2e8f0 !important;
    border-color: var(--nle-border-subtle) !important;
}

/* Status Log Output */
textarea[readonly] {
    font-family: 'Consolas', 'Courier New', monospace !important;
    font-size: 0.80rem !important;
}

/* NLE Footer Status Bar */
.nle-status-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 14px;
    background: var(--nle-panel-bg);
    border: 1px solid var(--nle-border);
    border-radius: 4px;
    margin-top: 10px;
    flex-wrap: wrap;
    gap: 8px;
}
.nle-footer-credits {
    font-size: 0.78rem;
    color: var(--nle-text-secondary);
}
.nle-footer-credits strong {
    color: var(--nle-text-primary);
}
.nle-footer-link {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: #202630;
    border: 1px solid var(--nle-border);
    padding: 2px 8px;
    border-radius: 3px;
    color: #60a5fa;
    text-decoration: none;
    font-size: 0.74rem;
    margin-left: 8px;
    transition: background-color 0.15s ease;
}
.nle-footer-link:hover {
    background: #2c333f;
    color: #93c5fd;
}
.nle-footer-spec {
    font-size: 0.74rem;
    color: var(--nle-text-muted);
}
"""

with gr.Blocks(title="AutoClipper PRO - Video Studio", theme=gr.themes.Default(primary_hue="slate", neutral_hue="slate", spacing_size="sm", radius_size="sm"), css=custom_css) as demo:
    # NLE App Header Bar
    gr.HTML("""
    <div class="nle-app-bar">
        <div class="nle-brand-section">
            <div class="nle-logo-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <polygon points="23 7 16 12 23 17 23 7"></polygon>
                    <rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect>
                </svg>
            </div>
            <div>
                <span class="nle-brand-title">AutoClipper</span>
                <span class="nle-version-tag">PRO v2.0</span>
            </div>
            <div class="nle-workspace-indicator">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                    <line x1="9" y1="3" x2="9" y2="21"></line>
                </svg>
                <span>Automated Slicing & Vertical Studio</span>
            </div>
        </div>
        <div class="nle-system-telemetry">
            <div class="nle-telemetry-tag">
                <span class="nle-status-bullet"></span>
                <span>NVIDIA GTX 1650 NVENC (60 FPS)</span>
            </div>
            <div class="nle-telemetry-tag">
                <span>Faster-Whisper CUDA</span>
            </div>
            <div class="nle-telemetry-tag">
                <span>NLE Codec: H.264 / HEVC</span>
            </div>
            <div class="nle-telemetry-tag">
                <span>D: Drive Isolated</span>
            </div>
        </div>
    </div>
    """)

    # Main Full-Screen Grid Split (Left: Inspector & Pipeline / Right: Program Monitor & Timeline)
    with gr.Row(equal_height=False):
        # LEFT PANEL: Inspector, Ingestion & Controls (Scale 5)
        with gr.Column(scale=5, min_width=460):
            # PANEL 1: Source Media & Encoding Presets
            with gr.Column(elem_classes=["nle-panel"]):
                gr.HTML("""
                <div class="nle-panel-title">
                    <span class="nle-panel-icon">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                            <polyline points="7 10 12 15 17 10"></polyline>
                            <line x1="12" y1="15" x2="12" y2="3"></line>
                        </svg>
                    </span>
                    <span>Source Media & Project Ingestion</span>
                </div>
                """)
                video_input = gr.Textbox(
                    label="Media Source (YouTube URL or Local File Path)",
                    placeholder="https://www.youtube.com/watch?v=... or D:\\Videos\\source.mp4",
                    lines=1
                )
                cached_dropdown = gr.Dropdown(
                    label="Project Media Pool (Cached in temp/)",
                    choices=get_recent_temp_videos(),
                    value=None,
                    info="Select an existing file to bypass re-downloading"
                )
                with gr.Row():
                    quality_dropdown = gr.Dropdown(
                        label="Resolution",
                        choices=[
                            "1440p QHD (Recommended)",
                            "1080p Full HD",
                            "2160p 4K UHD"
                        ],
                        value="1440p QHD (Recommended)",
                        info="1440p yields razor-sharp vertical crops"
                    )
                    codec_dropdown = gr.Dropdown(
                        label="Video Codec",
                        choices=[
                            "H.264 / AVC (DaVinci & Premiere)",
                            "HEVC / H.265 (High Efficiency)",
                            "Native (AV1 / VP9)"
                        ],
                        value="H.264 / AVC (DaVinci & Premiere)",
                        info="H.264 avoids offline media in DaVinci Free"
                    )
                    model_dropdown = gr.Dropdown(
                        label="Speech Model",
                        choices=[
                            "small (~850 MB - Recommended)",
                            "base (~500 MB - Fast)",
                            "tiny (~400 MB - Lightweight)",
                            "medium (~2 GB - High Accuracy)",
                            "turbo (~1.6 GB - Turbo)",
                            "large-v3 (~3.5 GB - Max Accuracy)"
                        ],
                        value="small (~850 MB - Recommended)",
                        info="Auto-flushes VRAM after transcription"
                    )

            # PANEL 2: Slicing Engine
            with gr.Column(elem_classes=["nle-panel"]):
                gr.HTML("""
                <div class="nle-panel-title">
                    <span class="nle-panel-icon">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="6" cy="6" r="3"></circle>
                            <circle cx="6" cy="18" r="3"></circle>
                            <line x1="20" y1="4" x2="8.12" y2="15.88"></line>
                            <line x1="14.47" y1="14.48" x2="20" y2="20"></line>
                            <line x1="8.12" y1="8.12" x2="12" y2="12"></line>
                        </svg>
                    </span>
                    <span>Slicing Strategy & Detection</span>
                </div>
                """)
                clipping_mode = gr.Radio(
                    label="Segmentation Engine",
                    choices=[
                        "AI Viral Highlights (Hook & Engagement Scoring)",
                        "Episodic Series (Fixed Duration per Part)",
                        "Episodic Series (Fixed Number of Parts)"
                    ],
                    value="AI Viral Highlights (Hook & Engagement Scoring)"
                )
                with gr.Row():
                    duration_dropdown = gr.Dropdown(
                        label="Duration per Part",
                        choices=[
                            "60 Seconds (Recommended)",
                            "30 Seconds (Fast Short)",
                            "45 Seconds (Standard Reel)",
                            "90 Seconds (Extended)",
                            "120 Seconds (2-Min Part)",
                            "180 Seconds (3-Min Part)"
                        ],
                        value="60 Seconds (Recommended)",
                        info="Used for Highlights & Fixed Duration"
                    )
                    parts_count_dropdown = gr.Dropdown(
                        label="Total Number of Parts",
                        choices=[
                            "5 Parts (Recommended)",
                            "2 Parts",
                            "3 Parts",
                            "4 Parts",
                            "6 Parts",
                            "8 Parts",
                            "10 Parts",
                            "12 Parts",
                            "15 Parts",
                            "20 Parts",
                            "25 Parts",
                            "30 Parts",
                            "50 Parts",
                            "100 Parts"
                        ],
                        value="5 Parts (Recommended)",
                        info="Used for Fixed Number of Parts"
                    )

                analyze_btn = gr.Button("Analyze Media & Detect Clips", variant="primary", size="lg", elem_classes=["nle-btn-primary"])
                status_output = gr.Textbox(label="Engine Status", lines=1)

            # PANEL 3: Effect Controls (Reframing & Captions)
            with gr.Column(elem_classes=["nle-panel"]):
                gr.HTML("""
                <div class="nle-panel-title">
                    <span class="nle-panel-icon">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"></rect>
                            <line x1="7" y1="2" x2="7" y2="22"></line>
                            <line x1="17" y1="2" x2="17" y2="22"></line>
                            <line x1="2" y1="12" x2="22" y2="12"></line>
                            <line x1="2" y1="7" x2="7" y2="7"></line>
                            <line x1="2" y1="17" x2="7" y2="17"></line>
                            <line x1="17" y1="17" x2="22" y2="17"></line>
                            <line x1="17" y1="7" x2="22" y2="7"></line>
                        </svg>
                    </span>
                    <span>Effect Controls: Reframing & Subtitle Studio</span>
                </div>
                """)
                with gr.Row():
                    aspect_dropdown = gr.Dropdown(
                        label="Aspect Ratio",
                        choices=[
                            "Vertical 9:16 (Shorts / Reels / TikTok)",
                            "Portrait 4:5 (Instagram Feed & Reels)",
                            "Portrait 3:4 (Standard Portrait)",
                            "Horizontal 16:9 (Landscape / Widescreen)"
                        ],
                        value="Vertical 9:16 (Shorts / Reels / TikTok)",
                        info="4:5 and 3:4 preserve extra width"
                    )
                    framing_dropdown = gr.Dropdown(
                        label="Framing Mode",
                        choices=[
                            "Centered Subject (Gaming & Gameplay)",
                            "Streamer Split-Screen (Facecam Top, Game Bottom)",
                            "Auto Face Tracking (Podcasts & Speeches)",
                            "Custom Horizontal Offset"
                        ],
                        value="Centered Subject (Gaming & Gameplay)",
                        info="Centered tracks gameplay protagonist"
                    )

                manual_offset_slider = gr.Slider(
                    minimum=0,
                    maximum=100,
                    value=50,
                    step=1,
                    label="Horizontal Pan Adjustment (0% Left, 50% Center, 100% Right)",
                    info="Fine-tune character positioning for off-center camera angles"
                )

                with gr.Row():
                    font_dropdown = gr.Dropdown(
                        label="Subtitle Typography",
                        choices=[
                            "Poppins (Modern Geometric Sans)",
                            "Nirmala UI (Devanagari & Latin)",
                            "Segoe UI (Clean Sans)",
                            "Impact (Bold Punch)",
                            "Arial Black (Heavy Gothic)"
                        ],
                        value="Poppins (Modern Geometric Sans)",
                        info="Nirmala UI renders Hindi matras natively"
                    )
                    style_dropdown = gr.Dropdown(
                        label="Caption Style",
                        choices=[
                            "Electric Yellow (High Contrast)",
                            "Neon Green (Vibrant Accent)",
                            "Clean White (Minimal Monochrome)"
                        ],
                        value="Electric Yellow (High Contrast)"
                    )

                clip_select = gr.Dropdown(
                    label="Active Target Clip # to Export",
                    choices=[str(i) for i in range(1, 101)],
                    value="1",
                    info="Synchronized with timeline cuts below"
                )

                with gr.Row():
                    render_btn = gr.Button("Render Selected Clip (NVENC)", variant="primary", scale=2, elem_classes=["nle-btn-primary"])
                    batch_render_btn = gr.Button("Batch Render All Clips", variant="secondary", scale=2, elem_classes=["nle-btn-secondary"])

                export_status = gr.Textbox(label="Export Log", lines=2)

        # RIGHT PANEL: Program Monitor & Timeline Clips Pool (Scale 7)
        with gr.Column(scale=7, min_width=540):
            # PANEL 4: Program Monitor
            with gr.Column(elem_classes=["nle-panel"]):
                gr.HTML("""
                <div class="nle-panel-title">
                    <span class="nle-panel-icon">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <polygon points="5 3 19 12 5 21 5 3"></polygon>
                        </svg>
                    </span>
                    <span>Program Monitor / Video Preview</span>
                </div>
                """)
                with gr.Tabs():
                    with gr.Tab("Program Monitor: Rendered Output (NVENC 60 FPS)"):
                        rendered_video_preview = gr.Video(label="Final Rendered Video", elem_id="rendered-preview")
                    with gr.Tab("Source Monitor: Ingested Media"):
                        source_video_preview = gr.Video(label="Raw Input Media", elem_id="source-preview")

            # PANEL 5: Timeline / Clips Pool
            with gr.Column(elem_classes=["nle-panel"]):
                gr.HTML("""
                <div class="nle-panel-title">
                    <span class="nle-panel-icon">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
                            <polyline points="2 17 12 22 22 17"></polyline>
                            <polyline points="2 12 12 17 22 12"></polyline>
                        </svg>
                    </span>
                    <span>Timeline Clips Pool & Candidate Breakdown</span>
                </div>
                """)
                highlight_table = gr.Dataframe(
                    headers=["ID", "Title", "Duration", "Timestamps", "Viral Score / Part", "Opening Hook"],
                    datatype=["str", "str", "str", "str", "str", "str"],
                    interactive=False,
                    label="Detected Timeline Cuts"
                )

    # NLE Footer Status Bar
    gr.HTML("""
    <div class="nle-status-footer">
        <div class="nle-footer-credits">
            <span>Developed by <strong>Ashish Pingale</strong></span>
            <a href="https://github.com/ashishh-pingale" target="_blank" rel="noopener noreferrer" class="nle-footer-link">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
                </svg>
                <span>GitHub Profile</span>
            </a>
        </div>
        <div class="nle-footer-spec">
            <span>AutoClipper Studio • Isolated Workspace • 0 Bytes on C: Drive</span>
        </div>
    </div>
    """)

    # Interactive Event Bindings
    cached_dropdown.change(
        fn=lambda choice: choice or "",
        inputs=[cached_dropdown],
        outputs=[video_input]
    )

    analyze_btn.click(
        fn=analyze_video,
        inputs=[video_input, quality_dropdown, codec_dropdown, model_dropdown, clipping_mode, duration_dropdown, parts_count_dropdown],
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
    print("[AutoClipper] Launching NLE Studio UI on http://127.0.0.1:7860...")
    try:
        demo.launch(server_name="127.0.0.1", server_port=7860, inbrowser=True, allowed_paths=[str(PROJECT_ROOT)])
    except OSError:
        print("[AutoClipper] Port 7860 is already in use. Launching on the next available open port...")
        demo.launch(server_name="127.0.0.1", inbrowser=True, allowed_paths=[str(PROJECT_ROOT)])
