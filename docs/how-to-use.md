# How to Use VIUStudio

## Basic workflow

1. Open VIUStudio and select CPU or GPU mode in the launcher.
2. Create or open a video project. **Prepare** becomes complete once the video is ready.
3. In **Settings**, choose a Subtitle Source: Audio (SenseVoice or Whisper) or Video (OCR). This choice is saved with the project, not globally.
4. Set source/target language and choose a translation provider.
5. Use **Generate**:
   - **Full Pipeline** runs Transcript → Translate → TTS.
   - **Step-by-Step** runs each stage in order. At TTS, choose **TTS** or **Skip**.
6. Review subtitles, speaker assignments, style, and timed layers in the editor.
7. Use **Fast Preview** to check a five-second rendered sample, then export.

## Transcript editing

- Select a TS1 segment to edit its text, timing, speaker, or voice speed in the Subtitle Inspector.
- Use **+ Layer → Subtitle Segment** to add a missing subtitle at the playhead.
- Use the timeline **Selection Range** and **Alt: OCR/Whisper** to re-transcribe only a problematic section with the opposite recognition engine.
- Alt Transcribe only changes transcription for the selected range; it does not run Translate, TTS, or Export.

## Timeline editing

- Use **Select Range** to create an interval on the ruler. Clear it when finished.
- Select a layer, then use **Split** or **Delete**. A range supplies split boundaries but never changes the selected target layer.
- Use the lock icon in an editable track header to prevent edits without affecting preview or export.
- **Layers** hides/shows whole tracks in the timeline only; it does not affect preview or export.

## Speaker diarization

Enable **Speaker Diarization** in Media before transcription when using Audio source. Detected speakers are colour-coded on TS1. In Voice → Detected Speakers, assign a voice per speaker; in Subtitle Inspector, correct an individual segment's speaker assignment.

## OCR Translator

OCR Translator is independent of subtitle transcription. Open it from the preview toolbar, position its region, capture visible text, then translate or copy the result. It does not modify subtitles, timeline data, or project transcript.

## Layers and export

Blur, Logo, Mask, and Text layers support direct positioning, timing fields, edge resizing, and timeline splitting. Text layers and subtitles are included in Fast Preview and final export.
