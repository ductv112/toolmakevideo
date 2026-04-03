"""
utils.py - Hàm tiện ích dùng chung cho toàn bộ dự án.
"""

import os
import subprocess
import json
import shutil


def get_media_duration(file_path: str) -> float:
    """Lấy thời lượng (giây) của file media (audio/video) bằng ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        file_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)
    return float(info["format"]["duration"])


def get_video_resolution(file_path: str) -> tuple[int, int]:
    """Lấy width x height của file video bằng ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-select_streams", "v:0",
        file_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)
    stream = info["streams"][0]
    return int(stream["width"]), int(stream["height"])


def parse_resolution(resolution_str: str) -> tuple[int, int]:
    """Parse chuỗi resolution '1080x1920' thành (width, height)."""
    parts = resolution_str.lower().split("x")
    return int(parts[0]), int(parts[1])


def ensure_dir(path: str):
    """Tạo thư mục nếu chưa tồn tại."""
    os.makedirs(path, exist_ok=True)


def clean_dir(path: str):
    """Xóa sạch thư mục rồi tạo lại."""
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)


def run_ffmpeg(args: list[str], description: str = ""):
    """Chạy lệnh ffmpeg với error handling."""
    cmd = ["ffmpeg", "-y"] + args
    print(f"  [FFmpeg] {description}")
    result = subprocess.run(
        cmd, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  [FFmpeg ERROR] {result.stderr[-500:]}")
        raise RuntimeError(f"FFmpeg failed: {description}\n{result.stderr[-500:]}")
    return result


def escape_text_for_ffmpeg(text: str) -> str:
    """Escape ký tự đặc biệt cho bộ lọc drawtext của FFmpeg.

    FFmpeg drawtext cần escape các ký tự: ' : \ [ ] ; ,
    """
    # Escape backslash trước tiên
    text = text.replace("\\", "\\\\\\\\")
    # Escape dấu nháy đơn
    text = text.replace("'", "'\\\\\\''")
    # Escape dấu hai chấm
    text = text.replace(":", "\\:")
    # Escape dấu ngoặc vuông
    text = text.replace("[", "\\[")
    text = text.replace("]", "\\]")
    # Escape dấu chấm phẩy
    text = text.replace(";", "\\;")
    return text
