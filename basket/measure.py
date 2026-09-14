"""Image-plane measurements, computed in pixels (not normalized aspect ratio)."""
import math

JOINTS = {"right": (12, 14, 16, 24, 26, 28), "left": (11, 13, 15, 23, 25, 27)}
EDGES = [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
         (11, 23), (12, 24), (23, 24), (23, 25), (25, 27), (24, 26), (26, 28)]


def angle(a, b, c):
    u, v = (a[0]-b[0], a[1]-b[1]), (c[0]-b[0], c[1]-b[1])
    norm = math.hypot(*u)*math.hypot(*v)
    if norm < 1e-9:
        return None
    return round(math.degrees(math.acos(max(-1, min(1, (u[0]*v[0]+u[1]*v[1])/norm)))), 2)


def valid(pose, ids):
    return bool(pose) and all(len(pose) > i and pose[i][2] >= 0.5 for i in ids)


def measurements(pose, handedness):
    s, e, w, h, k, a = JOINTS[handedness]
    result = {"elbow_deg": None, "knee_deg": None, "trunk_deg": None}
    if valid(pose, [s, e, w]):
        result["elbow_deg"] = angle(pose[s], pose[e], pose[w])
    if valid(pose, [h, k, a]):
        result["knee_deg"] = angle(pose[h], pose[k], pose[a])
    if valid(pose, [11, 12, 23, 24]):
        sx, sy = [(pose[11][i]+pose[12][i])/2 for i in (0, 1)]
        hx, hy = [(pose[23][i]+pose[24][i])/2 for i in (0, 1)]
        result["trunk_deg"] = round(math.degrees(math.atan2(sx-hx, hy-sy)), 2)
    return result
