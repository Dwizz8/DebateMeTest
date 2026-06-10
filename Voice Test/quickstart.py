import time
import requests
from sync import Sync
from sync.common import Audio, GenerationOptions, Video
from sync.core.api_error import ApiError
from dotenv import load_dotenv
import os
import cloudinary
import cloudinary.uploader

load_dotenv()  # ← must be first before any os.getenv calls

cloudinary.config(
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key    = os.getenv("CLOUDINARY_API_KEY"),
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
)

SYNC_API_KEY = os.getenv("SYNC_API_KEY")
TRUMP_VIDEO_URL = "https://res.cloudinary.com/dozzqm6mu/video/upload/v1780963000/Video_Project_n78p5i.mp4"
LUXON_VIDEO_URL = "https://res.cloudinary.com/dozzqm6mu/video/upload/v1780974879/Untitled_design_pycbky.mp4"
HIPKINS_VIDEO_URL = "https://res.cloudinary.com/dozzqm6mu/video/upload/v1780877478/Hipkins_Talking_gn9t7n.mp4"
SPEECH_TEXT = "I've got bills. You've got bills. Every Kiwi household has bills. The question is: how do we make life more affordable and help New Zealanders get ahead? That's what National is focused on. Ask me anything about our policies, our plans, and how we'll deliver results for New Zealand."

def generate_video(text: str) -> str:

    # Step 1 — Get raw audio bytes from TTS server
    print("Getting audio from TTS server...")
    tts_response = requests.post(
        "http://localhost:8000/speak",
        headers={"Content-Type": "application/json"},
        json={"text": text}
    )

    # Step 2 — Upload raw bytes to Cloudinary
    print("Uploading audio to Cloudinary...")
    upload = cloudinary.uploader.upload(
        tts_response.content,
        resource_type="raw",
        format="wav"
    )
    audio_url = upload["secure_url"]
    print(f"Audio URL: {audio_url}")

    # Step 3 — Send to Sync.so
    client = Sync(
        base_url="https://api.sync.so",
        api_key=SYNC_API_KEY
    ).generations

    print("Starting lip sync generation...")
    try:
        response = client.create(
            input=[Video(url=LUXON_VIDEO_URL), Audio(url=audio_url)],
            model="lipsync-2",
            options=GenerationOptions(sync_mode="loop"),
        )
    except ApiError as e:
        raise Exception(f"Sync.so failed: {e.status_code} - {e.body}")

    # Step 4 — Poll until done
    job = client.get(response.id)
    while job.status not in ["COMPLETED", "FAILED"]:
        print(f"Polling... {job.status}")
        time.sleep(10)
        job = client.get(response.id)

    if job.status == "FAILED":
        raise Exception("Sync.so generation failed")

    print(f"Done! Video URL: {job.output_url}")
    return job.output_url

if __name__ == "__main__":
    video_url = generate_video(SPEECH_TEXT)
    print(f"\nFinal video: {video_url}")

