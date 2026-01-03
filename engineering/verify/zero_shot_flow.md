# Zero-Shot 实验流程（工程版）

## 总览
- 目标：复现论文中的零样本 NL2SQL 流程，不引入示例（few-shot）。
- 方法：M1 基线（Baseline 简单反馈）、M2 Sphinteract（SRA Clarification）、M3 Break No Ambiguity（SRA + ES）。
- 约束：温度 `0`，每题最多 4 轮交互；当 SQL 语法错误时允许一次“修无效”纠错；不使用 few-shot 示例。

## 数据与路径
- 数据加载：`engineering/pipeline.py:50-57` 使用 `resolve_dataset_path('kaggle_dataset.csv')` 加载 CSV。
- 路径解析：`engineering/io/paths.py:26-36` 支持 `.env` 中的 `KAGGLE_DATASET_PATH`。
- .env 加载：包导入时自动读取 `engineering/.env`（`engineering/__init__.py:4-22`）。

## 样本筛选（模糊问题）
- 列映射：`engineering/pipeline.py:82-94` 自动识别 `nl` 与 `sql` 列。
- 强校验：若无 `nl` 或无 `sql`，丢弃并在终端提示（`engineering/pipeline.py:100-114`）。
- 模糊判定：`is_ambiguous_llm`（`engineering/pipeline.py:28-48`）基于架构与问题，用 LLM 返回“Ambiguous/Not”。
- 采样：收集满足条件的前 `k` 条（默认 30，`engineering/pipeline.py:135-139`）。

## 数据库准备
- 基于 CSV 构建临时 SQLite（表名 `kaggle`）：`engineering/debug/flow_demo.py:71-91`。
- 动态生成数据库 Schema：`engineering/db/schema.py:3-16`，供提示使用。
- 获取 Schema 与 DB 路径：`engineering/db/locator.py:1-18`。

## M1 基线（Zero-Shot Baseline）
- 初始提示（DAIL-SQL 风格）：
  - 前缀：`Complete sqlite SQL query only and with no explanation.`
  - 内容：`/* Given the following database schema: */ {schema} {meta} /* Answer the following with no explanation: {nlq} */`
  - 代码位置：`engineering/experiments/baseline.py:28-33`（已对齐 DAIL-SQL 前缀）
- 生成 SQL 并清洗：`engineering/experiments/baseline.py:33-34`，`engineering/utils/sanitize.py`。
- 执行与评估：`engineering/experiments/baseline.py:35-43`，底层执行器 `engineering/db/exec.py:1-44`。
- 修无效（仅一次）：若初次不可执行，提供异常信息进行“修无效”（`engineering/experiments/baseline.py:37-43`）。
- 零交互终止：`run_pipeline` 在零样本模式对 M1 传入 `max_rounds=0`（`engineering/pipeline.py:141-143` 已改为 `engineering/pipeline.py:141` 的 M1 行）。

## M2 Sphinteract（Zero-Shot, SRA Clarification）
- 初始提示同 DAIL-SQL：`engineering/experiments/sphinteract.py:28-33`（已加前缀）。
- 若不正确，进入交互轮：
  - 生成澄清问题（SRA）：`engineering/llm/prompts.py:1-49`，调用位置 `engineering/experiments/sphinteract.py:58-60`。
  - 反馈模拟（Oracle）：用 `gold_sql` + CQ 生成用户选项回答：`engineering/experiments/sphinteract.py:70-78`。
  - 带反馈的 SQL 再生成：`sql_generation_v2`，`engineering/experiments/sphinteract.py:88-93`。
  - 评估执行：`engineering/experiments/sphinteract.py:95-105`。
- 轮次上限：最多 4 轮（由 `run_pipeline` 的 `max_rounds` 控制）。

## M3 Break No Ambiguity（Zero-Shot, SRA + ES）
- 初始提示同 DAIL-SQL：`engineering/experiments/break_no_ambiguity.py:27-33`（已加前缀）。
- 若不正确，进入交互轮：
  - 生成澄清问题（SRA + ES 指令）：`engineering/llm/prompts.py:SRA_ES`（模板位置同文件，调用 `engineering/experiments/break_no_ambiguity.py:57-59`）。
  - 早停：若模型输出 `NO AMBIGUITY`，提前终止交互（`engineering/experiments/break_no_ambiguity.py:60-61`）。
  - 反馈与再生成：`engineering/experiments/break_no_ambiguity.py:71-73, 88-93`。
  - 评估执行：`engineering/experiments/break_no_ambiguity.py:95-105`。
- 轮次上限：最多 4 轮（由 `run_pipeline` 的 `max_rounds` 控制）。

## 统一执行入口与统计
- 入口：`run_pipeline`（`engineering/pipeline.py:135-164`）。
- 零样本设置：
  - M1：`max_rounds=0, n_shots=0`（只做初次生成与一次“修无效”）。
  - M2/M3：`max_rounds=4, n_shots=0`（交互但不引入示例）。
- 输出统计：各方法的行数与平均准确率（`engineering/pipeline.py:147-153`）。

## 运行方式
- 包运行（推荐）：`python3 -m engineering.pipeline`
- 单文件运行（IDE 直接运行已支持）：`python3 engineering/pipeline.py`

## 与论文的一致性与改动
- DAIL-SQL 前缀已在所有初次生成提示中加入（Baseline/M2/M3）。
- 零样本流程确保 `n_shots=0`，不引入示例检索。
- 轮次控制对齐“最多四次交互”；M1 作为零交互基线（仅一次“修无效”）。
- 为保证评估真实性，`extract_ambiguous_samples` 严格丢弃缺失 `nl/sql` 的样本并报错，不再使用占位 SQL（`engineering/pipeline.py:100-118`）。

## 代码参考（快速定位）
- Baseline 主流程：`engineering/experiments/baseline.py:18-75`
- Sphinteract 主流程：`engineering/experiments/sphinteract.py:18-134`
- Break No Ambiguity 主流程：`engineering/experiments/break_no_ambiguity.py:18-126`
- 提示模板：`engineering/llm/prompts.py:1-100, 264-275`
- 执行与评估：`engineering/db/exec.py:1-44`
- 清理 SQL：`engineering/utils/sanitize.py`
