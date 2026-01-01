import base64
import requests
from config import OPENAI_API_KEY

API_URL = "https://api.openai.com/v1/images/generations"


def generate_outline_images(image_bytes, count):
    if not OPENAI_API_KEY:
        raise RuntimeError("Missing OPENAI_API_KEY")

    b64 = base64.b64encode(image_bytes).decode("utf-8")

    prompt = """
Convert this portrait into realistic coloring-book style.
Keep only main contours.
Thick black outlines.
White background.
No shading.
No gray.
Closed shapes only.
"""

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }

    payload = {
        "model": "gpt-image-1",
        "prompt": prompt,
        "n": count,
        "image": b64,
        "size": "1024x1024"
    }

    r = requests.post(API_URL, json=payload, headers=headers, timeout=60)
    r.raise_for_status()

    return [d["b64_json"] for d in r.json()["data"]]
