import os
import re
import sqlite3
import pandas as pd
import numpy as np
try:
    from engineering.io.paths import resolve_dataset_path, PROJECT_ROOT
    from engineering.debug.demo import debug_wrapper
    from engineering.experiments.baseline import run_m1_sample
    from engineering.experiments.sphinteract import run_m2_sample
    from engineering.experiments.break_no_ambiguity import run_m3_sample
    from engineering.db.locator import get_schema
    from engineering.llm.client import LLM_generation
    from engineering.debug.flow_demo import build_demo_db, make_samples
except ModuleNotFoundError:
    import sys
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from engineering.io.paths import resolve_dataset_path, PROJECT_ROOT
    from engineering.debug.demo import debug_wrapper
    from engineering.experiments.baseline import run_m1_sample
    from engineering.experiments.sphinteract import run_m2_sample
    from engineering.experiments.break_no_ambiguity import run_m3_sample
    from engineering.db.locator import get_schema
    from engineering.llm.client import LLM_generation
    from engineering.debug.flow_demo import build_demo_db, make_samples

def is_ambiguous_llm(nlq, schema, model=None):
    if os.getenv("AMBIGUITY_USE_LLM", "1") != "1":
        return False
    m = model or os.getenv("AMBIGUITY_MODEL", "gpt-4o-mini")
    print(f"[TRACE] is_ambiguous_llm start model={m} nlq_len={len(nlq)}")
    prompt = (
        "/* Given the following database schema: */\n" + schema + "\n" +
        "/* And the following Natural Language Question: */\n" + nlq + "\n\n" +
        "/* Task: Determine if the question is ambiguous given the schema.\n"
        "   Ambiguity can arise from:\n"
        "   - AmbQuestion: The question phrasing is unclear.\n"
        "   - AmbTableColumn: Unclear mapping to tables/columns.\n"
        "   - AmbOutput: Unclear what columns to output.\n"
        "   - AmbValue: Unclear predicate values.\n\n"
        "   Answer \"Yes\" if the question is ambiguous, or \"No\" if it is clear.\n"
        "   Provide a brief reason.\n"
        "*/\n"
        "Is the question ambiguous? Answer: "
    )
    resp, _ = LLM_generation(prompt, model=m, retries=3, retry_delay=1.5, log_each_retry=False)
    txt = resp.strip()
    u = txt.upper()
    m_ans = re.search(r"(?i)answer\\s*:\\s*(?:\\*+\\s*)?(yes|no)(?:\\s*\\*+)?", txt)
    if m_ans:
        val = m_ans.group(1).lower()
        if val == "yes":
            print(f"[TRACE] is_ambiguous_llm result=YES resp={txt[:120]}")
            return True
        print(f"[TRACE] is_ambiguous_llm result=NO resp={txt[:120]}")
        return False
    pos_yes = u.find("YES")
    pos_no = u.find("NO")
    if pos_yes != -1 and (pos_no == -1 or pos_yes < pos_no):
        print(f"[TRACE] is_ambiguous_llm result=YES resp={txt[:120]}")
        return True
    print(f"[TRACE] is_ambiguous_llm result=NO resp={txt[:120]}")
    return False

def load_kaggle_csv():
    p = resolve_dataset_path('kaggle_dataset.csv')
    if p is None:
        return pd.DataFrame()
    try:
        df = pd.read_csv(str(p))
        print(f"[TRACE] load_kaggle_csv path={p} rows={len(df)} cols={len(df.columns)}")
        return df
    except Exception:
        return pd.DataFrame()

class _CSVDoc:
    def __init__(self, nl, gold, feedback):
        self.metadata = {'nl': nl, 'gold': gold, 'feedback': feedback}

class _QuestionBankVectorStore:
    def __init__(self, root_dir, db_filter=None, embed_model=None):
        self.pool = []
        self.embeds = None
        self.embed_model = embed_model
        self._load_pool(root_dir, db_filter)
        self._ensure_embeddings()

    def _load_pool(self, root_dir, db_filter):
        import json, glob, os
        files = glob.glob(os.path.join(str(root_dir), "*.json"))
        for fp in files:
            try:
                data = json.loads(open(fp, 'r').read())
                for item in data:
                    nl = item.get('question') or item.get('nl') or ''
                    gold = item.get('query') or item.get('sql') or ''
                    dbid = item.get('db_id') or item.get('db') or ''
                    if db_filter and dbid and dbid != db_filter:
                        continue
                    nl = str(nl).strip()
                    gold = str(gold).strip()
                    if nl and gold:
                        self.pool.append({'nl': nl, 'gold': gold, 'db_id': dbid})
            except Exception:
                continue
        print(f"[TRACE] _QuestionBankVectorStore._load_pool root={root_dir} files={len(files)} loaded_docs={len(self.pool)} filter={db_filter}")

    def _ensure_embeddings(self):
        mode = os.getenv("VECTOR_EMBED_MODE", "token").lower()
        if os.getenv("EMBED_DISABLE", "0") == "1" or mode != "embed":
            self.embeds = None
            print(f"[TRACE] _QuestionBankVectorStore._ensure_embeddings disabled mode={mode}")
            return
        from engineering.llm.client import embed_texts
        texts_all = [x['nl'] for x in self.pool]
        print(f"[TRACE] _QuestionBankVectorStore._ensure_embeddings texts={len(texts_all)} mode={mode}")
        if not texts_all:
            self.embeds = np.zeros((0, 1), dtype=float)
            print("[TRACE] _QuestionBankVectorStore._ensure_embeddings no_texts")
            return
        try:
            max_docs = int(os.getenv("EMBED_MAX_DOCS", "256"))
        except Exception:
            max_docs = 256
        try:
            batch = int(os.getenv("EMBED_BATCH_SIZE", "64"))
        except Exception:
            batch = 64
        texts = texts_all[:max_docs]
        vecs_all = []
        for i in range(0, len(texts), batch):
            chunk = texts[i:i+batch]
            v = embed_texts(chunk, model=self.embed_model)
            if not v:
                self.embeds = None
                print("[TRACE] _QuestionBankVectorStore._ensure_embeddings embed_chunk_failed; fallback token")
                return
            vecs_all.extend(v)
            print(f"[TRACE] _QuestionBankVectorStore._ensure_embeddings progress {i+len(chunk)}/{len(texts)}")
        self.embeds = np.array(vecs_all, dtype=float)
        print(f"[TRACE] _QuestionBankVectorStore._ensure_embeddings created_embeddings shape={self.embeds.shape}")

    def similarity_search(self, query, k=3):
        if len(self.pool) == 0:
            return []
        q_norm = query.strip().lower()
        docs = []
        print(f"[TRACE] _QuestionBankVectorStore.similarity_search start k={k} pool={len(self.pool)} embeds={'yes' if self.embeds is not None else 'no'} query={query[:80]}")
        if self.embeds is not None:
            from engineering.llm.client import embed_texts
            qv_list = embed_texts([query], model=self.embed_model)
            if not qv_list:
                print("[TRACE] _QuestionBankVectorStore.similarity_search embed_query_failed")
                return []
            qv = np.array(qv_list[0], dtype=float)
            mat = self.embeds
            denom = (np.linalg.norm(mat, axis=1) * np.linalg.norm(qv) + 1e-9)
            sims = (mat @ qv) / denom
            idxs = np.argsort(sims)[-k:][::-1]
            print(f"[TRACE] _QuestionBankVectorStore.similarity_search top_idxs={idxs.tolist()}")
            for i in idxs:
                nl = self.pool[i]['nl']
                gold = self.pool[i]['gold']
                if nl.strip().lower() == q_norm:
                    continue
                docs.append(_CSVDoc(nl, gold, ''))
            return docs
        # Fallback: token overlap similarity across question bank
        q_tokens = set(re.findall(r"\w+", q_norm))
        scored = []
        for item in self.pool:
            nl = item['nl']
            gold = item['gold']
            t = set(re.findall(r"\w+", nl.lower()))
            s = len(q_tokens.intersection(t))
            scored.append((s, nl, gold))
        scored.sort(key=lambda x: x[0], reverse=True)
        print(f"[TRACE] _QuestionBankVectorStore.similarity_search fallback_top_scores={[s for s,_,_ in scored[:min(k,5)]]}")
        for s, nl, gold in scored[:k]:
            if nl.strip().lower() == q_norm:
                continue
            docs.append(_CSVDoc(nl, gold, ''))
        return docs

def _map_columns(df):
    cols = set(df.columns)
    nl_col = None
    sql_col = None
    db_col = None
    for c in ['nl', 'question', 'text', 'nlq']:
        if c in cols:
            nl_col = c
            break
    for c in ['sql', 'gold', 'gold_sql', 'query']:
        if c in cols:
            sql_col = c
            break
    for c in ['db_id', 'db', 'target_db']:
        if c in cols:
            db_col = c
            break
    return nl_col, sql_col, db_col

def extract_ambiguous_samples(csv_df, db_name, k=10):
    if csv_df.empty:
        raise ValueError('kaggle_dataset.csv is empty or cannot be read')
    nl_col, sql_col, db_col = _map_columns(csv_df)
    if nl_col is None:
        raise ValueError('kaggle_dataset.csv must contain a natural language column such as nl/question/nlq')
    if sql_col is None:
        raise ValueError('kaggle_dataset.csv must contain a SQL column such as sql/gold/gold_sql/query')
    print(f"[TRACE] extract_ambiguous_samples start db={db_name} rows={len(csv_df)} nl_col={nl_col} sql_col={sql_col} db_col={db_col}")
    rows = []
    for _, r in csv_df.iterrows():
        nl = str(r.get(nl_col, ''))
        if not nl:
            print('[ERROR] Skip row: missing NL question')
            continue
        sql_val = str(r.get(sql_col, '')).strip()
        if not sql_val:
            print('[ERROR] Skip row: missing gold SQL')
            continue
        row_db = str(r.get(db_col, '')).strip() if db_col else ''
        if not row_db:
            # if dataset does not specify db, skip to ensure correctness
            print('[ERROR] Skip row: missing db_id')
            continue
        schema = get_schema(row_db)
        if not schema:
            print(f"[ERROR] Skip row: missing schema for db={row_db}")
            continue
        if os.getenv("AMBIGUITY_USE_LLM", "1") == "1":
            amb = is_ambiguous_llm(nl, schema)
        else:
            amb = True
        if amb:
            rows.append({'nl': nl, 'sql': sql_val, 'db_id': row_db})
            print(f"[TRACE] extract_ambiguous_samples accepted nl_len={len(nl)} db={row_db} total={len(rows)}")
        if len(rows) >= k:
            break
    if len(rows) < k:
        raise ValueError(f'Found only {len(rows)} ambiguous samples; need {k}. Please expand the dataset.')
    df = pd.DataFrame(rows)
    print(f"[TRACE] extract_ambiguous_samples done count={len(df)}")
    return df, df.copy()

def run_section(name, func, samples, model, max_rounds, n_shots, vectorstore):
    print(name)
    dbg = debug_wrapper(func)
    res = []
    for idx, row in samples.iterrows():
        print(f"[TRACE] run_section dispatch idx={idx} n_shots={n_shots} rounds={max_rounds}")
        out = dbg((idx, row, model, max_rounds, n_shots, vectorstore))
        if out:
            res.append(out)
    return pd.DataFrame(res)

def _calc_method_stats(df):
    if df is None or df.empty:
        return 0, 0, 0, 0, 0.0
    total = len(df)
    rounds = df['rounds']
    corr = df['is_correct']
    fix = df['syntax_fix']
    init_ok = int(((rounds == 0) & (corr) & (~fix)).sum())
    fix_ok = int(((rounds == 0) & (corr) & (fix)).sum())
    sra_ok = int(((rounds > 0) & (corr)).sum())
    # Only count rounds for entries that triggered rewrites (rounds > 0)
    rpos = rounds[rounds > 0]
    avg_rounds = float(rpos.mean()) if len(rpos) > 0 else 0.0
    return total, init_ok, fix_ok, sra_ok, avg_rounds

def run_pipeline(use_mock=False, max_rounds=4, n_shots_few=2):
    print(f"[TRACE] run_pipeline start use_mock={use_mock} max_rounds={max_rounds} n_shots_few={n_shots_few}")
    csv_df = load_kaggle_csv()
    # Randomly shuffle the dataframe to ensure random sampling
    csv_df = csv_df.sample(frac=1, random_state=42).reset_index(drop=True)
    k_target = int(os.getenv('AMBIGUITY_TARGET_COUNT', '10'))
    samples, df_full = extract_ambiguous_samples(csv_df, os.getenv('DEFAULT_DB', ''), k_target)
    print(f"[TRACE] run_pipeline ambiguous_samples={len(samples)}")
    qb_dir = os.getenv('KAGGLE_QUESTION_BANK_DIR', str(PROJECT_ROOT / 'KaggleDBQA-main' / 'examples'))
    vs = _QuestionBankVectorStore(qb_dir, db_filter=None, embed_model=os.getenv('EMBED_MODEL', 'text-embedding-ada-002'))
    print(f"[TRACE] run_pipeline vectorstore_pool={len(vs.pool)} qb_dir={qb_dir}")
    model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
    print(f"[TRACE] run_pipeline model={model}")
    res_m1_zero = run_section('===== M1 Zero-Shot (Baseline) =====', run_m1_sample, samples, model, max_rounds, 0, None)
    res_m2_zero = run_section('===== M2 Zero-Shot =====', run_m2_sample, samples, model, max_rounds, 0, None)
    res_m3_zero = run_section('===== M3 Zero-Shot =====', run_m3_sample, samples, model, max_rounds, 0, None)
    res_m1_few = run_section('===== M1 Few-Shot =====', run_m1_sample, samples, model, max_rounds, n_shots_few, vs)
    res_m2_few = run_section('===== M2 Few-Shot =====', run_m2_sample, samples, model, max_rounds, n_shots_few, vs)
    res_m3_few = run_section('===== M3 Few-Shot =====', run_m3_sample, samples, model, max_rounds, n_shots_few, vs)
    print('===== Summary =====')
    print(f"M1 Zero: {len(res_m1_zero)} rows, acc={res_m1_zero['is_correct'].mean() if not res_m1_zero.empty else 0}")
    print(f"M2 Zero: {len(res_m2_zero)} rows, acc={res_m2_zero['is_correct'].mean() if not res_m2_zero.empty else 0}")
    print(f"M3 Zero: {len(res_m3_zero)} rows, acc={res_m3_zero['is_correct'].mean() if not res_m3_zero.empty else 0}")
    print(f"M1 Few: {len(res_m1_few)} rows, acc={res_m1_few['is_correct'].mean() if not res_m1_few.empty else 0}")
    print(f"M2 Few: {len(res_m2_few)} rows, acc={res_m2_few['is_correct'].mean() if not res_m2_few.empty else 0}")
    print(f"M3 Few: {len(res_m3_few)} rows, acc={res_m3_few['is_correct'].mean() if not res_m3_few.empty else 0}")
    t1,i1,f1,s1,a1 = _calc_method_stats(res_m1_zero)
    t2,i2,f2,s2,a2 = _calc_method_stats(res_m2_zero)
    t3,i3,f3,s3,a3 = _calc_method_stats(res_m3_zero)
    t4,i4,f4,s4,a4 = _calc_method_stats(res_m1_few)
    t5,i5,f5,s5,a5 = _calc_method_stats(res_m2_few)
    t6,i6,f6,s6,a6 = _calc_method_stats(res_m3_few)
    print(f"M1 Zero-Shot (Baseline): total={t1} init_ok={i1} fix_ok={f1} sra_ok={s1} avg_rounds={a1:.2f}")
    print(f"M2 Zero-Shot: total={t2} init_ok={i2} fix_ok={f2} sra_ok={s2} avg_rounds={a2:.2f}")
    print(f"M3 Zero-Shot: total={t3} init_ok={i3} fix_ok={f3} sra_ok={s3} avg_rounds={a3:.2f}")
    print(f"M1 Few-Shot: total={t4} init_ok={i4} fix_ok={f4} sra_ok={s4} avg_rounds={a4:.2f}")
    print(f"M2 Few-Shot: total={t5} init_ok={i5} fix_ok={f5} sra_ok={s5} avg_rounds={a5:.2f}")
    print(f"M3 Few-Shot: total={t6} init_ok={i6} fix_ok={f6} sra_ok={s6} avg_rounds={a6:.2f}")
    dfs_all = [res_m1_zero, res_m2_zero, res_m3_zero, res_m1_few, res_m2_few, res_m3_few]
    dfs_all = [d for d in dfs_all if not d.empty]
    if len(dfs_all) > 0:
        df_all = pd.concat(dfs_all, ignore_index=True)
        tot, init, fix, sra, avg = _calc_method_stats(df_all)
        p_init = f"{(init / tot):.2%}" if tot > 0 else "0.00%"
        p_fix = f"{(fix / tot):.2%}" if tot > 0 else "0.00%"
        p_sra = f"{(sra / tot):.2%}" if tot > 0 else "0.00%"
        print(f"Overall: total={tot} init_ok={init} ({p_init}) fix_ok={fix} ({p_fix}) sra_ok={sra} ({p_sra}) avg_rounds={avg:.2f}")
    else:
        print("Overall: total=0 init_ok=0 (0.00%) fix_ok=0 (0.00%) sra_ok=0 (0.00%) avg_rounds=0.00")
    return {
        'res_m1_zero': res_m1_zero,
        'res_m2_zero': res_m2_zero,
        'res_m3_zero': res_m3_zero,
        'res_m1_few': res_m1_few,
        'res_m2_few': res_m2_few,
        'res_m3_few': res_m3_few,
        'samples': samples
    }

if __name__ == '__main__':
    run_pipeline()
