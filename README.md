# Sphinteract 复现实验（Ambiguity 30 样本）

- 本仓库提供在 KaggleDBQA 上复现 Sphinteract 的 3 种方法（M1/M2/M3）的完整流程与脚本，包含数据集要求、环境配置与运行方式。
- 重点输出包括：`experiment_results.json`、可视化图（`figs/`）、复现用笔记本 `reproduction_sphinteract_ambiguity_generated.ipynb`。

## 环境要求
- Python 3.10+
- 依赖安装：
  - `pip install openai python-dotenv pandas numpy matplotlib seaborn langchain-community chromadb xxhash`
- 凭据：在项目根目录创建 `.env`，包含：
  - `OPENAI_API_KEY="<你的密钥>"`
  - 可选：`OPENAI_BASE_URL`、`AMBIGUITY_MODEL`（如 `gpt-4o-mini`）、`AMBIGUITY_WORKERS`（并发数）

## 数据集要求
- `kaggle_dataset.csv`：用于驱动复现实验的样本表，需至少包含：
  - `nl`（自然语言问题）
  - `sql`（标准答案 SQL）
  - `db_id` 或 `target_db`（对应数据库名）
- SQLite 数据库目录结构：`./databases/<DB>/<DB>.sqlite` 或 `./databases/<DB>.sqlite`，本仓库已提供以下数据库：
  - `GeoNuclearData.sqlite`
  - `GreaterManchesterCrime.sqlite`
  - `Pesticide.sqlite`
  - `StudentMathScore.sqlite`
  - `TheHistoryofBaseball.sqlite`
  - `USWildFires.sqlite`
  - `WhatCDHipHop.sqlite`
  - `WorldSoccerDataBase.sqlite`
- 可选 Few-shot 检索：`./userstudy_chroma/`（Chroma 向量库，元数据包含 `nl/gold/feedback`），缺失时 Few-shot 将自动退化为无示例模式。

## 运行步骤
- 生成复现笔记本与执行实验：
  - `python reproduce_sphinteract_ambiguity.py`
  - 脚本将：
    - 生成 `reproduction_sphinteract_ambiguity_generated.ipynb`
    - 通过 LLM 过滤并选取 30 条 Ambiguous 样本
    - 分别运行 M1/M2/M3 在 Zero/Few 模式下的实验（并发执行）
    - 写出统一结果至 `experiment_results.json` 并进行可视化
- 在笔记本中重绘图表：
  - 在 `reproduction_sphinteract_ambiguity_generated.ipynb` 中执行：
    - `redraw_from_results('experiment_results.json', save_dir='./figs')`

## 输出文件
- `experiment_results.json`：合并后的结果表（含每条样本的 `Method/Mode/Status/rounds/is_correct` 等）
- `figs/`：可视化图（性能概览、正确性分解等）
- `reproduction_sphinteract_ambiguity_generated.ipynb`：复现用 Jupyter 笔记本

## 复现结果摘要（30 条 Ambiguous）
- M1（合并 Zero/Few）：准确率 `0.933`，平均轮数 `0.45`
- M2（合并 Zero/Few）：准确率 `1.000`，平均轮数 `0.32`
- M3（合并 Zero/Few）：准确率 `0.983`，平均轮数 `0.25`
- 详细分组指标见 `report/sphinteract_复现实验结果汇总.md`

## 注意事项
- 数据库路径由代码自动匹配（优先 `./databases/<DB>/<DB>.sqlite`，否则 `./databases/<DB>.sqlite`）。如路径缺失，将跳过该样本。
- Few-shot 检索依赖 `userstudy_chroma`；缺失时不影响 Zero-shot 与主要流程，只是无法注入示例。
- 需确保 `.env` 中的密钥可用，且网络可访问 OpenAI API。

## 许可证
- 见 `LICENSE`

