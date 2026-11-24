#!/bin/bash
#SBATCH --job-name=locality_job       # Job name
#SBATCH --nodes=1                     # Number of nodes
#SBATCH --ntasks=1                    # Number of CPU cores
#SBATCH --time=01:00:00               # Time limit
#SBATCH --output=locality_%j.out      # Output log

# 1. Load any necessary modules (e.g., gcc, python, mpi)
# module load gcc/9.3.0

# 2. Move into your specific locality folder
cd ~/BT2024135/locality

# 3. Run your code
echo "Starting job on $(hostname)"
# Example for C: gcc my_code.c -o my_program && ./my_program
echo "Job finished!"
