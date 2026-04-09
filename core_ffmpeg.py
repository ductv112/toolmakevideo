"""
core_ffmpeg.py - Module cốt lõi xử lý FFmpeg.

Chịu trách nhiệm:
1. Render từng Scene thành file temp_scene_X.mp4
2. Concat tất cả scene thành video hoàn chỉnh

Tuân thủ nguyên tắc "Chia để trị":
- Mỗi scene được render độc lập thành 1 file mp4
- Sau đó mới dùng Concat Demuxer ghép lại
"""

import os
import platform
from utils import (
    run_ffmpeg, parse_resolution, get_media_duration,
    escape_text_for_ffmpeg, validate_file_in_project
)


# ===========================================================================
# 1. RENDER SCENE - CHẾ ĐỘ IMAGE_SEQUENCE (Trường hợp A)
# ===========================================================================

def render_image_sequence_scene(
    scene: dict,
    target_w: int,
    target_h: int,
    fps: int,
    tts_path: str,
    output_path: str,
    base_dir: str,
    font_path: str = ""
):
    """Render 1 scene chế độ nối ảnh.

    Logic:
    1. Với mỗi ảnh trong visuals[], tạo 1 clip ngắn (ảnh tĩnh -> video câm)
       đúng duration chỉ định, ép vào khung hình target.
    2. Nối tất cả clip ngắn thành 1 video nền câm (silent_scene.mp4).
    3. Ốp TTS audio + drawtext lên video câm đó -> temp_scene_X.mp4.
       Luật 2: thời lượng = thời lượng video nền. TTS bị cắt nếu dài hơn.
    """
    temp_dir = os.path.dirname(output_path)
    scene_id = scene["scene_id"]
    visuals = scene["visuals"]
    text = scene.get("text", "")

    # --- Bước 1: Tạo clip câm cho từng ảnh ---
    if not visuals:
        raise ValueError(f"Scene {scene_id}: danh sách visuals rỗng!")

    clip_paths = []
    for i, v in enumerate(visuals):
        img_file = v["file"]
        img_path = validate_file_in_project(img_file, base_dir)
        if not os.path.exists(img_path):
            raise FileNotFoundError(
                f"Scene {scene_id}: không tìm thấy ảnh: {img_path}"
            )
        duration = v["duration"]
        clip_path = os.path.join(temp_dir, f"scene{scene_id}_clip{i}.mp4")
        clip_paths.append(clip_path)

        # Tạo video từ ảnh tĩnh:
        # -loop 1: lặp ảnh liên tục
        # -t duration: cắt đúng thời lượng
        # scale + pad: nhét ảnh vào giữa khung hình, bù viền đen (Luật 1)
        # -an: không có audio
        # -r fps: ép frame rate
        filter_str = (
            f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
            f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"setsar=1"
        )
        run_ffmpeg([
            "-loop", "1",
            "-i", img_path,
            "-vf", filter_str,
            "-t", str(duration),
            "-r", str(fps),
            "-c:v", "libx264", "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-an",
            clip_path
        ], f"Scene {scene_id} - ảnh {i+1}/{len(visuals)}")

    # --- Bước 2: Nối các clip ngắn thành 1 video câm ---
    silent_path = os.path.join(temp_dir, f"scene{scene_id}_silent.mp4")
    _concat_clips(clip_paths, silent_path, temp_dir, f"scene{scene_id}")

    # --- Bước 3: Ốp TTS + drawtext lên video câm ---
    _overlay_audio_and_text(
        video_path=silent_path,
        tts_path=tts_path,
        text=text,
        output_path=output_path,
        scene_id=scene_id,
        target_w=target_w,
        target_h=target_h,
        font_path=font_path
    )

    # Dọn file tạm của scene này
    for cp in clip_paths:
        _safe_remove(cp)
    _safe_remove(silent_path)


# ===========================================================================
# 2. RENDER SCENE - CHẾ ĐỘ VIDEO_SINGLE (Trường hợp B)
# ===========================================================================

def render_video_single_scene(
    scene: dict,
    target_w: int,
    target_h: int,
    fps: int,
    tts_path: str,
    output_path: str,
    base_dir: str,
    font_path: str = ""
):
    """Render 1 scene chế độ video đơn.

    Logic:
    1. Scale + pad video gốc vào khung hình target (Luật 1).
    2. Ốp TTS + drawtext lên, thời lượng lấy theo video gốc (Luật 2).
    """
    temp_dir = os.path.dirname(output_path)
    scene_id = scene["scene_id"]
    text = scene.get("text", "")

    if len(scene["visuals"]) > 1:
        print(f"  [WARN] Scene {scene_id}: mode=video_single chỉ dùng visual đầu tiên, "
              f"bỏ qua {len(scene['visuals']) - 1} visual còn lại")

    video_file = scene["visuals"][0]["file"]
    video_path = validate_file_in_project(video_file, base_dir)
    if not os.path.exists(video_path):
        raise FileNotFoundError(
            f"Scene {scene_id}: không tìm thấy video: {video_path}"
        )

    # Bước 1: Scale + pad video gốc, bỏ audio gốc
    scaled_path = os.path.join(temp_dir, f"scene{scene_id}_scaled.mp4")
    filter_str = (
        f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
        f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"setsar=1,fps={fps}"
    )
    run_ffmpeg([
        "-i", video_path,
        "-vf", filter_str,
        "-c:v", "libx264", "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-an",
        scaled_path
    ], f"Scene {scene_id} - scale video gốc")

    # Bước 2: Ốp TTS + drawtext
    _overlay_audio_and_text(
        video_path=scaled_path,
        tts_path=tts_path,
        text=text,
        output_path=output_path,
        scene_id=scene_id,
        target_w=target_w,
        target_h=target_h,
        font_path=font_path
    )

    _safe_remove(scaled_path)


# ===========================================================================
# 3. HÀM DÙNG CHUNG: ỐP AUDIO + TEXT LÊN VIDEO CÂM
# ===========================================================================

def _overlay_audio_and_text(
    video_path: str,
    tts_path: str,
    text: str,
    output_path: str,
    scene_id: int,
    target_w: int,
    target_h: int,
    font_path: str = ""
):
    """Ốp file TTS audio + drawtext lên video câm.

    Luật 2 được thực thi ở đây:
    - Thời lượng video nền là hệ quy chiếu tuyệt đối.
    - TTS ngắn hơn -> video chạy tiếp trong im lặng.
    - TTS dài hơn -> bị cắt cụt bằng -t (thời lượng video nền).
    - -shortest: dừng encode khi stream ngắn nhất kết thúc (video nền).
    """
    # Validate input files
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file không tồn tại: {video_path}")
    if not os.path.exists(tts_path):
        raise FileNotFoundError(f"TTS file không tồn tại: {tts_path}")

    video_duration = get_media_duration(video_path)

    # Build bộ lọc drawtext
    # Style: chữ trắng, viền vàng 3px, ở dưới cùng
    escaped_text = escape_text_for_ffmpeg(text)

    # Tính fontsize dựa trên chiều rộng video (khoảng 3.5% width)
    fontsize = max(24, int(target_w * 0.035))

    # Xây dựng drawtext filter
    if font_path and os.path.exists(font_path):
        # Escape đường dẫn font cho FFmpeg (backslash -> forward slash)
        safe_font = font_path.replace("\\", "/").replace(":", "\\:")
        font_opt = f"fontfile='{safe_font}'"
    else:
        # Fallback: chọn font theo OS
        if platform.system() == "Windows":
            font_opt = "font='Arial'"
        else:
            font_opt = "font='DejaVu Sans'"

    drawtext_filter = (
        f"drawtext={font_opt}:"
        f"text='{escaped_text}':"
        f"fontsize={fontsize}:"
        f"fontcolor=white:"
        f"borderw=3:bordercolor=yellow:"
        f"x=(w-text_w)/2:"          # Căn giữa ngang
        f"y=h-{fontsize + 80}:"     # Vị trí dưới cùng, cách mép ~80px
        f"line_spacing=8"
    )

    # Ốp audio TTS lên video, áp dụng Luật 2:
    # -t video_duration: cắt cụt audio nếu dài hơn video nền
    # -shortest: dừng khi stream ngắn nhất hết (safety net)
    run_ffmpeg([
        "-i", video_path,                          # Input 0: video câm
        "-i", tts_path,                             # Input 1: TTS audio
        "-vf", drawtext_filter,                     # Bộ lọc drawtext
        "-t", str(video_duration),                  # Luật 2: ép thời lượng = video nền
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",                                # Safety: dừng khi hết stream ngắn nhất
        "-map", "0:v:0",                            # Lấy video từ input 0
        "-map", "1:a:0",                            # Lấy audio từ input 1
        output_path
    ], f"Scene {scene_id} - ốp TTS + text")


# ===========================================================================
# 4. CONCAT TẤT CẢ SCENE THÀNH VIDEO HOÀN CHỈNH
# ===========================================================================

def concat_all_scenes(scene_paths: list[str], output_path: str, temp_dir: str):
    """Nối tất cả scene thành 1 video dài bằng Concat Demuxer.

    Concat Demuxer là cách an toàn nhất vì không re-encode,
    miễn là tất cả scene có cùng codec, resolution, fps.
    """
    if not scene_paths:
        raise ValueError("Danh sách scene rỗng, không thể concat!")

    # Tạo file danh sách cho concat demuxer
    list_file = os.path.join(temp_dir, "concat_list.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for path in scene_paths:
            # Dùng forward slash và escape dấu nháy cho FFmpeg
            safe_path = path.replace("\\", "/")
            f.write(f"file '{safe_path}'\n")

    run_ffmpeg([
        "-f", "concat",
        "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        output_path
    ], "Concat tất cả scene")

    _safe_remove(list_file)
    print(f"  [CONCAT] OK -> {output_path}")


# ===========================================================================
# 5. HÀM NỘI BỘ
# ===========================================================================

def _concat_clips(clip_paths: list[str], output_path: str, temp_dir: str, prefix: str):
    """Nối các clip ngắn trong 1 scene (dùng cho image_sequence)."""
    list_file = os.path.join(temp_dir, f"{prefix}_cliplist.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for path in clip_paths:
            safe_path = path.replace("\\", "/")
            f.write(f"file '{safe_path}'\n")

    run_ffmpeg([
        "-f", "concat",
        "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        output_path
    ], f"Nối clip ảnh -> {prefix}")

    _safe_remove(list_file)


def _safe_remove(path: str):
    """Xóa file nếu tồn tại, không raise lỗi."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
