import os
from runtime_paths import asset_path


class VideoFilterController:
    """Manages video filter presets, color adjustments, LUTs, and UI/inspector synchronization."""

    def __init__(self, gui):
        self.gui = gui

    def video_filter_presets(self):
        return {
            "original": {
                "brightness": 0, "contrast": 0, "saturation": 0,
                "gamma": 0, "hue": 0, "temperature": 0,
                "highlights": 0, "shadows": 0,
            },
            "warm": {
                "brightness": 5, "contrast": 10, "saturation": 15,
                "gamma": -5, "hue": 0, "temperature": 25,
                "highlights": 10, "shadows": -5,
            },
            "cool": {
                "brightness": 0, "contrast": 15, "saturation": -10,
                "gamma": 0, "hue": 0, "temperature": -25,
                "highlights": -10, "shadows": 10,
            },
            "vivid": {
                "brightness": 8, "contrast": 25, "saturation": 35,
                "gamma": -10, "hue": 0, "temperature": 5,
                "highlights": 15, "shadows": -15,
            },
            "vintage": {
                "brightness": -5, "contrast": -10, "saturation": -25,
                "gamma": 10, "hue": 5, "temperature": 15,
                "highlights": -20, "shadows": 20,
            },
            "cinema": {
                "brightness": -3, "contrast": 20, "saturation": 10,
                "gamma": -8, "hue": -3, "temperature": -8,
                "highlights": -5, "shadows": -10,
            },
            "hdr": {
                "brightness": 10, "contrast": 30, "saturation": 20,
                "gamma": -15, "hue": 0, "temperature": 0,
                "highlights": 20, "shadows": 15,
            },
        }

    def video_filter_lut_map(self):
        return {
            "warm": asset_path("luts", "Portrait", "Portrait3.cube"),
            "vivid": asset_path("luts", "Color Boost", "Earth_Tone_Boost.cube"),
            "cool": asset_path("luts", "Cinematic", "Cinematic-2.cube"),
        }

    def video_filter_fields(self):
        return ("brightness", "contrast", "saturation", "gamma", "hue", "temperature", "highlights", "shadows")

    def clamp_video_filter_value(self, value):
        try:
            numeric = int(round(float(value)))
        except Exception:
            numeric = 0
        return max(-100, min(100, numeric))

    def default_video_filter_overrides(self):
        return {field: 0 for field in self.video_filter_fields()}

    def default_video_filter_modified_flags(self):
        return {field: False for field in self.video_filter_fields()}

    def normalize_video_filter_preset_key(self, preset_key):
        key = str(preset_key or "original").strip().lower()
        return key if key in self.video_filter_presets() else "original"

    def get_video_filter_base_values(self, preset_key=None):
        key = self.normalize_video_filter_preset_key(preset_key or getattr(self.gui, "_video_filter_preset_key", "original"))
        return dict(self.video_filter_presets().get(key, self.video_filter_presets()["original"]))

    def get_video_filter_scaled_values(self, preset_key=None, intensity=None):
        base_values = self.get_video_filter_base_values(preset_key)
        current_intensity = intensity if intensity is not None else getattr(self.gui, "_video_filter_intensity", 75)
        scale = max(0.0, min(100.0, float(current_intensity))) / 100.0
        return {
            field: self.clamp_video_filter_value(base_values.get(field, 0) * scale)
            for field in self.video_filter_fields()
        }

    def get_video_filter_effective_values(self, preset_key=None, intensity=None, overrides=None, modified_flags=None):
        scaled_values = self.get_video_filter_scaled_values(preset_key, intensity)
        effective = {}
        active_overrides = overrides if overrides is not None else getattr(self.gui, "_video_filter_adjust_overrides", {})
        active_modified = modified_flags if modified_flags is not None else getattr(self.gui, "_video_filter_user_modified", {})
        for field in self.video_filter_fields():
            if active_modified.get(field, False):
                effective[field] = self.clamp_video_filter_value(active_overrides.get(field, 0))
            else:
                effective[field] = self.clamp_video_filter_value(scaled_values.get(field, 0))
        return effective

    def refresh_video_filter_ui(self):
        if not hasattr(self.gui, "video_filter_intensity_slider"):
            return
        self.gui._video_filter_ui_sync = True
        try:
            for preset_key, button in getattr(self.gui, "video_filter_preset_buttons", {}).items():
                button.setChecked(preset_key == self.normalize_video_filter_preset_key(self.gui._video_filter_preset_key))

            self.gui.video_filter_intensity_slider.setValue(int(self.gui._video_filter_intensity))
            if hasattr(self.gui, "video_filter_intensity_value_label"):
                self.gui.video_filter_intensity_value_label.setText(str(int(self.gui._video_filter_intensity)))

            for field, slider in getattr(self.gui, "video_filter_adjust_sliders", {}).items():
                slider.setValue(int(self.gui._video_filter_adjust_overrides.get(field, 0)))
                self.update_video_filter_slider_visual_state(field, slider)
            for field, label in getattr(self.gui, "video_filter_adjust_value_labels", {}).items():
                label.setText(str(int(self.gui._video_filter_adjust_overrides.get(field, 0))))
                is_modified = bool(self.gui._video_filter_user_modified.get(field, False))
                label.setProperty("filterModified", is_modified)
                label.style().unpolish(label)
                label.style().polish(label)
        finally:
            self.gui._video_filter_ui_sync = False

    def update_video_filter_slider_visual_state(self, field, slider):
        if not slider:
            return
        is_modified = bool(getattr(self.gui, "_video_filter_user_modified", {}).get(field, False))
        if is_modified:
            slider.setStyleSheet(
                "QSlider::groove:horizontal {"
                "background: #223248; height: 6px; border-radius: 3px; }"
                "QSlider::sub-page:horizontal {"
                "background: #4ea6d8; border-radius: 3px; }"
                "QSlider::handle:horizontal {"
                "background: #8ad7ff; width: 14px; margin: -5px 0; border-radius: 7px; }"
            )
        else:
            slider.setStyleSheet("")

    def set_video_filter_state(self, preset_key="original", intensity=75, overrides=None, modified_flags=None):
        self.gui._video_filter_preset_key = self.normalize_video_filter_preset_key(preset_key)
        self.gui._video_filter_intensity = max(0, min(100, int(round(float(intensity)))))
        base_overrides = self.default_video_filter_overrides()
        base_modified_flags = self.default_video_filter_modified_flags()
        for field in self.video_filter_fields():
            if overrides and field in overrides:
                base_overrides[field] = self.clamp_video_filter_value(overrides[field])
            if modified_flags and field in modified_flags:
                base_modified_flags[field] = bool(modified_flags[field])
        self.gui._video_filter_adjust_overrides = base_overrides
        self.gui._video_filter_user_modified = base_modified_flags
        self.refresh_video_filter_ui()
        try:
            self.gui._sync_video_inspector_ui()
        except Exception:
            pass
        if hasattr(self.gui, "media_player") and hasattr(self.gui, "_is_realtime_color_filter_state") and self.gui._is_realtime_color_filter_state():
            self.gui._apply_realtime_color_filter_preview()
        self.gui.refresh_ui_state()

    def on_video_filter_preset_selected(self, preset_key):
        if getattr(self.gui, "_video_filter_ui_sync", False):
            return
        normalized_preset = self.normalize_video_filter_preset_key(preset_key)
        seeded_overrides = self.get_video_filter_scaled_values(normalized_preset, 75)
        self.set_video_filter_state(
            normalized_preset,
            75,
            seeded_overrides,
            self.default_video_filter_modified_flags(),
        )
        self.gui._mark_video_filter_preview_dirty()
        self.gui.schedule_live_video_filter_preview()
        self.persist_video_filter_settings()

    def on_video_filter_intensity_changed(self, value):
        if getattr(self.gui, "_video_filter_ui_sync", False):
            return
        self.gui._video_filter_intensity = max(0, min(100, int(value)))
        self.refresh_video_filter_ui()
        self.gui.refresh_ui_state()
        self.gui._mark_video_filter_preview_dirty()
        if not (hasattr(self.gui, "_is_video_filter_slider_interacting") and self.gui._is_video_filter_slider_interacting()):
            self.gui.schedule_live_video_filter_preview()
        self.persist_video_filter_settings()

    def on_video_filter_adjust_changed(self, field_key, value):
        if getattr(self.gui, "_video_filter_ui_sync", False):
            return
        normalized_field = str(field_key or "").strip().lower()
        if normalized_field not in self.video_filter_fields():
            return
        clamped_value = self.clamp_video_filter_value(value)
        scaled_value = self.get_video_filter_scaled_values().get(normalized_field, 0)
        self.gui._video_filter_adjust_overrides[normalized_field] = clamped_value
        self.gui._video_filter_user_modified[normalized_field] = int(clamped_value) != int(scaled_value)
        self.refresh_video_filter_ui()
        self.gui.refresh_ui_state()
        self.gui._mark_video_filter_preview_dirty()
        if not (hasattr(self.gui, "_is_video_filter_slider_interacting") and self.gui._is_video_filter_slider_interacting()):
            self.gui.schedule_live_video_filter_preview()
        self.persist_video_filter_settings()

    def reset_video_filters(self):
        self.set_video_filter_state(
            "original",
            75,
            self.default_video_filter_overrides(),
            self.default_video_filter_modified_flags(),
        )
        if hasattr(self.gui, "_is_realtime_color_filter_state") and self.gui._is_realtime_color_filter_state():
            self.gui._apply_realtime_color_filter_preview()
        self.gui._video_filter_preview_dirty = False
        self.gui._video_filter_apply_requested = False
        if hasattr(self.gui, "_is_realtime_color_filter_state") and not self.gui._is_realtime_color_filter_state():
            self.gui.schedule_live_video_filter_preview()
        self.persist_video_filter_settings()

    def reset_video_filter_adjustments(self):
        preset_key = getattr(self.gui, "_video_filter_preset_key", "original")
        intensity = getattr(self.gui, "_video_filter_intensity", 75)
        seeded_overrides = self.get_video_filter_scaled_values(preset_key, intensity)
        self.set_video_filter_state(
            preset_key,
            intensity,
            seeded_overrides,
            self.default_video_filter_modified_flags(),
        )
        self.gui._mark_video_filter_preview_dirty()
        self.gui.schedule_live_video_filter_preview()

    def get_video_filter_state(self):
        base_values = self.get_video_filter_base_values()
        scaled_values = self.get_video_filter_scaled_values()
        effective_values = self.get_video_filter_effective_values()
        preset_key = self.normalize_video_filter_preset_key(getattr(self.gui, "_video_filter_preset_key", "original"))
        lut_path = str(self.video_filter_lut_map().get(preset_key, "") or "").strip()
        if lut_path and not os.path.exists(lut_path):
            lut_path = ""
        lut_strength = 0.0
        intensity = getattr(self.gui, "_video_filter_intensity", 75)
        if lut_path:
            lut_strength = max(0.0, min(1.0, float(intensity) / 100.0))
        active = any(abs(int(value)) > 0 for value in effective_values.values()) or bool(
            lut_path and lut_strength > 0.001
        )
        return {
            "preset": preset_key,
            "intensity": int(intensity),
            "base": base_values,
            "scaled": scaled_values,
            "overrides": dict(getattr(self.gui, "_video_filter_adjust_overrides", {})),
            "modified": dict(getattr(self.gui, "_video_filter_user_modified", {})),
            "final": effective_values,
            "lut_path": lut_path,
            "lut_strength": lut_strength,
            "active": active,
        }

    def has_active_video_filters(self):
        state = self.get_video_filter_state()
        return bool(state.get("active"))

    def persist_video_filter_settings(self):
        try:
            if hasattr(self.gui, "persist_current_timeline_project_data"):
                self.gui.persist_current_timeline_project_data()
        except Exception:
            pass
