"""Conservative shot proposals; retained evidence can be recomputed offline."""
import math
from .measure import JOINTS, valid, measurements


def observed(frame):
    ball = frame.get("ball")
    return ball if ball and ball["source"] == "detected" else None


def outcome_evidence(frames, rim, width, height, max_gap_s):
    cx, cy = (rim.x+rim.w/2)*width, (rim.y+rim.h/2)*height
    half = rim.w*width/2
    points = [(f["t"], observed(f)) for f in frames if observed(f)]
    for j in range(1, len(points)):
        t0, a = points[j-1]
        t1, b = points[j]
        # Only short, genuinely observed descending segments may cross the rim plane.
        if t1-t0 > max_gap_s or not (a["y"] < cy <= b["y"]):
            continue
        x = a["x"]+(b["x"]-a["x"])*(cy-a["y"])/(b["y"]-a["y"])
        if abs(x-cx) > half + max(a["radius"], b["radius"])*2:
            if abs(x-cx) < width*0.25:
                return "missed", "下降軌跡がリングの外側を通過（自動推定・要確認）", "missed"
            continue
        after = points[j:j+5]
        continuous = len(after) >= 3 and all(after[k][0]-after[k-1][0] <= max_gap_s for k in range(1, len(after)))
        below = continuous and all(abs(p["x"]-cx) <= half+p["radius"] for _, p in after) and after[-1][1]["y"] > cy+rim.h*height
        if below:
            # Single-view 2D tracks do not prove passage through the physical hoop.
            return "unknown", "リング下への連続軌跡あり。奥行き・ネット通過を目視確認してください", "made"
        return "unknown", "リング付近の軌跡だけでは成否を確定できません", None
    return "unknown", "リング付近の連続した検出が不足しています", None


def analyze_frames(frames, config, width, height):
    diagonal = math.hypot(width, height)
    wrist_id = JOINTS[config.handedness][2]
    near = []
    departures = []
    current = None
    shots = []
    rim_cx = (config.rim.x+config.rim.w/2)*width

    def finish(end_index):
        nonlocal current
        if current is None:
            return
        section = frames[current["release_frame"]:end_index+1]
        outcome, reason, candidate = outcome_evidence(section, config.rim, width, height, config.max_gap_s)
        current.update(end_s=frames[end_index]["t"], outcome=outcome, auto_outcome=outcome,
                       candidate=candidate, reason=reason, reviewed=False, deleted=False, note="")
        shots.append(current)
        current = None

    for i, frame in enumerate(frames):
        frame["angles"] = measurements(frame.get("pose"), config.handedness)
        ball = observed(frame)
        pose = frame.get("pose")
        if current:
            elapsed = frame["t"]-current["release_s"]
            if elapsed >= 3.0:
                finish(i)
                near, departures = [], []
            continue
        if not ball or not valid(pose, [wrist_id]):
            if near and frame["t"]-near[-1][1] > config.max_gap_s:
                near, departures = [], []
            continue
        wrist = pose[wrist_id]
        distance = math.hypot(ball["x"]-wrist[0], ball["y"]-wrist[1])
        if distance <= max(diagonal*0.028, ball["radius"]*2.5):
            if near and frame["t"]-near[-1][1] > config.max_gap_s:
                near = []
            near.append((i, frame["t"], ball))
            near = near[-30:]
            departures = []
            continue
        if len(near) < 3:
            continue
        origin_index, origin_t, origin = near[-1]
        if frame["t"]-origin_t > 0.55:
            near, departures = [], []
            continue
        direction = 1 if rim_cx > origin["x"] else -1
        toward = (ball["x"]-origin["x"])*direction > diagonal*0.025
        rising = origin["y"]-ball["y"] > diagonal*0.018
        if toward and rising:
            departures.append(i)
            if len(departures) >= 2:
                current = {"id": len(shots)+1, "start_s": near[0][1],
                           "release_s": origin_t, "auto_release_s": origin_t,
                           "release_frame": origin_index,
                           "release_window_s": [origin_t, frames[departures[0]]["t"]]}
                near, departures = [], []
        else:
            departures = []
    if current:
        finish(len(frames)-1)
    return shots


def summary(shots):
    active = [s for s in shots if not s.get("deleted")]
    counts = {key: sum(s["outcome"] == key for s in active) for key in ("made", "missed", "unknown")}
    denominator = counts["made"]+counts["missed"]
    return {**counts, "attempts": len(active), "denominator": denominator,
            "percentage": round(counts["made"]/denominator*100, 1) if denominator else None}
