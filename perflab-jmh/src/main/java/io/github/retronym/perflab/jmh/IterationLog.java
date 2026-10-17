package io.github.retronym.perflab.jmh;

import java.util.ArrayList;
import java.util.List;

/**
 * The iterations of a benchmark that alternates variants within one fork (see {@link Variants}): which
 * variant each iteration ran, and when, by the wall clock. The benchmark writes it; profilers in the same fork read it to
 * split their measurements by variant (time from {@link PairedProfiler}, counters from {@code XctraceProfiler}).
 */
public final class IterationLog {
    /** One iteration: its position among all iterations of the trial, warmup included, so consecutive iterations
     *  {@code index / variants().size()} form a cycle in which each variant ran once; its wall-clock span; and the time
     *  the JVM spent in collection pauses during it, and the bytes all its threads allocated during it (-1 when the JVM
     *  cannot say). */
    public record Entry(int index, String variant, boolean measured, long startMillis, long endMillis, long gcMillis,
                        long allocBytes) {
        public Entry(int index, String variant, boolean measured, long startMillis, long endMillis, long gcMillis) {
            this(index, variant, measured, startMillis, endMillis, gcMillis, -1);
        }
        public int cycle(int variants) { return index / variants; }
    }

    private static final List<Entry> entries = new ArrayList<>();
    private static List<String> variants = List.of();
    private static Entry open;
    private static long gcAtStart;
    private static long allocAtStart;

    /** Total time of collection pauses so far, by the GC MXBeans. Not G1's "Concurrent GC", which counts marking that
     *  runs beside the application rather than stopping it. */
    static long gcMillis() {
        long t = 0;
        for (var gc : java.lang.management.ManagementFactory.getGarbageCollectorMXBeans())
            if (!gc.getName().contains("Concurrent")) t += Math.max(0, gc.getCollectionTime());
        return t;
    }

    private static final java.lang.management.ThreadMXBean THREADS = java.lang.management.ManagementFactory.getThreadMXBean();
    // ThreadMXBean.getTotalThreadAllocatedBytes, JDK 21 and later (this module targets 17), counts ended threads too
    private static final java.lang.invoke.MethodHandle TOTAL_ALLOCATED = totalAllocated();

    private static java.lang.invoke.MethodHandle totalAllocated() {
        try {
            return java.lang.invoke.MethodHandles.publicLookup().findVirtual(com.sun.management.ThreadMXBean.class,
                "getTotalThreadAllocatedBytes", java.lang.invoke.MethodType.methodType(long.class));
        } catch (ReflectiveOperationException e) {
            return null;
        }
    }

    /** Bytes allocated so far by all threads (before JDK 21, by the live ones), or -1 when the JVM does not count them. */
    static long allocatedBytes() {
        if (!(THREADS instanceof com.sun.management.ThreadMXBean t) || !t.isThreadAllocatedMemorySupported()
                || !t.isThreadAllocatedMemoryEnabled()) return -1;
        if (TOTAL_ALLOCATED != null) {
            try {
                return (long) TOTAL_ALLOCATED.invoke(t);
            } catch (Throwable e) {
                return -1;
            }
        }
        long sum = 0;
        for (long b : t.getThreadAllocatedBytes(t.getAllThreadIds())) if (b > 0) sum += b;
        return sum;
    }

    private IterationLog() {}

    /** Starts a trial with these variants, in order; the first is the baseline. */
    public static synchronized void reset(List<String> names) {
        entries.clear();
        variants = List.copyOf(names);
        open = null;
    }

    /** Is the current trial alternating variants? */
    public static synchronized boolean paired() { return variants.size() > 1; }

    public static synchronized List<String> variants() { return variants; }

    public static synchronized void begin(String variant, boolean measured) {
        gcAtStart = gcMillis();
        allocAtStart = allocatedBytes();
        open = new Entry(entries.size(), variant, measured, System.currentTimeMillis(), -1, 0);
    }

    public static synchronized void end() {
        if (open == null) return;
        long alloc = allocatedBytes();
        Entry e = new Entry(open.index(), open.variant(), open.measured(), open.startMillis(), System.currentTimeMillis(),
                gcMillis() - gcAtStart, alloc < 0 || allocAtStart < 0 ? -1 : alloc - allocAtStart);
        entries.add(e);
        open = null;
    }

    /** The iteration that ended last, or null. */
    public static synchronized Entry last() { return entries.isEmpty() ? null : entries.get(entries.size() - 1); }

    public static synchronized List<Entry> entries() { return List.copyOf(entries); }
}
