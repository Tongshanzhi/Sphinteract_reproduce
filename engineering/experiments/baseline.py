import concurrent.futures
import pandas as pd
try:
    from ..db.locator import get_schema, get_db_path
    from ..llm.client import LLM_generation
    from ..llm.prompts import build_metadata_constraints, fix_invalid_v1, sql_generation_selfdebug, fewshot_prefix, make_selfdebug_few_shot
    from ..utils.sanitize import clean_query
    from ..db.exec import evalfunc
    from ..llm.fewshot import get_few_shot_examples
except ImportError:
    from engineering.db.locator import get_schema, get_db_path
    from engineering.llm.client import LLM_generation
    from engineering.llm.prompts import build_metadata_constraints, fix_invalid_v1, sql_generation_selfdebug, fewshot_prefix, make_selfdebug_few_shot
    from engineering.utils.sanitize import clean_query
    from engineering.db.exec import evalfunc
    from engineering.llm.fewshot import get_few_shot_examples

def run_m1_sample(args):
    idx, row, model, max_rounds, n_shots, vectorstore = args
    nlq = row['nl']
    gold_sql = row['sql']
    db_name = row['target_db'] if 'target_db' in row else row['db_id']
    schema = get_schema(db_name)
    db_path = get_db_path(db_name)
    if not db_path:
        return None
    meta = build_metadata_constraints(nlq, schema)
    examples_str = get_few_shot_examples(vectorstore, nlq, n_shots) if n_shots > 0 else ""
    if examples_str:
        initial_prompt = (
            "Complete sqlite SQL query only and with no explanation.\n"
            f"{examples_str}/* Given the following database schema: */\n{schema}\n{meta}\n/* Answer the following with no explanation: {nlq} */"
        )
    else:
        initial_prompt = (
            "Complete sqlite SQL query only and with no explanation.\n"
            f"/* Given the following database schema: */\n{schema}\n{meta}\n/* Answer the following with no explanation: {nlq} */"
        )
    print("[PROMPT M1 initial]" )
    print(initial_prompt)
    sql, _ = LLM_generation(initial_prompt, model=model)
    sql = clean_query(sql)
    is_correct, errors = evalfunc(sql, gold_sql, db_path)
    syntax_fix = False
    if not is_correct and errors:
        invalid_prompt = fix_invalid_v1.format(schema=schema, question=nlq, invalidSQL=sql, ex=str(errors[0]))
        print("[PROMPT M1 fix_invalid]" )
        print(invalid_prompt)
        sql, _ = LLM_generation(invalid_prompt, model=model)
        sql = clean_query(sql)
        is_correct, errors = evalfunc(sql, gold_sql, db_path)
        if is_correct:
            syntax_fix = True
    sqls_history = [sql]
    if is_correct:
        return {'id': idx, 'nlq': nlq, 'final_sql': sql, 'rounds': 0, 'is_correct': True, 'syntax_fix': syntax_fix}
    selfdebug_few = make_selfdebug_few_shot()
    success = False
    for round_i in range(max_rounds):
        print(f"[ROUND M1] {round_i+1}")
        sqls_str = "\n".join(sorted(list(set(sqls_history)), key=lambda x: sqls_history.index(x)))
        prompt = sql_generation_selfdebug.format(schema=schema, sqls=sqls_str, question=nlq, metadata="")
        if n_shots > 0 and len(selfdebug_few) >= 1:
            idx_shot = min(n_shots, len(selfdebug_few)) - 1
            if idx_shot < 0:
                idx_shot = 0
            prompt = fewshot_prefix + selfdebug_few[idx_shot] + prompt
        if n_shots > 0 and examples_str:
            prompt = examples_str + prompt
        print("[PROMPT M1 selfdebug]" )
        print(prompt)
        sql, _ = LLM_generation(prompt, model=model)
        sql = clean_query(sql)
        sqls_history.append(sql)
        is_correct, errors = evalfunc(sql, gold_sql, db_path)
        if not is_correct and errors:
            invalid_prompt = fix_invalid_v1.format(schema=schema, question=nlq, invalidSQL=sql, ex=str(errors[0]))
            print("[PROMPT M1 fix_invalid]" )
            print(invalid_prompt)
            fixed_sql, _ = LLM_generation(invalid_prompt, model=model)
            fixed_sql = clean_query(fixed_sql)
            sqls_history.pop()
            sqls_history.append(fixed_sql)
            sql = fixed_sql
            is_correct, errors = evalfunc(sql, gold_sql, db_path)
            if is_correct:
                syntax_fix = True
        if is_correct:
            success = True
            return {'id': idx, 'nlq': nlq, 'final_sql': sql, 'rounds': round_i+1, 'is_correct': True, 'syntax_fix': syntax_fix}
    if not success:
        return {'id': idx, 'nlq': nlq, 'final_sql': sql, 'rounds': max_rounds, 'is_correct': False, 'syntax_fix': False}

def run_simple_feedback_experiment(samples, df_full, model='gpt-3.5-turbo', max_rounds=6, n_shots=0, vectorstore=None):
    results = []
    args_list = []
    for idx, row in samples.iterrows():
        args_list.append((idx, row, model, max_rounds, n_shots, vectorstore))
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(run_m1_sample, args): args[0] for args in args_list}
        for future in concurrent.futures.as_completed(futures):
            try:
                res = future.result()
                if res:
                    results.append(res)
            except Exception as e:
                print(f"Error in parallel execution: {e}")
    return pd.DataFrame(results)
