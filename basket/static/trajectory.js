"use strict";
// Display-only local quadratic regression in time, never evidence for shot outcomes.
const Trajectory = (() => {
  function solve(matrix, rhs) {
    const a = matrix.map((row, i) => [...row, rhs[i]]);
    for (let k = 0; k < 3; k++) {
      let pivot = k;
      for (let i = k + 1; i < 3; i++) if (Math.abs(a[i][k]) > Math.abs(a[pivot][k])) pivot = i;
      if (Math.abs(a[pivot][k]) < 1e-10) return null;
      [a[k], a[pivot]] = [a[pivot], a[k]];
      const divisor = a[k][k];
      for (let j = k; j < 4; j++) a[k][j] /= divisor;
      for (let i = 0; i < 3; i++) if (i !== k) {
        const factor = a[i][k];
        for (let j = k; j < 4; j++) a[i][j] -= factor * a[k][j];
      }
    }
    return a.map(row => row[3]);
  }
  function smooth(points) {
    if (points.length < 5) return [];
    const start = points[0].t, duration = points.at(-1).t - start;
    if (duration <= 0) return [];
    const count = Math.min(240, Math.max(2, Math.ceil(duration * 60)));
    const curve = [];
    for (let i = 0; i <= count; i++) {
      const t = i === count ? points.at(-1).t : start + duration * i / count;
      const nearest = [...points].sort((a, b) => Math.abs(a.t-t)-Math.abs(b.t-t)).slice(0, 9);
      const bandwidth = Math.max(.05, ...nearest.map(p => Math.abs(p.t-t)));
      const matrix = Array.from({length:3}, () => [0, 0, 0]), bx = [0, 0, 0], by = [0, 0, 0];
      for (const p of nearest) {
        const u = (p.t-t)/bandwidth, weight = Math.exp(-2*u*u), basis = [1, u, u*u];
        for (let r = 0; r < 3; r++) {
          bx[r] += weight*basis[r]*p.x; by[r] += weight*basis[r]*p.y;
          for (let c = 0; c < 3; c++) matrix[r][c] += weight*basis[r]*basis[c];
        }
      }
      const x = solve(matrix, bx), y = solve(matrix, by);
      if (!x || !y) return [];
      curve.push({t, x:x[0], y:y[0]});
    }
    return curve;
  }
  function build(frames, shot, maxGap = .12) {
    const points = frames.filter(f => f.t >= shot.release_s && f.t <= Math.min(shot.end_s, shot.release_s+2.2)
      && f.ball?.source === "detected" && [f.t, f.ball.x, f.ball.y].every(Number.isFinite))
      .map(f => ({t:f.t, x:f.ball.x, y:f.ball.y}));
    // Avoid aligning to a predicted or distant release position.
    const origin = points.length && points[0].t-shot.release_s <= maxGap ? points[0] : null;
    const segments = [];
    for (const p of points) {
      let segment = segments.at(-1);
      if (!segment || p.t-segment.at(-1).t > maxGap || p.t <= segment.at(-1).t) {
        segment = []; segments.push(segment);
      }
      segment.push(p);
    }
    return {origin, points, curves:segments.map(smooth).filter(c => c.length)};
  }
  return {build, smooth};
})();
if (typeof module !== "undefined") module.exports = Trajectory;
