# Requirements and Resources

## System requirements

- Windows 10/11
- Python 3.11 when running from source
- FFmpeg and libmpv are included in the application resources
- CPU mode works on systems without an NVIDIA GPU

## GPU mode

GPU acceleration is used by Faster-Whisper and RapidOCR. It requires a supported NVIDIA GPU and a current NVIDIA driver. The CUDA runtime pack is intentionally downloaded on demand through **Manage Resources** rather than bundled into the installer.

No CUDA Toolkit installation is required when the CUDA runtime pack is installed.

## Resource Manager

Open **Manage Resources** from the launcher or Settings. It reports each resource as Ready, Partial, or Missing and provides download links.

| Resource | Target folder |
| --- | --- |
| Faster-Whisper models | `models/faster_whisper/` |
| CUDA 12 runtime pack | `bin/cuda12_fw/` |
| SenseVoice model | `models/sensevoice/` |
| Vietnamese Piper voices | `models/piper/` |
| English Piper voices | `models/piper-en/` |
| Speaker diarization models | `models/pyannote/` |

## Environment configuration

Copy `.env_example` to `.env` only for manual setup. The active variables are:

| Group | Variables |
| --- | --- |
| AI translation | `OPENAI_PROVIDER`, `AI_POLISHER_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL` |
| Google AI Studio | `GOOGLE_AI_STUDIO_API_KEY`, `GOOGLE_AI_STUDIO_MODEL`, `GOOGLE_AI_STUDIO_BASE_URL` |
| OCR crop | `OCR_SUBTITLE_REGION`, `OCR_SAMPLING_FPS`, optional `OCR_CROP_RATIO`, `OCR_SUBTITLE_RECT` |
| Remote API | `VIUSTUDIO_REMOTE_API_URL`, `VIUSTUDIO_REMOTE_API_TOKEN`, `VIUSTUDIO_REMOTE_API_HOST`, `VIUSTUDIO_REMOTE_API_PORT`, `VIUSTUDIO_REMOTE_API_TIMEOUT`, `VIUSTUDIO_QUIET` |
| Optional Whisper tuning | `VIUSTUDIO_WHISPER_DEVICE`, `VIUSTUDIO_WHISPER_GPU_BATCHED`, `VIUSTUDIO_WHISPER_GPU_BATCH_SIZE` |

Subtitle Source is project-local and intentionally is not an environment variable.
