import os
import sys
import unittest
from unittest.mock import patch


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "app"))

from remote_api_server import VIUStudioRemoteHandler, _is_loopback_host, _validate_bind_security


class RemoteApiSecurityTests(unittest.TestCase):
    def test_loopback_bind_does_not_require_token(self):
        _validate_bind_security("127.0.0.1", "")
        _validate_bind_security("::1", "")
        self.assertTrue(_is_loopback_host("localhost"))

    def test_external_bind_requires_token(self):
        with self.assertRaises(RuntimeError):
            _validate_bind_security("0.0.0.0", "")
        with self.assertRaises(RuntimeError):
            _validate_bind_security("192.168.1.10", "")
        _validate_bind_security("0.0.0.0", "per-process-secret")

    def test_transcribe_rejects_malformed_base64(self):
        handler = VIUStudioRemoteHandler.__new__(VIUStudioRemoteHandler)
        with self.assertRaisesRegex(ValueError, "valid standard base64"):
            handler._handle_transcribe({"audio_b64": "not-base64!"})

    def test_transcribe_rejects_oversized_decoded_audio(self):
        handler = VIUStudioRemoteHandler.__new__(VIUStudioRemoteHandler)
        with patch("remote_api_server._MAX_DECODED_AUDIO_BYTES", 2):
            with self.assertRaisesRegex(ValueError, "Decoded audio exceeds"):
                handler._handle_transcribe({"audio_b64": "YWJj"})


if __name__ == "__main__":
    unittest.main()
