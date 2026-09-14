"""Procedural test footage. All demo measurements are synthetic, never ML output."""
import math
from datetime import datetime, timezone
import cv2
import numpy as np
from .schema import AnalysisConfig
from .tracking import BallTracker
from .events import analyze_frames, summary
from .video import VideoWriter, read_frames
from .render import render_video
from .store import save_json, load_json


def scene():
    image = np.full((540, 960, 3), (216, 221, 214), dtype=np.uint8)
    cv2.rectangle(image, (0, 0), (960, 342), (202, 214, 203), -1)
    for x in range(0, 1000, 120):
        cv2.rectangle(image, (x, 0), (x+2, 343), (185, 200, 189), -1)
    cv2.rectangle(image, (0, 280), (960, 342), (107, 131, 112), -1)
    cv2.rectangle(image, (0, 342), (960, 540), (169, 196, 214), -1)
    for y in range(351, 540, 21):
        cv2.line(image, (0, y), (960, y), (148, 177, 196), 1)
    cv2.line(image, (0, 460), (960, 460), (226, 239, 235), 3)
    cv2.line(image, (650, 342), (810, 540), (226, 239, 235), 3)
    cv2.ellipse(image, (400, 416), (155, 55), 0, -90, 90, (233, 242, 236), 3)
    cv2.line(image, (400, 360), (400, 473), (233, 242, 236), 3)
    cv2.rectangle(image, (821, 102), (835, 385), (67, 83, 73), -1)
    cv2.rectangle(image, (800, 99), (807, 202), (234, 242, 234), -1)
    cv2.line(image, (800, 177), (759, 177), (81, 94, 234), 4)
    cv2.ellipse(image, (759, 177), (30, 6), 0, 0, 360, (81, 94, 234), 3)
    for offset in [-24, -12, 0, 12, 24]:
        cv2.line(image, (759+offset, 180), (759+int(offset*0.55), 218), (226, 240, 234), 1)
    cv2.line(image, (744, 218), (774, 218), (226, 240, 234), 1)
    cv2.putText(image, "B / L", (65, 94), cv2.FONT_HERSHEY_SIMPLEX, 1.7, (131, 157, 136), 3, cv2.LINE_AA)
    cv2.putText(image, "PRACTICE  /  OBSERVE  /  REPEAT", (67, 118), cv2.FONT_HERSHEY_SIMPLEX, .35, (123, 147, 126), 1, cv2.LINE_AA)
    cv2.putText(image, "SYNTHETIC DEMO - NOT REAL FOOTAGE", (590, 515), cv2.FONT_HERSHEY_SIMPLEX, .43, (62, 86, 77), 1, cv2.LINE_AA)
    return image


def sample(t):
    n, phase = int(t/4.4), t % 4.4
    crouch = 10*math.sin(min(phase, 1)*math.pi)
    extension = min(1, max(0, phase-0.5)*2)
    pose = [[0, 0, 0] for _ in range(33)]
    points = {0: (292, 263+crouch), 11: (280, 296+crouch), 12: (302, 295+crouch),
              13: (286, 322-36*extension), 14: (318, 316-32*extension),
              15: (322, 267), 16: (332, 267), 23: (276, 351+crouch), 24: (298, 352+crouch),
              25: (267+10*crouch/10, 389), 26: (311+10*crouch/10, 389), 27: (262, 438), 28: (307, 440)}
    for i, (x, y) in points.items():
        pose[i] = [x, y, 0.99]
    u = max(0, phase-1)
    x, y = 332+300*u, 265-360*u+210*u*u
    if n != 2 and u >= 1.43:
        x, y = 761+8*(u-1.43), 177+245*(u-1.43)
    if n == 2:
        x += 65*u
    ball = {"x": x, "y": y, "radius": 9, "confidence": 0.99}
    if phase > 3.1 or (n == 4 and 2.18 < phase < 2.85):
        ball = None
    return pose, ball


def create_demo(directory):
    directory.mkdir(parents=True, exist_ok=True)
    if (directory/"session.json").exists():
        return load_json(directory/"session.json")
    config = AnalysisConfig(rim={"x": 729/960, "y": 167/540, "w": 60/960, "h": 20/540},
                            person={"x": .2, "y": .35, "w": .22, "h": .5})
    background, frames = scene(), []
    tracker = BallTracker(math.hypot(960, 540))
    with VideoWriter(directory/"source.mp4", 960, 540, 30) as writer:
        for i in range(792):
            t = i/30
            pose, ball = sample(t)
            image = background.copy()
            cv2.ellipse(image, (285, 446), (48, 8), 0, 0, 360, (137, 164, 178), -1)
            for a, b in [(11, 13), (13, 15), (12, 14), (14, 16)]:
                cv2.line(image, tuple(map(int, pose[a][:2])), tuple(map(int, pose[b][:2])), (104, 150, 178), 12, cv2.LINE_AA)
            for a, b in [(23, 25), (25, 27), (24, 26), (26, 28)]:
                cv2.line(image, tuple(map(int, pose[a][:2])), tuple(map(int, pose[b][:2])), (53, 65, 56), 16, cv2.LINE_AA)
            body = np.array([pose[k][:2] for k in (11, 12, 24, 23)], dtype=np.int32)
            cv2.fillConvexPoly(image, body, (62, 89, 69), cv2.LINE_AA)
            cv2.circle(image, tuple(map(int, pose[0][:2])), 19, (104, 150, 178), -1, cv2.LINE_AA)
            cv2.ellipse(image, (291, int(pose[0][1])-8), (19, 13), 0, 180, 360, (45, 56, 47), -1)
            for k in (27, 28):
                x, y = map(int, pose[k][:2])
                cv2.line(image, (x-7, y), (x+16, y), (235, 242, 235), 9, cv2.LINE_AA)
            if ball:
                center = tuple(int(ball[k]) for k in ("x", "y"))
                cv2.circle(image, center, 9, (49, 129, 222), -1, cv2.LINE_AA)
                cv2.circle(image, center, 9, (39, 81, 130), 1, cv2.LINE_AA)
                cv2.line(image, (center[0]-8, center[1]), (center[0]+8, center[1]), (39, 81, 130), 1)
            writer.write(image, t)
            frames.append({"index": i, "t": t, "pts": i, "time_base": "1/30", "timestamp_source": "synthetic",
                           "pose": pose, "detections": [ball] if ball else [], "ball": tracker.update([ball] if ball else [], t)})
    shots = analyze_frames(frames, config, 960, 540)
    outcomes = ["made", "made", "missed", "made", "unknown", "made"]
    for shot, outcome in zip(shots, outcomes):
        shot["outcome"] = outcome
        shot["reason"] = "合成データの設定値です。AIによる実動画の判定結果ではありません"
    session = {"id": "demo", "name": "フリースロー・デモセッション", "is_demo": True, "status": "ready",
               "created_at": datetime.now(timezone.utc).isoformat(), "source_file": "source.mp4",
               "video": {"width": 960, "height": 540, "fps": 30, "duration_s": 26.4, "frame_count": 792, "codec": "h264", "audio_in_source": False},
               "config": config.model_dump(), "shots": shots, "summary": summary(shots),
               "quality": {"pose_coverage": 100, "ball_coverage": round(sum(bool(f["detections"]) for f in frames)/len(frames)*100, 1), "timestamp_fallback_frames": 0},
               "revision": 1, "rendered_revision": 1}
    save_json(directory/"frames.json", frames)
    render_video(directory/"source.mp4", directory/"annotated.mp4", frames, session, preview=directory/"preview.mp4")
    cv2.imwrite(str(directory/"thumbnail.jpg"), next(read_frames(directory/"source.mp4"))[1])
    save_json(directory/"session.json", session)
    return session
