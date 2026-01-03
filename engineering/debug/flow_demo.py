import os
import sqlite3
import pandas as pd
from .demo import debug_wrapper
from ..io.paths import resolve_dataset_path, PROJECT_ROOT
from ..experiments.baseline import run_m1_sample
from ..experiments.sphinteract import run_m2_sample
from ..experiments.break_no_ambiguity import run_m3_sample
import engineering.llm.client as llm_client
import engineering.db.exec as db_exec
import engineering.experiments.baseline as exp_baseline
import engineering.experiments.sphinteract as exp_sph
import engineering.experiments.break_no_ambiguity as exp_break

class DummyDoc:
    def __init__(self, metadata):
        self.metadata = metadata

class DummyVectorStore:
    def __init__(self, examples):
        self.examples = examples
    def similarity_search(self, query, k=3):
        res = []
        for i in range(min(k, len(self.examples))):
            res.append(DummyDoc(self.examples[i]))
        return res

def classify_prompt(p):
    s = p.lower()
    if "fix the exception" in s or "inexecutable sql" in s:
        return "fix_invalid_v1"
    if "ask the user a new multiple choice clarification question" in s:
        return "sra"
    if "answer the following multiple choice clarification question" in s:
        return "feedback_v2"
    if "and the following incorrect sql answers" in s and "user replies" in s:
        return "sql_generation_v2"
    if "and the following incorrect sql answers" in s and "no explanation" in s and "user replies" not in s:
        return "sql_generation_selfdebug"
    if "answer the following with no explanation" in s and "incorrect sql answers" not in s:
        return "initial"
    return "other"

def make_output_for_tag(tag, nl):
    if tag == "sra":
        return 'mul_choice_cq = "Which aggregation should be used? a) COUNT(*), b) SUM(value), c) other"'
    if tag == "feedback_v2":
        return 'answer_to_cq = "a) COUNT(*)"'
    if tag == "initial":
        return "```sql\nSELECT COUNT(*) FROM kaggle WHERE 1=0\n```"
    return "```sql\nSELECT COUNT(*) FROM kaggle\n```"

def mock_llm_generation(prompt, model='mock', temperature=0.0, retries=1, retry_delay=0.1, log_each_retry=False, fallback_models=None):
    tag = classify_prompt(prompt)
    print(f"[LLM] {tag}")
    out = make_output_for_tag(tag, "")
    print(f"[LLM Output] {out}")
    return out, 0.0

orig_llm = llm_client.LLM_generation
orig_eval = db_exec.evalfunc

def traced_evalfunc(sql_source, sql_target, db_path):
    print("[EVAL] start")
    print(f"[EVAL Source] {sql_source}")
    print(f"[EVAL Gold] {sql_target}")
    ok, errs = orig_eval(sql_source, sql_target, db_path)
    print(f"[EVAL Result] ok={ok} errs={errs}")
    return ok, errs

def build_demo_db(csv_path):
    db_name = "kaggle_demo"
    db_file = PROJECT_ROOT / f"{db_name}.sqlite"
    if db_file.exists():
        os.remove(str(db_file))
    conn = sqlite3.connect(str(db_file))
    used_csv = False
    if csv_path and os.path.isfile(str(csv_path)):
        try:
            df = pd.read_csv(str(csv_path))
            if len(df) > 0:
                df.to_sql('kaggle', conn, index=False, if_exists='replace')
                used_csv = True
        except Exception:
            pass
    if not used_csv:
        conn.execute("CREATE TABLE kaggle (id INTEGER PRIMARY KEY, value INTEGER)")
        conn.execute("INSERT INTO kaggle (value) VALUES (10), (15), (20), (25)")
    conn.commit()
    conn.close()
    return db_name, str(db_file)

def make_samples(db_name):
    data = [{
        'nl': 'How many rows are in the kaggle table?',
        'sql': 'SELECT COUNT(*) FROM kaggle',
        'target_db': db_name
    }]
    return pd.DataFrame(data), pd.DataFrame(data)

def make_vectorstore():
    ex = [{
        'nl': 'How many rows are in the kaggle table?',
        'gold': 'SELECT COUNT(*) FROM kaggle',
        'feedback': 'a) COUNT(*)'
    }, {
        'nl': 'How many rows are in the kaggle table?',
        'gold': 'SELECT COUNT(*) FROM kaggle',
        'feedback': 'a) COUNT(*)'
    }]
    return DummyVectorStore(ex)

def run_all():
    llm_client.LLM_generation = mock_llm_generation
    exp_baseline.LLM_generation = mock_llm_generation
    exp_sph.LLM_generation = mock_llm_generation
    exp_break.LLM_generation = mock_llm_generation
    exp_baseline.evalfunc = traced_evalfunc
    exp_sph.evalfunc = traced_evalfunc
    exp_break.evalfunc = traced_evalfunc
    csv_path = resolve_dataset_path('kaggle_dataset.csv')
    db_name, db_file = build_demo_db(csv_path)
    samples, df_full = make_samples(db_name)
    vectorstore = make_vectorstore()
    print("===== M1 Zero-Shot =====")
    dbg_m1 = debug_wrapper(run_m1_sample)
    res_m1_zero = dbg_m1((0, samples.iloc[0], 'mock', 3, 0, None))
    print("===== M1 Few-Shot =====")
    res_m1_few = dbg_m1((0, samples.iloc[0], 'mock', 3, 2, vectorstore))
    print("===== M2 Zero-Shot =====")
    dbg_m2 = debug_wrapper(run_m2_sample)
    res_m2_zero = dbg_m2((0, samples.iloc[0], 'mock', 3, 0, None))
    print("===== M2 Few-Shot =====")
    res_m2_few = dbg_m2((0, samples.iloc[0], 'mock', 3, 2, vectorstore))
    print("===== M3 Zero-Shot =====")
    dbg_m3 = debug_wrapper(run_m3_sample)
    res_m3_zero = dbg_m3((0, samples.iloc[0], 'mock', 3, 0, None))
    print("===== M3 Few-Shot =====")
    res_m3_few = dbg_m3((0, samples.iloc[0], 'mock', 3, 2, vectorstore))
    print("===== Summary =====")
    print(f"M1 Zero: {res_m1_zero}")
    print(f"M1 Few: {res_m1_few}")
    print(f"M2 Zero: {res_m2_zero}")
    print(f"M2 Few: {res_m2_few}")
    print(f"M3 Zero: {res_m3_zero}")
    print(f"M3 Few: {res_m3_few}")
    if os.path.exists(db_file):
        os.remove(db_file)
    llm_client.LLM_generation = orig_llm
    exp_baseline.LLM_generation = orig_llm
    exp_sph.LLM_generation = orig_llm
    exp_break.LLM_generation = orig_llm
    exp_baseline.evalfunc = orig_eval
    exp_sph.evalfunc = orig_eval
    exp_break.evalfunc = orig_eval
