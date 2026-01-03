from pathlib import Path
import os

PROJECT_ROOT = Path(os.getenv('PROJECT_ROOT', os.getcwd())).resolve()
DB_ROOT_DIR = Path(os.getenv('DB_ROOT_DIR', PROJECT_ROOT / 'databases')).resolve()
DATA_DIRS = [PROJECT_ROOT, PROJECT_ROOT / 'data', PROJECT_ROOT / 'datasets']

def resolve_file(name, extra_dirs=None):
    dirs = DATA_DIRS + (extra_dirs or [])
    for d in dirs:
        p = (d / name).expanduser()
        if p.exists():
            return p
    return None

def resolve_db_path(db_name):
    candidates = [
        DB_ROOT_DIR / db_name / f"{db_name}.sqlite",
        DB_ROOT_DIR / f"{db_name}.sqlite",
        PROJECT_ROOT / 'databases' / db_name / f"{db_name}.sqlite",
        PROJECT_ROOT / 'databases' / f"{db_name}.sqlite",
        PROJECT_ROOT / f"{db_name}.sqlite",
    ]
    for p in candidates:
        p = p.expanduser()
        if p.exists():
            return p
    return None

def resolve_dataset_path(filename='kaggle_dataset.csv'):
    p = resolve_file(filename)
    if p is not None:
        return p
    envp = os.getenv('KAGGLE_DATASET_PATH')
    if envp:
        q = Path(envp).expanduser()
        if q.exists():
            return q
    return None

