"""Safe temporary media backend used before the real player is initialized."""

from PySide6.QtMultimedia import QMediaPlayer


class BootstrapMediaBackend:
    """Expose the player contract without creating multimedia resources early."""

    backend_name = "bootstrap"
    _source_path = ""

    def setSource(self, source): self._source_path = ""
    def play(self): return None
    def pause(self): return None
    def stop(self): return None
    def setPosition(self, position): return None
    def position(self): return 0
    def duration(self): return 0
    def playbackState(self): return QMediaPlayer.StoppedState
    def is_playing(self): return False
    def set_subtitle_file(self, subtitle_path, subtitle_style=None): return None
    def clear_subtitle(self): return None
    def set_audio_file(self, audio_path): return None
    def clear_audio(self): return None
    def set_original_audio_file(self, audio_path): return None
    def _clear_original_audio(self): return None
    def set_blur_region(self, blur_region=None): return None
    def set_blur_regions_normalized(self, regions=None): return None
    def set_blur_edit_enabled(self, enabled=True): return None
    def set_blur_active_index(self, index=0): return None
    def clear_blur_region(self): return None
    def set_mask_region(self, mask_region=None): return None
    def set_mask_regions(self, regions=None, active_index=0): return None
    def set_mask_edit_enabled(self, enabled=True): return None
    def clear_mask_region(self): return None
    def set_volume(self, percent): return None
    def volume(self): return 100
    def set_muted(self, muted): return None
    def is_muted(self): return False
    def set_mute_original(self, muted): return None
    def set_mute_dubbed(self, muted): return None
    def is_original_muted(self): return False
    def is_dubbed_muted(self): return False
    def set_original_volume(self, percent): return None
    def set_dubbed_volume(self, percent): return None
    def original_volume(self): return 100
    def dubbed_volume(self): return 100
    def set_playback_rate(self, rate): return None
    def playback_rate(self): return 1.0
