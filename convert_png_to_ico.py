"""
Convert PNG to ICO format for Windows application icon
Usage: python convert_png_to_ico.py input.png output.ico
"""
from PIL import Image
import sys

def png_to_ico(png_path, ico_path):
    """Convert PNG image to ICO format"""
    # Open PNG image
    img = Image.open(png_path)
    
    # Convert to RGBA if needed
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    # Resize to standard icon sizes (optional, but recommended)
    # Windows supports multiple sizes in one ICO file
    sizes = [(16, 16), (32, 32), (48, 48), (256, 256)]
    
    # Save as ICO with multiple sizes
    img.save(ico_path, format='ICO', sizes=sizes)
    print(f"[OK] Converted {png_path} to {ico_path}")
    print(f"   Sizes included: {', '.join([f'{w}x{h}' for w,h in sizes])}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python convert_png_to_ico.py input.png output.ico")
        sys.exit(1)
    
    png_file = sys.argv[1]
    ico_file = sys.argv[2]
    
    try:
        png_to_ico(png_file, ico_file)
    except Exception as e:
        print(f"[ERROR] Conversion failed: {e}")
        sys.exit(1)
