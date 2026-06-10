// ── Audio state ───────────────────────────────────────────────────────────────
// These are declared outside functions so they persist between loadAudio() and play()
let audioCtx, analyser, audioBuffer;

async function loadAudio() {
    // Create the browser's audio workspace — must be triggered by a user gesture
    // (button click) otherwise the browser blocks it
    audioCtx = new AudioContext();

    // Call the TTS server
    // The server returns raw MP3 audio bytes
    const response = await fetch('http://localhost:8000/speak', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: "A month into Lincoln's presidency..." })
    });

    // Convert the raw bytes into an ArrayBuffer, then decode it into
    // a format the AudioContext can actually play
    const arrayBuffer = await response.arrayBuffer();
    audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);

    // Audio is ready — start playing and animating
    play();
}

function play() {
    // Create an analyser node — this sits between the audio source and the
    // speakers, letting us read the volume 60 times per second without
    // interrupting playback
    analyser = audioCtx.createAnalyser();

    // 256 gives us 128 frequency bins — enough for mouth animation
    analyser.fftSize = 256;

    // Create the audio source from our decoded buffer and chain it:
    // source → analyser → speakers
    const source = audioCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(analyser);
    analyser.connect(audioCtx.destination);
    source.start();

    // Array that gets filled with frequency data on every tick
    // Each value is 0-255 representing volume at that frequency band
    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    const img = document.getElementById('hipkins');

    function tick() {
        // Snapshot the current audio frequencies into dataArray
        analyser.getByteFrequencyData(dataArray);

        // Slice bands 2-18 which covers the voice frequency range
        // Average them into a single loudness value (0-255)
        const avg = dataArray.slice(2, 18).reduce((a, b) => a + b) / 16;

        // Map the loudness value to a mouth frame
        // Higher avg = louder = more open mouth
        // These thresholds were tuned manually for the Fish Audio output volume
        if (avg < 80) {
            img.src = 'PoliticianExpressions/luxon/mouth-closed.png';
        } else if (avg < 110) {
            img.src = 'PoliticianExpressions/luxon/mouth-slight.png';
        } else if (avg < 150) {
            img.src = 'PoliticianExpressions/luxon/mouth-half.png';
        } else {
            img.src = 'PoliticianExpressions/luxon/mouth-open.png';
        }

        // Schedule the next tick — runs ~60 times per second in sync with
        // the browser's render cycle
        requestAnimationFrame(tick);
    }

    // Start the animation loop
    tick();

    // When the audio finishes, reset to closed mouth
    source.onended = () => img.src = 'PoliticianExpressions/luxon/mouth-closed.png';
}