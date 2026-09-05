from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any
import time


@dataclass
class ProgressEvent:
    workflow: str = "general"
    stage: str = ""
    substage: str = ""
    current: float = 0.0
    total: float = 0.0
    percent: int = 0
    message: str = ""
    error_details: Optional[Dict[str, Any]] = None
    timestamp: float = field(default_factory=time.monotonic)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __str__(self) -> str:
        return self.message

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProgressEvent":
        if not isinstance(data, dict):
            return cls(message=str(data or ""))
        return cls(
            workflow=str(data.get("workflow", "general") or "general"),
            stage=str(data.get("stage", "") or ""),
            substage=str(data.get("substage", "") or ""),
            current=float(data.get("current", 0.0) or 0.0),
            total=float(data.get("total", 0.0) or 0.0),
            percent=int(data.get("percent", 0) or 0),
            message=str(data.get("message", "") or ""),
            error_details=data.get("error_details"),
            timestamp=float(data.get("timestamp", time.monotonic()) or time.monotonic()),
        )


class MonotonicProgressTracker:
    """Guarantees non-decreasing progress percentage, prevents premature 100%,
    and calculates smoothed non-linear ETA."""

    def __init__(self, workflow: str = "general", default_stage: str = ""):
        self.workflow = workflow
        self.default_stage = default_stage
        self._max_percent = 0
        self._start_time = time.monotonic()
        self._last_update_time = self._start_time
        self._last_current = 0.0
        self._velocity = 0.0  # units per second
        self._is_completed = False
        self._callbacks = []

    @property
    def current_percent(self) -> int:
        return self._max_percent

    def add_callback(self, cb):
        self._callbacks.append(cb)

    def reset(self):
        self._max_percent = 0
        self._start_time = time.monotonic()
        self._last_update_time = self._start_time
        self._last_current = 0.0
        self._velocity = 0.0
        self._is_completed = False

    def calculate_percent(self, current: float, total: float, stage_start_pct: int = 0, stage_end_pct: int = 100) -> int:
        if total <= 0:
            return self._max_percent
        ratio = max(0.0, min(1.0, float(current) / float(total)))
        raw_pct = stage_start_pct + int(ratio * (stage_end_pct - stage_start_pct))
        # Never exceed 99% until complete
        clamped_pct = max(0, min(99, raw_pct))
        # Monotonic non-decreasing
        if clamped_pct > self._max_percent:
            self._max_percent = clamped_pct
        return self._max_percent

    def update(
        self,
        current: float,
        total: float,
        *,
        stage: str = "",
        substage: str = "",
        message: str = "",
        stage_start_pct: int = 0,
        stage_end_pct: int = 100,
        override_percent: Optional[int] = None,
    ) -> ProgressEvent:
        now = time.monotonic()
        dt = now - self._last_update_time
        if dt >= 0.2 and current > self._last_current:
            instant_velocity = (current - self._last_current) / dt
            self._velocity = instant_velocity if self._velocity <= 0 else (0.7 * self._velocity + 0.3 * instant_velocity)
            self._last_current = current
            self._last_update_time = now

        if override_percent is not None:
            pct = max(self._max_percent, min(99 if not self._is_completed else 100, int(override_percent)))
            self._max_percent = pct
        else:
            pct = self.calculate_percent(current, total, stage_start_pct, stage_end_pct)

        event = ProgressEvent(
            workflow=self.workflow,
            stage=stage or self.default_stage,
            substage=substage,
            current=float(current),
            total=float(total),
            percent=pct,
            message=str(message or "").strip(),
            timestamp=now,
        )
        if hasattr(self, "_callbacks"):
            for cb in self._callbacks:
                cb(event)
        return event

    def estimate_remaining_seconds(self, current: float, total: float) -> Optional[float]:
        if total <= 0 or current <= 0:
            return None
        remaining_units = total - current
        if remaining_units <= 0:
            return 0.0
        if self._velocity > 0:
            return remaining_units / self._velocity
        elapsed = time.monotonic() - self._start_time
        if elapsed > 1.0 and current > 0:
            avg_rate = current / elapsed
            return remaining_units / avg_rate
        return None

    def finish(self, message: str = "Completed successfully") -> ProgressEvent:
        self._is_completed = True
        self._max_percent = 100
        event = ProgressEvent(
            workflow=self.workflow,
            stage=self.default_stage,
            substage="done",
            current=100.0,
            total=100.0,
            percent=100,
            message=message,
            timestamp=time.monotonic(),
        )
        if hasattr(self, "_callbacks"):
            for cb in self._callbacks:
                cb(event)
        return event

    complete = finish

    def fail(self, reason: str, error_details: Optional[Dict[str, Any]] = None, stage: str = "", substage: str = "") -> ProgressEvent:
        return ProgressEvent(
            workflow=self.workflow,
            stage=stage or self.default_stage,
            substage=substage or "failed",
            current=float(self._max_percent),
            total=100.0,
            percent=self._max_percent,
            message=str(reason or "Error encountered").strip(),
            error_details=error_details or {"reason": str(reason)},
            timestamp=time.monotonic(),
        )
