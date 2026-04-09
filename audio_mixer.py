"""
audio_mixer.py - Xử lý nhạc nền (BGM) và hiệu ứng ducking.

Chức năng:
- Ốp BGM xuyên suốt video
- Tự động loop BGM nếu video dài hơn nhạc
- Ducking: dìm nhạc nền khi có giọng đọc TTS
"""

import math
import os
from utils import run_ffmpeg, get_media_duration


def apply_bgm(
    video_path: str,
    bgm_file: str,
    output_path: str,
    duck_bgm: bool = False,
    bgm_volume: float = 0.15,
    voice_volume: float = 1.0
):
    """Ốp nhạc nền (BGM) vào video đã có TTS audio.

    Args:
        video_path: Video đã concat (có audio TTS).
        bgm_file: Đường dẫn file nhạc nền.
        output_path: File MP4 đầu ra cuối cùng.
        duck_bgm: True = dìm BGM khi có giọng đọc.
        bgm_volume: Âm lượng BGM (0.0 - 1.0), mặc định 0.15.
        voice_volume: Âm lượng giọng đọc TTS (0.0 - 1.0).
    """
    # Validate input files
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file không tồn tại: {video_path}")
    if not os.path.exists(bgm_file):
        raise FileNotFoundError(f"BGM file không tồn tại: {bgm_file}")

    # Validate volume ranges
    if not (0 < bgm_volume <= 1):
        raise ValueError(f"bgm_volume phải trong khoảng (0, 1], nhận được: {bgm_volume}")
    if not (0 < voice_volume <= 1):
        raise ValueError(f"voice_volume phải trong khoảng (0, 1], nhận được: {voice_volume}")

    video_duration = get_media_duration(video_path)
    bgm_duration = get_media_duration(bgm_file)

    # Tính số lần loop cần thiết thay vì loop vô hạn
    loop_count = max(0, math.ceil(video_duration / bgm_duration) - 1)

    print(f"  [BGM] Video: {video_duration:.1f}s | BGM: {bgm_duration:.1f}s | Loop: {loop_count}x")
    print(f"  [BGM] Ducking: {'ON' if duck_bgm else 'OFF'}")

    if duck_bgm:
        _apply_bgm_with_ducking(
            video_path, bgm_file, output_path,
            video_duration, bgm_volume, voice_volume, loop_count
        )
    else:
        _apply_bgm_simple(
            video_path, bgm_file, output_path,
            video_duration, bgm_volume, voice_volume, loop_count
        )


def _apply_bgm_simple(
    video_path: str,
    bgm_file: str,
    output_path: str,
    video_duration: float,
    bgm_volume: float,
    voice_volume: float,
    loop_count: int
):
    """Ốp BGM đơn giản (không ducking).

    Loop BGM đúng số lần cần thiết, rồi cắt bằng -t.
    Audio filter: mix giọng đọc (volume theo config) + BGM (volume thấp).
    """
    # Filter: giảm volume BGM, trộn 2 track audio
    filter_complex = (
        # Audio từ video (TTS) - volume theo config
        f"[0:a]volume={voice_volume}[voice];"
        # BGM - giảm volume
        f"[1:a]volume={bgm_volume}[bgm];"
        # Trộn 2 audio track thành 1
        f"[voice][bgm]amix=inputs=2:duration=first:dropout_transition=0[aout]"
    )

    run_ffmpeg([
        "-i", video_path,
        "-stream_loop", str(loop_count),  # Loop BGM đúng số lần cần
        "-i", bgm_file,
        "-filter_complex", filter_complex,
        "-map", "0:v:0",            # Lấy video từ input 0
        "-map", "[aout]",           # Lấy audio đã trộn
        "-t", str(video_duration),  # Cắt đúng thời lượng video
        "-c:v", "copy",             # Không re-encode video (nhanh!)
        "-c:a", "aac", "-b:a", "192k",
        output_path
    ], "Ốp BGM (không ducking)")


def _apply_bgm_with_ducking(
    video_path: str,
    bgm_file: str,
    output_path: str,
    video_duration: float,
    bgm_volume: float,
    voice_volume: float,
    loop_count: int
):
    """Ốp BGM có ducking - tự động dìm nhạc khi có giọng đọc.

    Dùng FFmpeg sidechaincompress:
    - Khi phát hiện giọng đọc (TTS), tự động giảm volume BGM.
    - Khi giọng đọc im, BGM trở lại volume bình thường.

    Tham số sidechaincompress:
    - threshold=0.03: ngưỡng phát hiện giọng đọc
    - ratio=6: tỉ lệ nén (giảm BGM khi có giọng)
    - attack=100: thời gian bắt đầu dìm (100ms, phản ứng nhanh)
    - release=800: thời gian phục hồi (800ms, mượt)
    """
    filter_complex = (
        # Tách giọng đọc TTS
        f"[0:a]volume={voice_volume},asplit=2[voice][voice_sc];"
        # BGM với volume cơ bản
        f"[1:a]volume={bgm_volume}[bgm_raw];"
        # Áp dụng sidechain compress: dìm BGM khi voice phát
        f"[bgm_raw][voice_sc]sidechaincompress="
        f"threshold=0.03:ratio=6:attack=100:release=800[bgm_ducked];"
        # Trộn voice + BGM đã ducked
        f"[voice][bgm_ducked]amix=inputs=2:duration=first:dropout_transition=0[aout]"
    )

    run_ffmpeg([
        "-i", video_path,
        "-stream_loop", str(loop_count),  # Loop BGM đúng số lần cần
        "-i", bgm_file,
        "-filter_complex", filter_complex,
        "-map", "0:v:0",
        "-map", "[aout]",
        "-t", str(video_duration),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        output_path
    ], "Ốp BGM (có ducking)")
