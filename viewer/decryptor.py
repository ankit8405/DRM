import os
import json
import zipfile
import io
import base64
from datetime import datetime
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from converter import convert_to_images, add_watermark
import filetype
from PIL import Image, ImageDraw

backend = default_backend()


def derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=backend
    )
    return kdf.derive(password.encode())


def check_access_window(start_str: str, end_str: str) -> bool:
    now = datetime.now()
    try:
        start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        return start <= now <= end
    except Exception:
        return False


def is_expired(metadata: dict) -> bool:
    start = metadata.get("start")
    end = metadata.get("end")
    if not start or not end:
        return True
    return not check_access_window(start, end)


def detect_file_type(file_path: str) -> str:
    try:
        kind = filetype.guess(file_path)
        if kind:
            return kind.extension
        
        file_ext = os.path.splitext(file_path)[1][1:].lower()
        if file_ext:
            return file_ext
            
        return "bin"
    except Exception as e:
        return "bin"


def create_unsupported_placeholder(file_path: str, watermark_text: str = None) -> str:
    """Create a placeholder image for unsupported file types."""
    try:
        from converter import add_watermark
        
        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1][1:].upper() if os.path.splitext(filename)[1] else "UNKNOWN"
        
        placeholder = Image.new("RGB", (800, 600), color=(240, 240, 240))
        draw = ImageDraw.Draw(placeholder)
        
        draw.text((50, 250), f"Unsupported File Type: {ext}", fill=(100, 100, 100))
        draw.text((50, 300), f"Filename: {filename}", fill=(100, 100, 100))
        
        if watermark_text:
            placeholder = add_watermark(placeholder, watermark_text)
        
        output_dir = os.path.join(os.path.dirname(__file__), "decrypted_images")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"unsupported_{ext.lower()}_preview.jpg")
        placeholder.save(output_path, "JPEG")
        
        return output_path
    except Exception as e:
        return None


def decrypt_file(filepath: str, password: str):
    """Original decrypt_file function without performance optimizations"""
    try:
        with open(filepath, "r") as f:
            file_data = json.load(f)
    except Exception as e:
        raise ValueError("Invalid or unreadable DRM file.")

    if file_data.get("magic") != "MYDRM01":
        raise ValueError("Invalid DRM file format.")

    try:
        salt = base64.urlsafe_b64decode(file_data["salt"])
        iv = base64.urlsafe_b64decode(file_data["iv"])
        encrypted_data = base64.urlsafe_b64decode(file_data["data"])
        metadata = file_data.get("metadata", {})
    except Exception as e:
        raise ValueError("Corrupted base64 fields in DRM file.")

    start = metadata.get("start")
    end = metadata.get("end")
    
    if not start or not end or not check_access_window(start, end):
        raise PermissionError("Access Denied: File is expired or not yet accessible.")
        
    key = derive_key(password, salt)
    cipher = Cipher(algorithms.AES(key), modes.CFB(iv), backend=backend)
    decryptor = cipher.decryptor()

    try:
        decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()
    except Exception as e:
        raise ValueError("Decryption failed. Wrong password or corrupted data.")

    if zipfile.is_zipfile(io.BytesIO(decrypted_data)):
        extract_dir = os.path.join(os.path.dirname(__file__), "decrypted_files", os.path.splitext(os.path.basename(filepath))[0])
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(decrypted_data), 'r') as zipf:
            zipf.extractall(extract_dir)
        extracted_files = [os.path.join(extract_dir, name) for name in zipf.namelist()]
        return extracted_files, metadata

    decrypted_dir = os.path.join("viewer", "decrypted_files")
    os.makedirs(decrypted_dir, exist_ok=True)

    original_filename = os.path.basename(filepath)
    decrypted_file_path = os.path.join(decrypted_dir, original_filename)
    with open(decrypted_file_path, "wb") as out_file:
        out_file.write(decrypted_data)

    ext = detect_file_type(decrypted_file_path)

    if ext and ext != "bin":
        new_path = f"{decrypted_file_path.rsplit('.', 1)[0]}.{ext}"
        try:
            os.rename(decrypted_file_path, new_path)
            decrypted_file_path = new_path
        except Exception as e:
            pass

    watermark_text = metadata.get("watermark_text") if metadata.get("watermark") else None

    if ext == "pdf":
        result = convert_to_images(decrypted_file_path, watermark_text), metadata
    elif ext in ["jpg", "jpeg", "png", "heic", "bmp", "gif", "tiff"]:
        img = Image.open(decrypted_file_path).convert("RGB")
        if watermark_text:
            img = add_watermark(img, watermark_text)
        output_dir = os.path.join(os.path.dirname(__file__), "decrypted_images")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"image_1.jpg")
        img.save(output_path, "JPEG", quality=95)
        result = [output_path], metadata
    elif ext in ["mp4", "mov", "avi", "mkv", "wmv", "flv"]:
        result = convert_to_images(decrypted_file_path, watermark_text), metadata
    else:
        raise ValueError("Unsupported file type after decryption.")
        print("H")
    return result