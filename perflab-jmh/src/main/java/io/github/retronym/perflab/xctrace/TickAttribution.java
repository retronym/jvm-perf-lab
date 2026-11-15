package io.github.retronym.perflab.xctrace;

import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Charges an xctrace counters-profile table's counts to threads by time on core, not by sample label.
 *
 * In a counters-profile table each row's counter values are the deltas since the previous sample <em>on the same
 * core</em>. Besides the timer samples (one per core per period, all cores at one phase, only on busy cores) the table
 * has context-switch samples, and those are labelled inconsistently: one labelled with the kernel's idle thread often
 * carries the work of the thread that ran before it. Crediting every delta to its row's thread therefore loses work to
 * "idle" (a quarter of the benchmark's instructions in an 8-thread run on an M5 Pro).
 *
 * Instead, for each bucket (a thread, a thread group, an iteration, a timeline bin) and core class:
 *  - time on core = the bucket's timer samples × the period: a timer sample names the thread running at that instant;
 *  - rates (instructions per ns, cycles per ns, ...) = the deltas of intervals whose two ends, on one core, name the
 *    same thread, over those intervals' length: such an interval is that thread's work alone;
 *  - an event's count = time on core × rate, summed over core classes (Super, Performance, Efficiency run the same
 *    code at different rates, and a thread's mix of them differs by fork).
 * A bucket and class with ticks but no same-thread interval falls back to its labelled deltas.
 *
 * Feed it samples in time order with {@link #sample}, then {@link #finish}; read with {@link #estimate}.
 */
final class TickAttribution {
    static final Pattern CORE_CLASS = Pattern.compile("\\((\\w) Core\\)");

    /** A core's class from its xctrace label, e.g. "CPU 12 (S Core)" -> "S"; "?" if it has none. */
    static String coreClass(String coreFmt) {
        Matcher m = coreFmt == null ? null : CORE_CLASS.matcher(coreFmt);
        return m != null && m.find() ? m.group(1) : "?";
    }

    static final class Acc {
        long ticks;          // timer samples
        long uniNs;          // length of same-thread intervals
        final long[] uni;    // their deltas
        final long[] labelled;   // every delta of rows with this bucket's label (the old attribution)
        Acc(int n) { uni = new long[n]; labelled = new long[n]; }
    }

    private record Sample(long t, String core, String cclass, String thread, long[] deltas, List<String> buckets) {}
    private record Last(long t, String thread) {}

    private static final int PHASE_SAMPLES = 20_000;
    private static final long PHASE_BIN_NS = 5_000;

    final int events;
    final long periodNs;
    final long windowNs;
    private long phase = -1;
    private final List<Sample> pending = new ArrayList<>();
    private final Map<String, Last> last = new HashMap<>();
    // bucket -> core class -> accumulators
    private final Map<String, Map<String, Acc>> acc = new LinkedHashMap<>();

    TickAttribution(int events, long periodNs) {
        this.events = events;
        this.periodNs = periodNs;
        this.windowNs = Math.max(1, periodNs * 15 / 1000);   // 15 µs of a 1 ms period
    }

    /** One row: its time (ns from trace start), core id and label, thread (any key unique to the thread), its
     *  counter deltas, and the buckets it counts towards. */
    void sample(long t, String core, String coreFmt, String thread, long[] deltas, List<String> buckets) {
        Sample s = new Sample(t, core, coreClass(coreFmt), thread, deltas, buckets);
        if (phase < 0) {
            pending.add(s);
            if (pending.size() >= PHASE_SAMPLES) flushPending();
        } else {
            add(s);
        }
    }

    void finish() { if (phase < 0) flushPending(); }

    /** The timer's phase: the most common (time mod period), at 5 µs resolution, over the first samples. Context
     *  switches fall anywhere in the period; timer samples all fall in one bin. */
    private void flushPending() {
        Map<Long, Integer> hist = new HashMap<>();
        for (Sample s : pending) hist.merge(Math.floorMod(s.t, periodNs) / PHASE_BIN_NS, 1, Integer::sum);
        phase = hist.entrySet().stream().max(Map.Entry.comparingByValue()).map(e -> e.getKey() * PHASE_BIN_NS + PHASE_BIN_NS / 2)
            .orElse(0L);
        for (Sample s : pending) add(s);
        pending.clear();
    }

    boolean isTick(long t) {
        long d = Math.floorMod(t - phase, periodNs);
        return d <= windowNs || d >= periodNs - windowNs;
    }

    private Acc acc(String bucket, String cclass) {
        return acc.computeIfAbsent(bucket, k -> new TreeMap<>()).computeIfAbsent(cclass, k -> new Acc(events));
    }

    private void add(Sample s) {
        boolean tick = isTick(s.t);
        Last prev = last.get(s.core);
        boolean same = prev != null && prev.thread.equals(s.thread) && s.t > prev.t;
        for (String b : s.buckets) {
            Acc a = acc(b, s.cclass);
            for (int i = 0; i < events; i++) a.labelled[i] += s.deltas[i];
            if (tick) a.ticks++;
            if (same) {
                a.uniNs += s.t - prev.t;
                for (int i = 0; i < events; i++) a.uni[i] += s.deltas[i];
            }
        }
        last.put(s.core, new Last(s.t, s.thread));
    }

    Set<String> buckets() { return acc.keySet(); }

    /** Core class -> accumulators of a bucket (empty if it never ran). */
    Map<String, Acc> classes(String bucket) { return acc.getOrDefault(bucket, Map.of()); }

    /** Time on core of a bucket, in ns. */
    long onCpuNs(String bucket) {
        return classes(bucket).values().stream().mapToLong(a -> a.ticks).sum() * periodNs;
    }

    /** Each event's count for a bucket: time on core × rate per core class. */
    long[] estimate(String bucket) {
        long[] out = new long[events];
        for (Acc a : classes(bucket).values()) {
            for (int i = 0; i < events; i++) {
                out[i] += a.uniNs > 0 ? Math.round(a.ticks * (double) periodNs * a.uni[i] / a.uniNs)
                    : a.ticks > 0 ? a.labelled[i] : 0;
            }
        }
        return out;
    }

    /** Each event's count credited to the rows labelled with this bucket (the attribution this class replaces). */
    long[] labelled(String bucket) {
        long[] out = new long[events];
        for (Acc a : classes(bucket).values()) for (int i = 0; i < events; i++) out[i] += a.labelled[i];
        return out;
    }
}
