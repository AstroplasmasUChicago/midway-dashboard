"""
Non-science and other meta plots.
"""

import matplotlib

matplotlib.use("Agg")
import argparse
import math
import pwd
import re
import subprocess
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np

import pyslurm

parser = argparse.ArgumentParser(
    prog="Pyslurm Chart", description="Generate a plot of Midway3 caslake usage"
)
parser.add_argument(
    "-n",
    "--dry-run",
    help="Compatibility flag; historical data storage is disabled.",
    action="store_true",
)


def periodic_slurm_status(nosave=False):
    """Collect current statistics from the SLURM scheduler and make plots."""
    _ = nosave

    def _expandNodeList(nodeListStr):
        if not nodeListStr:
            return []
        cmd = ["scontrol", "show", "hostnames", nodeListStr]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def _node_sort_key(nodeName):
        match = re.match(r"^(.*?)-(\d+)$", nodeName)
        if match:
            return (match.group(1), int(match.group(2)))
        return (nodeName, 0)

    def _build_node_groups(nodeNames, n_groups=6):
        sorted_nodes = sorted(nodeNames, key=_node_sort_key)
        if not sorted_nodes:
            return []

        n_groups = min(n_groups, len(sorted_nodes))
        chunk_size = int(np.ceil(len(sorted_nodes) / n_groups))
        groups = []
        for i in range(n_groups):
            group_nodes = sorted_nodes[i * chunk_size : (i + 1) * chunk_size]
            if group_nodes:
                groups.append((f"group {i + 1}", list(reversed(group_nodes))))
        return groups

    def _normalize_partitions(raw_parts):
        """Return partitions with stable dict fields across PySlurm API versions."""
        normalized = {}
        for name, part in raw_parts.items():
            if isinstance(part, dict):
                nodes = part.get("nodes", "")
                total_nodes = part.get("total_nodes")
                total_cpus = part.get("total_cpus")
            else:
                nodes = getattr(part, "nodes", "")
                total_nodes = getattr(part, "total_nodes", None)
                total_cpus = getattr(part, "total_cpus", None)

            if total_nodes is None:
                total_nodes = len(_expandNodeList(nodes)) if nodes else 0
            if total_cpus is None:
                total_cpus = 0

            normalized[name] = {
                "nodes": nodes,
                "total_nodes": int(total_nodes),
                "total_cpus": int(total_cpus),
            }

        return normalized

    # config
    outputImage = "caslake_stat_1.png"
    partNames = ["caslake"]
    coresPerNode = 48
    cpusPerNode = 2
    nHyper = 1  # 2 to enable HTing accounting

    allocStates = ["ALLOCATED", "MIXED"]
    idleStates = ["IDLE"]
    downStates = [
        "DOWN",
        "DRAINED",
        "ERROR",
        "FAIL",
        "FAILING",
        "POWER_DOWN",
        "IDLE+DRAIN",
        "DOWN*+DRAIN",
        "UNKNOWN",
    ]

    # get data
    jobs = pyslurm.job().get()
    stats = pyslurm.statistics().get()
    nodes = pyslurm.node().get()
    if hasattr(pyslurm, "Partitions"):
        parts = _normalize_partitions(pyslurm.Partitions.load())
    else:
        parts = _normalize_partitions(pyslurm.partition().get())

    curTime = datetime.fromtimestamp(stats["req_time"])
    print("Now [%s]." % curTime.strftime("%A (%d %b) %H:%M"))

    # jobs: split, and attach running job info to nodes
    jobs_running = [
        jobs[jid]
        for jid in jobs
        if jobs[jid]["job_state"] == "RUNNING"
        and jobs[jid].get("partition") in partNames
    ]
    jobs_pending = [
        jobs[jid]
        for jid in jobs
        if jobs[jid]["job_state"] == "PENDING"
        and jobs[jid].get("partition") in partNames
    ]

    n_jobs_running = len(jobs_running)
    n_jobs_pending = len(jobs_pending)

    pending_reasons = [job["state_reason"] for job in jobs_pending]
    n_pending_priority = pending_reasons.count("Priority")
    n_pending_dependency = pending_reasons.count("Dependency")
    n_pending_resources = pending_reasons.count("Resources")
    n_pending_userheld = pending_reasons.count("JobHeldUser")

    if "Resources" in pending_reasons:
        next_job_starting = jobs_pending[
            pending_reasons.index("Resources")
        ]  # always just 1?
        next_job_starting["user_name"] = pwd.getpwuid(next_job_starting["user_id"])[0]
    else:
        next_job_starting = None

    # restrict nodes to those in main partition (skip login nodes, etc)
    missing_parts = [name for name in partNames if name not in parts]
    if missing_parts:
        print(f"WARNING: Missing partitions in slurm state: {missing_parts}")
    partNames = [name for name in partNames if name in parts]
    if not partNames:
        raise RuntimeError(
            "None of the configured partitions were found. "
            f"Available partitions include: {list(parts.keys())[:10]}"
        )

    nodesInPart = []
    for partName in partNames:
        nodesInPart += _expandNodeList(parts[partName]["nodes"])
    nodesInPartSet = set(nodesInPart)

    for job in jobs_running:
        for nodeName, _ in job["cpus_allocated"].items():
            if nodeName not in nodesInPartSet:
                continue
            if nodeName not in nodes or "cur_job_owner" in nodes[nodeName]:
                continue
            nodes[nodeName]["cur_job_owner"] = pwd.getpwuid(job["user_id"])[4].split(
                ","
            )[0]
            nodes[nodeName]["cur_job_name"] = job["name"]
            nodes[nodeName]["cur_job_runtime"] = job["run_time_str"]

    for _, node in nodes.items():
        if node["cpu_load"] == 4294967294:
            node["cpu_load"] = 0  # fix uint32 overflow

    nodes_main = [nodes[name] for name in nodes if name in nodesInPart]
    nodes_misc = [nodes[name] for name in nodes if name not in nodesInPart]

    if nodes_main:
        coresPerNode = int(
            np.median([node.get("cpus", coresPerNode) for node in nodes_main])
        )
        cpusPerNode = int(
            np.median([node.get("sockets", cpusPerNode) for node in nodes_main])
        )
        cpusPerNode = max(cpusPerNode, 1)

    # nodes: gather statistics
    nodes_idle = []
    nodes_alloc = []
    nodes_down = []

    for node in nodes_main:
        # idle?
        for state in idleStates:
            if state == node["state"]:
                nodes_idle.append(node)
                continue

        # down for any reason?
        for state in downStates:
            if state == node["state"]:
                nodes_down.append(node)
                continue

        # in use?
        for state in allocStates:
            if state == node["state"]:
                nodes_alloc.append(node)
                continue

    # nodes: print statistics
    n_nodes_down = len(nodes_down)
    n_nodes_idle = len(nodes_idle)
    n_nodes_alloc = len(nodes_alloc)

    print(
        "Main nodes: [%d] total, of which [%d] are idle, [%d] are allocated, and [%d] are down."
        % (len(nodes_main), n_nodes_idle, n_nodes_alloc, n_nodes_down)
    )
    print("Misc nodes: [%d] total." % len(nodes_misc))

    if np.sum(
        np.fromiter((parts[partName]["total_nodes"] for partName in partNames), int)
    ) != len(nodes_main):
        print("WARNING: Node count mismatch.")
    if len(nodes_main) != n_nodes_idle + n_nodes_alloc + n_nodes_down:
        print("WARNING: Nodes not all accounted for.")

    nCores = np.sum([parts[partName]["total_cpus"] for partName in partNames])
    if nCores == 0:
        nCores = np.sum(
            [parts[partName]["total_nodes"] * coresPerNode for partName in partNames]
        )
    nCores_alloc = np.sum([j["num_cpus"] for j in jobs_running]) / nHyper
    nCores_idle = nCores - nCores_alloc

    print(
        "Cores: [%d] total, of which [%d] are allocated, [%d] are idle or unavailable."
        % (nCores, nCores_alloc, nCores_idle)
    )

    if nCores != nCores_alloc + nCores_idle:
        print("WARNING: Cores not all accounted for.")

    for node in nodes_main:
        if node["cpu_load"] is None:
            node["cpu_load"] = 0.0

    # cluster: statistics
    cluster_load = float(nCores_alloc) / nCores * 100 if nCores else 0.0

    cpu_load_allocnodes_mean = (
        np.mean(
            [float(node["cpu_load"]) / (node["cpus"] / nHyper) for node in nodes_alloc]
        )
        if nodes_alloc
        else 0.0
    )
    cpu_load_allnodes_mean = (
        np.mean(
            [float(node["cpu_load"]) / (node["cpus"] / nHyper) for node in nodes_main]
        )
        if nodes_main
        else 0.0
    )

    print(
        "Cluster: [%.1f%%] global load, with mean per-node CPU loads: [%.1f%% %.1f%%]."
        % (cluster_load, cpu_load_allocnodes_mean, cpu_load_allnodes_mean)
    )

    # health metrics for compact right-side panel
    queue_pressure = (
        float(n_jobs_pending) / n_jobs_running if n_jobs_running else math.inf
    )

    pending_wait_seconds = []
    for job in jobs_pending:
        submit_time = job.get("submit_time")
        if submit_time is None:
            continue
        wait_s = max(0, int(stats["req_time"]) - int(submit_time))
        pending_wait_seconds.append(wait_s)
    p90_wait_seconds = (
        int(np.percentile(pending_wait_seconds, 90)) if pending_wait_seconds else None
    )

    user_cores = {}
    for job in jobs_running:
        uid = job.get("user_id")
        if uid is None:
            continue
        try:
            username = pwd.getpwuid(uid).pw_name
        except KeyError:
            username = str(uid)
        user_cores[username] = user_cores.get(username, 0.0) + (
            float(job.get("num_cpus", 0)) / nHyper
        )
    if user_cores:
        top_user, top_user_cores = max(user_cores.items(), key=lambda item: item[1])
    else:
        top_user, top_user_cores = ("n/a", 0.0)


    # group nodes into fixed columns (topology is not available on this cluster)
    nodeGroups = _build_node_groups(nodesInPart, n_groups=6)
    maxNodesPerRack = max(len(rackNodes) for _, rackNodes in nodeGroups)
    nodeHeadroom = 1
    nodes_down_set = {n["name"] for n in nodes_down}
    nodes_alloc_set = {n["name"] for n in nodes_alloc}
    nodes_idle_set = {n["name"] for n in nodes_idle}

    # start node figure
    fig = plt.figure(figsize=(18.9, 11.2), tight_layout=False, dpi=350)

    for i, (groupName, rackNodes) in enumerate(nodeGroups):
        print(groupName, len(rackNodes))

        ax = fig.add_subplot(1, len(nodeGroups), i + 1)

        ax.set_xlim([0, 1])
        ax.set_ylim([-1, maxNodesPerRack + nodeHeadroom])
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.get_xaxis().set_visible(False)
        ax.get_yaxis().set_visible(False)
        # Use a custom rack frame so the top border sits below the header text.
        for spine in ["top", "right", "left", "bottom"]:
            ax.spines[spine].set_visible(False)
        rack_bottom = -1
        rack_top = len(rackNodes)
        ax.plot([0, 1], [rack_bottom, rack_bottom], "-", lw=1.5, color="black")
        ax.plot([0, 1], [rack_top, rack_top], "-", lw=1.5, color="black")
        ax.plot([0, 0], [rack_bottom, rack_top], "-", lw=2.0, color="black")
        ax.plot([1, 1], [rack_bottom, rack_top], "-", lw=2.5, color="black")

        # draw representation of each node
        for j, name in enumerate(rackNodes):
            # circle: color by status
            color = "gray"
            if name in nodes_down_set:
                color = "red"
            elif name in nodes_alloc_set:
                color = "green"
            elif name in nodes_idle_set:
                color = "orange"
            ax.plot(0.14, j, "o", color=color, markersize=10.0)
            textOpts = {
                "fontsize": 8.0,
                "horizontalalignment": "left",
                "verticalalignment": "center",
            }

            pad = 0.10
            xmin = 0.18
            xmax = 0.475
            padx = 0.002
            dx = (xmax - xmin) / (coresPerNode / cpusPerNode)

            # entire node
            # ax.fill_between( [xmin,xmax], [j-0.5+pad,j-0.5+pad], [j+0.5-pad, j+0.5-pad], facecolor=color, alpha=0.2)

            # load
            load = 0.0
            try:
                if nodes[name]["cpu_load"] is not None:
                    load = float(nodes[name]["cpu_load"]) / (
                        nodes[name]["cpus"] / nHyper
                    )
            except KeyError:
                print(f"node with {name=} does not exist")
            ax.text(xmax + padx * 10, j, "%.0f%%" % load, color="#333333", **textOpts)

            # individual cores
            for k in range(cpusPerNode):
                if k == 0:
                    y0 = j - 0.5 + pad
                    y1 = j - pad / 2
                if k == 1:
                    y0 = j + pad / 2
                    y1 = j + 0.5 - pad

                for m in range(
                    min(
                        int(coresPerNode / cpusPerNode * load / 100),
                        int(coresPerNode / cpusPerNode),
                    )
                ):
                    ax.fill_between(
                        [xmin + m * dx + padx, xmin + (m + 1) * dx - padx],
                        [y0, y0],
                        [y1, y1],
                        facecolor=color,
                        alpha=0.3,
                    )
                for m in range(
                    min(
                        int(coresPerNode / cpusPerNode * load / 100),
                        int(coresPerNode / cpusPerNode),
                    ),
                    int(coresPerNode / cpusPerNode),
                ):
                    ax.fill_between(
                        [xmin + m * dx + padx, xmin + (m + 1) * dx - padx],
                        [y0, y0],
                        [y1, y1],
                        facecolor="gray",
                        alpha=0.3,
                    )

            # node name
            ax.text(0.02, j, name.replace("midway3-", ""), color="#222222", **textOpts)

            try:
                if "cur_job_owner" in nodes[name]:
                    real_name = nodes[name]["cur_job_owner"]
                    real_name = (
                        real_name[:16] + "..." if len(real_name) > 16 else real_name
                    )  # truncate
                    ax.text(
                        xmax + 0.14 + padx * 10,
                        j,
                        real_name,
                        color="#333333",
                        **textOpts,
                    )
            except KeyError:
                print(f"node {name=} does not exist")

    fig.subplots_adjust(left=0.005, right=0.995, bottom=0.005, top=0.82, wspace=0.05)

    # historical load panel intentionally removed for this view

    # text
    stats_lines = [
        "nodes: %d total, %d idle, %d allocated, %d down"
        % (len(nodes_main), len(nodes_idle), len(nodes_alloc), len(nodes_down)),
        "cores: %d total, %d allocated, %d idle/unavailable"
        % (nCores, nCores_alloc, nCores_idle),
        "load: %.1f%% cluster, %.1f%% mean node CPU"
        % (cluster_load, cpu_load_allocnodes_mean),
        "jobs: %d running, %d waiting, %d userheld, %d dependent"
        % (
            n_jobs_running,
            n_pending_priority + n_pending_resources,
            n_pending_userheld,
            n_pending_dependency,
        ),
    ]
    statsText = "\n".join(stats_lines)
    updatedText = "Last Updated\n%s\n%s" % (
        curTime.strftime("%a %d %b"),
        curTime.strftime("%H:%M"),
    )
    if p90_wait_seconds is None:
        p90_wait_str = "n/a"
    elif p90_wait_seconds < 3600:
        p90_wait_str = f"{p90_wait_seconds // 60}m"
    else:
        p90_wait_str = f"{p90_wait_seconds / 3600.0:.1f}h"
    if math.isinf(queue_pressure):
        queue_pressure_str = "inf"
    else:
        queue_pressure_str = f"{queue_pressure:.2f}"
    health_lines = [
        "Health Panel (quick guide)",
        f"queue pressure (pending/running): {queue_pressure_str}",
        f"p90 wait (90% start sooner): {p90_wait_str}",
        f"top user by running cores: {top_user} ({int(top_user_cores)})",
    ]
    healthText = "\n".join(health_lines)
    headerBox = dict(facecolor="white", alpha=0.75, edgecolor="none", pad=2.0)

    if next_job_starting is not None:
        next_job_starting["name2"] = (
            next_job_starting["name"][:6] + "..."
            if len(next_job_starting["name"]) > 8
            else next_job_starting["name"]
        )  # truncate
        nextJobsStr = "next to run: id=%d %s (%s)" % (
            next_job_starting["job_id"],
            next_job_starting["name2"],
            next_job_starting["user_name"],
        )

    ax.annotate(
        "MIDWAY3 caslake Status",
        [1 - 0.994, 0.99],
        xycoords="figure fraction",
        fontsize=34.0,
        horizontalalignment="left",
        verticalalignment="top",
        bbox=headerBox,
    )
    ax.annotate(
        updatedText,
        [0.995, 0.995],
        xycoords="figure fraction",
        fontsize=12.0,
        horizontalalignment="right",
        verticalalignment="top",
        color="green",
        bbox=headerBox,
    )
    ax.annotate(
        healthText,
        [0.8, 0.88],
        xycoords="figure fraction",
        fontsize=12.0,
        horizontalalignment="left",
        verticalalignment="top",
        linespacing=1.3,
        bbox=headerBox,
    )
    ax.annotate(
        statsText,
        [0.006, 0.91],
        xycoords="figure fraction",
        fontsize=16.5,
        horizontalalignment="left",
        verticalalignment="top",
        linespacing=1.35,
        bbox=headerBox,
    )
    # if next_job_starting is not None:
    #    ax.annotate(nextJobsStr, [0.73, 0.906], xycoords='figure fraction', fontsize=20.0, horizontalalignment='right', verticalalignment='center')

    # filesystem reporting intentionally disabled for this cluster-specific view

    # save
    fig.savefig(outputImage, dpi=100)  # 1890x1120 pixels
    plt.close(fig)


def main():
    args = parser.parse_args()
    periodic_slurm_status(nosave=args.dry_run)


if __name__ == "__main__":
    main()
