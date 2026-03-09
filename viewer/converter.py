import os
import fitz 
from PIL import Image, ImageDraw, ImageFont
import cv2
import threading
import sys 

try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(current_dir, 'config.py')
    
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config_code = f.read()
        exec(config_code)
    else:
        PDF_DPI = 150
        JPEG_QUALITY = 85
        VIDEO_FRAME_INTERVAL = 30
        VIDEO_JPEG_QUALITY = 90
        CURRENT_PROFILE = "balanced"
        PERFORMANCE_PROFILES = {
            "balanced": {
                "PDF_DPI": 150,
                "JPEG_QUALITY": 85,
                "VIDEO_FRAME_INTERVAL": 30,
                "VIDEO_JPEG_QUALITY": 90
            }
        }
except Exception:
    PDF_DPI = 150
    JPEG_QUALITY = 85
    VIDEO_FRAME_INTERVAL = 30
    VIDEO_JPEG_QUALITY = 90
    CURRENT_PROFILE = "balanced"
    PERFORMANCE_PROFILES = {
        "balanced": {
            "PDF_DPI": 150,
            "JPEG_QUALITY": 85,
            "VIDEO_FRAME_INTERVAL": 30,
            "VIDEO_JPEG_QUALITY": 90
        }
    }

def add_watermark(image: Image.Image, text: str = "DRM Protected") -> Image.Image:
    """Add semi-transparent watermark to image."""
    try:
        overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)
        
        font_size = max(12, image.width // 20)
        try:
            font_paths = [
                "arial.ttf", "Arial.ttf", "/System/Library/Fonts/Arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "C:/Windows/Fonts/arial.ttf"
            ]
            font = None
            for font_path in font_paths:
                try:
                    font = ImageFont.truetype(font_path, font_size)
                    break
                except:
                    continue
            if not font:
                font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()
        
        bbox = draw.textbbox((0, 0), text, font=font)
        x = (image.width - (bbox[2] - bbox[0])) // 2
        y = (image.height - (bbox[3] - bbox[1])) // 2
        
        draw.text((x, y), text, fill=(255, 0, 0, 80), font=font)
        return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    except Exception as e:
        return image

def extract_video_frames(video_path: str, watermark_text: str = None, frame_interval: int = None, progress_callback=None) -> list:
    """Extract frames from video file at specified intervals with progress tracking."""
    try:
        profile_settings = PERFORMANCE_PROFILES.get(CURRENT_PROFILE, {})
        frame_interval = frame_interval or profile_settings.get("VIDEO_FRAME_INTERVAL", VIDEO_FRAME_INTERVAL)
        jpeg_quality = profile_settings.get("VIDEO_JPEG_QUALITY", VIDEO_JPEG_QUALITY)
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []
        
        output_dir = os.path.join(os.path.dirname(__file__), "decrypted_images")
        os.makedirs(output_dir, exist_ok=True)
        
        frame_paths = []
        frame_count = 0
        extracted_count = 0
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        if progress_callback:
            progress_callback(0, f"Processing video: {total_frames} frames")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_count % frame_interval == 0:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb)
                
                if watermark_text:
                    img = add_watermark(img, watermark_text)
                
                output_path = os.path.join(output_dir, f"frame_{extracted_count + 1}.jpg")
                img.save(output_path, "JPEG", quality=jpeg_quality, optimize=True)
                frame_paths.append(output_path)
                extracted_count += 1
                
                if progress_callback and total_frames > 0:
                    progress = min(90, (frame_count / total_frames) * 90)
                    progress_callback(progress, f"Extracted {extracted_count} frames...")
            
            frame_count += 1
        
        cap.release()
        
        if progress_callback:
            progress_callback(100, f"Video processing complete: {extracted_count} frames")
            
        return frame_paths
        
    except Exception as e:
        return []

def convert_to_images_async(file_path: str, watermark_text: str = None, frame_interval: int = None, progress_callback=None) -> threading.Thread:
    """Async version of convert_to_images with progress callback"""
    def convert_worker():
        try:
            result = convert_to_images(file_path, watermark_text, frame_interval, progress_callback)
            return result, None
        except Exception as e:
            return None, str(e)
    
    thread = threading.Thread(target=lambda: setattr(convert_worker, 'result', convert_worker()))
    thread.start()
    return thread

def convert_to_images(file_path: str, watermark_text: str = None, frame_interval: int = None, progress_callback=None) -> list:
    """Convert any supported file to watermarked images with progress tracking."""
    if not os.path.exists(file_path):
        return []
    
    profile_settings = PERFORMANCE_PROFILES.get(CURRENT_PROFILE, {})
    pdf_dpi = profile_settings.get("PDF_DPI", PDF_DPI)
    jpeg_quality = profile_settings.get("JPEG_QUALITY", JPEG_QUALITY)
    frame_interval = frame_interval or profile_settings.get("VIDEO_FRAME_INTERVAL", VIDEO_FRAME_INTERVAL)
    
    output_dir = os.path.join(os.path.dirname(__file__), "decrypted_images")
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        for f in os.listdir(output_dir):
            if f.endswith((".jpg", ".jpeg")):
                file_path_to_remove = os.path.join(output_dir, f)
                try:
                    os.remove(file_path_to_remove)
                except:
                    pass 
    except:
        pass
    
    ext = os.path.splitext(file_path)[1].lower()
    image_paths = []
    
    try:
        if ext == '.pdf':
            pdf_path = file_path
            if progress_callback:
                progress_callback(0, "Processing PDF...")
                
            try:
                doc = fitz.open(pdf_path)
                total_pages = len(doc)
                doc.close()
            except:
                total_pages = 1
                
            try:
                doc = fitz.open(pdf_path)
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    pix = page.get_pixmap(dpi=pdf_dpi)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    
                    if watermark_text:
                        img = add_watermark(img, watermark_text)
                    
                    output_path = os.path.join(output_dir, f"page_{page_num + 1}.jpg")
                    img.save(output_path, "JPEG", quality=jpeg_quality, optimize=True)
                    image_paths.append(output_path)
                    
                    if progress_callback and total_pages > 0:
                        progress = min(90, (page_num / total_pages) * 90)
                        progress_callback(progress, f"Processing page {page_num + 1}/{total_pages}...")
                        
                doc.close()
                
                if progress_callback:
                    progress_callback(100, f"PDF processing complete: {len(image_paths)} pages")
                    
            except Exception as e:
                return []
                
        elif ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif', '.webp']:
            try:
                if progress_callback:
                    progress_callback(0, "Processing image...")
                    
                img = Image.open(file_path).convert("RGB")
                if watermark_text:
                    img = add_watermark(img, watermark_text)
                output_path = os.path.join(output_dir, f"image_1.jpg")
                img.save(output_path, "JPEG", quality=jpeg_quality, optimize=True)
                
                if progress_callback:
                    progress_callback(100, "Image processing complete")
                    
                return [output_path]
            except Exception as e:
                return []
        elif ext in ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm', '.m4v']:
            return extract_video_frames(file_path, watermark_text, frame_interval, progress_callback)
        else:
            return []
            
        return image_paths
    except Exception as e:
        return []