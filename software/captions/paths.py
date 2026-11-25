"""Local (never committed) locations for models, clips and logs."""
import os

ROOT = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~/.local/share")), "POVColumn", "captions")
MODELS_DIR = os.path.join(ROOT, "models")
CLIPS_DIR = os.path.join(ROOT, "clips")
LOG_DIR = os.path.join(ROOT, "logs")
HERE = os.path.dirname(os.path.abspath(__file__))
SOFTWARE = os.path.dirname(HERE)
OUT_DIR = os.path.join(SOFTWARE, "out", "captions")
for _d in (MODELS_DIR, CLIPS_DIR, LOG_DIR):
    os.makedirs(_d, exist_ok=True)
