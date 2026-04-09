"""
tts_generator.py - Tạo file TTS bằng thư viện edge-tts (miễn phí).
"""

import asyncio
import os
import tempfile
import edge_tts

# Giới hạn ký tự cho edge-tts (an toàn)
MAX_TTS_TEXT_LENGTH = 5000


async def _generate_tts(text: str, voice: str, output_path: str):
    """Gọi edge-tts async để tạo file mp3."""
    try:
        communicate = edge_tts.Communicate(text, voice)
        # Ghi vào file tạm trước, rồi rename (atomic)
        temp_fd, temp_path = tempfile.mkstemp(suffix=".mp3", dir=os.path.dirname(output_path))
        os.close(temp_fd)
        try:
            await communicate.save(temp_path)
            # Atomic rename
            if os.path.exists(output_path):
                os.remove(output_path)
            os.rename(temp_path, output_path)
        except Exception:
            # Dọn file tạm nếu lỗi
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise
    except Exception as e:
        raise RuntimeError(
            f"TTS generation thất bại (voice='{voice}'): {e}"
        )


def generate_tts_for_scene(
    text: str,
    voice: str,
    output_path: str
) -> str:
    """Tạo file TTS cho 1 scene.

    Args:
        text: Nội dung text cần đọc.
        voice: Tên giọng đọc (vd: vi-VN-HoaiMyNeural).
        output_path: Đường dẫn file mp3 đầu ra.

    Returns:
        Đường dẫn file TTS đã tạo.
    """
    # Validate text
    if not text or not text.strip():
        raise ValueError("Text TTS không được rỗng!")

    if len(text) > MAX_TTS_TEXT_LENGTH:
        print(f"  [TTS WARN] Text quá dài ({len(text)} ký tự), cắt còn {MAX_TTS_TEXT_LENGTH}")
        text = text[:MAX_TTS_TEXT_LENGTH]

    # Validate voice
    if not voice or not voice.strip():
        raise ValueError("Tên giọng đọc TTS không được rỗng!")

    print(f"  [TTS] Đang tạo giọng đọc: {voice}")
    print(f"  [TTS] Text ({len(text)} chars): {text[:60]}...")

    asyncio.run(_generate_tts(text, voice, output_path))

    if not os.path.exists(output_path):
        raise RuntimeError(f"Không tạo được file TTS: {output_path}")

    file_size = os.path.getsize(output_path)
    if file_size == 0:
        os.remove(output_path)
        raise RuntimeError(f"File TTS rỗng (0 bytes), có thể text không hợp lệ: {output_path}")

    print(f"  [TTS] OK -> {output_path} ({file_size / 1024:.1f} KB)")
    return output_path
