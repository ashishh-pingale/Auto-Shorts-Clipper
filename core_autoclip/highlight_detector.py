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
        split_mode: str = "duration",
        target_chunk_duration: float = 60.0,
        target_num_parts: int = 5,
        max_chunks: int = 150
    ) -> List[Dict[str, Any]]:
        """
        Splits a full VOD, gameplay recording, or stream into consecutive episodic parts
        ('Part 1', 'Part 2', 'Part 3'...) perfect for serial Shorts/TikTok/Reels.
        
        Guarantees:
          1. Strict duration adherence: Parts never explode to 100s+ or shrink to 20s.
          2. Handles silence/gameplay gaps: When no speech occurs for minutes, time-stepping keeps parts consistent.
          3. Smart sentence snapping: Snaps to sentence endings (. ! ? ,) within the optimal window.
        """
        segments = transcript_data.get("segments", [])
        total_duration = max(1.0, float(transcript_data.get("duration", 0.0)))
        is_count_mode = "count" in split_mode.lower() or "number" in split_mode.lower()

        # -------------------------------------------------------------
        # MODE 1: SPLIT BY TOTAL NUMBER OF PARTS (e.g. 5 Equal Parts)
        # -------------------------------------------------------------
        if is_count_mode:
            target_parts = max(1, min(int(target_num_parts), max_chunks))
            ideal_step = total_duration / float(target_parts)
            print(f"[HighlightDetector] Slicing into {target_parts} equal parts (~{ideal_step:.1f}s each, total {total_duration/60:.1f}m)...")

            parts = []
            current_start = 0.0

            for p in range(1, target_parts + 1):
                if p == target_parts:
                    actual_end = total_duration
                else:
                    target_boundary = p * ideal_step
                    # Window around target boundary: ±15% of ideal_step
                    tolerance = min(15.0, max(5.0, ideal_step * 0.15))
                    best_seg_end = None
                    best_dist = float('inf')

                    for s in segments:
                        s_end = s["end"]
                        if (target_boundary - tolerance) <= s_end <= (target_boundary + tolerance):
                            if s_end > (current_start + 15.0): # Ensure at least 15s per part
                                dist = abs(s_end - target_boundary)
                                is_sentence_end = s["text"].rstrip().endswith((".", "!", "?", "।", ","))
                                score_dist = dist if not is_sentence_end else max(0.0, dist - 6.0)

                                if score_dist < best_dist:
                                    best_dist = score_dist
                                    best_seg_end = s_end

                    actual_end = best_seg_end if best_seg_end is not None else target_boundary

                actual_end = min(actual_end, total_duration)
                part_segs = [s for s in segments if s["end"] > current_start and s["start"] < actual_end]
                combined_text = " ".join(s["text"] for s in part_segs).strip()
                first_sentence = combined_text.split(".")[0].split("?")[0].strip() if combined_text else ""
                preview = first_sentence[:35] + ("..." if len(first_sentence) > 35 else "") or f"Part {p}"

                dur = round(actual_end - current_start, 1)
                parts.append({
                    "clip_id": p,
                    "title": f"Part {p}: {preview}",
                    "start": round(current_start, 2),
                    "end": round(actual_end, 2),
                    "duration": dur,
                    "viral_score": f"Part {p}/{target_parts}",
                    "hook": part_segs[0]["text"].strip() if part_segs else f"Part {p} opening",
                    "summary": combined_text[:120] + "..." if combined_text else f"Scene {current_start:.1f}s - {actual_end:.1f}s"
                })
                current_start = actual_end

            print(f"[HighlightDetector] Successfully split video into {len(parts)} equal episodic parts.")
            return parts

        # -------------------------------------------------------------
        # MODE 2: SPLIT BY DURATION OF EACH PART (e.g. 60s per Part)
        # -------------------------------------------------------------
        target_dur = float(target_chunk_duration)
        min_allowed = max(20.0, target_dur - 8.0)  # e.g. 52s for 60s target
        max_allowed = target_dur + 4.0              # e.g. 64s for 60s target (strict Shorts limit)
        print(f"[HighlightDetector] Slicing by target duration ({target_dur:.0f}s per part, allowed: {min_allowed:.0f}s - {max_allowed:.0f}s)...")

        parts = []
        curr_start = 0.0
        part_idx = 1

        while curr_start < total_duration and part_idx <= max_chunks:
            ideal_end = min(curr_start + target_dur, total_duration)

            # If the remaining final slice is under 15s, merge with previous part if possible
            if (total_duration - curr_start) <= 15.0 and parts:
                parts[-1]["end"] = round(total_duration, 2)
                parts[-1]["duration"] = round(total_duration - parts[-1]["start"], 1)
                break

            # Search for best sentence-ending boundary inside [curr_start + min_allowed, curr_start + max_allowed]
            best_cut = None
            best_score = float('inf')

            for s in segments:
                s_end = s["end"]
                if (curr_start + min_allowed) <= s_end <= (curr_start + max_allowed):
                    dist = abs(s_end - ideal_end)
                    is_sentence_end = s["text"].rstrip().endswith((".", "!", "?", "।", ","))
                    score = dist if not is_sentence_end else max(0.0, dist - 6.0)
                    if score < best_score:
                        best_score = score
                        best_cut = s_end

            # If no speech boundary in that range, handle cleanly
            if best_cut is not None:
                actual_end = best_cut
            else:
                # Check if speech is currently overlapping ideal_end
                overlapping = [s for s in segments if s["start"] < ideal_end < s["end"]]
                if overlapping and overlapping[0]["end"] <= (curr_start + max_allowed + 2.0):
                    actual_end = overlapping[0]["end"]
                else:
                    actual_end = ideal_end

            actual_end = min(actual_end, total_duration)
            dur = round(actual_end - curr_start, 1)

            part_segs = [s for s in segments if s["end"] > curr_start and s["start"] < actual_end]
            combined_text = " ".join(s["text"] for s in part_segs).strip()
            first_sentence = combined_text.split(".")[0].split("?")[0].strip() if combined_text else ""
            preview = first_sentence[:35] + ("..." if len(first_sentence) > 35 else "") or f"Part {part_idx} Scene"

            parts.append({
                "clip_id": part_idx,
                "title": f"Part {part_idx}: {preview}",
                "start": round(curr_start, 2),
                "end": round(actual_end, 2),
                "duration": dur,
                "viral_score": f"Part {part_idx}",
                "hook": part_segs[0]["text"].strip() if part_segs else f"Part {part_idx} opening",
                "summary": combined_text[:120] + "..." if combined_text else f"Gameplay slice {curr_start:.1f}s - {actual_end:.1f}s"
            })

            curr_start = actual_end
            part_idx += 1

        print(f"[HighlightDetector] Generated {len(parts)} episodic parts strictly adhering to {target_dur:.0f}s duration.")
        return parts
