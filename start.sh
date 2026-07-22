#!/bin/bash
# ==============================================================================
#  JARVIS — one-command launcher
#  Starts, in order:
#    1. the WebSocket bridge server  (jarvis_bridge.py, ws://127.0.0.1:8765)
#    2. the Flutter face frontend    (jarvis_face/, native Linux window)
#    3. the JARVIS backend           (jarvis_launcher.py -> agent + HUD)
#
#  Ctrl-C (or the backend exiting) shuts all three down cleanly.
# ==============================================================================

set -u
cd "$(dirname "$0")" || exit 1

FLUTTER_DIR="jarvis_face"
BRIDGE="jarvis_bridge.py"
PIDS=()

# A non-interactive ./start.sh does NOT read your shell profiles, so tools you
# added to PATH there (most importantly `flutter`) are invisible — which makes
# this script skip the rebuild and launch a STALE binary. Pull those PATH
# additions in, best-effort. (set +u while sourcing so a profile referencing an
# unset var can't abort us.)
set +u
for _prof in "$HOME/.profile" "$HOME/.bash_profile" "$HOME/.bashrc" \
             "$HOME/.zprofile" "$HOME/.zshrc"; do
    [ -f "$_prof" ] && . "$_prof" >/dev/null 2>&1
done
set -u

echo "=============================================================="
echo "                JARVIS - AI Assistant  (full stack)"
echo "=============================================================="

# ── Clean shutdown ────────────────────────────────────────────────────────────
cleanup() {
    echo ""
    echo "[start] Shutting down..."
    if [ "${#PIDS[@]}" -gt 0 ]; then
        for pid in "${PIDS[@]}"; do
            kill "$pid" 2>/dev/null
        done
    fi
    # Best-effort: also stop anything the launcher/frontend spawned.
    pkill -f "jarvis_launcher.py" 2>/dev/null
    pkill -f "jarvis_bridge.py"   2>/dev/null
    pkill -f "flutter run"        2>/dev/null
    exit 0
}
trap cleanup INT TERM

# ── Linux desktop build toolchain (for the native Flutter window) ─────────────
# Runs in the FOREGROUND so a sudo password prompt actually works. Returns 0 if
# the GTK toolchain is available (installing it if needed).
ensure_linux_toolchain() {
    local missing=()
    command -v clang      >/dev/null 2>&1 || missing+=(clang)
    command -v cmake      >/dev/null 2>&1 || missing+=(cmake)
    command -v ninja      >/dev/null 2>&1 || missing+=(ninja-build)
    command -v pkg-config >/dev/null 2>&1 || missing+=(pkg-config)
    pkg-config --exists gtk+-3.0 2>/dev/null || missing+=(libgtk-3-dev)

    if [ "${#missing[@]}" -eq 0 ]; then
        return 0
    fi

    echo "[ui] Missing Linux desktop build tools: ${missing[*]}"
    if command -v apt-get >/dev/null 2>&1; then
        echo "[ui] Installing them (you may be prompted for your sudo password)..."
        sudo apt-get update && sudo apt-get install -y "${missing[@]}" || return 1
    else
        echo "[ui] Please install these manually, then re-run: ${missing[*]}"
        return 1
    fi
    pkg-config --exists gtk+-3.0 2>/dev/null   # final verdict
}

# ── Python environment ────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] Python 3 is not installed or not on PATH."
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "[start] Creating virtual environment..."
    python3 -m venv venv || { echo "[ERROR] venv creation failed."; exit 1; }
fi
# shellcheck disable=SC1091
source venv/bin/activate

# Make sure the bridge's only extra dependency is present.
if ! python3 -c "import websockets" &>/dev/null; then
    echo "[start] Installing 'websockets' (bridge dependency)..."
    pip install websockets >/dev/null 2>&1 || python3 -m pip install websockets
fi

# ── 1. WebSocket bridge (background) ──────────────────────────────────────────
echo "[start] (1/3) Starting bridge on ws://127.0.0.1:8765 ..."
python3 "$BRIDGE" &
PIDS+=($!)

# ── 2. Flutter frontend ───────────────────────────────────────────────────────
# The shell that runs this script may not have Flutter on PATH even though your
# IDE does — so look in the usual install locations before giving up.
if ! command -v flutter &>/dev/null; then
    for cand in "$HOME/develop/flutter/bin" "$HOME/flutter/bin" \
                "$HOME/development/flutter/bin" "$HOME/dev/flutter/bin" \
                "$HOME/tools/flutter/bin" "$HOME/snap/flutter/common/flutter/bin" \
                "$HOME/.local/flutter/bin" "$HOME/.local/bin" \
                "/opt/flutter/bin" "/usr/lib/flutter/bin" \
                "/usr/local/flutter/bin" "/snap/flutter/current/bin" "/snap/bin"; do
        if [ -x "$cand/flutter" ]; then
            export PATH="$PATH:$cand"
            echo "[ui] Found Flutter at: $cand"
            break
        fi
    done
fi
# Last-ditch search under the home dir (bounded so it stays fast).
if ! command -v flutter &>/dev/null; then
    _f="$(find "$HOME" -maxdepth 5 -type f -name flutter -path '*/bin/flutter' 2>/dev/null | head -n1)"
    [ -n "$_f" ] && export PATH="$PATH:$(dirname "$_f")" && echo "[ui] Found Flutter at: $(dirname "$_f")"
fi

# Newest already-built native binary (searched from the project root).
prebuilt_bin() {
    local d
    d="$(ls -dt "$FLUTTER_DIR"/build/linux/*/release/bundle 2>/dev/null | head -n1)"
    [ -n "$d" ] && find "$d" -maxdepth 1 -type f -executable 2>/dev/null | head -n1
}

if command -v flutter &>/dev/null; then
    echo "[ui] Preparing Flutter frontend ($(command -v flutter))..."
    flutter config --enable-linux-desktop --enable-web >/dev/null 2>&1
    if ensure_linux_toolchain; then
        echo "[ui] Native desktop toolchain ready."
    else
        echo "[ui][WARN] Native toolchain unavailable — will try a browser window."
    fi
    (
        cd "$FLUTTER_DIR" || exit 1
        LOG="jarvis_ui.log"
        : > "$LOG"
        echo "[ui] Detailed build log: $FLUTTER_DIR/$LOG"

        if [ ! -d "linux" ] || [ ! -d "web" ]; then
            echo "[ui] Scaffolding Flutter platforms (linux, web)..."
            flutter create --platforms=linux,web . >>"$LOG" 2>&1
        fi

        echo "[ui] Resolving packages..."
        flutter pub get >>"$LOG" 2>&1

        find_bin() {
            local d
            d="$(ls -dt build/linux/*/release/bundle 2>/dev/null | head -n1)"
            [ -n "$d" ] && find "$d" -maxdepth 1 -type f -executable 2>/dev/null | head -n1
        }

        # Always (incrementally) build so the latest face code is picked up.
        echo "[ui] Building native Linux app (incremental; first time is slow)..."
        if flutter build linux --release >>"$LOG" 2>&1; then
            BIN="$(find_bin)"
            if [ -n "$BIN" ] && [ -x "$BIN" ]; then
                echo "[ui] (2/3) Launching JARVIS face (native window)..."
                exec "$BIN"
            fi
        else
            echo "[ui][WARN] Native build failed — last lines of $FLUTTER_DIR/$LOG:"
            tail -n 12 "$LOG" | sed 's/^/[ui]   /'
        fi

        # Fallbacks that still surface a window.
        echo "[ui] Falling back to 'flutter run' (native → browser)..."
        flutter run -d linux --release 2>>"$LOG" \
            || flutter run -d chrome --release 2>>"$LOG" \
            || echo "[ui][ERROR] Could not launch UI. Try: cd $FLUTTER_DIR && flutter run -d chrome"
    ) &
    PIDS+=($!)
else
    # Flutter truly not found — but if we've built the app before, just run it.
    echo "[start][WARN] 'flutter' is not on PATH for this script."
    BIN="$(prebuilt_bin)"
    if [ -n "$BIN" ] && [ -x "$BIN" ]; then
        # Is the built binary older than the source? Then it's STALE and won't
        # show recent changes (this is exactly the "still wrong" trap).
        if [ -n "$(find "$FLUTTER_DIR/lib" -name '*.dart' -newer "$BIN" 2>/dev/null | head -n1)" ]; then
            echo "[ui][WARN] ===================================================================="
            echo "[ui][WARN] The built app is OLDER than your latest code — it will show STALE UI"
            echo "[ui][WARN] (old lip-sync, old weather, etc.). Flutter isn't on PATH so I can't"
            echo "[ui][WARN] rebuild it. Rebuild once with your IDE, or add Flutter to PATH:"
            echo "[ui][WARN]   echo 'export PATH=\"\$PATH:\$HOME/flutter/bin\"' >> ~/.bashrc"
            echo "[ui][WARN]   source ~/.bashrc  &&  ./stop_jarvis.sh  &&  ./start.sh"
            echo "[ui][WARN] ===================================================================="
        fi
        echo "[ui] Launching the previously-built JARVIS face:"
        echo "[ui]   $BIN"
        ( exec "$BIN" ) &
        PIDS+=($!)
    else
        echo "[ui] No prebuilt binary found. Add Flutter to your PATH, e.g.:"
        echo "       echo 'export PATH=\"\$PATH:\$HOME/flutter/bin\"' >> ~/.bashrc && source ~/.bashrc"
        echo "     then re-run ./start.sh — or launch manually:"
        echo "       cd $FLUTTER_DIR && flutter run -d linux"
    fi
fi

# ── 3. JARVIS backend (foreground) ────────────────────────────────────────────
# Install the heavy backend deps on first run (mirrors start_jarvis.sh).
if ! python3 -c "import livekit" &>/dev/null; then
    echo "[start] Installing backend dependencies (first run, may take a while)..."
    if [ -f "venv/bin/uv" ]; then
        venv/bin/uv pip install -r requirements.txt --python venv/bin/python
    else
        python3 -m pip install --upgrade pip
        python3 -m pip install uv
        if [ -f "venv/bin/uv" ]; then
            venv/bin/uv pip install -r requirements.txt --python venv/bin/python
        else
            pip install -r requirements.txt
        fi
    fi
fi

echo "[start] (3/3) Booting JARVIS backend..."
echo "=============================================================="
# Hide the old PyQt HUD pill — the Flutter face replaces it. The HUD process
# still runs (mic capture, voice playback, state mirror to the bridge); it just
# isn't drawn. Set JARVIS_HUD_HIDDEN=0 before running to bring the pill back.
export JARVIS_HUD_HIDDEN="${JARVIS_HUD_HIDDEN:-1}"
python3 jarvis_launcher.py

# Backend exited → tear down the bridge and UI too.
cleanup
