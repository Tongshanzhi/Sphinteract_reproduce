import sqlite3
import os
from multiprocessing import Process, Queue

def execute_query_worker(db_path, sql, output):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        results = cursor.execute(sql).fetchall()
        conn.close()
        output.put(results)
    except Exception as e:
        output.put(e)

def evalfunc(sql_source, sql_target, db_path):
    if not os.path.isfile(db_path):
        return False, [FileNotFoundError(f"Database not found: {db_path}")]
    timeout = 30
    output = Queue()
    p = Process(target=execute_query_worker, args=(db_path, sql_source, output))
    p.start()
    try:
        source_results = output.get(timeout=timeout)
        p.join()
        if isinstance(source_results, Exception):
            return False, [source_results]
    except Exception as e:
        p.terminate()
        return False, [e]
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        target_results = cursor.execute(sql_target).fetchall()
        conn.close()
    except Exception as e:
        return False, [e]
    if len(source_results) != len(target_results):
        return False, []
    if 'ORDER BY' in sql_target.upper():
        return source_results == target_results, []
    s_sorted = sorted(list(source_results), key=lambda x: str(x))
    t_sorted = sorted(list(target_results), key=lambda x: str(x))
    return s_sorted == t_sorted, []

