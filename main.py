"""
main.py - Entry point CLI cho Tool sản xuất video tự động.

Usage:
    # Chạy toàn bộ video
    python main.py Video/SonTinhThuyTinh

    # Chỉ chạy lại scene 3 và 5 (bị lỗi hoặc cần sửa)
    python main.py Video/SonTinhThuyTinh --scene 3 5

    # Chỉ ghép lại video final (không render lại scene nào)
    python main.py Video/SonTinhThuyTinh --concat-only

    # Dọn rác sau khi hoàn thành (giữ file gốc + TTS + video final)
    python main.py Video/SonTinhThuyTinh --clean

    # Dọn sạch hoàn toàn (chỉ giữ file gốc)
    python main.py Video/SonTinhThuyTinh --clean-all

    # Chỉ định font chữ
    python main.py Video/SonTinhThuyTinh --font "C:/Windows/Fonts/arial.ttf"
"""

import argparse
import os
import shutil
import time

from config_parser import load_config
from tts_generator import generate_tts_for_scene
from core_ffmpeg import (
    render_image_sequence_scene,
    render_video_single_scene,
    concat_all_scenes,
    apply_watermark
)
from audio_mixer import apply_bgm
from utils import parse_resolution, ensure_dir


# Prefix các file tạm do tool tạo ra
TEMP_PREFIXES = ("temp_scene_", "scene", "concat_raw", "concat_list")
TTS_PREFIX = "tts_scene"


def main():
    parser = argparse.ArgumentParser(
        description="Tool tự động sản xuất video YouTube"
    )
    parser.add_argument(
        "project_dir",
        help="Đường dẫn thư mục dự án video (vd: Video/SonTinhThuyTinh)"
    )
    parser.add_argument(
        "--scene", "-s",
        nargs="+", type=int, default=[],
        help="Chỉ render lại scene cụ thể (vd: --scene 3 5)"
    )
    parser.add_argument(
        "--concat-only",
        action="store_true",
        help="Chỉ ghép lại video final từ các scene đã render, không render lại"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Dọn rác: xóa file tạm, giữ TTS + file gốc + video final"
    )
    parser.add_argument(
        "--clean-all",
        action="store_true",
        help="Dọn sạch: xóa tất cả file tạm + TTS, giữ file gốc + video final"
    )
    parser.add_argument(
        "--font", "-f",
        default="",
        help="Đường dẫn file font cho drawtext (mặc định: font hệ thống)"
    )
    args = parser.parse_args()

    # Xác định thư mục dự án (tuyệt đối, resolve từ thư mục hiện tại)
    project_dir = os.path.abspath(args.project_dir)

    if not os.path.isdir(project_dir):
        print(f"[ERROR] Không tìm thấy thư mục dự án: {project_dir}")
        return

    # Validate font path sớm
    if args.font and not os.path.exists(args.font):
        print(f"[WARN] Font file không tồn tại: {args.font}, sẽ dùng font mặc định")
        args.font = ""

    # === CHẾ ĐỘ DỌN RÁC ===
    if args.clean or args.clean_all:
        _clean_project(project_dir, keep_tts=not args.clean_all)
        return

    # === LOAD CONFIG ===
    config_path = os.path.join(project_dir, "config.json")
    config = load_config(config_path)

    project_name = config["project_name"]
    target_w, target_h = parse_resolution(config["resolution"])
    fps = config.get("fps", 30)

    # Validate FPS range
    if not (1 <= fps <= 120):
        print(f"[ERROR] FPS phải trong khoảng 1-120, nhận được: {fps}")
        return
    scenes = config["scenes"]
    total_scenes = len(scenes)

    # Xác định scene nào cần render
    if args.scene:
        scenes_to_render = set(args.scene)
    elif args.concat_only:
        scenes_to_render = set()  # Không render scene nào
    else:
        scenes_to_render = set(s["scene_id"] for s in scenes)  # Render tất cả

    print(f"\n{'='*60}")
    print(f"  DỰ ÁN: {project_name}")
    print(f"  Thư mục: {project_dir}")
    print(f"  Resolution: {target_w}x{target_h} | FPS: {fps}")
    print(f"  Tổng scene: {total_scenes}")
    if args.concat_only:
        print(f"  Chế độ: CHỈ GHÉP LẠI VIDEO FINAL")
    elif args.scene:
        print(f"  Chế độ: RENDER LẠI SCENE {sorted(scenes_to_render)}")
    else:
        print(f"  Chế độ: RENDER TOÀN BỘ")
    print(f"{'='*60}\n")

    start_time = time.time()

    # ===== BƯỚC 1: Render từng Scene =====
    scene_paths = []

    for scene in scenes:
        scene_id = scene["scene_id"]
        scene_output = os.path.join(project_dir, f"temp_scene_{scene_id}.mp4")
        scene_paths.append(scene_output)

        # Nếu scene này không cần render -> kiểm tra file đã tồn tại
        if scene_id not in scenes_to_render:
            if os.path.exists(scene_output):
                print(f"  [SKIP] Scene {scene_id} - đã có sẵn")
                continue
            else:
                # File không tồn tại -> thêm vào danh sách render
                scenes_to_render.add(scene_id)
                print(f"  [WARN] Scene {scene_id} chưa có file, thêm vào danh sách render")

        print(f"\n--- SCENE {scene_id}/{total_scenes} ({scene['mode']}) ---")

        # 1a. Tạo TTS (skip nếu đã tồn tại)
        tts_path = os.path.join(project_dir, f"tts_scene{scene_id}.mp3")
        if os.path.exists(tts_path):
            print(f"  [TTS] Đã có sẵn, skip tải lại: {tts_path}")
        else:
            generate_tts_for_scene(
                text=scene.get("tts", scene["text"]),
                voice=scene["tts_voice"],
                output_path=tts_path
            )

        # 1b. Xóa file scene cũ (nếu render lại)
        if os.path.exists(scene_output):
            os.remove(scene_output)
            print(f"  [DEL] Xóa scene cũ: {scene_output}")

        # 1c. Render scene
        if scene["mode"] == "image_sequence":
            render_image_sequence_scene(
                scene=scene,
                target_w=target_w,
                target_h=target_h,
                fps=fps,
                tts_path=tts_path,
                output_path=scene_output,
                base_dir=project_dir,
                font_path=args.font
            )
        elif scene["mode"] == "video_single":
            render_video_single_scene(
                scene=scene,
                target_w=target_w,
                target_h=target_h,
                fps=fps,
                tts_path=tts_path,
                output_path=scene_output,
                base_dir=project_dir,
                font_path=args.font
            )

        print(f"  [OK] Scene {scene_id} hoàn thành!")

    # ===== BƯỚC 2: Concat tất cả scene =====
    # Validate tất cả scene đã render thành công
    missing_scenes = [p for p in scene_paths if not os.path.exists(p)]
    if missing_scenes:
        print(f"\n[ERROR] Các scene sau bị thiếu, không thể concat:")
        for p in missing_scenes:
            print(f"  - {os.path.basename(p)}")
        return

    print(f"\n--- CONCAT {len(scene_paths)} SCENE ---")
    concat_output = os.path.join(project_dir, "concat_raw.mp4")
    concat_all_scenes(scene_paths, concat_output, project_dir)

    # ===== BƯỚC 3: Ốp BGM (nếu có) =====
    audio_settings = config.get("audio_settings", {})
    bgm_file = audio_settings.get("bgm_file", "")
    final_output = os.path.join(project_dir, f"{project_name}.mp4")

    if bgm_file:
        bgm_path = os.path.join(project_dir, bgm_file) if not os.path.isabs(bgm_file) else bgm_file
        duck_bgm = audio_settings.get("duck_bgm", False)
        bgm_volume = audio_settings.get("bgm_volume", 0.15)
        voice_volume = audio_settings.get("voice_volume", 1.0)

        print(f"\n--- ỐP NHẠC NỀN ---")
        apply_bgm(
            video_path=concat_output,
            bgm_file=bgm_path,
            output_path=final_output,
            duck_bgm=duck_bgm,
            bgm_volume=bgm_volume,
            voice_volume=voice_volume
        )
    else:
        print("\n--- Không có BGM, xuất trực tiếp ---")
        shutil.copy2(concat_output, final_output)

    # Xóa file concat tạm
    if os.path.exists(concat_output):
        os.remove(concat_output)

    # ===== BƯỚC 4: Chèn Watermark/Logo (nếu có) =====
    watermark_cfg = config.get("watermark", {})
    wm_file = watermark_cfg.get("file", "") if isinstance(watermark_cfg, dict) else ""
    if wm_file:
        wm_path = os.path.join(project_dir, wm_file) if not os.path.isabs(wm_file) else wm_file
        if os.path.exists(wm_path):
            wm_margin = watermark_cfg.get("margin", 10)
            wm_height = watermark_cfg.get("height", 0)
            print(f"\n--- CHÈN WATERMARK ---")
            # Render watermark vào file tạm, rồi thay thế file final
            wm_temp = os.path.join(project_dir, "temp_watermark.mp4")
            apply_watermark(
                video_path=final_output,
                watermark_path=wm_path,
                output_path=wm_temp,
                margin=wm_margin,
                height=wm_height
            )
            os.replace(wm_temp, final_output)
        else:
            print(f"\n[WARN] Watermark file không tồn tại: {wm_path}, bỏ qua")

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"  HOÀN THÀNH!")
    print(f"  Output: {final_output}")
    print(f"  Thời gian: {elapsed:.1f}s")
    print(f"  Dọn rác: python main.py {args.project_dir} --clean")
    print(f"{'='*60}\n")


def _clean_project(project_dir: str, keep_tts: bool = True):
    """Dọn rác trong thư mục dự án.

    - Luôn giữ: file gốc (ảnh, video, nhạc, config.json) + video final
    - keep_tts=True (--clean): giữ file TTS để lần sau đỡ tải lại
    - keep_tts=False (--clean-all): xóa luôn TTS
    """
    removed = 0

    for f in os.listdir(project_dir):
        filepath = os.path.join(project_dir, f)
        if not os.path.isfile(filepath):
            continue

        # File tạm scene (temp_scene_*.mp4, scene*_clip*.mp4, scene*_silent.mp4...)
        if f.startswith(TEMP_PREFIXES):
            os.remove(filepath)
            print(f"  [DEL] {f}")
            removed += 1
            continue

        # File concat tạm
        if f in ("concat_raw.mp4", "concat_list.txt"):
            os.remove(filepath)
            print(f"  [DEL] {f}")
            removed += 1
            continue

        # File TTS
        if f.startswith(TTS_PREFIX) and f.endswith(".mp3"):
            if not keep_tts:
                os.remove(filepath)
                print(f"  [DEL] {f}")
                removed += 1
            else:
                print(f"  [KEEP] {f}")
            continue

    if removed == 0:
        print("  Không có rác để dọn!")
    else:
        print(f"\n  Đã xóa {removed} file tạm.")


if __name__ == "__main__":
    main()
