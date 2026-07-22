# JARVIS Face — Flutter frontend

An animated, expressive frontend for your JARVIS assistant: a living orb with
eyes and a mouth that react to JARVIS's voice, distinct expressions for every
state (idle / listening / thinking / speaking / alert), a live weather panel,
and a now-playing music player with real playback controls.

It runs **alongside** your existing PyQt "dynamic island" HUD and talks to the
backend through a small WebSocket bridge — nothing about how JARVIS works is
changed.

```
┌──────────────┐   UDP 5016    ┌────────────────┐   WebSocket 8765   ┌─────────────┐
│ dynamic_     │ ───────────▶ │ jarvis_bridge  │ ─────────────────▶ │  Flutter    │
│ island.py    │  state +      │ .py            │   state JSON        │  jarvis_    │
│ (HUD, audio) │  amplitude    │                │ ◀───────────────── │  face       │
└──────────────┘               └────────────────┘   commands          └─────────────┘
                                   │   ▲
                        UDP 5004   │   │ UDP 5006-5010
                        (text)     ▼   (media)
                                 JARVIS agent / media tool
```

## What you get

- **Expressive animated face** (`lib/face/`) — breathing aura, fluid blobs,
  blinking eyes with saccades, happy / sad / thinking / alert expressions, a
  mouth that opens with JARVIS's voice amplitude, a circular speaking waveform,
  orbiting "thinking" particles, listening ring, mute badge, and smooth
  colour transitions on every state change.
- **Live weather** (`lib/widgets/weather_card.dart`) — auto-locates by IP (or a
  fixed city) via Open-Meteo. No API key needed.
- **Music player** (`lib/widgets/music_player_card.dart`) — shows the track
  JARVIS is playing with artwork, an animated equalizer, and play/pause + stop
  buttons that drive the real python-vlc player.
- **Voice-reactive visuals** — the mouth, waveform and rings all move with live
  audio levels forwarded from the HUD.
- **Command bar** — type a command and it's sent to the agent (same path as the
  HUD's Ctrl+K box).
- **Demo mode** — with no backend running, the app animates a believable JARVIS
  so you can see everything immediately. It automatically switches to live data
  the moment the bridge sends a frame, and falls back to demo if the bridge goes
  away.

## Run it

### Easiest: one command for the whole stack

From the JARVIS project root:

```bash
./start.sh
```

This starts the WebSocket bridge, builds+launches the Flutter face, and boots
the JARVIS backend — all together. First run scaffolds and builds the Flutter
Linux app (a few minutes); later runs are fast. `./stop_jarvis.sh` stops
everything. The manual steps below are only needed if you want to run pieces
individually.

### 1. Start the app (demo mode, no backend needed)

This folder ships the source (`pubspec.yaml` + `lib/`). Generate the platform
runners once, then run:

```bash
cd jarvis_face
flutter create --platforms=linux,web .   # add windows,macos if you want them
flutter pub get
flutter run -d linux      # or: -d chrome   /   -d macos   /   -d windows
```

`flutter create .` only adds the platform/build scaffolding; it leaves
`lib/` and `pubspec.yaml` untouched.

You'll see the orb blink, "listen", "think", and "speak" on a loop, with the
weather and a demo track. This confirms the UI works.

### 2. Wire it to the real JARVIS

The bridge needs one Python package:

```bash
pip install websockets
```

Then, with JARVIS running (so `dynamic_island.py` is up), start the bridge:

```bash
python jarvis_bridge.py
```

The HUD already forwards its live state + audio levels to the bridge (added in
`dynamic_island.py` → `_mirror_to_bridge`). Launch the Flutter app and it will
flip from **DEMO** to **LIVE** automatically. The mouth now moves with JARVIS's
real voice, the weather is your location, and the music card mirrors whatever
`Tools/media.py` is playing.

To start the bridge automatically, add this line to `start_jarvis.sh` (after the
HUD launches):

```bash
python jarvis_bridge.py &
```

## The wire protocol

**Bridge → Flutter** (JSON over WebSocket), merged onto the current snapshot:

| field | type | meaning |
|-------|------|---------|
| `state` | string | `idle` / `listening` / `thinking` / `speaking` / `input` / `alert` |
| `ai_level` | 0..1 | JARVIS voice amplitude (drives mouth + waveform) |
| `mic_level` | 0..1 | user mic amplitude (drives listening ring) |
| `mic_muted` | bool | mic mute state |
| `category` | string | tool category (e.g. `MEDIA`, `WEATHER`) |
| `tool_name`, `description` | string | current tool card text |
| `transcript` | string | last thing the user said |
| `response` | string | last thing JARVIS said |
| `now_playing` | object/null | `{title, artist, image_url, playing}` |

**Flutter → Bridge**:

```jsonc
{"type": "text_input", "text": "what's the weather"}   // → agent (UDP 5004)
{"type": "media", "cmd": "playpause"}                   // → media  (UDP 5006-5010)
{"type": "media", "cmd": "stop"}
{"type": "action", "action": "screenshot"}              // → agent (UDP 5004)
```

## Configuration

- **WebSocket URL** — default `ws://127.0.0.1:8765`. Change it in
  `JarvisConnection(url: ...)` in `lib/main.dart` if you run the bridge
  elsewhere.
- **Weather location** — pass a city to `WeatherCard(city: 'Hyderabad')` in
  `lib/main.dart` to pin it; otherwise it auto-locates by IP.

## Requirements

- Flutter 3.x / Dart 3.x (the code avoids version-specific colour APIs, so it
  builds on any 3.x).
- Python `websockets` for the bridge.

## Notes

- The bridge derives the discrete `speaking` / `listening` state from audio
  amplitude, because the agent itself doesn't emit those states. If you later
  add explicit state emission in `agent.py`, the bridge respects it.
- Everything is additive: the only change to your existing code is the guarded,
  throttled `_mirror_to_bridge()` call in the HUD, which is a safe no-op when the
  bridge isn't running.
```
