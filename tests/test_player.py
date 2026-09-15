from basket.player import PlayerTracker
from basket.schema import AnalysisConfig


def test_tracks_movement_with_padded_image_bounds():
    tracker = PlayerTracker()
    first = tracker.update([[0, 20, 80, 180]], 0, 640, 480)
    second = tracker.update([[60, 10, 140, 200]], .1, 640, 480)
    assert first[0] == 0
    assert second[2] > first[2] and second[2] >= 140
    assert second[1] <= 10 and second[3] >= 200


def test_missing_player_has_no_crop_and_can_reenter_elsewhere():
    tracker = PlayerTracker()
    tracker.update([[10, 20, 90, 200]], 0, 640, 480)
    assert tracker.update([], .2, 640, 480) is None
    assert tracker.update([[500, 20, 580, 200]], 1, 640, 480) is not None


def test_ambiguity_and_invalid_boxes_produce_missing_measurements():
    tracker = PlayerTracker()
    assert tracker.update([[0, 0, 20, 20], [30, 0, 50, 20]], 0, 640, 480) is None
    assert tracker.update([[0, 0, float('nan'), 50]], .1, 640, 480) is None
    assert tracker.update([[900, 0, 1000, 50]], .2, 640, 480) is None


def test_configuration_defaults_to_auto_and_keeps_manual_compatibility():
    rim = {'x': .4, 'y': .3, 'w': .1, 'h': .02}
    assert AnalysisConfig(rim=rim).person is None
    assert AnalysisConfig(rim=rim, person={'x': 0, 'y': 0, 'w': 1, 'h': 1}).person.w == 1


def test_small_background_detections_do_not_block_dominant_player():
    tracker = PlayerTracker()
    assert tracker.update([[10, 20, 110, 220], [400, 30, 420, 70]], 0, 640, 480)
    result = tracker.update([[40, 20, 140, 220], [400, 30, 420, 70]], .1, 640, 480)
    assert result and result[0] < 40 and result[2] >= 140


def test_lone_small_false_positive_cannot_replace_tracked_player():
    tracker = PlayerTracker()
    tracker.update([[100, 100, 200, 400]], 0, 640, 480)
    assert tracker.update([[140, 150, 155, 175]], .1, 640, 480) is None
    assert tracker.update([[110, 100, 210, 400]], .2, 640, 480)


def test_custom_class_requires_manual_region():
    import pytest
    with pytest.raises(ValueError):
        AnalysisConfig(rim={'x': .4, 'y': .3, 'w': .1, 'h': .02}, ball_class_id=0)
