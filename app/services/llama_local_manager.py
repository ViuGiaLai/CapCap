import os
import subprocess
import threading
import time
import json
import logging
from typing import List, Dict
import socket
import urllib.request
import atexit
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class LlamaServerManager:
    _instance = None
    
    def __init__(self):
        self.process = None
        self.port = 49683
        self.current_model = None
        self.log_handle = None
        self.bin_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "bin", "llama_cpp"))
        self.exe_path = os.path.join(self.bin_dir, "llama-server.exe")
        self.models_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "models", "local_translation"))
        os.makedirs(self.models_dir, exist_ok=True)
        atexit.register(self.stop_server)
        
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = LlamaServerManager()
        return cls._instance

    def _is_port_in_use(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', port)) == 0

    def start_server(self, model_path: str):
        if self.process and self.process.poll() is None:
            if self.current_model == model_path:
                return  # Already running the right model
            self.stop_server()
            
        if not os.path.exists(self.exe_path):
            raise FileNotFoundError(f"llama-server.exe not found at {self.exe_path}")
            
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found at {model_path}")
            
        # Find available port
        while self._is_port_in_use(self.port):
            self.port += 1

        cmd = [
            self.exe_path,
            "-m", model_path,
            "--port", str(self.port),
            "-c", "8192", # Context size
            "--threads", "6"
        ]
        
        log_path = os.path.join(self.models_dir, "llama-server.log")
        self.log_handle = open(log_path, "w", encoding="utf-8")
        
        # Start server without a window
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        
        self.process = subprocess.Popen(
            cmd,
            stdout=self.log_handle,
            stderr=subprocess.STDOUT,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        self.current_model = model_path
        
        # Wait for the actual HTTP health endpoint. A listening socket alone
        # can appear before the model is ready, which made Test Connection
        # report success while the translation worker immediately failed.
        health_url = f"http://127.0.0.1:{self.port}/health"
        deadline = time.monotonic() + 120.0
        last_error = ""
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                last_error = f"llama-server exited with code {self.process.returncode}"
                break
            try:
                with urllib.request.urlopen(health_url, timeout=1.0) as response:
                    if response.status == 200:
                        return
            except Exception as exc:
                last_error = str(exc)
            time.sleep(0.25)
        self.stop_server()
        log_tail = ""
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as handle:
                log_tail = handle.read()[-1200:]
        except OSError:
            pass
        raise RuntimeError(f"llama.cpp server did not become ready: {last_error}\n{log_tail}".strip())

    def stop_server(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
            self.process = None
            self.current_model = None
        if self.log_handle is not None:
            try:
                self.log_handle.close()
            except OSError:
                pass
            self.log_handle = None

    def get_base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

def fast_scan_gguf() -> List[Dict]:
    """Scans local drives for .gguf files very quickly, skipping system directories."""
    import string
    drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
    results = []
    
    skip_dirs = {
        "Windows", "Program Files", "Program Files (x86)", "$Recycle.Bin", 
        "System Volume Information", "ProgramData", "AppData",
        "node_modules", ".git"
    }

    def scan_dir(path):
        try:
            with os.scandir(path) as it:
                for entry in it:
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in skip_dirs and not entry.name.startswith('.'):
                            scan_dir(entry.path)
                    elif entry.is_file(follow_symlinks=False) and entry.name.lower().endswith('.gguf'):
                        stat = entry.stat()
                        results.append({
                            "name": entry.name,
                            "path": entry.path,
                            "size": stat.st_size
                        })
        except (PermissionError, OSError):
            pass

    with ThreadPoolExecutor(max_workers=len(drives)) as executor:
        executor.map(scan_dir, drives)
        
    return sorted(results, key=lambda x: x["size"], reverse=True)
