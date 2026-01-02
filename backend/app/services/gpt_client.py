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
    # 1. Prepare the image (Square PNG)
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    width, height = img.size
    
    # We use 'side' to define the square dimensions
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    
    # FIXED: Changed 'size' to 'side' below
    img = img.crop((left, top, left + side, top + side)).resize((1024, 1024))

    byte_io = io.BytesIO()
    img.save(byte_io, format='PNG')
    byte_io.seek(0)

    prompt = "A high-contrast coloring book outline of this portrait. Bold black lines, pure white background, no shading, no gray."

    try:
        # GPT-image-1 Edit call
        response = client.images.edit(
            model="gpt-image-1",
            image=("image.png", byte_io, "image/png"),
            prompt=prompt,
            n=int(variants_count),
            size="1024x1024"
        )

        outlines_b64 = []
        for data in response.data:
            url = getattr(data, 'url', None)
            if url:
                img_response = requests.get(url)
                if img_response.status_code == 200:
                    encoded_str = base64.b64encode(img_response.content).decode('utf-8')
                    outlines_b64.append(encoded_str)
            
        return outlines_b64

    except Exception as e:
        print(f"Error calling gpt-image-1: {e}")
        return []