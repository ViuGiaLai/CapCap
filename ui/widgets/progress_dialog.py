from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QProgressBar, QFrame, QScrollArea, QWidget, 
    QGraphicsDropShadowEffect, QPushButton, QProgressDialog
)
import time
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor


class BackgroundableProgressDialog(QProgressDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._background_only = True

    def set_background_only(self, enabled: bool):
        self._background_only = bool(enabled)

    def closeEvent(self, event):
        if self._background_only:
            self.hide()
            event.ignore()
            return
        super().closeEvent(event)

class StepWidget(QFrame):
    def __init__(self, name, parent=None):
        super().__init__(parent)
        self.setObjectName("stepWidget")
        self.status = "pending"
        self.setStyleSheet("""
            #stepWidget {
                background-color: #11141d;
                border: 1px solid #1e2433;
                border-radius: 8px;
                padding: 6px;
                margin-bottom: 4px;
            }
            QLabel {
                color: #e2e8f0;
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Inter', Roboto, sans-serif;
            }
            #stepName {
                font-size: 13px;
                font-weight: 600;
            }
            #stepStatus {
                font-size: 11px;
                font-weight: 600;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 11)
        layout.setSpacing(7)
        header = QHBoxLayout()
        
        self.indicator = QWidget()
        self.indicator.setFixedSize(8, 8)
        self.indicator.setStyleSheet("background-color: #334155; border-radius: 4px;")
        header.addWidget(self.indicator)
        header.addSpacing(8)
        
        self.name_label = QLabel(name)
        self.name_label.setObjectName("stepName")
        header.addWidget(self.name_label)
        
        header.addStretch()
        
        self.status_label = QLabel("Pending")
        self.status_label.setObjectName("stepStatus")
        self.status_label.setFixedWidth(80)
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status_label.setStyleSheet("color: #64748b;")
        header.addWidget(self.status_label)
        layout.addLayout(header)

        self.detail_label = QLabel("Waiting for the previous step")
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet("color: #718096; font-size: 11px;")
        layout.addWidget(self.detail_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setStyleSheet("""
            QProgressBar { background: #0b1020; border: none; border-radius: 2px; }
            QProgressBar::chunk { background: #3b82f6; border-radius: 2px; }
        """)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        # Pulse animation for running state
        self.pulse_timer = QTimer(self)
        self.pulse_timer.setInterval(800)
        self.pulse_timer.timeout.connect(self._toggle_pulse)
        self._pulse_state = False

    def set_status(self, status):
        self.status = status
        if status == "running":
            self.status_label.setText("Running")
            self.status_label.setStyleSheet("color: #60a5fa;")
            self.indicator.setStyleSheet("background-color: #3b82f6; border-radius: 4px;")
            self.setStyleSheet("""
                #stepWidget {
                    background-color: #162035;
                    border: 1px solid #3b82f6;
                    border-radius: 8px;
                    padding: 6px;
                    margin-bottom: 4px;
                }
                QLabel { color: #f8fafc; }
                #stepName { font-size: 13px; font-weight: 600; }
                #stepStatus { font-size: 11px; font-weight: 600; }
            """)
            self.pulse_timer.start()
            self.progress_bar.show()
            if self.detail_label.text() == "Waiting for the previous step":
                self.detail_label.setText("Starting…")
        elif status == "done":
            self.status_label.setText("Completed")
            self.status_label.setStyleSheet("color: #6ee7b7;")
            self.indicator.setStyleSheet("background-color: #10b981; border-radius: 4px;")
            self.setStyleSheet("""
                #stepWidget {
                    background-color: #0d291e;
                    border: 1px solid #165b40;
                    border-radius: 8px;
                    padding: 6px;
                    margin-bottom: 4px;
                }
                QLabel { color: #f8fafc; }
                #stepName { font-size: 13px; font-weight: 600; }
                #stepStatus { font-size: 11px; font-weight: 600; }
            """)
            self.pulse_timer.stop()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.progress_bar.show()
            if self.detail_label.text() in {"Starting…", "Waiting for the previous step"}:
                self.detail_label.setText("Finished successfully")
        elif status == "failed":
            self.status_label.setText("Failed")
            self.status_label.setStyleSheet("color: #fca5a5;")
            self.indicator.setStyleSheet("background-color: #ef4444; border-radius: 4px;")
            self.setStyleSheet("""
                #stepWidget {
                    background-color: #2a181e;
                    border: 1px solid #4f202a;
                    border-radius: 8px;
                    padding: 6px;
                    margin-bottom: 4px;
                }
                QLabel { color: #f8fafc; }
                #stepName { font-size: 13px; font-weight: 600; }
                #stepStatus { font-size: 11px; font-weight: 600; }
            """)
            self.pulse_timer.stop()
            self.progress_bar.show()
        elif status == "skipped":
            self.status_label.setText("Skipped")
            self.status_label.setStyleSheet("color: #fde047;")
            self.indicator.setStyleSheet("background-color: #f59e0b; border-radius: 4px;")
            self.pulse_timer.stop()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.progress_bar.show()
            self.detail_label.setText("Not required for this run")
        else:
            self.status_label.setText("Pending")
            self.status_label.setStyleSheet("color: #64748b;")
            self.indicator.setStyleSheet("background-color: #334155; border-radius: 4px;")
            self.setStyleSheet("""
                #stepWidget {
                    background-color: #11141d;
                    border: 1px solid #1e2433;
                    border-radius: 8px;
                    padding: 6px;
                    margin-bottom: 4px;
                }
                QLabel { color: #94a3b8; }
                #stepName { font-size: 13px; font-weight: 600; }
                #stepStatus { font-size: 11px; font-weight: 600; }
            """)
            self.progress_bar.hide()
            self.detail_label.setText("Waiting for the previous step")

    def set_progress(self, percent=None, detail=""):
        if detail:
            self.detail_label.setText(str(detail).strip())
        self.progress_bar.show()
        if percent is None or int(percent) < 0:
            self.progress_bar.setRange(0, 0)
            self.status_label.setText("Working")
            return
        value = max(0, min(100, int(percent)))
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(value)
        if self.status == "running":
            self.status_label.setText(f"{value}%")

    def set_error(self, detail):
        self.set_status("failed")
        self.detail_label.setText(str(detail or "Unknown error").strip())
        
    def _toggle_pulse(self):
        self._pulse_state = not self._pulse_state
        alpha = 255 if self._pulse_state else 120
        self.indicator.setStyleSheet(f"background-color: rgba(59, 130, 246, {alpha}); border-radius: 4px;")

class PipelineProgressDialog(QDialog):
    stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stopped = False
        self._drag_pos = None
        self.setWindowTitle("VIUStudio AI Pipeline")
        self.setFixedSize(640, 700)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setWindowModality(Qt.NonModal)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.workflow_start_time = None
        self.total_timer = QTimer(self)
        self.total_timer.setInterval(1000)
        self.total_timer.timeout.connect(self._update_total_time)
        
        self.main_frame = QFrame(self)
        self.main_frame.setObjectName("mainFrame")
        self.main_frame.setFixedSize(620, 680)
        self.main_frame.move(10, 10)
        self.main_frame.setStyleSheet("""
            #mainFrame {
                background-color: #141824;
                border: 1px solid #23293a;
                border-radius: 12px;
            }
        """)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(10)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.main_frame.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.main_frame)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)
        
        header_layout = QHBoxLayout()
        self.title_label = QLabel("AI Production Pipeline")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #f8fafc;")
        header_layout.addWidget(self.title_label)

        self.overall_percent_label = QLabel("0%")
        self.overall_percent_label.setAlignment(Qt.AlignCenter)
        self.overall_percent_label.setFixedSize(48, 26)
        self.overall_percent_label.setStyleSheet(
            "background:#10243d; color:#7dd3fc; border:1px solid #28527a; "
            "border-radius:13px; font-size:12px; font-weight:700;"
        )
        
        self.close_btn = QPushButton("✕", self)
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: none;
                color: #94a3b8;
                font-size: 14px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1e2433;
                color: #f8fafc;
            }
        """)
        self.close_btn.clicked.connect(self.hide)
        header_layout.addStretch()
        header_layout.addWidget(self.overall_percent_label)
        header_layout.addWidget(self.close_btn)
        layout.addLayout(header_layout)
        
        self.overall_progress = QProgressBar()
        self.overall_progress.setFixedHeight(8)
        self.overall_progress.setRange(0, 100)
        self.overall_progress.setValue(0)
        self.overall_progress.setTextVisible(False)
        self.overall_progress.setStyleSheet("""
            QProgressBar {
                background: #11141d;
                border: 1px solid #1e2433;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #10b981);
                border-radius: 2px;
            }
        """)
        layout.addWidget(self.overall_progress)

        self.overall_detail = QLabel("Preparing workflow…")
        self.overall_detail.setStyleSheet("color:#8292aa; font-size:11px;")
        layout.addWidget(self.overall_detail)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 6, 4, 0)
        self.scroll_layout.setSpacing(4)
        self.scroll_layout.addStretch()
        
        self.scroll.setWidget(self.scroll_content)
        self.scroll.setStyleSheet("background: transparent;")
        layout.addWidget(self.scroll, 1)
        
        self.steps = {}
        self.step_order = []
        
        self.footer = QLabel("Initializing workflow engine...")
        self.footer.setWordWrap(True)
        self.footer.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(self.footer)

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.error_label.setStyleSheet(
            "background:#29151b; color:#fecaca; border:1px solid #6b2635; "
            "border-radius:7px; padding:9px; font-size:11px;"
        )
        self.error_label.hide()
        layout.addWidget(self.error_label)

        self.total_time_label = QLabel("Elapsed 00:00  •  Remaining —")
        self.total_time_label.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        layout.addWidget(self.total_time_label)

        self.dismiss_btn = QPushButton("Close")
        self.dismiss_btn.setFixedHeight(34)
        self.dismiss_btn.setStyleSheet("""
            QPushButton {
                background-color: #1c2230;
                color: #e2e8f0;
                border: 1px solid #2b354a;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #262e42;
                border-color: #3b82f6;
                color: #ffffff;
            }
        """)
        self.dismiss_btn.clicked.connect(self.hide)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setFixedHeight(34)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #24141a;
                color: #fca5a5;
                border: 1px solid #4a2028;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #361a24;
                border-color: #ef4444;
            }
        """)
        self.stop_btn.clicked.connect(self._on_stop)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.stop_btn.setMinimumWidth(160)
        self.dismiss_btn.setMinimumWidth(160)
        btn_row.addWidget(self.stop_btn)
        btn_row.addWidget(self.dismiss_btn)
        layout.addLayout(btn_row)

    def closeEvent(self, event):
        self.hide()
        event.ignore()

    def _set_preview_overlays_suppressed(self, suppressed: bool):
        """Keep top-level video overlays below this non-modal pipeline window."""
        parent = self.parentWidget()
        video_view = getattr(parent, "video_view", None)
        if video_view is None:
            return
        subtitle = getattr(video_view, "subtitle_item", None)
        text_overlay = getattr(video_view, "text_overlay", None)
        if subtitle is not None:
            if hasattr(subtitle, "set_suppressed"):
                subtitle.set_suppressed(suppressed)
            elif hasattr(subtitle, "setVisible"):
                subtitle.setVisible(not suppressed)
        if text_overlay is not None:
            if hasattr(text_overlay, "set_suppressed"):
                text_overlay.set_suppressed(suppressed)
            elif hasattr(text_overlay, "setVisible"):
                text_overlay.setVisible(not suppressed)
        if not suppressed and hasattr(video_view, "_restore_subtitle_overlay"):
            QTimer.singleShot(0, video_view._restore_subtitle_overlay)

    def showEvent(self, event):
        self._set_preview_overlays_suppressed(True)
        super().showEvent(event)

    def add_step(self, step_id, name):
        widget = StepWidget(name)
        self.steps[step_id] = widget
        self.step_order.append(step_id)
        self.scroll_layout.insertWidget(len(self.step_order) - 1, widget)
        return widget

    def start_step(self, step_id):
        if step_id in self.steps:
            if self.workflow_start_time is None:
                self.workflow_start_time = time.monotonic()
                self.total_timer.start()
            self.steps[step_id].set_status("running")
            idx = self.step_order.index(step_id)
            val = int((idx / len(self.step_order)) * 100)
            self.overall_progress.setValue(val)
            self.overall_percent_label.setText(f"{val}%")
            self.overall_detail.setText(
                f"Step {idx + 1} of {len(self.step_order)}  •  {self.steps[step_id].name_label.text()}"
            )
            self.footer.setText(f"Stage {idx+1}/{len(self.step_order)}: {self.steps[step_id].name_label.text()}")

    def update_step_progress(self, step_id, percent=None, detail=""):
        if step_id not in self.steps:
            return
        widget = self.steps[step_id]
        if widget.status != "running":
            self.start_step(step_id)
        widget.set_progress(percent, detail)
        idx = self.step_order.index(step_id)
        stage_fraction = (
            0.0 if percent is None or int(percent) < 0
            else max(0, min(100, int(percent))) / 100.0
        )
        overall = int(((idx + stage_fraction) / max(1, len(self.step_order))) * 100)
        self.overall_progress.setValue(overall)
        self.overall_percent_label.setText(f"{overall}%")
        self.overall_detail.setText(
            f"Step {idx + 1} of {len(self.step_order)}  •  {widget.name_label.text()}"
        )
        if detail:
            self.footer.setText(str(detail).strip())

    def finish_step(self, step_id):
        if step_id in self.steps:
            self.steps[step_id].set_status("done")
            idx = self.step_order.index(step_id)
            val = int(((idx + 1) / len(self.step_order)) * 100)
            self.overall_progress.setValue(val)
            self.overall_percent_label.setText(f"{val}%")

    def fail_step(self, step_id):
        if step_id in self.steps:
            self.steps[step_id].set_status("failed")
            self.footer.setText(f"Error encountered during: {self.steps[step_id].name_label.text()}")
            self.footer.setStyleSheet("color: #FF4444; font-weight: bold; margin-top: 15px;")
            self._stop_total_timer()

    def skip_step(self, step_id):
        if step_id in self.steps:
            self.steps[step_id].set_status("skipped")

    def set_error(self, step_id, reason):
        step = self.steps.get(step_id)
        if step is not None:
            step.set_error(reason)
            step_name = step.name_label.text()
        else:
            step_name = str(step_id or "Current step")
        message = str(reason or "Unknown error").strip()
        self.error_label.setText(f"Failed in {step_name}\n{message}")
        self.error_label.show()
        self.footer.setText(f"Stopped at: {step_name}")
        self.footer.setStyleSheet("color:#fca5a5; font-size:12px; font-weight:600;")
        self._stop_total_timer()

    def set_completed(self):
        self.stop_btn.hide()
        for step_id in self.step_order:
            widget = self.steps.get(step_id)
            if widget is None:
                continue
            if widget.status == "running":
                widget.set_status("done")
            elif widget.status == "pending":
                widget.set_status("skipped")
        self.overall_progress.setValue(100)
        self.overall_percent_label.setText("100%")
        self.overall_detail.setText("All requested steps completed")
        self.footer.setText("✨ Pipeline execution complete! Video is ready.")
        self.footer.setStyleSheet("color: #00FF88; font-weight: bold; font-size: 14px; margin-top: 15px;")
        self._stop_total_timer()

    def _update_total_time(self):
        if self.workflow_start_time is None:
            return
        elapsed = int(time.monotonic() - self.workflow_start_time)
        mins = elapsed // 60
        secs = elapsed % 60
        hours, mins = divmod(mins, 60)
        elapsed_text = (
            f"{hours}:{mins:02d}:{secs:02d}" if hours > 0
            else f"{mins:02d}:{secs:02d}"
        )
        value = self.overall_progress.value()
        if 1 <= value < 100:
            remaining = max(0, int(elapsed * (100 - value) / value))
            eta_text = f"{remaining // 60:02d}:{remaining % 60:02d}"
        else:
            eta_text = "—"
        self.total_time_label.setText(f"Elapsed {elapsed_text}  •  Remaining {eta_text}")

    def _stop_total_timer(self):
        if self.total_timer.isActive():
            self.total_timer.stop()
        if self.workflow_start_time is None:
            return
        elapsed = int(time.monotonic() - self.workflow_start_time)
        mins = elapsed // 60
        secs = elapsed % 60
        hours, mins = divmod(mins, 60)
        elapsed_text = (
            f"{hours}:{mins:02d}:{secs:02d}" if hours > 0
            else f"{mins:02d}:{secs:02d}"
        )
        remaining_text = "00:00" if self.overall_progress.value() >= 100 else "—"
        self.total_time_label.setText(f"Elapsed {elapsed_text}  •  Remaining {remaining_text}")
        self.workflow_start_time = None

    def _on_stop(self):
        self._stopped = True
        self.stop_btn.setEnabled(False)
        self.stop_btn.setText("Stopping...")
        self.footer.setText("Stopping pipeline...")
        self.footer.setStyleSheet("color: #FF6B6B; font-weight: bold; font-size: 14px; margin-top: 15px;")
        self.stop_requested.emit()

    def cancel_stop_request(self):
        self._stopped = False
        self.stop_btn.setEnabled(True)
        self.stop_btn.setText("Stop")
        self.footer.setText("Pipeline is still running.")
        self.footer.setStyleSheet("color: #888; font-size: 13px; margin-top: 15px;")

    def hideEvent(self, event):
        self._stop_total_timer()
        super().hideEvent(event)
        self._set_preview_overlays_suppressed(False)

    # Drag support for frameless window
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.move(self.pos() + event.globalPosition().toPoint() - self._drag_pos)
            self._drag_pos = event.globalPosition().toPoint()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)
