"""Shared ZeroTTS metadata used by the UI and synthesis runtime."""

ZEROTTS_MODEL_ID = "zeroweight-ai/ZeroTTS"

ZEROTTS_VOICES = (
    ("maichi", "Mai Chi", "female", ("young", "gentle", "storytelling")),
    ("baotrang", "Bảo Trang", "female", ("mature", "clear", "news")),
    ("kimoanh", "Kim Oanh", "female", ("warm", "emotional", "storytelling")),
    ("hamy", "Hà My", "female", ("young", "expressive", "animation")),
    ("giahuy", "Gia Huy", "male", ("young", "warm", "storytelling")),
    ("huuduc", "Hữu Đức", "male", ("deep", "calm", "storytelling")),
    ("quangminh", "Quang Minh", "male", ("young", "clear", "news")),
    ("tiendat", "Tiến Đạt", "male", ("young", "lively", "commentary")),
)


def catalog_entries() -> list[dict]:
    return [
        {
            "id": f"zerotts:{voice_id}",
            "name": f"{display_name} (ZeroTTS)",
            "provider": "zerotts",
            "provider_voice": voice_id,
            "language": "vi",
            "gender": gender,
            "tier": "free",
            "preview_video_url": "",
            "preview_video_path": "",
            "preview_audio_url": "",
            "preview_audio_path": "",
            "enabled": True,
            "tags": ["local", "zerotts", *tags],
        }
        for voice_id, display_name, gender, tags in ZEROTTS_VOICES
    ]
