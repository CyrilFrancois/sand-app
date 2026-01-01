import base64
import io
from PIL import Image
import numpy as np
import cv2
from app.services.gpt_client import generate_outline_images


async def generate_line_art(upload, variants):
    image_bytes = await upload.read()

    # call GPT
    outlines = generate_outline_images(image_bytes, variants)

    svgs = []

    for b64 in outlines:
        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("L")
        np_img = np.array(img)

        # binary threshold
        _, bw = cv2.threshold(np_img, 180, 255, cv2.THRESH_BINARY_INV)

        # TODO: replace with real vectorization
        # temporary fake SVG
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1000">
            <rect x="10" y="10" width="980" height="980" stroke="black" fill="none"/>
        </svg>
        """

        svgs.append(svg)

    return svgs
