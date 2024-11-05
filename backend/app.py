from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from transformers import BlipProcessor, BlipForConditionalGeneration
from gtts import gTTS
import torch
from PIL import Image
import io
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Allow requests from the frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load the BLIP model
processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")

# Ensure the audio directory exists
audio_dir = "audio"
os.makedirs(audio_dir, exist_ok=True)

@app.post("/describe-image/")
async def describe_image(file: UploadFile = File(...)):
    # Load and process the image
    image = Image.open(io.BytesIO(await file.read()))
    inputs = processor(image, return_tensors="pt")
    caption_ids = model.generate(inputs.pixel_values, max_new_tokens=50)
    description = processor.decode(caption_ids[0], skip_special_tokens=True)
    
    # Generate TTS audio
    audio_path = os.path.join(audio_dir, "description_audio.mp3")
    tts = gTTS(description)
    tts.save(audio_path)

    return JSONResponse({"description": description, "audio_url": f"/audio/{os.path.basename(audio_path)}"})

@app.get("/audio/{filename}")
async def get_audio(filename: str):
    response = FileResponse(os.path.join(audio_dir, filename))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
