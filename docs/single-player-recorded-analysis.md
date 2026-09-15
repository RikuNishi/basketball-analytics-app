# Single-player recorded practice analysis

## Problem

The current application requires a fixed player crop and accepts recordings only
up to 20 minutes. A lone player naturally moves between shooting positions and
retrieves the ball during a 30-minute practice. The crop can lose the player, and
loading every frame measurement into memory does not scale to longer recordings.

## Agreed scope

- Exactly one player, who may move and temporarily leave the frame.
- One fixed camera and one basket; the rim is selected once manually.
- Analyze recorded videos up to 30 minutes after recording.
- Automatically locate the player and follow their movement for pose estimation.
- Retain observed ball tracks, video forecasts, 2D measurements, and manual review.
- Keep uncertain outcomes unknown; predictions must not become scoring evidence.

## Out of scope

- Real-time or live-stream analysis.
- Multiple-player identification or re-identification.
- Moving cameras, pans, and zooms.
- Automatic rim/net detection, physical 3D calibration, and form scoring.
- Native mobile packaging, on-device inference, or cloud deployment.

## Work plan

1. **Automatic player localization:** retain RF-DETR person boxes, associate the
   single player over time, expand crops for raised hands, and restore full-frame
   coordinates. Handle detection loss and re-entry without fabricated poses.
   Evaluate temporal pose behavior when the crop moves. Keep manual cropping as
   an optional compatibility fallback.
2. **Long-session processing:** accept 30-minute recordings, persist observations
   incrementally, bound memory use, and checkpoint progress for retries/resume.
   Carry tracking and shot state across storage boundaries.
3. **Review and exports:** load measurements for the playback window, paginate
   shots, and keep full-video export separate from initial result availability.
4. **Validation:** test movement, exit/re-entry, tracking gaps, chunk boundaries,
   timestamp preservation, resume, and manual corrections. Measure a full
   30-minute run and clearly separate synthetic load tests from real-video
   detection accuracy.

## Acceptance criteria

- [ ] A lone moving player can be analyzed without drawing a player region.
- [ ] Lost-player intervals produce missing measurements; tracking resumes on return.
- [ ] A manually selected rim remains fixed throughout the recording.
- [ ] A 30-minute recording is accepted and processed with bounded working memory.
- [ ] Progress is persisted and interrupted analysis can resume consistently.
- [ ] Playback requests only the required measurement window.
- [ ] Shot review and annotated export continue to work.
- [ ] Tests and documentation cover the new behavior and remaining limitations.

Media, model weights, and generated analysis outputs must remain outside Git.
This agreed scope supersedes the live-analysis proposal in
`long-session-and-live-analysis.md` for the current implementation.
