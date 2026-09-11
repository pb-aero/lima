/*
 * poller_probe.c -- measure the scheduling tail seen by an ArduPilot Linux HAL
 * IMU bus poller, and report it against the ICM-45686 FIFO overflow deadline.
 *
 * Why not just cyclictest: cyclictest measures clock_nanosleep() wakeup latency
 * at whatever priority you ask for. ArduPilot's SPI poller is a PollerThread --
 * timerfd + poll() -- running SCHED_FIFO at priority 12 (AP_LINUX_SENSORS_SCHED_PRIO,
 * Scheduler.h:16), below the UART thread at 14 and level with the main flight
 * loop. This probe replicates that shape, and reports the one number that maps
 * directly onto FIFO overflow: the longest run of CONSECUTIVE MISSED PERIODS.
 *
 * timerfd's expiry counter is the honest analogue of a FIFO backlog. If read()
 * returns N, the thread was denied the CPU across N-1 periods, and those are
 * exactly the periods in which samples piled up in the sensor.
 *
 * Build:  cc -O2 -Wall -o poller_probe poller_probe.c -lrt
 * Run:    sudo ./poller_probe --rate 4000 --seconds 600
 *
 * Exit 0 = no excursion reached the deadline. Exit 2 = deadline breached.
 * Exit 3 = could not obtain SCHED_FIFO, so the run measured nothing useful.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <sched.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/timerfd.h>
#include <poll.h>
#include <time.h>
#include <unistd.h>

/* ICM-45686: 2 KB FIFO. 20-byte HiRes packets -> 105 samples, 16-byte -> 128.
 * Source: AP_InertialSensor_Invensensev3.cpp:198-202 and the static_asserts at
 * :192-193. NOTE this is the driver's comment, not a read of TDK DS-000563. */
#define FIFO_SAMPLES_HIRES   105
#define FIFO_SAMPLES_STD     128

static volatile int g_stop;
static void on_sig(int s) { (void)s; g_stop = 1; }

static inline uint64_t ns_now(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

static void usage(const char *p)
{
    fprintf(stderr,
      "usage: %s [--rate HZ] [--seconds N] [--prio P] [--cpu N] [--std-packet]\n"
      "  --rate       IMU backend rate: 1000, 2000, 4000 or 8000 (default 4000)\n"
      "  --seconds    run length (default 300)\n"
      "  --prio       SCHED_FIFO priority (default 12 -- ArduPilot's real one)\n"
      "  --cpu        pin to this CPU (default: unpinned, as ArduPilot runs)\n"
      "  --std-packet assume 16-byte FIFO packets (HiRes off) -> 128 samples\n", p);
    exit(1);
}

int main(int argc, char **argv)
{
    unsigned rate_hz = 4000, seconds = 300;
    int prio = 12, cpu = -1;
    unsigned fifo_samples = FIFO_SAMPLES_HIRES;
    const char *packet = "20-byte HiRes";

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--rate") && i+1 < argc)         rate_hz = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--seconds") && i+1 < argc) seconds = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--prio") && i+1 < argc)    prio = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--cpu") && i+1 < argc)     cpu = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--std-packet")) { fifo_samples = FIFO_SAMPLES_STD;
                                                     packet = "16-byte standard"; }
        else usage(argv[0]);
    }
    if (rate_hz < 100 || rate_hz > 20000 || seconds == 0) usage(argv[0]);

    const uint64_t period_ns   = 1000000000ull / rate_hz;
    const uint64_t deadline_ns = (uint64_t)fifo_samples * period_ns;

    /* SCHED_FIFO at the real priority, or say plainly that we measured nothing. */
    struct sched_param sp = { .sched_priority = prio };
    if (sched_setscheduler(0, SCHED_FIFO, &sp) != 0) {
        fprintf(stderr,
          "FATAL: sched_setscheduler(SCHED_FIFO, %d) failed: %s\n"
          "  Run as root, or raise the rtprio limit for this user:\n"
          "    /etc/security/limits.d/rt.conf ->  <user>  -  rtprio  20\n"
          "  A run without SCHED_FIFO measures a different thing entirely and\n"
          "  would read as far worse than reality. Refusing to continue.\n",
          prio, strerror(errno));
        return 3;
    }
    if (mlockall(MCL_CURRENT | MCL_FUTURE) != 0)
        fprintf(stderr, "WARNING: mlockall failed (%s) -- page faults may show as latency\n",
                strerror(errno));
    if (cpu >= 0) {
        cpu_set_t set; CPU_ZERO(&set); CPU_SET(cpu, &set);
        if (sched_setaffinity(0, sizeof(set), &set) != 0)
            fprintf(stderr, "WARNING: could not pin to CPU %d (%s)\n", cpu, strerror(errno));
    }

    int tfd = timerfd_create(CLOCK_MONOTONIC, 0);
    if (tfd < 0) { perror("timerfd_create"); return 1; }

    signal(SIGINT, on_sig); signal(SIGTERM, on_sig);

    /* Print BEFORE arming. An earlier version armed the timer, then printed,
     * then took its time baseline -- so every "due" time was computed later
     * than the timer's real expiry and lateness measured a flat 0.0 us across
     * 32k wakeups. A zero tail is precisely the answer a broken instrument
     * gives you, so the baseline is now absolute and self-anchoring. */
    printf("poller_probe: rate %u Hz, period %" PRIu64 " us, prio SCHED_FIFO %d, %u s\n",
           rate_hz, period_ns/1000, prio, seconds);
    printf("FIFO model: %u samples (%s) -> overflow deadline %" PRIu64 " us (%.1f ms)\n\n",
           fifo_samples, packet, deadline_ns/1000, deadline_ns/1e6);
    fflush(stdout);

    /* Absolute first expiry: due times are then exact, not relative to whenever
     * settime happened to be called. */
    const uint64_t t_start = ns_now();
    const uint64_t first   = t_start + period_ns;
    struct itimerspec its = {
        .it_interval = { .tv_sec = 0, .tv_nsec = (long)period_ns },
        .it_value    = { .tv_sec  = (time_t)(first / 1000000000ull),
                         .tv_nsec = (long)(first % 1000000000ull) },
    };
    if (timerfd_settime(tfd, TFD_TIMER_ABSTIME, &its, NULL) != 0) {
        perror("timerfd_settime"); return 1;
    }

    uint64_t wakeups = 0, late_ns_max = 0, late_ns_sum = 0;
    uint64_t missed_total = 0, missed_run_max = 0;
    uint64_t worst_stall_ns = 0, worst_stall_at_s = 0;
    /* log2-ish histogram of lateness, 1us..~1s */
    uint64_t hist[24] = {0};

    const uint64_t t0 = t_start;
    const uint64_t t_end = t0 + (uint64_t)seconds * 1000000000ull;
    uint64_t ticks = 0;   /* total timer expiries consumed */

    while (!g_stop && ns_now() < t_end) {
        struct pollfd pfd = { .fd = tfd, .events = POLLIN };
        int pr = poll(&pfd, 1, 1000);
        if (pr < 0) { if (errno == EINTR) continue; perror("poll"); break; }
        if (pr == 0) continue;

        uint64_t expiries = 0;
        if (read(tfd, &expiries, sizeof(expiries)) != (ssize_t)sizeof(expiries)) continue;
        const uint64_t now = ns_now();

        /* lateness of THIS wakeup relative to when the LAST consumed tick was
         * due. Due times are absolute multiples of the period from `first`. */
        ticks += expiries;
        const uint64_t due = first + (ticks - 1) * period_ns;
        const uint64_t late = now > due ? now - due : 0;

        /* expiries-1 periods went by with the thread off-CPU: the backlog */
        const uint64_t missed = expiries - 1;
        if (missed > 0) {
            missed_total += missed;
            if (missed > missed_run_max) missed_run_max = missed;
        }
        /* the stall this wakeup represents, in FIFO terms */
        const uint64_t stall = missed * period_ns + late;
        if (stall > worst_stall_ns) {
            worst_stall_ns = stall;
            worst_stall_at_s = (now - t0) / 1000000000ull;
        }

        wakeups++;
        late_ns_sum += late;
        if (late > late_ns_max) late_ns_max = late;
        unsigned b = 0; for (uint64_t v = late/1000; v; v >>= 1) b++;
        if (b > 23) b = 23;
        hist[b]++;

    }

    const double run_s = (ns_now() - t0) / 1e9;
    printf("wakeups            : %" PRIu64 " over %.1f s\n", wakeups, run_s);
    printf("mean lateness      : %.1f us\n", wakeups ? (late_ns_sum/(double)wakeups)/1000.0 : 0.0);
    printf("max lateness       : %.1f us\n", late_ns_max/1000.0);
    printf("missed periods     : %" PRIu64 " total, longest run %" PRIu64 "\n",
           missed_total, missed_run_max);
    printf("WORST STALL        : %.3f ms  (at t+%" PRIu64 " s)\n",
           worst_stall_ns/1e6, worst_stall_at_s);
    printf("deadline           : %.3f ms\n", deadline_ns/1e6);

    printf("\nlateness histogram (us, log2 buckets):\n");
    for (unsigned b = 0; b < 24; b++) {
        if (!hist[b]) continue;
        printf("  %8u ..%8u : %" PRIu64 "\n",
               b ? 1u << (b-1) : 0u, (1u << b) - 1, hist[b]);
    }

    if (worst_stall_ns >= deadline_ns) {
        printf("\nVERDICT: BREACHED. Worst stall %.3f ms >= deadline %.3f ms.\n"
               "  At %u Hz this rate loses IMU samples on this host under this load.\n"
               "  Drop INS_GYRO_RATE a step and re-run, or fix the platform "
               "(PREEMPT_RT, performance governor, CPU isolation).\n",
               worst_stall_ns/1e6, deadline_ns/1e6, rate_hz);
        return 2;
    }
    printf("\nVERDICT: within deadline. Margin %.1fx (worst stall %.3f ms vs %.3f ms).\n"
           "  This is evidence for THIS load and THIS run length only -- a tail is\n"
           "  not a maximum. Run longer, and under the worst load you can stage.\n",
           worst_stall_ns > 0 ? (double)deadline_ns/worst_stall_ns : 999.0,
           worst_stall_ns/1e6, deadline_ns/1e6);
    return 0;
}
