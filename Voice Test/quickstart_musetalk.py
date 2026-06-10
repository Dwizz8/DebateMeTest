"""
quickstart_musetalk.py
======================
Test script: Fish Audio TTS -> MuseTalk lip-sync -> plays video in browser.

This replaces the Sync.so approach entirely. Everything runs locally
on your 1080 Ti.

Folder layout expected:
  ./MuseTalk/                  <- cloned MuseTalk repo (with weights downloaded)
  ./politician_videos/
      trump.mp4                <- 5-10 sec front-facing video, 25fps
      hipkins.mp4
      luxon.mp4
  ./musetalk_outputs/          <- created automatically, output videos land here
  ./musetalk_temp/             <- created automatically, scratch files

Usage:
  1. Activate the conda env:   conda activate debate-me-musetalk310
  2. Make sure TTS server is running: uvicorn tts:app --reload  (port 8000)
  3. Run:  python quickstart_musetalk.py
  4. A browser tab opens playing the generated video when done.
"""

import os
import subprocess
import shutil
import uuid
import webbrowser
import http.server
import threading
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
MUSETALK_DIR    = Path("C:/Users/Luka/MuseTalk")
POLITICIAN_VIDEOS = {
    "trump":   Path("./politician_videos/trump.mp4"),
    "hipkins": Path("./politician_videos/hipkins.mp4"),
    "luxon":   Path("./politician_videos/luxon.mp4"),
}
OUTPUT_DIR = Path("./musetalk_outputs")
TEMP_DIR   = Path("./musetalk_temp")

# Which politician and what they say — edit these to test
POLITICIAN  = "hipkins"
SPEECH_TEXT = "Peter Piper picked a peck of pickled peppers."

# TTS server (your mate's FastAPI)
TTS_URL = "http://localhost:8000/speak"


# ── Helpers ───────────────────────────────────────────────────────────────────
def get_audio(text: str, politician: str) -> bytes:
    """Call Fish Audio TTS server, return raw MP3 bytes."""
    print(f"[1/4] Getting audio from TTS server...")
    response = requests.post(
        TTS_URL,
        headers={"Content-Type": "application/json"},
        json={"text": text, "character": politician},
        timeout=60,
    )
    response.raise_for_status()
    print(f"      Got {len(response.content):,} bytes of audio")
    return response.content


def convert_audio_to_16k_wav(mp3_bytes: bytes, wav_path: Path) -> bool:
    """
    Convert MP3 bytes -> 16kHz mono WAV file.
    MuseTalk requires 16kHz WAV — Fish Audio returns MP3.
    Uses ffmpeg (already installed in the conda env).
    """
    print(f"[2/4] Converting audio to 16kHz WAV...")
    mp3_path = wav_path.with_suffix(".mp3")
    mp3_path.write_bytes(mp3_bytes)

    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i",  str(mp3_path),
            "-ar", "16000",   # 16kHz — MuseTalk requirement
            "-ac", "1",       # mono
            str(wav_path),
        ],
        capture_output=True,
        timeout=30,
    )
    mp3_path.unlink(missing_ok=True)

    if result.returncode != 0:
        print(f"      ffmpeg error: {result.stderr.decode()}")
        return False

    print(f"      Saved to {wav_path}")
    return True


def run_musetalk(video_path: Path, audio_path: Path, output_path: Path) -> bool:
    """
    Run MuseTalk standard inference.

    What this does:
      1. Copies input-data into the MuseTalk repo directory (MuseTalk
         reads from its own working directory, not absolute paths)
      2. Writes a minimal YAML inference config pointing at those files
      3. Runs: python -m scripts.inference --inference_config <yaml>
      4. Copies the result out of MuseTalk's results/ folder

    The YAML format matches the tutor's ja-test.yaml exactly:
      task_0:
        video_path: "input-data/<video>"
        audio_path: "input-data/<audio>"
    """
    print(f"[3/4] Running MuseTalk...")

    # MuseTalk needs input-data/ inside its own repo directory
    musetalk_input = MUSETALK_DIR / "input-data"
    musetalk_input.mkdir(exist_ok=True)

    # Copy files in
    video_dest = musetalk_input / video_path.name
    audio_dest = musetalk_input / audio_path.name
    shutil.copy2(video_path, video_dest)
    shutil.copy2(audio_path, audio_dest)

    # Write the inference config YAML
    config_path = MUSETALK_DIR / "debate_inference_config.yaml"
    config_path.write_text(
        f'task_0:\n'
        f'  video_path: "input-data/{video_path.name}"\n'
        f'  audio_path: "input-data/{audio_path.name}"\n'
    )

    # Run MuseTalk from inside its repo directory
    result = subprocess.run(
        [
            "python", "-m", "scripts.inference",
            "--inference_config", str(config_path.resolve()),
        ],
        cwd=str(MUSETALK_DIR),
        capture_output=False,  # show live output so you can see GPU progress
        timeout=300,           # 5 min ceiling
    )

    # Clean up input-data from MuseTalk repo
    shutil.rmtree(str(musetalk_input), ignore_errors=True)
    config_path.unlink(missing_ok=True)

    if result.returncode != 0:
        print(f"      MuseTalk failed with return code {result.returncode}")
        return False

    # Find the output — MuseTalk writes to results/ inside its repo
    musetalk_results = MUSETALK_DIR / "results"
    mp4_files = list(musetalk_results.glob("**/*.mp4"))
    if not mp4_files:
        print(f"      No .mp4 found in {musetalk_results}")
        return False

    # Take the most recently created one
    latest = max(mp4_files, key=lambda p: p.stat().st_mtime)
    shutil.move(str(latest), str(output_path))
    print(f"      Output saved to {output_path}")
    return True


def play_video_in_browser(video_path: Path) -> None:
    """Spin up a tiny HTTP server and open the video in the default browser."""
    print(f"[4/4] Opening video in browser...")

    port = 9999
    serve_dir = video_path.parent

    # Simple one-file HTTP server
    handler = http.server.SimpleHTTPRequestHandler
    httpd = http.server.HTTPServer(("", port), handler)
    httpd.allow_reuse_address = True

    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    url = f"http://localhost:{port}/{video_path.name}"
    print(f"      Opening: {url}")
    webbrowser.open(url)

    input("\nPress Enter to stop the server and exit...")
    httpd.shutdown()


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    # Setup directories
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # Validate inputs
    if not MUSETALK_DIR.exists():
        print(f"ERROR: MuseTalk not found at {MUSETALK_DIR}")
        print("Clone it: git clone https://github.com/TMElyralab/MuseTalk")
        return

    video_path = POLITICIAN_VIDEOS.get(POLITICIAN)
    if not video_path or not video_path.exists():
        print(f"ERROR: No video for '{POLITICIAN}' at {video_path}")
        print("Add a short 5-10 sec front-facing video at that path.")
        return

    job_id = str(uuid.uuid4())[:8]
    wav_path    = TEMP_DIR  / f"{job_id}_audio_16k.wav"
    output_path = OUTPUT_DIR / f"{job_id}_{POLITICIAN}.mp4"

    try:
        # Step 1: Get audio from TTS
        mp3_bytes = get_audio(SPEECH_TEXT, POLITICIAN)

        # Step 2: Convert to 16kHz WAV
        if not convert_audio_to_16k_wav(mp3_bytes, wav_path):
            print("Audio conversion failed — check ffmpeg is in your PATH")
            return

        # Step 3: Run MuseTalk
        if not run_musetalk(video_path, wav_path, output_path):
            print("MuseTalk failed — check the output above for errors")
            return

        print(f"\n✓ Done! Generated: {output_path}")

        # Step 4: Play in browser
        play_video_in_browser(output_path)

    finally:
        # Clean up temp files
        wav_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
