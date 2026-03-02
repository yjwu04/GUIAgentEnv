#!/bin/bash
set -e
set -o pipefail

LOG_DIR=${LOG_DIR:-/tmp}
START_LOG="${LOG_DIR}/start.log"
ENTRY_LOG="${LOG_DIR}/entry.log"

echo "[START] starting container entrypoint" | tee -a "$START_LOG"

export DISPLAY=${DISPLAY:-:99}
export WIDTH=${WIDTH:-1920}
export HEIGHT=${HEIGHT:-1080}
if [ -z "${DISPLAY_NUM:-}" ]; then
    DISPLAY_NUM="${DISPLAY##*:}"
    export DISPLAY_NUM
fi
export XAUTHORITY=${XAUTHORITY:-"$HOME/.Xauthority"}
echo "[START] DISPLAY=${DISPLAY} DISPLAY_NUM=${DISPLAY_NUM} WIDTH=${WIDTH} HEIGHT=${HEIGHT}" | tee -a "$START_LOG"

# Prepare desktop/browser shortcuts for the agent
DESKTOP_DIR="$HOME/Desktop"
mkdir -p "$DESKTOP_DIR"
for desktop_file in /usr/share/applications/firefox*.desktop; do
    if [ -f "$desktop_file" ]; then
        cp "$desktop_file" "$DESKTOP_DIR/Firefox.desktop"
        chmod +x "$DESKTOP_DIR/Firefox.desktop"
        break
    fi
done

# at the top of start.sh, before launching Xvfb
sudo chown root:root /tmp/.X11-unix
sudo chmod 1777 /tmp/.X11-unix

echo "[START] launching Xvfb" | tee -a "$START_LOG"
Xvfb "$DISPLAY" -screen 0 "${WIDTH}x${HEIGHT}x24" >>"$START_LOG" 2>&1 &
for _ in {1..50}; do
    if xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then
        break
    fi
    sleep 0.1
done
echo "[START] launching xfce4" | tee -a "$START_LOG"
startxfce4 >>"$START_LOG" 2>&1 &

# Disable screen blanking/locking to avoid password prompts (needs X to be up)
xset s off -dpms || true
xset s noblank || true
pkill -f xfce4-screensaver >/dev/null 2>&1 || true
pkill -f light-locker >/dev/null 2>&1 || true
if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get remove -y xfce4-screensaver light-locker >/dev/null 2>&1 || true
fi
if command -v xfconf-query >/dev/null 2>&1; then
    xfconf-query -c xfce4-session -p /shutdown/LockScreen -s false >/dev/null 2>&1 || true
    xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/lock-screen-suspend-hibernate -s false >/dev/null 2>&1 || true
fi

echo "[START] launching x11vnc" | tee -a "$START_LOG"
x11vnc -display "$DISPLAY" -nopw -forever -rfbport 5900 >>"$START_LOG" 2>&1 &
echo "[START] launching noVNC" | tee -a "$START_LOG"
/opt/noVNC/utils/novnc_proxy --vnc localhost:5900 --listen 6080 >>"$START_LOG" 2>&1 &

echo "[INFO] http://localhost:6080"

echo "[START] running entry.py $*" | tee -a "$START_LOG"
python3 -u /home/computeruse/entry.py "$@" 2>&1 | tee -a "$ENTRY_LOG"

wait
