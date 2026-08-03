# Metacentrum Cluster & Local macOS Experiment Operations Guide

This guide details the common commands used for task submission, status monitoring, data synchronization, and log analysis for the DAG Solver project (`project-bestdagsolverintheworld`) on both the **Metacentrum HPC Platform** and the **local macOS environment**.

---

## 1. Metacentrum Cluster Operations (Server Side)

### 1.1 Job Submission
Navigate to the corresponding directory based on the specific workspace copy and submit the PBS jobs:
```bash
# Workspace Copy 0 (Main Directory)
cd /storage/praha1/home/hexiaoyu/project-bestdagsolverintheworld
source .venv/bin/activate
qsub cluster_computing/run_exdbn_clique_metacentrum.pbs

# Workspace Copy 1
cd /storage/praha1/home/hexiaoyu/project-bestdagsolverintheworld1
qsub cluster_computing/run_exdbn_clique_metacentrum.pbs
```

### 1.2 Monitoring Job Status
```bash
# List a summary of all active jobs for the current user
qstat -u hexiaoyu

# Check the exact executing node assigned to a specific job (filter by exec_host2)
qstat -f 21717257.pbs-m1.metacentrum.cz | grep exec_host2
# Example Output: exec_host2 = elmu1-17.hw.elixir-czech.cz:15002/11*2

# Check core job execution state, resource usage, and IO paths
qstat -f 21779812.pbs-m1.metacentrum.cz | egrep "job_state|resources_used|exec_host|Output_Path|Error_Path"
```

### 1.3 Terminating Jobs
```bash
# Kill a specific PBS job
qdel 22487945.pbs-m1.metacentrum.cz || qdel 22487945
```

### 1.4 Interactive Access to Assigned Nodes
```bash
# Log in directly via SSH to the specific compute node allocated to your running job for debugging
ssh elmu1-17.hw.elixir-czech.cz
```

### 1.5 Viewing Real-time System Logs
```bash
cd /var/spool/pbs/spool/
ls -lh 21717257*
tail -f 21717257.pbs-m1.metacentrum.cz.OU
```

### 1.6 Verifying the Python Environment
```bash
source .venv/bin/activate 
which python 
python -c "import sys; print(sys.executable)"
```

---

## 2. Data Analysis & Summary Table Generation

### 2.1 Quick Script Aggregation
```bash
cd /storage/praha1/home/hexiaoyu/project-bestdagsolverintheworld1/dagsolvers
sh /storage/praha1/home/hexiaoyu/project-bestdagsolverintheworld1/dagsolvers/scripts/summary.sh
```

### 2.2 Aggregating A-G Experiment Results
Navigate to the test workspace and use the Python interpreter from the main virtual environment to execute the aggregation:

```bash
cd /storage/praha1/home/hexiaoyu/project-bestdagsolverintheworld-test

# Standard Mode (Outputs 96 metrics, outputs to A-G_experiments.csv)
/storage/praha1/home/hexiaoyu/project-bestdagsolverintheworld/.venv/bin/python \
  dagsolvers/scripts/summarize_ag_runs.py \
  metacentrum_runs \
  --output reports/A-G_experiments.csv

# Strict Mode
/storage/praha1/home/hexiaoyu/project-bestdagsolverintheworld/.venv/bin/python \
  dagsolvers/scripts/summarize_ag_runs.py \
  metacentrum_runs \
  --output reports/A-G_experiments.csv \
  --strict
```

> 💡 **Inspection and Resume Process**:
> 1. Open the generated `reports/A-G_experiments.csv` and check which rows have **missing degree** values.
> 2. Once the gaps are identified, restart the `Test_new.sh` script to resume background execution seamlessly.

---

## 3. Bidirectional Synchronization (Rsync)

### 3.1 Partial Copy: Download Diagnostics & Logs Only
Sync only log files, configurations, and metric outputs (JSON, CSV). Heavy weight files and raw datasets are skipped:
```bash
mkdir -p /Users/xiaoyuhe/Downloads/metacentrum_logs_complete

rsync -av --prune-empty-dirs \
  --include='*/' \
  --include='run_experiments.log' \
  --include='config.yaml' \
  --include='*_summary_diagnostics.json' \
  --include='*_mipsol_diagnostics.csv' \
  --include='*_progress_diagnostics.csv' \
  --include='*_root_diagnostics.csv' \
  --exclude='*' \
  hexiaoyu@skirit-lite.metacentrum.cz:/storage/praha1/home/hexiaoyu/project-bestdagsolverintheworld-test/metacentrum_runs/ \
  /Users/xiaoyuhe/Downloads/metacentrum_logs_complete/
```

### 3.2 Backup Copy: Full Project Download from Server
Exclude virtual environments, caches, bulky runtime artifacts, and plots to create a clean code backup:
```bash
rsync -avz \
  --exclude='.git/' \
  --exclude='.venv/' \
  --exclude='venv/' \
  --exclude='env/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='.DS_Store' \
  --exclude='dagsolvers/results/' \
  --exclude='dagsolvers/reports/' \
  --exclude='dagsolvers/multirun/' \
  --exclude='dagsolvers/outputs/' \
  --exclude='dagsolvers/logs/' \
  --exclude='dagsolvers/mlruns/' \
  --exclude='dagsolvers/metacentrum_runs/' \
  --exclude='data/' \
  --exclude='datasets/' \
  --exclude='*.png' \
  --exclude='*.jpg' \
  --exclude='*.jpeg' \
  --exclude='*.pdf' \
  --exclude='*.pptx' \
  hexiaoyu@skirit-lite.metacentrum.cz:/storage/praha1/home/hexiaoyu/project-bestdagsolverintheworld/ \
  '/Users/xiaoyuhe/project-bestdagsolverintheworld-服务器当前版本/'
```

### 3.3 Deploy Code: Upload from Local Machine to Server Copy 1
```bash
rsync -avz \
  --exclude='.git/' \
  --exclude='.venv/' \
  --exclude='venv/' \
  --exclude='env/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='.DS_Store' \
  --exclude='.pytest_cache/' \
  --exclude='.mypy_cache/' \
  --exclude='.ruff_cache/' \
  --exclude='dagsolvers/results/' \
  --exclude='dagsolvers/reports/' \
  --exclude='dagsolvers/multirun/' \
  --exclude='dagsolvers/outputs/' \
  --exclude='dagsolvers/logs/' \
  --exclude='dagsolvers/mlruns/' \
  --exclude='dagsolvers/metacentrum_runs/' \
  --exclude='data/' \
  --exclude='datasets/' \
  --exclude='*.log' \
  --exclude='*.png' \
  --exclude='*.jpg' \
  --exclude='*.jpeg' \
  --exclude='*.pdf' \
  --exclude='*.pptx' \
  '/Users/xiaoyuhe/project-bestdagsolverintheworld/' \
  hexiaoyu@skirit-lite.metacentrum.cz:/storage/praha1/home/hexiaoyu/project-bestdagsolverintheworld1/
```

---

## 4. macOS Local Long-Running Experiment Management

### Approach A: Using `launchctl` (Recommended for Anti-Sleep Protection)

#### 4.1 Submitting a Task
This triggers the `/usr/bin/caffeinate` wrapper to prevent your Mac from going to sleep, ensuring unbroken computational runs:
```bash
cd /Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers

JOB_STAMP=$(date +%Y%m%d_%H%M%S)
JOB_LABEL="com.xiaoyuhe.dagsolvers.experiments-ag-${JOB_STAMP}"
JOB_LOG="$PWD/logs/experiments_A-G_${JOB_STAMP}.log"

RUN_COMMAND="cd '$PWD' && exec /usr/bin/caffeinate -dimsu /bin/sh ./scripts/experiments_exdbn_clique1.sh"

mkdir -p logs

launchctl submit \
  -l "$JOB_LABEL" \
  -o "$JOB_LOG" \
  -e "$JOB_LOG" \
  -- /bin/zsh -lc "$RUN_COMMAND"

echo "Job Label: $JOB_LABEL"
echo "Log Path: $JOB_LOG"
```

#### 4.2 Checking & Monitoring Job States
```bash
# Track active Python processes via your inspection script
python3 /Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers/scripts/查看当前进程.py

# Check active experiments currently managed by launchctl
launchctl list | grep -E 'xiaoyuhe.*(experiments|dagsolvers)'
launchctl list | grep experiments-ag

# Print detailed command trees for running scripts before termination
printf '%s\n' '--- running experiment processes before stop ---'
ps -axo pid,ppid,etime,state,command | rg '/scripts/experiments[^ ]*\.sh|run_experiments\.py' | rg -v 'rg ' || true

printf '%s\n' '--- active launchctl experiment jobs ---'
for label in $(launchctl list | awk '$3 ~ /com\.xiaoyuhe.*(experiments|dagsolvers)/ && $1 != "-" {print $3}'); do
  program=$(launchctl print "gui/$(id -u)/$label" 2>/dev/null | sed -n '/arguments = {/,/}/p' | tr '\n' ' ')
  if printf '%s' "$program" | rg -q 'experiments.*\.sh'; then
    echo "$label"
  fi
done

# Print target configurations for an explicit Job Label
launchctl print "gui/$(id -u)/$JOB_LABEL"

# Stream live updates of the log file
tail -f "$JOB_LOG"
```

#### 4.3 Pinpointing Core Experiment PIDs
```bash
pgrep -af 'experiments_A-G.sh|run_experiments.py'
```

#### 4.4 Gracefully Stopping and Cleaning Processes
```bash
# Kill a specific job instance managed by launchctl
launchctl remove "com.xiaoyuhe.dagsolvers.experiments-ag-20260727_235435"

# Clean up all active launchctl instances for this experimental block
for label in $(launchctl list | awk '$3 ~ /com\.xiaoyuhe.*(experiments|dagsolvers)/ && $1 != "-" {print $3}')
do
    echo "Stopping launchctl job: $label"
    launchctl remove "$label"
done

# Gracefully terminate dangling/orphan Python script workers
pkill -TERM -f 'run_experiments\.py' || true

# Gracefully terminate parent runner wrapper Shell instances
pkill -TERM -f '/scripts/experiments[^ ]*\.sh' || true

# Verification (If there is no terminal output, all tasks have fully stopped)
ps -axo pid,ppid,etime,%cpu,%mem,state,command | \
  grep -E '/scripts/experiments[^ ]*\.sh|run_experiments\.py' | \
  grep -v grep

# [Fallback] If processes remain stubborn, force close using SIGKILL (-KILL)
pkill -KILL -f 'run_experiments\.py' || true
pkill -KILL -f '/scripts/experiments[^ ]*\.sh' || true
```
*(Note: Terminating tasks will safely halt execution but will never wipe or compromise existing Hydra data structures, cached logs, or runtime saves that have already been written to the disk).*

---

### Approach B: Using Legacy `nohup` 

#### 4.1 Running in the Background
```bash
cd /Users/xiaoyuhe/project-bestdagsolverintheworld/dagsolvers

nohup sh scripts/experiments_exdbn_clique.sh > experiments_exdbn_clique.log 2>&1 < /dev/null & 
```

#### 4.2 Open log
```bash
tail -f experiments_exdbn_clique.log
```
