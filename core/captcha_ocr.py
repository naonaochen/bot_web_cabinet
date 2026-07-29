"""
Automatic CAPTCHA Recognition Module
Uses OCR (Optical Character Recognition) to automatically read captcha images
"""
from __future__ import annotations

import base64
import os
import re
import logging
import traceback
from pathlib import Path
from typing import Optional
from functools import lru_cache
from collections import Counter
import numpy as np

os.environ["TESSDATA_PREFIX"] = r"C:\Program Files\Tesseract-OCR\tessdata"

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import pytesseract
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    from io import BytesIO
    from datetime import datetime
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    logging.getLogger(__name__).info("OCR init: tesseract_cmd=%s", pytesseract.pytesseract.tesseract_cmd)
    logging.getLogger(__name__).info("OCR init: TESSDATA_PREFIX=%s", os.environ.get("TESSDATA_PREFIX", ""))
    OCR_AVAILABLE = True
except ImportError:
    pytesseract = None
    Image = None
    ImageEnhance = None
    ImageFilter = None
    ImageOps = None
    BytesIO = None
    datetime = None
    OCR_AVAILABLE = False

logger = logging.getLogger(__name__)


CAPTCHA_LENGTH = 4
OCR_WHITELIST = '0123456789'
TEMPLATE_CHARS = '0123456789'


def _clamp_four_digits(text: str) -> str:
    digits = re.sub(r'\D', '', text or '')
    if not digits:
        return ''
    return digits[:CAPTCHA_LENGTH]


def _score_candidate(code: str, score: float, source: str) -> tuple[float, float, float]:
    completeness = 1.0 if len(code) == CAPTCHA_LENGTH else 0.0
    distinct_digits = len(set(code)) / CAPTCHA_LENGTH if code else 0.0
    source_bonus = 0.05 if source.startswith('template') else 0.0
    return (completeness, score, distinct_digits + source_bonus)


def _resize_for_ocr(image, scale_factor: int):
    return image.resize(
        (image.width * scale_factor, image.height * scale_factor),
        Image.Resampling.LANCZOS,
    )


def _cv2_to_pil(binary_img):
    return Image.fromarray(binary_img)


def _pil_to_cv2(image: Image.Image):
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def _image_to_binary(image: Image.Image) -> Image.Image:
    if image.mode == 'RGBA':
        background = Image.new('RGB', image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        image = background
    elif image.mode != 'RGB':
        image = image.convert('RGB')
    image = _resize_for_ocr(image, 3)
    gray = image.convert('L')
    gray = ImageEnhance.Contrast(gray).enhance(2.5)
    gray = gray.filter(ImageFilter.MedianFilter(size=3))
    return gray.point(lambda x: 255 if x > 140 else 0, '1')


def _cv2_preprocess(image: Image.Image):
    rgb = np.array(image.convert('RGB'))
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = np.ones((2, 2), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    return binary


def _extract_digit_rois(binary: np.ndarray) -> list[np.ndarray]:
    inv = 255 - binary
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(inv, connectivity=8)
    rois = []
    h_img, w_img = binary.shape[:2]
    for idx in range(1, num_labels):
        x = stats[idx, cv2.CC_STAT_LEFT]
        y = stats[idx, cv2.CC_STAT_TOP]
        w = stats[idx, cv2.CC_STAT_WIDTH]
        h = stats[idx, cv2.CC_STAT_HEIGHT]
        area = stats[idx, cv2.CC_STAT_AREA]
        if w < 2 or h < 8:
            continue
        if area < 12:
            continue
        if h > h_img * 0.95 and w > w_img * 0.95:
            continue
        rois.append((x, y, w, h, area))
    rois.sort(key=lambda item: (item[0], -item[4]))
    if len(rois) < CAPTCHA_LENGTH:
        return []
    if len(rois) > CAPTCHA_LENGTH:
        rois = sorted(rois, key=lambda item: item[4], reverse=True)[:CAPTCHA_LENGTH]
        rois.sort(key=lambda item: item[0])
    return [binary[y:y+h, x:x+w] for x, y, w, h, _ in rois]


def _resize_digit_array(arr: np.ndarray, size: tuple[int, int] = (28, 28)) -> np.ndarray:
    return cv2.resize(arr, size, interpolation=cv2.INTER_AREA)


def _standardize_digit_array(arr: np.ndarray, size: tuple[int, int] = (28, 28)) -> np.ndarray:
    if arr.ndim == 3:
        arr = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
    arr = 255 - arr if np.mean(arr) > 127 else arr
    ys, xs = np.where(arr < 250)
    if len(xs) and len(ys):
        x0, x1 = xs.min(), xs.max()
        y0, y1 = ys.min(), ys.max()
        arr = arr[y0:y1+1, x0:x1+1]
    arr = _resize_digit_array(arr, size)
    canvas = np.full(size, 255, dtype=np.uint8)
    h, w = arr.shape[:2]
    y_off = (size[1] - h) // 2
    x_off = (size[0] - w) // 2
    canvas[max(0, y_off):max(0, y_off) + h, max(0, x_off):max(0, x_off) + w] = arr[:min(h, size[1]), :min(w, size[0])]
    return canvas


def _crop_ink_bbox(binary_image: Image.Image) -> Image.Image:
    bbox = binary_image.getbbox()
    if bbox:
        return binary_image.crop(bbox)
    return binary_image


def _normalize_template_image(image: Image.Image) -> Image.Image:
    if image.mode == 'RGBA':
        background = Image.new('RGB', image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        image = background
    elif image.mode != 'RGB':
        image = image.convert('RGB')
    image = _resize_for_ocr(image, 3)
    gray = image.convert('L')
    gray = ImageEnhance.Contrast(gray).enhance(2.5)
    gray = gray.filter(ImageFilter.MedianFilter(size=3))
    binary = gray.point(lambda x: 255 if x > 140 else 0, '1')
    return _crop_ink_bbox(binary)


def _binary_to_pil(binary: np.ndarray) -> Image.Image:
    return Image.fromarray(binary)


@lru_cache(maxsize=1)
def _build_digit_templates() -> dict[str, list[Image.Image]]:
    templates: dict[str, list[Image.Image]] = {ch: [] for ch in TEMPLATE_CHARS}
    try:
        font_candidates = [
            r"C:\Windows\Fonts\arialbd.ttf",
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\calibri.ttf",
        ]
        font_path = next((p for p in font_candidates if Path(p).exists()), None)
        if font_path is not None:
            from PIL import ImageDraw, ImageFont
            font_sizes = [26, 28, 30, 32, 36, 40]
            paddings = [2, 4, 6, 8]
            for ch in TEMPLATE_CHARS:
                for font_size in font_sizes:
                    font = ImageFont.truetype(font_path, font_size)
                    for padding in paddings:
                        canvas = Image.new('L', (60, 60), 255)
                        draw = ImageDraw.Draw(canvas)
                        bbox = draw.textbbox((0, 0), ch, font=font)
                        x = (canvas.width - (bbox[2] - bbox[0])) // 2 - bbox[0]
                        y = (canvas.height - (bbox[3] - bbox[1])) // 2 - bbox[1]
                        x += padding // 2
                        y += padding // 2
                        draw.text((x, y), ch, fill=0, font=font)
                        binary = canvas.point(lambda x: 255 if x > 180 else 0, '1')
                        binary = _crop_ink_bbox(binary)
                        templates[ch].append(binary)

        sample_dir = Path("debug/captcha_samples")
        if sample_dir.exists():
            for sample_path in sorted(sample_dir.glob("*.png")):
                stem = sample_path.stem
                if "__" not in stem:
                    continue
                label = stem.split("__")[-1]
                try:
                    sample_img = Image.open(sample_path)
                    if len(label) == 1 and label in TEMPLATE_CHARS:
                        templates[label].append(_normalize_template_image(sample_img))
                    elif len(label) == CAPTCHA_LENGTH and all(ch in TEMPLATE_CHARS for ch in label):
                        norm = _normalize_template_image(sample_img)
                        digit_imgs = _segment_digit_candidates(norm)
                        if len(digit_imgs) >= CAPTCHA_LENGTH:
                            for digit_img, digit_char in zip(digit_imgs[:CAPTCHA_LENGTH], label):
                                templates[digit_char].append(_crop_ink_bbox(digit_img))
                        else:
                            logger.debug("Skipping sample %s: could not split into %d digits", sample_path, CAPTCHA_LENGTH)
                    else:
                        logger.debug("Skipping sample %s: unsupported label '%s'", sample_path, label)
                except Exception as e:
                    logger.debug("Failed to load captcha sample %s: %s", sample_path, e)
    except Exception as e:
        logger.debug("Failed to build digit templates: %s", e)
    return templates


def _mismatch_score(img1: Image.Image, img2: Image.Image) -> float:
    a = img1.convert('1').convert('L')
    b = img2.convert('1').convert('L')
    width = max(a.width, b.width)
    height = max(a.height, b.height)
    canvas_a = Image.new('L', (width, height), 255)
    canvas_b = Image.new('L', (width, height), 255)
    canvas_a.paste(a, ((width - a.width) // 2, (height - a.height) // 2))
    canvas_b.paste(b, ((width - b.width) // 2, (height - b.height) // 2))
    diff = 0
    total = width * height
    if total == 0:
        return 1.0
    pa = canvas_a.load()
    pb = canvas_b.load()
    for y in range(height):
        for x in range(width):
            diff += 0 if pa[x, y] == pb[x, y] else 1
    return diff / total


def _template_score(char_img: Image.Image, digit: str, templates: dict[str, list[Image.Image]]) -> float:
    candidates = templates.get(digit, [])
    if not candidates:
        return 1.0
    return min(_mismatch_score(char_img, template) for template in candidates)


def _match_digit_roi(roi: np.ndarray, templates: dict[str, list[Image.Image]]) -> tuple[str, float]:
    if roi.size == 0:
        return '', 1.0
    roi_pil = Image.fromarray(roi)
    roi_pil = _crop_ink_bbox(roi_pil)
    best_digit = ''
    best_score = 1.0
    for digit in TEMPLATE_CHARS:
        score = _template_score(roi_pil, digit, templates)
        if score < best_score:
            best_score = score
            best_digit = digit
    return best_digit, best_score


def _template_library_stats(templates: dict[str, list[Image.Image]]) -> dict[str, int]:
    return {digit: len(items) for digit, items in templates.items()}


def _segment_digit_candidates(binary_image: Image.Image) -> list[Image.Image]:
    if binary_image.mode != '1':
        binary_image = binary_image.convert('1')
    bbox = binary_image.getbbox()
    if bbox:
        binary_image = binary_image.crop(bbox)
    width, height = binary_image.size
    if width <= 0 or height <= 0:
        return []
    counts = []
    pixels = binary_image.load()
    for x in range(width):
        dark = 0
        for y in range(height):
            if pixels[x, y] == 0:
                dark += 1
        counts.append(dark)

    segments = []
    in_digit = False
    start = 0
    gap_threshold = max(1, height // 10)
    for x, dark in enumerate(counts + [0]):
        if dark > gap_threshold and not in_digit:
            in_digit = True
            start = x
        elif dark <= gap_threshold and in_digit:
            end = x
            if end - start > 1:
                chunk = binary_image.crop((start, 0, end, height))
                chunk_bbox = chunk.getbbox()
                if chunk_bbox:
                    chunk = chunk.crop(chunk_bbox)
                segments.append(chunk)
            in_digit = False

    if len(segments) >= CAPTCHA_LENGTH:
        return segments[:CAPTCHA_LENGTH]

    slices = []
    step = max(1, width // CAPTCHA_LENGTH)
    for idx in range(CAPTCHA_LENGTH):
        left = idx * step
        right = width if idx == CAPTCHA_LENGTH - 1 else min(width, (idx + 1) * step)
        chunk = binary_image.crop((left, 0, right, height))
        chunk_bbox = chunk.getbbox()
        if chunk_bbox:
            chunk = chunk.crop(chunk_bbox)
        slices.append(chunk)
    return slices


def _preprocess_variants(image):
    variants = []
    variants.append(("template_base", preprocess_captcha_image(image)))
    variants.append(("template_light", preprocess_captcha_light(image)))
    variants.append(("template_threshold", _threshold_scan_variants(image)[0][1] if _threshold_scan_variants(image) else preprocess_captcha_image(image)))
    return variants


def _opencv_variants(image):
    if cv2 is None:
        return []
    variants = []
    binary = _cv2_preprocess(image)
    variants.append(("opencv_binary", binary))
    variants.append(("opencv_invert", 255 - binary))
    return variants


def _threshold_scan_variants(image):
    variants = []
    if image.mode == 'RGBA':
        background = Image.new('RGB', image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        image = background
    elif image.mode != 'RGB':
        image = image.convert('RGB')

    image = _resize_for_ocr(image, 2)
    gray = image.convert('L')
    for threshold in (125, 140):
        binary = gray.point(lambda x, t=threshold: 0 if x < t else 255, '1')
        variants.append((f"threshold_{threshold}", binary))
    return variants


def recognize_captcha(page, logger, config: dict) -> Optional[str]:
    """
    Automatically recognize captcha using a template-matching strategy.
    """
    try:
        from io import BytesIO

        captcha_canvas = page.locator("canvas[id*='captcha'], canvas.s-canvas, .captcha canvas, canvas").first
        if captcha_canvas.count():
            logger.info("Found CAPTCHA as <canvas> element")
            captcha_bytes = captcha_canvas.screenshot(type='png')
        else:
            captcha_img = page.locator("img[src*='captcha'], img.captcha, .captcha img, img#captcha").first
            if captcha_img.count():
                logger.info("Found CAPTCHA as <img> element")
                captcha_bytes = captcha_img.screenshot(type='png')
            else:
                logger.warning("Captcha image/canvas not found")
                return None

        save_dir = config.get("files", {}).get("screenshot_dir", "screenshots")
        debug_path = Path(save_dir) / "debug_captcha_original.png"
        try:
            with open(debug_path, 'wb') as f:
                f.write(captcha_bytes)
            logger.info(f"Original captcha saved to: {debug_path}")
        except Exception as e:
            logger.debug(f"Could not save debug image: {e}")

        sample_dir = Path("debug/captcha_samples")
        try:
            sample_dir.mkdir(parents=True, exist_ok=True)
            sample_path = sample_dir / f"captcha_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
            with open(sample_path, 'wb') as f:
                f.write(captcha_bytes)
            logger.info("Captcha sample saved to: %s", sample_path)
            logger.info("Captcha sample note: rename this file with '__correct_digits' later for template labeling")
            build_captcha_sample_index(str(sample_dir))
        except Exception as e:
            logger.debug("Could not save captcha sample: %s", e)

        image = Image.open(BytesIO(captcha_bytes))
        logger.info(f"Captcha image loaded: size={image.size}, mode={image.mode}")

        processed_debug = Path(save_dir) / "debug_captcha_processed.png"
        try:
            processed_debug.parent.mkdir(parents=True, exist_ok=True)
            processed_image = preprocess_captcha_image(image)
            processed_image.save(processed_debug)
            logger.info(f"Processed captcha saved to: {processed_debug}")
        except Exception as e:
            logger.debug(f"Could not save processed image: {e}")
            processed_image = preprocess_captcha_image(image)

        templates = _build_digit_templates()
        logger.info("Template library stats: %s", _template_library_stats(templates))
        min_length = int(config.get("login", {}).get("captcha_min_length", 1))
        variants = _preprocess_variants(image) + _opencv_variants(image)
        best_candidate = None
        best_avg_score = 1.0
        best_source = None
        for tag, variant in variants:
            logger.info("Attempting recognition with %s preprocessing...", tag)
            if cv2 is not None and isinstance(variant, np.ndarray):
                digit_rois = _extract_digit_rois(variant)
                if not digit_rois:
                    logger.debug("No digit contours found for %s", tag)
                    continue
                recognized = []
                scores = []
                for roi in digit_rois:
                    roi_resized = _standardize_digit_array(roi)
                    digit, score = _match_digit_roi(roi_resized, templates)
                    if digit:
                        recognized.append(digit)
                        scores.append(score)
            else:
                binary = _image_to_binary(variant)
                digit_images = _segment_digit_candidates(binary)
                if not digit_images:
                    logger.debug("No digit segments found for %s", tag)
                    continue
                recognized = []
                scores = []
                for idx, digit_img in enumerate(digit_images, 1):
                    scored_digits = []
                    for digit in TEMPLATE_CHARS:
                        score = _template_score(digit_img, digit, templates)
                        scored_digits.append((score, digit))
                    scored_digits.sort(key=lambda item: item[0])
                    if scored_digits:
                        best_score, best_digit = scored_digits[0]
                        recognized.append(best_digit)
                        scores.append(best_score)

            candidate = ''.join(recognized)
            if len(candidate) >= min_length:
                avg_score = (sum(scores) / len(scores)) if scores else 1.0
                logger.info("Candidate from %s: '%s' (score: %.3f)", tag, candidate, avg_score)
                if best_candidate is None or avg_score < best_avg_score:
                    best_candidate = candidate[:CAPTCHA_LENGTH]
                    best_avg_score = avg_score
                    best_source = tag

        if best_candidate:
            logger.info("✓ CAPTCHA recognized by template matching: '%s' (score: %.3f, source: %s)", best_candidate, best_avg_score, best_source)
            return best_candidate

        logger.warning("All recognition attempts failed")
        return None
    except Exception as e:
        logger.error("CAPTCHA recognition failed with exception: %s", str(e))
        try:
            logger.debug(traceback.format_exc())
        except Exception:
            pass
        logger.warning("Falling back to manual captcha input")
        return None


def preprocess_captcha_image(image: Image.Image) -> Image.Image:
    """
    Preprocess captcha image to improve OCR accuracy
    
    Advanced preprocessing steps:
    - Convert to grayscale
    - Noise reduction using Gaussian blur
    - Increase contrast aggressively
    - Binarize with adaptive thresholding
    - Scale up for better recognition
    - Remove borders and lines
    """
    from PIL import ImageEnhance, ImageFilter
    
    # Step 1: Convert to RGBA if needed (handle transparency)
    if image.mode == 'RGBA':
        # Create white background
        background = Image.new('RGB', image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])  # Use alpha channel as mask
        image = background
    elif image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Step 2: Scale up the image for better OCR
    original_size = image.size
    scale_factor = 2
    image = image.resize(
        (image.width * scale_factor, image.height * scale_factor),
        Image.Resampling.LANCZOS
    )
    
    # Step 3: Convert to grayscale
    gray = image.convert('L')
    
    # Step 4: Apply Gaussian blur to reduce noise
    gray = gray.filter(ImageFilter.GaussianBlur(radius=0.5))
    
    # Step 5: Moderate contrast enhancement
    enhancer = ImageEnhance.Contrast(gray)
    enhanced = enhancer.enhance(2.0)

    # Step 6: Light brightness adjustment
    brightness = ImageEnhance.Brightness(enhanced)
    enhanced = brightness.enhance(1.05)

    logger.info(f"Preprocessed captcha: size={original_size}->{enhanced.size}")

    return enhanced


def preprocess_captcha_alternative(image: Image.Image) -> Image.Image:
    """
    Alternative preprocessing for difficult captchas
    Uses different approach: invert colors, then OCR
    """
    from PIL import ImageEnhance, ImageFilter, ImageOps
    
    # Convert to RGB if needed
    if image.mode == 'RGBA':
        background = Image.new('RGB', image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        image = background
    elif image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Scale up gently
    scale_factor = 2
    image = _resize_for_ocr(image, scale_factor)

    # Convert to grayscale
    gray = image.convert('L')

    # Invert colors (sometimes works better for light text on dark background)
    inverted = ImageOps.invert(gray)

    # Enhance contrast modestly
    enhancer = ImageEnhance.Contrast(inverted)
    enhanced = enhancer.enhance(1.6)

    return enhanced


def preprocess_captcha_light(image: Image.Image) -> Image.Image:
    if image.mode == 'RGBA':
        background = Image.new('RGB', image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        image = background
    elif image.mode != 'RGB':
        image = image.convert('RGB')
    image = _resize_for_ocr(image, 2)
    gray = image.convert('L')
    return ImageEnhance.Contrast(gray).enhance(1.3)


def preprocess_captcha_contrast_scan(image: Image.Image) -> Image.Image:
    if image.mode == 'RGBA':
        background = Image.new('RGB', image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        image = background
    elif image.mode != 'RGB':
        image = image.convert('RGB')
    image = _resize_for_ocr(image, 2)
    gray = image.convert('L')
    return ImageEnhance.Contrast(gray).enhance(2.4)


def clean_captcha_text(text: str) -> str:
    """
    Clean recognized captcha text with advanced filtering
    
    Removes:
    - Whitespace and newlines
    - Special characters
    - Non-alphanumeric characters
    - Common OCR artifacts
    """
    import re
    
    # Remove whitespace and normalize
    text = text.strip()
    text = text.replace('\n', '').replace('\r', '').replace(' ', '')
    
    # Remove common OCR artifacts and special characters
    # Keep only alphanumeric characters
    text = re.sub(r'[^a-zA-Z0-9]', '', text)
    
    # Convert to uppercase (most captchas are case-insensitive)
    text = text.upper()
    
    # Remove common confusable characters that might be misread
    # O vs 0, I vs 1 vs l, etc.
    replacements = {
        'O': '0',  # Letter O to zero (common in captchas)
        'I': '1',  # Letter I to one
        'l': '1',  # Lowercase L to one
        'S': '5',  # S to 5 (sometimes confused)
        'Z': '2',  # Z to 2 (sometimes confused)
    }
    
    # Apply replacements cautiously (only if it makes sense)
    # This is optional and depends on your captcha style
    # Uncomment if needed:
    # for old, new in replacements.items():
    #     text = text.replace(old, new)
    
    # Limit length (most captchas are 4-8 characters)
    if len(text) > 10:
        text = text[:8]
    elif len(text) < 3:
        # Too short, likely wrong
        text = ''
    
    return text


def save_captcha_for_debug(page, logger, config: dict, save_dir: str = "debug/captcha"):
    """
    Save captcha image for debugging and template collection.
    """
    try:
        Path(save_dir).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        captcha_canvas = page.locator("canvas[id*='captcha'], canvas.s-canvas, .captcha canvas, canvas").first
        if captcha_canvas.count():
            filepath = Path(save_dir) / f"captcha_canvas_{timestamp}.png"
            captcha_canvas.screenshot(path=str(filepath))
            logger.info("Captcha canvas saved for debugging: %s", filepath)
            return filepath

        captcha_img = page.locator("img[src*='captcha'], img.captcha, .captcha img, img#captcha").first
        if captcha_img.count():
            filepath = Path(save_dir) / f"captcha_img_{timestamp}.png"
            captcha_img.screenshot(path=str(filepath))
            logger.info("Captcha image saved for debugging: %s", filepath)
            return filepath

        logger.warning("No captcha element found to save")
    except Exception as e:
        logger.warning("Failed to save captcha image: %s", str(e))

    return None


def save_captcha_sample(page, logger, config: dict, label: str | None = None, save_dir: str = "debug/captcha_samples", prompt_label: bool = True):
    """
    Save captcha image for building a template library.
    """
    try:
        filepath = save_captcha_for_debug(page, logger, config, save_dir)
        if filepath and label:
            labeled_path = Path(save_dir) / f"{Path(filepath).stem}__{label}.png"
            Path(filepath).rename(labeled_path)
            logger.info("Labeled captcha sample saved to: %s", labeled_path)
            build_captcha_sample_index(save_dir)
            return labeled_path
        if filepath:
            build_captcha_sample_index(save_dir)
            if prompt_label:
                logger.info("Captcha sample saved. If you know the correct digit, rename the file with '__digit' to add it to the template library.")
        return filepath
    except Exception as e:
        logger.warning("Failed to save captcha sample: %s", str(e))
        return None


def build_captcha_sample_index(sample_dir: str = "debug/captcha_samples", index_file: str | None = None) -> Path | None:
    """
    Build or refresh a simple index file for captcha samples.
    """
    try:
        sample_path = Path(sample_dir)
        if not sample_path.exists():
            return None
        if index_file is None:
            index_path = sample_path / "index.txt"
        else:
            index_path = Path(index_file)
        lines = []
        for png_path in sorted(sample_path.glob("*.png")):
            label = ""
            stem = png_path.stem
            if "__" in stem:
                label = stem.split("__")[-1]
            lines.append(f"{png_path.name}\t{label}\n")
        index_path.write_text("".join(lines), encoding="utf-8")
        logger.info("Captcha sample index written to: %s", index_path)
        logger.info("Captcha sample stats: %s", get_captcha_sample_stats(sample_path))
        return index_path
    except Exception as e:
        logger.warning("Failed to build captcha sample index: %s", str(e))
        return None


def get_captcha_sample_stats(sample_dir: str | Path = "debug/captcha_samples") -> dict[str, int]:
    """
    Count captcha samples per label.
    """
    stats = {ch: 0 for ch in TEMPLATE_CHARS}
    try:
        sample_path = Path(sample_dir)
        if not sample_path.exists():
            return stats
        for png_path in sample_path.glob("*.png"):
            stem = png_path.stem
            if "__" not in stem:
                continue
            label = stem.split("__")[-1]
            if label in stats:
                stats[label] += 1
    except Exception as e:
        logger.debug("Failed to compute captcha sample stats: %s", e)
    return stats
