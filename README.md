# <img src="assets/viustudio_logo.jpg" style="width: 300px; height: auto;"> 

![VIUStudio Editor Preview](assets/preview.JPG)
### [Demo + Tutorial](https://www.tiktok.com/@nguyenthach617/video/7674305087023369493)

VIUStudio is a Windows desktop video-localization editor for creating Vietnamese or English subtitles, translated video, voice-over, and timed visual layers.

## Upcoming Features

We're continuously improving VIUStudio.

[View the development roadmap](https://github.com/users/notepower2k1/projects/2)

## Highlights

- Guided workflow: **Prepare → Transcript → Translate → TTS → Export**
- Audio transcription with Faster-Whisper or SenseVoice, plus OCR subtitle extraction
- Cloud/API translation providers with Google Translate fallback
- Piper and Edge TTS, optional speaker diarization, and per-speaker voice assignment
- Editor timeline with subtitles, blur, logo, mask, text, selection ranges, locks, and Fast Preview

## Documentation

- [How to Use](docs/how-to-use.md)
- [Requirements and Resources](docs/requirements.md)
- [Technical Stack](docs/technical-stack.md)
- [Project Structure](docs/project-structure.md)

## Run from Source

```bash
git clone https://github.com/notepower2k1/VIUStudio.git
cd VIUStudio
python -m venv venv
venv\Scripts\activate
pip install -r requirements-local.txt
python ui/gui.py
```

Copy `.env_example` to `.env` only if you need manual provider or remote-server configuration. Most settings are available in the app.

## Support VIUStudio

If VIUStudio is useful to you, you can support development:

### Donate in Vietnam

Scan the QR code:

<img src="assets/qr.png"  style="width: 25%; height: auto;">

<!-- ### International Donation

[![Buy Me a Coffee](assets/buymeacoffee.png)](https://buymeacoffee.com/hcaht)

Click the image or visit [Buy Me a Coffee](https://buymeacoffee.com/hcaht). -->

## License

Apache License 2.0. See [LICENSE](LICENSE).
