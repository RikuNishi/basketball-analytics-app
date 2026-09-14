"""Optional local ML adapters; imports do not affect demo/review mode."""
from pathlib import Path
import os
import numpy as np


class VisionDetectors:
    def __init__(self, config, model_dir):
        try:
            import mediapipe as mp
            from rfdetr import RFDETRNano
            from rfdetr.assets.coco_classes import COCO_CLASSES
        except ImportError as exc:
            raise RuntimeError("解析用ライブラリがありません。setup.ps1 -Vision を実行してください") from exc
        self.mp, self.config = mp, config
        model_path = Path(model_dir)/"pose_landmarker_lite.task"
        if not model_path.exists():
            raise RuntimeError("姿勢モデルがありません。python -m basket.cli setup-models を実行してください")
        weights = os.environ.get("BASKET_RFDETR_WEIGHTS")
        kwargs = {"pretrain_weights": weights} if weights else {}
        os.environ.setdefault("RF_HOME", str(Path(model_dir).resolve()/"rfdetr"))
        self.ball = RFDETRNano(**kwargs)
        if config.ball_class_id is not None:
            self.ball_ids = {config.ball_class_id}
        else:
            entries = COCO_CLASSES.items() if isinstance(COCO_CLASSES, dict) else enumerate(COCO_CLASSES)
            self.ball_ids = {int(i) for i, label in entries if label == "sports ball"}
        if not self.ball_ids:
            raise RuntimeError("モデルのボールクラスが見つかりません")
        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO, num_poses=1)
        self.pose = mp.tasks.vision.PoseLandmarker.create_from_options(options)
        self.previous_ms = -1

    def predict(self, image, t):
        h, w = image.shape[:2]
        rgb = np.ascontiguousarray(image[:, :, ::-1])
        detections = self.ball.predict(rgb, threshold=self.config.threshold)
        balls = []
        for box, confidence, class_id in zip(detections.xyxy, detections.confidence, detections.class_id):
            if int(class_id) in self.ball_ids:
                x1, y1, x2, y2 = [float(v) for v in box]
                balls.append({"x": (x1+x2)/2, "y": (y1+y2)/2, "radius": max(x2-x1, y2-y1)/2,
                              "confidence": float(confidence), "bbox": [x1, y1, x2, y2]})
        # Fixed one-person ROI prevents selecting a bystander outside the configured area.
        r = self.config.person
        x0, y0 = int(r.x*w), int(r.y*h)
        x1, y1 = max(x0+1, min(w, round((r.x+r.w)*w))), max(y0+1, min(h, round((r.y+r.h)*h)))
        crop = np.ascontiguousarray(rgb[y0:y1, x0:x1])
        self.previous_ms = max(self.previous_ms+1, round(t*1000))
        result = self.pose.detect_for_video(self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=crop), self.previous_ms)
        pose = None
        if result.pose_landmarks:
            pose = [[p.x*(x1-x0)+x0, p.y*(y1-y0)+y0, min(p.visibility, p.presence)] for p in result.pose_landmarks[0]]
        return balls, pose

    def close(self):
        self.pose.close()
