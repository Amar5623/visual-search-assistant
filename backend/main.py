import hashlib
import redis
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from transformers import BlipProcessor, BlipForConditionalGeneration, CLIPProcessor, CLIPModel
import torch
from PIL import Image
import io
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
from TTS.api import TTS
import logging
from datetime import datetime

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI instance
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis setup
redis_client = redis.StrictRedis(host="localhost", port=6379, db=0, decode_responses=True)

# Load environment variables and models
HF_AUTH_TOKEN = os.getenv("HF_AUTH_TOKEN")
processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-large", token=HF_AUTH_TOKEN)
blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-large", token=HF_AUTH_TOKEN)
clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

# Directory for audio output
audio_dir = "audio"
os.makedirs(audio_dir, exist_ok=True)

# Define VITS models and speakers
tts_model = "tts_models/en/vctk/vits"
female_speaker = "p270"  # VCTK speaker ID for a female voice
male_speaker = "p317"    # VCTK speaker ID for a male voice

def get_tts_model_and_speaker(speaker_type):
    if speaker_type.lower() == "female":
        logger.info(f"{datetime.now()} - Selected female model with speaker: {female_speaker}")
        return tts_model, female_speaker
    else:
        logger.info(f"{datetime.now()} - Selected male model with speaker: {male_speaker}")
        return tts_model, male_speaker

# Function to generate a hash for images
def get_image_hash(image):
    return hashlib.md5(image).hexdigest()

# Function to refine description using CLIP
def refine_description_with_clip(image, initial_description):
    inputs = clip_processor(text=[initial_description], images=image, return_tensors="pt", padding=True)
    outputs = clip_model(**inputs)
    refined_description = initial_description  # Update logic as needed
    return refined_description

@app.post("/describe-image/")  # Endpoint to describe the image and generate audio
async def describe_image(
    file: UploadFile = File(...),
    speaker_type: str = Form("female"),
    description_type: str = Form("detailed")
):
    try:
        logger.info(f"{datetime.now()} - Starting image description process")

        image_data = await file.read()
        logger.info(f"{datetime.now()} - Image data read successfully")

        image_hash = get_image_hash(image_data)
        logger.info(f"{datetime.now()} - Generated image hash: {image_hash}")

        # Check Redis key type and reset if necessary
        key_type = redis_client.type(image_hash)
        if key_type != "hash" and key_type != "none":
            redis_client.delete(image_hash)
            logger.info(f"{datetime.now()} - Redis key reset for hash: {image_hash}")

        # Check if description is cached in Redis
        cached_data = redis_client.hgetall(image_hash)
        cached_description = cached_data.get(description_type) if cached_data else None
        audio_filename = f"{image_hash}_{description_type}_{speaker_type}_audio.wav"
        audio_path = os.path.join(audio_dir, audio_filename)

        # Only generate description if not cached
        if not cached_description:
            logger.info(f"{datetime.now()} - Processing image for new description")
            image = Image.open(io.BytesIO(image_data))
            inputs = processor(image, return_tensors="pt").to("cuda" if torch.cuda.is_available() else "cpu")

            # Adjust generation parameters for detailed vs. simplified
            generation_args = {
                "max_length": 150 if description_type == "detailed" else 40,
                "min_length": 40 if description_type == "detailed" else 8,
                "num_beams": 5 if description_type == "detailed" else 1,
                "no_repeat_ngram_size": 2,
                "early_stopping": True,
            }

            # Generate initial description
            caption_ids = blip_model.generate(inputs["pixel_values"], **generation_args)
            initial_description = processor.decode(caption_ids[0], skip_special_tokens=True)
            logger.info(f"{datetime.now()} - Initial description generated")

            # Refine description with CLIP
            refined_description = refine_description_with_clip(image, initial_description)
            redis_client.hset(image_hash, description_type, refined_description)
            cached_description = refined_description
            logger.info(f"{datetime.now()} - Description refined and cached")

        # Only generate audio if not cached
        if not os.path.exists(audio_path):
            logger.info(f"{datetime.now()} - Generating audio for description")
            tts_model, speaker = get_tts_model_and_speaker(speaker_type)
            tts = TTS(tts_model, gpu=torch.cuda.is_available())
            tts.tts_to_file(text=cached_description, file_path=audio_path, speaker=speaker)
            logger.info(f"{datetime.now()} - Audio generated using TTS with speaker {speaker}")

        return JSONResponse({
            "description": cached_description,
            "audio_url": f"/audio/{audio_filename}",
            "image_url": f"data:image/png;base64,{image_data.hex()}"
        })
    
    except Exception as e:
        logger.error(f"{datetime.now()} - Error occurred: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.get("/audio/{filename}")  # Endpoint to retrieve audio file
async def get_audio(filename: str):
    try:
        logger.info(f"{datetime.now()} - Request received for audio file: {filename}")
        file_path = os.path.join(audio_dir, filename)
        if os.path.exists(file_path):
            logger.info(f"{datetime.now()} - Audio file found: {filename}")
            return FileResponse(file_path)

        # Regenerate audio if missing
        parts = filename.split("_")
        image_hash = parts[0]
        description_type = parts[1] if len(parts) > 1 else "detailed"

        cached_description = redis_client.hget(image_hash, description_type)
        if not cached_description:
            raise RuntimeError(f"Description for {description_type} not found in cache.")

        tts_model, speaker = get_tts_model_and_speaker("female")  # Default to female
        tts = TTS(tts_model, progress_bar=False, gpu=torch.cuda.is_available())
        tts.tts_to_file(text=cached_description, file_path=file_path, speaker=speaker)
        logger.info(f"{datetime.now()} - Audio regenerated and returned for file: {filename}")
        return FileResponse(file_path)

    except Exception as e:
        logger.error(f"{datetime.now()} - Error occurred while fetching audio: {e}")
        return JSONResponse(
            {"error": f"Audio file {filename} not found and could not be regenerated."},
            status_code=404
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=os.getenv(PORT))
