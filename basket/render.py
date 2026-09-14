from collections import deque
import cv2
from .measure import EDGES, valid
from .video import read_frames, VideoWriter
from .prediction import video_predictions


def annotate(image, frame, trail, session, prediction=None):
    h, w = image.shape[:2]
    rim = session["config"]["rim"]
    a = (int(rim["x"]*w), int(rim["y"]*h))
    b = (int((rim["x"]+rim["w"])*w), int((rim["y"]+rim["h"])*h))
    cv2.rectangle(image, a, b, (80, 219, 195), 2)
    pose = frame.get("pose")
    for p, q in EDGES:
        if valid(pose, [p, q]):
            cv2.line(image, tuple(int(v) for v in pose[p][:2]), tuple(int(v) for v in pose[q][:2]), (178, 231, 123), 2, cv2.LINE_AA)
    for p in pose or []:
        if p[2] >= 0.5:
            cv2.circle(image, tuple(int(v) for v in p[:2]), 3, (255, 255, 240), -1)
    ball = frame.get("ball")
    if ball:
        point = (int(ball["x"]), int(ball["y"]))
        color = (68, 162, 250) if ball["source"] == "detected" else (170, 170, 170)
        cv2.circle(image, point, max(5, int(ball["radius"])+4), color, 2)
        trail.append((frame["t"], point, ball["source"]))
    while trail and frame["t"]-trail[0][0] > 2:
        trail.popleft()
    for p, q in zip(trail, list(trail)[1:]):
        if q[0]-p[0] <= session["config"]["max_gap_s"] and p[2] == q[2] == "detected":
            cv2.line(image, p[1], q[1], (68, 162, 250), 2, cv2.LINE_AA)
    if prediction:
        for i, (p, q) in enumerate(zip(prediction, prediction[1:])):
            if i % 3 != 2:
                cv2.line(image, tuple(map(round, p)), tuple(map(round, q)), (199, 137, 7), 4, cv2.LINE_AA)
        cv2.putText(image, "PREDICTED / 2D", (12, h-16), cv2.FONT_HERSHEY_SIMPLEX, .5, (199, 137, 7), 1, cv2.LINE_AA)
    active = next((s for s in session["shots"] if not s.get("deleted") and s["start_s"] <= frame["t"] <= s["end_s"]), None)
    label = f"SHOT {active['id']:02d} | {active['outcome'].upper()}" if active else "BASKET LAB | 2D MEASUREMENTS"
    cv2.rectangle(image, (12, 12), (min(w-12, 550), 75), (30, 40, 35), -1)
    cv2.putText(image, label, (24, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (240, 244, 240), 1, cv2.LINE_AA)
    angles = frame.get("angles", {})
    cv2.putText(image, f"Elbow {angles.get('elbow_deg')}  Knee {angles.get('knee_deg')} deg (2D)", (24, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (178, 231, 123), 1, cv2.LINE_AA)
    return image


def render_video(source, output, frames, session, progress=None, preview=None):
    meta = session["video"]
    trail = deque()
    predictions = video_predictions(frames, session)
    # H.264 YUV420 requires even dimensions. Crop at most one border pixel.
    width, height = meta["width"]//2*2, meta["height"]//2*2
    plain = VideoWriter(preview, width, height, meta["fps"]) if preview else None
    try:
        with VideoWriter(output, width, height, meta["fps"]) as writer:
            for i, (stamp, image) in enumerate(read_frames(source)):
                if i >= len(frames):
                    raise ValueError("元動画と保存済み検出データのフレーム数が一致しません")
                image = image[:height, :width]
                if plain:
                    plain.write(image, stamp["t"])
                writer.write(annotate(image.copy(), frames[i], trail, session, predictions.get(frames[i]['index'])), stamp["t"])
                if progress and i % 30 == 0:
                    progress(i/max(1, len(frames)))
    finally:
        if plain:
            plain.close()
