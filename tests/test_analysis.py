import math
import pytest
from basket.measure import angle, measurements
from basket.tracking import BallTracker
from basket.events import analyze_frames, outcome_evidence, summary
from basket.schema import AnalysisConfig, Region
from basket.demo import sample


@pytest.fixture
def config():
    return AnalysisConfig(rim={"x":729/960,"y":167/540,"w":60/960,"h":20/540},
                          person={"x":.2,"y":.35,"w":.22,"h":.5})


def test_angles_and_low_visibility():
    assert angle((0,1),(0,0),(1,0)) == 90
    assert angle((0,0),(0,0),(1,0)) is None
    assert measurements(None,"right")["elbow_deg"] is None
    pose, _ = sample(0)
    pose[14][2] = .1
    assert measurements(pose,"right")["elbow_deg"] is None


def detection(x,y):
    return {"x":x,"y":y,"radius":5,"confidence":.9}


def test_tracking_short_prediction_and_long_gap():
    tracker=BallTracker(1000,.12)
    assert tracker.update([detection(100,100)],0)["source"] == "detected"
    tracker.update([detection(110,90)],.03)
    assert tracker.update([],.06)["source"] == "predicted"
    assert tracker.update([],.16) is None
    assert tracker.update([detection(800,500)],.2)["source"] == "detected"


def test_tracker_rejects_distant_false_positive():
    tracker=BallTracker(1000,.12)
    tracker.update([detection(100,100)],0)
    result=tracker.update([detection(800,100)],.03)
    assert result["source"] == "predicted"
    assert result["x"] == 100


def synthetic_frames(duration=26.4):
    tracker=BallTracker(math.hypot(960,540))
    frames=[]
    for i in range(round(duration*30)):
        t=i/30
        pose, ball=sample(t)
        frames.append({"index":i,"t":t,"pose":pose,"ball":tracker.update([ball] if ball else [],t)})
    return frames


def test_repeated_shots_have_one_release_each(config):
    shots=analyze_frames(synthetic_frames(),config,960,540)
    assert len(shots)==6
    assert all(abs(s["release_s"]-(i*4.4+1))<.2 for i,s in enumerate(shots))
    assert all(s["outcome"]!="made" for s in shots)
    assert shots[2]["outcome"]=="missed"
    assert shots[4]["outcome"]=="unknown"


def test_dribble_is_not_a_shot(config):
    frames=synthetic_frames(4)
    for frame in frames:
        if frame["t"]>1 and frame["ball"]:
            frame["ball"]["y"]=300+frame["t"]*40
    assert analyze_frames(frames,config,960,540)==[]


def test_no_wrist_evidence_does_not_create_attempt(config):
    frames=synthetic_frames(4)
    for frame in frames:
        frame["pose"]=None
    assert analyze_frames(frames,config,960,540)==[]


def test_projection_through_rim_needs_review(config):
    frames=[{"t":i*.03,"ball":{**detection(759,150+i*15),"source":"detected"}} for i in range(8)]
    outcome,_,candidate=outcome_evidence(frames,config.rim,960,540,.12)
    assert outcome=="unknown"
    assert candidate=="made"


def test_predicted_crossing_and_long_gap_never_confirm_success(config):
    frames=[{"t":i*.5,"ball":{**detection(759,140+i*40),"source":"detected"}} for i in range(4)]
    assert outcome_evidence(frames,config.rim,960,540,.12)[0]=="unknown"
    for f in frames:
        f["ball"]["source"]="predicted"
    assert outcome_evidence(frames,config.rim,960,540,.12)[2] is None


def test_success_rate_excludes_unknown_and_deleted():
    shots=[{"outcome":"made"},{"outcome":"missed"},{"outcome":"unknown"},{"outcome":"made","deleted":True}]
    result=summary(shots)
    assert result["attempts"]==3
    assert result["denominator"]==2
    assert result["percentage"]==50
    assert summary([{"outcome":"unknown"}])["percentage"] is None


def test_invalid_region_rejected():
    with pytest.raises(ValueError):
        Region(x=.9,y=0,w=.2,h=.1)
