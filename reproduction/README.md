# Locality-aware Bruck reproduction

Figures 7–10 are in `figures/` as PDF and PNG. The associated CSVs contain every model point, all measured batches, and the median and interquartile range by configuration and method.

## Measured figures

The university runs used Open MPI 2.1.1, shared memory within nodes and TCP between nodes. The earlier logs show OpenFabrics initialization errors and some incomplete jobs. The reproduction sweep uses explicit TCP to keep the transport consistent. Figure 9 uses nodes as regions. Figure 10 uses one socket per node. Both use the university's Open MPI baseline rather than the original machines' MPI libraries. The 16-node cases are omitted under the four-node allocation limit.

Each rank contributes two 4-byte integers. The driver validates the entire result on every rank against a rank-coded sequence before collecting timings. For each of seven batches it warms up the algorithm, times 1,000 calls, and records the maximum per-call batch mean across ranks. Bars are medians with 25th–75th percentile whiskers. Dashed segments mark the MPI baseline median.

| PBS job | Configurations | Placement |
| --- | --- | --- |
| 33064 | 4 nodes × 2 or 4 ranks | One socket per node, separate cores |
| 33065 | 1 node × 4, 16 or 32 ranks | 4 ranks on one socket, 16 ranks on separate cores across two sockets, 32 on distinct hardware threads across two sockets |
| 33068 | 1 node × 16 ranks | One socket using SMT, since the socket has 10 physical cores |
| 33069 | 2 nodes × 4 ranks | One socket per node, separate cores |

The 4-node 2-rank and 2-node 4-rank runs are additional data in the CSVs. Figures 9 and 10 use the paper's configurations through four nodes. Figure 10 labels the single-socket 16-rank SMT measurement. PBS job 33070 also found fewer than 16 physical cores per socket on compute05. The compute07 probe produced no benchmark log.

On four nodes with four ranks per node, the median was 28.03 µs for locality-aware Bruck, 76.85 µs for standard Bruck, and 49.62 µs for MPI_Allgather. The logs report an Open MPI memory-binding warning. The driver checked rank CPU placement and unique physical cores or hardware threads as appropriate.

## Modeled figures

Figures 7 and 8 use the paper's original model domains. They require no cluster allocation. The parameters come from the Lassen CPU rows of Table I in [Modeling Data Movement Performance on Heterogeneous Architectures](https://arxiv.org/pdf/2010.10378). Eager and rendezvous parameters switch at 8,192 bytes for each modeled message.

The curves in [A Locality-Aware Bruck Allgather](https://arxiv.org/pdf/2206.03564) match a per-message postal sum. For locality-aware Bruck, the match uses only complete radix-PPN rounds and gives the inter-node postal term the number of 4-byte values as its size argument. This convention was inferred from the plotted curves. Across all 254 plotted points, the regenerated vertical coordinates differ from the paper PDF by less than 0.0001 PDF points. The measured benchmark uses full messages and implements partial rounds.

## Re-run

The four collective implementations in the original checkout match [the author's collectives branch](https://github.com/bienz2/locality_aware/blob/72b1e06e77b046680337fe9e80efbbecedb9ce97/src/collective/allgather.c). The source change in `src/collective/allgather.c` implements the partial rounds described by the paper. It uses an in-place local allgatherv so inactive lanes do not read or write beyond the receive buffer. A one-node locality-aware call ends after the local Bruck step.

### Regenerate the saved figures locally

From the checkout root in Bash (Linux, WSL, or macOS), install Python 3 dependencies in a virtual environment and run the plotter. The four saved PBS logs are included as inputs. Figures 7 and 8 use the baked-in model parameters and Figures 9 and 10 use the logs.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install matplotlib numpy
python reproduction/plot.py reproduction/330{64,65,68,69}.master.local.log
```

The script writes the following files to `reproduction/figures/`. Pass `--output PATH` to write to another directory.

| Output | Contents |
| --- | --- |
| `figure7.pdf`, `figure7.png`, `figure7.csv` | Modeled node-count sweep |
| `figure8.pdf`, `figure8.png`, `figure8.csv` | Modeled payload-size sweep |
| `figure9.pdf`, `figure9.png` | Measured timings using node-local regions |
| `figure10.pdf`, `figure10.png` | Measured timings using one socket per node |
| `measured_samples.csv` | Individual timing batches from the verified runs |
| `measured_summary.csv` | Batch counts, medians, and quartiles by configuration and algorithm |

### Collect fresh measurements on the cluster

1. Put the checkout on the PBS cluster's shared filesystem. Use a PBS login node with Bash, `qsub`, `qstat`, compiler wrappers from the Open MPI 2.1.1 module, `setfacl`, and passwordless SSH between allocated nodes for the PBS execution account.
2. Check the project path in `reproduction/submit.sh` and `reproduction/measure.pbs` (currently `/home/student4/BT2024135/locality`). For another cluster, also update the execution account in the ACL, the PBS node requests in `submit.sh`, and the MPI module and installation prefix in `measure.pbs`. Match the rank counts, topology and placement in the table above.
3. From the cluster checkout root, submit the four jobs.

   ```bash
   bash reproduction/submit.sh 4n 1n 1s 2n
   qstat -u "$USER"
   ```

4. Save the four IDs printed by `qsub`. Once the jobs finish, collect the corresponding `reproduction/runs/<job-id>.log` files. Each file has job-wide output and should contain `VERIFIED` and `DONE` records for each expected node and rank configuration. Per-configuration logs are under `reproduction/runs/<job-id>/`. PBS scheduler output goes into `reproduction/`.
5. Copy the four job-wide logs into `reproduction/runs/` on the plotting machine, or use the Python environment on the cluster. Substitute the four full PBS job IDs in the commands below. The separate output directory preserves the saved plots.

   ```bash
   job_4n='FULL_4N_JOB_ID'
   job_1n='FULL_1N_JOB_ID'
   job_1s='FULL_1S_JOB_ID'
   job_2n='FULL_2N_JOB_ID'
   python reproduction/plot.py --output reproduction/figures-new \
     "reproduction/runs/${job_4n}.log" "reproduction/runs/${job_1n}.log" \
     "reproduction/runs/${job_1s}.log" "reproduction/runs/${job_2n}.log"
   ```

   Fresh timing measurements will vary.

## Push to GitHub

The WSL copy is mounted from the cluster and can report `fatal: detected dubious ownership`. If you recognize and trust this checkout, register this exact path in your WSL Git configuration before running any repository commands.

```bash
cd /home/paul/cluster-locality
git config --global --add safe.directory /home/paul/cluster-locality
git status -sb
```

If Git then reports a filesystem permission error such as an inability to create `.git/index.lock`, run the Git commands from the cluster as the checkout owner.

From the checkout root in Bash, verify that `origin` is the intended remote and that your GitHub SSH key has write access to it. This checkout uses `git@github.com:poughkeepsie7/locality.git` and tracks `origin/main`.

```bash
git remote -v
git fetch origin
git status -sb
git add -- .gitignore src/ benchmarks/bruck_allgather.cpp job.sh \
  reproduction/README.md reproduction/measure.cpp reproduction/measure.pbs \
  reproduction/submit.sh reproduction/plot.py reproduction/figures/ \
  reproduction/330{64,65,68,69}.master.local.log
git diff --cached --stat
git diff --cached
git commit -m "Add reproducible locality-aware Bruck figures"
git push origin main
```

Review the staged changes and the cluster hostnames in the four saved logs before publishing. If Git reports that the remote branch has advanced, integrate the remote changes before pushing. If `main` requires a pull request, create a branch with `git switch -c reproduce-figures` before committing, push it with `git push -u origin reproduce-figures`, and open a pull request into `main`.
