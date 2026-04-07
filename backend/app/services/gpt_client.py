import os
import io
import base64
import requests
from PIL import Image, ImageEnhance, ImageOps
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def post_process_image(img_data):
    # Load the image from bytes
    img = Image.open(io.BytesIO(img_data)).convert("L") # Convert to Grayscale
    
    # 1. Increase Contrast significantly
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0) 
    
    # 2. Thresholding: Everything darker than 140 becomes 0 (Black)
    # Everything lighter becomes 255 (White)
    # Adjust 140 to be higher if you want more lines, lower for fewer
    fn = lambda x : 255 if x > 140 else 0
    img = img.point(fn, mode='1') # Mode '1' is 1-bit pixels (Black/White)
    
    # Convert back to RGB so it displays nicely in browsers
    img = img.convert("RGB")
    
    # Save back to bytes
    byte_io = io.BytesIO()
    img.save(byte_io, format='PNG')
    return byte_io.getvalue()

def generate_outline_images(image_bytes, variants_count):
    # Load image just to ensure it's a valid format for OpenAI (PNG/JPG/WEBP)
    # We remove the crop/resize logic entirely
    img = Image.open(io.BytesIO(image_bytes))
    
    # Convert to PNG (standard for Edits) but keep original dimensions
    byte_io = io.BytesIO()
    img.save(byte_io, format='PNG')
    byte_io.seek(0)

    prompt = ("""
Convert this image into a coloring-book style outline drawing designed for 3D printing. 
The subject may be a person (portrait) or an object/landscape (e.g., vase, mountain, animal) or abstract. 
Don't had any features. Keep the original drawning/composition. Keep all the lines/patterns/features, without transformation. Including inner detaillines.

Rules:
- NO SOLID BLACK AREAS: Every part of the drawing must be an empty zone defined only by outlines. Do not fill in eyes, hair, or shadows with solid black.
- SUBJECT FLEXIBILITY: If the subject is a portrait, outline the face and hair. If the subject is an object or landscape, outline only the primary structural shapes (e.g., the silhouette of the mountain or the body of the vase).
- THICK & CONTINUOUS: Use thick, consistent black lines. Every line must be strong enough to be extruded.
- CLOSED LOOPS: Lines must be closed wherever possible to create distinct "wells" for sand.
- ZERO DETAIL: No shading, gradients, hatching, or texture. Remove wrinkles, eyelashes, individual hair strands, or fine patterns.
- PURE CONTRAST: Use only black lines on a pure white background. Remove all background elements that are not part of the main subject.

Output goal:
A clean, printable line drawing consisting strictly of empty, outlined "cells" that can be extruded into walls for a sand-art frame.
Don't had any features. Keep the original drawning/composition.
""")

    try:
        response = client.images.edit(
            model="gpt-image-1",
            image=("original_image.png", byte_io, "image/png"),
            prompt=prompt,
            n=int(variants_count),
            # 'auto' tells GPT to adapt to the input image's aspect ratio
            size="auto" 
        )

        outlines_b64 = []
        for data in response.data:
            url = getattr(data, 'url', None)
            if url:
                img_response = requests.get(url)
                if img_response.status_code == 200:
                    # Black and white
                    clean_bytes = post_process_image(img_response.content)
                    encoded_str = base64.b64encode(clean_bytes).decode('utf-8')
                    outlines_b64.append(encoded_str)
            elif hasattr(data, 'b64_json'):
                outlines_b64.append(data.b64_json)
            
        return outlines_b64

    except Exception as e:
        print(f"Error calling gpt-image-1: {e}")
        return []