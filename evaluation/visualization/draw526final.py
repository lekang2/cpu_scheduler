

import os, numpy as np, matplotlib
import matplotlib.pyplot as plt
import statsmodels.api as sm
import re
import glob
import pandas as pd
import statsmodels.api as sm
import matplotlib.ticker as mtick 

############################################
# 1) Configuration & Helper Functions
############################################

# Path configurations - adjust to match your environment
workload_path = "C:/myfile/master/thesis/project/code/evaluation/workload_and_result/0618/result/int/"
#workload_path = "C:/myfile/master/thesis/project/code/evaluation/workload_and_result/0404/revise_result/workload02/"
optimal_path  = "C:/myfile/master/thesis/project/code/evaluation/optimal.txt" 
refer_path    = "C:/myfile/master/thesis/project/code/evaluation/workload_and_result/0618/workload/workload101.txt"
#refer_path    = "C:/myfile/master/thesis/project/code/evaluation/workload_and_result/0404/workload/workload02.txt"
#workload_path = "C:/myfile/master/thesis/project/code/evaluation/workload_and_result/0412/result/workload09/"
#refer_path    = "C:/myfile/master/thesis/project/code/evaluation/workload_and_result/0412/workload/workload09.txt"
scheduler_types = ["invocation50","invocation80","invocation100","invocation150"]

matplotlib.use('Agg')
matplotlib.rcParams['pdf.fonttype'] = 42
matplotlib.rcParams['ps.fonttype']  = 42
plt.rcParams.update({
    'font.family'       : 'sans-serif',
    'font.sans-serif'   : ['Arial'],
    'font.size'         : 16,
    'axes.linewidth'    : 1.5,
    'xtick.major.width' : 1.5,
    'ytick.major.width' : 1.5,
    'ytick.minor.width' : 1.5,
    'text.usetex'       : False,
    'mathtext.fontset'  : 'dejavuserif'
})


sched_colors = {
    "ideal":"#076AEB",
    "srtf": "#F89306",  # grey
    "sfs": "#3498DB",  # blue
    "tla": "#E74C3C",  # red
    "cfs": "#2ECC71",  # green
    "rr": "#DD7404", 
    "fifo": "#8E44AD",  # purple
}

for s in scheduler_types:
    sched_colors.setdefault(s, None)   # fall-back = matplotlib default
# We will parse these 4 schedulers, and then add "ideal"
#scheduler_types = ["cfs", "sfs", "tla", "srtf","rr","fifo"]
#scheduler_types = ["srtf","tla","sfs","cfs","rr","fifo"]
#scheduler_types = ["srtf","tla","cfs","sfs"]
#scheduler_types = ["srtf","tla","sfs"]

def convert_to_milliseconds(value, unit):
    """
    Convert time strings to milliseconds.
    Handles these formats: 
      - (XX)mYY.s   (like '1m31.174608791' if unit == 's')
      - microseconds (µs)
      - milliseconds (ms)
      - seconds (s)
    """
    # Example: "1m31.1746" with unit=="s"
    if 'm' in value and unit == 's':
        mins, secs = value.split('m')
        return int(mins) * 60 * 1000 + float(secs) * 1000
    if unit == "µs":
        return float(value) / 1000.0
    elif unit == "ms":
        return float(value)
    elif unit == "s":
        return float(value) * 1000.0
    else:
        raise ValueError(f"Unknown time unit: {unit}")

############################################
# 2) Load SLO (and thus 'ideal') times
############################################

# slo_values[fibN] = SLO_time_in_ms
slo_values = {}
with open(optimal_path, "r") as f:
    for line in f:
        parts = line.strip().split()
        if len(parts) == 2:
            fib_n = int(parts[0])
            slo_time_ms = float(parts[1])
            slo_values[fib_n] = slo_time_ms

# We'll also need to map from "fib39" -> actual fibN, so we can look up SLO
fib_id_to_n = {}
with open(refer_path, "r", encoding="utf-8") as f:
    for line in f:
        parts = line.strip().split()
        if len(parts) >= 3:
            # e.g. 'fib39 21xxx 21'
            fib_id_str = parts[0]  # 'fib39'
            fib_n      = int(parts[2])
            fib_id_to_n[fib_id_str] = fib_n

############################################
# 3) Parse Execution Times from Logs
############################################

# We'll store data in these structures:
# execution_data[scheduler][fib_id_int] = <avg execution time in ms>
# tail_latency_data[scheduler][fib_id_int] = <(turnaround/SLO) - 1>

execution_data = {}
tail_latency_data = {}

for sched in scheduler_types:
    file_list = sorted(glob.glob(os.path.join(workload_path, f"{sched}.txt")))
    execution_records = {}
    for file_path in file_list:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                match = re.search(
                    r"logs TIME:\s+fib(\d+)\s+([\d.]+)(µs|ms|s)\s+((?:\d+m)?[\d.]+)(µs|ms|s)\s+Request#\s+(\d+)",
                    line
                )
                if match:
                    fib_id_int = int(match.group(1))
                    # The second group is not relevant for final exec time, the 4th group is
                    exec_time_value = match.group(4)
                    exec_time_unit  = match.group(5)
                    exec_time_ms    = convert_to_milliseconds(exec_time_value, exec_time_unit)
                    execution_records.setdefault(fib_id_int, []).append(exec_time_ms)
    
    # Average each fib's times
    avg_exec_time = {k: np.mean(v) for k, v in execution_records.items()}
    execution_data[sched] = avg_exec_time

    # Tail lat = (exec_time / SLO) - 1
    tail_latencies = {}
    for fib_id, avg_time in avg_exec_time.items():
        fib_key = f"fib{fib_id}"
        if fib_key in fib_id_to_n:
            fib_n = fib_id_to_n[fib_key]
            if fib_n in slo_values:
                slo_time = slo_values[fib_n]
                tail_latencies[fib_id] = max((avg_time / slo_time) - 1,0)
    tail_latency_data[sched] = tail_latencies

#print(execution_data["sfs"])

############################################
# 4) Add "ideal" Scheduler (Unlimited Resource)
############################################

# "ideal" means execution == SLO time, so tail latency = 0
ideal_exec_data = {}
ideal_tail_data = {}

for fib_key, fib_n in fib_id_to_n.items():
    fib_id_int = int(fib_key.replace("fib",""))
    if fib_n in slo_values:
        # If "ideal" = SLO, then tail = 0
        e_time_ms = slo_values[fib_n]
        ideal_exec_data[fib_id_int] = e_time_ms
        ideal_tail_data[fib_id_int] = (e_time_ms / e_time_ms) - 1  # 0

execution_data["ideal"] = ideal_exec_data
tail_latency_data["ideal"] = ideal_tail_data

scheduler_types.append("ideal")
scheduler_types = sorted(scheduler_types, key=lambda s: 0 if s == 'ideal' else 1)

############################################
# 5) Create percentiles_with_schedulers.txt
#    (Execution times: P90, P95, P99, P99.9)
############################################

exec_percentiles_needed = ["P90", "P95", "P99", "P99.9"]

# We'll store them in a dict for convenience
execution_percentiles = {}
for sched in scheduler_types:
    times = list(execution_data[sched].values())
    if len(times) == 0:
        execution_percentiles[sched] = {"P90":0,"P95":0,"P99":0,"P99.9":0}
        continue
    execution_percentiles[sched] = {
        "P90":   np.percentile(times, 90),
        "P95":   np.percentile(times, 95),
        "P99":   np.percentile(times, 99),
        "P99.9": np.percentile(times, 99.9)
    }

exec_table_path = os.path.join(workload_path, "percentiles_with_schedulers.txt")
with open(exec_table_path, "w") as f:
    f.write("Scheduler\tP90\tP95\tP99\tP99.9\n")
    for sched in scheduler_types:
        pvals = execution_percentiles[sched]
        row = [f"{pvals['P90']:.2f}", f"{pvals['P95']:.2f}",
               f"{pvals['P99']:.2f}", f"{pvals['P99.9']:.2f}"]
        f.write(f"{sched}\t" + "\t".join(row) + "\n")

############################################
# 6) Create tail_with_schedulers.txt
#    (Tail latencies: P50, P90, P99, P99.9)
############################################

tail_percentiles_needed = ["P90", "P95", "P99", "P99.9"]

tail_percentiles = {}
for sched in scheduler_types:
    tails = list(tail_latency_data[sched].values())
    #if sched=='srtf':
    #    print(tails)
    if len(tails) == 0:
        tail_percentiles[sched] = {"P90":0,"P95":0,"P99":0,"P99.9":0}
        continue
    tail_percentiles[sched] = {
        "P90":   np.percentile(tails, 90),
        "P95":   np.percentile(tails, 95),
        "P99":   np.percentile(tails, 99),
        "P99.9": np.percentile(tails, 99.9)
    }

tail_table_path = os.path.join(workload_path, "tail_with_schedulers.txt")
with open(tail_table_path, "w") as f:
    f.write("Scheduler\tP90\tP95\tP99\tP99.9\n")
    for sched in scheduler_types:
        pvals = tail_percentiles[sched]
        row = [f"{pvals['P90']:.4f}", f"{pvals['P95']:.4f}",
               f"{pvals['P99']:.4f}", f"{pvals['P99.9']:.4f}"]
        f.write(f"{sched}\t" + "\t".join(row) + "\n")

############################################
# 7) Draw Percentile Breakdown Bar Charts
############################################

# 7a) Execution-time percentile breakdown
#     We'll show the 4 percentiles from "percentiles_with_schedulers"
#     on the x-axis, 1 group per scheduler.
exec_percentile_list = ["P90", "P95", "P99", "P99.9"]
plt.figure(figsize=(8.4, 6))
x = np.arange(len(exec_percentile_list))
bar_w = 0.12

for i, sched in enumerate(scheduler_types):
    y = [execution_percentiles[sched][p] for p in exec_percentile_list]
    offset = (i - len(scheduler_types)/2)*bar_w + bar_w/2
    plt.bar(x+offset, y, width=bar_w,
            label=sched.upper(), color=sched_colors[sched])

plt.yscale('log')
plt.xlabel("Execution-time Percentiles")
plt.ylabel("Duration (ms)")
plt.title("Execution-time Percentile Breakdown")
plt.xticks(x, exec_percentile_list)
plt.grid(True, axis='y', linestyle=':', alpha=0.7)
plt.legend(frameon=False, fontsize=14)
plt.tight_layout()
plt.savefig(os.path.join(workload_path, "bar_execution_breakdown.png"),
            bbox_inches='tight', pad_inches=0.01)
plt.close()
# 7b) Tail-latency percentile breakdown
#     We'll show P50, P90, P99, P99.9
EPS = 1e-3
tail_percentile_list = ["P90", "P95", "P99", "P99.9"]
plt.figure(figsize=(8.4, 6))
x = np.arange(len(tail_percentile_list))
bar_w = 0.12

for i, sched in enumerate(scheduler_types):
    if sched == "ideal":
        continue                     # skip drawing an actual bar
    yvals = [max(tail_percentiles[sched][p], EPS) for p in tail_percentile_list]
    offset = (i - len(scheduler_types) / 2) * bar_w + bar_w / 2
    plt.bar(x + offset, yvals, width=bar_w,
            label=sched.upper(), color=sched_colors[sched])

# ---- add a single text label for IDEAL ----------------------------
plt.text(0.02, 0.05, "ideal = 0", transform=plt.gca().transAxes,
         fontsize=14, va='bottom', ha='left')

plt.yscale('log')
plt.xlabel("Tail-latency Percentiles")
plt.ylabel("(Turnaround / SLO) − 1")
plt.title("Tail-latency Percentile Breakdown")
plt.xticks(x, tail_percentile_list)
plt.grid(True, axis='y', linestyle=':', alpha=0.7)
plt.legend(frameon=False, fontsize=14)
plt.tight_layout()
plt.savefig(os.path.join(workload_path, "bar_tail_breakdown.png"),
            bbox_inches='tight', pad_inches=0.01)
plt.close()
############################################
# 8) Generate Another Tail Latency - CDF and
#    Execution - CDF with X in [10^0..10^3]
############################################

# For these CDFs, we'll plot them on a normal y-axis, but *x-axis in log scale*
# from 10^0 to 10^3. We'll set up 400 points in that range.

# 8a) Execution-CDF
# 8a) Execution-time CDF (log-x)
plt.figure(figsize=(8.4, 6))
for sched in scheduler_types:
    times = list(execution_data[sched].values())
    if not times:
        continue
    arr  = np.sort(times)
    ecdf = sm.distributions.ECDF(arr)

    log_min = np.floor(np.log10(min(arr))) - 1
    log_max = np.ceil (np.log10(max(arr))) + 1
    x_vals  = np.logspace(log_min, log_max, 400)
    y_vals  = ecdf(x_vals)

    ls = '--' if sched.lower() == 'tla' else '-'
    plt.step(x_vals, y_vals, where='post',
             label=sched.upper(),
             linestyle=ls, linewidth=2,
             color=sched_colors[sched])

plt.xscale('log')
plt.xlabel("Execution Time (ms)")
plt.ylabel("CDF")
plt.title("CDF of Execution Time")
plt.xlim([10**log_min, 10**log_max])
plt.ylim([0, 1])
plt.grid(True, axis='y', linestyle=':', alpha=0.7)
plt.legend(frameon=False, fontsize=14)
plt.tight_layout()
plt.savefig(os.path.join(workload_path, "cdf_execution_time_log.png"),
            bbox_inches='tight', pad_inches=0.01)
plt.close()

# 8b) Tail-Latency CDF, x in [10^0..10^3]
# If tail-lat is negative, we must clamp them to a small positive number for log scale 
EPS = 1e-3                       # where we draw Ideal

plt.figure(figsize=(8.4, 6))
for sched in scheduler_types:
    tails = np.array(list(tail_latency_data[sched].values()))
    if tails.size == 0:
        continue
    tails[tails <= 0] = EPS      # clamp for log axis (incl. ideal==0)

    arr  = np.sort(tails)
    ecdf = sm.distributions.ECDF(arr)
    x_vals = np.logspace(-3, 4, 400)
    plt.step(x_vals, ecdf(x_vals), where='post',
             label=sched.upper(),
             color=sched_colors[sched],
             linestyle='--' if sched == 'tla' else '-', linewidth=2)

# --- vertical Ideal line ------------------------------------------
plt.axvline(EPS, color=sched_colors['ideal'],
            linestyle='-', linewidth=1)
plt.text(EPS*1.05, 0.05, "IDEAL=0", rotation=90,
         va='bottom', ha='left',
         fontsize=14, color=sched_colors['ideal'])

# --- relabel tick closest to EPS as “0” ---------------------------
ax = plt.gca()
ax.xaxis.set_major_locator(mtick.LogLocator(base=10, subs=[1.0]))  # 10⁻¹,10⁰,10¹…
ax.xaxis.set_minor_locator(mtick.NullLocator())                    # suppress 10⁻²,10⁻³

# --- now inject the EPS tick and relabel --------------------
ticks = list(ax.get_xticks())          # decade ticks from LogLocator
ticks.append(EPS)                      # add ideal marker
ticks = sorted(set(ticks))

labels = ["0" if abs(t - EPS) < 1e-12 else f"{t:g}" for t in ticks]
plt.xticks(ticks, labels)

# --- final decorations --------------------------------------------
plt.xscale('log')
plt.xlabel("(Turnaround / SLO) − 1")
plt.ylabel("CDF")
plt.title("CDF of Tail Latency")
plt.ylim(0, 1)
plt.grid(True, axis='y', linestyle=':', alpha=0.7)
plt.legend(frameon=False, fontsize=14, loc='upper left',
           bbox_to_anchor=(0.02, 0.98))      # keeps legend left of Ideal line
plt.tight_layout()
plt.savefig(os.path.join(workload_path, "cdf_tail_latency_log.png"),
            bbox_inches='tight', pad_inches=0.01)
plt.close()
############################################
# Done!
############################################

print("Done! Generated files in:", workload_path)
print("  1) percentiles_with_schedulers.txt")
print("  2) tail_with_schedulers.txt")
print("  3) bar_execution_breakdown.png")
print("  4) bar_tail_breakdown.png")
print("  5) cdf_execution_time_log.png")
print("  6) cdf_tail_latency_log.png")



# -------------  Matplotlib style (from your sample) -----------------
matplotlib.use('Agg')
matplotlib.rcParams['pdf.fonttype'] = 42
matplotlib.rcParams['ps.fonttype']  = 42
plt.rcParams.update({
    'font.family'       : 'sans-serif',
    'font.sans-serif'   : ['Arial'],
    'font.size'         : 16,
    'axes.linewidth'    : 1.5,
    'xtick.major.width' : 1.5,
    'ytick.major.width' : 1.5,
    'ytick.minor.width' : 1.5,
    'text.usetex'       : False,
    'mathtext.fontset'  : 'dejavuserif'
})

# ------------ 1. bucket execution times by category -----------------
cat_ranges = {
    "short" : range(20, 26),   # fib 20–25
    "middle": range(26, 32),   # fib 26–31
    "long"  : range(32, 36),   # fib 32–35
}

exec_by_sched_cat = {s: {c: [] for c in cat_ranges} for s in scheduler_types}
for sched, fid_map in execution_data.items():
    for fid, t_ms in fid_map.items():
        n = fib_id_to_n.get(f"fib{fid}")
        if n is None:
            continue
        for cat, rng in cat_ranges.items():
            if n in rng:
                exec_by_sched_cat[sched][cat].append(t_ms)
                break

# ------------ 2. prep output dir ------------------------------------
out_dir = os.path.join(workload_path, "cdf_by_category")
os.makedirs(out_dir, exist_ok=True)

# color palette for schedulers
sched_colors = {
    "sfs": "#3498DB",  # blue
    "tla": "#E74C3C",  # red
    "cfs": "#2ECC71",  # green
    "rr": "#DD7404", 
    "fifo": "#8E44AD",  # purple
}
# fallback if others
for s in scheduler_types:
    sched_colors.setdefault(s, None)

percentile_labels = ["P50", "P80", "P90", "P99.9"]
percent_vals      = [50, 80, 90, 99.9]

# ------------- 3. loop over categories ------------------------------
for cat, rng in cat_ranges.items():
    # --------- 3a. CDF figure ---------------------------------------
    plt.figure(figsize=(7.5, 5.4))
    for sched in scheduler_types:
        data = exec_by_sched_cat[sched][cat]
        if not data:
            continue
        data = np.sort(data)
        ecdf = sm.distributions.ECDF(data)

        x_min = np.floor(np.log10(min(data)))
        x_max = np.ceil (np.log10(max(data))) + 1
        x_vals = np.logspace(x_min, x_max, 400)
        y_vals = ecdf(x_vals)

        ls = '--' if sched.lower() == 'tla' else '-'
        plt.step(x_vals, y_vals, where='post',
                 label=sched.upper(),
                 linestyle=ls, linewidth=2,
                 color=sched_colors.get(sched))

    plt.xscale('log')
    plt.ylim(0, 1)
    plt.xlabel("Execution Time (ms)")
    plt.ylabel("CDF")
    plt.title(f"{cat.capitalize()} Functions (fib{min(rng)}–{max(rng)})")
    plt.grid(True, axis='y', linestyle=':', alpha=0.7)
    plt.legend(frameon=False, fontsize=14)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f"exec_cdf_{cat}.png"),
                bbox_inches='tight', pad_inches=0.01)
    plt.close()

    # --------- 3b. Percentile-breakdown bar chart -------------------
    # collect percentile numbers
    exec_percentiles = {s: {} for s in scheduler_types}
    for sched in scheduler_types:
        data = exec_by_sched_cat[sched][cat]
        if not data:
            exec_percentiles[sched] = {lbl: np.nan for lbl in percentile_labels}
            continue
        arr = np.sort(data)
        for lbl, p in zip(percentile_labels, percent_vals):
            exec_percentiles[sched][lbl] = np.percentile(arr, p)

    plt.figure(figsize=(8.4, 5.6))
    x = np.arange(len(percentile_labels))
    bar_w = 0.14

    for i, sched in enumerate(scheduler_types):
        yvals = [exec_percentiles[sched][lbl] for lbl in percentile_labels]
        offset = (i - len(scheduler_types)/2)*bar_w + bar_w/2
        plt.bar(x + offset, yvals, width=bar_w,
                label=sched.upper(), color=sched_colors.get(sched))

    plt.yscale('log')
    plt.xlabel("Execution Time Percentiles")
    plt.ylabel("Duration (ms)")
    plt.title(f"Percentile Breakdown — {cat.capitalize()} Functions")
    plt.xticks(x, percentile_labels)
    plt.grid(True, axis='y', linestyle=':', alpha=0.7)
    plt.legend(frameon=False, fontsize=14)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f"exec_bar_{cat}.png"),
                bbox_inches='tight', pad_inches=0.01)
    plt.close()

print(f"[INFO] CDF & bar charts for short/middle/long saved to {out_dir}")