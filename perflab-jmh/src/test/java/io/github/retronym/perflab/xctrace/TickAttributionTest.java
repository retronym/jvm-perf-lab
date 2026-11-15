package io.github.retronym.perflab.xctrace;

import org.junit.jupiter.api.Test;

import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

class TickAttributionTest {
    static final long MS = 1_000_000;

    @Test
    void coreClassFromLabel() {
        assertEquals("S", TickAttribution.coreClass("CPU 12 (S Core)"));
        assertEquals("P", TickAttribution.coreClass("CPU 3 (P Core)"));
        assertEquals("E", TickAttribution.coreClass("CPU 0 (E Core)"));
        assertEquals("?", TickAttribution.coreClass("CPU 0"));
        assertEquals("?", TickAttribution.coreClass(null));
    }

    /** One core runs "bench" the whole time at 4 instructions/ns, with timer ticks every 1 ms. A context-switch
     *  sample 0.6 ms after each tick is labelled "idle" but carries bench's work since the tick. The labelled
     *  attribution loses that work to idle; time on core × rate recovers it. */
    @Test
    void workCarriedByMislabelledSwitchSamplesIsChargedToTheRunningThread() {
        TickAttribution ta = new TickAttribution(1, MS);
        long phase = 300_000, rate = 4;
        long prev = phase - MS;
        int n = 30_000;
        Random r = new Random(2);
        for (int k = 0; k < n; k++) {
            long tick = phase + k * MS;
            long sw = tick + 100_000 + r.nextInt(800_000);   // context switches fall anywhere in the period
            ta.sample(tick, "12", "CPU 12 (S Core)", "bench#1", new long[]{(tick - prev) * rate}, List.of("bench"));
            ta.sample(sw, "12", "CPU 12 (S Core)", "idle", new long[]{(sw - tick) * rate}, List.of("idle"));
            prev = sw;
        }
        ta.finish();
        long truth = n * MS * rate;
        assertEquals(n * MS, ta.onCpuNs("bench"));
        assertTrue(ta.labelled("bench")[0] < truth * 0.5, "labelled attribution loses the work");
        // no two consecutive samples on the core name bench, so its rate falls back to its labelled counts:
        // a bucket needs same-thread intervals for a rate (real traces have them: see the next test)
        assertEquals(0, ta.classes("bench").get("S").uniNs);
    }

    /** As above, but some ticks are followed by another bench tick (no switch in between), as in real traces where
     *  most of a busy thread's ticks are back to back. Those intervals give bench's rate; its ticks give its time. */
    @Test
    void timeOnCoreTimesSameThreadRateRecoversMislabelledWork() {
        TickAttribution ta = new TickAttribution(1, MS);
        long phase = 300_000, rate = 4;
        long prev = phase - MS;
        int n = 30_000;
        for (int k = 0; k < n; k++) {
            long tick = phase + k * MS;
            ta.sample(tick, "12", "CPU 12 (S Core)", "bench#1", new long[]{(tick - prev) * rate}, List.of("bench"));
            prev = tick;
            if (k % 4 == 0) {   // every 4th ms a switch sample, mislabelled idle, carrying bench's work
                long sw = tick + 600_000;
                ta.sample(sw, "12", "CPU 12 (S Core)", "idle", new long[]{(sw - tick) * rate}, List.of("idle"));
                prev = sw;
            }
        }
        ta.finish();
        long truth = n * MS * rate;
        long lab = ta.labelled("bench")[0];
        long est = ta.estimate("bench")[0];
        assertTrue(lab < truth * 0.9, "labelled loses about 15%: " + lab + " of " + truth);
        assertEquals(truth, est, truth * 0.001, "time × rate recovers it");
    }

    /** A thread's work is its time on each core class times that class's own rate. */
    @Test
    void ratesArePerCoreClass() {
        TickAttribution ta = new TickAttribution(2, MS);   // instructions, cycles
        long[] t = {100_000, 100_000};
        for (int k = 0; k < 25_000; k++) {
            long now = 100_000 + (k + 1) * MS;
            for (int c = 0; c < 2; c++) {
                boolean fast = c == 0;
                long cyc = (now - t[c]) * 4;            // 4 GHz on both
                long ins = fast ? cyc * 4 : cyc * 2;   // IPC 4 vs 2
                ta.sample(now, fast ? "12" : "3", fast ? "CPU 12 (S Core)" : "CPU 3 (P Core)", "bench#" + c,
                    new long[]{ins, cyc}, List.of(fast ? "fast" : "slow", "all"));
                t[c] = now;
            }
        }
        ta.finish();
        assertEquals(2.0, ta.estimate("fast")[0] / (double) ta.estimate("slow")[0], 0.01);
        long all = ta.estimate("all")[0];
        assertEquals(ta.estimate("fast")[0] + ta.estimate("slow")[0], all, all * 0.001);
        assertEquals(Set.of("S", "P"), ta.classes("all").keySet());
        TickAttribution.Acc s = ta.classes("fast").get("S");
        assertEquals(4.0, s.uni[1] / (double) s.uniNs, 0.01, "GHz");
    }

    @Test
    void phaseIsFoundAmongSwitchSamples() {
        TickAttribution ta = new TickAttribution(1, MS);
        Random r = new Random(1);
        for (int k = 0; k < 25_000; k++) {
            ta.sample(k * MS + 700_000, "0", "CPU 0 (P Core)", "a", new long[]{1}, List.of("a"));
            ta.sample(k * MS + 720_000 + r.nextInt(900_000), "0", "CPU 0 (P Core)", "b", new long[]{1}, List.of("b"));
        }
        ta.finish();
        assertTrue(ta.isTick(700_000) && ta.isTick(5 * MS + 702_000));
        assertFalse(ta.isTick(5 * MS + 300_000));
        assertEquals(25_000L * MS, ta.onCpuNs("a"));
    }

    @Test
    void aClassWithTicksButNoSameThreadIntervalFallsBackToItsLabelledCounts() {
        TickAttribution ta = new TickAttribution(1, MS);
        for (int k = 0; k < 25_000; k++)
            ta.sample(k * MS, "0", "CPU 0 (P Core)", k % 2 == 0 ? "x" : "y", new long[]{10}, List.of(k % 2 == 0 ? "x" : "y"));
        ta.finish();
        assertEquals(12_500L * 10, ta.estimate("x")[0]);
    }
}
