# 工程化封装状态与交付计划

## 已完成
- Zero/Few‑shot 流水线（Python）：入口与六版块执行，含样本筛选与统计输出（`engineering/pipeline.py:273-289`, `engineering/pipeline.py:290-319`）
- 歧义筛选：LLM 判定并早停（`engineering/pipeline.py:29-66`, `engineering/pipeline.py:241-243`）
- Schema 获取与执行评估（SQLite）：`get_schema`（`engineering/db/locator.py:6-13`）、`evalfunc`（`engineering/db/exec.py:15-43`）
- 约束注入：统一粒度与合法连接键（`engineering/llm/prompts.py:87-100`），首轮提示已在 M1/M2/M3 注入（`engineering/experiments/baseline.py:28-38`, `engineering/experiments/sphinteract.py:27-38`, `engineering/experiments/break_no_ambiguity.py:27-38`）
- Few‑shot 首轮示例：M1/M2/M3 前置拼接（`engineering/experiments/baseline.py:28-38`, `engineering/experiments/sphinteract.py:28-38`, `engineering/experiments/break_no_ambiguity.py:28-38`）
- 交互链路：M2 SRA+Oracle 反馈+再生成（`engineering/experiments/sphinteract.py:68-107`）；M3 SRA_ES 早停+Oracle 反馈+再生成（`engineering/experiments/break_no_ambiguity.py:69-108`）
- 统计口径：`init_ok/fix_ok/sra_ok/avg_rounds`，`avg_rounds` 仅对 `rounds>0` 计算（`engineering/pipeline.py:260-271`, `engineering/pipeline.py:297-317`）
- 日志输出：统一入口包裹与打印（`engineering/debug/demo.py:8-36`），运行日志写入 `engineering/logs/`

## 未完成
- 统一日志管理（结构化、多级别、滚动存档）
- 只读沙盒执行与 `EXPLAIN` 预算守护（Postgres/MySQL/Oracle）
- 多方言适配（Postgres/MySQL/Oracle），当前仅 SQLite
- REST 接口（HTTP 服务）
- 安全合规：黑/白名单与静态分析拦截、强制 `LIMIT`、禁止 `SELECT *`、只读连接
- 指标看板（执行准确率、Exact Match、CQ 触发/成功率、延迟与失败率）
- 资源编排与监控（算力管控平台）
- 离线部署与数据不外流（无外部依赖方案）
- Git 分支/PR 管理模板、配置模板；CLI/REST 交付脚本

## 完成方案（分模块）
- 统一日志管理
  - 选择：`logging` + `RotatingFileHandler` 或 `structlog`
  - 修改点：替换 `print` 为 `logger` 输出（`engineering/pipeline.py`, `engineering/experiments/*`, `engineering/debug/demo.py:8-36`）
  - 级别定义：TRACE/INFO/WARN/ERROR，模块化 logger 名称
  - 格式：JSON 行或文本行；按日期滚动存档至 `engineering/logs/`
- 只读沙盒执行与 `EXPLAIN` 预算守护
  - Postgres：`psycopg2`，执行 `EXPLAIN (FORMAT JSON)` 估算成本，超阈值拒绝；只读用户
  - MySQL：`pymysql`/`mysqlclient`，执行 `EXPLAIN` 行列估算
  - Oracle：`cx_Oracle`，`EXPLAIN PLAN FOR` + `SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY)`
  - 修改点：扩展 `evalfunc`（`engineering/db/exec.py:15-43`）为方言路由，新增 `eval_pg/eval_mysql/eval_oracle`，统一签名返回 `is_correct/errors/cost`
- 多方言适配
  - 方言选择：在 `run_pipeline` 传入或从 `db_id` 推断
  - 修改点：`engineering/db/locator.py` 增加 DSN/驱动路由；`engineering/utils/sanitize.py:3-28` 方言安全清洗
- REST 接口
  - 框架：`FastAPI`；端点 `/generate`, `/evaluate`, `/pipeline/run`
  - 修改点：新增 `engineering/server/app.py`（路由调用现有函数），`uvicorn` 启动；统一模型/方言配置来自 `.env`

- 安全合规
  - 静态分析：`sqlparse` 检查禁止关键字（`DELETE/UPDATE/DROP`）、禁止 `SELECT *`、强制 `LIMIT`、仅允许 `SELECT/WITH`
  - 连接策略：只读用户/事务只读
  - 修改点：在 `clean_query` 前后新增 `safety_check(sql)`；拦截并返回错误（`engineering/utils/sanitize.py:3-28` 与 `engineering/db/exec.py:15-43`）
- 指标看板
  - 数据源：结构化日志（JSON）+ 结果 DataFrame
  - 展示：`FastAPI` + 前端简单页或接入 Grafana/Prometheus
  - 指标：执行准确率、Exact Match、CQ 触发/成功率、延迟、失败率；源自 `run_pipeline`（`engineering/pipeline.py:290-319`）
- 资源编排与监控
  - 管控平台：对接 K8s/本地 supervisor；暴露 `/health`、Prometheus 指标端点
  - 修改点：REST 服务中新增健康检查与指标导出；部署脚本配合
- 离线部署与数据不外流
  - 模型/检索：使用本地或企业内模型与嵌入；禁用外部 API
  - 数据：数据库连接仅指向内网；日志与缓存落地本机
- Git 分支/PR 管理与交付
  - 流程：`dev`→`feature/*`→PR→`main`；配置模板 `.env.example`、`config.yml`
  - 交付：CLI（`python -m engineering.pipeline`）与 REST（`uvicorn`）脚本、复现实验文档

## 函数与修改点（精确定位）
- 歧义与样本筛选：`is_ambiguous_llm`（`engineering/pipeline.py:29-66`）、`extract_ambiguous_samples`（`engineering/pipeline.py:207-248`）
- 向量库与检索：`_QuestionBankVectorStore`（`engineering/pipeline.py:83-145`）
- 首轮提示（Few‑shot 前置）：M1（`engineering/experiments/baseline.py:28-38`）、M2（`engineering/experiments/sphinteract.py:28-38`）、M3（`engineering/experiments/break_no_ambiguity.py:28-38`）
- 交互链路与反馈块：M2（`engineering/experiments/sphinteract.py:68-107`）、M3（`engineering/experiments/break_no_ambiguity.py:69-108`）
- 约束与模板：`build_metadata_constraints`（`engineering/llm/prompts.py:87-100`）、`feedback_v2`（`engineering/llm/prompts.py:126-142`）、`sql_generation_v2`（`engineering/llm/prompts.py:54-64`）
- 清洗与执行评估：`clean_query`（`engineering/utils/sanitize.py:3-28`）、`evalfunc`（`engineering/db/exec.py:15-43`）
- 统计指标：`_calc_method_stats`（`engineering/pipeline.py:260-271`）、汇总打印（`engineering/pipeline.py:297-317`）

## 多方言适配扩展指南 (Extension Guide for Multi-Dialect)

当前系统仅深度适配 **SQLite**。若需扩展 **Postgres / MySQL / Oracle**，需修改以下核心文件：

### 1. 数据库连接与定位 (`engineering/db/locator.py`)
- **现状**：仅通过 `resolve_db_path` 查找本地 `.sqlite` 文件。
- **修改**：
  - 新增 `get_connection_config(db_id)`：从环境变量读取 DSN 信息（如 `DB_HOST`, `DB_PORT`, `DB_USER`）。
  - 支持 `dialect` 参数路由：`sqlite` 走文件路径，其他走网络连接配置。

### 2. Schema 提取 (`engineering/db/schema.py`)
- **现状**：硬编码查询 `sqlite_master` 表。
- **修改**：
  - 抽象 `SchemaStrategy` 接口。
  - **Postgres**：查询 `information_schema.tables` / `columns` 或调用 `pg_dump -s`。
  - **MySQL**：使用 `SHOW CREATE TABLE`。
  - **Oracle**：查询 `USER_TAB_COLUMNS` 或使用 `DBMS_METADATA.GET_DDL`。

### 3. SQL 执行引擎 (`engineering/db/exec.py`)
- **现状**：直接导入 `sqlite3`，使用 `execute_query_worker` 进行进程隔离执行。
- **修改**：
  - 引入驱动库：`psycopg2` (PG), `pymysql` (MySQL), `cx_Oracle` / `oracledb` (Oracle)。
  - 实现 `ConnectionFactory`：根据方言返回对应的连接对象。
  - 统一异常处理：将不同驱动的 `OperationalError` / `ProgrammingError` 映射为标准错误格式。

### 4. 提示词工程 (`engineering/llm/prompts.py`)
- **现状**：通用 SQL 生成指令，默认为 SQLite 语法（如 `LIMIT`）。
- **修改**：
  - 在 `sql_generation_v2` 等模板中增加 `{dialect}` 变量。
  - 明确方言特性指令：例如对 Oracle 提示 "Use FETCH FIRST n ROWS ONLY or ROWNUM" 而非 `LIMIT`。

### 5. 安全与清洗 (`engineering/utils/sanitize.py`)
- **现状**：通用正则清洗（去除 Markdown，定位 `SELECT`）。
- **修改**：
  - 增加方言特有的注释清洗规则（如 MySQL 的 `#`，Oracle 的 `--`）。
  - 针对 Oracle 禁用 `;` 结尾（视驱动要求而定）。

### 6. 流水线入口 (`engineering/pipeline.py`)
- **修改**：
  - 在 `run_pipeline` 增加 `dialect` 参数（默认 `sqlite`）。
  - 将 `dialect` 信息透传至 `run_section` -> `run_sample`，最终注入 Prompt。

## 环境建议
- 语言与运行
  - Python 3.10+；macOS 开发环境或 Linux 服务器
  - 依赖建议：`fastapi`, `uvicorn`, `psycopg2-binary`, `pymysql`, `cx_Oracle`, `sqlparse`, `scikit-learn`, `rank-bm25`, `pandas`, `numpy`
- 数据库
  - Postgres/MySQL/Oracle 客户端与只读账号；Oracle 需安装 Instant Client 或使用 Thin 模式
- 安全与离线
  - 内网访问、禁止外部 API；环境变量 `.env` 管理凭据与模型参数

## Docker 封装（mac 环境）
- 可否封装：可以
  - 注意事项：Apple Silicon 需 `linux/arm64` 基础镜像；Oracle 驱动可能需要额外镜像与许可
- 封装思路
  - 基础镜像：`python:3.11-slim`（`--platform linux/arm64`）
  - 安装系统依赖：`build-essential`, `libpq-dev`, `default-libmysqlclient-dev`；Oracle 选择 Thin 驱动或单独镜像
  - 安装 Python 依赖：`pip install -r requirements.txt`
  - 运行方式：CLI `python -m engineering.pipeline` 或 REST `uvicorn engineering.server.app:app --host 0.0.0.0 --port 8000`
  - 多阶段构建：分离构建/运行层，减小镜像体积
  - 资源限制：通过 Docker 运行参数或 K8s 配置（CPU/内存）实现预算守护的外层保障
- 不可行情形
  - 若必须使用 Oracle 非 Thin 驱动且无法在 arm64 获得兼容包或许可，需改为 x86_64 构建或跳过 Oracle 支持

## 里程碑
- Stone1：统一日志 + REST 接口 
- Stone2：只读沙盒 + `EXPLAIN` 预算守护 + 安全合规拦截
- Stone3：指标看板 + 资源编排 + Docker 化交付

## 附录：实现细节补充

- 只读沙盒与预算守护返回值与实现
  - 现状：`evalfunc`（SQLite）返回 `(is_correct, errors)`，参考 `engineering/db/exec.py:15-43`。
  - 拟扩展：按方言路由执行 `EXPLAIN` 并统一返回三元组：
    - `is_correct`: 布尔，表示候选 SQL 与 Gold SQL 比对是否一致
    - `errors`: 列表，包含执行或校验过程中的异常
    - `cost`: 数值或结构体，来源于 `EXPLAIN/EXPLAIN PLAN` 的代价与行数等（用于阈值守护与指标看板）
  - 示例（Postgres）：调用 `EXPLAIN (FORMAT JSON)`，解析 `Plan->Total Cost/Actual Rows`；若 `Total Cost` 超过阈值（如 1e6），拒绝执行并返回 `errors` 说明。
  - 设计定位：通过 `eval_pg/eval_mysql/eval_oracle` 实现三路方言适配，并在 `evalfunc` 总入口汇总三元组。

- TF‑IDF + BM25 低置信判定流程示例
  - 索引准备：以“schema 文档+历史正确 SQL”为语料，构建 TF‑IDF 与 BM25 两套索引。
  - 输入 NLQ：对问题分别计算 TF‑IDF 与 BM25 相关性得分，融合为 `score = α*tfidf + (1-α)*bm25`（例如 `α=0.5`）。
  - 低置信判定规则（满足任一触发 CQ）：
    - Top‑1 融合得分低于阈值（如 `<0.35`）
    - Top‑1 与 Top‑2 得分差小（如 `<0.05`），无明显最优片段
    - 片段冲突：Top‑K 在核心列/粒度/口径上互相矛盾（例如 city vs province、是否包含工作日/节假日口径）
    - 列覆盖率不足：NLQ 的关键实体在 Top‑K 片段覆盖率低（如 `<60%`）
  - 行为：低置信仅用于选择 few‑shot 检索器（≥0.75 使用双索引，<0.75 使用原方法）；不再直接触发 CQ。CQ 与再生成仅在“EX=0 则重写”的失败评估链路中执行与记录。

## 执行流程与用户界面示例
- 函数案例（M2 Few‑shot）
  - 构建向量库：`_QuestionBankVectorStore`（`engineering/pipeline.py:84-145`）
  - 计算置信度：融合 TF‑IDF 与 BM25 得分（建议在向量库检索时返回融合分）
  - 选择示例源：
    - 若 `score ≥ 0.75`：`get_few_shot_examples` 以双索引结果拼接
    - 若 `score < 0.75`：使用原有 few‑shot 相似样本召回方法
  - 首轮生成：`run_m2_sample` 首轮提示注入 Schema + 约束 + 示例（`engineering/experiments/sphinteract.py:27-38`）
  - 评估与重写：若评估结果失败（EX=0），进入重写链路；在链路中执行 CQ（`SRA`），Oracle 反馈与再生成（`engineering/experiments/sphinteract.py:68-126`）
  - 统计与日志：记录 `shots_by_dual_index/shots_by_original`，并在 `run_pipeline` 汇总打印（`engineering/pipeline.py:299-319`）
- 用户界面
  - CLI：`python -m engineering.pipeline` 打印样本筛选、方法摘要、统计与每样本日志（含示例源切换统计）
  - REST（可选）：`uvicorn engineering.server.app:app --host 0.0.0.0 --port 8000` 暴露 `/pipeline/run`；请求体包含模型与阈值配置，响应返回分方法摘要与日志指针

## Presto 多源异构联邦查询适配指南 (Extension Guide for Presto/Trino Federation)

本系统完全支持在 Presto/Trino 上运行，从而实现对后端多源数据库（Oracle, MySQL, MongoDB, Hive, Kafka 等）的统一查询。此时，Presto 作为统一的计算引擎和 SQL 方言层，屏蔽了底层异构数据源的差异。

### 架构说明
- **Few-shot 题库**：保持现有的 `.json` 格式不变（KaggleDBQA 格式）。
  - *注意*：JSON 中的 Schema 仅作为 LLM 理解的上下文；实际执行时的 Schema 需从 Presto 实时获取。
- **测试集执行**：直接连接 Presto Coordinator。
- **方言**：LLM 统一生成 **Presto SQL** (ANSI SQL 标准扩展)。

### 需要补充的文件
1.  **`engineering/db/presto_client.py`** (建议新增)：
    - 封装 `presto-python-client` 或 `trino-python-client`。
    - 实现 `PrestoConnection` 类，负责连接池管理和 Catalog/Schema 切换。

### 核心函数修改点

#### 1. 数据库连接定位 (`engineering/db/locator.py`)
- **目标**：将数据集中的 `db_id` 映射为 Presto 的 `Catalog.Schema`。
- **修改函数**：`resolve_db_path(db_id)` -> 重构为 `resolve_db_connection(db_id)`。
- **逻辑**：
  - 读取环境变量 `PRESTO_HOST`, `PRESTO_PORT`, `PRESTO_USER`。
  - 维护一个映射字典（或从 `.env` 读取），例如：`{'geo_nuclear': 'hive.geo_data', 'financial': 'mysql.fin_db'}`。
  - 返回连接配置而非文件路径。

#### 2. Schema 提取 (`engineering/db/schema.py`)
- **目标**：从 Presto 系统表获取表结构。
- **修改函数**：`get_schema(db_id)`。
- **逻辑**：
  - 调用 `presto_client` 执行 SQL：
    ```sql
    SELECT table_name, column_name, data_type 
    FROM information_schema.columns 
    WHERE table_schema = '<mapped_schema_name>'
    ORDER BY table_name, ordinal_position
    ```
  - 将结果格式化为当前项目所需的 DDL 字符串格式（`CREATE TABLE ...`）。

#### 3. SQL 执行引擎 (`engineering/db/exec.py`)
- **目标**：在 Presto 上执行生成的 SQL 并获取结果。
- **修改函数**：`execute_query_worker` (或新增 `execute_query_presto`)。
- **逻辑**：
  - 建立 Presto 连接。
  - 执行生成的 SQL。
  - **特殊处理**：Presto 对类型要求严格，可能需要处理 `DECIMAL` vs `DOUBLE` 的精度差异，或在对比结果时进行类型放宽（Relaxed Comparison）。

#### 4. Prompt 注入 (`engineering/llm/prompts.py`)
- **目标**：告知 LLM 生成 Presto 方言。
- **修改函数**：`sql_generation_v2`, `initial_prompt` 等。
- **逻辑**：
  - 在 System Prompt 中明确：`"Use Presto SQL dialect."`
  - 针对性提示：
    - 聚合函数：`approx_distinct()` vs `count(distinct)`（视精度要求）。
    - 日期处理：使用 `date_parse`, `format_datetime` 等 Presto 特有函数。
    - JSON 处理：针对 MongoDB 源，使用 `json_extract`。

#### 5. 流水线配置 (`engineering/pipeline.py`)
- **修改**：
  - 增加环境变量 `EXECUTION_ENGINE=presto`。
  - 在 `run_pipeline` 初始化时，加载 Presto 驱动而非 SQLite 驱动。

### 依赖补充 (`requirements.txt`)
- 添加：`presto-python-client` 或 `trino`。
