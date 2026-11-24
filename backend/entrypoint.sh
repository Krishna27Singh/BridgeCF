#!/bin/sh
set -eu

export DATA_DIR="${DATA_DIR:-data}"

python - <<'PY'
import os
import tarfile
import urllib.request
from pathlib import Path

data_dir = Path(os.environ.get("DATA_DIR", "data"))
if not data_dir.is_absolute():
    data_dir = Path.cwd() / data_dir
data_dir.mkdir(parents=True, exist_ok=True)

database = data_dir / "bridgecf.db"
index = data_dir / "vector_database.index"
archive_url = os.environ.get("INDEX_ARCHIVE_URL", "").strip()

if archive_url and (not database.exists() or not index.exists()):
    archive = data_dir / ".bridgecf-index.tar.gz"
    try:
        urllib.request.urlretrieve(archive_url, archive)
        with tarfile.open(archive, "r:gz") as tar:
            root = data_dir.resolve()
            for member in tar.getmembers():
                if member.issym() or member.islnk():
                    raise RuntimeError("Links are not allowed in index archive")
                destination = (root / member.name).resolve()
                if root not in destination.parents and destination != root:
                    raise RuntimeError("Unsafe archive member path")
            tar.extractall(root)
        print("Hydrated BridgeCF index archive")
    except Exception as exc:
        print(f"Index archive hydration failed: {exc}")
    finally:
        archive.unlink(missing_ok=True)
PY

exec python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}"
