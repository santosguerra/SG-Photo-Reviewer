"""
SG Photo Reviewer - Backend
Version 1.1.3 - 2025-10-19

Changelog:
  v1.1.3: Correcciones críticas y optimización UI
          - CRÍTICO: Fotos respetan orientación EXIF (ImageOps.exif_transpose)
          - Filtro de carpetas de sistema (Windows/Linux/hidden)
          - Desmarcar todas sin confirmación
          - UI compacta: Header 50px, Breadcrumb 45px, Panel carpetas 180px max
          - Todos los elementos más compactos (gaps, padding reducidos)
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
from PIL import Image, ImageOps
import os
import hashlib
import io
import json
from pathlib import Path
import threading
from config import load_config, save_config, is_path_allowed

app = Flask(__name__)

# Debug mode for EXIF extraction (set to True to see all EXIF tags in console)
EXIF_DEBUG = os.environ.get('EXIF_DEBUG', 'False').lower() == 'true'

# RAW file extensions
RAW_EXTENSIONS = {'.cr2', '.cr3', '.arw', '.nef', '.pef', '.dng', '.raf', '.orf'}
JPG_EXTENSIONS = {'.jpg', '.jpeg'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.mkv', '.avi', '.m4v'}

# System folders to exclude from browsing
EXCLUDED_FOLDERS = {
    # Windows
    'system volume information', '$recycle.bin', 'pagefile.sys', 'hiberfil.sys',
    'config.msi', 'recovery', 'windows', 'program files', 'program files (x86)',
    'programdata', 'perflogs',
    # Linux
    'proc', 'sys', 'dev', 'run', 'tmp', 'lost+found', '.trash', '.cache',
    'boot', 'etc', 'lib', 'lib64', 'sbin', 'var',
    # Development/hidden
    '.git', '__pycache__', 'node_modules', '.vscode', '.idea', '.vs',
    '.svn', '.hg', '.DS_Store'
}

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

def should_exclude_folder(folder_name):
    """Check if folder should be excluded from browsing"""
    folder_lower = folder_name.lower()

    # Exclude hidden folders (starting with dot)
    if folder_name.startswith('.'):
        return True

    # Exclude system folders (case-insensitive)
    if folder_lower in EXCLUDED_FOLDERS:
        return True

    return False

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

def extract_exif_data(image_path, debug=False):
    """Extract EXIF data from image file using rawpy for RAW and exifread for JPG

    Returns dict with: camera_brand, camera_model, iso, aperture, shutter_speed, date

    Args:
        image_path: Path to the image file
        debug: If True, prints all available EXIF tags to console
    """
    exif_data = {
        'camera_brand': '',
        'camera_model': '',
        'iso': None,
        'aperture': None,
        'shutter_speed': None,
        'date': ''
    }

    # Detect file type by extension
    ext = os.path.splitext(image_path)[1].lower()
    is_raw = ext in RAW_EXTENSIONS
    is_jpg = ext in JPG_EXTENSIONS

    try:
        if is_raw:
            # Use rawpy for RAW files
            import rawpy

            with rawpy.imread(image_path) as raw:
                # Get EXIF data from RAW
                metadata = raw.metadata

                if debug:
                    print(f"\n=== EXIF DEBUG (rawpy) for: {os.path.basename(image_path)} ===")
                    print(f"  Make: {metadata.make if hasattr(metadata, 'make') else 'N/A'}")
                    print(f"  Model: {metadata.model if hasattr(metadata, 'model') else 'N/A'}")
                    print(f"  ISO: {metadata.iso_speed if hasattr(metadata, 'iso_speed') else 'N/A'}")
                    print(f"  Aperture: {metadata.aperture if hasattr(metadata, 'aperture') else 'N/A'}")
                    print(f"  Shutter: {metadata.shutter if hasattr(metadata, 'shutter') else 'N/A'}")
                    print(f"  Timestamp: {metadata.timestamp if hasattr(metadata, 'timestamp') else 'N/A'}")
                    print("=" * 60)

                # Extract camera make (brand)
                if hasattr(metadata, 'make') and metadata.make:
                    exif_data['camera_brand'] = metadata.make.strip()

                # Extract camera model
                if hasattr(metadata, 'model') and metadata.model:
                    exif_data['camera_model'] = metadata.model.strip()

                # Extract ISO
                if hasattr(metadata, 'iso_speed') and metadata.iso_speed:
                    exif_data['iso'] = int(metadata.iso_speed)

                # Extract Aperture
                if hasattr(metadata, 'aperture') and metadata.aperture:
                    exif_data['aperture'] = round(metadata.aperture, 1)

                # Extract Shutter Speed
                if hasattr(metadata, 'shutter') and metadata.shutter:
                    shutter = metadata.shutter
                    if shutter >= 1:
                        exif_data['shutter_speed'] = str(round(shutter, 2))
                    else:
                        # Convert to fraction format (e.g., 1/250)
                        exif_data['shutter_speed'] = f"1/{int(1/shutter)}"

                # Extract DateTime from timestamp
                if hasattr(metadata, 'timestamp') and metadata.timestamp:
                    import datetime
                    dt = datetime.datetime.fromtimestamp(metadata.timestamp)
                    exif_data['date'] = dt.strftime('%Y:%m:%d %H:%M:%S')

        elif is_jpg:
            # Use exifread for JPG files
            import exifread

            with open(image_path, 'rb') as f:
                tags = exifread.process_file(f, details=False)

                if debug:
                    print(f"\n=== EXIF DEBUG (exifread) for: {os.path.basename(image_path)} ===")
                    if tags:
                        for tag, value in tags.items():
                            print(f"  {tag}: {value}")
                    else:
                        print("  NO EXIF TAGS FOUND")
                    print("=" * 60)

                # Extract camera make (brand)
                if 'Image Make' in tags:
                    exif_data['camera_brand'] = str(tags['Image Make']).strip()

                # Extract camera model
                if 'Image Model' in tags:
                    exif_data['camera_model'] = str(tags['Image Model']).strip()

                # Extract ISO
                if 'EXIF ISOSpeedRatings' in tags:
                    exif_data['iso'] = int(str(tags['EXIF ISOSpeedRatings']))

                # Extract Aperture (F-number)
                if 'EXIF FNumber' in tags:
                    f_number = tags['EXIF FNumber']
                    if hasattr(f_number, 'num') and hasattr(f_number, 'den'):
                        exif_data['aperture'] = round(f_number.num / f_number.den, 1)
                    else:
                        try:
                            exif_data['aperture'] = round(float(str(f_number)), 1)
                        except:
                            pass

                # Extract Shutter Speed (Exposure Time)
                if 'EXIF ExposureTime' in tags:
                    exposure = tags['EXIF ExposureTime']
                    if hasattr(exposure, 'num') and hasattr(exposure, 'den'):
                        if exposure.num == 1:
                            exif_data['shutter_speed'] = f"1/{exposure.den}"
                        else:
                            exif_data['shutter_speed'] = str(round(exposure.num / exposure.den, 2))
                    else:
                        exif_data['shutter_speed'] = str(exposure)

                # Extract DateTime Original (preferred) or DateTime
                if 'EXIF DateTimeOriginal' in tags:
                    exif_data['date'] = str(tags['EXIF DateTimeOriginal'])
                elif 'Image DateTime' in tags:
                    exif_data['date'] = str(tags['Image DateTime'])

    except Exception as e:
        if debug:
            print(f"ERROR extracting EXIF from {os.path.basename(image_path)}: {e}")
        pass

    return exif_data

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

        # Apply EXIF orientation if present
        img = ImageOps.exif_transpose(img) if img else img

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

        # Apply EXIF orientation correction (fixes rotated photos)
        img = ImageOps.exif_transpose(img) if img else img

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
                    # Skip excluded system folders
                    if should_exclude_folder(entry.name):
                        continue

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

                    # Extract EXIF data
                    # Rule: If JPG+RAW paired, use RAW data; otherwise use JPG data
                    exif_data = {}
                    if raw_file:
                        exif_data = extract_exif_data(raw_file, debug=EXIF_DEBUG)
                        processed_raws.add(raw_file)
                    else:
                        exif_data = extract_exif_data(entry.path, debug=EXIF_DEBUG)

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
                        'camera_brand': exif_data.get('camera_brand', ''),
                        'camera_model': exif_data.get('camera_model', ''),
                        'iso': exif_data.get('iso'),
                        'aperture': exif_data.get('aperture'),
                        'shutter_speed': exif_data.get('shutter_speed'),
                        'date': exif_data.get('date', ''),
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
                        # This is an orphan RAW - extract EXIF from RAW
                        exif_data = extract_exif_data(entry.path, debug=EXIF_DEBUG)
                        file_size = entry.stat().st_size

                        photos.append({
                            'jpg': None,
                            'raw': entry.path,
                            'name': entry.name,
                            'type': 'raw_only',
                            'media_type': 'image',
                            'camera_brand': exif_data.get('camera_brand', ''),
                            'camera_model': exif_data.get('camera_model', ''),
                            'iso': exif_data.get('iso'),
                            'aperture': exif_data.get('aperture'),
                            'shutter_speed': exif_data.get('shutter_speed'),
                            'date': exif_data.get('date', ''),
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
                        'camera_model': '',
                        'iso': None,
                        'aperture': None,
                        'shutter_speed': None,
                        'date': '',
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
