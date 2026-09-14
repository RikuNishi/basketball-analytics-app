import csv
import io
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import importlib.util
import cv2
from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .store import ROOT, MODEL_DIR, save_json, load_json
from .schema import AnalysisConfig, ShotEdit
from .events import analyze_frames, summary
from .measure import measurements
from .tracking import BallTracker
from .video import probe
from .prediction import video_predictions
from .pipeline import process_session
from .render import render_video

app = FastAPI(title="Basket Lab", docs_url="/api/docs")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])
pool = ThreadPoolExecutor(max_workers=1)
lock = threading.RLock()
jobs = {}
STATIC = Path(__file__).parent/"static"


def directory(session_id):
    if not (session_id == "demo" or (len(session_id) == 32 and all(c in "0123456789abcdef" for c in session_id))):
        raise HTTPException(404, "セッションが見つかりません")
    result = ROOT/session_id
    if not (result/"session.json").exists():
        raise HTTPException(404, "セッションが見つかりません")
    return result


def idle(session_id):
    if any(j["session_id"] == session_id and j["status"] in ("queued", "running") for j in jobs.values()):
        raise HTTPException(409, "このセッションを処理中です。完了後に操作してください")


def launch(session_id, operation):
    with lock:
        idle(session_id)
        job_id = uuid4().hex
        jobs[job_id] = {"id": job_id, "session_id": session_id, "status": "queued", "progress": 0, "message": "順番待ち"}

    def run():
        def progress(value, message):
            with lock:
                jobs[job_id].update(status="running", progress=value, message=message)
        try:
            progress(0, "処理を開始")
            operation(progress)
            with lock:
                jobs[job_id].update(status="complete", progress=1, message="完了")
        except Exception as exc:
            logging.exception("Session job failed")
            with lock:
                jobs[job_id].update(status="failed", message=str(exc))
    pool.submit(run)
    return dict(jobs[job_id])


@app.get("/api/health")
def health():
    vision = all(importlib.util.find_spec(name) is not None for name in ("mediapipe", "rfdetr"))
    return {"ok": True, "vision_installed": vision, "pose_model_ready": (MODEL_DIR/"pose_landmarker_lite.task").exists()}


@app.get("/api/sessions")
def list_sessions():
    ROOT.mkdir(parents=True, exist_ok=True)
    sessions = [load_json(p) for p in ROOT.glob("*/session.json")]
    return sorted(sessions, key=lambda s: s["created_at"], reverse=True)


@app.post("/api/sessions")
def upload(file: UploadFile):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"):
        raise HTTPException(400, "MP4 / MOV / M4V / AVI / MKV / WebM を選択してください")
    session_id = uuid4().hex
    folder = ROOT/session_id
    folder.mkdir(parents=True)
    source = folder/("source"+suffix)
    try:
        size = 0
        with source.open("wb") as output:
            while chunk := file.file.read(1024*1024):
                size += len(chunk)
                if size > 2*1024**3:
                    raise ValueError("動画は2GB以内にしてください")
                output.write(chunk)
        metadata, first = probe(source)
        cv2.imwrite(str(folder/"thumbnail.jpg"), first)
    except Exception as exc:
        source.unlink(missing_ok=True)
        raise HTTPException(400, str(exc)) from exc
    finally:
        file.file.close()
    session = {"id": session_id, "name": file.filename, "is_demo": False,
               "created_at": datetime.now(timezone.utc).isoformat(), "source_file": source.name,
               "status": "uploaded", "video": metadata, "config": None,
               "shots": [], "summary": summary([]), "quality": None, "revision": 0, "rendered_revision": -1}
    save_json(folder/"session.json", session)
    return session


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    return load_json(directory(session_id)/"session.json")


@app.get("/api/sessions/{session_id}/frames")
def get_frames(session_id: str):
    path = directory(session_id)/"frames.json"
    if not path.exists():
        raise HTTPException(409, "まだ解析されていません")
    return FileResponse(path, media_type="application/json")


@app.post("/api/sessions/{session_id}/analyze")
def analyze(session_id: str, config: AnalysisConfig):
    folder = directory(session_id)
    if session_id == "demo":
        raise HTTPException(400, "デモ動画を実動画解析には使用しません。練習動画を読み込んでください")
    return launch(session_id, lambda progress: process_session(folder, config, MODEL_DIR, progress))


@app.get("/api/sessions/{session_id}/predictions")
def get_predictions(session_id: str):
    folder = directory(session_id)
    with lock:
        session = load_json(folder/"session.json")
        if not session.get("config") or not (folder/"frames.json").exists():
            raise HTTPException(409, "まだ解析されていません")
        return video_predictions(load_json(folder/"frames.json"), session)


@app.post("/api/sessions/{session_id}/recompute")
def recompute(session_id: str):
    folder = directory(session_id)
    with lock:
        idle(session_id)
        session = load_json(folder/"session.json")
        if not session.get("config") or not (folder/"frames.json").exists():
            raise HTTPException(409, "再計算には解析済みデータが必要です")
        frames = load_json(folder/"frames.json")
        config = AnalysisConfig(**session["config"])
        # Proposals are exported separately; existing human edits stay intact.
        proposals = analyze_frames(frames, config, session["video"]["width"], session["video"]["height"])
        save_json(folder/"proposals.json", {"shots": proposals, "summary": summary(proposals)})
    return {"url": f"/api/sessions/{session_id}/files/proposals.json", "attempts": len(proposals)}


@app.patch("/api/sessions/{session_id}/shots/{shot_id}")
def edit_shot(session_id: str, shot_id: int, edit: ShotEdit):
    folder = directory(session_id)
    with lock:
        idle(session_id)
        session = load_json(folder/"session.json")
        shot = next((s for s in session["shots"] if s["id"] == shot_id), None)
        if not shot:
            raise HTTPException(404, "シュートが見つかりません")
        if not shot["start_s"] <= edit.release_s <= shot["end_s"]:
            raise HTTPException(422, "リリース時刻はシュート区間内で指定してください")
        history = load_json(folder/"edits.json") if (folder/"edits.json").exists() else []
        history.append({"at": datetime.now(timezone.utc).isoformat(), "revision": session["revision"], "shot_id": shot_id, "before": dict(shot), "after": edit.model_dump()})
        shot.update(edit.model_dump(), reviewed=True)
        frames = load_json(folder/"frames.json")
        shot["release_frame"] = min(range(len(frames)), key=lambda i: abs(frames[i]["t"]-edit.release_s))
        shot["release_s"] = frames[shot["release_frame"]]["t"]
        session["summary"] = summary(session["shots"])
        session["revision"] += 1
        save_json(folder/"edits.json", history)
        save_json(folder/"session.json", session)
    return session


@app.post("/api/sessions/{session_id}/render")
def export_video(session_id: str):
    folder = directory(session_id)
    if not (folder/"frames.json").exists():
        raise HTTPException(409, "まだ解析されていません")
    def operation(progress):
        session = load_json(folder/"session.json")
        render_video(folder/session["source_file"], folder/"annotated-next.mp4", load_json(folder/"frames.json"), session,
                     lambda p: progress(p, "修正を反映した動画を書き出し中"))
        (folder/"annotated-next.mp4").replace(folder/"annotated.mp4")
        session["rendered_revision"] = session["revision"]
        save_json(folder/"session.json", session)
    return launch(session_id, operation)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    with lock:
        if job_id not in jobs:
            raise HTTPException(404, "ジョブが見つかりません")
        return dict(jobs[job_id])


@app.get("/api/sessions/{session_id}/shots.csv")
def export_csv(session_id: str):
    folder = directory(session_id)
    session = load_json(folder/"session.json")
    frames = load_json(folder/"frames.json") if (folder/"frames.json").exists() else []
    output = io.StringIO(newline="")
    columns = ["id", "release_s", "start_s", "end_s", "outcome", "auto_outcome", "candidate", "reviewed", "deleted", "elbow_deg_2d", "knee_deg_2d", "trunk_deg_2d", "is_demo", "note"]
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for shot in session["shots"]:
        angles = frames[shot["release_frame"]].get("angles", {}) if frames else {}
        row = {key: shot.get(key, "") for key in columns}
        row.update({f"{key}_2d": value for key, value in angles.items()})
        row["is_demo"] = session["is_demo"]
        # Spreadsheet-formula injection protection for user-entered text.
        if str(row["note"]).startswith(("=", "+", "-", "@", "\t", "\r")):
            row["note"] = "'"+row["note"]
        writer.writerow(row)
    return Response(output.getvalue().encode("utf-8-sig"), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="shots.csv"'})


@app.get("/api/sessions/{session_id}/files/{filename}")
def file_download(session_id: str, filename: str):
    folder = directory(session_id)
    allowed = {"preview.mp4", "annotated.mp4", "thumbnail.jpg", "frames.json", "session.json", "edits.json", "proposals.json"}
    if filename not in allowed or not (folder/filename).exists():
        raise HTTPException(404, "ファイルがありません")
    return FileResponse(folder/filename)


app.mount("/", StaticFiles(directory=STATIC, html=True), name="frontend")
