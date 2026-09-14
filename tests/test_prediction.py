import copy
import numpy as np
from basket.prediction import video_predictions


def example():
    frames = [{'index': i, 't': i/30, 'ball': {'source': 'detected', 'x': 100+200*i/30,
               'y': 350-300*i/30+180*(i/30)**2}} for i in range(50)]
    session = {'video': {'width': 960, 'height': 540}, 'config': {'max_gap_s': .12,
               'rim': {'y': .4, 'h': .04}}, 'shots': [{'release_s': 0, 'end_s': 2}]}
    return frames, session


def test_forecast_uses_only_past_observations():
    frames, session = example()
    result = video_predictions(frames, session)
    assert result[10] == video_predictions(frames[:11], session)[10]
    future = copy.deepcopy(frames)
    for f in future[11:]:
        f['ball']['x'] = 900
    assert result[10] == video_predictions(future, session)[10]
    t = 10/30+.6
    assert np.allclose(result[10][-1], [100+200*t, 350-300*t+180*t*t], atol=.01)


def test_no_prediction_on_missing_or_short_tracks():
    frames, session = example()
    for f in frames[7:14]:
        f['ball']['source'] = 'predicted'
    result = video_predictions(frames, session)
    assert not any(i in result for i in range(7, 19))
    assert 20 in result
    session['shots'][0]['deleted'] = True
    assert not video_predictions(frames, session)


def test_stops_after_descending_past_rim():
    frames, session = example()
    result = video_predictions(frames, session)
    assert 25 in result
    assert not any(i in result for i in range(32, 50))
