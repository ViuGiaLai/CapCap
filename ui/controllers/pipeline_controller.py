import json
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.request
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QMessageBox
from worker_adapters import PrepareWorkflowWorker
from runtime_paths import subprocess_hidden_kwargs

# Robust import for the progress widget
try:
    from widgets.progress_dialog import BackgroundableProgressDialog, PipelineProgressDialog
except ImportError:
    # Fallback for different execution contexts
    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    from widgets.progress_dialog import BackgroundableProgressDialog, PipelineProgressDialog

class PipelineController:
    """
    Orchestrates the multi-stage video translation pipeline.
    Connects background workers to the UI and progress tracking widgets.
    """
    def __init__(self, gui):
        self.gui = gui
        self.progress_dialog = None
        self.whisper_download_dialog = None
        self.local_worker_process = None
        self.local_worker_api_url = ""
        self.local_worker_api_token = ""
        self.prepare_run_id = 0
        self.prepare_status_timer = None
        self.prepare_status_phase = ""
        self.active_processing_device = "cpu"

    def _app_root(self):
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    def _find_free_local_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    def _wait_for_local_worker_server(self, api_url, timeout_s=60.0):
        deadline = time.monotonic() + timeout_s
        health_url = f"{api_url.rstrip('/')}/health"
        while time.monotonic() < deadline:
            process = self.local_worker_process
            if process is not None and process.poll() is not None:
                raise RuntimeError(f"Local worker process exited early with code {process.returncode}.")
            try:
                with urllib.request.urlopen(health_url, timeout=1.0) as response:
                    if response.status == 200:
                        return
            except Exception:
                time.sleep(0.2)
        raise RuntimeError("Local worker process did not become ready.")

    def _kill_process_tree(self, process):
        if process is None:
            return
        if process.poll() is not None:
            return
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    **subprocess_hidden_kwargs(),
                )
            else:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    def _stop_local_worker_server(self):
        process = self.local_worker_process
        self.local_worker_process = None
        self.local_worker_api_url = ""
        self.local_worker_api_token = ""
        self._kill_process_tree(process)

    def _start_prepare_status_polling(self):
        self._stop_prepare_status_polling()
        self.prepare_status_phase = ""
        timer = QTimer(self.gui)
        timer.setInterval(10000)
        timer.timeout.connect(self._poll_prepare_status)
        self.prepare_status_timer = timer
        timer.start()

    def _stop_prepare_status_polling(self):
        timer = self.prepare_status_timer
        self.prepare_status_timer = None
        if timer is not None:
            try:
                timer.stop()
                timer.deleteLater()
            except Exception:
                pass

    def _poll_prepare_status(self):
        api_url = self.local_worker_api_url
        token = self.local_worker_api_token
        if not api_url:
            return
        try:
            request = urllib.request.Request(f"{api_url.rstrip('/')}/v1/status")
            if token:
                request.add_header("X-CapCap-Token", token)
            with urllib.request.urlopen(request, timeout=0.35) as response:
                data = json.loads(response.read().decode("utf-8", errors="replace"))
            phase = str(data.get("phase", "") or "").strip()
            message = str(data.get("message", "") or "").strip()
            if phase and phase != self.prepare_status_phase:
                self.prepare_status_phase = phase
                self._on_prepare_step_started(phase, message)
        except Exception:
            pass

    def _start_local_worker_server(self, processing_device: str = ""):
        self._stop_local_worker_server()
        app_root = self._app_root()
        server_script = os.path.join(app_root, "app", "remote_api_server.py")
        port = self._find_free_local_port()
        token = secrets.token_urlsafe(24)
        env = os.environ.copy()
        env["CAPCAP_RUNTIME_PROFILE"] = "local"
        env["CAPCAP_REMOTE_API_HOST"] = "127.0.0.1"
        env["CAPCAP_REMOTE_API_PORT"] = str(port)
        env["CAPCAP_REMOTE_API_TOKEN"] = token
        env["CAPCAP_REMOTE_PRELOAD_MODELS"] = "0"
        env["CAPCAP_RUN_REMOTE_API_SERVER"] = "1" if getattr(sys, "frozen", False) else "0"
        # The worker is a separate frozen Python process.  Force UTF-8 before
        # it starts so any third-party code that still relies on Python's
        # default text encoding cannot inherit a locale-specific ANSI codec.
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["CAPCAP_DEVICE"] = (
            "cuda" if str(processing_device or os.getenv("CAPCAP_DEVICE", "cpu")).strip().lower() == "cuda"
            else "cpu"
        )

        process_kwargs = subprocess_hidden_kwargs()
        if os.name == "nt":
            process_kwargs["creationflags"] = int(process_kwargs.get("creationflags", 0)) | getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP", 0
            )

        # A frozen GUI executable must be launched in an explicit worker mode.
        # Starting it with no arguments would open a second launcher window;
        # the worker entrypoint then runs the HTTP server without importing the
        # GUI or creating a QApplication.
        worker_command = ([sys.executable, "--worker-server"]
                          if getattr(sys, "frozen", False)
                          else [sys.executable, server_script])
        self.local_worker_process = subprocess.Popen(
            worker_command,
            cwd=app_root,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=None,
            stderr=None,
            close_fds=False,
            **process_kwargs,
        )
        self.local_worker_api_url = f"http://127.0.0.1:{port}"
        self.local_worker_api_token = token
        try:
            self._wait_for_local_worker_server(self.local_worker_api_url)
        except Exception:
            self._stop_local_worker_server()
            raise

    def _mark_running_project_steps_stopped(self):
        state = getattr(self.gui, "current_project_state", None)
        steps = getattr(state, "steps", {}) or {}
        for step_name, status in list(steps.items()):
            if status != "running":
                continue
            try:
                self.gui.update_project_step(step_name, "failed")
            except Exception:
                try:
                    steps[step_name] = "failed"
                except Exception:
                    pass

    def _on_pipeline_stop(self):
        if self.progress_dialog:
            reply = QMessageBox.question(
                self.progress_dialog,
                "Stop Pipeline?",
                "Stop the current pipeline run? The worker process for this run will be killed.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply != QMessageBox.Yes:
                self.progress_dialog.cancel_stop_request()
                return

        self.gui._pipeline_active = False
        self.gui._pipeline_step = ""
        self.prepare_run_id += 1
        self._stop_prepare_status_polling()
        self._mark_running_project_steps_stopped()
        self._stop_local_worker_server()
        if self.progress_dialog:
            self.progress_dialog.fail_step("ai_process")
            self.progress_dialog.footer.setText("Pipeline stopped.")
            self.progress_dialog.footer.setStyleSheet("color: #FFB86B; font-weight: bold; font-size: 14px; margin-top: 15px;")
            self.progress_dialog.stop_btn.setEnabled(False)
            self.progress_dialog.stop_btn.setText("Stopped")
        if hasattr(self.gui, "run_all_btn"):
            self.gui.run_all_btn.setEnabled(True)
            self.gui.run_all_btn.setText("Generate")
        if hasattr(self.gui, "progress_bar") and self.gui.progress_bar is not None:
            self.gui.progress_bar.setRange(0, 100)
            self.gui.progress_bar.setValue(0)
        self.gui.refresh_ui_state()
        self.gui.log("[Pipeline] Stop requested. Local worker process killed.")

    
    def _whisper_model_cached(self, model_name: str) -> bool:
        try:
            name = str(model_name or "").strip().lower()
            if not name:
                return True
            cache_root = os.path.join(self.gui.workspace_root, "models", "faster_whisper")
            if not os.path.isdir(cache_root):
                return False
            for entry in os.listdir(cache_root):
                low = entry.lower()
                if low.startswith("models--") and name in low:
                    return True
            return False
        except Exception:
            return True

    def _hide_whisper_download_dialog(self):
        try:
            if self.whisper_download_dialog is not None:
                self.whisper_download_dialog.hide()
                self.whisper_download_dialog.deleteLater()
                self.whisper_download_dialog = None
        except Exception:
            self.whisper_download_dialog = None

    def _show_whisper_download_dialog(self):
        try:
            if self.whisper_download_dialog is not None:
                return
            model_name = getattr(self.gui, "get_whisper_model_name", lambda: "medium")()
            dlg = BackgroundableProgressDialog(f"Downloading Whisper model: {model_name} ...", "Hide", 0, 0, self.gui)
            dlg.setWindowTitle("Downloading models")
            dlg.setWindowModality(Qt.NonModal)
            dlg.setMinimumDuration(0)
            dlg.setAutoReset(False)
            dlg.setAutoClose(False)
            try:
                dlg.canceled.connect(dlg.hide)
            except Exception:
                pass
            self.whisper_download_dialog = dlg
            if hasattr(self.gui, "_register_progress_dialog"):
                self.gui._register_progress_dialog(dlg)
            dlg.show()
        except Exception:
            self.whisper_download_dialog = None
    def _setup_progress_dialog(self, includes_separation=True):
        """Creates and initializes the progress tracking dialog."""
        if self.progress_dialog:
            try:
                self.progress_dialog.stop_requested.disconnect(self._on_pipeline_stop)
            except (RuntimeError, TypeError):
                pass
            self.progress_dialog.hide()
            self.progress_dialog.deleteLater()
            self.progress_dialog = None
        self.progress_dialog = PipelineProgressDialog(self.gui)
        self.progress_dialog.stop_requested.connect(self._on_pipeline_stop)
        if hasattr(self.gui, "_register_progress_dialog"):
            self.gui._register_progress_dialog(self.progress_dialog)
        if hasattr(self.gui, "is_auto_recap_enabled") and self.gui.is_auto_recap_enabled():
            if hasattr(self.progress_dialog, "title_label"):
                self.progress_dialog.title_label.setText("✨ Auto Edit Recap")
            self.progress_dialog.add_step("analyzing", "Analyzing Video (Effect Shot Boundaries)")
            self.progress_dialog.add_step("building", "Building Effect Plan (No Content Removal)")
            self.progress_dialog.add_step("smart_edits", "Applying Smart Edits (Zoom, Pan, Crop & Speed)")
            self.progress_dialog.add_step("audio", "Processing Audio (Voiceover & Ducking)")
            self.progress_dialog.add_step("rendering", "Rendering Recap (FFmpeg 1-Pass)")
        else:
            if hasattr(self.progress_dialog, "title_label"):
                self.progress_dialog.title_label.setText("AI Production Pipeline")
            self.progress_dialog.add_step("ai_process", "Subtitle Processing (AI)")
            self.progress_dialog.add_step("voiceover", "Synthesizing AI Voiceover")
            self.progress_dialog.add_step("preview", "Preparing Video Preview")
        self.progress_dialog.show()

    def run_all_pipeline(self, video_path=None, requires_separation=None, target_stage="full"):
        """Entry point for the full generation process."""
        if video_path is None:
            # Fallback to the UI field if not provided
            video_path = getattr(self.gui, "video_path_edit", None)
            if video_path:
                video_path = video_path.text().strip()
            else:
                video_path = getattr(self.gui, "last_video_path", "")

        if not video_path or not os.path.exists(video_path):
            QMessageBox.warning(self.gui, "Error", "Please select a video file first.")
            return

        # Determine if we need vocal separation based on UI settings
        if requires_separation is None:
            requires_separation = (self.gui.get_audio_handling_mode() == "clean")

        # Initialize state
        self.prepare_run_id += 1
        prepare_run_id = self.prepare_run_id
        self.gui._pipeline_active = True
        self.gui._pipeline_step = "prepare"
        self.target_stage = str(target_stage or "full").strip().lower()
        self._generate_export_started = False
        
        # UI Feedback
        if hasattr(self.gui, "run_all_btn"):
            self.gui.run_all_btn.setEnabled(False)
            self.gui.run_all_btn.setText("Processing...")
            
        self._setup_progress_dialog(includes_separation=requires_separation)
        if self.progress_dialog:
            if hasattr(self.gui, "is_auto_recap_enabled") and self.gui.is_auto_recap_enabled():
                self.progress_dialog.start_step("analyzing")
            else:
                self.progress_dialog.start_step("ai_process")

        # Start the background worker
        self.gui.log(f"[Pipeline] Starting prepare workflow for: {video_path}")
        try:
            self.active_processing_device = (
                "cuda" if os.getenv("CAPCAP_DEVICE", "cpu").strip().lower() == "cuda" else "cpu"
            )
            self._start_local_worker_server(self.active_processing_device)
            self.gui.log(
                f"[Pipeline] Local worker process started at {self.local_worker_api_url} "
                f"(device={self.active_processing_device})"
            )
        except Exception as exc:
            self.pipeline_fail(f"Could not start local worker process: {exc}")
            return
        self._start_prepare_status_polling()
        transcription_engine = self.gui.get_transcription_engine()
        skip_translation = self.gui.is_skip_translation() or self.target_stage == "transcript"
        output_mode = self.gui.get_output_mode_key()
        prefetch_tts = self.target_stage == "full" and output_mode in ("voice", "both")
        self.gui.prepare_workflow_thread = PrepareWorkflowWorker(
            self.gui.workspace_root,
            video_path,
            output_mode,
            self.gui.get_audio_handling_mode(),
            self.gui.get_source_language_code(),
            self.gui.get_target_language_code(),
            self.gui.is_ai_polish_enabled(),
            False,
            self.gui.get_ai_style_instruction(),
            self.gui.get_whisper_model_name(),
            transcription_engine=transcription_engine,
            speaker_diarization=self.gui.is_speaker_diarization_enabled(),
            speaker_diarization_num_speakers=self.gui.get_speaker_diarization_num_speakers(),
            skip_translation=skip_translation,
            prefetch_voice_name=self.gui.get_active_voice_name() if prefetch_tts else "",
            prefetch_voice_speed=self.gui._parse_voice_speed_value() if prefetch_tts else 1.0,
            remote_api_url=self.local_worker_api_url,
            remote_api_token=self.local_worker_api_token,
            force_remote_api=True,
            timeline_clips=(
                self.gui.get_timeline_video_clips(existing_only=True)
                if hasattr(self.gui, "get_timeline_video_clips") else []
            ),
        )
        
        # Connect signals
        self.gui.prepare_workflow_thread.step_started.connect(self._on_prepare_step_started)
        self.gui.prepare_workflow_thread.finished.connect(
            lambda project_state_path, error, run_id=prepare_run_id: self.on_prepare_workflow_finished(
                project_state_path,
                error,
                run_id,
            )
        )
        self.gui.prepare_workflow_thread.start()

    def _on_prepare_step_started(self, step_id, message=""):
        if step_id == "translation":
            try:
                self.gui.update_project_step("translate_raw", "running")
            except Exception:
                pass
        if not self.progress_dialog:
            return
        labels = {
            "prepare": "Preparing project",
            "extract_audio": "Extracting audio",
            "extraction": "Extracting audio",
            "separation": "Separating vocals",
            "diarization": "Detecting speakers",
            "transcription": "Transcribing audio",
            "translation": "Translating subtitles",
            "done": "Prepare complete",
            "error": "Prepare failed",
        }
        label = str(message or labels.get(str(step_id or ""), step_id or "Processing")).strip()
        if label and self.progress_dialog:
            self.progress_dialog.footer.setText(f"Prepare: {label}")
            self.progress_dialog.footer.setStyleSheet("color: #9fb7d5; font-size: 13px; margin-top: 15px;")
        if step_id == "transcription":
            self._hide_whisper_download_dialog()

    def on_prepare_workflow_finished(self, project_state_path, error, run_id=None):
        """Callback when the background PrepareWorkflow finishes completely."""
        self._hide_whisper_download_dialog()
        if run_id is not None and run_id != self.prepare_run_id:
            self.gui.log("[Pipeline] Ignoring stale prepare result from a stopped run.")
            return
        self._stop_prepare_status_polling()
        self._stop_local_worker_server()
        if not getattr(self.gui, "_pipeline_active", False):
            return

        if error or not project_state_path:
            self.pipeline_fail(f"Prepare workflow failed: {error}")
            self.gui.show_error("Prepare Failed", "Could not complete project preparation.", str(error))
            return

        is_auto_recap = hasattr(self.gui, "is_auto_recap_enabled") and self.gui.is_auto_recap_enabled()

        if self.progress_dialog:
            if is_auto_recap:
                self.progress_dialog.finish_step("analyzing")
            else:
                self.progress_dialog.finish_step("ai_process")

        try:
            state = self.gui.project_service.load_project(project_state_path)
            self.gui.current_project_state = state
            self.gui.load_project_context(state)
            self.gui.refresh_ui_state()
            if self.gui.get_transcription_engine() == "ocr":
                self.gui.toggle_ocr_overlay_visibility(False)
                self.gui.log("[OCR Region] Hidden after OCR transcription completed.")
            self._notify_translation_fallback_if_used()

            if is_auto_recap:
                if self.progress_dialog:
                    self.progress_dialog.finish_step("analyzing")

                # Stage 2: Build a full-timeline effect plan. Scene cuts are
                # boundaries only; Auto Recap must not remove source content.
                self.gui._pipeline_step = "building"
                if self.progress_dialog:
                    self.progress_dialog.start_step("building")
                    self.progress_dialog.footer.setText("Stage 2/5: Building Effect Plan (Keeping All Content)")

                decisions = []
                if hasattr(self.gui, "run_auto_recap_processing"):
                    decisions = self.gui.run_auto_recap_processing()

                if not decisions:
                    self.pipeline_fail("Auto Edit Recap could not create any usable shots from this video.")
                    return

                if self.progress_dialog:
                    self.progress_dialog.finish_step("building")

                # Stage 3: Applying Smart Edits (Zoom, Pan, Crop & Speed)
                self.gui._pipeline_step = "smart_edits"
                if self.progress_dialog:
                    self.progress_dialog.start_step("smart_edits")
                    self.progress_dialog.footer.setText("Stage 3/5: Applying Smart Edits (Zoom, Pan, Crop & Speed)")
                    self.progress_dialog.finish_step("smart_edits")

                # Stage 4: Processing Audio (Voiceover & Ducking)
                self.gui._pipeline_step = "audio"
                if self.progress_dialog:
                    self.progress_dialog.start_step("audio")
                    self.progress_dialog.footer.setText("Stage 4/5: Processing Audio (Voiceover & Ducking)")
                    self.progress_dialog.finish_step("audio")

                # Stage 5: Rendering Recap (FFmpeg 1-Pass)
                self.gui._pipeline_step = "rendering"
                if self.progress_dialog:
                    self.progress_dialog.start_step("rendering")
                    self.progress_dialog.footer.setText("Stage 5/5: Rendering Recap (FFmpeg 1-Pass)")

                video_path = self.gui.video_path_edit.text().strip()
                if video_path and os.path.exists(video_path) and decisions:
                    output_dir = os.path.join(self.gui.workspace_root, "output")
                    os.makedirs(output_dir, exist_ok=True)
                    output_path = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(video_path))[0]}_recap.mp4")
                    from app.services.auto_recap_engine import AutoRecapEngine
                    engine = AutoRecapEngine(getattr(self.gui, "auto_recap_config", None))
                    timeline_clips = self.gui.get_timeline_video_clips(existing_only=True) if hasattr(self.gui, "get_timeline_video_clips") else []
                    timeline_recap_required = bool(
                        len(timeline_clips) > 1
                        or (
                            timeline_clips
                            and float(timeline_clips[0].get("source_start", 0.0) or 0.0) > 0.01
                        )
                    )
                    rendered = (
                        engine.render_timeline_recap_1pass(timeline_clips, output_path, decisions)
                        if timeline_recap_required
                        else engine.render_recap_video_1pass(video_path, output_path, decisions)
                    )
                    if rendered:
                        self.gui.last_recap_video_path = output_path
                        if hasattr(self.gui, "persist_auto_recap_project_data"):
                            self.gui.persist_auto_recap_project_data(decisions, output_path)
                        self.gui.log(f"[Auto Recap] 1-Pass Render complete: {output_path}")

                        # Defer media player reload and timeline sync slightly to allow QThread to exit cleanly without deadlock
                        def _update_recap_ui():
                            try:
                                from PySide6.QtCore import QUrl
                                if hasattr(self.gui, "media_player") and self.gui.media_player is not None:
                                    self.gui.media_player.setSource(QUrl.fromLocalFile(output_path))
                                    if hasattr(self.gui.media_player, "setPosition"):
                                        self.gui.media_player.setPosition(0)
                                if hasattr(self.gui, "video_path_edit"):
                                    self.gui.video_path_edit.setText(output_path)

                                if hasattr(self.gui, "timeline") and getattr(self.gui.timeline, "_timeline", None):
                                    from app.layers.sync_bridge import sync_auto_recap_decisions_to_timeline
                                    sync_auto_recap_decisions_to_timeline(self.gui.timeline._timeline, decisions, output_path)
                                    self.gui.timeline.set_duration(self.gui.timeline._timeline.duration)
                                    self.gui.timeline._redraw()

                                if hasattr(self.gui, "_loaded_live_ass_path"):
                                    self.gui._loaded_live_ass_path = ""
                            except Exception as ex:
                                if hasattr(self.gui, "log"):
                                    self.gui.log(f"[Auto Recap] Warning updating recap UI: {ex}")

                        from PySide6.QtCore import QTimer
                        QTimer.singleShot(150, _update_recap_ui)
                    else:
                        render_error = str(getattr(engine, "last_render_error", "") or "").strip()
                        if render_error:
                            self.gui.log(f"[Auto Recap] FFmpeg render error: {render_error}")
                        self.pipeline_fail("Auto Edit Recap render failed. Check that FFmpeg can read the selected video.")
                        return
                else:
                    self.pipeline_fail("Auto Edit Recap lost access to the selected source video.")
                    return

                if self.progress_dialog:
                    self.progress_dialog.finish_step("rendering")
                    self.progress_dialog.set_completed()
                    self.progress_dialog.footer.setText("✨ Auto Edit Recap Complete! Ready for export.")
                    self.progress_dialog.footer.setStyleSheet("color: #6ee7b7; font-weight: bold; font-size: 13px;")

                self.gui._pipeline_active = False
                self.pipeline_done()
                return
        except Exception as e:
            self.gui.log(f"[Pipeline] Error reloading state: {e}")

        mode = self.gui.get_output_mode_key()
        if self.target_stage in {"transcript", "translate"} or mode == "subtitle":
            self.pipeline_done()
            if self.progress_dialog:
                if self.target_stage == "transcript":
                    self.progress_dialog.skip_step("voiceover")
                elif self.target_stage == "translate":
                    self.progress_dialog.skip_step("voiceover")
                self.progress_dialog.set_completed()
            self.gui.log(f"[Pipeline] Reached requested stage: {self.target_stage}.")
        else:
            self.pipeline_advance("translation")

    def _notify_translation_fallback_if_used(self):
        """Show a UI notice when an AI translation request used Google fallback."""
        selected_provider = str(os.getenv("OPENAI_PROVIDER") or "google").strip().lower()
        if selected_provider == "google" or not self.gui.is_ai_polish_enabled():
            return
        models = list(getattr(self.gui, "current_translated_segment_models", []) or [])
        providers = {
            str(getattr(model, "metadata", {}).get("translation_provider", "") or "").strip().lower()
            for model in models
        }
        if "google-web" not in providers:
            return
        signature = f"{getattr(self, 'prepare_run_id', 0)}:{selected_provider}"
        if getattr(self, "_fallback_notification_signature", "") == signature:
            return
        self._fallback_notification_signature = signature
        notice = "AI Provider is unavailable. Translation completed using Google Translate instead."
        self.gui.log(f"[Translation] {notice}")
        QMessageBox.information(self.gui, "Translation Fallback", notice)

    def pipeline_advance(self, completed_step: str):
        """Manages transitions between major pipeline segments."""
        if not self.gui._pipeline_active:
            return
            
        if self.progress_dialog:
            self.progress_dialog.finish_step(completed_step)

        mode = self.gui.get_output_mode_key()
        
        # State transitions
        if completed_step == "translation":
            if mode == "subtitle":
                self.pipeline_done()
                if self.progress_dialog:
                    self.progress_dialog.skip_step("voiceover")
                    self.progress_dialog.skip_step("preview")
                    self.progress_dialog.set_completed()
                return
            # Start voiceover
            self.gui._pipeline_step = "voiceover"
            if self.progress_dialog and self.progress_dialog.isVisible():
                self.progress_dialog.start_step("voiceover")
            self.gui.run_voiceover()
            
        elif completed_step == "voiceover":
            if getattr(self, "target_stage", "full") == "tts":
                self.pipeline_done()
                if self.progress_dialog:
                    self.progress_dialog.skip_step("preview")
                    self.progress_dialog.set_completed()
                return
            self.gui._pipeline_step = "preview"
            if self.progress_dialog and self.progress_dialog.isVisible():
                self.progress_dialog.start_step("preview")
            timeline_clips = self.gui.get_timeline_video_clips(existing_only=True) if hasattr(self.gui, "get_timeline_video_clips") else []
            if len(timeline_clips) > 1:
                self.gui.log("[Pipeline] Multi-video V1 preview is live; continuing to one-pass Timeline export.")
                self.pipeline_advance("preview")
                return
            try:
                self.gui.log("[Pipeline] Voiceover complete. Preparing video preview.")
                self.gui.preview_video()
            except Exception as exc:
                self.pipeline_fail(f"Preview start failed: {exc}")
            
        elif completed_step == "preview":
            # Success!
            self.pipeline_done()
            if self.progress_dialog: 
                self.progress_dialog.set_completed()

    def pipeline_fail(self, reason: str):
        """Safely stops the pipeline and restores UI state on failure."""
        self.gui._pipeline_active = False
        self._stop_prepare_status_polling()
        self._stop_local_worker_server()
        
        if self.progress_dialog:
            current_step = getattr(self.gui, "_pipeline_step", "prepare")
            self.progress_dialog.fail_step(current_step)
            # Show the error reason in the footer
            self.progress_dialog.footer.setText(f"FAILED: {reason}")
            self.progress_dialog.footer.setStyleSheet("color: #FF4444; font-weight: bold;")

        # Restore UI
        if hasattr(self.gui, "run_all_btn"):
            self.gui.run_all_btn.setEnabled(True)
            self.gui.run_all_btn.setText("Generate")
        
        if hasattr(self.gui, "progress_bar") and self.gui.progress_bar is not None:
            self.gui.progress_bar.setRange(0, 100)
            self.gui.progress_bar.setValue(0)
        self.gui.refresh_ui_state()

    def pipeline_done(self):
        """Marks the entire pipeline as successfully finished."""
        self.gui._pipeline_active = False
        self.gui._pipeline_step = ""
        self._stop_prepare_status_polling()
        self._stop_local_worker_server()
        if hasattr(self.gui, "prepare_workflow_thread") and self.gui.prepare_workflow_thread is not None:
            try:
                self.gui.prepare_workflow_thread.deleteLater()
            except Exception:
                pass
            self.gui.prepare_workflow_thread = None
        
        if hasattr(self.gui, "run_all_btn"):
            self.gui.run_all_btn.setEnabled(True)
            self.gui.run_all_btn.setText("Generate")
            
        if hasattr(self.gui, "progress_bar") and self.gui.progress_bar is not None:
            self.gui.progress_bar.setRange(0, 100)
            self.gui.progress_bar.setValue(100)
        self.gui.refresh_ui_state()
        should_auto_export = (
            getattr(self, "target_stage", "") == "full"
            and not getattr(self, "_generate_export_started", False)
            and not (hasattr(self.gui, "is_auto_recap_enabled") and self.gui.is_auto_recap_enabled())
        )
        if should_auto_export:
            self._generate_export_started = True
            self.gui.log("[Pipeline] Generate complete; exporting the current V1 Timeline order.")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self.gui.export_final_video(automatic=True))
