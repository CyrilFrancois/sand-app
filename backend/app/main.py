import tempfile
import uuid
import logging
import base64
import os
import io
import shutil  # <--- ADDED THIS IMPORT
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
    content = await file.read()
    with Image.open(io.BytesIO(content)) as img:
        width, height = img.size
    
    file.file.seek(0)
    variants_data = await generate_line_art(file, count)
    
    rich_variants = []
    for i, v_raw in enumerate(variants_data):
        if isinstance(v_raw, dict):
            image_url = v_raw.get("url") or v_raw.get("b64_json")
        else:
            image_url = v_raw

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
    
    scale_percent = settings.get("scalePercent", 100)
    logger.info(f"--- STEP 2: Building STL (Scale: {scale_percent}%) ---")

    # --- UPDATED LOGIC TO HANDLE BOTH BASE64 AND LOCAL PATHS ---
    image_input = None

    # Check if the input is a local file path (Direct Upload)
    if isinstance(variant_url, str) and variant_url.startswith("/tmp/"):
        image_input = variant_url
    else:
        # It's a Base64 string (from AI Variants)
        try:
            if "," in variant_url:
                _, encoded = variant_url.split(",", 1)
                image_input = base64.b64decode(encoded)
            else:
                image_input = base64.b64decode(variant_url)
        except Exception as e:
            logger.error(f"Base64 decoding failed: {e}")
            return JSONResponse(status_code=400, content={"error": "Invalid image data"})

    # Pass the resolved image_input (either bytes or path string)
    stl_path = generate_stl_from_image(image_input, settings)

    if stl_path and os.path.exists(stl_path):
        logger.info(f"--- STEP 2 COMPLETE: STL generated at {stl_path} ---")
        return FileResponse(
            stl_path, 
            filename=f"sand-art-{uuid.uuid4().hex[:6]}.stl",
            media_type="application/sla"
        )
    
    return JSONResponse(status_code=500, content={"error": "STL generation failed"})

@app.post("/upload-direct")
async def upload_direct(file: UploadFile = File(...)):
    os.makedirs("/tmp", exist_ok=True)
    file_path = f"/tmp/{uuid.uuid4().hex}_{file.filename}"
    
    try:
        # Read the uploaded bytes
        content = await file.read()
        # Open with PIL to "validate" and "standardize" it
        with Image.open(io.BytesIO(content)) as img:
            # Convert to RGBA to ensure it's a standard format PIL can always re-read
            standardized_img = img.convert("RGBA")
            standardized_img.save(file_path, "PNG")
            w, h = standardized_img.size
            
        logger.info(f"Direct upload standardized and saved to {file_path}")
        
        return {
            "server_url": file_path, 
            "width": w, 
            "height": h
        }
    except Exception as e:
        logger.error(f"Failed to process direct upload: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/health")
def health():
    return {"status": "ok"}