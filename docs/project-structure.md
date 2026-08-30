# Project Structure

```text
VIUStudio/
├── ui/
│   ├── gui.py                 # Application entry point
│   ├── main_window.py         # Main-window behavior and signal handling
│   ├── controllers/           # Pipeline, preview, and subtitle controllers
│   ├── views/                 # Launcher, panels, timeline, inspectors
│   ├── widgets/               # MPV preview and custom Qt widgets
│   ├── worker_adapters/       # QThread adapters
│   └── utils/                 # UI/media/settings helpers
├── app/
│   ├── workflows/             # Prepare, voice, and export workflows
│   ├── translation/           # Translation orchestration and providers
│   ├── engines/               # Whisper, OCR, TTS, FFmpeg adapters
│   ├── services/              # Project, resource, ASR, diarization services
│   ├── layers/                # Timeline track and layer domain models
│   ├── ocr_processor.py       # OCR subtitle extraction
│   ├── whisper_processor.py   # Faster-Whisper integration
│   └── sensevoice_processor.py
├── bin/                       # FFmpeg, MPV, on-demand CUDA runtime
├── models/                    # Downloaded ASR, Piper, and diarization models
├── assets/                    # Icons, fonts, and image assets
├── docs/                      # Focused project documentation
├── .env_example               # Optional environment template
└── requirements-*.txt         # Python dependency sets
```

Projects and generated artifacts are stored beneath `projects/`; temporary preview and processing files are stored beneath `temp/`.
