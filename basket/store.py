import json
import os
from pathlib import Path
from uuid import uuid4

ROOT = Path(os.environ.get("BASKET_DATA_DIR", Path(__file__).resolve().parent.parent/"data")).resolve()
MODEL_DIR = Path(os.environ.get("BASKET_MODEL_DIR", Path(__file__).resolve().parent.parent/"models")).resolve()


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+f".{uuid4().hex}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")), encoding="utf-8")
    os.replace(temporary, path)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
