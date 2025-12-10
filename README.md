# Sphinteract Reproduction (30 Ambiguous Samples)

- This repository reproduces the Sphinteract [Zhao, F., Deep, S., Psallidas, F., Floratou, A., Agrawal, D., & El Abbadi, A. (2024). Sphinteract: Resolving Ambiguities in NL2SQL Through User Interaction. PVLDB, 18(4), 1145 - 1158. doi:10.14778/3717755.3717772] framework on KaggleDBQA with three methods (M1/M2/M3). It includes dataset requirements, environment setup, and execution steps.
- Key outputs: `experiment_results.json`, figures under `figs/`, and the notebook `reproduction_sphinteract_ambiguity_generated.ipynb`.

## Environment
- Python 3.10+
- Install dependencies:
  - `pip install openai python-dotenv pandas numpy matplotlib seaborn langchain-community chromadb xxhash`
- Credentials: create a `.env` in project root with:
  - `OPENAI_API_KEY="<your key>"`
  - Optional: `OPENAI_BASE_URL`, `AMBIGUITY_MODEL` (e.g., `gpt-4o-mini`), `AMBIGUITY_WORKERS` (parallelism)

## Dataset Requirements
- `kaggle_dataset.csv` must contain at least:
  - `nl` (natural language question)
  - `sql` (gold SQL)
  - `db_id` or `target_db` (database name)
- SQLite layout: `./databases/<DB>/<DB>.sqlite` or `./databases/<DB>.sqlite`. Provided DBs:
  - `GeoNuclearData.sqlite`
  - `GreaterManchesterCrime.sqlite`
  - `Pesticide.sqlite`
  - `StudentMathScore.sqlite`
  - `TheHistoryofBaseball.sqlite`
  - `USWildFires.sqlite`
  - `WhatCDHipHop.sqlite`
  - `WorldSoccerDataBase.sqlite`
- Optional Few-shot retrieval: `./userstudy_chroma/` (Chroma store with `nl/gold/feedback` metadata). If missing, Few-shot falls back to no examples.

## How to Run
- Run experiments:`reproduction_sphinteract_ambiguity_generated.ipynb`
  - The script will:
    - Filter and select 30 ambiguous samples via LLM
    - Run M1/M2/M3 in Zero/Few modes (parallel)
    - Write unified results to `experiment_results.json` and plot figures
- Redraw figures in the notebook:
  - In `reproduction_sphinteract_ambiguity_generated.ipynb` execute:
    - `redraw_from_results('experiment_results.json', save_dir='./figs')`

## Outputs
- `experiment_results.json`: unified results (per-sample `Method/Mode/Status/rounds/is_correct` etc.)
- `figs/`: figures (performance overview, correctness breakdown, etc.)

## Summary (30 Ambiguous)
- M1 (Zero+Few): accuracy `0.933`, avg rounds `0.45`
- M2 (Zero+Few): accuracy `1.000`, avg rounds `0.32`
- M3 (Zero+Few): accuracy `0.983`, avg rounds `0.25`

## Notes
- DB paths are auto-resolved (prefer `./databases/<DB>/<DB>.sqlite`, fallback `./databases/<DB>.sqlite`). Missing DBs are skipped.
- Few-shot retrieval depends on `userstudy_chroma`; missing store does not affect Zero-shot or main flow.
- Ensure `.env` key is valid and OpenAI API is reachable.
