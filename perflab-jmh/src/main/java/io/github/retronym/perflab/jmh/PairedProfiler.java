package io.github.retronym.perflab.jmh;

import org.openjdk.jmh.infra.BenchmarkParams;
import org.openjdk.jmh.infra.IterationParams;
import org.openjdk.jmh.profile.InternalProfiler;
import org.openjdk.jmh.results.AggregationPolicy;
import org.openjdk.jmh.results.IterationResult;
import org.openjdk.jmh.results.Result;
import org.openjdk.jmh.results.ScalarResult;
import org.openjdk.jmh.runner.IterationType;

import java.lang.management.ManagementFactory;
import java.util.*;

/**
 * Time per variant for a benchmark that alternates variants within one fork ({@link IterationLog}); with
 * {@code -Dperflab.cell=<dir>}, also each iteration's span and score in {@code <dir>/iterations.tsv} as it finishes.
 * JMH's own score mixes the variants. Reports, over the measurement iterations: each variant's mean score
 * ({@code paired.<variant>}, in the benchmark's unit), and for each variant but the baseline the paired difference, the
 * mean and standard deviation over cycles of {@code 100 * (variant / baseline - 1)}, where a cycle is the consecutive
 * iterations in which each variant ran once ({@code paired.<variant>.delta%}, {@code .delta%.sd}). The same again with
 * each iteration's GC time taken out ({@code paired.gcFree.<variant>}), and for the bytes allocated per op, by all
 * threads ({@code paired.alloc.<variant>}, in B/op: JMH's {@code -prof gc} mixes the variants).
 */
public class PairedProfiler implements InternalProfiler {
    // Each result is emitted once per fork, after the last measurement iteration. Not MAX, which floors at zero and
    // so loses a negative difference.
    static final AggregationPolicy POLICY = AggregationPolicy.SUM;

    /** One measured iteration's value, e.g. its score or a counter per op. */
    public record Point(IterationLog.Entry entry, double score) {}

    private final List<Point> points = new ArrayList<>();
    private final List<Point> gcFree = new ArrayList<>();
    private final List<Point> alloc = new ArrayList<>();
    private String unit = "";
    private int seen;

    @Override
    public String getDescription() {
        return "Time per variant, and paired differences, when variants alternate by iteration within the fork";
    }

    // -Dperflab.cell=<dir> (`perflab run` and `perflab ab` give it): each iteration is appended to <dir>/iterations.tsv
    // as it finishes, warmup included, for the timeline (timeline.js). Every fork appends to the same file, with its pid;
    // a fork also adds a "startup" row (JVM start to its first iteration: JVM boot, benchmark setup) and, from a
    // shutdown hook, an "exit" row (its last iteration to JVM exit).
    private static final String CELL = System.getProperty("perflab.cell");
    static final String HEADER = "index\tkind\tvariant\tstart_ms\tend_ms\tscore\tops\tgc_ms\tpid\tunit\talloc_bytes\n";
    private static final long PID = ProcessHandle.current().pid();
    private long iterationStart;
    private int iterations;
    private volatile long lastEnd;

    @Override
    public void beforeIteration(BenchmarkParams bp, IterationParams ip) { iterationStart = System.currentTimeMillis(); }

    private static void append(String row) {
        java.nio.file.Path f = java.nio.file.Path.of(CELL, "iterations.tsv");
        try {
            java.nio.file.Files.createDirectories(f.getParent());
            synchronized (PairedProfiler.class) {
                if (!java.nio.file.Files.exists(f)) java.nio.file.Files.writeString(f, HEADER);
                java.nio.file.Files.writeString(f, row, java.nio.file.StandardOpenOption.APPEND);
            }
        } catch (java.io.IOException ex) {
            System.err.println("[perflab] cannot write iterations.tsv: " + ex);
        }
    }

    static String row(int index, String kind, String variant, long start, long end, String score, String ops, String gc, String unit,
                      String alloc) {
        return String.join("\t", Integer.toString(index), kind, variant, Long.toString(start), Long.toString(end), score, ops, gc,
            Long.toString(PID), unit, alloc) + "\n";
    }

    /** Did the iteration finish with a score? Not when the benchmark threw: JMH then has no primary result. */
    static boolean scored(IterationResult ir) { return !ir.getRawPrimaryResults().isEmpty(); }

    private void logIteration(IterationParams ip, IterationResult ir) {
        if (CELL == null) return;
        boolean scored = scored(ir);
        String unit = scored ? ir.getPrimaryResult().getScoreUnit() : "";
        if (iterations == 0) {
            append(row(-1, "startup", "", ManagementFactory.getRuntimeMXBean().getStartTime(), iterationStart, "", "", "", unit, ""));
            Runtime.getRuntime().addShutdownHook(new Thread(() ->
                append(row(-1, "exit", "", lastEnd, System.currentTimeMillis(), "", "", "", unit, "")), "perflab-exit"));
        }
        IterationLog.Entry e = IterationLog.paired() ? IterationLog.last() : null;
        lastEnd = System.currentTimeMillis();
        append(row(iterations, ip.getType() == IterationType.MEASUREMENT ? "measure" : "warmup", e == null ? "" : e.variant(),
            iterationStart, lastEnd, scored ? String.format(Locale.ROOT, "%.4f", ir.getPrimaryResult().getScore()) : "",
            ir.getMetadata() == null ? "" : Long.toString(ir.getMetadata().getMeasuredOps()), e == null ? "" : Long.toString(e.gcMillis()), unit,
            e == null || e.allocBytes() < 0 ? "" : Long.toString(e.allocBytes())));
        iterations++;
    }

    @Override
    public Collection<? extends Result> afterIteration(BenchmarkParams bp, IterationParams ip, IterationResult ir) {
        logIteration(ip, ir);
        if (!IterationLog.paired()) return List.of();
        IterationLog.Entry e = IterationLog.last();
        if (e != null && ip.getType() == IterationType.MEASUREMENT && scored(ir)) {
            double score = ir.getPrimaryResult().getScore();
            points.add(new Point(e, score));
            // the same time per op with the iteration's GC time taken out, pro rata: separates "this variant's code is
            // slower" from "a collection landed in this variant's iteration"
            long span = e.endMillis() - e.startMillis();
            if (span > 0) gcFree.add(new Point(e, score * Math.max(0, 1 - e.gcMillis() / (double) span)));
            long ops = ir.getMetadata().getMeasuredOps();
            if (e.allocBytes() >= 0 && ops > 0) alloc.add(new Point(e, e.allocBytes() / (double) ops));
            unit = ir.getPrimaryResult().getScoreUnit();
        }
        if (ip.getType() != IterationType.MEASUREMENT || ++seen < ip.getCount()) return List.of();
        List<Result> out = new ArrayList<>(results(IterationLog.variants(), points, unit, "paired."));
        out.addAll(results(IterationLog.variants(), gcFree, unit, "paired.gcFree."));
        if (!alloc.isEmpty()) out.addAll(results(IterationLog.variants(), alloc, "B/op", "paired.alloc."));
        return out;
    }

    /** Mean per variant, and paired differences against the first variant, from per-iteration values. */
    public static List<Result> results(List<String> variants, List<Point> points, String unit, String prefix) {
        Map<String, List<Double>> by = new LinkedHashMap<>();
        Map<Integer, Map<String, Double>> cycles = new TreeMap<>();
        for (Point p : points) {
            by.computeIfAbsent(p.entry().variant(), k -> new ArrayList<>()).add(p.score());
            cycles.computeIfAbsent(p.entry().cycle(variants.size()), k -> new HashMap<>()).put(p.entry().variant(), p.score());
        }
        List<Result> out = new ArrayList<>();
        String base = variants.get(0);
        StringBuilder log = new StringBuilder("[perflab] paired " + prefix + " (" + unit + "):");
        for (String v : variants) {
            List<Double> xs = by.getOrDefault(v, List.of());
            if (xs.isEmpty()) continue;
            double mean = mean(xs);
            out.add(new ScalarResult(prefix + v, mean, unit, POLICY));
            log.append(String.format(" %s %.4g", v, mean));
            if (v.equals(base)) continue;
            List<Double> deltas = new ArrayList<>();
            for (Map<String, Double> c : cycles.values())
                if (c.containsKey(v) && c.containsKey(base) && c.get(base) != 0) deltas.add(100 * (c.get(v) / c.get(base) - 1));
            if (deltas.isEmpty()) continue;
            double d = mean(deltas), sd = sd(deltas, d);
            out.add(new ScalarResult(prefix + v + ".delta%", d, "%", POLICY));
            out.add(new ScalarResult(prefix + v + ".delta%.sd", sd, "%", POLICY));
            // the median shrugs off a few disturbed cycles (a preempted iteration loses up to 10% of its sampled counts)
            List<Double> sorted = new ArrayList<>(deltas);
            Collections.sort(sorted);
            int m = sorted.size();
            double median = m % 2 == 1 ? sorted.get(m / 2) : (sorted.get(m / 2 - 1) + sorted.get(m / 2)) / 2;
            out.add(new ScalarResult(prefix + v + ".delta%.median", median, "%", POLICY));
            log.append(String.format(" (%+.2f%% ± %.2f, median %+.2f%%, %d pairs)", d, sd, median, deltas.size()));
        }
        System.out.println(log);
        return out;
    }

    static double mean(List<Double> xs) {
        double s = 0;
        for (double x : xs) s += x;
        return s / xs.size();
    }

    static double sd(List<Double> xs, double mean) {
        if (xs.size() < 2) return 0;
        double s = 0;
        for (double x : xs) s += (x - mean) * (x - mean);
        return Math.sqrt(s / (xs.size() - 1));
    }
}
