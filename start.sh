#!/bin/bash
# VRCHAT Video Stream Server - Startup Script

set -e

echo "========================================="
echo "VRCHAT Video Stream Server"
echo "========================================="

# Configuration - Change this to your actual data directory on production
WORKSPACE_DIR="${WORKSPACE_DIR:-/opt/workspace}"
DATA_DIR="$WORKSPACE_DIR/data"

# Create directories
echo "[1/4] Creating directories..."
mkdir -p "$DATA_DIR/uploads"
mkdir -p "$DATA_DIR/raw"
mkdir -p "$DATA_DIR/videos"
chmod -R 777 "$WORKSPACE_DIR"

# Check FFmpeg
echo "[2/4] Checking FFmpeg..."
if command -v ffmpeg &> /dev/null; then
    ffmpeg -version | head -n 1
else
    echo "Error: FFmpeg is not installed"
    exit 1
fi

# Install Python dependencies
echo "[3/4] Installing Python dependencies..."
pip install flask werkzeug --quiet 2>/dev/null || pip install flask werkzeug

# Stop existing services if any
echo "[4/4] Starting services..."
pkill -f "python.*app.py" 2>/dev/null || true
sleep 1

# Update app.py to use correct directory
sed -i "s|WORKSPACE_DIR = '/opt/workspace'|WORKSPACE_DIR = '$WORKSPACE_DIR'|g" /root/projects/app.py

# Start Flask app
echo ""
echo "========================================="
echo "Service Started!"
echo "========================================="
echo ""
echo "Web Interface: http://47.120.24.142:5000"
echo "Video Streaming: http://47.120.24.142:5000/stream/"
echo ""
echo "Press Ctrl+C to stop service"
echo "========================================="
export SERVER_HOST='http://47.120.24.142:5000/'
python /root/projects/app.py