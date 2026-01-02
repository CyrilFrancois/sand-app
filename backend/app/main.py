import tempfile
import uuid
import logging
from fastapi import FastAPI, UploadFile, File, Form, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from backend.app.services.generate_stl_from_image import generate_stl_from_image
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
    
    logger.info(f"--- STEP 2: Building STL for {variant_url} ---")
    logger.info(f"Settings: {settings}")

    # Create temporary file for STL
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".stl")
    
    # Process the 3D conversion
    # Note: generate_stl_from_image needs to be able to handle the variant_url/data
    generate_stl_from_image(
        variant_url, 
        tmp.name, 
        settings.get("wallHeight", 3.0), 
        settings.get("wallThickness", 0.8), 
        settings.get("basePlate", True)
    )

    logger.info(f"--- STEP 2 COMPLETE: STL generated at {tmp.name} ---")
    return FileResponse(tmp.name, filename=f"sand-art-{uuid.uuid4().hex[:6]}.stl")

@app.get("/health")
def health():
    return {"status": "ok"}