import csv
import io
import json
import pytest
from fastapi.testclient import TestClient
from basket import server
from basket.store import save_json, load_json


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(server,"ROOT",tmp_path)
    folder=tmp_path/"demo"
    session={"id":"demo","name":"Synthetic API test","is_demo":True,"created_at":"2026-01-01", "status":"ready",
             "video":{"duration_s":3,"width":960,"height":540},"revision":1,"rendered_revision":1,
             "shots":[{"id":1,"start_s":0,"end_s":3,"release_s":1,"release_frame":1,
                       "outcome":"unknown","auto_outcome":"unknown","reviewed":False,"deleted":False}],
             "summary":{},"config":{"rim":{"x":.7,"y":.2,"w":.1,"h":.02},"person":{"x":.1,"y":.1,"w":.3,"h":.8}}}
    save_json(folder/"session.json",session)
    save_json(folder/"frames.json",[{"t":i,"angles":{"elbow_deg":90+i,"knee_deg":170,"trunk_deg":3}} for i in range(4)])
    with TestClient(server.app) as client:
        yield client,folder


def test_edit_persists_audit_and_updates_export(client):
    web,folder=client
    result=web.patch("/api/sessions/demo/shots/1",json={"outcome":"made","release_s":1.2,"note":"=SUM(A1)"})
    assert result.status_code==200
    assert result.json()["summary"]["percentage"]==100
    assert result.json()["shots"][0]["release_s"]==1
    assert result.json()["revision"]==2
    assert result.json()["rendered_revision"]==1
    assert load_json(folder/"edits.json")[0]["before"]["outcome"]=="unknown"
    content=web.get("/api/sessions/demo/shots.csv").content.decode("utf-8-sig")
    row=list(csv.DictReader(io.StringIO(content)))[0]
    assert row["outcome"]=="made"
    assert row["note"].startswith("'=")
    assert row["elbow_deg_2d"]=="91"
    assert row["is_demo"]=="True"


def test_deletion_and_restore(client):
    web,_=client
    path="/api/sessions/demo/shots/1"
    result=web.patch(path,json={"outcome":"made","release_s":1,"deleted":True})
    assert result.json()["summary"]["attempts"]==0
    result=web.patch(path,json={"outcome":"made","release_s":1,"deleted":False})
    assert result.json()["summary"]["attempts"]==1


def test_validation_and_file_allowlist(client):
    web,_=client
    assert web.patch("/api/sessions/demo/shots/1",json={"outcome":"made","release_s":100}).status_code==422
    assert web.get("/api/sessions/demo/files/source.mp4").status_code==404
    assert web.get("/api/sessions/invalid-id").status_code==404
    assert web.post("/api/sessions",files={"file":("a.txt",b"test")}).status_code==400


def test_edit_busy_session_rejected(client):
    web,_=client
    server.jobs["test"]={"session_id":"demo","status":"running"}
    try:
        assert web.patch("/api/sessions/demo/shots/1",json={"outcome":"made","release_s":1}).status_code==409
    finally:
        del server.jobs["test"]
