import tempfile
import uuid
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from services.image_pipeline import generate_line_art
from services.svg_to_stl import svg_to_stl

app = FastAPI(
    title="Sand Art Backend",
    version="0.1"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/generate")
async def generate(
    image: UploadFile = File(...),
    variants: int = Form(...),
    wall_height: float = Form(...),
    wall_thickness: float | None = Form(None),
    base_plate: bool = Form(False),
):
    # >>> STEP 1 — get outlines
    svgs = await generate_line_art(image, variants)

    # >>> STEP 2 — for now generate ONE STL
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".stl")
    svg_to_stl(svgs[0], tmp.name, wall_height, wall_thickness, base_plate)

    return FileResponse(tmp.name, filename=f"{uuid.uuid4()}.stl")


@app.get("/health")
def health():
    return JSONResponse({"status": "ok"})
