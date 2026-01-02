import os
import io
import base64
import requests
from PIL import Image
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_outline_images(image_bytes, variants_count):
    # Load image just to ensure it's a valid format for OpenAI (PNG/JPG/WEBP)
    # We remove the crop/resize logic entirely
    img = Image.open(io.BytesIO(image_bytes))
    
    # Convert to PNG (standard for Edits) but keep original dimensions
    byte_io = io.BytesIO()
    img.save(byte_io, format='PNG')
    byte_io.seek(0)

    prompt = ("""
Convert this portrait into a coloring-book style outline drawing designed for 3D printing.

Rules:
- Keep only the main structural lines of the face, hair, and clothing.
- Use thick, continuous black lines.
- Lines must be closed wherever possible.
- No shading, no gradients, no hatching, no textures.
- No colors except black on pure white background.
- Simplify details: remove eyelashes, wrinkles, small texture details, hair strands, background.
- Keep recognizable facial features but simplified.

Output goal:
A clean, printable line drawing that looks like a coloring book page and can be extruded into walls for a sand-art frame.
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
                    encoded_str = base64.b64encode(img_response.content).decode('utf-8')
                    outlines_b64.append(encoded_str)
            elif hasattr(data, 'b64_json'):
                outlines_b64.append(data.b64_json)
            
        return outlines_b64

    except Exception as e:
        print(f"Error calling gpt-image-1: {e}")
        return []