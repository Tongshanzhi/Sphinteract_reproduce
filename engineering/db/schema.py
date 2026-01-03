import sqlite3

def generate_db_schema(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    schemas = []
    for table in tables:
        if table[0] == 'sqlite_sequence':
            continue
        cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table[0]}'")
        create_prompt = cursor.fetchone()[0]
        schemas.append(create_prompt)
    conn.close()
    return "\n\n".join(schemas)

