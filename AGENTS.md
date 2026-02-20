# Repository Guidelines

## Project Structure & Module Organization
This repository’s active code lives at the root. The main script is `periodic_slurm_status.py`, which collects SLURM state and renders `freya_stat_1.png`. Helper launchers are `run.sh` (single run) and `run_periodic.sh` (looped execution).

Treat `pyslurmRepo/` as external and out of scope for normal changes. Versioned snapshots in `pyslurm-20-02-0/` and `pyslurm-21.08.4/` are historical references, not primary development targets.

## Build, Test, and Development Commands
- `python periodic_slurm_status.py`: run one data collection and plot generation pass.
- `python periodic_slurm_status.py --dry-run`: execute logic without intended output persistence checks.
- `bash run.sh`: run with the project’s preferred launcher settings (`OMP_NUM_THREADS=1`, `nice -n20`).
- `bash run_periodic.sh`: continuously refresh output every ~290 seconds.

Dependencies are pinned in `requirements.txt` (Conda-style export). Use a compatible environment with `pyslurm`, `matplotlib`, `numpy`, `scipy`, and SLURM CLI tools (`scontrol`, `df`) available.

## Coding Style & Naming Conventions
Use Python with 4-space indentation and keep imports at the top of the file. Follow existing naming patterns:
- `snake_case` for functions/variables (for example, `get_topology`, `jobs_running`)
- descriptive constants near configuration blocks (for example, `partNames`, `downStates`)

Keep changes focused and minimal in this single-script workflow. If reformatting is needed, use Black/isort-compatible style already reflected in commit history and dependencies.

## Testing Guidelines
There is no dedicated root-level automated test suite. Validate changes by:
1. Running `python periodic_slurm_status.py --dry-run`
2. Running `bash run.sh`
3. Confirming successful completion and expected updates to `freya_stat_1.png`

When modifying SLURM parsing, test on a host with live `pyslurm` and `scontrol` access.

## Commit & Pull Request Guidelines
Use short, imperative commit messages, typically lowercase (for example, `fix layout now that we have more gpu nodes`). Keep each commit scoped to one change.

PRs should include:
- what changed and why
- operational impact (cluster load, runtime cadence, output file behavior)
- a sample output note or screenshot when plot/layout logic changes
