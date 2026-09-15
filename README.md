# Basket Lab

Basket Lab is a local proof of concept for analyzing and reviewing fixed-camera, single-player free-throw practice recorded on a smartphone. Python performs the analysis, while the browser interface displays pose landmarks, the ball trajectory, shot attempts, and 2D joint-angle charts.

## Technical overview

Basket Lab analyzes fixed-camera footage of a single basketball player locally in Python and provides a mobile-friendly browser interface for reviewing results. The current default session uses the real clip at `data/demo/single_three_point.mov`. The initial target is free-throw practice; this particular sample shows a three-point shot.

### Models and responsibilities

| Model / library | Purpose | Input and output | Application configuration |
|---|---|---|---|
| **RF-DETR Nano** (`rfdetr==1.10.1`) | Per-frame ball detection | RGB image -> bounding boxes, classes, and confidence scores. Each box is converted to a center point and approximate radius | COCO-pretrained `rf-detr-nano.pth`, filtered to the `sports ball` class. No basketball-specific fine-tuning has been performed |
| **MediaPipe Pose Landmarker Lite** (`mediapipe==0.10.35`) | Body pose estimation | Image cropped to the automatically detected or manually selected player region -> 33 body landmarks, mapped back to full-frame pixel coordinates | `pose_landmarker_lite.task`, `num_poses=1`; `IMAGE` mode for moving automatic crops and `VIDEO` mode for fixed manual crops. Landmark confidence is the minimum of visibility and presence |

RF-DETR locates the **ball**, while MediaPipe estimates **body landmarks**. Python rules operating on their time series determine shot attempts, release times, and proposed outcomes. The application does not use a trained outcome classifier, a form-scoring model, or an LLM. The rim is selected manually. Player localization defaults to automatic detection for a single moving player; a manually selected fixed crop remains available. Automatic rim and net detection are not implemented.

Implementation: [detectors.py](basket/detectors.py). See [models/README.md](models/README.md) for model storage and custom-weight configuration.

### Analysis pipeline

```text
Video file (MP4 / MOV / other supported formats)
  -> PyAV decodes frames and source timestamps
  |-- RF-DETR Nano -> ball detections
  |-- MediaPipe Pose Landmarker Lite -> body landmarks
  -> Ball tracking and 2D angle measurements
  -> Shot intervals, release times, and outcome proposals
  -> Frame measurements and shot records saved as JSON
  |-- Short-horizon forecasts from observations available at each timestamp
  |-- Browser playback with pose, observed tracks, and forecast overlays
  |-- Annotated MP4 output through OpenCV / PyAV
```

| Stage | Current method | Implementation |
|---|---|---|
| Video and timing | Preserve PTS, time base, and relative timestamps. Mark FPS-derived fallback timestamps separately | [video.py](basket/video.py) |
| Ball tracking | Predict the next position from previous position and velocity, then associate nearby detections. Reset after gaps exceeding 0.12 seconds by default | [tracking.py](basket/tracking.py) |
| Attempts and release | Confirm possession near the shooting wrist across multiple frames, followed by upward separation toward the rim. Retain a release-time candidate interval | [events.py](basket/events.py) |
| Outcomes | Inspect observed descending tracks near the rim. Clear outside passages are automatically classified as misses. Continuous tracks below the rim become make candidates, with the outcome left unknown for review | [events.py](basket/events.py) |
| Body measurements | Calculate 2D elbow and knee angles from shoulder-elbow-wrist and hip-knee-ankle landmarks. Derive torso lean from shoulder and hip centers. Treat low-confidence landmarks as missing | [measure.py](basket/measure.py) |
| Video trajectory forecasts | Fit recent observed coordinates as quadratic functions of time and draw up to 0.6 seconds ahead. Browser overlays and MP4 exports share the same prediction logic | [prediction.py](basket/prediction.py), [render.py](basket/render.py) |
| Cross-shot trajectory comparison | Overlay local quadratic fits on observed points and align shots by their first observed position immediately after release | [trajectory.js](basket/static/trajectory.js) |

### Observations, smoothed curves, and forecasts

- **Observed points:** Ball positions detected by the model in individual frames. These are model measurements, not human-annotated ground truth, and may include false detections.
- **Comparison curves:** Display-only smoothing of already observed tracks. Segments with fewer than five points receive no fitted curve. Curves do not bridge long gaps or extend beyond their observed interval.
- **Video forecasts:** Forward estimates using only observations available by the current frame. Least-squares fits of `x(t)` and `y(t)` use at least six points spanning at least 0.15 seconds within the latest 0.45-second window. Forecasts extend up to 0.6 seconds ahead and appear as blue dashed lines.

Forecasts are suppressed on frames without a detection or when the fit is unstable, and are truncated at the image boundary. Forecasting for a shot ends when its descending ball crosses the rim's image-space height. This is a 2D image-space estimate, not a calibrated 3D simulation of gravity and physical distance. Neither smoothed comparison curves nor forecast lines are used as evidence for outcome classification.

### Application stack and execution

| Area | Technology and behavior |
|---|---|
| Languages | Python 3.10-3.12, JavaScript, HTML, CSS |
| API | FastAPI / Uvicorn, served locally at `127.0.0.1:8000` |
| Analysis jobs | Sequential processing through a single Python worker thread |
| Numerical computation | NumPy; PyTorch for the object detector and the MediaPipe runtime for pose estimation |
| Video rendering | OpenCV (`opencv-contrib-python==5.0.0.93`) for drawing, PyAV / H.264 for encoding |
| Review UI | Plain HTML / CSS / JavaScript, with Canvas overlays and charts |
| Storage | Local files: frame JSON, session JSON, edit history, CSV, and MP4. No database |
| Mobile support | Responsive interface, inline video playback, and bottom navigation. Native packaging, on-device inference, and app-store distribution are not implemented |

Inference runs on the PC without a cloud inference API. Initial dependency installation and model retrieval require network access. Dependency constraints are defined in [pyproject.toml](pyproject.toml); versions from the validated environment are recorded in [requirements.lock.txt](requirements.lock.txt).

### Current real-video sample and limitations

If `data/demo/single_three_point.mov` exists, startup registers it as a real-video session. Existing analysis results are retained across restarts. If the file is absent, startup does not generate synthetic footage. Video files are excluded from Git, so place the clip at the same path on another machine or import a video through the UI. Registration alone does not run inference; start analysis from the recording setup screen.

During local verification on 2026-09-15, the approximately 4.1-second, 3840 x 2160 clip decoded into 246 frames and produced one detected attempt. Pose coverage was 72.4% and ball detection coverage was 54.1%. These are **fractions of frames with available detections**, not accuracy against ground truth. The automatically proposed miss still requires visual review. One clip is insufficient to establish general accuracy.

Angles and trajectories are measured in 2D image coordinates. Physical speed in km/h, height in meters, 3D joint angles, and form scoring are not implemented. Comparisons assume a fixed camera, one target player, and consistent recording conditions.

## Getting started

Requirements: Windows and Python 3.10–3.12. Open PowerShell in this directory, then run:

```powershell
# First run: install the analysis dependencies and download the pose model
.\setup.ps1 -Vision

# Start the server
.\start.ps1
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). To use a different port, run `start.ps1 -Port 8001`. Stop the server with Ctrl+C in its terminal.

If PowerShell script execution is disabled, use the equivalent commands below without changing the system policy:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[vision,test]"
.\.venv\Scripts\python.exe -m basket.cli setup-models
.\.venv\Scripts\python.exe -m basket.cli serve
```

Omit `-Vision` from `setup.ps1` if you only want to review previously analyzed sessions. Real-video analysis requires the vision dependencies. Exact package versions used by the validated environment are recorded in `requirements.lock.txt`.

RF-DETR downloads its official pretrained weights on the first real analysis. Model initialization and inference can take some time. CPU inference is supported, but the application is not designed to process 60 fps video in real time. See [models/README.md](models/README.md) for the model architecture, local-execution behavior, cache paths, and custom-weight configuration.

## Usage

1. **Import a practice video:** MP4, MOV, M4V, AVI, MKV, or WebM; up to 2 GB, 20 minutes, and 4K.
2. **Configure the recording:** Mark the rim, enable automatic player detection for one moving player, select handedness, and start analysis. An optional manual player region is available; include the entire body and shooting-hand motion when using it.
3. **Review:** Select a shot to seek to just before release. Use slow playback, frame stepping, and the pose, trajectory, and rim display toggles.
4. **Correct:** Edit the outcome, release time, and notes. False detections can be excluded and later restored. An edit history is retained.
5. **Export:** Download shot data as CSV, raw per-frame measurements as JSON, or an annotated MP4. After corrections, the video is rendered again before download.

Videos are stored and analyzed on this computer. The application does not implement cloud video uploads or account registration. Network access is needed to install dependencies and retrieve models for the first time; once those files are present, inference is local.

## Implemented features

| Area | Current implementation |
|---|---|
| Video decoding | PyAV preserves the original presentation timestamps, time base, and relative time; an FPS-derived fallback is explicitly marked when timestamps are missing |
| Pose | MediaPipe Pose Landmarker (IMAGE mode for moving crops; VIDEO for fixed crops), one person in a moving automatic crop or an optional fixed manual crop |
| Ball detection | RF-DETR Nano pretrained on COCO; RGB input and class-name resolution for `sports ball` |
| Tracking | Velocity prediction and distance gating; measured and predicted positions remain distinguishable; tracking resets after a gap longer than 0.12 seconds by default |
| Attempt and release detection | Multi-frame ball possession near the wrist followed by upward motion and separation toward the rim; the release candidate interval is retained |
| Outcome | A clear outside passage becomes a miss candidate; a continuous trajectory below the rim becomes a make candidate, while the final result remains unknown pending visual confirmation |
| Joint angles | Pixel-space 2D elbow and knee angles plus torso lean derived from shoulder and hip centers; low-confidence points are treated as missing |
| Summary | Make percentage is `made / (made + missed)`; unknown and excluded attempts are omitted from the denominator, and unknown attempts are reported separately |
| Recompute | Re-runs event detection from saved measurements and exports `proposals.json` without overwriting manual corrections |

The application does not automatically confirm made shots because a 2D rim crossing cannot prove that the ball passed through the net. Automatically proposed misses should also be reviewed. The current model does not detect the net itself.

## Code and data layout

```text
basket/
  schema.py       Setup configuration and input validation
  video.py        Timestamp-aware decoding and VFR-preserving H.264 output
  detectors.py    MediaPipe and RF-DETR adapters
  tracking.py     Ball association and short-gap prediction
  measure.py      2D measurements
  events.py       Shot, release, and outcome proposals
  prediction.py   Past-observation-only short-horizon trajectory forecasts
  pipeline.py     Analysis pipeline orchestration
  render.py       Annotated video rendering
  server.py       Local API, jobs, manual corrections, and exports
  default_session.py  Registers the local real clip without synthetic results
  demo.py         Legacy synthetic fixture generator; not used on startup
  static/         Japanese review interface
data/<session>/
  source.*        Original video, including its audio
  preview.mp4     Silent H.264 browser preview
  annotated.mp4   Silent annotated video
  frames.json     Detections, pose, tracking source flags, timestamps, and 2D angles
  session.json    Configuration, summary, automatic proposals, and reviewed shots
  edits.json      Manual edit history, created after the first correction
  proposals.json  Recomputed automatic proposals, created on request
  history/        Session, frame, and edit data archived before re-analysis
models/
  README.md                   Model behavior and RF-DETR technical notes
  pose_landmarker_lite.task   Downloaded MediaPipe model; not committed
  rfdetr/rf-detr-nano.pth     Downloaded RF-DETR weights; not committed
```

Set `BASKET_DATA_DIR` to change the data directory and `BASKET_MODEL_DIR` to change the application model directory. RF-DETR honors an existing `RF_HOME`; otherwise the application points it at `models/rfdetr`.

The local API specification is available at [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs) while the server is running.

To use fine-tuned **RF-DETR Nano** weights, set `BASKET_RFDETR_WEIGHTS` to the absolute checkpoint path before starting the server. For a model with a custom label map, pass its ball class number as `ball_class_id` to the analysis API. The initial UI configuration assumes the COCO label map.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --check basket/static/app.js
node --test tests/trajectory.test.cjs
.\.venv\Scripts\python.exe -m basket.cli demo
```

The tests cover short and long tracking gaps, false candidates, dribbling, repeated shots, occlusion, inconclusive 2D crossings, 2D angles, the make-percentage denominator, correction persistence and history, exclusion restoration, CSV export, and variable-frame-rate video.

`python -m basket.cli demo` now registers the local `data/demo/single_three_point.mov` clip; it does not generate synthetic footage or run analysis. Forecast tests additionally verify that future frames do not affect an earlier prediction, gaps reset the observation window, and excluded shots have no forecasts.

## Further validation required

- Expand beyond the supplied single-shot real clip: collect free-throw videos from multiple camera positions, with 10–20 shots per video.
- Use a single player in a consistent location, filmed side-on with a fixed tripod; keep the whole body, trajectory apex, and rim visible.
- Measure ball recall near the hands, trajectory apex, and rim; release-time error; attempt precision and recall; outcome agreement; and the unknown-result rate.
- Reserve videos from a separate recording day for evaluation, apart from tuning and training footage.

A general-purpose `sports ball` model can miss a small, blurred, or occluded basketball. Manual attempt creation, training-data labeling, fine-tuning, and evaluation reports are future work. The current event window ends three seconds after release, and the initial thresholds are relative to the image dimensions; both require calibration on real footage.

Videos containing multiple people inside the configured player region, camera movement, or rotation metadata are outside the initial scope. Export videos with rotation metadata in landscape orientation before importing them.

Real-world speed in km/h, physical height in meters, 3D joint angles, and form scoring are not implemented. Re-analysis updates the same session and archives its previous measurements and corrections under `history/`. To compare experiments in the UI, import the same video as a separate session.

## References

- [MediaPipe Pose Landmarker: Python guide](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker/python)
- [RF-DETR object detection guide](https://rfdetr.roboflow.com/latest/learn/run/detection/)
- [RF-DETR API reference](https://rfdetr.roboflow.com/latest/reference/rfdetr/)

Any attached social-media posts were used only as visual and structural references; their text was not treated as implementation requirements.

## Current development scope

[Issue #1](https://github.com/RikuNishi/basketball-analytics-app/issues/1) tracks moving single-player analysis for 30-minute recorded practice. Real-time processing, multiple players, moving cameras, and automatic rim detection are out of scope. See [the scoped work plan](docs/single-player-recorded-analysis.md).

Automatic localization uses the person boxes returned by the existing RF-DETR pass. It pauses pose measurements when no unique person is detected and reacquires after absence. Moving crops use MediaPipe IMAGE mode to avoid carrying temporal pose state between different crop coordinate systems. This costs additional pose inference work and needs longer real-video validation. The 30-minute storage, resume, and windowed-review work is still pending; the existing 20-minute upload limit remains in place.

Automatic player localization currently requires the bundled COCO model. When using `BASKET_RFDETR_WEIGHTS` or a custom `ball_class_id`, select a manual player region; a custom model may not expose the expected person class.
