import os
import sys
import unittest
from unittest.mock import patch

import requests


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "app"))

from remote_api import remote_api_post


class RemoteApiClientTests(unittest.TestCase):
    def test_read_timeout_is_retried(self):
        with patch("remote_api.requests.post", side_effect=requests.Timeout("slow")) as post:
            with self.assertRaises(requests.Timeout):
                remote_api_post("/v1/status", {}, timeout=1, retries=2)
        self.assertEqual(post.call_count, 2)


if __name__ == "__main__":
    unittest.main()
