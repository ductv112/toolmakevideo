"""
audio_mixer.py - Xử lý nhạc nền (BGM) và hiệu ứng ducking.

Chức năng:
- Ốp BGM xuyên suốt video
- Tự động loop BGM nếu video dài hơn nhạc
- Ducking: dìm nhạc nền khi có giọng đọc TTS
"""

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
    video_duration = get_media_duration(video_path)
    bgm_duration = get_media_duration(bgm_file)

    print(f"  [BGM] Video: {video_duration:.1f}s | BGM: {bgm_duration:.1f}s")
    print(f"  [BGM] Ducking: {'ON' if duck_bgm else 'OFF'}")

    if duck_bgm:
        _apply_bgm_with_ducking(
            video_path, bgm_file, output_path,
            video_duration, bgm_volume, voice_volume
        )
    else:
        _apply_bgm_simple(
            video_path, bgm_file, output_path,
            video_duration, bgm_volume
        )


def _apply_bgm_simple(
    video_path: str,
    bgm_file: str,
    output_path: str,
    video_duration: float,
    bgm_volume: float
):
    """Ốp BGM đơn giản (không ducking).

    Dùng -stream_loop -1 để loop BGM vô hạn, rồi cắt bằng -t.
    Audio filter: mix giọng đọc (volume giữ nguyên) + BGM (volume thấp).
    """
    # Filter: giảm volume BGM, trộn 2 track audio
    filter_complex = (
        # Audio từ video (TTS) - giữ nguyên volume
        f"[0:a]volume={voice_volume}[voice];"
        # BGM - giảm volume
        f"[1:a]volume={bgm_volume}[bgm];"
        # Trộn 2 audio track thành 1
        f"[voice][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )

    run_ffmpeg([
        "-i", video_path,
        "-stream_loop", "-1",       # Loop BGM vô hạn
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
    voice_volume: float
):
    """Ốp BGM có ducking - tự động dìm nhạc khi có giọng đọc.

    Dùng FFmpeg sidechaincompress:
    - Khi phát hiện giọng đọc (TTS), tự động giảm volume BGM.
    - Khi giọng đọc im, BGM trở lại volume bình thường.

    Tham số sidechaincompress:
    - threshold=0.02: ngưỡng phát hiện giọng đọc (rất nhạy)
    - ratio=8: tỉ lệ nén (giảm BGM mạnh khi có giọng)
    - attack=200: thời gian bắt đầu dìm (200ms, mượt)
    - release=1000: thời gian phục hồi (1s, không bị giật)
    """
    filter_complex = (
        # Tách giọng đọc TTS
        f"[0:a]volume={voice_volume},asplit=2[voice][voice_sc];"
        # BGM với volume cơ bản
        f"[1:a]volume={bgm_volume}[bgm_raw];"
        # Áp dụng sidechain compress: dìm BGM khi voice phát
        f"[bgm_raw][voice_sc]sidechaincompress="
        f"threshold=0.02:ratio=8:attack=200:release=1000[bgm_ducked];"
        # Trộn voice + BGM đã ducked
        f"[voice][bgm_ducked]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )

    run_ffmpeg([
        "-i", video_path,
        "-stream_loop", "-1",
        "-i", bgm_file,
        "-filter_complex", filter_complex,
        "-map", "0:v:0",
        "-map", "[aout]",
        "-t", str(video_duration),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        output_path
    ], "Ốp BGM (có ducking)")
