#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VRCHAT Video Stream Server
Flask Backend Application
- Web upload interface
- Video streaming server
- Automatic format detection and transcoding
- Folder management
- Rename support
"""

import os
import subprocess
import threading
import uuid
import json
import re
import shutil
from datetime import datetime
from flask import Flask, request, jsonify, render_template, Response
from werkzeug.utils import secure_filename

app = Flask(__name__, template_folder='templates', static_folder='static')

# Configuration
SERVER_HOST = os.environ.get('SERVER_HOST', 'http://YOUR_SERVER_IP:5000')
WORKSPACE_DIR = '/root/projects'  # 代码目录
VIDEO_FOLDER = '/opt/workspace/data/videos'  # 视频存储目录
UPLOAD_FOLDER = '/root/projects/data/uploads'  # 元数据存储目录
TEMP_FOLDER = '/opt/workspace/data/temp'  # 临时处理目录

# VRCHAT compatible formats (must be H.264 video + AAC audio)
VRCHAT_COMPATIBLE_VIDEO = {'h264', 'avc', 'mpeg4'}
VRCHAT_COMPATIBLE_AUDIO = {'aac', 'mp3', 'opus'}
# Formats that always need transcoding
ALWAYS_NEED_TRANSCODE = {'mkv', 'avi', 'webm', 'wmv', 'flv', 'ogv', 'm4v'}

# Allowed video extensions
ALLOWED_EXTENSIONS = {'mp4', 'mkv', 'mov', 'avi', 'webm', 'wmv', 'flv', 'm4v', 'ogv'}
MAX_CONTENT_LENGTH = 20 * 1024 * 1024 * 1024  # 20GB

app.config['VIDEO_FOLDER'] = VIDEO_FOLDER
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Ensure directories exist
for folder in [VIDEO_FOLDER, UPLOAD_FOLDER, TEMP_FOLDER]:
    os.makedirs(folder, exist_ok=True)


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def analyze_video_format(filepath):
    """Analyze video format and determine if transcoding is needed"""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_streams', '-show_format',
            '-of', 'json', filepath
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        data = json.loads(result.stdout)

        video_codec = None
        audio_codec = None
        duration = 0
        size = 0
        width = height = 0
        needs_transcode = False
        reason = ""

        # Get video info
        if 'streams' in data:
            for stream in data['streams']:
                if stream.get('codec_type') == 'video' and not video_codec:
                    video_codec = stream.get('codec_name', '').lower()
                    width = stream.get('width', 0)
                    height = stream.get('height', 0)
                elif stream.get('codec_type') == 'audio' and not audio_codec:
                    audio_codec = stream.get('codec_name', '').lower()

        # Get format info
        if 'format' in data:
            duration = float(data['format'].get('duration', 0))
            size = int(data['format'].get('size', 0))

        # Determine if transcoding is needed
        file_ext = filepath.rsplit('.', 1)[-1].lower() if '.' in filepath else ''

        # Check video codec
        if video_codec not in VRCHAT_COMPATIBLE_VIDEO:
            needs_transcode = True
            reason = f"视频编码 {video_codec} 不兼容，需要转换为 H.264"
        # Check audio codec
        elif audio_codec not in VRCHAT_COMPATIBLE_AUDIO:
            needs_transcode = True
            reason = f"音频编码 {audio_codec} 不兼容，需要转换为 AAC"
        # MKV always needs transcoding for better compatibility
        elif file_ext == 'mkv':
            needs_transcode = True
            reason = "MKV 格式建议转换为 MP4 以获得更好的兼容性"

        return {
            'video_codec': video_codec,
            'audio_codec': audio_codec,
            'duration': duration,
            'size': size,
            'width': width,
            'height': height,
            'needs_transcode': needs_transcode,
            'reason': reason,
            'is_compatible': not needs_transcode
        }
    except Exception as e:
        print(f"Error analyzing video: {e}")
        return {
            'video_codec': 'unknown',
            'audio_codec': 'unknown',
            'duration': 0,
            'size': 0,
            'width': 0,
            'height': 0,
            'needs_transcode': True,
            'reason': f'分析失败: {str(e)}',
            'is_compatible': False,
            'error': str(e)
        }


def get_video_info_simple(filepath):
    """Get basic video info using ffprobe"""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration,size:stream=codec_name,width,height',
            '-of', 'json', filepath
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        data = json.loads(result.stdout)

        duration = 0
        size = 0
        codec = 'unknown'
        width = height = 0

        if 'format' in data:
            duration = float(data['format'].get('duration', 0))
            size = int(data['format'].get('size', 0))

        if 'streams' in data and len(data['streams']) > 0:
            stream = data['streams'][0]
            codec = stream.get('codec_name', 'unknown')
            width = stream.get('width', 0)
            height = stream.get('height', 0)

        return duration, size, codec, width, height
    except Exception as e:
        print(f"Error getting video info: {e}")
        return 0, 0, 'unknown', 0, 0


# Target format for VRCHAT (H.264 video + AAC audio in MP4)
TARGET_VIDEO_CODEC = 'h264'
TARGET_AUDIO_CODEC = 'aac'
TARGET_CONTAINER = 'mp4'


def is_video_already_compatible(filepath):
    """Check if video is already in the target format (H.264 + AAC in MP4)
    Returns True if video is already in target format (no transcoding needed)
    Returns False if video needs transcoding
    """
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_streams', '-show_format',
            '-of', 'json', filepath
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        data = json.loads(result.stdout)

        video_codec = None
        audio_codec = None
        container = None

        # Get video and audio codecs
        if 'streams' in data:
            for stream in data['streams']:
                if stream.get('codec_type') == 'video' and not video_codec:
                    video_codec = stream.get('codec_name', '').lower()
                elif stream.get('codec_type') == 'audio' and not audio_codec:
                    audio_codec = stream.get('codec_name', '').lower()

        # Get container format
        if 'format' in data:
            format_name = data['format'].get('format_name', '')
            container = format_name.split(',')[0].lower() if format_name else None

        # Check if already in target format
        file_ext = filepath.rsplit('.', 1)[-1].lower() if '.' in filepath else ''

        # Video is compatible if:
        # 1. Container is MP4
        # 2. Video codec is H.264
        # 3. Audio codec is AAC
        if container == TARGET_CONTAINER and video_codec == TARGET_VIDEO_CODEC and audio_codec == TARGET_AUDIO_CODEC:
            return True

        return False
    except Exception as e:
        print(f"Error checking video compatibility: {e}")
        return False


def transcode_video(input_path, output_path):
    """Transcode video to VRCHAT compatible format using the specified command

    Args:
        input_path: Path to input video
        output_path: Path to output video

    Uses the following FFmpeg parameters:
        -c:v libx264 -crf 18 -preset medium (H.264 video, quality CRF 18)
        -c:a aac -b:a 192k -ar 48000 -ac 2 (AAC audio, 192kbps, 48kHz stereo)
        -movflags +faststart (MP4 streaming optimization)
    """
    # Use the exact command specified by the user
    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-c:v', 'libx264', '-crf', '18', '-preset', 'medium',
        '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2',
        '-movflags', '+faststart',
        output_path
    ]

    # Run transcoding and capture output
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        error_msg = result.stderr.decode() if result.stderr else 'Unknown error'
        raise Exception(f"Transcode failed: {error_msg}")


def get_transcode_progress(video_id):
    """Get transcoding progress"""
    progress_file = os.path.join(TEMP_FOLDER, f'{video_id}_transcode.progress')
    if os.path.exists(progress_file):
        try:
            with open(progress_file, 'r') as f:
                for line in f:
                    if line.startswith('out_time_ms='):
                        time_ms = int(line.split('=')[1].strip())
                        time_sec = time_ms / 1000000
                        return time_sec
        except:
            pass
    return 0


def update_video_metadata(video_id, data):
    """Update video metadata in JSON file"""
    meta_file = os.path.join(UPLOAD_FOLDER, f'{video_id}_meta.json')
    try:
        with open(meta_file, 'w') as f:
            json.dump(data, f)
        return True
    except Exception as e:
        print(f"Error updating metadata: {e}")
        return False


def get_video_metadata(video_id):
    """Get video metadata from JSON file"""
    meta_file = os.path.join(UPLOAD_FOLDER, f'{video_id}_meta.json')
    if os.path.exists(meta_file):
        try:
            with open(meta_file, 'r') as f:
                return json.load(f)
        except:
            pass
    return None


def sanitize_filename(filename):
    """Sanitize filename to prevent path traversal"""
    filename = secure_filename(filename)
    filename = re.sub(r'[^a-zA-Z0-9_\-\.\u4e00-\u9fff]', '_', filename)
    return filename


def get_all_videos(folder=None):
    """Get all videos, optionally filtered by folder"""
    videos = []
    base_url = SERVER_HOST.rstrip('/')

    if not os.path.exists(VIDEO_FOLDER):
        return videos

    for filename in os.listdir(VIDEO_FOLDER):
        filepath = os.path.join(VIDEO_FOLDER, filename)

        if not os.path.isfile(filepath):
            continue

        file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        if file_ext not in ALLOWED_EXTENSIONS:
            continue

        video_id = filename.rsplit('.', 1)[0]

        # Get metadata
        meta = get_video_metadata(video_id) or {}

        # Check folder filter
        video_folder = meta.get('folder', '')
        if folder and video_folder != folder:
            continue

        file_size = os.path.getsize(filepath)
        duration, _, codec, width, height = get_video_info_simple(filepath)

        videos.append({
            'id': video_id,
            'name': meta.get('name', filename),
            'filename': filename,
            'folder': video_folder,
            'url': f'{base_url}/stream/{filename}',
            'size': file_size,
            'duration': duration,
            'codec': codec,
            'resolution': f'{width}x{height}' if width and height else 'N/A',
            'status': meta.get('status', 'ready'),
            'transcode_status': meta.get('transcode_status', 'completed')
        })

    return sorted(videos, key=lambda x: x['name'].lower())


def get_all_folders():
    """Get all folders - both from storage and from videos with assigned folders"""
    # Get explicitly created folders
    stored_folders = get_folders_list()

    # Get folders assigned to videos (from metadata)
    video_folders = set()
    if os.path.exists(VIDEO_FOLDER):
        for filename in os.listdir(VIDEO_FOLDER):
            if not os.path.isfile(os.path.join(VIDEO_FOLDER, filename)):
                continue
            if '.' not in filename:
                continue
            file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
            if file_ext not in ALLOWED_EXTENSIONS:
                continue
            video_id = filename.rsplit('.', 1)[0]
            meta = get_video_metadata(video_id)
            if meta and meta.get('folder'):
                video_folders.add(meta['folder'])

    # Combine and sort both sources
    all_folders = list(set(stored_folders) | video_folders)
    all_folders.sort()
    return all_folders


@app.route('/')
def index():
    """Serve main page"""
    return render_template('index.html')


@app.route('/api/analyze', methods=['POST'])
def analyze_video():
    """Analyze video format before upload"""
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400

    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': f'File type not allowed. Supported: {", ".join(ALLOWED_EXTENSIONS)}'}), 400

    video_id = str(uuid.uuid4())
    temp_path = os.path.join(TEMP_FOLDER, f'{video_id}_temp_{file.filename}')

    try:
        # Save to temp location
        file.save(temp_path)

        # Analyze
        analysis = analyze_video_format(temp_path)
        analysis['filename'] = file.filename
        analysis['video_id'] = video_id
        analysis['temp_path'] = temp_path

        # Save analysis for later use during upload
        analysis_file = os.path.join(TEMP_FOLDER, f'{video_id}_analysis.json')
        with open(analysis_file, 'w') as f:
            json.dump(analysis, f)

        # Check if video is already in target format
        is_compatible = is_video_already_compatible(temp_path)
        analysis['is_already_compatible'] = is_compatible

        # Update analysis file with compatibility info
        with open(analysis_file, 'w') as f:
            json.dump(analysis, f)

        return jsonify(analysis)
    except Exception as e:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500


@app.route('/api/upload', methods=['POST'])
def upload_video():
    """Handle video upload with optional transcoding"""
    data = request.get_json(silent=True) or {}
    video_id = data.get('video_id')
    folder = data.get('folder', '')

    if not video_id:
        return jsonify({'error': 'Video ID required'}), 400

    # Find temp file
    temp_dir = TEMP_FOLDER
    temp_files = [f for f in os.listdir(temp_dir) if f.startswith(f'{video_id}_temp_')]
    if not temp_files:
        return jsonify({'error': 'Temp file not found. Please upload again.'}), 400

    temp_path = os.path.join(temp_dir, temp_files[0])
    original_filename = temp_files[0].replace(f'{video_id}_temp_', '')

    try:
        # Check if video is already in target format (H.264 + AAC in MP4)
        # If already compatible, we can skip transcoding
        is_already_compatible = is_video_already_compatible(temp_path)

        if is_already_compatible:
            # Video is already in target format, just copy as MP4
            final_filename = f'{video_id}.mp4'
            final_path = os.path.join(VIDEO_FOLDER, final_filename)
            shutil.move(temp_path, final_path)
            message = '视频上传成功（已是目标格式，无需转码）'
            transcode_status = 'skipped'
        else:
            # Always transcode to ensure consistent output format
            final_filename = f'{video_id}.mp4'
            final_path = os.path.join(VIDEO_FOLDER, final_filename)

            # Run transcoding in background
            def do_transcode():
                try:
                    transcode_video(temp_path, final_path)
                    # Clean up temp file after transcoding
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    # Clean up analysis file
                    analysis_file = os.path.join(TEMP_FOLDER, f'{video_id}_analysis.json')
                    if os.path.exists(analysis_file):
                        os.remove(analysis_file)
                except Exception as e:
                    print(f"Transcode error: {e}")
                    # If transcode fails, use original
                    if os.path.exists(temp_path) and not os.path.exists(final_path):
                        shutil.move(temp_path, final_path)

            thread = threading.Thread(target=do_transcode)
            thread.daemon = True
            thread.start()

            message = '视频正在后台转码中，请稍后刷新查看状态'
            transcode_status = 'processing'

        # Get file info
        file_size = os.path.getsize(final_path)
        duration, _, codec, width, height = get_video_info_simple(final_path)

        # Save metadata
        metadata = {
            'id': video_id,
            'original_name': original_filename,
            'name': original_filename.rsplit('.', 1)[0] if '.' in original_filename else original_filename,
            'folder': folder,
            'created_at': datetime.now().isoformat(),
            'status': 'processing' if transcode_status == 'processing' else 'ready',
            'transcode_status': transcode_status,
            'transcode_params': {
                'video_codec': 'libx264',
                'crf': 18,
                'preset': 'medium',
                'audio_codec': 'aac',
                'audio_bitrate': '192k',
                'audio_sample_rate': 48000,
                'audio_channels': 2
            }
        }
        update_video_metadata(video_id, metadata)

        base_url = SERVER_HOST.rstrip('/')

        return jsonify({
            'success': True,
            'video_id': video_id,
            'filename': final_filename,
            'url': f'{base_url}/stream/{final_filename}',
            'message': message,
            'transcode_status': transcode_status
        })
    except Exception as e:
        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500


@app.route('/api/video/<video_id>/status')
def video_status(video_id):
    """Get video processing status"""
    meta = get_video_metadata(video_id)
    if not meta:
        return jsonify({'error': 'Video not found'}), 404

    # Check if file exists
    final_path = os.path.join(VIDEO_FOLDER, f'{video_id}.mp4')
    file_exists = os.path.exists(final_path)

    status = 'ready' if file_exists else 'processing'
    if meta.get('transcode_status') == 'skipped':
        status = 'ready'

    # Update metadata with current status
    if file_exists and meta.get('status') != 'ready':
        meta['status'] = 'ready'
        update_video_metadata(video_id, meta)

    return jsonify({
        'video_id': video_id,
        'status': status,
        'transcode_status': meta.get('transcode_status', 'unknown'),
        'file_exists': file_exists
    })


@app.route('/api/videos')
def list_videos():
    """List all videos with optional folder filter"""
    folder = request.args.get('folder', '')
    videos = get_all_videos(folder if folder else None)
    folders = get_all_folders()

    return jsonify({
        'videos': videos,
        'folders': folders,
        'current_folder': folder
    })


@app.route('/api/folders')
def list_folders():
    """List all folders"""
    return jsonify({'folders': get_all_folders()})


def get_folders_list():
    """Get list of all folders from storage"""
    folders_file = os.path.join(UPLOAD_FOLDER, 'folders.json')
    if os.path.exists(folders_file):
        try:
            with open(folders_file, 'r') as f:
                return json.load(f)
        except:
            pass
    return []


def save_folders_list(folders):
    """Save folders list to storage"""
    folders_file = os.path.join(UPLOAD_FOLDER, 'folders.json')
    try:
        with open(folders_file, 'w') as f:
            json.dump(folders, f)
        return True
    except Exception as e:
        print(f"Error saving folders: {e}")
        return False


@app.route('/api/folder', methods=['POST'])
def create_folder():
    """Create a new folder"""
    data = request.get_json()
    folder_name = data.get('name', '').strip()

    if not folder_name:
        return jsonify({'error': 'Folder name is required'}), 400

    # Sanitize folder name
    folder_name = sanitize_filename(folder_name)

    # Get existing folders
    folders = get_folders_list()

    # Check if folder already exists
    if folder_name in folders:
        return jsonify({'success': True, 'folder': folder_name, 'message': 'Folder already exists'})

    # Add new folder
    folders.append(folder_name)
    folders.sort()
    save_folders_list(folders)

    return jsonify({'success': True, 'folder': folder_name})


@app.route('/api/folder/<folder_name>', methods=['DELETE'])
def delete_folder(folder_name):
    """Delete a folder (move all videos out of it)"""
    # Get existing folders
    folders = get_folders_list()

    if folder_name in folders:
        folders.remove(folder_name)
        save_folders_list(folders)

    return jsonify({'success': True})


@app.route('/api/video/<video_id>', methods=['PUT'])
def update_video(video_id):
    """Update video metadata (rename, move to folder)"""
    data = request.get_json()

    # Find the video file
    video_file = None
    for ext in ALLOWED_EXTENSIONS:
        potential_file = f'{video_id}.{ext}'
        filepath = os.path.join(VIDEO_FOLDER, potential_file)
        if os.path.exists(filepath):
            video_file = potential_file
            break

    if not video_file:
        return jsonify({'error': 'Video not found'}), 404

    # Update metadata
    meta = get_video_metadata(video_id) or {}

    if 'name' in data:
        new_name = data['name'].strip()
        if new_name:
            meta['name'] = sanitize_filename(new_name)

    if 'folder' in data:
        meta['folder'] = data['folder'].strip()

    update_video_metadata(video_id, meta)

    return jsonify({'success': True, 'video': meta})


@app.route('/api/video/<video_id>', methods=['DELETE'])
def delete_video(video_id):
    """Delete a video"""
    try:
        # Delete video file
        deleted = False
        for ext in ALLOWED_EXTENSIONS:
            filepath = os.path.join(VIDEO_FOLDER, f'{video_id}.{ext}')
            if os.path.exists(filepath):
                os.remove(filepath)
                deleted = True

        # Delete metadata file
        meta_file = os.path.join(UPLOAD_FOLDER, f'{video_id}_meta.json')
        if os.path.exists(meta_file):
            os.remove(meta_file)

        if not deleted:
            return jsonify({'error': 'Video not found'}), 404

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/stream/<path:filename>')
def stream_video(filename):
    """Stream video with range request support"""
    # Security: prevent path traversal
    filename = secure_filename(filename)
    video_path = os.path.join(VIDEO_FOLDER, filename)

    if not os.path.exists(video_path):
        return "Video not found", 404

    file_size = os.path.getsize(video_path)
    file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'mp4'

    # Set content type based on extension
    content_types = {
        'mp4': 'video/mp4',
        'mkv': 'video/x-matroska',
        'webm': 'video/webm',
        'mov': 'video/quicktime',
        'avi': 'video/x-msvideo',
        'ogv': 'video/ogg',
        'm4v': 'video/x-m4v'
    }
    content_type = content_types.get(file_ext, 'video/mp4')

    # Handle range requests for video streaming
    range_header = request.headers.get('Range')

    if range_header:
        byte_start, byte_end = 0, file_size - 1
        range_match = range_header.replace('bytes=', '').split('-')
        if range_match[0]:
            byte_start = int(range_match[0])
        if len(range_match) > 1 and range_match[1]:
            byte_end = int(range_match[1])

        length = byte_end - byte_start + 1

        def generate():
            with open(video_path, 'rb') as f:
                f.seek(byte_start)
                remaining = length
                chunk_size = 1024 * 1024  # 1MB chunks
                while remaining > 0:
                    chunk = min(chunk_size, remaining)
                    data = f.read(chunk)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        response = Response(generate(), status=206)
        response.headers['Content-Range'] = f'bytes {byte_start}-{byte_end}/{file_size}'
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Content-Length'] = length
        response.headers['Content-Type'] = content_type
    else:
        response = Response(open(video_path, 'rb').read())
        response.headers['Content-Length'] = file_size
        response.headers['Content-Type'] = content_type

    # CORS headers
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Range'
    response.headers['Access-Control-Expose-Headers'] = 'Content-Length, Content-Range'

    return response


@app.route('/api/scan', methods=['POST'])
def scan_folder():
    """Scan videos folder for manually uploaded files and add them to database"""
    try:
        added = 0
        errors = []

        # Ensure directories exist
        os.makedirs(VIDEO_FOLDER, exist_ok=True)
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        # Check if folder exists
        if not os.path.exists(VIDEO_FOLDER):
            return jsonify({
                'success': True,
                'added': 0,
                'errors': ['Videos folder does not exist'],
                'message': 'Videos folder not found'
            })

        for filename in os.listdir(VIDEO_FOLDER):
            filepath = os.path.join(VIDEO_FOLDER, filename)

            if not os.path.isfile(filepath):
                continue

            if '.' not in filename:
                continue

            file_ext = filename.rsplit('.', 1)[1].lower()
            if file_ext not in ALLOWED_EXTENSIONS:
                continue

            video_id = filename.rsplit('.', 1)[0]

            # Check if metadata exists
            meta_file = os.path.join(UPLOAD_FOLDER, f'{video_id}_meta.json')
            if os.path.exists(meta_file):
                continue

            try:
                # Create metadata for this file
                metadata = {
                    'id': video_id,
                    'original_name': filename,
                    'name': filename.rsplit('.', 1)[0],
                    'folder': '',
                    'created_at': datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat(),
                    'source': 'manual',
                    'status': 'ready',
                    'transcode_status': 'skipped'
                }
                update_video_metadata(video_id, metadata)
                added += 1
            except Exception as e:
                errors.append(f'{filename}: {str(e)}')

        return jsonify({
            'success': True,
            'added': added,
            'errors': errors,
            'message': f'扫描完成，新增 {added} 个视频'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '扫描失败'
        }), 500


if __name__ == '__main__':
    print("=" * 50)
    print("VRCHAT Video Stream Server")
    print("=" * 50)
    print(f"Server URL: {SERVER_HOST}")
    print(f"Video Folder: {VIDEO_FOLDER}")
    print()
    print("Features:")
    print("  - Auto format detection")
    print("  - Optional transcoding")
    print("  - VRCHAT compatible output")
    print()
    print("Web Interface: http://localhost:5000")
    print("Video Streaming: http://localhost:5000/stream/")
    print()
    print("=" * 50)

    app.run(host='0.0.0.0', port=5000, debug=False)