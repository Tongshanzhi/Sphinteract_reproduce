# Sphinteract Reproduction

本项目旨在复现 Sphinteract 框架在 KaggleDBQA 数据集上的表现，包含三种核心方法（M1, M2, M3）以及 Zero-shot 和 Few-shot 的实验设置。

## 项目结构

```
.
├── engineering/            # 核心工程代码
│   ├── pipeline.py         # 主流程入口
│   ├── main.py             # FastAPI 接口封装
│   ├── db/                 # 数据库操作
│   ├── llm/                # LLM 调用与 Prompt
│   └── experiments/        # M1/M2/M3 实验逻辑
├── databases/              # SQLite 数据库文件
├── KaggleDBQA-main/        # 数据集原始文件与 Few-shot 题库
├── kaggle_dataset.csv      # 实验用的数据集（包含 NLQ, Gold SQL, DB_ID）
├── requirements.txt        # 依赖列表
├── .env.example            # 环境变量示例
└── README.md               # 本文档
```

## 方法介绍 (M1-M3)

### M1: Baseline (Direct Generation)
**基线方法**，直接将自然语言问题（NLQ）和数据库 Schema 输入给 LLM，生成 SQL。
*   **流程**：`NLQ + Schema` -> `LLM` -> `SQL`
*   **举例**：
    *   用户问："有哪些通过测试的学生？"
    *   M1 直接生成：`SELECT * FROM students WHERE status = 'passed'`

### M2: Sphinteract (Interactive)
**交互式消歧**，模型主动识别歧义并向用户提问，根据反馈优化 SQL。
*   **流程**：
    1.  `NLQ + Schema` -> `LLM` -> 初步 SQL
    2.  如果存在歧义 -> 生成多项选择澄清问题 (CQ)
    3.  用户（或模拟器）反馈选项 -> `Feedback`
    4.  `NLQ + Schema + History(CQ+Feedback)` -> `LLM` -> 修正 SQL
*   **举例**：
    *   用户问："有哪些通过测试的学生？"
    *   M2 提问："这里的‘通过’是指分数大于60，还是状态为‘pass’？\n a) 分数 > 60\n b) status = 'pass'"
    *   用户反馈："b"
    *   M2 生成：`SELECT * FROM students WHERE status = 'pass'`

### M3: Break No Ambiguity (Early Stop)
**带早停机制的交互式消歧**，逻辑与 M2 类似，但引入了 `SRA_ES` (Self-Reflection with Early Stop) 机制。
*   **流程**：在每轮交互中，如果模型判断当前已经没有歧义（输出 `NO AMBIGUITY`），则提前终止交互循环，输出最终 SQL。这可以减少不必要的交互轮次，提高效率。

## Zero-shot vs Few-shot

### Zero-shot (零样本)
模型仅依赖预定义的 Prompt 模板、当前问题的 Schema 和问题本身来生成 SQL，不提供任何参考示例。
*   **适用场景**：新领域、无历史数据。

### Few-shot (少样本)
模型在生成前，会先从题库（`KaggleDBQA-main/examples`）中检索 `k` 个（默认 k=2）与当前问题最相似的 `(NLQ, SQL)` 对作为示例（Demonstrations）。
*   **机制**：基于向量相似度（如果配置了 Embeddings）或 Token 重叠度检索。
*   **Prompt 变化**：
    ```text
    Example 1: ...
    Example 2: ...
    /* Given the following database schema: */
    ...
    /* Answer the following: ... */
    ```
*   **优势**：通过类比学习，通常能提高生成的准确率和规范性。

## 本地部署指南

### 1. 环境准备
确保安装 Python 3.10+。

```bash
# 克隆项目
git clone https://github.com/Tongshanzhi/Sphinteract_reproduce.git
cd Sphinteract_reproduce

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量
复制示例配置文件并填写你的 API Key：

```bash
cp .env.example .env
```

编辑 `.env` 文件：
```properties
OPENAI_API_KEY=sk-xxxxxx
OPENAI_BASE_URL=https://api.openai.com/v1  # 或你的中转地址
OPENAI_MODEL=gpt-4o-mini                   # 生成 SQL 的模型
AMBIGUITY_MODEL=gpt-4o-mini                # 判断歧义的模型
AMBIGUITY_TARGET_COUNT=100                 # 实验运行的样本数量
```

### 3. 运行项目

**方式一：运行完整实验 Pipeline**
该命令会依次运行 M1/M2/M3 的 Zero-shot 和 Few-shot 实验，并输出统计结果。
```bash
python -m engineering.pipeline
```

**方式二：启动 FastAPI 服务**
提供 HTTP 接口供前端调用。
```bash
uvicorn engineering.main:app --reload --host 0.0.0.0 --port 8000
```
API 文档地址：`http://localhost:8000/docs`

## 数据集替换指南

### 1. 替换/新增数据库
将你的 SQLite 数据库文件（`.sqlite`）放入 `databases/` 目录。
*   例如：`databases/MyNewDB/MyNewDB.sqlite`

### 2. 替换测试数据集
修改根目录下的 `kaggle_dataset.csv` 文件。
*   **格式要求**：CSV 必须包含以下列：
    *   `nl` (或 `question`, `nlq`)：自然语言问题
    *   `sql` (或 `gold`, `query`)：标准答案 SQL（用于评估正确性）
    *   `db_id` (或 `db`, `target_db`)：对应的数据库名称（需与 `databases/` 下的文件名一致）

### 3. 替换 Few-shot 题库
如果需要使用自定义的 Few-shot 示例，请在 `KaggleDBQA-main/examples/` 下添加或修改 `.json` 文件。
*   **格式**：
    ```json
    [
      {
        "question": "...",
        "query": "SELECT ...",
        "db_id": "..."
      },
      ...
    ]
    ```
