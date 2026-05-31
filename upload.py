#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VRCHAT Video Manager - CLI Upload Tool
命令行上传工具，用于直接从服务器上传视频文件
"""

import os
import sys
import json
import uuid
import argparse
from datetime import datetime
from pathlib import Path

# Configuration
WORKSPACE_DIR = os.environ.get('WORKSPACE_DIR', '/opt/workspace')
VIDEO_FOLDER = f'{WORKSPACE_DIR}/data/videos'
UPLOAD_FOLDER = f'{WORKSPACE_DIR}/data/uploads'
SERVER_HOST = os.environ.get('SERVER_HOST', 'http://47.120.24.142:5000')

# Allowed video extensions
ALLOWED_EXTENSIONS = {'mp4', 'mkv', 'mov', 'avi', 'webm', 'wmv', 'flv', 'm4v', 'ogv'}


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def sanitize_filename(filename):
    """Sanitize filename"""
    import re
    from werkzeug.utils import secure_filename
    filename = secure_filename(filename)
    filename = re.sub(r'[^a-zA-Z0-9_\-\.\u4e00-\u9fff]', '_', filename)
    return filename


def get_video_info(filepath):
    """Get video info using ffprobe"""
    try:
        import subprocess
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration,size:stream=codec_name,width,height',
            '-of', 'json', filepath
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        data = json.loads(result.stdout)

        duration = float(data.get('format', {}).get('duration', 0))
        size = int(data.get('format', {}).get('size', 0))

        streams = data.get('streams', [])
        codec = 'unknown'
        width = height = 0

        if streams:
            stream = streams[0]
            codec = stream.get('codec_name', 'unknown')
            width = stream.get('width', 0)
            height = stream.get('height', 0)

        return duration, size, codec, width, height
    except Exception as e:
        print(f"Warning: Could not get video info: {e}")
        return 0, os.path.getsize(filepath), 'unknown', 0, 0


def save_metadata(video_id, metadata):
    """Save video metadata"""
    meta_file = os.path.join(UPLOAD_FOLDER, f'{video_id}_meta.json')
    with open(meta_file, 'w') as f:
        json.dump(metadata, f)


def upload_video(filepath, folder='', name=None):
    """Upload a video file to the server"""

    # Check if file exists
    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}")
        return False

    # Get filename
    filename = os.path.basename(filepath)

    # Check file extension
    if not allowed_file(filename):
        print(f"Error: File type not allowed. Supported: {', '.join(ALLOWED_EXTENSIONS)}")
        return False

    # Get file info
    file_size = os.path.getsize(filepath)
    print(f"File: {filename}")
    print(f"Size: {format_size(file_size)}")

    # Generate unique ID
    video_id = str(uuid.uuid4())
    file_ext = filename.rsplit('.', 1)[1].lower()

    # Generate unique filename
    unique_filename = f'{video_id}.{file_ext}'
    output_path = os.path.join(VIDEO_FOLDER, unique_filename)

    # Copy file
    print(f"Copying file to {output_path}...")
    import shutil
    shutil.copy2(filepath, output_path)

    # Get video info
    print("Getting video info...")
    duration, size, codec, width, height = get_video_info(output_path)

    # Create metadata
    original_name = name if name else sanitize_filename(filename.rsplit('.', 1)[0])
    metadata = {
        'id': video_id,
        'original_name': filename,
        'name': original_name,
        'folder': folder,
        'created_at': datetime.now().isoformat(),
        'source': 'cli'
    }
    save_metadata(video_id, metadata)

    # Print result
    base_url = SERVER_HOST.rstrip('/')
    video_url = f'{base_url}/stream/{unique_filename}'

    print()
    print("=" * 60)
    print("Video uploaded successfully!")
    print("=" * 60)
    print(f"ID: {video_id}")
    print(f"Name: {original_name}")
    print(f"Duration: {format_duration(duration)}")
    print(f"Resolution: {width}x{height}")
    print(f"Codec: {codec}")
    print(f"URL: {video_url}")
    print("=" * 60)
    print()

    return True


def format_size(size):
    """Format file size"""
    if size == 0:
        return '0 B'
    k = 1024
    sizes = ['B', 'KB', 'MB', 'GB', 'TB']
    i = int(math.log(size) / math.log(k))
    return f"{size / math.pow(k, i):.2f} {sizes[i]}"


def format_duration(seconds):
    """Format duration"""
    if not seconds:
        return '00:00'
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def scan_videos_folder():
    """Scan videos folder for files without metadata"""
    added = 0
    errors = []

    print("Scanning videos folder...")
    print(f"Folder: {VIDEO_FOLDER}")
    print()

    for filename in os.listdir(VIDEO_FOLDER):
        filepath = os.path.join(VIDEO_FOLDER, filename)

        if not os.path.isfile(filepath):
            continue

        file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        if file_ext not in ALLOWED_EXTENSIONS:
            continue

        video_id = filename.rsplit('.', 1)[0]
        meta_file = os.path.join(UPLOAD_FOLDER, f'{video_id}_meta.json')

        if os.path.exists(meta_file):
            continue

        try:
            metadata = {
                'id': video_id,
                'original_name': filename,
                'name': filename.rsplit('.', 1)[0],
                'folder': '',
                'created_at': datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat(),
                'source': 'manual'
            }
            save_metadata(video_id, metadata)
            added += 1
            print(f"Added: {filename}")
        except Exception as e:
            errors.append(f"{filename}: {e}")
            print(f"Error: {filename}: {e}")

    print()
    print(f"Scan complete. Added {added} videos.")
    if errors:
        print(f"Errors: {len(errors)}")
        for e in errors:
            print(f"  - {e}")

    return added


def list_videos():
    """List all videos"""
    if not os.path.exists(VIDEO_FOLDER):
        print("No videos found.")
        return

    print()
    print("=" * 60)
    print("VRCHAT Video Manager - Video List")
    print("=" * 60)
    print()

    videos = []
    for filename in os.listdir(VIDEO_FOLDER):
        filepath = os.path.join(VIDEO_FOLDER, filename)

        if not os.path.isfile(filepath):
            continue

        file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        if file_ext not in ALLOWED_EXTENSIONS:
            continue

        video_id = filename.rsplit('.', 1)[0]
        meta_file = os.path.join(UPLOAD_FOLDER, f'{video_id}_meta.json')

        name = filename
        folder = ''

        if os.path.exists(meta_file):
            with open(meta_file, 'r') as f:
                meta = json.load(f)
                name = meta.get('name', filename)
                folder = meta.get('folder', '')

        file_size = os.path.getsize(filepath)
        duration, _, codec, width, height = get_video_info(filepath)

        videos.append({
            'filename': filename,
            'name': name,
            'folder': folder,
            'size': file_size,
            'duration': duration,
            'resolution': f'{width}x{height}'
        })

    # Sort by name
    videos.sort(key=lambda x: x['name'].lower())

    for i, video in enumerate(videos, 1):
        print(f"{i}. {video['name']}")
        print(f"   File: {video['filename']}")
        print(f"   Size: {format_size(video['size'])}")
        print(f"   Duration: {format_duration(video['duration'])}")
        print(f"   Resolution: {video['resolution']}")
        if video['folder']:
            print(f"   Folder: {video['folder']}")
        print()

    print(f"Total: {len(videos)} videos")


def main():
    import math

    parser = argparse.ArgumentParser(
        description='VRCHAT Video Manager - CLI Upload Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload a video file
  python upload.py upload /path/to/video.mkv

  # Upload with custom name
  python upload.py upload /path/to/video.mkv -n "My Video"

  # Upload to a folder
  python upload.py upload /path/to/video.mkv -f "VRChat Worlds"

  # Scan videos folder for manually added files
  python upload.py scan

  # List all videos
  python upload.py list
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Upload command
    upload_parser = subparsers.add_parser('upload', help='Upload a video file')
    upload_parser.add_argument('filepath', help='Path to video file')
    upload_parser.add_argument('-n', '--name', help='Custom name for the video')
    upload_parser.add_argument('-f', '--folder', help='Folder to place the video in')
    upload_parser.add_argument('-d', '--dest', help='Destination folder (alternative to -f)')

    # Scan command
    subparsers.add_parser('scan', help='Scan videos folder for manually added files')

    # List command
    subparsers.add_parser('list', help='List all videos')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Ensure directories exist
    os.makedirs(VIDEO_FOLDER, exist_ok=True)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    if args.command == 'upload':
        folder = ''
        if hasattr(args, 'folder') and args.folder:
            folder = args.folder
        elif hasattr(args, 'dest') and args.dest:
            folder = args.dest

        upload_video(args.filepath, folder=folder, name=args.name)

    elif args.command == 'scan':
        scan_videos_folder()

    elif args.command == 'list':
        list_videos()


if __name__ == '__main__':
    main()