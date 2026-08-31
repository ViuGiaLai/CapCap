import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "app"), str(ROOT)]

from app.services.project_service import ProjectService


class ProjectIsolationTests(unittest.TestCase):
    def test_same_filename_in_different_folders_has_separate_project(self):
        with tempfile.TemporaryDirectory() as folder:
            first_dir = os.path.join(folder, "first")
            second_dir = os.path.join(folder, "second")
            os.makedirs(first_dir)
            os.makedirs(second_dir)
            first = os.path.join(first_dir, "episode.mp4")
            second = os.path.join(second_dir, "episode.mp4")
            Path(first).write_bytes(b"first-video")
            Path(second).write_bytes(b"second-video")
            service = ProjectService(folder)

            first_state = service.ensure_project(first)
            second_state = service.ensure_project(second)

            self.assertNotEqual(first_state.project_id, second_state.project_id)
            self.assertNotEqual(first_state.project_root, second_state.project_root)

    def test_replaced_file_at_same_path_is_marked_as_new_content(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "episode.mp4")
            Path(source).write_bytes(b"video-version-one")
            service = ProjectService(folder)
            original = service.ensure_project(source)
            self.assertNotIn("input_video_content_changed", original.settings)

            Path(source).write_bytes(b"video-version-two")
            reopened = service.ensure_project(source)

            self.assertIn("input_video_content_changed", reopened.settings)
            change = reopened.settings["input_video_content_changed"]
            self.assertNotEqual(
                change["previous"]["sample_sha1"],
                change["current"]["sample_sha1"],
            )

    def test_new_projects_receive_sequential_names_and_are_video_independent(self):
        with tempfile.TemporaryDirectory() as folder:
            service = ProjectService(folder)

            first = service.create_project()
            second = service.create_project()

            self.assertEqual(first.display_name, "VIUSTUDIO10000")
            self.assertEqual(second.display_name, "VIUSTUDIO10001")
            self.assertEqual(first.project_id, "viustudio10000")
            self.assertEqual(second.project_id, "viustudio10001")
            self.assertEqual(first.input_video, "")
            self.assertNotEqual(first.project_id, second.project_id)
            self.assertTrue(os.path.isfile(service.project_file(first.project_root)))

    def test_rename_changes_only_display_name(self):
        with tempfile.TemporaryDirectory() as folder:
            service = ProjectService(folder)
            state = service.create_project()
            old_id = state.project_id
            old_root = state.project_root

            service.rename_project(state, "My Episode 01")
            reopened = service.load_project(service.project_file(old_root))

            self.assertEqual(reopened.display_name, "My Episode 01")
            self.assertEqual(reopened.project_id, old_id)
            self.assertEqual(reopened.project_root, old_root)
            next_project = service.create_project()
            self.assertEqual(next_project.display_name, "VIUSTUDIO10001")

    def test_rename_rejects_empty_or_path_like_names(self):
        with tempfile.TemporaryDirectory() as folder:
            service = ProjectService(folder)
            state = service.create_project()
            with self.assertRaises(ValueError):
                service.rename_project(state, "   ")
            with self.assertRaises(ValueError):
                service.rename_project(state, "bad/name")

    def test_translation_cache_changes_with_provider_and_local_model(self):
        previous_provider = os.environ.get("OPENAI_PROVIDER")
        previous_model = os.environ.get("LLAMA_APP_MODEL")
        try:
            with tempfile.TemporaryDirectory() as folder:
                service = ProjectService(folder)
                segments = [{"start": 0.0, "end": 2.0, "text": "你好"}]
                os.environ["OPENAI_PROVIDER"] = "google"
                google_signature = service.build_translation_signature(segments)
                model = os.path.join(folder, "local.gguf")
                Path(model).write_bytes(b"model-v1")
                os.environ["OPENAI_PROVIDER"] = "llama_app"
                os.environ["LLAMA_APP_MODEL"] = model
                llama_signature = service.build_translation_signature(segments)
                Path(model).write_bytes(b"model-v2")
                replaced_model_signature = service.build_translation_signature(segments)
                self.assertNotEqual(google_signature, llama_signature)
                self.assertNotEqual(llama_signature, replaced_model_signature)
        finally:
            if previous_provider is None:
                os.environ.pop("OPENAI_PROVIDER", None)
            else:
                os.environ["OPENAI_PROVIDER"] = previous_provider
            if previous_model is None:
                os.environ.pop("LLAMA_APP_MODEL", None)
            else:
                os.environ["LLAMA_APP_MODEL"] = previous_model

    def test_ensure_project_reuses_existing_project_with_same_video_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            service = ProjectService(folder)
            video = os.path.join(folder, "3-4_movie_douyin.mp4")
            Path(video).write_bytes(b"video-content")
            viustudio_state = service.create_project()
            viustudio_state.input_video = os.path.abspath(video)
            viustudio_state.set_setting("input_video_identity", service._input_video_identity(video))
            service.save_project(viustudio_state)

            ensured_state = service.ensure_project(video)
            self.assertEqual(ensured_state.project_id, viustudio_state.project_id)
            self.assertEqual(ensured_state.project_root, viustudio_state.project_root)
            self.assertEqual(ensured_state.input_video, os.path.abspath(video))
            self.assertEqual(ensured_state.display_name, viustudio_state.display_name)

    def test_ensure_project_creates_new_project_when_no_matching_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            service = ProjectService(folder)
            video1 = os.path.join(folder, "3-4_movie_douyin.mp4")
            video2 = os.path.join(folder, "5-6_movie_youtube.mp4")
            Path(video1).write_bytes(b"video-content-1")
            Path(video2).write_bytes(b"video-content-2")
            viustudio_state = service.create_project()
            service.save_project(viustudio_state)

            ensured_state = service.ensure_project(video2)
            self.assertNotEqual(ensured_state.project_id, viustudio_state.project_id)
            self.assertEqual(ensured_state.input_video, os.path.abspath(video2))


if __name__ == "__main__":
    unittest.main()
