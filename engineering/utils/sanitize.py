import re

def clean_query(sql_query):
    pattern = r"```sql(.*?)```"
    match = re.search(pattern, sql_query, re.DOTALL | re.IGNORECASE)
    if match:
        sql_query = match.group(1)
    else:
        sql_query = sql_query.replace("```sql", '').replace("```", '')
    sql_query = sql_query.replace(';', '')
    sql_query = sql_query.replace('"""', '')
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
        if 'FROM' in sql_query.upper():
            sql_query = 'SELECT ' + sql_query
        else:
            sql_query = 'SELECT ' + sql_query
    return sql_query.strip()

