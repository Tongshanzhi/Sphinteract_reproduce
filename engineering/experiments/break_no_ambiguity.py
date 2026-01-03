import concurrent.futures
import pandas as pd
try:
    from ..db.locator import get_schema, get_db_path
    from ..llm.client import LLM_generation
    from ..llm.prompts import build_metadata_constraints, fix_invalid_v1, SRA_ES, sql_generation_v2, cq_prefix_v1, feedback_v2, feedback_prefix_v1
    from ..utils.sanitize import clean_query
    from ..db.exec import evalfunc
    from ..llm.fewshot import get_few_shot_examples, get_feedback_few_shot_examples
except ImportError:
    from engineering.db.locator import get_schema, get_db_path
    from engineering.llm.client import LLM_generation
    from engineering.llm.prompts import build_metadata_constraints, fix_invalid_v1, SRA_ES, sql_generation_v2, cq_prefix_v1, feedback_v2, feedback_prefix_v1
    from engineering.utils.sanitize import clean_query
    from engineering.db.exec import evalfunc
    from engineering.llm.fewshot import get_few_shot_examples, get_feedback_few_shot_examples

def run_m3_sample(args):
    idx, row, model, max_rounds, n_shots, vectorstore = args
    nlq = row['nl']
    gold_sql = row['sql']
    db_name = row['target_db'] if 'target_db' in row else row['db_id']
    schema = get_schema(db_name)
    db_path = get_db_path(db_name)
    if not db_path:
        return None
    meta = build_metadata_constraints(nlq, schema)
    if n_shots > 0:
        examples_str = get_few_shot_examples(vectorstore, nlq, n_shots)
        initial_prompt = (
            "Complete sqlite SQL query only and with no explanation.\n"
            f"{examples_str}/* Given the following database schema: */\n{schema}\n{meta}\n/* Answer the following with no explanation: {nlq} */"
        )
    else:
        initial_prompt = (
            "Complete sqlite SQL query only and with no explanation.\n"
            f"/* Given the following database schema: */\n{schema}\n{meta}\n/* Answer the following with no explanation: {nlq} */"
        )
    print("[PROMPT M3 initial]")
    print(initial_prompt)
    sql, _ = LLM_generation(initial_prompt, model=model)
    sql = clean_query(sql)
    is_correct, errors = evalfunc(sql, gold_sql, db_path)
    syntax_fix = False
    if not is_correct and errors:
        invalid_prompt = fix_invalid_v1.format(schema=schema, question=nlq, invalidSQL=sql, ex=str(errors[0]))
        print("[PROMPT M3 fix_invalid]")
        print(invalid_prompt)
        sql, _ = LLM_generation(invalid_prompt, model=model)
        sql = clean_query(sql)
        is_correct, errors = evalfunc(sql, gold_sql, db_path)
        if is_correct:
            syntax_fix = True
    sqls_history = [sql]
    cqas_history = []
    if is_correct:
        return {'id': idx, 'nlq': nlq, 'final_sql': sql, 'rounds': 0, 'is_correct': True, 'syntax_fix': syntax_fix}
    success = False
    for round_i in range(max_rounds):
        print(f"[ROUND M3] {round_i+1}")
        cqas_str = ""
        for i in range(0, len(cqas_history), 2):
            if i+1 < len(cqas_history):
                cqas_str += f"multiple choice clarification question: {cqas_history[i]}\n"
                cqas_str += f"user: {cqas_history[i+1]}\n"
        if not cqas_str:
            cqas_str = "no previous clarification question.\n"
        sqls_unique = ";\n".join(sorted(list(set(sqls_history)), key=lambda x: sqls_history.index(x)))
        cq_prompt = SRA_ES.format(schema=schema, question=nlq, sqls=sqls_unique, cqs=cqas_str)
        cq_prompt = cq_prefix_v1 + cq_prompt
        print("[PROMPT M3 cq]")
        print(cq_prompt)
        cq, _ = LLM_generation(cq_prompt, model=model)
        print("[CQ]")
        print(cq)
        if "NO AMBIGUITY" in cq:
            break
        if "mul_choice_cq =" in cq:
            cq = cq.split("mul_choice_cq =")[-1].strip().strip('"')
        elif "mul_choice_cq=" in cq:
            cq = cq.split("mul_choice_cq=")[-1].strip().strip('"')
        elif len(cq.split('\n')) < 5:
            pass
        else:
            lines = cq.strip().split('\n')
            cq = lines[-1]
        feedback_prompt = feedback_v2.format(nlq=nlq, query=gold_sql, question=cq)
        feedback_prompt = feedback_prefix_v1 + feedback_prompt
        print("[PROMPT M3 feedback]")
        print(feedback_prompt)
        feedback, _ = LLM_generation(feedback_prompt, model=model)
        if "answer_to_cq =" in feedback:
            feedback = feedback.split("answer_to_cq =")[-1].strip().strip('"')
        elif "answer_to_cq" in feedback:
            feedback = feedback.split("answer_to_cq=")[-1].strip().strip('"')
        print("[ANSWER]")
        print(feedback)
        cqas_history.append(cq)
        cqas_history.append(feedback)
        cqas_block = ""
        for i in range(0, len(cqas_history), 2):
            if i+1 < len(cqas_history):
                cqas_block += f"multiple choice clarification question: {cqas_history[i]}\n"
                cqas_block += f"user: {cqas_history[i+1]}\n"
        if not cqas_block:
            cqas_block = "no previous clarification questions are asked.\n"
        sqls_unique = ";\n".join(sorted(list(set(sqls_history)), key=lambda x: sqls_history.index(x)))
        sql_prompt = sql_generation_v2.format(schema=schema, question=nlq, sqls=sqls_unique, cqas=cqas_block, metadata=meta)
        print("[PROMPT M3 sql_gen]")
        print(sql_prompt)
        sql, _ = LLM_generation(sql_prompt, model=model)
        sql = clean_query(sql)
        sqls_history.append(sql)
        is_correct, errors = evalfunc(sql, gold_sql, db_path)
        if not is_correct and errors:
            invalid_prompt = fix_invalid_v1.format(schema=schema, question=nlq, invalidSQL=sql, ex=str(errors[0]))
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

def run_break_no_ambiguity_experiment(samples, df_full, model='gpt-3.5-turbo', max_rounds=6, n_shots=0, vectorstore=None):
    results = []
    args_list = []
    for idx, row in samples.iterrows():
        args_list.append((idx, row, model, max_rounds, n_shots, vectorstore))
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(run_m3_sample, args): args[0] for args in args_list}
        for future in concurrent.futures.as_completed(futures):
            try:
                res = future.result()
                if res:
                    results.append(res)
            except Exception as e:
                print(f"Error in parallel execution: {e}")
    return pd.DataFrame(results)
