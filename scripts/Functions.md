def clean_query(sql_query):
    # Remove markdown code blocks
    pattern = r"```sql(.*?)```"
    match = re.search(pattern, sql_query, re.DOTALL | re.IGNORECASE)
    if match:
        sql_query = match.group(1)
    else:
        sql_query = sql_query.replace("```sql", '').replace("```", '')

    sql_query = sql_query.replace(';', '')
    sql_query = sql_query.replace('"""', '')
    
    # Find the start of the SQL statement (SELECT or WITH)
    match_select = re.search(r'\bSELECT\b', sql_query, re.IGNORECASE)
    match_with = re.search(r'\bWITH\b', sql_query, re.IGNORECASE)
    
    start_index = -1
    if match_with and match_select:
        start_index = min(match_with.start(), match_select.start())
    elif match_with:
        start_index = match_with.start()
    elif match_select:
        start_index = match_select.start()
        
    if start_index != -1:
        sql_query = sql_query[start_index:]
    else:
        # If no SELECT/WITH found, assume it's a completion and prepend SELECT
        # But ensure we don't double prepend if the user output " * FROM ..."
        if 'FROM' in sql_query.upper():
             sql_query = 'SELECT ' + sql_query
        else:
             # Fallback: just prepend SELECT
             sql_query = 'SELECT ' + sql_query
             
    return sql_query.strip()

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

def evalfunc(sql_source, sql_target, db_path):
    if not os.path.isfile(db_path):
        return False, [FileNotFoundError(f"Database not found: {db_path}")]
    
    timeout = 30 # seconds
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
        
    # Execute Gold SQL (Target) - assumed safe and fast
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        target_results = cursor.execute(sql_target).fetchall()
        conn.close()
    except Exception as e:
        return False, [e]

    # Compare results
    if len(source_results) != len(target_results):
        return False, []
        
    # Heuristic comparison (order-independent if no ORDER BY, else strict)
    if 'ORDER BY' in sql_target.upper():
        return source_results == target_results, []
    else:
        # Sort both by a stable key (str representation)
        s_sorted = sorted(list(source_results), key=lambda x: str(x))
        t_sorted = sorted(list(target_results), key=lambda x: str(x))
        return s_sorted == t_sorted, []

def LLM_generation(prompt, model='gpt-3.5-turbo', temperature=0.0, retries=3, retry_delay=1.5, log_each_retry=False, fallback_models=None):
    last_err = None
    models_to_try = [model]
    if fallback_models is None:
        fallback_models = [os.getenv("AMBIGUITY_MODEL", "gpt-4o-mini"), "gpt-4o"]
    for m in fallback_models:
        if m not in models_to_try:
            models_to_try.append(m)
    for try_model in models_to_try:
        for attempt in range(retries):
            try:
                response = client.chat.completions.create(
                    model=try_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=4096
                )
                return response.choices[0].message.content.strip(), 0.0
            except Exception as e:
                last_err = e
                err_str = str(e)
                l = err_str.lower()
                if "502" in err_str or "bad gateway" in l:
                    err_label = "502 Bad Gateway"
                elif "429" in err_str or "too many requests" in l or "rate limit" in l:
                    err_label = "rate_limit"
                elif "timeout" in l or "timed out" in l:
                    err_label = "timeout"
                elif "connection reset" in l or "reset by peer" in l:
                    err_label = "conn_reset"
                elif "ssl" in l:
                    err_label = "ssl_error"
                elif "unauthorized" in l or "401" in err_str:
                    err_label = "unauthorized"
                elif "model" in l and "not found" in l:
                    err_label = "model_not_found"
                else:
                    err_label = "error"
                if log_each_retry:
                    print(f"LLM error ({err_label}), retry {attempt+1}/{retries}")
                time.sleep(retry_delay * (1.5 ** attempt))
    if last_err is not None:
        err_str = str(last_err)
        l = err_str.lower()
        if "502" in err_str or "bad gateway" in l:
            err_label = "502 Bad Gateway"
        elif "429" in err_str or "too many requests" in l or "rate limit" in l:
            err_label = "rate_limit"
        elif "timeout" in l or "timed out" in l:
            err_label = "timeout"
        elif "connection reset" in l or "reset by peer" in l:
            err_label = "conn_reset"
        elif "ssl" in l:
            err_label = "ssl_error"
        elif "unauthorized" in l or "401" in err_str:
            err_label = "unauthorized"
        elif "model" in l and "not found" in l:
            err_label = "model_not_found"
        else:
            err_label = "error"
        print(f"LLM error ({err_label}); giving up")
    return "SELECT * FROM error", 0.0