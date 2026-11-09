import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "200"))
    max_video_frames: int = int(os.getenv("MAX_VIDEO_FRAMES", "80"))

def get_settings():
    return Settings()
