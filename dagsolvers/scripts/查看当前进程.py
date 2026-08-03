import re
import subprocess

output = subprocess.check_output(
    [
        "ps", "-ww", "-axo",
        "pid=,ppid=,etime=,%cpu=,%mem=,state=,command="
    ],
    text=True,
)

processes = {}

for line in output.splitlines():
    parts = line.strip().split(None, 6)
    if len(parts) != 7:
        continue

    pid, ppid, elapsed, cpu, mem, state, command = parts

    processes[int(pid)] = {
        "pid": int(pid),
        "ppid": int(ppid),
        "elapsed": elapsed,
        "cpu": cpu,
        "mem": mem,
        "state": state,
        "command": command,
    }

def argument(command, name, default="-"):
    match = re.search(
        rf"(?:^|\s){re.escape(name)}=(\S+)",
        command,
    )
    return match.group(1) if match else default

rows = []

for process in processes.values():
    command = process["command"]

    if "run_experiments.py" not in command:
        continue

    parent = processes.get(process["ppid"], {})
    parent_command = parent.get("command", "-")

    script_match = re.search(
        r"scripts/([^/\s]+\.sh)",
        parent_command,
    )
    script = script_match.group(1) if script_match else "-"

    experiment = argument(command, "experiment")
    ratio = argument(command, "++problem.intra_edge_ratio")
    features = argument(command, "problem.number_of_variables")
    samples = argument(command, "problem.number_of_samples")
    seeds = argument(command, "problem.seed")
    big_m = argument(command, "solver.weights_bound")

    configuration = (
        f"ER-{ratio}、d={features}、n={samples}、"
        f"seed={seeds}、M={big_m}"
    )

    rows.append([
        process["ppid"],
        process["pid"],
        parent.get("elapsed", "-"),
        process["elapsed"],
        experiment,
        configuration,
        process["cpu"] + "%",
        process["state"],
        script,
    ])

print("| 父 PID | 子 PID | 父进程已运行 | 子任务已运行 | 当前实验 | 配置 | CPU | 状态 | 脚本 |")
print("|---:|---:|---:|---:|---|---|---:|---|---|")

for row in rows:
    print("| " + " | ".join(map(str, row)) + " |")

if not rows:
    print("| - | - | - | - | 当前没有实验运行 | - | - | - | - |")
