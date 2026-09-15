import numpy as np
from basket.default_session import prepare_default
from basket.store import save_json


def test_missing_clip_does_not_generate_synthetic_data(tmp_path):
    assert prepare_default(tmp_path) is None
    assert not (tmp_path/'demo').exists()


def test_real_default_is_registered_once_and_preserves_analysis(tmp_path, monkeypatch):
    folder = tmp_path/'demo'
    folder.mkdir()
    (folder/'single_three_point.mov').touch()
    monkeypatch.setattr('basket.default_session.probe', lambda _: ({'width': 16, 'height': 16}, np.zeros((16, 16, 3), dtype=np.uint8)))
    session = prepare_default(tmp_path)
    assert session['is_demo'] is False
    assert session['shots'] == [] and session['status'] == 'uploaded'
    session.update(status='ready', revision=7)
    save_json(folder/'session.json', session)
    assert prepare_default(tmp_path)['revision'] == 7
