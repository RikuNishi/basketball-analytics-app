# Local vision models

This directory is the default local store for the vision models used by Basket Lab. Model binaries are intentionally excluded from Git because they are large; this README is tracked so the runtime behavior and setup remain documented.

## RF-DETR in Basket Lab

[RF-DETR](https://github.com/roboflow/rf-detr) is a real-time object detector derived from the Detection Transformer (DETR) family. Unlike detector pipelines that generate region proposals and then classify each proposal, DETR-style models formulate detection as direct set prediction: a fixed collection of learned object queries is decoded into class scores and bounding boxes, and duplicate predictions are discouraged during training through one-to-one matching.

Basket Lab uses `RFDETRNano` from the pinned `rfdetr==1.10.1` package. The supplied checkpoint is pretrained on COCO, and the application keeps detections whose class label is `sports ball`. RF-DETR receives each decoded video frame as a contiguous RGB NumPy array and returns bounding boxes, confidence values, and class IDs. Basket Lab converts every retained box into a center point and an approximate radius, then passes those observations to its temporal ball tracker.

RF-DETR performs only per-frame ball detection here. It does not determine possession, release, shot outcome, or pose. Those responsibilities are split as follows:

```text
video frame
  |-- RF-DETR Nano --> sports-ball boxes --> temporal ball tracker
  |-- MediaPipe ----> pose landmarks ------|
                                             v
                               release and shot heuristics
                                             |
                                             v
                                  reviewable local results
```

The rim is selected manually in the setup UI. The current model does not detect the rim or net.

## Local execution and network access

Inference runs in the local Python process. Video frames and detections are not sent to Roboflow or another inference API, and Basket Lab has no cloud-video upload implementation.

Network access is still required during provisioning:

- `setup.ps1 -Vision` installs Python dependencies and downloads the MediaPipe Pose Landmarker asset.
- On the first real analysis, `rfdetr` downloads the official RF-DETR Nano checkpoint if it is missing.

After the dependencies and both model files are present, normal analysis can run offline. The RF-DETR package checks whether the checkpoint exists locally and skips its download when it does. Deleting the checkpoint causes a later model initialization to try downloading it again.

## Default files

```text
models/
  pose_landmarker_lite.task
  rfdetr/
    rf-detr-nano.pth
```

Basket Lab sets `RF_HOME` to the absolute `models/rfdetr` path only when `RF_HOME` is not already defined. Consequently, a user-defined `RF_HOME` takes precedence and the checkpoint may be stored outside this directory.

`BASKET_MODEL_DIR` changes the application model directory, including the expected MediaPipe path and Basket Lab's fallback RF-DETR cache directory.

## Custom RF-DETR weights

Set `BASKET_RFDETR_WEIGHTS` to an absolute local checkpoint path before starting the server:

```powershell
$env:BASKET_RFDETR_WEIGHTS = "C:\models\basketball-rfdetr-nano.pth"
.\start.ps1
```

The checkpoint must be compatible with `RFDETRNano`. If it uses a custom label map, supply the basketball class number through the analysis API's `ball_class_id` field. Without that override, Basket Lab resolves the class ID by searching the bundled COCO labels for the exact name `sports ball`.

Use only checkpoints from a trusted source. Model checkpoints are parsed by the local ML framework and should be treated as executable inputs rather than passive media files.

## Input and output contract

The adapter is implemented in `basket/detectors.py`:

- Input: one BGR video frame from PyAV/OpenCV-style processing, converted to contiguous RGB before inference.
- Threshold: the session's configured detection confidence threshold.
- Filter: COCO `sports ball`, or the explicitly configured `ball_class_id`.
- Output per detection: center `x`/`y`, approximate `radius`, `confidence`, and `[x1, y1, x2, y2]` bounding box.

The downstream tracker records whether a location came directly from RF-DETR or from short-gap prediction. This distinction is retained in `frames.json` so detection coverage can be evaluated independently from interpolated tracking coverage.

## Operational limitations

- The COCO checkpoint is general purpose, not basketball-practice specific.
- Small balls, motion blur, hand occlusion, background balls, and distant trajectories can reduce recall or create false positives.
- CPU inference is supported but is not expected to keep up with 60 fps video in real time.
- Detection is two-dimensional and cannot establish whether the ball truly passed through the net.
- Confidence thresholds and tracking gates require validation against representative real footage.

For these reasons, Basket Lab presents reviewable proposals and preserves manual corrections instead of treating the detector output as ground truth.

## References

- [RF-DETR documentation](https://rfdetr.roboflow.com/)
- [RF-DETR source repository](https://github.com/roboflow/rf-detr)
- [DETR paper: End-to-End Object Detection with Transformers](https://arxiv.org/abs/2005.12872)
