#!/bin/bash
set -e

# 启动虚拟显示和桌面环境
Xvfb :99 -screen 0 1080x1920x24 &
export DISPLAY=:99
startxfce4 &
x11vnc -display :99 -nopw -forever -rfbport 5900 &
/opt/noVNC/utils/novnc_proxy --vnc localhost:5900 --listen 6080 &

echo "[INFO] noVNC running at http://localhost:6080"

# 启动 adb
adb start-server

# 启动 emulator 放后台
emulator -avd "Default_AVD" -noaudio -no-boot-anim -gpu swiftshader_indirect -no-snapshot-load -no-snapshot-save &

# 等待 adb 设备就绪
echo "[INFO] Waiting for emulator to be ready..."
until adb devices | grep -w "device" >/dev/null 2>&1; do
    sleep 2
done

echo "[INFO] Emulator started successfully!"
adb devices

# 启动你的 Python 脚本
# python3 -u /home/computeruse/entry.py "$@"
wait