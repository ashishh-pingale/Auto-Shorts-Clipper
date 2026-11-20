"""
core_autoclip.subtitle_generator
Phase 7: Dynamic Animated Karaoke Captions (.ass).
Generates mobile-optimized vertical subtitles with active word-level pop-in / highlight
in viral styles (MrBeast Electric Yellow, Alex Hormozi Bold, TikTok Green).
"""

import unicodedata
from pathlib import Path
from typing import List, Dict, Any

# Devanagari Unicode combining marks: matras, signs, halant/virama
DEVANAGARI_COMBINING_MARKS = set(range(0x0901, 0x0904)) | set(range(0x093A, 0x0950))

class SubtitleGenerator:
    def __init__(
        self,
        font_name: str = "Nirmala UI",           # Universal Windows font with native Hindi/Devanagari + clean Latin
        font_size: int = 56,
        primary_color: str = "&H00FFFFFF",       # Default text color: Pure White (AABBGGRR)
        highlight_color: str = "&H0000D7FF",     # Active karaoke word: Electric Gold/Yellow
        outline_color: str = "&H00000000",       # Outline: Pure Black
        outline_width: int = 4,
        words_per_line: int = 3                  # 2-4 words per line for clean vertical mobile layout
    ):
        self.font_name = font_name
        self.font_size = font_size
        self.primary_color = primary_color
        self.highlight_color = highlight_color
        self.outline_color = outline_color
        self.outline_width = outline_width
        self.words_per_line = words_per_line

    def _format_ass_time(self, seconds: float) -> str:
        """Converts float seconds to ASS format: H:MM:SS.cs"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int(round((seconds - int(seconds)) * 100))
        if cs >= 100:
            s += 1
            cs -= 100
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    def _clean_word(self, raw_text: str) -> str:
        """Normalizes Unicode (NFC) and preserves Hindi ligatures without case mangling."""
        text = unicodedata.normalize('NFC', raw_text.strip())
        has_devanagari = any('\u0900' <= char <= '\u097F' for char in text)
        if not has_devanagari:
            text = text.upper()
        return text

    def generate_karaoke_ass(
        self,
        words: List[Dict[str, Any]],
        output_ass_path: str,
        screen_w: int = 1080,
        screen_h: int = 1920
    ) -> str:
        """
        Creates an Advanced SubStation Alpha (.ass) file with word-by-word karaoke highlight.
        Includes full support for Hindi / Devanagari ligatures (Nirmala UI) and prevents orphan dotted circles.
        """
        out_p = Path(output_ass_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        # Responsive margin and line length based on aspect ratio
        if screen_w > screen_h:
            margin_v = 110
            effective_words_per_line = 6
        else:
            margin_v = 340
            effective_words_per_line = self.words_per_line

        # Spacing=0 is critical for Devanagari so matras do not detach into dotted circles
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {screen_w}
PlayResY: {screen_h}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: KaraokeDefault,{self.font_name},{self.font_size},{self.primary_color},&H000000FF,{self.outline_color},&H80000000,-1,0,0,0,100,100,0,0,1,{self.outline_width},2,2,40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        dialogue_lines = []

        if not words:
            out_p.write_text(header, encoding="utf-8")
            return str(out_p)

        # Sanitize words: merge orphan combining matras that Whisper may have split across tokens
        sanitized_words = []
        for w in words:
            cleaned = self._clean_word(w.get("word", ""))
            if not cleaned:
                continue
            # If word starts with an orphan matra, merge with previous word to fix the dotted circle
            if sanitized_words and ord(cleaned[0]) in DEVANAGARI_COMBINING_MARKS:
                sanitized_words[-1]["word"] += cleaned
                sanitized_words[-1]["end"] = max(sanitized_words[-1]["end"], w.get("end", sanitized_words[-1]["end"]))
            else:
                # Strip orphan combining marks at start of standalone word
                if ord(cleaned[0]) in DEVANAGARI_COMBINING_MARKS:
                    cleaned = cleaned.lstrip(''.join(chr(c) for c in DEVANAGARI_COMBINING_MARKS))
                if cleaned:
                    new_item = dict(w)
                    new_item["word"] = cleaned
                    sanitized_words.append(new_item)

        # Group words into clean lines
        chunks = []
        for i in range(0, len(sanitized_words), effective_words_per_line):
            chunk = sanitized_words[i:i + effective_words_per_line]
            chunks.append(chunk)

        for chunk in chunks:
            for active_idx, active_word in enumerate(chunk):
                w_start = active_word["start"]
                w_end = active_word["end"]
                start_str = self._format_ass_time(w_start)
                end_str = self._format_ass_time(w_end)

                formatted_words = []
                for idx, w in enumerate(chunk):
                    word_str = w["word"]
                    if idx == active_idx:
                        # Highlighted active word with pop-in scale tag
                        formatted_words.append(f"{{\\c{self.highlight_color}\\fscx108\\fscy108}}{word_str}{{\\r}}")
                    else:
                        # Normal white text
                        formatted_words.append(f"{{\\c{self.primary_color}}}{word_str}{{\\r}}")

                line_text = " ".join(formatted_words)
                dialogue_lines.append(f"Dialogue: 0,{start_str},{end_str},KaraokeDefault,,0,0,0,,{line_text}")

        full_content = header + "\n".join(dialogue_lines) + "\n"
        out_p.write_text(full_content, encoding="utf-8")
        print(f"[SubtitleGenerator] Generated animated ASS subtitles ({self.font_name}): {out_p.name} ({len(dialogue_lines)} events)")
        return str(out_p)
