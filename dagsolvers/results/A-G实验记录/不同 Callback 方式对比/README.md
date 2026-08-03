# Callback Order 1800 秒实验结果

本目录保存 callback separation order 的筛选结果：原始完整运行32次、8次 ER4 新顺序实验，以及从自动重跑记录中筛选的8次 ER5 严格双阶段顺序实验，共48次。`callback_order_1800_experiments.csv` 已按正式的 `callback_order_runs.csv` 精确筛选为同一组48次运行；重复重跑、未完成及仍标记为运行中的记录已剔除。筛选前的99行版本保存在 `callback_order_1800_experiments.csv.bak-before-48-run-filter-20260721`。

## 实验设计

- 图模型：`cliquefree-er`
- 特征数：20
- 样本数：2000
- `p`：0
- 单次时间上限：1800 秒
- Seed：1、2、3、4
- 图密度配置：
  - `er-4-0`：`intra_edge_ratio=4`、`inter_edge_ratio=4`
  - `er-5-0`：`intra_edge_ratio=5`、`inter_edge_ratio=5`
- 方法：
  - `Cycle-only`
  - `Clique-only`
  - `Cycle-early`（原始日志中的旧 `Cycle-first`，找到cycle后短路）
  - `Clique-early`（原始日志中的旧 `Clique-first`，找到clique后短路）
  - `Cycle-then-Clique`（ER4/ER5，两个阶段都执行）
  - `Clique-then-Cycle`（ER4/ER5，两个阶段都执行）

总实验数：

```text
原始4 methods × 2 densities × 4 seeds = 32 runs
新增2 methods × 2 densities × 4 seeds = 16 runs
合计48 runs
```

## 运行时间边界

- 首次干净运行开始：2026-07-18 20:55:55 CEST
- 首次干净运行结束：2026-07-19 13:03:48 CEST
- 干净 combined log：`logs/callback_order_1800_original_32.log`

该日志以首次 `[RUNNER] ... finished` 为结束边界，包含且仅包含原计划的 32 条 `[EXPERIMENT-METADATA]`。首次完成后的自动重启和重复实验没有收录。

## 目录结构

```text
callback_order_1800_运行结果/
├── README.md
├── callback_order_runs.csv
├── callback_order_summary.csv
├── SHA256SUMS.txt
├── multirun_files_manifest.txt
├── logs/
│   └── callback_order_1800_original_32.log
├── imports/
│   └── callback_order_1800_background_20260719_174714/
│       ├── callback_order_runs.csv
│       └── callback_order_summary.csv
└── multirun/
    ├── 2026-07-18/
    │   ├── 20-55-59/   # Cycle-only, er-4-0
    │   └── 22-56-59/   # Cycle-only, er-5-0
    └── 2026-07-19/
        ├── 00-57-56/   # Clique-only, er-4-0
        ├── 02-58-58/   # Clique-only, er-5-0
        ├── 04-59-58/   # Cycle-early, er-4-0
        ├── 07-00-56/   # Cycle-early, er-5-0
        ├── 09-01-54/   # Clique-early, er-4-0
        └── 11-02-54/   # Clique-early, er-5-0
```

每个 multirun 目录包含 4 个 job 子目录，分别对应 seed 1–4。每个 job 均保留：

- `.hydra/config.yaml`
- `.hydra/hydra.yaml`
- `.hydra/overrides.yaml`
- `config.yaml`
- `W_true.csv`
- `X.csv`
- `run_experiments.log`
- 求解成功时生成的其他结果文件

`Clique-only` 不保证产生 DAG，因此没有 `W_est.csv` 不表示实验未完成。其 8 个 job 均在独立日志中包含 `SOLVER FINISHED`。

## 结果文件

### `callback_order_runs.csv`

包含48行逐实验结果。每种方法在 ER4/ER5 上均有 seed 1--4。主要字段：

- `graph_density`：`er-4-0` 或 `er-5-0`
- `method`：callback 方法
- `seed`：随机种子
- `callback_inside_seconds`：Gurobi 报告的 user callback 时间
- `callback_inside_ratio`：callback 时间占总求解时间的比例
- `callback_outside_seconds`：总求解时间减 callback 时间
- `callback_outside_ratio`：callback 外时间比例
- `lazy_constraints`：Gurobi 日志报告的 lazy constraints 数量
- `nodes`：explored nodes
- `gap`：最终 MIP gap，单位为百分数
- `mipsol_total`：MIPSOL callback 候选总数
- `rejection_rate`：被 lazy constraints 拒绝的 MIPSOL 比例
- `cycle_cuts`：加入的 cycle constraints 数量
- `clique_cuts`：加入的 clique constraints 数量
- `solve_after_last_constraint_seconds`：最后一次加入约束后继续求解的时间

### `callback_order_summary.csv`

包含12行汇总结果：6种方法在 ER4/ER5 上的全部组合。每行是对应4个seed的算术平均值，`seeds=4`。

## 完整性验证

整理时已完成以下验证：

- `callback_order_runs.csv`：48行数据，无重复的“密度×方法×seed”键
- `callback_order_summary.csv`：12行数据，无重复的“密度×方法”键
- multirun job：32 个
- Hydra config：32 份
- `W_true.csv`：32 份
- 独立 `run_experiments.log`：32 份
- 包含 `SOLVER FINISHED` 的独立日志：32/32
- 每个“方法 × 密度”组合均包含 seed 1、2、3、4
- 原始32行仍可由干净 combined log重新解析；新增8行的原始来源CSV保存在 `imports/` 中

可执行以下命令检查 combined log 的实验数量：

```bash
rg -c '^\[EXPERIMENT-METADATA\]' logs/callback_order_1800_original_32.log
```

预期输出：

```text
32
```

检查所有独立 job 是否完成：

```bash
rg -l 'SOLVER FINISHED' multirun/*/*/*/run_experiments.log | wc -l
```

预期输出：

```text
32
```

## 校验和

`SHA256SUMS.txt` 保存以下关键文件的 SHA-256：

- `callback_order_runs.csv`
- `callback_order_summary.csv`
- `logs/callback_order_1800_original_32.log`

验证命令：

```bash
shasum -a 256 -c SHA256SUMS.txt
```

`multirun_files_manifest.txt` 列出本目录收录的所有 multirun 文件，用于审计和归档。
