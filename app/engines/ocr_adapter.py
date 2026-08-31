from ocr_processor import (
    _load_ocr_engine,
    transcribe_video_ocr,
    transcribe_video_ocr_ranges,
)
from services.gpu_stage_scheduler import GPUStageScheduler


class OcrAdapter:
    def transcribe(self, video_path: str, model_path: str = "", *, language: str = "auto", task: str = "transcribe", region: str = "bottom", **kwargs):
        with GPUStageScheduler.stage("ocr"):
            return transcribe_video_ocr(video_path, region=region, **kwargs)

    def load_model(self, model_path: str = ""):
        return _load_ocr_engine()

    def transcribe_ranges(
        self, video_path: str, time_ranges: list[tuple[float, float]],
        *, region: str = "bottom", expected_texts: list[str] | None = None,
        scan_modes: list[str] | None = None,
        progress_callback=None,
    ):
        with GPUStageScheduler.stage("ocr"):
            return transcribe_video_ocr_ranges(
                video_path,
                time_ranges,
                region=region,
                expected_texts=expected_texts,
                scan_modes=scan_modes,
                progress_callback=progress_callback,
            )

    def transcribe_with_model(self, model, video_path: str, *, language: str = "auto", task: str = "transcribe", region: str = "bottom"):
        with GPUStageScheduler.stage("ocr"):
            return transcribe_video_ocr(video_path, region=region, ocr_engine=model)
