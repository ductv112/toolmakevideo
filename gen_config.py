"""
gen_config.py - Tự sinh config.json từ file kịch bản (cho video ngang 16:9).

Đọc file kịch bản (dạng kichban.txt), tự động trích xuất Text + TTS
cho mỗi cảnh, ghép với clip1.mp4, clip2.mp4... và sinh ra config.json
đúng format config_ghep_video_ngang.json.

Usage:
    # Mặc định (1920x1080, giọng nữ)
    python gen_config.py Video/Planet404/kichban.txt

    # Đổi giọng nam
    python gen_config.py Video/Planet404/kichban.txt --voice vi-VN-NamMinhNeural

    # Chỉ định tên project
    python gen_config.py Video/Planet404/kichban.txt --name planet_404_ep1

    # Không cần watermark
    python gen_config.py Video/Planet404/kichban.txt --no-watermark
"""

import argparse
import json
import os
import re
import sys

# Fix encoding cho Windows console
sys.stdout.reconfigure(encoding="utf-8")


def parse_kichban(file_path: str) -> list[dict]:
    """Parse file kịch bản, trích xuất Text + TTS cho mỗi cảnh.

    Hỗ trợ format:
        Cảnh X: Tiêu đề
        Prompt video: ... (bỏ qua)
        Text: Nội dung phụ đề
        TTS: Nội dung giọng đọc
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    scene_pattern = re.compile(
        r'Cảnh\s+(\d+)\s*:(.*?)(?=Cảnh\s+\d+\s*:|$)',
        re.DOTALL | re.IGNORECASE
    )

    scenes = []
    for match in scene_pattern.finditer(content):
        scene_num = int(match.group(1))
        block = match.group(2)

        text_match = re.search(r'^Text:\s*(.+)$', block, re.MULTILINE)
        text = text_match.group(1).strip() if text_match else ""

        tts_match = re.search(r'^TTS:\s*(.+)$', block, re.MULTILINE)
        tts = tts_match.group(1).strip() if tts_match else ""

        if not text and not tts:
            print(f"  [WARN] Cảnh {scene_num}: không tìm thấy Text hoặc TTS, bỏ qua")
            continue

        scenes.append({
            "scene_num": scene_num,
            "text": text,
            "tts": tts
        })

    return scenes


def write_config(
    scenes: list[dict],
    output_path: str,
    project_name: str,
    resolution: str,
    fps: int,
    voice: str,
    bgm_file: str,
    bgm_volume: float,
    duck_bgm: bool,
    clip_prefix: str,
    watermark_file: str,
    watermark_margin: int
):
    """Ghi config.json theo đúng format config_ghep_video_ngang.json.

    Phần header (project_name, resolution, audio_settings...) dùng indent đẹp.
    Phần scenes ghi nén gọn mỗi scene 1 dòng.
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("{\n")
        f.write(f'  "project_name": "{project_name}",\n')
        f.write(f'  "resolution": "{resolution}",\n')
        f.write(f'  "fps": {fps},\n')

        # audio_settings
        f.write(f'  "audio_settings": {{\n')
        f.write(f'    "bgm_file": "{bgm_file}",\n')
        f.write(f'    "bgm_volume": {bgm_volume},\n')
        f.write(f'    "voice_volume": 1.0,\n')
        f.write(f'    "duck_bgm": {"true" if duck_bgm else "false"}\n')
        f.write(f'  }},\n')

        # watermark (nếu có)
        if watermark_file:
            f.write(f'  "watermark": {{\n')
            f.write(f'    "file": "{watermark_file}",\n')
            f.write(f'    "margin": {watermark_margin}\n')
            f.write(f'  }},\n')

        # scenes - mỗi scene 1 dòng gọn
        f.write(f'  "scenes": [\n')
        for i, s in enumerate(scenes):
            scene_id = i + 1
            # Escape dấu nháy kép trong text và tts
            text = s["text"].replace('"', '\\"')
            tts = s["tts"].replace('"', '\\"')

            line = (
                f'    {{"scene_id": {scene_id}, '
                f'"mode": "video_single", '
                f'"visuals": [{{"file": "{clip_prefix}{scene_id}.mp4"}}], '
                f'"text": "{text}", '
                f'"tts": "{tts}", '
                f'"tts_voice": "{voice}"}}'
            )

            if i < len(scenes) - 1:
                line += ","
            f.write(line + "\n")

        f.write(f'  ]\n')
        f.write("}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Tự sinh config.json từ file kịch bản (video ngang 16:9)"
    )
    parser.add_argument(
        "kichban",
        help="Đường dẫn file kịch bản (vd: Video/Planet404/kichban.txt)"
    )
    parser.add_argument(
        "--name", "-n",
        default="",
        help="Tên project (mặc định: lấy từ tên thư mục)"
    )
    parser.add_argument(
        "--fps",
        type=int, default=30,
        help="FPS (mặc định: 30)"
    )
    parser.add_argument(
        "--voice", "-v",
        default="vi-VN-HoaiMyNeural",
        help="Giọng đọc TTS (mặc định: vi-VN-HoaiMyNeural)"
    )
    parser.add_argument(
        "--bgm",
        default="nhacnen.mp3",
        help="Tên file nhạc nền (mặc định: nhacnen.mp3)"
    )
    parser.add_argument(
        "--bgm-volume",
        type=float, default=0.5,
        help="Âm lượng nhạc nền 0.0-1.0 (mặc định: 0.5)"
    )
    parser.add_argument(
        "--no-duck",
        action="store_true",
        help="Tắt ducking (mặc định: bật)"
    )
    parser.add_argument(
        "--clip-prefix",
        default="clip",
        help="Prefix tên file video (mặc định: clip -> clip1.mp4, clip2.mp4...)"
    )
    parser.add_argument(
        "--watermark", "-w",
        default="DucTV.jpg",
        help="Tên file watermark (mặc định: DucTV.jpg)"
    )
    parser.add_argument(
        "--watermark-margin",
        type=int, default=10,
        help="Margin watermark (mặc định: 10)"
    )
    parser.add_argument(
        "--no-watermark",
        action="store_true",
        help="Không chèn watermark"
    )
    parser.add_argument(
        "--output", "-o",
        default="",
        help="Đường dẫn file config.json đầu ra (mặc định: cùng thư mục kịch bản)"
    )
    args = parser.parse_args()

    # Xác định đường dẫn
    kichban_path = os.path.abspath(args.kichban)
    if not os.path.exists(kichban_path):
        print(f"[ERROR] Không tìm thấy file kịch bản: {kichban_path}")
        return

    project_dir = os.path.dirname(kichban_path)

    # Tên project
    if args.name:
        project_name = args.name
    else:
        project_name = os.path.basename(project_dir).lower().replace(" ", "_")

    # Parse kịch bản
    print(f"\n[1/2] Đang parse kịch bản: {kichban_path}")
    scenes = parse_kichban(kichban_path)

    if not scenes:
        print("[ERROR] Không tìm thấy cảnh nào trong file kịch bản!")
        return

    print(f"  -> Tìm thấy {len(scenes)} cảnh")

    # Ghi file
    if args.output:
        output_path = os.path.abspath(args.output)
    else:
        output_path = os.path.join(project_dir, "config.json")

    print(f"[2/2] Đang ghi config: {output_path}")
    write_config(
        scenes=scenes,
        output_path=output_path,
        project_name=project_name,
        resolution="1920x1080",
        fps=args.fps,
        voice=args.voice,
        bgm_file=args.bgm,
        bgm_volume=args.bgm_volume,
        duck_bgm=not args.no_duck,
        clip_prefix=args.clip_prefix,
        watermark_file="" if args.no_watermark else args.watermark,
        watermark_margin=args.watermark_margin
    )

    print(f"\n{'='*50}")
    print(f"  XONG!")
    print(f"  Số cảnh: {len(scenes)}")
    print(f"  Resolution: 1920x1080")
    print(f"  Giọng đọc: {args.voice}")
    print(f"  Output: {output_path}")
    print(f"{'='*50}")

    print(f"\n  File cần chuẩn bị trong {project_dir}:")
    print(f"    - {args.clip_prefix}1.mp4 đến {args.clip_prefix}{len(scenes)}.mp4")
    print(f"    - {args.bgm} (nhạc nền)")
    if not args.no_watermark:
        print(f"    - {args.watermark} (watermark)")


if __name__ == "__main__":
    main()
