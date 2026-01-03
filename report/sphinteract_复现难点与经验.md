# 复现 Sphinteract 实验的难点与经验

**数据与任务背景**
- 使用 KaggleDBQA 数据集，在 30 条经“Ambiguous”筛选的样本上复现三种方法（M1/M2/M3）。
- 统一的可视化与结果结构由 `experiment_results.json` 驱动，生成位置 `reproduce_sphinteract_ambiguity.py:1237-1245`。

**主要难点**
- 外部 API 的稳健调用与限流
  - 问题：502/429/超时等导致“LLM error (error); giving up”以及返回 HTML 片段污染日志。
  - 解决：在 `LLM_generation` 中加入多模型回退与指数退避，并根据错误类型打标；配置化模型 `AMBIGUITY_MODEL`，见 `reproduce_sphinteract_ambiguity.py:121-174`、`1207-1251`。
- Ambiguous 样本筛选的一致性与效率
  - 需求：并行调用、达到目标数量即提前停止，错误样本不计入“清晰/模糊”。
  - 方案：批量并行 + 三态判定（True/False/None），并在达到 `target_n` 立即停止后续批次，见 `reproduce_sphinteract_ambiguity.py:1433-1477`；Notebook 版本同步于 `reproduction_sphinteract_ambiguity_generated.ipynb:1629-1671`。
- 交互式方法的并行化与可重复性
  - 方法一与方法三已并行；方法二原为顺序实现，改造成 `ThreadPoolExecutor` 并行入口，具体见 `reproduce_sphinteract_ambiguity.py:1018-1037`，单样本逻辑在 `run_m2_sample`。
- SQL 可执行性与语法修复的区分
  - 问题：把“语法修复后正确”与“交互后正确/初始正确”混淆。
  - 方案：状态标签统一在可视化前计算：`Syntax Fix Correct`、`Interactive Correct`、`Initial Correct`、`Incorrect`，见 `reproduce_sphinteract_ambiguity.py:1225-1234`、`1304-1316`。
- Few-shot 取例与颜色编码一致性
  - Few-shot 示例通过向量库检索（若存在 `./userstudy_chroma`），见 Notebook 头部初始化；绘图中 Few-shot 使用 Zero-shot 基色的亮色版本以强化区分。
- 配置管理与环境加载
  - `.env` 中 `OPENAI_API_KEY`/`OPENAI_BASE_URL` 正确导入，见 Notebook 头部初始化；模型并发度由 `AMBIGUITY_WORKERS` 控制，默认 8。

**工程性取舍与设计**
- 并发度默认 20（方法并行），筛选并发度从环境读取（默认 8），在速率与稳定性间权衡；需要更保守时建议下调。
- 早停策略在批内就地终止收集，并在批间循环条件上停止后续批次，兼顾吞吐与目标达成。
- 统一 JSON 结果结构，避免 Notebook 与脚本间状态不一致，便于二次绘图与报告生成。

**复现中的关键经验**
- 将异常转化为类别标签，而非直接打印原始 HTML/错误串，能显著提升可观测性与日志卫生。
- 以“可执行性校验 → 语法修复 → 交互”分层推进，能更稳定地提升成功率并减少不必要的交互轮数。
- 并行的最佳实践：批量大小与并发度一致，避免单批过长阻塞；对高错误率批次增加短暂冷却窗口。
- 图表的“单一数据源”策略（统一读取 `experiment_results.json`）可降低 Notebook 断点执行造成的可视化偏差。

**可定位的关键代码**
- 可视化与 JSON 保存：`reproduce_sphinteract_ambiguity.py:1207-1262`, `1304-1345`。
- Ambiguous 并行筛选与早停：`reproduce_sphinteract_ambiguity.py:1433-1477`。
- 方法二并行入口：`reproduce_sphinteract_ambiguity.py:1018-1037`；方法一入口：`reproduce_sphinteract_ambiguity.py:697`；方法三入口：`reproduce_sphinteract_ambiguity.py:1182`。
- 语法修复与状态聚合：`reproduce_sphinteract_ambiguity.py:1225-1234`, `1304-1316`。

**后续改进方向**
- 将 LLM 请求改造为异步（aiohttp/async OpenAI SDK）以实现批内真正中断；当前实现已满足“并行+目标达成即停止后续批次”。
- 将测试集难度分布随结果一并保存，便于报告中的一致溯源。
