import base64
import io
from PIL import Image
import numpy as np
import cv2
from app.services.gpt_client import generate_outline_images

async def generate_line_art(upload, variants):
    image_bytes = await upload.read()
    
    # Call our GPT/DALL-E client
    outlines_b64 = generate_outline_images(image_bytes, int(variants))

    # Return as objects the frontend expects
    variant_results = []
    for i, b64 in enumerate(outlines_b64):
        # We wrap it in a data URI so the React <img> tag can render it directly
        variant_results.append({
            "id": i,
            "url": f"data:image/png;base64,{b64}"
        })

    return variant_results