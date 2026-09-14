import math
import shutil
from pathlib import Path
from .detectors import VisionDetectors
from .events import analyze_frames, summary
from .tracking import BallTracker
from .video import read_frames
from .render import render_video
from .store import save_json, load_json


def process_session(directory, config, model_dir, progress):
    directory = Path(directory)
    session = load_json(directory/"session.json")
    meta = session["video"]
    # Keep the previous analysis and its human review recoverable before replacing it.
    if session.get("status") == "ready":
        archive = directory/"history"/f"revision-{session.get('revision', 0)}"
        archive.mkdir(parents=True, exist_ok=True)
        for name in ("session.json", "frames.json", "edits.json"):
            if (directory/name).exists():
                shutil.copy2(directory/name, archive/name)
    progress(0.01, "MediaPipe / RF-DETR を準備中（初回は重みを取得）")
    detectors = VisionDetectors(config, model_dir)
    tracker = BallTracker(math.hypot(meta["width"], meta["height"]), config.max_gap_s)
    frames = []
    try:
        for stamp, image in read_frames(directory/session["source_file"]):
            balls, pose = detectors.predict(image, stamp["t"])
            frames.append({**stamp, "detections": balls, "pose": pose,
                           "ball": tracker.update(balls, stamp["t"])})
            if stamp["index"] % 10 == 0:
                progress(min(0.7, 0.05+0.65*stamp["t"]/max(meta["duration_s"], 1)), f"骨格・ボールを解析中 · {stamp['index']+1} frames")
    finally:
        detectors.close()
    if not frames:
        raise ValueError("解析できるフレームがありません")
    session["config"] = config.model_dump()
    session["shots"] = analyze_frames(frames, config, meta["width"], meta["height"])
    session["summary"] = summary(session["shots"])
    session["quality"] = {
        "pose_coverage": round(sum(bool(f["pose"]) for f in frames)/len(frames)*100, 1),
        "ball_coverage": round(sum(bool(f["ball"] and f["ball"]["source"] == "detected") for f in frames)/len(frames)*100, 1),
        "timestamp_fallback_frames": sum(f["timestamp_source"] != "pts" for f in frames),
    }
    session["video"]["frame_count"] = len(frames)
    session["video"]["duration_s"] = frames[-1]["t"]+1/meta["fps"]
    session["revision"] = session.get("revision", 0)+1
    # The previous frame data stays in place until the new rendering succeeds.
    progress(0.72, "確認用動画とオーバーレイ動画を書き出し中")
    render_video(directory/session["source_file"], directory/"annotated-next.mp4", frames, session,
                 lambda p: progress(0.72+p*0.27, "オーバーレイ動画を書き出し中"), directory/"preview-next.mp4")
    (directory/"annotated-next.mp4").replace(directory/"annotated.mp4")
    (directory/"preview-next.mp4").replace(directory/"preview.mp4")
    session.update(status="ready", rendered_revision=session["revision"])
    save_json(directory/"frames.json", frames)
    save_json(directory/"session.json", session)
    return session
