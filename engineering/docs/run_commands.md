# 运行命令集合

- **本地运行（CLI）**
  - ‘source .env && export PROJECT_ROOT=$(pwd) && export AMBIGUITY_TARGET_COUNT=10 && export AMBIGUITY_USE_LLM=1 && export LLM_MODE="" && python3 -u -m engineering.pipeline | tee engineering/logs/pipeline_run_$(date +%Y%m%d_%H%M%S).log’

- **自定义配置运行（高级）**
  - 设置数据集大小并记录日志：
    ```bash
    export PROJECT_ROOT=$(pwd)
    export AMBIGUITY_TARGET_COUNT=10  # 设置实验数据条数
    export AMBIGUITY_USE_LLM=1        # 启用 LLM 模糊性检测 (0 为禁用)
    python3 -u -m engineering.pipeline | tee engineering/logs/pipeline_run_$(date +%Y%m%d_%H%M%S).log
    ```

- **构建 Docker 镜像**
  - Apple Silicon 本地测试（arm64）：
    - `docker build --platform linux/arm64 -f engineering/Dockerfile -t text2sql-mc:latest .`
  - 远程服务器通用构建（amd64）：
    - `docker build --platform linux/amd64 -f engineering/Dockerfile -t text2sql-mc:latest .`

- **运行 Docker（远程 LLM）**
  - `docker run --rm \`
  - `  -e OPENAI_API_KEY="your_key" \`
  - `  -e OPENAI_BASE_URL="https://api.openai.com/v1" \`
  - `  -e OPENAI_TIMEOUT="30" \`
  - `  -e PROJECT_ROOT="/app" \`
  - `  text2sql-mc:latest`

- **运行 Docker（离线/Mock LLM）- 注意这里没有接入真实的数据集**
  - `docker run --rm \`
  - `  -e LLM_MODE="mock" \`
  - `  -e PROJECT_ROOT="/app" \`
  - `  text2sql-mc:latest`

- **部署到远程服务器**

  **方法一：源码构建（推荐）**
  1. 将整个项目目录上传至服务器：
     `scp -r /Users/liuzichun/Desktop/Classes/SDSC_5003/Final_Project user@remote_ip:/path/to/project`
  2. 在服务器上构建镜像：
     `cd /path/to/project`
     `docker build -f engineering/Dockerfile -t text2sql-mc:latest .`
  3. 运行容器（参考上方运行命令）。

  **方法二：镜像传输（离线部署）**
  1. 本地构建 amd64 镜像（即使是 Mac 芯片也可构建）：
     `docker build --platform linux/amd64 -f engineering/Dockerfile -t text2sql-mc:amd64 .`
  2. 导出镜像为文件：
     `docker save -o text2sql_image.tar text2sql-mc:amd64`
  3. 上传 tar 包到服务器：
     `scp text2sql_image.tar user@remote_ip:/tmp/`
  4. 服务器导入镜像：
     `docker load -i /tmp/text2sql_image.tar`
  5. 运行容器：
     `docker run --rm -e OPENAI_API_KEY="..." text2sql-mc:amd64`

- **Few-shot 相似度检索（2-shot 示例，远程嵌入）**
  - `export OPENAI_API_KEY="your_key"`
  - `export VECTOR_EMBED_MODE=embed EMBED_DISABLE=0 EMBED_MODE=remote EMBED_MAX_DOCS=64 EMBED_BATCH_SIZE=64`
  - `python3 - << 'PY'`
    ```python
    from engineering.pipeline import _QuestionBankVectorStore
    from engineering.io.paths import PROJECT_ROOT
    import os
    qb_dir = os.path.join(str(PROJECT_ROOT), 'KaggleDBQA-main', 'examples')
    vs = _QuestionBankVectorStore(qb_dir, db_filter=None, embed_model=os.getenv('EMBED_MODEL', 'text-embedding-ada-002'))
    nlq = 'Which release type is most popular?'
    docs = vs.similarity_search(nlq, k=2)
    print(f"[DOCS_LEN] {len(docs)}")
    for i, d in enumerate(docs, 1):
        md = d.metadata
        print(f"[{i}] NL: {md.get('nl')}")
        print(f"SQL: {md.get('gold')}\n")
    ```
    `PY`

- **指定数据库与题库（自定义评估数据集）**
  - **运行指令**：
    ```bash
    export PROJECT_ROOT=$(pwd) && 
    export KAGGLE_DATASET_PATH="/path/to/your_dataset.csv"  &&  # 指定评估数据集 (CSV)
    export KAGGLE_QUESTION_BANK_DIR="/path/to/question_bank"  && # 指定 Few-shot 题库目录 (JSONs)
    export AMBIGUITY_TARGET_COUNT=50  &&                        # 指定测试数据条数
    export AMBIGUITY_USE_LLM=1 && export LLM_MODE="" 
    # 确保日志目录存在
    mkdir -p engineering/logs

    # 运行程序：同时输出到终端并保存到日志文件
    python3 -u -m engineering.pipeline | tee engineering/logs/custom_eval_$(date +%Y%m%d_%H%M%S).log
    ```
  - **数据文件要求**：
    - **1. 评估数据集 (CSV)**
      - 格式：CSV 文件 (由 `KAGGLE_DATASET_PATH` 指定)
      - 必须包含以下三类列（任选其一即可识别）：
        - **自然语言问题**: `nl`, `question`, `text`, `nlq`
        - **标准 SQL (Gold)**: `sql`, `gold`, `gold_sql`, `query`
        - **数据库标识**: `db_id`, `db`, `target_db` (对应 SQLite 文件名)
    - **2. 数据库文件 (SQLite)**
      - 格式：SQLite 数据库 (`.sqlite`)
      - 存放位置 (按优先级查找)：
        - `databases/{db_id}/{db_id}.sqlite` (推荐，符合 KaggleDBQA 结构)
        - `databases/{db_id}.sqlite`
        - `{project_root}/{db_id}.sqlite`
      - 方言：默认支持 SQLite 语法。
    - **3. Few-shot 题库 (JSON)**
      - 格式：目录 (由 `KAGGLE_QUESTION_BANK_DIR` 指定)，包含一个或多个 `.json` 文件。
      - 内容结构：JSON 数组，每个元素包含 `question`/`nl`, `query`/`sql`, `db_id`/`db`。
      - 示例：
        ```json
        [
          {
            "question": "Show all student names.",
            "query": "SELECT name FROM students",
            "db_id": "university"
          }
        ]
        ```

- **指定默认数据库与模型**
  - `export DEFAULT_DB="WhatCDHipHop"`
  - `export OPENAI_MODEL="gpt-4o-mini"`
