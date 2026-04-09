"""
utils.py - Hàm tiện ích dùng chung cho toàn bộ dự án.
"""

import os
import subprocess
import json
import shutil
import re

# Timeout cho ffprobe (30 giây là đủ vì chỉ đọc metadata)
FFPROBE_TIMEOUT = 30


def get_media_duration(file_path: str) -> float:
    """Lấy thời lượng (giây) của file media (audio/video) bằng ffprobe."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Media file không tồn tại: {file_path}")

    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        file_path
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True,
            timeout=FFPROBE_TIMEOUT
        )
        info = json.loads(result.stdout)
        return float(info["format"]["duration"])
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe lỗi khi đọc '{file_path}': {e.stderr[:300]}")
    except (json.JSONDecodeError, KeyError) as e:
        raise RuntimeError(f"Không parse được duration từ '{file_path}': {e}")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"ffprobe timeout khi đọc '{file_path}'")


def get_video_resolution(file_path: str) -> tuple[int, int]:
    """Lấy width x height của file video bằng ffprobe."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Video file không tồn tại: {file_path}")

    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-select_streams", "v:0",
        file_path
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True,
            timeout=FFPROBE_TIMEOUT
        )
        info = json.loads(result.stdout)
        streams = info.get("streams", [])
        if not streams:
            raise RuntimeError(f"Không tìm thấy video stream trong '{file_path}'")
        stream = streams[0]
        return int(stream["width"]), int(stream["height"])
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe lỗi khi đọc '{file_path}': {e.stderr[:300]}")
    except (json.JSONDecodeError, KeyError) as e:
        raise RuntimeError(f"Không parse được resolution từ '{file_path}': {e}")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"ffprobe timeout khi đọc '{file_path}'")


def parse_resolution(resolution_str: str) -> tuple[int, int]:
    """Parse chuỗi resolution '1080x1920' thành (width, height)."""
    if not re.match(r'^\d+x\d+$', resolution_str.lower()):
        raise ValueError(
            f"Resolution không đúng format 'WIDTHxHEIGHT': '{resolution_str}'"
        )
    parts = resolution_str.lower().split("x")
    w, h = int(parts[0]), int(parts[1])
    if w <= 0 or h <= 0:
        raise ValueError(f"Resolution phải > 0, nhận được: {w}x{h}")
    return w, h


def ensure_dir(path: str):
    """Tạo thư mục nếu chưa tồn tại."""
    os.makedirs(path, exist_ok=True)


def clean_dir(path: str):
    """Xóa sạch thư mục rồi tạo lại."""
    if os.path.exists(path):
        try:
            shutil.rmtree(path)
        except PermissionError:
            print(f"  [WARN] Không thể xóa thư mục '{path}': permission denied")
    os.makedirs(path, exist_ok=True)


def run_ffmpeg(args: list[str], description: str = ""):
    """Chạy lệnh ffmpeg với error handling (không giới hạn thời gian)."""
    cmd = ["ffmpeg", "-y"] + args
    print(f"  [FFmpeg] {description}")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True
        )
    except FileNotFoundError:
        raise RuntimeError(
            "FFmpeg không tìm thấy trong PATH. Hãy cài FFmpeg trước."
        )
    if result.returncode != 0:
        print(f"  [FFmpeg ERROR] {result.stderr[-500:]}")
        raise RuntimeError(f"FFmpeg failed: {description}\n{result.stderr[-500:]}")
    return result


def escape_text_for_ffmpeg(text: str) -> str:
    """Escape ký tự đặc biệt cho bộ lọc drawtext của FFmpeg.

    FFmpeg drawtext cần escape các ký tự: \\ : ' [ ] ; %
    Thứ tự escape quan trọng: backslash phải escape trước tiên.
    """
    # Escape backslash trước tiên (\ -> \\)
    text = text.replace("\\", "\\\\")
    # Escape dấu nháy đơn (' -> '\\'')
    text = text.replace("'", "'\\''")
    # Escape dấu hai chấm
    text = text.replace(":", "\\:")
    # Escape dấu ngoặc vuông
    text = text.replace("[", "\\[")
    text = text.replace("]", "\\]")
    # Escape dấu chấm phẩy
    text = text.replace(";", "\\;")
    # Escape dấu phần trăm (% là ký tự đặc biệt trong drawtext, dùng cho text expansion)
    text = text.replace("%", "%%")
    return text


def has_audio_stream(file_path: str) -> bool:
    """Kiểm tra file media có chứa audio stream hay không."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0",
             file_path],
            capture_output=True, text=True, timeout=FFPROBE_TIMEOUT
        )
        return "audio" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def validate_file_in_project(file_path: str, base_dir: str) -> str:
    """Validate file path nằm trong project dir, trả về absolute path.

    Ngăn chặn path traversal (../../etc/passwd).
    """
    if os.path.isabs(file_path):
        full_path = os.path.normpath(file_path)
    else:
        full_path = os.path.normpath(os.path.join(base_dir, file_path))

    abs_base = os.path.normpath(os.path.abspath(base_dir))
    abs_full = os.path.normpath(os.path.abspath(full_path))

    if not abs_full.startswith(abs_base + os.sep) and abs_full != abs_base:
        raise ValueError(
            f"File path không hợp lệ (ngoài project dir): {file_path}"
        )
    return full_path
