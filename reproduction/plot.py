#!/usr/bin/env python3
"""Regenerate Figures 7–10 from model parameters and verified PBS logs."""
import argparse
import csv
from collections import defaultdict
from math import isfinite, log2
from pathlib import Path
from statistics import median

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
from matplotlib.ticker import FixedLocator

COLORS = {
    "Bruck": "#2b719a",
    "Hierarchical": "#adc2d9",
    "Multi-lane": "#e58025",
    "Locality": "#f0bd83",
}
METHODS = ("MPI", *COLORS)
FIGURE9 = ((1, 4), (4, 4), (1, 16), (1, 32))
FIGURE10 = ((1, 4), (4, 4), (1, 16))


def exchange(message_bytes, local):
    """Lassen inter-CPU parameters from Table I of arXiv:2010.10378."""
    if local:
        alpha, beta = ((3.99e-7, 5.59e-11) if message_bytes < 8192
                       else (3.62e-6, 3.71e-11))
    else:
        alpha, beta = ((1.53e-6, 4.38e-10) if message_bytes < 8192
                       else (6.90e-6, 4.63e-11))
    return alpha + beta * message_bytes


def bruck(nodes, ppn, payload_bytes):
    return sum(exchange(payload_bytes * 2**step, local=False)
               for step in range(int(log2(nodes * ppn))))


def locality(nodes, ppn, payload_bytes):
    # The published curves use complete radix-PPN rounds and pass a count
    # of four-byte values to the inter-node postal calculation.
    local_steps = int(log2(ppn))
    rounds = int(log2(nodes)) // local_steps
    total = 0
    for step in range(rounds + 1):
        block_bytes = payload_bytes * ppn**step
        if step:
            total += exchange(block_bytes / 4, local=False)
        total += sum(exchange(block_bytes * 2**message, local=True)
                     for message in range(local_steps))
    return total


def write_csv(path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def save(fig, directory, name):
    for extension in ("png", "pdf"):
        fig.savefig(directory / f"{name}.{extension}", dpi=180)
    plt.close(fig)


def style(ax, ylabel):
    ax.set_ylabel(ylabel)
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#dadfe4", linewidth=0.8)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#c1c8d0")
    ax.tick_params(length=0)


def modeled(directory):
    nodes = [2**power for power in range(1, 10)]
    fig, ax = plt.subplots(figsize=(7.2, 4.1), layout="constrained")
    rows = []
    for ppn, color in zip((4, 8, 16), ("#2473a8", "#718bb2", "#d96e20")):
        standard = [bruck(node, ppn, 4) for node in nodes]
        aware = [locality(node, ppn, 4) for node in nodes]
        ax.loglog(nodes, standard, color=color, label=f"{ppn} ranks per node")
        ax.loglog(nodes, aware, color=color, linestyle="--")
        rows.extend(zip(nodes, [ppn] * len(nodes), standard, aware))
    handles, labels = ax.get_legend_handles_labels()
    handles += [Line2D([], [], color="#333", ls="-"), Line2D([], [], color="#333", ls="--")]
    ax.legend(handles, labels + ["Bruck", "Locality-aware"], ncol=2, frameon=False)
    ax.set(xlabel="Number of nodes", title="Figure 7 · Modeled scaling on Lassen")
    ax.set_xticks(nodes, [str(node) for node in nodes])
    style(ax, "Modeled time (s)")
    save(fig, directory, "figure7")
    write_csv(directory / "figure7.csv", ("nodes", "ppn", "bruck_s", "locality_s"), rows)

    sizes = [2**power for power in range(100)]
    standard = [bruck(1024, 16, 4 * size) for size in sizes]
    aware = [locality(1024, 16, 4 * size) for size in sizes]
    fig, ax = plt.subplots(figsize=(7.2, 4.1), layout="constrained")
    ax.loglog(sizes, standard, color="#2473a8", label="Bruck")
    ax.loglog(sizes, aware, color="#718bb2", linestyle="--", label="Locality-aware")
    ax.legend(frameon=False)
    ax.set(xlabel="4-byte values per rank", title="Figure 8 · Modeled payload sweep on Lassen")
    ax.xaxis.set_major_locator(FixedLocator([10.0**e for e in range(3, 29, 5)]))
    ax.yaxis.set_major_locator(FixedLocator([10.0**e for e in range(-1, 24, 6)]))
    style(ax, "Modeled time (s)")
    save(fig, directory, "figure8")
    write_csv(directory / "figure8.csv", ("int32_values_per_rank", "bruck_s", "locality_s"),
              zip(sizes, standard, aware))


def read_samples(files):
    samples = []
    seen = set()
    for path in files:
        lines = path.read_text(encoding="utf-8").splitlines()
        socket_cores = defaultdict(set)
        for line in lines:
            fields = line.split(",")
            if len(fields) == 3 and all(field.isdecimal() for field in fields):
                _, core, socket = map(int, fields)
                socket_cores[socket].add(core)
        max_socket_cores = max(map(len, socket_cores.values()), default=0)
        verified = {tuple(map(int, line.split(",")[1:])) for line in lines
                    if line.startswith("VERIFIED,")}
        done = {tuple(map(int, line.split(",")[1:])) for line in lines
                if line.startswith("DONE,")}
        groups = defaultdict(dict)
        for line in lines:
            if not line.startswith("RESULT,"):
                continue
            _, nodes, ppn, socket, batch, method, seconds = line.split(",")
            key = (int(nodes), int(ppn))
            if key not in verified or key not in done:
                continue
            batch_key = (int(batch), method)
            seconds = float(seconds)
            if batch_key in groups[key] or not isfinite(seconds) or seconds <= 0:
                raise ValueError(f"Invalid sample in {path}: {line}")
            groups[key][batch_key] = (int(socket), seconds)
        expected = {(batch, method) for batch in range(1, 8) for method in METHODS}
        for (nodes, ppn), runs in groups.items():
            if set(runs) != expected or len({socket for socket, _ in runs.values()}) != 1:
                raise ValueError(f"Incomplete or inconsistent batches in {path}: {(nodes, ppn)}")
            key = (path.name, nodes, ppn)
            if key in seen:
                raise ValueError(f"Duplicate job/configuration: {key}")
            seen.add(key)
            for (batch, method), (socket, seconds) in sorted(runs.items()):
                smt = ppn == 32 or (nodes == 1 and socket and ppn > max_socket_cores)
                samples.append((path.stem, nodes, ppn, socket, smt, batch, method, seconds))
    return samples


def measured(directory, samples):
    timing = defaultdict(list)
    for _, nodes, ppn, single_socket, smt, _, method, seconds in samples:
        timing[nodes, ppn, single_socket, smt, method].append(seconds * 1e6)
    for figure, configs in ((9, FIGURE9), (10, FIGURE10)):
        fig, ax = plt.subplots(figsize=(8.2, 4.4), layout="constrained")
        width = 0.16
        labels = []
        for index, (nodes, ppn) in enumerate(configs):
            scope_order = (0, 1) if figure == 9 else (1,)
            placements = [(scope, smt) for scope in scope_order for smt in (False, True)
                          if (nodes, ppn, scope, smt, "MPI") in timing]
            label = f"{ppn} PPN\n{nodes} {'node' if nodes == 1 else 'nodes'}"
            labels.append(label + (" · SMT" if placements and placements[0][1] else ""))
            if not placements:
                ax.text(index, 0.05, "Single-socket\nplacement unavailable"
                        if figure == 10 and any((nodes, ppn, 0, smt, "MPI") in timing for smt in (False, True))
                        else "No verified run", transform=ax.get_xaxis_transform(),
                        ha="center", va="bottom", fontsize=8, color="#4a5560")
                continue
            scope, smt = placements[0]
            for offset, (method, color) in enumerate(COLORS.items()):
                values = timing[nodes, ppn, scope, smt, method]
                low, high = np.percentile(values, [25, 75])
                middle = median(values)
                ax.bar(index + (offset - 1.5) * width, middle, width * 0.94,
                       color=color, edgecolor="#344255", linewidth=0.5,
                       yerr=[[middle - low], [high - middle]], capsize=2,
                       error_kw={"ecolor": "#344255", "linewidth": 0.8})
            mpi = median(timing[nodes, ppn, scope, smt, "MPI"])
            ax.hlines(mpi, index - 2 * width, index + 2 * width,
                      color="#1d2630", linewidth=1.5, linestyles="--")
        handles = [plt.Rectangle((0, 0), 1, 1, color=color, label=method)
                   for method, color in COLORS.items()]
        handles.append(Line2D([], [], color="#1d2630", ls="--", label="MPI_Allgather"))
        ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0, 1.02),
                  ncols=5, frameon=False, fontsize=9)
        ax.set_xticks(range(len(configs)), labels)
        ax.set_xlim(-0.5, len(configs) - 0.5)
        ax.set_ylim(bottom=0)
        topic = "Node-local regions" if figure == 9 else "Single-socket placement"
        ax.set_title(f"Figure {figure} · {topic}", pad=30)
        style(ax, "Measured time (µs)")
        save(fig, directory, f"figure{figure}")

    write_csv(directory / "measured_samples.csv",
              ("job", "nodes", "ppn", "single_socket", "smt", "batch", "algorithm", "time_s"), samples)
    summary = [(nodes, ppn, socket, smt, method, len(values), median(values),
                *np.percentile(values, [25, 75]))
               for (nodes, ppn, socket, smt, method), values in sorted(timing.items())]
    write_csv(directory / "measured_summary.csv",
              ("nodes", "ppn", "single_socket", "smt", "algorithm", "batches",
               "median_us", "p25_us", "p75_us"), summary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="+", type=Path, help="PBS logs with verified benchmark runs")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "figures")
    args = parser.parse_args()
    samples = read_samples(args.logs)
    if not samples:
        parser.error("No verified benchmark samples")
    args.output.mkdir(parents=True, exist_ok=True)
    modeled(args.output)
    measured(args.output, samples)


if __name__ == "__main__":
    main()

