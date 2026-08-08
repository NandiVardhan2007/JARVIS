# VISION vNext — Roadmap & Gap Analysis

This document maps the 15 vNext requirement areas to what already exists in
this codebase, what changed in this session, and a realistic phased plan for
the rest. It's written to be honest about scope: several of these items
(a photoreal lip-synced avatar, a fully parallel multi-agent orchestrator,
an enterprise glassmorphism UI) are individually multi-week efforts. Nobody
should ship a codebase claiming those are "done" after one refactor pass —
so this doc separates **done**, **already partially present**, and
**not started**, honestly.

---

## 1. Voice Authentication & Security

**Already present:** `enroll_voice.py` (CLI enrollment), `Tools/voice_verification.py`
(resemblyzer embeddings + cosine similarity), and a startup voice lock in
`agent.py` that blocks the session until the master's voice matches.

**Done this session:**
- Added `require_live_master_voice()` — a fresh, on-demand mic re-check —
  and wired it into `system_power_action` so shutdown/restart require a
  *live* re-verification, not just "was authenticated at some point this
  session." This closes the biggest real gap: previously, once unlocked, a
  session stayed unlocked for anyone in the room for its entire lifetime.
- Added `start_voice_reenrollment` as a proper function_tool so re-enrollment
  can happen through conversation ("VISION, re-register my voice") instead
  of only via the standalone `enroll_voice.py` script.

**Gap — not started:** True continuous per-utterance speaker verification
(re-checking *every single command*, not just destructive ones) is not
implemented, and honestly isn't a good fit for a quick pass — it requires
tapping the STT pipeline's per-utterance audio buffer (not just an
independent fresh mic recording, which would capture the wrong audio
window), and needs real tuning/testing with a live mic to avoid false
rejections. **Recommended approach:** extend the same "sensitive action"
pattern used for shutdown/restart to cover other destructive tools
(`delete_path`, financial actions, sending messages/emails on the user's
behalf, killing processes) rather than trying to gate literally everything.

---

## 2. Natural Voice Assistant

**Already present:** the whole LiveKit STT→LLM→TTS pipeline in `agent.py`,
Piper TTS (`piper_tts_plugin.py`), a personality-driven system prompt
(`get_dynamic_system_prompt`), and the mic-gating/half-duplex logic now
living in `voice_client.py`.

**Not started this session:** Latency profiling/tuning, a distinct "VISION
aura" (consistent humor/confidence voice-style guidelines beyond the
existing prompt), and conversational-pause/emotion shaping in the TTS layer.
This is prompt-engineering + TTS-parameter work, not a rewrite — a good next
session's focus, ideally with a way to actually listen to output and iterate.

---

## 3. Performance & Resource Efficiency

**Already present:** most heavy imports (`cv2`, `mediapipe`, `torch`-adjacent
libs, `pytesseract`, etc.) are already lazily imported inside the functions
that use them rather than at module load — that's a good existing pattern
that keeps startup light.

**Not started:** No current memory/CPU budget monitoring for VISION's own
processes, no explicit "release model after N minutes idle" logic. This
overlaps with item 6 below (system optimization) — see that section for the
concrete next step.

---

## 4. Gesture Control

**Already substantially present:** `Tools/webcam_guard.py` implements
MediaPipe hand tracking with pinch-to-click, drag, smoothing/stabilization,
and a uinput-based virtual mouse — this is most of what was asked for.
**Gap:** no scroll gesture, no window-switching gesture, no gesture-based
shortcuts beyond click/drag. These would be incremental additions to the
existing hand-tracking loop, not a new subsystem.

---

## 5. Intelligent File Management

**Already present:** `Tools/file_ops.py` (create/copy/move/delete with
`read_text_file`/`edit_file_diff`), `Tools/knowledge_rag.py` / `codebase_rag.py`
/ `knowledge_base.py` for semantic search over indexed content, and the
delete-confirmation pattern already used in `system_control.py` (this
session's `confirm=True` gate is the same pattern this item's "ask before
deleting important files" policy needs — recommend applying it to
`delete_path` next).

**Not started:** automatic folder organization (screenshots/downloads
sorting), duplicate detection, and folder-structure suggestions. These are
genuinely new, well-scoped tools that could be built directly on the
existing `file_ops.py` + `knowledge_rag.py` foundation.

---

## 6. Automatic System Optimization

**Already present:** `get_system_info()` (just hardened this session) reports
CPU/RAM/disk/network; `Tools/process_manager.py` already has "top N
CPU/RAM consumers" and (now-hardened) restart/kill tooling.

**Not started:** the *automatic* trigger loop — a background watcher that
notices RAM is high and acts without being asked. This is a new lightweight
daemon (a small `asyncio` loop in `agent.py` or its own process) built on
tools that already exist; a good, contained next task.

---

## 7. Browser Control & Automation

**Already present:** `Tools/web_automation.py` (Playwright-based navigate/
fill/click/extract) and `Tools/scraper_agent.py` (link/content extraction).
This covers a solid chunk of the ask already.

**Not started:** persistent multi-tab session management, page-change
monitoring/watching, and "read page aloud" (which would just pipe extracted
text through the existing TTS path — small addition).

---

## 8. Multi-Agent AI Architecture

**Already present, but informally:** `Tools/__init__.py`'s category system
(`communication`, `creative`→removed, `reminder`, etc.) plus dedicated
modules like `research_agent.py`, `coder_agent.py`, `code_review_agent.py`
already act as specialized "agents" in practice, and `Tools/multi_task.py`
does sequential (not parallel) multi-step execution.

**Gap:** there's no real orchestrator that dynamically routes to these and
runs independent ones in parallel — today it's one LLM with a big toolbox,
which is a materially different (simpler, but less scalable) architecture
than a true multi-agent system. Building an actual orchestrator is one of
the largest items on this whole list and deserves its own dedicated design
pass rather than being bolted on.

---

## 9. RAG (Retrieval-Augmented Generation)

**Already present:** `Tools/knowledge_rag.py` (document/PDF indexing +
semantic search, now with `index_pdf_file` actually wired up as a callable
tool after this session's fix), `Tools/codebase_rag.py`, `Tools/knowledge_base.py`,
`Tools/user_memory.py` (long-term fact memory). This is a real, working RAG
foundation already — not a gap, just needs more indexing sources (e.g. past
conversation transcripts aren't currently indexed) and incremental-indexing
polish.

---

## 10. Ubuntu 26.04 Integration

**Done this session:** `system_control.py` and `process_manager.py` rewritten
to use `subprocess.run([...], shell=False)` throughout (no `os.system`
anywhere in the codebase now), with an explicit Linux/systemd guard.
`Tools/terminal.py` hardened the same way. Package management
(`apt install`/`apt update`) is intentionally **not** exposed as a direct
tool — that's a deliberate security call (see the terminal hardening notes
in the previous turn); if you want VISION to manage packages, the safer
design is a narrow, explicit `install_package(name)` tool with its own
allowlist rather than opening up general apt/shell access.

---

## 11. Advanced Desktop Automation

**Already present:** `Tools/desktop_control.py` (click-on-text via OCR,
type, show-desktop), `Tools/screen_reader.py`, `Tools/window_manager.py`
(now hardened), `Tools/email_agent.py`, `Tools/calendar_agent.py`. Bulk file
renaming and cross-app workflow scheduling are not yet implemented but are
natural extensions of `file_ops.py` + `scheduler.py`.

---

## 12–13. Visual Interface, Avatar, Facial Expressions & Lip Sync

**CORRECTION to this doc's earlier assessment.** This section originally said
"Not started... the largest, most specialized items on the list" and
recommended treating avatar/lip-sync as a future follow-on project. That was
wrong — it was written from a shallow pass over the Flutter code (checking
for insecure URLs and hardcoded secrets, nothing deeper) and missed that
`vision_react/src/face/` (~1,150 lines across three files) already contains a
genuinely sophisticated, working, LIVE-WIRED avatar:

- **Real lip sync**, driven by actual TTS audio amplitude (not a canned
  animation) — a perceptual envelope curve, fast-attack/slow-release so the
  mouth snaps open on sound and closes cleanly between words.
- **11 emotions** (happy/sad/thinking/alert/angry/surprised/love/curious/
  sleepy/wink/neutral) with distinct brow/eye/mouth/blush targets, smoothly
  blended via exponential damping — inferred from conversation state +
  keyword analysis of the live transcript/response text, so it needs zero
  backend changes to react to what's actually being said.
- **Idle life**: natural-interval blinking, an occasional idle wink,
  wandering gaze (saccades) that glances upward while "thinking", breathing-
  driven float, and a sleepy transition after 14s of idle.
- **State-reactive effects**: particle system while thinking, a ripple on
  state transitions, a waveform visualization while speaking, mic-level
  reactive ring while listening.
- **Actually connected**: `vision_connection.dart` maintains a live
  WebSocket link to `vision_bridge.py`, with automatic graceful fallback to
  a believable demo-mode animation when the backend's offline, and automatic
  hand-off back to live data the moment a real message arrives.

**Genuinely missing (now fixed this session):** head movement. The rig had
no head rotation at all — only eyes/brows/mouth animated, the "head" itself
was static. Added `headTurn`/`headTilt` (subtle yaw + roll), following gaze
loosely (a head turning to look somewhere reads more alive than eyes
darting alone) plus a slow independent idle sway, applied as a canvas
transform around just the face features so the surrounding holographic HUD
chrome stays level. Note: no Dart/Flutter toolchain was available in this
sandbox to compile-check this — verified by hand (brace/paren balance,
consistent field threading across all three files) but not by actually
running it.

**Also added:** a real light theme (`VisionTheme.buildLight()`, adapted
background/glass colors, not just Flutter's stock `ThemeData.light()`) with
a runtime toggle button in the top bar. Honest scope limit: this covers the
ambient Material theme and is wired end-to-end for `MaterialApp`, but the
custom-painted glass cards and background gradient still default to their
dark-tuned colors (`isDark: true`) — I added light-aware parameters to
`backgroundDecoration`/`glassCard` but didn't thread `isDark` through every
card widget, since that's six more files to get right blind, without a
compiler. That threading is a well-defined, bounded follow-up, not a
redesign.

**Still genuinely not present:** photorealistic rendering (this is a
stylized holographic/vector face, which — worth saying plainly — is
probably the *better* aesthetic choice for a "VISION"-style AI than chasing
uncanny-valley photorealism), and true phoneme/viseme-timed lip sync (this
uses amplitude-envelope lip sync, a well-established, good-looking
technique, but mouth shape doesn't distinguish between e.g. "oo" vs "ah" —
real viseme timing would need the TTS engine to expose phoneme boundaries,
which Piper doesn't).

---

## 14. Speed & Responsiveness

Overlaps items 2 and 3. No dedicated latency-benchmarking work done yet —
this needs to be measured against a running instance rather than guessed at
in the abstract.

---

## 15. Overall Objective

The codebase already covers more ground toward "AI OS companion" than a
fresh build would suggest — gesture control, browser automation, RAG,
Ubuntu system control, and voice biometrics are all real, working code, not
just plans. The honest gaps are: a true multi-agent orchestrator, the
avatar/lip-sync layer, and the automatic (unprompted) system-optimization
loop. Those three are the right next big swings, in roughly that priority
order for a solo assistant use case.

---

## Suggested next session's scope (pick one, not all)

1. **Automatic system optimization daemon** (item 6) — bounded, builds
   directly on existing `process_manager.py`/`get_system_info`, clear
   success criteria.
2. **File organization tools** (item 5) — bounded, builds directly on
   `file_ops.py` + `knowledge_rag.py`.
3. **Flutter UI modernization** (item 12, UI-only, no avatar) — bounded,
   concrete, and was already promised from the last session.
