"""
config_parser.py - Đọc và validate file config.json.
"""

import json
import os
import sys


def load_config(config_path: str) -> dict:
    """Đọc file config.json và trả về dict."""
    if not os.path.exists(config_path):
        print(f"[ERROR] Không tìm thấy file config: {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    validate_config(config, os.path.dirname(config_path))
    return config


def validate_config(config: dict, base_dir: str):
    """Validate các trường bắt buộc trong config."""

    # --- Trường cấp cao ---
    required_top = ["project_name", "resolution", "fps", "scenes"]
    for field in required_top:
        if field not in config:
            _error(f"Thiếu trường bắt buộc: '{field}'")

    # Validate resolution format
    res = config["resolution"]
    if "x" not in res.lower():
        _error(f"Resolution không đúng format 'WIDTHxHEIGHT': {res}")

    # --- Audio settings ---
    audio = config.get("audio_settings", {})
    if audio:
        bgm = audio.get("bgm_file", "")
        if bgm:
            bgm_path = os.path.join(base_dir, bgm) if not os.path.isabs(bgm) else bgm
            if not os.path.exists(bgm_path):
                _error(f"Không tìm thấy file BGM: {bgm_path}")

    # --- Scenes ---
    scenes = config["scenes"]
    if not scenes:
        _error("Danh sách scenes rỗng!")

    for scene in scenes:
        _validate_scene(scene, base_dir)

    print(f"[OK] Config hợp lệ: {len(scenes)} scene(s)")


def _validate_scene(scene: dict, base_dir: str):
    """Validate 1 scene."""
    scene_id = scene.get("scene_id", "?")

    # Trường bắt buộc
    for field in ["scene_id", "mode", "visuals", "text", "tts_voice"]:
        if field not in scene:
            _error(f"Scene {scene_id}: thiếu trường '{field}'")

    mode = scene["mode"]
    if mode not in ("image_sequence", "video_single"):
        _error(f"Scene {scene_id}: mode không hợp lệ '{mode}' (chỉ chấp nhận: image_sequence, video_single)")

    visuals = scene["visuals"]
    if not visuals:
        _error(f"Scene {scene_id}: danh sách visuals rỗng!")

    for v in visuals:
        file_path = v.get("file", "")
        if not file_path:
            _error(f"Scene {scene_id}: visual thiếu trường 'file'")

        full_path = os.path.join(base_dir, file_path) if not os.path.isabs(file_path) else file_path
        if not os.path.exists(full_path):
            _error(f"Scene {scene_id}: không tìm thấy file visual: {full_path}")

        # image_sequence bắt buộc có duration
        if mode == "image_sequence" and "duration" not in v:
            _error(f"Scene {scene_id}: mode=image_sequence yêu cầu 'duration' cho mỗi ảnh")


def _error(msg: str):
    """In lỗi và thoát."""
    print(f"[CONFIG ERROR] {msg}")
    sys.exit(1)
