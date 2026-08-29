from __future__ import annotations

import atexit
import json
import os
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request

from runtime_paths import join_root, subprocess_hidden_kwargs

from .local_translation_config import is_valid_gguf, selected_model_info


def local_translation_executable() -> str:
    return join_root("bin", "llama_cpp", "llama-server.exe")


def local_translation_model() -> str:
    return str(selected_model_info().get("path") or "")


def local_translation_model_name() -> str:
    return str(selected_model_info().get("filename") or "local-model.gguf")


def local_translation_assets_ready() -> bool:
    return os.path.isfile(local_translation_executable()) and is_valid_gguf(local_translation_model())


class LocalTranslationRuntime:
    """Own the bundled llama.cpp server used only by CapCap translation."""

    def __init__(self):
        self._lock = threading.RLock()
        self._process: subprocess.Popen | None = None
        self._base_url = ""
        self._log_handle = None

    @property
    def base_url(self) -> str:
        return self._base_url

    def ensure_ready(self, timeout: float = 90.0) -> str:
        if not local_translation_assets_ready():
            raise FileNotFoundError(
                "Local translation package is not installed. Open Manage Resources and download Local AI Translation."
            )
        with self._lock:
            selected_path = os.path.normcase(os.path.abspath(local_translation_model()))
            if (
                self._process is not None
                and self._process.poll() is None
                and self._is_healthy()
                and getattr(self, "_active_model_path", "") == selected_path
            ):
                return self._base_url
            self.stop()
            port = self._free_loopback_port()
            self._base_url = f"http://127.0.0.1:{port}/v1"
            os.makedirs(os.path.dirname(local_translation_model()), exist_ok=True)
            log_path = os.path.join(os.path.dirname(local_translation_model()), "llama-server.log")
            self._log_handle = open(log_path, "a", encoding="utf-8")
            cpu_count = max(1, os.cpu_count() or 1)
            threads = max(2, min(16, cpu_count))

            proc_env = os.environ.copy()
            cuda_dir = join_root("bin", "cuda12_fw")
            if os.path.isdir(cuda_dir):
                proc_env["PATH"] = cuda_dir + os.pathsep + proc_env.get("PATH", "")
                if hasattr(os, "add_dll_directory"):
                    try:
                        os.add_dll_directory(cuda_dir)
                    except Exception:
                        pass

            command = [
                local_translation_executable(),
                "--model", local_translation_model(),
                "--host", "127.0.0.1",
                "--port", str(port),
                "--ctx-size", os.getenv("CAPCAP_LOCAL_TRANSLATION_CONTEXT", "8192"),
                "--threads", str(threads),
                "--n-gpu-layers", os.getenv("CAPCAP_LOCAL_TRANSLATION_GPU_LAYERS", "99"),
                "--parallel", "1",
                "--no-webui",
            ]
            self._process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=self._log_handle,
                stderr=subprocess.STDOUT,
                env=proc_env,
                **subprocess_hidden_kwargs(),
            )
            self._active_model_path = selected_path

        deadline = time.monotonic() + max(5.0, timeout)
        while time.monotonic() < deadline:
            if self._process is None or self._process.poll() is not None:
                raise RuntimeError(
                    f"Local translation runtime stopped during startup. See {log_path}."
                )
            if self._is_healthy():
                return self._base_url
            time.sleep(0.25)
        self.stop()
        raise TimeoutError(f"Local translation runtime did not start in time. See {log_path}.")

    def stop(self) -> None:
        with self._lock:
            process = self._process
            self._process = None
            self._base_url = ""
            self._active_model_path = ""
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
            if self._log_handle is not None:
                self._log_handle.close()
                self._log_handle = None

    def _is_healthy(self) -> bool:
        if not self._base_url:
            return False
        try:
            with urllib.request.urlopen(self._base_url.removesuffix("/v1") + "/health", timeout=1.0) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace") or "{}")
            return response.status == 200 and payload.get("status") in {"ok", "no slot available"}
        except (OSError, ValueError, urllib.error.URLError):
            return False

    @staticmethod
    def _free_loopback_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])


_runtime = LocalTranslationRuntime()
atexit.register(_runtime.stop)


def get_local_translation_runtime() -> LocalTranslationRuntime:
    return _runtime


def stop_local_translation_runtime() -> None:
    _runtime.stop()
