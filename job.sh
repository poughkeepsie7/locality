#!/bin/bash
#PBS -N bruck_allgather
#PBS -l nodes=4:ppn=4
#PBS -l walltime=00:10:00
#PBS -j oe

LOG=/home/student4/BT2024135/locality/logs/run.${PBS_JOBID}.log
exec > "$LOG" 2>&1

echo "=== job started $(date) ==="
echo "hostname: $(hostname)"
echo "user:     $(whoami)"
echo "---"

cd /home/student4/BT2024135/locality || exit 2
module load mpi/openmpi-2.1.1

echo "POST PATH: $PATH"
echo "POST LD_LIBRARY_PATH: $LD_LIBRARY_PATH"
echo "which orted: $(which orted)"
echo "--- starting mpirun ---"

mpirun --prefix /opt/apps/mpi/openmpi-2.1.1 \
       -x LD_LIBRARY_PATH \
       --mca plm_rsh_agent /bin/ssh \
       --mca orte_base_help_aggregate 0 \
       --hostfile "$PBS_NODEFILE" \
       -np 16 \
       ./build/bruck_allgather
RC=$?

echo "=== mpirun finished $(date), rc=$RC ==="
exit $RC
