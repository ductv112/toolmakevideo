"""
tts_generator.py - Tạo file TTS bằng thư viện edge-tts (miễn phí).
"""

import asyncio
import os
import edge_tts


async def _generate_tts(text: str, voice: str, output_path: str):
    """Gọi edge-tts async để tạo file mp3."""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)


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
    print(f"  [TTS] Đang tạo giọng đọc: {voice}")
    print(f"  [TTS] Text: {text[:60]}...")

    asyncio.run(_generate_tts(text, voice, output_path))

    if not os.path.exists(output_path):
        raise RuntimeError(f"Không tạo được file TTS: {output_path}")

    file_size = os.path.getsize(output_path)
    print(f"  [TTS] OK -> {output_path} ({file_size / 1024:.1f} KB)")
    return output_path
