"""Exercise actual upload, decode, pipeline, render and export with a fake ML boundary."""
import time
import numpy as np
from fastapi.testclient import TestClient
from basket import server, pipeline
from basket.video import VideoWriter, read_frames
from basket.store import load_json


def test_upload_analysis_render_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(server,"ROOT",tmp_path/"sessions")
    class EmptyDetectors:
        def __init__(self,*args): pass
        def predict(self,image,t): return [],None
        def close(self): pass
    monkeypatch.setattr(pipeline,"VisionDetectors",EmptyDetectors)
    source=tmp_path/"tiny.mp4"
    with VideoWriter(source,96,64,30) as writer:
        for i in range(9): writer.write(np.zeros((64,96,3),dtype=np.uint8),i/30)
    with TestClient(server.app) as client:
        result=client.post("/api/sessions",files={"file":("tiny.mp4",source.read_bytes(),"video/mp4")})
        assert result.status_code==200
        session_id=result.json()["id"]
        prefix=f"/api/sessions/{session_id}"
        assert result.json()["status"]=="uploaded"
        assert client.get(prefix+"/files/thumbnail.jpg").status_code==200
        job=client.post(prefix+"/analyze",json={"rim":{"x":.7,"y":.2,"w":.1,"h":.05},"person":{"x":.1,"y":.1,"w":.4,"h":.8}}).json()
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            status=client.get(f"/api/jobs/{job['id']}").json()
            if status["status"] in ("complete","failed"): break
            time.sleep(.05)
        assert status["status"]=="complete",status
        session=client.get(prefix).json()
        assert session["summary"]["attempts"]==0
        assert session["quality"]["pose_coverage"]==0
        assert session["status"]=="ready"
        folder=server.ROOT/session_id
        assert len(load_json(folder/"frames.json"))==9
        assert len(list(read_frames(folder/"annotated.mp4")))==9
        assert client.get(prefix+"/files/preview.mp4",headers={"Range":"bytes=0-99"}).status_code==206
        assert client.post(prefix+"/recompute").json()["attempts"]==0
        # Re-analysis failure must retain the previous raw measurements and metadata.
        before_session=(folder/"session.json").read_bytes()
        before_frames=(folder/"frames.json").read_bytes()
        def failed_render(*args,**kwargs):
            raise RuntimeError("test render failure")
        monkeypatch.setattr(pipeline,"render_video",failed_render)
        from basket.schema import AnalysisConfig
        import pytest
        with pytest.raises(RuntimeError,match="test render failure"):
            pipeline.process_session(folder,AnalysisConfig(**session["config"]),tmp_path,lambda *_:None)
        assert (folder/"session.json").read_bytes()==before_session
        assert (folder/"frames.json").read_bytes()==before_frames
        assert (folder/"history"/"revision-1"/"session.json").exists()
