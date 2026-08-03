# Clique experiment shard schedule

Each solver run has a 1,800-second limit. Shards group all four methods for a
matched data instance and reserve at least two hours of the 24-hour PBS job for
startup, model construction, output synchronization, and shutdown.

| Experiment | Matched instances | Solver runs | Shards | Runs/shard | Worst solver time/shard |
|---|---:|---:|---:|---:|---:|
| ER/SF | 120 | 480 | 12 | 40 | 20 h |
| Real benchmarks | 45 | 180 | 5 | 36 | 18 h |

With two simultaneous MetaCentrum jobs, run one ER/SF shard and one real-data
shard during the first five waves. The sixth through twelfth ER/SF shards can
then use both slots in pairs. This requires nine waves in the worst case. If
each wave consumes the full limit, the calendar time is about nine days; most
runs are expected to finish before their individual limit.

Example first wave:

```bash
qsub -v EXPERIMENT_KIND=er_sf,SHARD_INDEX=0,SHARD_COUNT=12 \
  cluster_computing/run_clique_shard_metacentrum.pbs
qsub -v EXPERIMENT_KIND=real,SHARD_INDEX=0,SHARD_COUNT=5 \
  cluster_computing/run_clique_shard_metacentrum.pbs
```

Submit ER/SF indices `0..11` exactly once and real-data indices `0..4`
exactly once. Outputs are written into shard-specific directories under
`metacentrum_runs/`.
