# Caslake Status Plotter

This project generates `caslake_stat_1.png` from live Slurm data on Midway3 (`caslake` partition).

## Installation

1. Clone this repo and enter it.
2. Create/sync the UV environment:

```bash
./scripts/bootstrap_uv.sh
```

3. Verify runtime dependencies:

```bash
.venv/bin/python -c "import pyslurm, matplotlib, numpy; print('ok')"
```

4. Run a smoke test:

```bash
./run.sh --dry-run
```

Python is pinned to `3.11` via `.python-version`. UV config is in `pyproject.toml`.
`bootstrap_uv.sh` auto-detects Slurm via `scontrol --version` and installs the
matching PySlurm tag (`v<slurm_version>-1`) by cloning PySlurm automatically.
By default it clones from `https://github.com/PySlurm/pyslurm.git`.

## If `pyslurm` Is Missing

The bootstrap script should install it automatically. If you need to run it manually:

```bash
cd pyslurmRepo
CC=/usr/bin/clang CXX=/usr/bin/clang++ \
  ../.venv/bin/python setup.py build --slurm=/software/slurm-20.11.8 install
```

Then rerun:

```bash
cd ..
./run.sh --dry-run
```

## Run Modes

- `./run.sh`: one collection + render pass.
- `./run_periodic.sh`: loop every ~290 seconds.
- `./run_cron_5min.sh`: single cron-safe run (lock + logging).

Output image: `caslake_stat_1.png`  
Cron log: `logs/cron_periodic_slurm_status.log`

## Cron (Every 5 Minutes)

```cron
*/5 * * * * /home/cernetic/pyslurm/freya/u/mihac/pyslurm/run_cron_5min.sh
```
