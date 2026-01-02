import tempfile
import uuid
import logging
import base64
import os
from fastapi import FastAPI, UploadFile, File, Form, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from app.services.generate_stl_from_image import generate_stl_from_image
from app.services.image_pipeline import generate_line_art

# Setup basic logging to see it in Docker logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sand-backend")

app = FastAPI(title="Sand Art Backend", version="0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Simplified for debugging
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/generate-variants")
async def generate_variants(file: UploadFile = File(...), count: int = Form(...)):
    logger.info(f"--- STEP 1: Received image {file.filename} for {count} variants ---")
    
    # Process image through AI pipeline
    # Note: image_pipeline needs to return a list of URLs or base64 strings
    variants = await generate_line_art(file, count)
    
    logger.info(f"--- STEP 1 COMPLETE: Generated {len(variants)} variants ---")
    return {"variants": variants}

@app.post("/generate-stl")
async def generate_model(data: dict = Body(...)):
    variant_url = data.get("image_url")
    settings = data.get("settings", {})
    
    logger.info(f"--- STEP 2: Building STL for variant ---")

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
    stl_path = generate_stl_from_image(image_bytes, settings)

    # 3. Verify path exists using 'os'
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