import os
from pathlib import Path

def _load_env():
    env_files = [Path(__file__).parent / ".env", Path(os.getcwd()) / ".env"]
    for p in env_files:
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                if "=" in s:
                    k, v = s.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    if v.startswith('"') and v.endswith('"'):
                        v = v[1:-1]
                    if v.startswith("'") and v.endswith("'"):
                        v = v[1:-1]
                    cur = os.environ.get(k)
                    if k and v and (cur is None or cur.strip() == ""):
                        os.environ[k] = v

_load_env()
