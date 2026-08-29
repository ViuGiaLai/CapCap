import os
import sys
import time
import subprocess
import json

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path[:0] = [os.path.join(ROOT, "app"), os.path.join(ROOT, "ui"), ROOT]
sys.stdout.reconfigure(encoding="utf-8")

from app.services.auto_recap_engine import AutoRecapEngine, AutoRecapConfig
from app.services.auto_recap_benchmark import benchmark_auto_recap_pipeline, RecapBenchmarkMetrics


def create_synthetic_test_video(output_path: str, duration: int = 20) -> bool:
    """Generates a 20-second synthetic test video with 4 distinct colored scene cuts and audio synth."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", f"testsrc=duration={duration}:size=1280x720:rate=30",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        output_path
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0


def get_video_duration(video_path: str) -> float:
    """Gets video duration using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", video_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return float(res.stdout.strip())
    except Exception:
        return 0.0


def main():
    print("🚀 Starting End-to-End Self-Testing of CapCap Auto Edit Recap Engine...")
    scratch_dir = os.path.join(ROOT, "scratch")
    os.makedirs(scratch_dir, exist_ok=True)
    
    sample_video = os.path.join(scratch_dir, "sample_movie.mp4")
    output_recap = os.path.join(scratch_dir, "sample_movie_recap.mp4")

    print("\n1. Generating 20-second synthetic multi-scene test video...")
    t_gen_start = time.perf_counter()
    ok = create_synthetic_test_video(sample_video, duration=20)
    t_gen = time.perf_counter() - t_gen_start
    if not ok:
        print("❌ Failed to generate synthetic test video.")
        sys.exit(1)
    print(f"✅ Generated '{sample_video}' ({get_video_duration(sample_video):.2f}s) in {t_gen:.2f}s")

    print("\n2. Defining 5 realistic movie scene segments for Stage 1-4...")
    segments = [
        {"start": 0.0, "end": 4.0, "text": "Dramatic opening scene cut!", "source_clip_id": "clip_hero", "has_logo": False, "has_hard_sub": False},
        {"start": 4.0, "end": 9.0, "text": "Ordinary conversation scene with long text description of dialogue", "source_clip_id": "clip_dialogue", "has_logo": False, "has_hard_sub": False},
        {"start": 9.0, "end": 13.0, "text": "High stakes climax action shot!", "source_clip_id": "clip_hero", "has_logo": False, "has_hard_sub": False},
        {"start": 13.0, "end": 17.0, "text": "Subtle emotional reaction shot", "source_clip_id": "clip_reaction", "has_logo": False, "has_hard_sub": False},
        {"start": 17.0, "end": 20.0, "text": "Final resolution scene!", "source_clip_id": "clip_ending", "has_logo": False, "has_hard_sub": False},
    ]

    engine = AutoRecapEngine(AutoRecapConfig(editing_style="Balanced", max_zoom_percent=110.0))

    print("\n3. Executing Stage 1 to 4 Pipeline & Benchmark Metrics...")
    decisions, metrics = benchmark_auto_recap_pipeline(engine, segments, has_voiceover=False)

    print("\n4. Executing Stage 5 Single-Pass FFmpeg Complex Filtergraph Render...")
    t_render_start = time.perf_counter()
    render_ok = engine.render_recap_video_1pass(sample_video, output_recap, decisions)
    t_render = time.perf_counter() - t_render_start
    metrics.render_time_sec = t_render

    if not render_ok:
        print("❌ Stage 5 Render Failed.")
        sys.exit(1)

    out_dur = get_video_duration(output_recap)
    print(f"✅ Rendered '{output_recap}' ({out_dur:.2f}s) in {t_render:.2f}s!")

    print("\n================================================================================")
    print(metrics.generate_ascii_report())
    print("================================================================================")

    print("\n5. Verification Checks:")
    print(f"  • Output file exists: {os.path.exists(output_recap)}")
    print(f"  • Output size: {os.path.getsize(output_recap) / 1024:.1f} KB")
    print(f"  • Duration ratio: {out_dur:.2f}s / {get_video_duration(sample_video):.2f}s")
    print(f"  • Speed ratio: {get_video_duration(sample_video) / t_render:.2f}x real-time")

    if os.path.exists(output_recap) and out_dur > 0:
        print("\n🎉 SELF-TEST PASSED SUCCESSFULLY!")
    else:
        print("\n❌ Self-test failed verification checks.")
        sys.exit(1)


if __name__ == "__main__":
    main()
