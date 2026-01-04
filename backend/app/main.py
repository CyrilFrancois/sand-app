import tempfile
import uuid
import logging
import base64
import os
import io
from PIL import Image
from fastapi import FastAPI, UploadFile, File, Form, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from app.services.generate_stl_from_image import generate_stl_from_image
from app.services.image_pipeline import generate_line_art

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sand-backend")

app = FastAPI(title="Sand Art Backend", version="0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/generate-variants")
async def generate_variants(file: UploadFile = File(...), count: int = Form(...)):
    logger.info(f"--- STEP 1: Received image {file.filename} for {count} variants ---")
    
    # 1. Read file to get original dimensions
    content = await file.read()
    with Image.open(io.BytesIO(content)) as img:
        width, height = img.size
    
    file.file.seek(0)

    # 2. Process image
    variants_data = await generate_line_art(file, count)
    
    # 3. Package variants with metadata
    rich_variants = []
    for i, v_raw in enumerate(variants_data):
        # FIX: Check if OpenAI returned a dictionary with a 'url' or 'b64_json' key
        if isinstance(v_raw, dict):
            # Try to get URL first, then b64_json
            image_url = v_raw.get("url") or v_raw.get("b64_json")
        else:
            image_url = v_raw

        # Ensure the string is formatted for the browser
        if image_url and not image_url.startswith(("data:image", "http")):
            image_url = f"data:image/png;base64,{image_url}"
            
        rich_variants.append({
            "id": i,
            "url": image_url,
            "width": width,
            "height": height
        })
    
    logger.info(f"--- STEP 1 COMPLETE: Generated {len(rich_variants)} variants ---")
    return {"variants": rich_variants}

@app.post("/generate-stl")
async def generate_model(data: dict = Body(...)):
    variant_url = data.get("image_url")
    settings = data.get("settings", {})
    
    # Extract the new high-precision settings
    # Defaults are handled here in case frontend misses them
    wall_thickness = settings.get("wallThickness", 0.3)
    wall_height = settings.get("wallHeight", 3.0)
    base_plate = settings.get("basePlate", True)
    base_plate_thickness = settings.get("basePlateThickness", 0.3)
    scale_percent = settings.get("scalePercent", 100)

    logger.info(f"--- STEP 2: Building STL (Scale: {scale_percent}%, Wall: {wall_thickness}mm) ---")

    # 1. Decode the Base64 image
    try:
        if "," in variant_url:
            _, encoded = variant_url.split(",", 1)
            image_bytes = base64.b64decode(encoded)
        else:
            image_bytes = base64.b64decode(variant_url)
    except Exception as e:
        logger.error(f"Base64 decoding failed: {e}")
        return JSONResponse(status_code=400, content={"error": "Invalid image data"})

    # 2. Generate the STL
    # We pass the full settings dictionary which now includes our 0.3mm precision
    stl_path = generate_stl_from_image(image_bytes, settings)

    # 3. Verify path exists and return file
    if stl_path and os.path.exists(stl_path):
        logger.info(f"--- STEP 2 COMPLETE: STL generated at {stl_path} ---")
        return FileResponse(
            stl_path, 
            filename=f"sand-art-{uuid.uuid4().hex[:6]}.stl",
            media_type="application/sla"
        )
    
    return JSONResponse(status_code=500, content={"error": "STL generation failed"})

@app.get("/health")
def health():
    return {"status": "ok"}