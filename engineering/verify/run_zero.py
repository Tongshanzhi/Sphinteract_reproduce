import engineering
from engineering.pipeline import run_pipeline

if __name__ == "__main__":
    run_pipeline(n_shots_few=3, max_rounds=4)
