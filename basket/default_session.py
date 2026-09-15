"""Register the user-provided real clip without fabricating measurements."""
from datetime import datetime, timezone
import cv2
from .store import load_json, save_json
from .video import probe
from .events import summary


def prepare_default(root):
    folder = root/'demo'
    source = folder/'single_three_point.mov'
    if not source.exists():
        return None
    if (folder/'session.json').exists():
        current = load_json(folder/'session.json')
        if not current.get('is_demo') and current.get('source_file') == source.name:
            return current
        save_json(folder/'history'/'previous-default-session.json', current)
    metadata, first = probe(source)
    cv2.imwrite(str(folder/'thumbnail.jpg'), first)
    session = {'id': 'demo', 'name': source.name, 'is_demo': False, 'status': 'uploaded',
               'created_at': datetime.now(timezone.utc).isoformat(), 'source_file': source.name,
               'video': metadata, 'config': None, 'shots': [], 'summary': summary([]),
               'quality': None, 'revision': 0, 'rendered_revision': -1}
    save_json(folder/'session.json', session)
    return session
