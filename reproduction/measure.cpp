#include "mpi_advance.h"
#include <mpi.h>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <sched.h>
#include <string>
#include <vector>

int main(int argc, char** argv)
{
    MPI_Init(&argc, &argv);
    int rank, size;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);
    if (argc != 4) MPI_Abort(MPI_COMM_WORLD, 1);
    const int nodes = std::atoi(argv[1]);
    const int ppn = std::atoi(argv[2]);
    if (nodes < 1 || nodes > 4 || ppn < 2 || (ppn & (ppn - 1)) ||
            (nodes & (nodes - 1)) || size != nodes * ppn)
        MPI_Abort(MPI_COMM_WORLD, 2);

    MPIX_Comm* topology;
    MPIX_Comm_init(&topology, MPI_COMM_WORLD);
    MPIX_Comm_topo_init(topology);
    if (topology->ppn != ppn || topology->num_nodes != nodes ||
            topology->ordered_global_ranks[rank] != rank)
        MPI_Abort(MPI_COMM_WORLD, 3);

    const int cpu = sched_getcpu();
    const std::string cpu_path = "/sys/devices/system/cpu/cpu" +
            std::to_string(cpu) + "/topology/";
    int socket = -1, core = -1;
    std::ifstream(cpu_path + "physical_package_id") >> socket;
    std::ifstream(cpu_path + "core_id") >> core;
    const std::string placement_mode = argv[3];
    const bool smt = placement_mode == "smt" || placement_mode == "socket_smt";
    const int placement[] = {socket, smt ? cpu : core};
    std::vector<int> placements(2 * size);
    MPI_Allgather(placement, 2, MPI_INT, placements.data(), 2, MPI_INT, MPI_COMM_WORLD);
    bool single_socket = true;
    for (int first = 0; first < size; first += ppn) {
        for (int i = first; i < first + ppn; ++i) {
            if (placements[2 * i] < 0 || placements[2 * i + 1] < 0)
                MPI_Abort(MPI_COMM_WORLD, 4);
            single_socket &= placements[2 * i] == placements[2 * first];
            for (int j = first; j < i; ++j)
                if (placements[2 * i] == placements[2 * j] &&
                        placements[2 * i + 1] == placements[2 * j + 1])
                    MPI_Abort(MPI_COMM_WORLD, 5);
        }
    }

    if (placement_mode.compare(0, 7, "socket_") == 0 && !single_socket)
        MPI_Abort(MPI_COMM_WORLD, 7);

    static_assert(sizeof(int) == 4, "Expected 4-byte integers");
    constexpr int count = 2;
    constexpr int iterations = 1000;
    constexpr int repetitions = 7;
    const int input[count] = {rank * 2, rank * 2 + 1};
    std::vector<int> output(count * size);
    const char* names[] = {"MPI", "Bruck", "Locality", "Hierarchical", "Multi-lane"};
    const auto gather = [&](int method) {
        switch (method) {
            case 0: return MPI_Allgather(input, count, MPI_INT, output.data(), count, MPI_INT, MPI_COMM_WORLD);
            case 1: return allgather_bruck(input, count, MPI_INT, output.data(), count, MPI_INT, MPI_COMM_WORLD);
            case 2: return allgather_loc_bruck(input, count, MPI_INT, output.data(), count, MPI_INT, topology);
            case 3: return allgather_hier_bruck(input, count, MPI_INT, output.data(), count, MPI_INT, topology);
            default: return allgather_mult_hier_bruck(input, count, MPI_INT, output.data(), count, MPI_INT, topology);
        }
    };
    for (int method = 0; method < 5; ++method) {
        std::fill(output.begin(), output.end(), -1);
        gather(method);
        for (int i = 0; i < count * size; ++i) {
            if (output[i] != i) {
                std::fprintf(stderr, "%s rank %d index %d: expected %d, got %d\n",
                        names[method], rank, i, i, output[i]);
                MPI_Abort(MPI_COMM_WORLD, 6);
            }
        }
    }
    for (int rep = 0; rep < repetitions; ++rep) {
        for (int offset = 0; offset < 5; ++offset) {
            const int method = (offset + rep) % 5;
            for (int i = 0; i < 25; ++i) gather(method);
            MPI_Barrier(MPI_COMM_WORLD);
            const double start = MPI_Wtime();
            for (int i = 0; i < iterations; ++i) gather(method);
            const double elapsed = (MPI_Wtime() - start) / iterations;
            double slowest;
            MPI_Reduce(&elapsed, &slowest, 1, MPI_DOUBLE, MPI_MAX, 0, MPI_COMM_WORLD);
            if (rank == 0) {
                std::printf("RESULT,%d,%d,%d,%d,%s,%.12g\n",
                        nodes, ppn, single_socket, rep + 1, names[method], slowest);
                std::fflush(stdout);
            }
        }
    }
    MPIX_Comm_free(&topology);
    MPI_Finalize();
    if (rank == 0) std::printf("VERIFIED,%d,%d\n", nodes, ppn);
    return 0;
}
