"""Short-horizon image-space forecasts, for visualization only."""
import math
import numpy as np


def forecast(points, width, height):
    if len(points) < 6 or points[-1][0]-points[0][0] < .15:
        return []
    data = np.asarray(points, dtype=float)
    t = data[:, 0]-data[-1, 0]
    design = np.column_stack((np.ones(len(t)), t, t*t))
    coefficients, _, rank, _ = np.linalg.lstsq(design, data[:, 1:3], rcond=None)
    if rank < 3 or not np.isfinite(coefficients).all():
        return []
    residual = np.sqrt(np.mean(np.sum((design@coefficients-data[:, 1:3])**2, axis=1)))
    # Screen y increases downward; reject non-ballistic or unstable fits.
    diagonal = math.hypot(width, height)
    if residual > diagonal*.008 or not 0 < coefficients[2, 1] < diagonal*5:
        return []
    result = []
    for dt in np.linspace(0, .6, 31):
        x, y = np.array([1, dt, dt*dt])@coefficients
        if not (0 <= x < width and 0 <= y < height):
            break
        result.append([round(float(x), 2), round(float(y), 2)])
    return result if len(result) > 1 else []


def video_predictions(frames, session):
    """Use only observations available at each frame, reset on gaps/each shot."""
    result = {}
    width, height = session['video']['width'], session['video']['height']
    gap = session['config']['max_gap_s']
    rim = session['config']['rim']
    rim_y = (rim['y']+rim['h']/2)*height
    for shot in session['shots']:
        if shot.get('deleted'):
            continue
        points = []
        finished = False
        for frame in frames:
            t = frame['t']
            if t < shot['release_s'] or t > shot['end_s'] or finished:
                continue
            ball = frame.get('ball')
            if not ball or ball['source'] != 'detected':
                continue
            if not all(math.isfinite(v) for v in (t, ball['x'], ball['y'])):
                continue
            if points and (t-points[-1][0] > gap or t <= points[-1][0]):
                points = []
            if points and points[-1][2] < rim_y <= ball['y']:
                finished = True
                continue
            points.append((t, ball['x'], ball['y']))
            points = [p for p in points if t-p[0] <= .45]
            curve = forecast(points, width, height)
            if curve:
                result[frame['index']] = curve
    return result
