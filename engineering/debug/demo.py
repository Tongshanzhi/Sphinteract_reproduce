import functools
import inspect
import os
import sqlite3
from ..db.schema import generate_db_schema
from ..utils.sanitize import clean_query

def debug_wrapper(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print(f"=== Calling {func.__name__} ===")
        try:
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            print("Inputs:")
            for k, v in bound.arguments.items():
                s = str(v)
                if len(s) > 500:
                    s = s[:500] + "..."
                print(f" - {k}: {s}")
        except Exception:
            pass
        try:
            out = func(*args, **kwargs)
            s = str(out)
            if len(s) > 500:
                s = s[:500] + "..."
            print(f"Output: {s}")
            return out
        except Exception as e:
            print(f"Exception: {e}")
            raise
        finally:
            print(f"=== End {func.__name__} ===")
    return wrapper

def run_debug_demo():
    db_path = "debug_demo.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER, role TEXT)")
    conn.execute("INSERT INTO users (name, age, role) VALUES ('Alice', 30, 'admin'), ('Bob', 25, 'user'), ('Charlie', 35, 'user')")
    conn.commit()
    conn.close()
    dbg_generate_schema = debug_wrapper(generate_db_schema)
    dbg_clean_query = debug_wrapper(clean_query)
    @debug_wrapper
    def mock_llm_generation(prompt):
        return "```sql\nSELECT name FROM users WHERE age > 20 AND role = 'user'\n```", 0.0
    schema = dbg_generate_schema(db_path)
    user_question = "Find all users older than 20."
    prompt = f"Question: {user_question}\nSchema: {schema}"
    raw_sql_output, _ = mock_llm_generation(prompt)
    cleaned_sql = dbg_clean_query(raw_sql_output)
    try:
        conn = sqlite3.connect(db_path)
        res = conn.execute(cleaned_sql).fetchall()
        print(f"{res}")
        conn.close()
    except Exception as e:
        print(f"{e}")
    if os.path.exists(db_path):
        os.remove(db_path)

