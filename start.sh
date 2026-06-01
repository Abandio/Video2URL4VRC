#!/bin/bash
# VRCHAT Video Stream Server - Startup Script
# Production version with separated directories

set -e

echo "========================================="
echo "VRCHAT Video Stream Server"
echo "========================================="

# Configuration - Production directories
CODE_DIR="/root/projects"
DATA_DIR="/opt/workspace/data"

# Server IP - Change this to your actual server IP
SERVER_IP="YOUR_SERVER_IP"

echo "[1/5] Creating directories..."
mkdir -p "$DATA_DIR/videos"
mkdir -p "$DATA_DIR/temp"
mkdir -p "$CODE_DIR/data/uploads"
chmod -R 777 "$DATA_DIR"
chmod -R 777 "$CODE_DIR/data/uploads"
echo "      Code directory: $CODE_DIR"
echo "      Data directory: $DATA_DIR"

# Check FFmpeg
echo "[2/5] Checking FFmpeg..."
if command -v ffmpeg &> /dev/null; then
    ffmpeg -version | head -n 1
else
    echo "Error: FFmpeg is not installed"
    exit 1
fi

# Check Python dependencies
echo "[3/5] Checking Python dependencies..."
if python -c "import flask" 2>/dev/null; then
    echo "      Flask: OK"
else
    echo "      Installing Flask..."
    pip install flask werkzeug --quiet
fi

# Update app.py with correct paths
echo "[4/5] Updating configuration..."
sed -i "s|WORKSPACE_DIR = '/root/projects'|WORKSPACE_DIR = '$CODE_DIR'|g" "$CODE_DIR/app.py"
sed -i "s|VIDEO_FOLDER = '/opt/workspace/data/videos'|VIDEO_FOLDER = '$DATA_DIR/videos'|g" "$CODE_DIR/app.py"
sed -i "s|UPLOAD_FOLDER = '/root/projects/data/uploads'|UPLOAD_FOLDER = '$CODE_DIR/data/uploads'|g" "$CODE_DIR/app.py"
sed -i "s|TEMP_FOLDER = '/opt/workspace/data/temp'|TEMP_FOLDER = '$DATA_DIR/temp'|g" "$CODE_DIR/app.py"
sed -i "s|http://47.120.24.142:5000|http://$SERVER_IP:5000|g" "$CODE_DIR/app.py"
echo "      Paths updated"

# Stop existing services if any
echo "[5/5] Starting service..."
pkill -f "python.*app.py" 2>/dev/null || true
sleep 1

# Start Flask app
echo ""
echo "========================================="
echo "Service Started!"
echo "========================================="
echo ""
echo "Web Interface: http://$SERVER_IP:5000"
echo "Video Streaming: http://$SERVER_IP:5000/stream/"
echo ""
echo "Press Ctrl+C to stop service"
echo "========================================="

cd "$CODE_DIR"
python app.py