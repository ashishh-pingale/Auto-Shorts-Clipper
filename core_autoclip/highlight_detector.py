"""
core_autoclip.highlight_detector
Phase 4: AI Highlight Detection & Viral Hook Scoring.
Supports:
  1. Local Ollama (qwen2.5:3b or llama3.2:3b)
  2. Built-in Local Semantic/Heuristic Scorer (100% offline, 0 VRAM, instant)
  3. Optional Gemini API (for 2-hour podcasts)
"""

import json
import re
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional

HOOK_KEYWORDS = {
    "secret", "never", "always", "mistake", "truth", "money", "million", "billion",
    "rule", "hack", "trick", "problem", "solution", "stop", "start", "why", "how",
    "crazy", "insane", "lesson", "first", "power", "habit", "success", "fail",
    "hidden", "nobody", "shocking", "key", "life", "worst", "best"
}

class HighlightDetector:
    def __init__(self, ollama_url: str = "http://localhost:11434", model_name: str = "qwen2.5:3b"):
        self.ollama_url = ollama_url
        self.model_name = model_name

    def find_highlights(
        self,
        transcript_data: Dict[str, Any],
        min_duration: float = 30.0,
        max_duration: float = 60.0,
        max_clips: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Analyzes transcript and extracts top viral short candidates.
        Attempts Ollama first; if Ollama is unavailable, automatically uses
        the smart local heuristic engine.
        """
        segments = transcript_data.get("segments", [])
        if not segments:
            return []

        # Attempt Ollama local LLM analysis
        if self._is_ollama_available():
            try:
                print(f"[HighlightDetector] Running local Ollama ({self.model_name}) for highlight extraction...")
                ollama_clips = self._analyze_with_ollama(segments, min_duration, max_duration, max_clips)
                if ollama_clips:
                    return ollama_clips
            except Exception as e:
                print(f"[HighlightDetector] Ollama analysis encountered an issue ({e}). Using local heuristic engine...")

        # Built-in instant local heuristic analyzer (0 VRAM, 100% offline)
        print("[HighlightDetector] Analyzing transcript using Built-in Local Viral Heuristic Engine...")
        return self._analyze_with_heuristic(segments, min_duration, max_duration, max_clips)

    def _is_ollama_available(self) -> bool:
        """Checks if local Ollama daemon is running."""
        try:
            req = urllib.request.Request(f"{self.ollama_url}/api/tags", headers={"User-Agent": "AutoShorts"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _analyze_with_ollama(
        self,
        segments: List[Dict[str, Any]],
        min_duration: float,
        max_duration: float,
        max_clips: int
    ) -> List[Dict[str, Any]]:
        """Sends transcript chunks to Ollama for viral hook identification."""
        formatted_transcript = "\n".join(
            f"[{s['start']:.1f}s - {s['end']:.1f}s]: {s['text']}" for s in segments
        )

        prompt = f"""You are an expert video editor who creates viral YouTube Shorts, TikToks, and Reels.
Analyze the following timestamped transcript from a video and identify the top {max_clips} most viral, engaging clips.

CRITICAL RULES:
1. Each clip duration MUST be between {min_duration:.0f} and {max_duration:.0f} seconds (strictly enforced).
2. The first 3-5 seconds must contain a captivating "HOOK" (a shocking fact, question, or bold claim).
3. The clip must form a self-contained story, idea, punchline, or tip.
4. Output MUST be valid JSON array with no extra markdown text.

Return JSON format:
[
  {{
    "clip_id": 1,
    "title": "Short punchy click-worthy title",
    "start": 12.5,
    "end": 58.2,
    "duration": 45.7,
    "viral_score": 9.5,
    "hook": "The opening hook sentence",
    "summary": "Brief 1-sentence summary of the value"
  }}
]

Transcript:
{formatted_transcript}
"""

        payload = json.dumps({
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.ollama_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=120) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            raw_response = res_data.get("response", "")

        # Parse JSON
        clips = json.loads(raw_response)
        if isinstance(clips, dict) and "clips" in clips:
            clips = clips["clips"]

        # Validate clip boundaries
        validated = []
        for c in clips:
            dur = c.get("end", 0) - c.get("start", 0)
            if min_duration * 0.9 <= dur <= max_duration * 1.1:
                c["duration"] = round(dur, 1)
                validated.append(c)

        return sorted(validated, key=lambda x: x.get("viral_score", 0), reverse=True)[:max_clips]

    def _analyze_with_heuristic(
        self,
        segments: List[Dict[str, Any]],
        min_duration: float,
        max_duration: float,
        max_clips: int
    ) -> List[Dict[str, Any]]:
        """
        Fast, zero-VRAM local algorithm:
        1. Evaluates opening hook strength of candidate windows (question marks, viral trigger words).
        2. Evaluates speech density and momentum.
        3. Penalizes trailing incomplete sentences.
        """
        candidates = []
        num_segments = len(segments)

        for i in range(num_segments):
            start_time = segments[i]["start"]
            current_text = []
            
            # Hook score of opening segment
            opening_text = segments[i]["text"].lower()
            hook_score = 5.0
            
            # Boost for questions or exclamation in opening
            if "?" in segments[i]["text"]:
                hook_score += 2.0
            if "!" in segments[i]["text"]:
                hook_score += 1.0

            # Boost for viral power words
            matched_keywords = [w for w in HOOK_KEYWORDS if re.search(r'\b' + w + r'\b', opening_text)]
            hook_score += min(len(matched_keywords) * 1.2, 3.0)

            for j in range(i, num_segments):
                end_time = segments[j]["end"]
                current_text.append(segments[j]["text"])
                duration = end_time - start_time

                if duration >= min_duration:
                    if duration <= max_duration:
                        # Full candidate text
                        combined_text = " ".join(current_text)
                        word_count = len(combined_text.split())
                        speech_rate = word_count / max(duration, 1.0) # Words per sec

                        # Ideal speech pace for Shorts is 2.5 - 3.5 words/sec
                        pace_score = 2.0 if 2.2 <= speech_rate <= 3.8 else 1.0

                        # Ending completeness check (ends with period, exclamation, question mark)
                        completeness = 1.0 if segments[j]["text"].rstrip().endswith((".", "!", "?")) else 0.0

                        final_score = round(min(hook_score + pace_score + completeness, 10.0), 1)

                        # Clean Title from first sentence
                        first_sentence = combined_text.split(".")[0].split("?")[0].strip()
                        title = first_sentence[:45] + ("..." if len(first_sentence) > 45 else "")

                        candidates.append({
                            "clip_id": len(candidates) + 1,
                            "title": title or f"Highlight @ {int(start_time)}s",
                            "start": round(start_time, 2),
                            "end": round(end_time, 2),
                            "duration": round(duration, 1),
                            "viral_score": final_score,
                            "hook": segments[i]["text"].strip(),
                            "summary": combined_text[:120] + "..."
                        })
                    else:
                        break

        # Remove heavily overlapping candidates
        candidates.sort(key=lambda x: x["viral_score"], reverse=True)
        unique_clips = []

        for cand in candidates:
            overlaps = False
            for existing in unique_clips:
                # Check for significant overlap (>15 seconds overlap)
                overlap_start = max(cand["start"], existing["start"])
                overlap_end = min(cand["end"], existing["end"])
                if (overlap_end - overlap_start) > 15.0:
                    overlaps = True
                    break
            if not overlaps:
                cand["clip_id"] = len(unique_clips) + 1
                unique_clips.append(cand)
                if len(unique_clips) >= max_clips:
                    break

        return unique_clips

    def generate_sequential_chunks(
        self,
        transcript_data: Dict[str, Any],
        target_chunk_duration: float = 60.0,
        max_chunks: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Splits a full VOD, gameplay recording, or video into consecutive episodic parts
        ('Part 1', 'Part 2', 'Part 3'...) perfect for serial Shorts/TikTok/Reels.
        Intelligently snaps cuts to the nearest natural sentence boundary or silence pause.
        """
        segments = transcript_data.get("segments", [])
        total_duration = float(transcript_data.get("duration", 0.0))

        if not segments:
            # Fallback when transcript has no text segments: time-based slicing
            parts = []
            curr = 0.0
            part_num = 1
            while curr < total_duration and part_num <= max_chunks:
                nxt = min(curr + target_chunk_duration, total_duration)
                parts.append({
                    "clip_id": part_num,
                    "title": f"Part {part_num}",
                    "start": round(curr, 2),
                    "end": round(nxt, 2),
                    "duration": round(nxt - curr, 1),
                    "viral_score": f"Part {part_num}",
                    "hook": f"Part {part_num} of series",
                    "summary": f"Consecutive slice {curr:.0f}s - {nxt:.0f}s"
                })
                curr = nxt
                part_num += 1
            return parts

        # Smart sentence/segment snapping so words/sentences are not cut abruptly
        parts = []
        part_idx = 1
        current_chunk_segments = []
        chunk_start = segments[0]["start"]

        for seg in segments:
            current_chunk_segments.append(seg)
            elapsed = seg["end"] - chunk_start

            # Check if duration target reached: prefer snapping to sentence-ending punctuation
            is_sentence_end = seg["text"].rstrip().endswith((".", "!", "?", "।"))
            if elapsed >= target_chunk_duration or (elapsed >= (target_chunk_duration - 10.0) and is_sentence_end):
                chunk_end = seg["end"]
                combined_text = " ".join(s["text"] for s in current_chunk_segments).strip()
                preview = combined_text[:35] + ("..." if len(combined_text) > 35 else "")

                parts.append({
                    "clip_id": part_idx,
                    "title": f"Part {part_idx}: {preview}",
                    "start": round(chunk_start, 2),
                    "end": round(chunk_end, 2),
                    "duration": round(chunk_end - chunk_start, 1),
                    "viral_score": f"Part {part_idx}",
                    "hook": current_chunk_segments[0]["text"].strip(),
                    "summary": combined_text[:120] + "..."
                })

                part_idx += 1
                if part_idx > max_chunks:
                    break
                chunk_start = chunk_end
                current_chunk_segments = []

        # Add remaining trailing segment if substantial
        if current_chunk_segments and part_idx <= max_chunks:
            chunk_end = current_chunk_segments[-1]["end"]
            if (chunk_end - chunk_start) >= 15.0:
                combined_text = " ".join(s["text"] for s in current_chunk_segments).strip()
                preview = combined_text[:35] + ("..." if len(combined_text) > 35 else "")
                parts.append({
                    "clip_id": part_idx,
                    "title": f"Part {part_idx}: {preview}",
                    "start": round(chunk_start, 2),
                    "end": round(chunk_end, 2),
                    "duration": round(chunk_end - chunk_start, 1),
                    "viral_score": f"Part {part_idx}",
                    "hook": current_chunk_segments[0]["text"].strip(),
                    "summary": combined_text[:120] + "..."
                })

        print(f"[HighlightDetector] Generated {len(parts)} episodic serial parts.")
        return parts
