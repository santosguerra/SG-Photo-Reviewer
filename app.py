"""
SG Photo Reviewer - Backend
Version 1.1.2 - 2025-10-19

Changelog:
  v1.1.2: Actualización completa de documentación de ayuda
          - Tab de ayuda expandido con todas las features v1.1.0
          - 13 secciones de documentación profesional
          - Tips, trucos y advertencias
          - Changelog visible
  v1.1.1: Corrección de versiones (sistema de versionado +0.0.1)
  v1.1.0: Mejoras significativas de UX/UI
          - Corrección: Modal de eliminación simplificado (sin input DELETE)
          - Corrección: Botón "Seleccionar todas" agregado
          - Corrección: Carpetas de revisión vacías se eliminan automáticamente
          - Feature: Selección por rango con Shift+Click
          - Feature: Contador de espacio en disco (MB/GB)
          - Feature: Modal de atajos de teclado (botón ? o tecla H)
          - Feature: Historial de navegación ◀ ▶ (como navegador web)
          - Feature: Favoritos/Bookmarks de carpetas (persistencia localStorage)
  v1.0.7: Agregado soporte completo para videos
          - Extensiones soportadas: MP4, MOV, MKV, AVI, M4V
          - Generación de thumbnails con OpenCV (primer frame)
          - Endpoint /api/video para streaming
          - Integrado en funciones move, restore, delete
"""

from flask import Flask, render_template, jsonify, request, send_file
from PIL import Image
import os
import hashlib
import io
import json
from pathlib import Path
import threading
from config import load_config, save_config, is_path_allowed

app = Flask(__name__)

# RAW file extensions
RAW_EXTENSIONS = {'.cr2', '.cr3', '.arw', '.nef', '.pef', '.dng', '.raf', '.orf'}
JPG_EXTENSIONS = {'.jpg', '.jpeg'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.mkv', '.avi', '.m4v'}

# Cache for thumbnails
THUMBNAIL_DIR = 'static/thumbnails'
THUMBNAIL_SIZE = (300, 300)

def get_file_hash(filepath):
    """Generate hash for file path to use as thumbnail name"""
    return hashlib.md5(filepath.encode()).hexdigest()

def is_raw_file(filename):
    """Check if file is a RAW format"""
    ext = os.path.splitext(filename)[1].lower()
    return ext in RAW_EXTENSIONS

def is_jpg_file(filename):
    """Check if file is a JPG"""
    ext = os.path.splitext(filename)[1].lower()
    return ext in JPG_EXTENSIONS

def is_video_file(filename):
    """Check if file is a video"""
    ext = os.path.splitext(filename)[1].lower()
    return ext in VIDEO_EXTENSIONS

def find_paired_raw(jpg_path):
    """Find corresponding RAW file for a JPG"""
    base_name = os.path.splitext(jpg_path)[0]
    directory = os.path.dirname(jpg_path)

    for ext in RAW_EXTENSIONS:
        # Check both lowercase and uppercase extensions
        for raw_ext in [ext, ext.upper()]:
            raw_path = base_name + raw_ext
            if os.path.exists(raw_path):
                return raw_path
    return None

def find_paired_jpg(raw_path):
    """Find corresponding JPG file for a RAW"""
    base_name = os.path.splitext(raw_path)[0]

    for ext in JPG_EXTENSIONS:
        # Check both lowercase and uppercase extensions
        for jpg_ext in [ext, ext.upper()]:
            jpg_path = base_name + jpg_ext
            if os.path.exists(jpg_path):
                return jpg_path
    return None

def get_camera_brand(filename):
    """Get camera brand from RAW file extension"""
    ext = os.path.splitext(filename)[1].lower()
    brand_map = {
        '.cr2': 'Canon',
        '.cr3': 'Canon',
        '.arw': 'Sony',
        '.nef': 'Nikon',
        '.pef': 'Pentax',
        '.dng': 'DJI',
        '.raf': 'Fuji',
        '.orf': 'Olympus'
    }
    return brand_map.get(ext, '')

def generate_video_thumbnail(video_path):
    """Generate thumbnail from first frame of video"""
    try:
        import cv2

        # Check if thumbnail already exists
        file_hash = get_file_hash(video_path)
        thumbnail_path = os.path.join(THUMBNAIL_DIR, f"{file_hash}.jpg")

        if os.path.exists(thumbnail_path):
            return thumbnail_path

        # Open video and extract first frame
        cap = cv2.VideoCapture(video_path)

        # Try to read the first frame
        success, frame = cap.read()
        cap.release()

        if not success:
            print(f"Failed to read first frame from {video_path}")
            return None

        # Convert BGR to RGB (OpenCV uses BGR)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Convert to PIL Image
        img = Image.fromarray(frame_rgb)

        # Resize maintaining aspect ratio
        img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

        # Save thumbnail
        img.save(thumbnail_path, 'JPEG', quality=85)
        return thumbnail_path

    except Exception as e:
        print(f"Error generating video thumbnail for {video_path}: {e}")
        return None

def generate_thumbnail(image_path):
    """Generate thumbnail for image or video"""
    try:
        # Check if it's a video file
        if is_video_file(image_path):
            return generate_video_thumbnail(image_path)

        # Check if thumbnail already exists
        file_hash = get_file_hash(image_path)
        thumbnail_path = os.path.join(THUMBNAIL_DIR, f"{file_hash}.jpg")

        if os.path.exists(thumbnail_path):
            return thumbnail_path

        # Generate new thumbnail for image
        if is_raw_file(image_path):
            try:
                import rawpy
                import imageio
                with rawpy.imread(image_path) as raw:
                    rgb = raw.postprocess()
                img = Image.fromarray(rgb)
            except Exception as e:
                print(f"Error processing RAW {image_path}: {e}")
                return None
        else:
            img = Image.open(image_path)

        # Resize maintaining aspect ratio
        img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

        # Save thumbnail
        img.save(thumbnail_path, 'JPEG', quality=85)
        return thumbnail_path
    except Exception as e:
        print(f"Error generating thumbnail for {image_path}: {e}")
        return None

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/version')
def get_version():
    """Get application version"""
    try:
        with open('version.json', 'r') as f:
            return jsonify(json.load(f))
    except:
        return jsonify({"version": "1.0.6", "name": "SG Photo Reviewer"})

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    config = load_config()
    return jsonify(config)

@app.route('/api/config', methods=['POST'])
def update_config():
    """Update configuration"""
    try:
        new_config = request.json
        if save_config(new_config):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to save config'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/check-permissions', methods=['GET'])
def check_permissions():
    """Check read/write permissions for a path"""
    path = request.args.get('path', '')
    config = load_config()

    if not is_path_allowed(path, config['mount_points']):
        return jsonify({'error': 'Path not allowed'}), 403

    result = {
        'exists': os.path.exists(path),
        'readable': os.access(path, os.R_OK),
        'writable': os.access(path, os.W_OK)
    }
    return jsonify(result)

@app.route('/api/browse', methods=['GET'])
def browse():
    """List folders and files in a path"""
    path = request.args.get('path', '')
    config = load_config()

    # If no path provided, return mount points
    if not path:
        mount_points = []
        for mp in config['mount_points']:
            if os.path.exists(mp) and os.path.isdir(mp):
                mount_points.append({
                    'name': os.path.basename(mp) or mp,
                    'path': mp,
                    'type': 'directory'
                })
        return jsonify({'items': mount_points, 'current_path': ''})

    # Security check
    if not is_path_allowed(path, config['mount_points']):
        return jsonify({'error': 'Path not allowed'}), 403

    if not os.path.exists(path):
        return jsonify({'error': 'Path does not exist'}), 404

    if not os.path.isdir(path):
        return jsonify({'error': 'Path is not a directory'}), 400

    try:
        items = []
        for entry in os.scandir(path):
            try:
                if entry.is_dir():
                    items.append({
                        'name': entry.name,
                        'path': entry.path,
                        'type': 'directory'
                    })
            except PermissionError:
                continue

        # Sort directories alphabetically
        items.sort(key=lambda x: x['name'].lower())

        return jsonify({'items': items, 'current_path': path})
    except PermissionError:
        return jsonify({'error': 'Permission denied'}), 403
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scan', methods=['GET'])
def scan():
    """Scan folder and return JPG files with their paired RAW files, plus orphan RAW files and videos"""
    path = request.args.get('path', '')
    config = load_config()

    if not path:
        return jsonify({'error': 'Path required'}), 400

    # Security check
    if not is_path_allowed(path, config['mount_points']):
        return jsonify({'error': 'Path not allowed'}), 403

    if not os.path.exists(path) or not os.path.isdir(path):
        return jsonify({'error': 'Invalid directory'}), 400

    try:
        photos = []
        processed_raws = set()

        # First pass: collect all JPG files with their paired RAWs
        for entry in os.scandir(path):
            try:
                if entry.is_file() and is_jpg_file(entry.name):
                    raw_file = find_paired_raw(entry.path)

                    # Get camera brand
                    camera_brand = ''
                    if raw_file:
                        camera_brand = get_camera_brand(raw_file)
                        processed_raws.add(raw_file)

                    # Get file size (JPG + RAW if exists)
                    file_size = entry.stat().st_size
                    if raw_file and os.path.exists(raw_file):
                        file_size += os.path.getsize(raw_file)

                    photos.append({
                        'jpg': entry.path,
                        'raw': raw_file,
                        'name': entry.name,
                        'type': 'jpg+raw' if raw_file else 'jpg_only',
                        'media_type': 'image',
                        'camera_brand': camera_brand,
                        'size': file_size,
                        'display_path': entry.path  # Path to use for display (thumbnail/image)
                    })
            except Exception as e:
                print(f"Error processing {entry.name}: {e}")
                continue

        # Second pass: find orphan RAW files (RAWs without JPG)
        for entry in os.scandir(path):
            try:
                if entry.is_file() and is_raw_file(entry.name):
                    if entry.path not in processed_raws:
                        # This is an orphan RAW
                        camera_brand = get_camera_brand(entry.path)
                        file_size = entry.stat().st_size

                        photos.append({
                            'jpg': None,
                            'raw': entry.path,
                            'name': entry.name,
                            'type': 'raw_only',
                            'media_type': 'image',
                            'camera_brand': camera_brand,
                            'size': file_size,
                            'display_path': entry.path  # Use RAW for display
                        })
            except Exception as e:
                print(f"Error processing orphan RAW {entry.name}: {e}")
                continue

        # Third pass: collect video files
        for entry in os.scandir(path):
            try:
                if entry.is_file() and is_video_file(entry.name):
                    file_size = entry.stat().st_size

                    photos.append({
                        'jpg': None,
                        'raw': None,
                        'video': entry.path,
                        'name': entry.name,
                        'type': 'video',
                        'media_type': 'video',
                        'camera_brand': '',
                        'size': file_size,
                        'display_path': entry.path  # Use video path for thumbnail
                    })
            except Exception as e:
                print(f"Error processing video {entry.name}: {e}")
                continue

        # Sort by filename
        photos.sort(key=lambda x: x['name'].lower())

        return jsonify({'photos': photos, 'count': len(photos)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/thumbnail', methods=['GET'])
def thumbnail():
    """Generate or return cached thumbnail"""
    path = request.args.get('path', '')
    config = load_config()

    if not path:
        return jsonify({'error': 'Path required'}), 400

    # Security check
    if not is_path_allowed(path, config['mount_points']):
        return jsonify({'error': 'Path not allowed'}), 403

    if not os.path.exists(path):
        return jsonify({'error': 'File does not exist'}), 404

    thumbnail_path = generate_thumbnail(path)
    if thumbnail_path and os.path.exists(thumbnail_path):
        return send_file(thumbnail_path, mimetype='image/jpeg')
    else:
        return jsonify({'error': 'Failed to generate thumbnail'}), 500

@app.route('/api/image', methods=['GET'])
def image():
    """Return full size image (or convert RAW to JPG if needed)"""
    path = request.args.get('path', '')
    config = load_config()

    if not path:
        return jsonify({'error': 'Path required'}), 400

    # Security check
    if not is_path_allowed(path, config['mount_points']):
        return jsonify({'error': 'Path not allowed'}), 403

    if not os.path.exists(path):
        return jsonify({'error': 'File does not exist'}), 404

    # If it's a video file, return error (use /api/video endpoint)
    if is_video_file(path):
        return jsonify({'error': 'Use /api/video endpoint for videos'}), 400

    # If it's a RAW file, convert to JPG for display
    if is_raw_file(path):
        try:
            import rawpy
            with rawpy.imread(path) as raw:
                rgb = raw.postprocess()
            img = Image.fromarray(rgb)

            # Save to BytesIO to send
            img_io = io.BytesIO()
            img.save(img_io, 'JPEG', quality=95)
            img_io.seek(0)
            return send_file(img_io, mimetype='image/jpeg')
        except Exception as e:
            print(f"Error converting RAW to display: {e}")
            return jsonify({'error': 'Failed to process RAW file'}), 500

    return send_file(path, mimetype='image/jpeg')

@app.route('/api/video', methods=['GET'])
def video():
    """Return video file"""
    path = request.args.get('path', '')
    config = load_config()

    if not path:
        return jsonify({'error': 'Path required'}), 400

    # Security check
    if not is_path_allowed(path, config['mount_points']):
        return jsonify({'error': 'Path not allowed'}), 403

    if not os.path.exists(path):
        return jsonify({'error': 'File does not exist'}), 404

    if not is_video_file(path):
        return jsonify({'error': 'Not a video file'}), 400

    # Determine mimetype based on extension
    ext = os.path.splitext(path)[1].lower()
    mimetype_map = {
        '.mp4': 'video/mp4',
        '.mov': 'video/quicktime',
        '.mkv': 'video/x-matroska',
        '.avi': 'video/x-msvideo',
        '.m4v': 'video/mp4'
    }
    mimetype = mimetype_map.get(ext, 'video/mp4')

    return send_file(path, mimetype=mimetype)

@app.route('/api/move', methods=['POST'])
def move_files():
    """Move JPG, RAW, and video files to destination subfolder"""
    try:
        data = request.json
        folder = data.get('folder')
        files = data.get('files', [])
        destination_name = data.get('destination_name')
        config = load_config()

        if not folder or not files or not destination_name:
            return jsonify({'error': 'Missing required parameters'}), 400

        # Security check
        if not is_path_allowed(folder, config['mount_points']):
            return jsonify({'error': 'Path not allowed'}), 403

        # Create destination folder
        dest_folder = os.path.join(folder, destination_name)
        if not os.path.exists(dest_folder):
            os.makedirs(dest_folder)

        moved_count = 0
        errors = []

        for file_info in files:
            try:
                jpg_path = file_info.get('jpg')
                raw_path = file_info.get('raw')
                video_path = file_info.get('video')

                # Move JPG
                if jpg_path and os.path.exists(jpg_path):
                    jpg_dest = os.path.join(dest_folder, os.path.basename(jpg_path))
                    os.rename(jpg_path, jpg_dest)
                    moved_count += 1

                # Move RAW if exists
                if raw_path and os.path.exists(raw_path):
                    raw_dest = os.path.join(dest_folder, os.path.basename(raw_path))
                    os.rename(raw_path, raw_dest)

                # Move video if exists
                if video_path and os.path.exists(video_path):
                    video_dest = os.path.join(dest_folder, os.path.basename(video_path))
                    os.rename(video_path, video_dest)
                    moved_count += 1
            except Exception as e:
                errors.append(f"Error moving {file_info.get('name', 'unknown')}: {str(e)}")

        return jsonify({
            'success': True,
            'moved': moved_count,
            'errors': errors
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/restore', methods=['POST'])
def restore_files():
    """Restore JPG, RAW, and video files from review folder to parent folder"""
    try:
        data = request.json
        folder = data.get('folder')
        files = data.get('files', [])
        config = load_config()

        if not folder or not files:
            return jsonify({'error': 'Missing required parameters'}), 400

        # Security check
        if not is_path_allowed(folder, config['mount_points']):
            return jsonify({'error': 'Path not allowed'}), 403

        # Get parent folder
        parent_folder = os.path.dirname(folder)

        restored_count = 0
        errors = []

        for file_info in files:
            try:
                jpg_path = file_info.get('jpg')
                raw_path = file_info.get('raw')
                video_path = file_info.get('video')

                # Restore JPG
                if jpg_path and os.path.exists(jpg_path):
                    jpg_dest = os.path.join(parent_folder, os.path.basename(jpg_path))
                    os.rename(jpg_path, jpg_dest)
                    restored_count += 1

                # Restore RAW if exists
                if raw_path and os.path.exists(raw_path):
                    raw_dest = os.path.join(parent_folder, os.path.basename(raw_path))
                    os.rename(raw_path, raw_dest)

                # Restore video if exists
                if video_path and os.path.exists(video_path):
                    video_dest = os.path.join(parent_folder, os.path.basename(video_path))
                    os.rename(video_path, video_dest)
                    restored_count += 1
            except Exception as e:
                errors.append(f"Error restoring {file_info.get('name', 'unknown')}: {str(e)}")

        # Check if folder is empty and is a review folder, then delete it
        folder_deleted = False
        folder_name = os.path.basename(folder)
        if folder_name == config['destination_folder']:
            try:
                if os.path.exists(folder) and os.path.isdir(folder):
                    if not os.listdir(folder):  # Check if empty
                        os.rmdir(folder)
                        folder_deleted = True
            except Exception as e:
                print(f"Could not delete empty review folder: {e}")

        return jsonify({
            'success': True,
            'restored': restored_count,
            'errors': errors,
            'folder_deleted': folder_deleted
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete', methods=['POST'])
def delete_files():
    """Delete JPG, RAW, and video files permanently"""
    try:
        data = request.json
        files = data.get('files', [])
        folder = data.get('folder')  # Get folder path to check if empty after deletion
        config = load_config()

        if not files:
            return jsonify({'error': 'Missing required parameters'}), 400

        deleted_count = 0
        errors = []

        for file_info in files:
            try:
                jpg_path = file_info.get('jpg')
                raw_path = file_info.get('raw')
                video_path = file_info.get('video')

                # Security check for each file
                if jpg_path:
                    if not is_path_allowed(jpg_path, config['mount_points']):
                        errors.append(f"Path not allowed: {jpg_path}")
                        continue
                    if os.path.exists(jpg_path):
                        os.remove(jpg_path)
                        deleted_count += 1

                if raw_path:
                    if not is_path_allowed(raw_path, config['mount_points']):
                        errors.append(f"Path not allowed: {raw_path}")
                        continue
                    if os.path.exists(raw_path):
                        os.remove(raw_path)

                if video_path:
                    if not is_path_allowed(video_path, config['mount_points']):
                        errors.append(f"Path not allowed: {video_path}")
                        continue
                    if os.path.exists(video_path):
                        os.remove(video_path)
                        deleted_count += 1
            except Exception as e:
                errors.append(f"Error deleting {file_info.get('name', 'unknown')}: {str(e)}")

        # Check if folder is empty and is a review folder, then delete it
        folder_deleted = False
        if folder:
            folder_name = os.path.basename(folder)
            if folder_name == config['destination_folder']:
                try:
                    if os.path.exists(folder) and os.path.isdir(folder):
                        if not os.listdir(folder):  # Check if empty
                            os.rmdir(folder)
                            folder_deleted = True
                except Exception as e:
                    print(f"Could not delete empty review folder: {e}")

        return jsonify({
            'success': True,
            'deleted': deleted_count,
            'errors': errors,
            'folder_deleted': folder_deleted
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete-jpgs', methods=['POST'])
def delete_jpgs():
    """Delete only JPG files, keeping RAW files intact"""
    try:
        data = request.json
        files = data.get('files', [])
        config = load_config()

        if not files:
            return jsonify({'error': 'Missing required parameters'}), 400

        deleted_count = 0
        skipped_count = 0
        errors = []

        for file_info in files:
            try:
                jpg_path = file_info.get('jpg')
                raw_path = file_info.get('raw')

                # Only delete if both JPG and RAW exist
                if not jpg_path or not raw_path:
                    skipped_count += 1
                    continue

                # Security check for JPG path
                if not is_path_allowed(jpg_path, config['mount_points']):
                    errors.append(f"Path not allowed: {jpg_path}")
                    skipped_count += 1
                    continue

                # Verify JPG exists
                if not os.path.exists(jpg_path):
                    skipped_count += 1
                    continue

                # Verify RAW exists (safety check)
                if not os.path.exists(raw_path):
                    errors.append(f"RAW not found for {os.path.basename(jpg_path)}, skipping")
                    skipped_count += 1
                    continue

                # Delete only the JPG file
                os.remove(jpg_path)
                deleted_count += 1

            except Exception as e:
                errors.append(f"Error deleting JPG {file_info.get('name', 'unknown')}: {str(e)}")
                skipped_count += 1

        return jsonify({
            'success': True,
            'deleted': deleted_count,
            'skipped': skipped_count,
            'errors': errors
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Ensure thumbnail directory exists
    os.makedirs(THUMBNAIL_DIR, exist_ok=True)

    # Run server
    app.run(host='0.0.0.0', port=5500, debug=True)
