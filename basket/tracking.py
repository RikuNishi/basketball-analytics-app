"""One-ball motion association. Predictions are never detection evidence."""
import math


class BallTracker:
    def __init__(self, diagonal, max_gap_s=0.12):
        self.diagonal = diagonal
        self.max_gap_s = max_gap_s
        self.last = None
        self.velocity = (0.0, 0.0)

    def update(self, detections, t):
        dt = t-self.last[0] if self.last else 0
        if self.last and dt > self.max_gap_s:
            self.last = None
            self.velocity = (0.0, 0.0)
        target = None
        if self.last:
            target = (self.last[1]+self.velocity[0]*dt, self.last[2]+self.velocity[1]*dt)
        candidates = detections
        if target:
            gate = self.diagonal*(0.035+max(0, dt)*1.3)
            candidates = [d for d in candidates if math.hypot(d["x"]-target[0], d["y"]-target[1]) <= gate]
        if candidates:
            chosen = (min(candidates, key=lambda d: math.hypot(d["x"]-target[0], d["y"]-target[1]))
                      if target else max(candidates, key=lambda d: d["confidence"]))
            x, y = chosen["x"], chosen["y"]
            if self.last and dt > 0:
                self.velocity = ((x-self.last[1])/dt, (y-self.last[2])/dt)
            self.last = (t, x, y)
            return {**chosen, "source": "detected"}
        if target:
            return {"x": target[0], "y": target[1], "radius": 5, "confidence": 0,
                    "source": "predicted"}
        return None
