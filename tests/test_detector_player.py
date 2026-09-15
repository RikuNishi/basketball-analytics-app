"""Test adapter contracts without loading ML dependencies or model weights."""
from types import SimpleNamespace as NS
import numpy as np
from basket.detectors import VisionDetectors
from basket.player import PlayerTracker


def adapter(automatic=True):
    detector = VisionDetectors.__new__(VisionDetectors)
    detector.automatic_person = automatic
    detector.player = PlayerTracker()
    detector.person_ids, detector.ball_ids = {0}, {1}
    detector.previous_ms = -1
    detector.config = NS(threshold=.35, person=None if automatic else NS(x=.2, y=.1, w=.4, h=.8))
    detector.mp = NS(Image=lambda **kwargs: kwargs['data'], ImageFormat=NS(SRGB='rgb'))
    detector.ball = NS(predict=lambda *_args, **_kwargs: NS(
        xyxy=[[40, 20, 80, 90], [100, 30, 110, 40]], confidence=[.9, .8], class_id=[0, 1]))
    return detector


def landmarks():
    return NS(pose_landmarks=[[NS(x=.5, y=.5, visibility=.9, presence=.8)]])


def test_automatic_crop_uses_image_mode_and_restores_full_frame_coordinates():
    detector = adapter()
    crops = []
    detector.pose = NS(detect=lambda image: (crops.append(image.shape), landmarks())[1])
    balls, pose = detector.predict(np.zeros((100, 200, 3), dtype=np.uint8), 0)
    assert crops == [(94, 56, 3)]
    assert pose == [[60, 53, .8]]
    assert balls[0]['x'] == 105


def test_missing_person_retains_ball_without_calling_pose():
    detector = adapter()
    detector.person_ids = {99}
    detector.pose = NS()  # Any accidental pose call must fail.
    balls, pose = detector.predict(np.zeros((100, 200, 3), dtype=np.uint8), 0)
    assert balls and pose is None


def test_manual_crop_preserves_video_mode_and_monotonic_timestamps():
    detector = adapter(False)
    timestamps = []
    detector.pose = NS(detect_for_video=lambda image, t: (timestamps.append(t), landmarks())[1])
    for _ in range(2):
        _, pose = detector.predict(np.zeros((100, 200, 3), dtype=np.uint8), 0)
    assert timestamps == [0, 1]
    assert pose == [[80, 50, .8]]
