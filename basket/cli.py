import argparse
import urllib.request
from .store import ROOT, MODEL_DIR


def main():
    parser = argparse.ArgumentParser(description="Basket Lab · ローカル動画解析")
    parser.add_argument("command", choices=["serve", "demo", "setup-models"], nargs="?", default="serve")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.command == "setup-models":
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        path = MODEL_DIR/"pose_landmarker_lite.task"
        url = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
        if not path.exists():
            temporary = path.with_suffix(".download")
            urllib.request.urlretrieve(url, temporary)
            temporary.replace(path)
        print(f"Pose model: {path}")
        print("RF-DETR weights are downloaded by RF-DETR on first analysis.")
    elif args.command == "demo":
        from .demo import create_demo
        session = create_demo(ROOT/"demo")
        print(f"Synthetic demo ready: {session['summary']}")
    else:
        import uvicorn
        from .demo import create_demo
        create_demo(ROOT/"demo")
        uvicorn.run("basket.server:app", host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
