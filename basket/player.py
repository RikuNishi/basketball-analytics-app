"""Conservative localization for one moving player, not multi-person identity."""
import math


class PlayerTracker:
    def __init__(self):
        self.box = None
        self.last_t = None

    def update(self, boxes, t, width, height):
        candidates = []
        for box in boxes:
            if len(box) != 4 or not all(math.isfinite(v) for v in box):
                continue
            x0, y0, x1, y1 = box
            x0, y0, x1, y1 = max(0, x0), max(0, y0), min(width, x1), min(height, y1)
            if x1 > x0 and y1 > y0:
                candidates.append((x0, y0, x1, y1))
        if self.last_t is not None and (t-self.last_t > .75 or t <= self.last_t):
            self.box = None
        # Ignore small background false positives only when the foreground target
        # is clearly dominant, or a single candidate continues the existing track.
        area = lambda b: (b[2]-b[0])*(b[3]-b[1])
        if self.box:
            px, py = (self.box[0]+self.box[2])/2, (self.box[1]+self.box[3])/2
            candidates = [b for b in candidates if area(b) >= area(self.box)*.5
                          and math.hypot((b[0]+b[2])/2-px, (b[1]+b[3])/2-py)
                          < math.hypot(width, height)*.25]
        elif len(candidates) > 1:
            candidates.sort(key=area, reverse=True)
            if area(candidates[0]) >= area(candidates[1])*2:
                candidates = candidates[:1]
        if len(candidates) != 1:
            return None
        current = candidates[0]
        if self.box:
            cx, cy = (current[0]+current[2])/2, (current[1]+current[3])/2
            px, py = (self.box[0]+self.box[2])/2, (self.box[1]+self.box[3])/2
            if math.hypot(cx-px, cy-py) > math.hypot(width, height)*.25:
                return None
            stable = tuple(.5*a+.5*b for a, b in zip(self.box, current))
        else:
            stable = current
        self.box, self.last_t = stable, t
        # Include both raw and stabilized bounds so smoothing cannot crop a moving arm.
        x0, y0 = min(stable[0], current[0]), min(stable[1], current[1])
        x1, y1 = max(stable[2], current[2]), max(stable[3], current[3])
        mx, my = (x1-x0)*.2, (y1-y0)*.2
        return (max(0, math.floor(x0-mx)), max(0, math.floor(y0-my)),
                min(width, math.ceil(x1+mx)), min(height, math.ceil(y1+my)))
