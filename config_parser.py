"""
config_parser.py - Đọc và validate file config.json.
"""

import json
import os
import re
import sys


def load_config(config_path: str) -> dict:
    """Đọc file config.json và trả về dict."""
    if not os.path.exists(config_path):
        print(f"[ERROR] Không tìm thấy file config: {config_path}")
        sys.exit(1)

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[ERROR] File config JSON không hợp lệ: {e}")
        sys.exit(1)

    validate_config(config, os.path.dirname(config_path))
    return config


def validate_config(config: dict, base_dir: str):
    """Validate các trường bắt buộc trong config."""

    # --- Trường cấp cao ---
    required_top = ["project_name", "resolution", "fps", "scenes"]
    for field in required_top:
        if field not in config:
            _error(f"Thiếu trường bắt buộc: '{field}'")

    # Validate resolution format (chỉ chấp nhận WIDTHxHEIGHT, số nguyên dương)
    res = config["resolution"]
    if not re.match(r'^\d+x\d+$', res.lower()):
        _error(f"Resolution không đúng format 'WIDTHxHEIGHT': {res}")
    res_parts = res.lower().split("x")
    res_w, res_h = int(res_parts[0]), int(res_parts[1])
    if res_w <= 0 or res_h <= 0:
        _error(f"Resolution phải > 0: {res}")

    # Validate FPS
    fps = config.get("fps", 30)
    if not isinstance(fps, (int, float)) or not (1 <= fps <= 120):
        _error(f"FPS phải trong khoảng 1-120, nhận được: {fps}")

    # --- Audio settings ---
    audio = config.get("audio_settings", {})
    if audio:
        bgm = audio.get("bgm_file", "")
        if bgm:
            bgm_path = os.path.join(base_dir, bgm) if not os.path.isabs(bgm) else bgm
            if not os.path.exists(bgm_path):
                _error(f"Không tìm thấy file BGM: {bgm_path}")

        # Validate volume ranges
        bgm_vol = audio.get("bgm_volume", 0.15)
        if not isinstance(bgm_vol, (int, float)) or not (0 < bgm_vol <= 1):
            _error(f"bgm_volume phải trong khoảng (0, 1], nhận được: {bgm_vol}")

        voice_vol = audio.get("voice_volume", 1.0)
        if not isinstance(voice_vol, (int, float)) or not (0 < voice_vol <= 1):
            _error(f"voice_volume phải trong khoảng (0, 1], nhận được: {voice_vol}")

    # --- Scenes ---
    scenes = config["scenes"]
    if not scenes:
        _error("Danh sách scenes rỗng!")

    # Check scene_id trùng lặp
    scene_ids = set()
    for scene in scenes:
        sid = scene.get("scene_id")
        if sid in scene_ids:
            _error(f"scene_id bị trùng: {sid}")
        scene_ids.add(sid)
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
        _error(f"Scene {scene_id}: mode không hợp lệ '{mode}' "
               f"(chỉ chấp nhận: image_sequence, video_single)")

    # Validate tts_voice không rỗng
    tts_voice = scene.get("tts_voice", "")
    if not tts_voice or not tts_voice.strip():
        _error(f"Scene {scene_id}: tts_voice không được rỗng")

    # Validate text không rỗng
    text = scene.get("text", "")
    if not text or not text.strip():
        _error(f"Scene {scene_id}: text (phụ đề) không được rỗng")

    # Validate tts (giọng đọc) - nếu có thì không được rỗng
    if "tts" in scene:
        tts_text = scene.get("tts", "")
        if not tts_text or not tts_text.strip():
            _error(f"Scene {scene_id}: tts (giọng đọc) không được rỗng nếu đã khai báo")

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
        if mode == "image_sequence":
            if "duration" not in v:
                _error(f"Scene {scene_id}: mode=image_sequence yêu cầu 'duration' cho mỗi ảnh")
            dur = v["duration"]
            if not isinstance(dur, (int, float)) or dur <= 0:
                _error(f"Scene {scene_id}: duration phải > 0, nhận được: {dur}")


def _error(msg: str):
    """In lỗi và thoát."""
    print(f"[CONFIG ERROR] {msg}")
    sys.exit(1)
