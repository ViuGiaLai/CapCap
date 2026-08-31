from sensevoice_processor import (
    load_model,
    transcribe_audio,
    transcribe_presegmented_audio_batch,
)


class SenseVoiceAdapter:
    def transcribe(self, audio_path: str, model_path: str, *, language: str = "auto"):
        return transcribe_audio(audio_path, model_path, language=language)

    def load_model(self, model_dir: str):
        return load_model(model_dir)

    def transcribe_presegmented_batch(
        self, audio_paths: list[str], model_path: str, *, language: str = "auto",
        progress_callback=None,
    ):
        return transcribe_presegmented_audio_batch(
            audio_paths, model_path, language=language,
            progress_callback=progress_callback,
        )
