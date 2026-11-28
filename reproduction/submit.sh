#!/bin/bash
set -e
cd /home/student4/BT2024135/locality
mkdir -p reproduction/runs
setfacl -m u:student3:rwx reproduction/runs
for shape in "$@"; do
case "$shape" in
4n) nodes=4; ppns="2 4"; spec=compute01:ppn=4+compute02:ppn=4+compute04:ppn=4+compute06:ppn=4;;
1n) nodes=1; ppns="4 16 32"; spec=compute00:ppn=32;;
2n) nodes=2; ppns=4; spec=compute01:ppn=4+compute02:ppn=4;;
1s) nodes=1; ppns=16:socket_smt; spec=compute00:ppn=16;;
1c5) nodes=1; ppns=16:socket_core; spec=compute05:ppn=16;;
1c7) nodes=1; ppns=16:socket_core; spec=compute07:ppn=16;;
*) echo "Unknown configuration: $shape" >&2; exit 2;;
esac
file="reproduction/job_$shape.pbs"
printf '#!/bin/bash\n#PBS -N bt135_%s\n#PBS -l nodes=%s\n#PBS -l walltime=00:12:00\n#PBS -j oe\n#PBS -o /home/student4/BT2024135/locality/reproduction/\nexport SWEEP_NODES=%s\nexport SWEEP_PPN="%s"\n' "$shape" "$spec" "$nodes" "$ppns" > "$file"
printf 'exec bash /home/student4/BT2024135/locality/reproduction/measure.pbs\n' >> "$file"
qsub "$file" || exit
done
