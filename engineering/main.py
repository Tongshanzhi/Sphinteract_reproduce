import os
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel

# Import internal modules
# Ensure engineering is in python path or run from root
from engineering.db.locator import get_schema
from engineering.llm.client import LLM_generation
from engineering.llm.prompts import build_metadata_constraints, SRA, cq_prefix_v1, feedback_v2, feedback_prefix_v1, fix_invalid_v1
from engineering.utils.sanitize import clean_query
from engineering.pipeline import _QuestionBankVectorStore, is_ambiguous_llm
from engineering.io.paths import PROJECT_ROOT
from engineering.llm.fewshot import get_few_shot_examples

# Global state for vector store
vector_store = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global vector_store
    # Initialize vector store for few-shot examples
    qb_dir = os.getenv('KAGGLE_QUESTION_BANK_DIR', str(PROJECT_ROOT / 'KaggleDBQA-main' / 'examples'))
    embed_model = os.getenv('EMBED_MODEL', 'text-embedding-ada-002')
    
    print(f"Initializing VectorStore from {qb_dir}...")
    if os.path.exists(qb_dir):
        try:
            vector_store = _QuestionBankVectorStore(qb_dir, db_filter=None, embed_model=embed_model)
            print("VectorStore initialized successfully.")
        except Exception as e:
            print(f"Failed to initialize VectorStore: {e}")
            vector_store = None
    else:
        print(f"Warning: Question bank directory {qb_dir} not found. Few-shot capabilities may be limited.")
        vector_store = None
    
    yield
    # Cleanup if necessary
    vector_store = None

app = FastAPI(title="Engineering SQL Pipeline API", lifespan=lifespan)

# --- Pydantic Models ---

class SchemaResponse(BaseModel):
    db_id: str
    schema_str: str

class AmbiguityCheckRequest(BaseModel):
    nlq: str
    db_id: str
    model: Optional[str] = "gpt-4o-mini"

class AmbiguityCheckResponse(BaseModel):
    is_ambiguous: bool
    details: Optional[str] = None

class SQLGenerationRequest(BaseModel):
    nlq: str
    db_id: str
    model: Optional[str] = "gpt-4o-mini"
    n_shots: int = 0
    
class SQLGenerationResponse(BaseModel):
    sql: str
    prompt_used: Optional[str] = None

class FixSQLRequest(BaseModel):
    nlq: str
    db_id: str
    invalid_sql: str
    error_message: str
    model: Optional[str] = "gpt-4o-mini"

class ClarificationRequest(BaseModel):
    nlq: str
    db_id: str
    sqls_history: List[str]
    cqas_history: List[str] # Alternating CQ and Answer strings
    model: Optional[str] = "gpt-4o-mini"

class ClarificationResponse(BaseModel):
    clarification_question: Optional[str] = None
    final_sql: Optional[str] = None

# --- Endpoints ---

@app.get("/")
def health_check():
    return {"status": "ok", "vector_store_loaded": vector_store is not None}

@app.get("/schema/{db_id}", response_model=SchemaResponse)
def get_schema_endpoint(db_id: str):
    schema_str = get_schema(db_id)
    if not schema_str:
        raise HTTPException(status_code=404, detail=f"Schema for database '{db_id}' not found.")
    return SchemaResponse(db_id=db_id, schema_str=schema_str)

@app.post("/ambiguity/check", response_model=AmbiguityCheckResponse)
def check_ambiguity_endpoint(req: AmbiguityCheckRequest):
    schema_str = get_schema(req.db_id)
    if not schema_str:
        raise HTTPException(status_code=404, detail=f"Schema for database '{req.db_id}' not found.")
    
    is_amb = is_ambiguous_llm(req.nlq, schema_str, model=req.model)
    return AmbiguityCheckResponse(is_ambiguous=is_amb)

@app.post("/generate/sql", response_model=SQLGenerationResponse)
def generate_sql_endpoint(req: SQLGenerationRequest):
    schema_str = get_schema(req.db_id)
    if not schema_str:
        raise HTTPException(status_code=404, detail=f"Schema for database '{req.db_id}' not found.")
    
    meta = build_metadata_constraints(req.nlq, schema_str)
    
    initial_prompt = ""
    if req.n_shots > 0:
        if vector_store:
            examples_str = get_few_shot_examples(vector_store, req.nlq, req.n_shots)
            initial_prompt = (
                "Complete sqlite SQL query only and with no explanation.\n"
                f"{examples_str}/* Given the following database schema: */\n{schema_str}\n{meta}\n/* Answer the following with no explanation: {req.nlq} */"
            )
        else:
            # Fallback if vector store not loaded
            initial_prompt = (
                "Complete sqlite SQL query only and with no explanation.\n"
                f"/* Given the following database schema: */\n{schema_str}\n{meta}\n/* Answer the following with no explanation: {req.nlq} */"
            )
    else:
        initial_prompt = (
            "Complete sqlite SQL query only and with no explanation.\n"
            f"/* Given the following database schema: */\n{schema_str}\n{meta}\n/* Answer the following with no explanation: {req.nlq} */"
        )
    
    sql, _ = LLM_generation(initial_prompt, model=req.model)
    sql = clean_query(sql)
    return SQLGenerationResponse(sql=sql, prompt_used=initial_prompt)

@app.post("/generate/fix", response_model=SQLGenerationResponse)
def fix_sql_endpoint(req: FixSQLRequest):
    schema_str = get_schema(req.db_id)
    if not schema_str:
        raise HTTPException(status_code=404, detail=f"Schema for database '{req.db_id}' not found.")
        
    invalid_prompt = fix_invalid_v1.format(
        schema=schema_str, 
        question=req.nlq, 
        invalidSQL=req.invalid_sql, 
        ex=req.error_message
    )
    
    sql, _ = LLM_generation(invalid_prompt, model=req.model)
    sql = clean_query(sql)
    return SQLGenerationResponse(sql=sql, prompt_used=invalid_prompt)

@app.post("/generate/clarify", response_model=ClarificationResponse)
def generate_clarification_endpoint(req: ClarificationRequest):
    """
    Generates a clarification question based on history of SQLs and CQs.
    This corresponds to the 'SRA' (Self-Reflection / Ambiguity) step.
    """
    schema_str = get_schema(req.db_id)
    if not schema_str:
        raise HTTPException(status_code=404, detail=f"Schema for database '{req.db_id}' not found.")
    
    # Format history
    cqas_str = ""
    for i in range(0, len(req.cqas_history), 2):
        if i+1 < len(req.cqas_history):
            cqas_str += f"multiple choice clarification question: {req.cqas_history[i]}\n"
            cqas_str += f"user: {req.cqas_history[i+1]}\n"
    if not cqas_str:
        cqas_str = "no previous clarification question.\n"
        
    sqls_unique = ";\n".join(sorted(list(set(req.sqls_history))))
    
    cq_prompt = SRA.format(schema=schema_str, question=req.nlq, sqls=sqls_unique, cqs=cqas_str)
    cq_prompt = cq_prefix_v1 + cq_prompt
    
    cq, _ = LLM_generation(cq_prompt, model=req.model)
    
    # Parse CQ
    final_cq = cq
    if "mul_choice_cq =" in cq:
        final_cq = cq.split("mul_choice_cq =")[-1].strip().strip('"')
    elif "mul_choice_cq=" in cq:
        final_cq = cq.split("mul_choice_cq=")[-1].strip().strip('"')
    
    return ClarificationResponse(clarification_question=final_cq)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
