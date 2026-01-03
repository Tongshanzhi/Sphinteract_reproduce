from .schema import generate_db_schema
from ..io.paths import resolve_db_path

db_schema_cache = {}

def get_schema(db_name):
    if db_name not in db_schema_cache:
        db_path = resolve_db_path(db_name)
        if db_path is not None:
            db_schema_cache[db_name] = generate_db_schema(str(db_path))
        else:
            db_schema_cache[db_name] = ""
    return db_schema_cache[db_name]

def get_db_path(db_name):
    p = resolve_db_path(db_name)
    return str(p) if p is not None else None

