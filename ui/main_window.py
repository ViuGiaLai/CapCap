import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow)
from PySide6.QtCore import Qt, QTimer, QSettings, Signal
from PySide6.QtGui import QIcon

APP_PATH = os.path.join(os.path.dirname(__file__), '..', 'app')
if APP_PATH not in sys.path:
    sys.path.append(APP_PATH)

from services import GUIProjectBridge, ProjectService, VoiceCatalogService
from controllers import OcrController, PipelineController, PreviewController, ProjectController, SubtitleController, VideoFilterController
from features.timeline_selection import TimelineSelectionMixin
from features.visual_layer_editor import VisualLayerEditorMixin
from features.voice_catalog import VoiceCatalogMixin
from features.runtime_media import RuntimeMediaMixin
from features.window_ui import WindowUiMixin
from features.speaker_voice import SpeakerVoiceMixin
from features.filter_subtitle_style import FilterSubtitleStyleMixin
from features.project_state import ProjectStateMixin
from features.preview_configuration import PreviewConfigurationMixin
from features.segment_editor import SegmentEditorMixin
from features.timeline_editing import TimelineEditingMixin
from features.voice_subtitle_preview import VoiceSubtitlePreviewMixin
from features.workflow_actions import WorkflowActionsMixin
from features.model_settings import ModelSettingsMixin
from features.pipeline_lifecycle import PipelineLifecycleMixin
from utils.bootstrap_media_backend import BootstrapMediaBackend
from runtime_paths import asset_path, workspace_root
from runtime_profile import is_remote_profile

def _default_asr_engine() -> str:
    return "sensevoice"


class VideoTranslatorGUI(PipelineLifecycleMixin, ModelSettingsMixin, WorkflowActionsMixin, VoiceSubtitlePreviewMixin, TimelineEditingMixin, SegmentEditorMixin, PreviewConfigurationMixin, ProjectStateMixin, FilterSubtitleStyleMixin, SpeakerVoiceMixin, WindowUiMixin, RuntimeMediaMixin, VoiceCatalogMixin, VisualLayerEditorMixin, TimelineSelectionMixin, QMainWindow):
    VOICE_ENTRY_ID_ROLE = Qt.UserRole + 1
    runtime_log_received = Signal(str)
    subtitle_ass_ready = Signal(int, str, str, object)

    def __init__(self):
        super().__init__()
        self._current_video_path = ""
        title = "CapCap Video Translator"
        if is_remote_profile():
            title += " (Remote)"
        self.setWindowTitle(title)
        self.settings = QSettings("CapCap", "VideoTranslatorGUI")
        self.setAcceptDrops(True)
        self.logo_path = asset_path("capcap.png")
        if os.path.exists(self.logo_path):
            self.setWindowIcon(QIcon(self.logo_path))
        self.setWindowFlag(Qt.FramelessWindowHint)

        # Start maximized, but keep the window genuinely resizable.  Locking
        # it to the first monitor's pixel size prevented Qt from adapting the
        # layout when users moved between laptop/desktop displays or changed
        # DPI scaling.
        self.setWindowState(Qt.WindowMaximized)
        self.setMinimumSize(1024, 640)
        self._responsive_layout_pending = False
        self._responsive_layout_mode = "desktop"
        self._initial_layout_finalized = False

        # Stylesheet for Premium Dark Mode
        self.setStyleSheet("""
            /* ── Base ─────────────────────────────────────────────── */
            QMainWindow {
                background-color: #0b1118;
            }
            QWidget {
                color: #cdd9e5;
                font-family: 'Segoe UI', 'Inter', Arial, sans-serif;
            }
            #centralWidget {
                background-color: #0b1118;
            }

            /* ── Panels ───────────────────────────────────────────── */
            #leftPanelArea {
                background-color: #0e1520;
                border-right: 1px solid #1a2536;
            }
            #leftPanelContainer {
                background-color: #0e1520;
            }
            #rightPanel {
                background-color: #0b1118;
            }

            /* ── Cards ─────────────────────────────────────────────── */
            QFrame#heroCard, QFrame#statusCard, QFrame#sideInfoCard {
                background-color: #0f1c2b;
                border: 1px solid #1e3047;
                border-radius: 12px;
            }
            QFrame#audioSourcePanel {
                background-color: #0f1c2b;
                border: 1px solid #1e3047;
                border-radius: 10px;
            }
            QFrame#subtitleInspectorHandle {
                background-color: #0f1c2b;
                border: 1px solid #1e3047;
                border-left: none;
                border-top-right-radius: 12px;
                border-bottom-right-radius: 12px;
            }

            /* ── Group boxes ─────────────────────────────────────── */
            QGroupBox {
                border: none;
                border-radius: 0px;
                margin-top: 0px;
                font-weight: 700;
                color: #e0eaf4;
                background-color: transparent;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #4da6e8;
            }

            /* ── Typography ──────────────────────────────────────── */
            QLabel#heroTitle {
                font-size: 19px;
                font-weight: 700;
                color: #eaf4ff;
                letter-spacing: 0.2px;
            }
            QLabel#statusHeadline {
                font-size: 14px;
                font-weight: 700;
                color: #eaf4ff;
            }
            QLabel#sectionTitle {
                font-size: 11px;
                font-weight: 700;
                color: #4da6e8;
                letter-spacing: 0.8px;
                text-transform: uppercase;
            }
            QLabel#heroBody, QLabel#statusBody, QLabel#helperLabel, QLabel#previewContextLabel {
                color: #7a8fa8;
                line-height: 1.45em;
            }
            QLabel#helperLabel[filterModified="true"] {
                color: #4da6e8;
                font-weight: 700;
            }
            QLabel#audioSourceTitle {
                color: #eaf4ff;
                font-weight: 700;
            }
            QLabel {
                background: transparent;
                color: #c2cfe0;
                font-size: 12px;
            }

            /* ── Chips / Pills ───────────────────────────────────── */
            QLabel#timingChip {
                background-color: #0e2235;
                color: #6ec6f5;
                border: 1px solid #1e4a6a;
                border-radius: 999px;
                padding: 3px 10px;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 0.3px;
            }
            QLabel#statusPill {
                background-color: #0e2235;
                color: #6ec6f5;
                border: 1px solid #1e4a6a;
                border-radius: 999px;
                padding: 3px 10px;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel#statusChip {
                background-color: #131e2e;
                color: #c8d6e6;
                border: 1px solid #253a54;
                border-radius: 999px;
                padding: 3px 10px;
                font-size: 10px;
                font-weight: 600;
            }
            QLabel#statusChip[state="ok"] {
                background-color: #0e2a1e;
                color: #7de8b0;
                border: 1px solid #1e6445;
            }
            QLabel#statusChip[state="running"] {
                background-color: #2a1f08;
                color: #ffd97a;
                border: 1px solid #7a5518;
            }
            QLabel#statusChip[state="na"] {
                background-color: #131e2e;
                color: #7a8fa8;
                border: 1px solid #1e3047;
            }
            QLabel#statusChip[state="pending"] {
                background-color: #131e2e;
                color: #c8d6e6;
                border: 1px solid #253a54;
            }

            /* ── Buttons ─────────────────────────────────────────── */
            QPushButton {
                background-color: #162130;
                color: #c2cfe0;
                border: 1px solid #243a55;
                border-radius: 8px;
                padding: 7px 14px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #1c2d42;
                border-color: #3a6090;
                color: #e0eaf4;
            }
            QPushButton:pressed {
                background-color: #122030;
                border-color: #2f5078;
            }
            QPushButton:disabled {
                background-color: #0e1824;
                color: #3d5068;
                border-color: #1a2a3a;
            }

            /* Generate — primary CTA */
            QPushButton#mainActionBtn, QToolButton#mainActionBtn {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2dbd9a, stop:1 #1e9078);
                color: #071210;
                border: none;
                border-bottom: 2px solid #136754;
                border-radius: 9px;
                font-size: 13px;
                font-weight: 700;
                padding: 8px 18px;
                letter-spacing: 0.2px;
            }
            QPushButton#mainActionBtn:hover, QToolButton#mainActionBtn:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #40d4ae, stop:1 #25a98d);
            }
            QPushButton#mainActionBtn:pressed, QToolButton#mainActionBtn:pressed {
                border-bottom: 1px solid #0e4d3c;
                padding-top: 9px;
            }
            QToolButton#mainActionBtn::menu-indicator { image: none; width: 0px; }

            /* Secondary header buttons */
            QPushButton#secondaryActionBtn {
                background-color: #142032;
                color: #c8dcf0;
                border: 1px solid #2e5070;
                border-bottom: 2px solid #1e3d58;
                border-radius: 9px;
                font-size: 12px;
                font-weight: 700;
                padding: 7px 16px;
            }
            QPushButton#secondaryActionBtn:hover {
                background-color: #1a2d44;
                border-color: #4480b0;
                color: #e8f4ff;
            }
            QPushButton#secondaryActionBtn:pressed {
                border-bottom: 1px solid #1a3248;
                padding-top: 8px;
            }
            QPushButton#secondaryActionBtn::menu-indicator { width: 0px; image: none; }

            /* Workflow tab buttons */
            QPushButton#workflowTabBtn {
                background-color: #121f30;
                color: #7a8fa8;
                border: 1px solid #1e3047;
                border-radius: 8px;
                padding: 5px 10px;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 0.3px;
            }
            QPushButton#workflowTabBtn:hover {
                background-color: #182840;
                border-color: #3570a0;
                color: #a8c8e0;
            }
            QPushButton#workflowTabBtn:checked {
                background-color: #1a3550;
                color: #eaf4ff;
                border-color: #3a90d0;
            }

            /* Inspector handle button */
            QPushButton#subtitleInspectorHandleBtn {
                background-color: #132031;
                color: #4da6e8;
                border: 1px solid #1e3d58;
                border-right: none;
                border-top-left-radius: 999px;
                border-bottom-left-radius: 999px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                font-size: 18px;
                font-weight: 900;
                padding: 0px;
            }
            QPushButton#subtitleInspectorHandleBtn:hover {
                background-color: #1a2d44;
                border-color: #3a80c0;
            }

            /* ── Menus ───────────────────────────────────────────── */
            QMenu#headerMoreMenu, QMenu#generateMenu, QMenu#generateStepMenu {
                background-color: #0d1828;
                color: #c8d6e6;
                border: 1px solid #1e3047;
                border-radius: 10px;
                padding: 6px;
            }
            QMenu#headerMoreMenu::item, QMenu#generateMenu::item, QMenu#generateStepMenu::item {
                background-color: transparent;
                color: #c8d6e6;
                padding: 7px 14px;
                border-radius: 6px;
            }
            QMenu#generateStepMenu::item:enabled {
                background-color: #112134;
                color: #d8eeff;
                border: 1px solid #254a6a;
                font-weight: 700;
            }
            QMenu#generateStepMenu::item:disabled {
                background-color: #0d1828;
                color: rgba(120, 140, 165, 100);
                border: 1px solid #162030;
                font-weight: 400;
            }
            QMenu#headerMoreMenu::item:selected, QMenu#generateMenu::item:selected,
            QMenu#generateStepMenu::item:selected {
                background-color: #1a3048;
                color: #eaf4ff;
            }
            QMenu#generateStepMenu::item:disabled:selected {
                background-color: #0d1828;
                color: rgba(120, 140, 165, 100);
            }
            QMenu#headerMoreMenu::separator, QMenu#generateMenu::separator,
            QMenu#generateStepMenu::separator {
                height: 1px;
                background: #1e3047;
                margin: 5px 8px;
            }

            /* ── Inputs ──────────────────────────────────────────── */
            QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #0d1825;
                border: 1px solid #243a55;
                border-radius: 8px;
                color: #dce8f4;
                padding: 7px 10px;
                selection-background-color: #1e4a7a;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus,
            QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #3a90d0;
                background-color: #0e2035;
            }
            QLineEdit:disabled, QTextEdit:disabled, QComboBox:disabled,
            QSpinBox:disabled, QDoubleSpinBox:disabled {
                background-color: #0b1420;
                color: #3d5068;
                border: 1px solid #162030;
            }

            /* Segment inspector text area */
            QScrollArea#segmentEditorScroll { background-color: transparent; border: none; }
            QWidget#segmentEditorContainer { background-color: transparent; }
            QFrame#segmentInspectorCard {
                background-color: #0f1c2b;
                border: 1px solid #1e3047;
                border-radius: 0px;
            }
            QTextEdit#segmentInspectorEditor {
                background-color: #0d1825;
                border: 1px solid #1e3a58;
                border-radius: 8px;
                padding: 10px 12px;
            }
            QTextEdit#segmentInspectorEditor:focus {
                border: 1px solid #3a90d0;
                background-color: #0e2035;
            }

            /* ── Progress bar ────────────────────────────────────── */
            QProgressBar {
                border: 1px solid #1a2f45;
                border-radius: 8px;
                text-align: center;
                background-color: #0d1825;
                color: #7a9ab8;
                font-size: 10px;
                font-weight: 600;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #29b89f, stop:1 #1980c0);
                border-radius: 8px;
            }

            /* ── Checkboxes / Radios ─────────────────────────────── */
            QCheckBox { background: transparent; color: #b8cce0; spacing: 6px; }
            QCheckBox::indicator {
                width: 15px; height: 15px;
                border: 1px solid #2a4560;
                border-radius: 4px;
                background-color: #0e1e30;
            }
            QCheckBox::indicator:checked {
                background-color: #1e80c0;
                border-color: #3aaced;
                image: none;
            }
            QCheckBox::indicator:hover { border-color: #3a6090; }
            QRadioButton { background: transparent; color: #b8cce0; spacing: 6px; }
            QRadioButton::indicator {
                width: 14px; height: 14px;
                border: 1px solid #2a4560;
                border-radius: 7px;
                background-color: #0e1e30;
            }
            QRadioButton::indicator:checked {
                background-color: #1e80c0;
                border-color: #3aaced;
            }

            /* ── Scroll bars ─────────────────────────────────────── */
            QScrollArea { border: none; background-color: #0e1520; }
            QScrollBar:vertical {
                border: none;
                background: #0b1118;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #1e3555;
                min-height: 28px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover { background: #2a4e7a; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar:horizontal {
                border: none;
                background: #0b1118;
                height: 8px;
            }
            QScrollBar::handle:horizontal {
                background: #1e3555;
                min-width: 28px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal:hover { background: #2a4e7a; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
            QStackedWidget#leftPanelStack { background: transparent; }

            /* ── ComboBox dropdown ───────────────────────────────── */
            QComboBox QAbstractItemView {
                background-color: #0d1825;
                color: #dce8f4;
                selection-background-color: #1e4a7a;
                border: 1px solid #243a55;
                border-radius: 6px;
                outline: none;
                padding: 4px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                width: 10px;
                height: 10px;
            }

            /* ── Message boxes ───────────────────────────────────── */
            QMessageBox { background-color: #0d1825; }
            QMessageBox QLabel { color: #c8d6e6; background: transparent; }
            QMessageBox QPushButton { min-width: 90px; }

            /* ── Tabs ────────────────────────────────────────────── */
            QTabWidget::pane {
                border: 1px solid #1e3047;
                border-radius: 10px;
                background: #0d1825;
                top: -1px;
            }
            QTabBar::tab {
                background: #111e30;
                color: #7a8fa8;
                padding: 8px 14px;
                border: 1px solid #1e3047;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                min-width: 100px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: #0d1825;
                color: #4da6e8;
                border-bottom: none;
            }
            QTabBar::tab:hover:!selected {
                background: #162030;
                color: #a8c0d8;
            }

            /* ── Sliders ─────────────────────────────────────────── */
            QSlider::groove:horizontal {
                height: 4px;
                background: #1a2f45;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #3a90d0;
                border: 1px solid #2070b0;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #5ab0f0;
                border-color: #3a90d0;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1e5a9a, stop:1 #3a90d0);
                border-radius: 2px;
            }

            /* ── Tooltip ─────────────────────────────────────────── */
            QToolTip {
                background-color: #0d1825;
                color: #c8d6e6;
                border: 1px solid #1e3047;
                border-radius: 6px;
                padding: 5px 9px;
                font-size: 11px;
            }
        """)

        # -----------------------------
        # State (must exist before setup_ui)
        # -----------------------------
        # Track generated/selected artifacts for quick inspection.
        # Keys are stable IDs, values are absolute file paths.
        self.processed_artifacts = {}
        self._runtime_logs = []
        self._pending_runtime_log_entries = []
        self._runtime_log_view_entry_count = 0
        self._runtime_log_flush_timer = QTimer(self)
        self._runtime_log_flush_timer.setSingleShot(True)
        self._runtime_log_flush_timer.setInterval(100)
        self._runtime_log_flush_timer.timeout.connect(self._flush_runtime_log_entries)
        self._editor_highlight_chunks = {}
        self._editor_highlight_state = {}
        self.runtime_log_received.connect(self._append_runtime_log_entry)
        self.workspace_root = workspace_root()
        self._cleanup_temp_root()
        self.project_service = ProjectService(self.workspace_root)
        self.project_bridge = GUIProjectBridge(self.project_service)
        self.voice_catalog_service = VoiceCatalogService(self.workspace_root)
        self.subtitle_controller = SubtitleController(self)
        self.pipeline_controller = PipelineController(self)
        self.preview_controller = PreviewController(self)
        self.project_controller = ProjectController(self)
        self.video_filter_controller = VideoFilterController(self)
        self.ocr_controller = OcrController(self)
        self.current_project_state = None
        # Do not inherit a legacy global Subtitle Source from .env.  Opening
        # a project below will replace this with that project's own setting.
        os.environ["TRANSCRIPTION_ENGINE"] = _default_asr_engine()
        self.current_segment_models = []
        self.current_translated_segment_models = []
        self.selected_whisper_model_name = "auto"
        self._last_audio_preview_path = ""
        self._segment_preview_threads = {}
        self._voice_sample_preview_thread = None
        self._voiceover_force_refresh = False
        self.voice_catalog_entries_all = []
        self.voice_catalog_entries = []

        self.voice_catalog_map = {}
        self._voice_signals_bound = False
        self._media_backend_ready = False
        self._blur_region_signal_bound = False
        self._blur_edit_finished_signal_bound = False
        self._preview_audio_signals_bound = False
        self.media_player = BootstrapMediaBackend()
        self.voice_preview_dialog = None
        self._voice_preview_row_buttons = {}
        self._tracked_progress_dialogs = []
        self._timeline_timing_undo_stack = []
        self._timeline_timing_redo_stack = []
        self._suspend_timeline_undo = False
        self._timeline_waveform_cache_key = None
        self._timeline_waveform_samples = []
        self._timeline_waveform_duration_s = 0.0
        self._timeline_waveform_worker = None
        self._desired_timeline_waveform_request = None
        self._timeline_video_thumb_cache_key = None
        self._timeline_video_thumbnails = []
        self._timeline_thumbnail_worker = None
        self._desired_timeline_thumbnail_request = None
        self._pending_timeline_waveform_refresh = False
        self._pending_timeline_thumbnail_refresh = False
        self._allow_post_pipeline_preview_assets = False
        self._subtitle_custom_style_state = None
        self._subtitle_preset_apply_in_progress = False
        # Exact full-block subtitle backgrounds are measured by libass.  Keep
        # that expensive work out of the GUI thread; the active ASS track is
        # intentionally retained until the newest debounced result is ready.
        self._subtitle_ass_request_token = 0
        self._subtitle_ass_worker_running = False
        self._subtitle_ass_worker_threads = []
        self._subtitle_ass_pending_snapshot = None
        self.subtitle_ass_ready.connect(self._on_async_subtitle_ass_ready)
        self._video_filter_ui_sync = False
        self._video_filter_preset_key = "original"
        self._video_filter_intensity = 75
        self._video_filter_adjust_overrides = {
            "brightness": 0,
            "contrast": 0,
            "saturation": 0,
            "temperature": 0,
            "highlights": 0,
            "shadows": 0,
        }
        self._video_filter_user_modified = {
            "brightness": False,
            "contrast": False,
            "saturation": False,
            "temperature": False,
            "highlights": False,
            "shadows": False,
        }
        self._pending_video_filter_preview = False
        self._filter_thumbnail_visible = False
        self._filter_preview_blur_was_checked = False
        self._filter_preview_ocr_was_editable = False
        self._suspend_ocr_overlay = False
        self._ocr_overlay_visible = True
        self._ocr_translator_active = False
        self._ocr_translator_rect = (0.2, 0.2, 0.6, 0.25)
        self._ocr_translator_capture_worker = None
        self._ocr_translator_translation_worker = None
        self._play_video_filter_preview_when_ready = False
        self._filter_thumbnail_target_height = 320
        self._video_filter_preview_dirty = False
        self._video_filter_apply_requested = False
        self._blur_edit_finish_syncing = False
        self._blur_region_preview_dirty = False
        # Blur/Mask are MPV filter effects. During a paused geometry edit we
        # suppress only the active layer from the filter graph so an old,
        # stale effect is never left behind the lightweight edit overlay.
        self._deferred_effect_edit_type = ""
        self._deferred_effect_edit_layer_id = ""
        # A selected layer becomes editable only after an explicit paused
        # selection.  Playback and its pause transition never implicitly
        # restore edit chrome for the previously selected layer.
        self._preview_edit_layer_id = ""
        self._review_mode_active = False
        # Overlay drags can emit dozens of events per second.  Persisting the
        # full project/timeline for each one causes synchronous JSON and
        # project-file writes on the UI thread, so collect rapid edits and
        # save their final state shortly after interaction settles.
        self._pending_timeline_persist = False
        self._pending_mask_state_persist = False
        self._pending_blur_state_persist = False
        self._timeline_persist_timer = QTimer(self)
        self._timeline_persist_timer.setSingleShot(True)
        self._timeline_persist_timer.setInterval(180)
        self._timeline_persist_timer.timeout.connect(self._flush_pending_timeline_persist)
        # Simple pipeline runner (Run All)
        self._pipeline_active = False
        self._pipeline_step = ""

        # Pre-rendered video state
        self.last_preview_video_path = ""
        self.last_styled_preview_path = ""
        self.last_styled_preview_signature = ""
        self.last_exact_preview_5s_path = ""

        self._deferred_startup_stage1_done = False
        self._deferred_startup_stage2_done = False

        self.setup_ui()
        self._configure_local_voice_mode_ui()
        self._timeline_visual_refresh_timer = QTimer(self)
        self._timeline_visual_refresh_timer.setSingleShot(True)
        self._timeline_visual_refresh_timer.timeout.connect(self._run_pending_timeline_visual_refresh)
        QTimer.singleShot(0, self._run_deferred_startup_stage1)
        QTimer.singleShot(600, self._run_deferred_startup_stage2)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VideoTranslatorGUI()
    window.show()
    sys.exit(app.exec())


