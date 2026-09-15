# Moving-player, long-session, and live analysis design

Status: historical proposal, not implemented. Reviewed 2026-09-15.

The current agreed scope explicitly excludes live analysis. See
[single-player-recorded-analysis.md](single-player-recorded-analysis.md) for the
active scope; live-related sections below are retained only as background.

## Recommended scope

Support one selected player moving around a visible half-court, with a fixed
camera and one selected basket. Movement of the player must not require a new
manual region. Camera movement is a separate, harder requirement.

Prioritize reliable recorded-session analysis, followed by live feedback after
each shot. Fully on-device live overlays remain a later deployment target.

## Use cases

| Mode | Expected behavior | Processing policy |
|---|---|---|
| Recorded 30-minute practice | Review all attempts, including movement and ball retrieval | Preserve source timestamps; process to completion with checkpoints |
| Live practice feedback | Show tracking status and provisional counts, then update after each shot | Keep the display current; save footage for later correction |
| Live trajectory overlay | Draw observations and a short forecast on the corresponding video frame | Synchronize by timestamp; never draw an old result on a newer frame |

An initial product target could be feedback within 1-2 seconds of a shot ending.
This is a proposed target, not measured performance. Outcome confirmation must
wait for post-rim evidence and can still remain unknown.

## Player detection and identity

- Retain RF-DETR person detections as well as sports-ball detections.
- Automatically select a sole player; when several people are visible, let the
  user select the shooter once.
- Associate detections over time using motion and overlap. Add appearance-based
  identity matching only if crossings or re-entry make it necessary.
- Distinguish player identity from ball ownership. A nearby rebounder must not
  automatically become the target shooter.
- Expand and stabilize the player crop to include raised hands. Convert pose
  coordinates back to the full image before calculating measurements.
- Test MediaPipe temporal tracking with a moving crop: crop changes alter its
  coordinate frame. Reset tracking on discontinuities or compare full-frame pose
  estimation with identity association instead of assuming crops are harmless.
- When the player leaves the frame, pause measurements. Reacquire the target on
  return and request selection only if identity is ambiguous.

## Is automatic hoop detection necessary?

The rim position is needed for the current attempt-direction and outcome rules.
A learned rim detector is not required when the camera and basket remain fixed:
one initial selection can remain valid while the player moves.

Recommended progression:

1. Keep manual rim selection as a fallback.
2. Add automatic initial rim/backboard proposals for simpler setup. Confirm the
   target if several baskets are visible.
3. Cache the accepted geometry and check periodically for camera displacement.
4. On camera displacement, invalidate stale geometry, suspend outcome decisions,
   and reacquire the rim before resuming. Do not silently reuse old coordinates.

For handheld/panning footage, repeated localization and camera-motion handling
become necessary. A moving camera also invalidates the current image-space
ballistic forecast; redetecting the rim alone does not solve that problem.

A backboard box helps find the basket, but outcome analysis needs a more precise
rim region. Rim detection does not itself prove a made shot: post-rim ball motion,
occlusion, and depth ambiguity still need handling. Net detection is an optional
additional cue, not sufficient evidence on its own.

## Long-session architecture

The current implementation rejects videos longer than 20 minutes and uploads
larger than 2 GB. It accumulates frame measurements in memory, writes a single
JSON file, and loads all measurements into the browser. Raising the duration
limit alone is insufficient. A 30-minute, 60 fps recording contains 108,000 frames.

- Decode incrementally and retain only bounded tracking/event windows in RAM.
- Store timestamped frame records incrementally in chunks or an indexed store.
- Preserve tracking and shot state across chunk boundaries; never reset solely
  because a storage chunk ends.
- Checkpoint progress for cancellation, retry, and resume.
- Query the browser's current playback interval instead of downloading all frame
  measurements and forecasts. Paginate the shot list.
- Separate preview generation, inference, and full annotated export. Export the
  full video on request rather than making it a prerequisite for review.
- Replace the fixed three-second shot window with explicit possession, release,
  flight, rim interaction, and recovery states plus bounded timeouts.
- Keep camera segments and player identity in records. Do not directly compare
  pixel trajectories or 2D joint angles across substantially different viewing
  angles. Court-position grouping requires separate floor-plane calibration.

## Live scheduling and deployment

Use bounded queues, timestamps, and independent capture/render/inference stages.
For live preview, avoid unbounded lag: outdated frames may be skipped, but missing
evidence must remain visible in quality flags. Save source video to enable later
re-analysis. Offline processing should not inherit the same frame-drop policy.

Person detection may run less frequently when tracking is stable; reacquire on
low confidence. Prioritize ball observations during release, flight, and rim
interaction. Any reduced-rate search outside these intervals needs a recent-frame
buffer and validation against missed attempts, especially quick catch-and-shoots.

Initially evaluate a phone camera feeding a local GPU-equipped PC. Measure decode,
transfer, inference, and display delays separately. Native phone inference requires
model/runtime compatibility checks and sustained thermal/battery testing; a
mobile-friendly web UI does not establish on-device inference support.

MediaPipe supports asynchronous LIVE_STREAM processing and may ignore incoming
frames while busy. Its mode alone does not make the complete pipeline real time.
RF-DETR performance claims likewise do not establish this application's end-to-end
performance on the target device.

## Validation gates

- Moving-player coverage, identity switches, and successful reacquisition after exit.
- Attempt precision/recall and duplicate counts on independently labeled sessions.
- Release-time error; outcome accuracy among classified shots plus unknown rate.
- Ball coverage near hands, apex, and rim; camera-shift recovery time.
- 30-minute sustained throughput, peak memory, checkpoint recovery, and UI latency.
- Live end-to-end latency percentiles, dropped-frame rate, and count drift against
  offline analysis of the same recording.

## Sources

- [MediaPipe Pose Landmarker Python guide](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker/python)
- [RF-DETR inference documentation](https://rfdetr.roboflow.com/latest/learn/run/detection/)
- Current application: `basket/detectors.py`, `tracking.py`, `events.py`,
  `video.py`, `pipeline.py`, `prediction.py`, and `static/app.js`.
