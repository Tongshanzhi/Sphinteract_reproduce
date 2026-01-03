import os
import time

def get_client():
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    timeout = float(os.getenv("OPENAI_TIMEOUT", "30"))
    from openai import OpenAI
    return OpenAI(api_key=api_key, base_url=base_url if base_url else "https://api.openai.com/v1", timeout=timeout)

def _classify_prompt(p):
    s = p.lower()
    if "is the question ambiguous? answer:" in s:
        return "ambiguous_check"
    if "fix the exception" in s or "inexecutable sql" in s or "invalid sql" in s:
        return "fix_invalid_v1"
    if "ask the user a new multiple choice clarification question" in s or ("multiple choice clarification question" in s and "answer the following" not in s):
        return "sra"
    if "answer the following multiple choice clarification question" in s or "answer_to_cq" in s:
        return "feedback_v2"
    if "and the following incorrect sql answers" in s and "user replies" in s:
        return "sql_generation_v2"
    if "and the following incorrect sql answers" in s and "no explanation" in s and "user replies" not in s:
        return "sql_generation_selfdebug"
    if "complete sqlite sql query only and with no explanation" in s:
        return "initial"
    return "other"

def _mock_llm_generation(prompt):
    tag = _classify_prompt(prompt)
    if tag == "ambiguous_check":
        s = prompt.lower()
        keys = ["which", "or", "between", "and", "top", "most", "least", "maybe", "should"]
        hits = sum(1 for k in keys if k in s)
        if hits >= 2:
            return "Yes: ambiguous", 0.0
        return "No: clear", 0.0
    if tag == "sra":
        return 'mul_choice_cq = "Which aggregation should be used? a) COUNT(*), b) SUM(value), c) other"', 0.0
    if tag == "feedback_v2":
        return 'answer_to_cq = "a) COUNT(*)"', 0.0
    return "```sql\nSELECT 1\n```", 0.0

def LLM_generation(prompt, model='gpt-3.5-turbo', temperature=0.0, retries=3, retry_delay=1.5, log_each_retry=False, fallback_models=None):
    if os.getenv("LLM_MODE", "remote").lower() == "mock":
        return _mock_llm_generation(prompt)
    if not os.getenv("OPENAI_API_KEY"):
        print("LLM warn: OPENAI_API_KEY missing, return stub")
        return "```sql\nSELECT 1\n```", 0.0
    client = get_client()
    # allow env overrides
    try:
        retries = int(os.getenv("LLM_RETRIES", str(retries)))
    except Exception:
        pass
    try:
        retry_delay = float(os.getenv("LLM_RETRY_DELAY", str(retry_delay)))
    except Exception:
        pass
    llm_timeout = float(os.getenv("LLM_TIMEOUT", os.getenv("OPENAI_TIMEOUT", "30")))
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

def _mock_embed_texts(texts):
    import re
    try:
        dim = int(os.getenv("EMBED_DIM", "128"))
    except Exception:
        dim = 128
    def one(t):
        v = [0.0] * dim
        for tok in re.findall(r"\w+", (t or "").lower()):
            idx = (hash(tok) & 0xffffffff) % dim
            v[idx] += 1.0
        norm = sum(x*x for x in v) ** 0.5
        if norm > 0:
            v = [x / norm for x in v]
        return v
    return [one(t) for t in texts]

def embed_texts(texts, model=None, retries=3, retry_delay=1.5, log_each_retry=False):
    if os.getenv("EMBED_MODE", "remote").lower() == "mock" or not os.getenv("OPENAI_API_KEY"):
        return _mock_embed_texts(texts)
    client = get_client()
    try:
        retries = int(os.getenv("EMBED_RETRIES", str(retries)))
    except Exception:
        pass
    try:
        retry_delay = float(os.getenv("EMBED_RETRY_DELAY", str(retry_delay)))
    except Exception:
        pass
    embed_timeout = float(os.getenv("EMBED_TIMEOUT", os.getenv("OPENAI_TIMEOUT", "30")))
    m = model or os.getenv("EMBED_MODEL", "text-embedding-ada-002")
    last_err = None
    for attempt in range(retries):
        try:
            resp = client.embeddings.create(model=m, input=texts)
            return [d.embedding for d in resp.data]
        except Exception as e:
            last_err = e
            if log_each_retry:
                print(f"Embedding error, retry {attempt+1}/{retries}: {e}")
            import time
            time.sleep(retry_delay * (1.5 ** attempt))
    if last_err is not None:
        print(f"Embedding error; giving up: {last_err}")
    return []
