package io.github.retronym.perflab.jmh;

import java.util.ArrayList;
import java.util.List;

/**
 * Variants compared within one fork (see doc/paired-ab.md): a benchmark parameter such as
 * {@code variants=base=-Ya -Yb|fast=-Ya}, read with {@link #parse}, and the order to run them in, {@link #order}. Each
 * iteration runs one variant, bracketed by {@link IterationLog#begin} and {@link IterationLog#end}, so that
 * {@link PairedProfiler} and the xctrace profiler can report per variant:
 *
 * <pre>
 * &#64;Setup(Level.Trial)     void setup()       { variants = Variants.parse(param); IterationLog.reset(variants.names()); ... }
 * &#64;Setup(Level.Iteration) void next(IterationParams ip) {
 *     Variants.Variant v = variants.forIteration(iteration++);   // switch the benchmark to v.options()
 *     IterationLog.begin(v.name(), ip.getType() == IterationType.MEASUREMENT); }
 * &#64;TearDown(Level.Iteration) void end() { IterationLog.end(); }
 * </pre>
 *
 * JMH splits a parameter value at commas, so variants are separated by {@code |} and options cannot contain commas.
 */
public record Variants(List<Variant> all) {
    /** A variant: its name, and its options split at spaces (e.g. compiler options, or whatever the benchmark takes). */
    public record Variant(String name, List<String> options) {}

    public static Variants parse(String spec) {
        List<Variant> out = new ArrayList<>();
        for (String v : spec.split("\\|")) {
            v = v.trim();
            if (v.isEmpty()) continue;
            int eq = v.indexOf('=');
            if (eq <= 0) throw new IllegalArgumentException("variant without a name: '" + v + "' (expected <name>=<options>)");
            List<String> opts = new ArrayList<>();
            for (String o : v.substring(eq + 1).trim().split("\\s+")) if (!o.isEmpty()) opts.add(o);
            out.add(new Variant(v.substring(0, eq).trim(), List.copyOf(opts)));
        }
        return new Variants(List.copyOf(out));
    }

    public List<String> names() { return all.stream().map(Variant::name).toList(); }

    public boolean isEmpty() { return all.isEmpty(); }

    /** The variant of the trial's {@code iteration}-th iteration (warmup included, from 0). */
    public Variant forIteration(int iteration) {
        int n = all.size();
        return all.get(order(n, iteration / n)[iteration % n]);
    }

    /**
     * The order of {@code n} variants in cycle {@code k}: the rows of a Williams design, so that over a whole number of
     * its rows ({@code n} for even {@code n}, {@code 2n} for odd) each variant runs in each position equally often, and
     * right after each other variant equally often. A fixed order would put one variant always after the same one and
     * at the same point in the heap's fill, where collections land; for two variants this is A B, B A.
     */
    public static int[] order(int n, int k) {
        int[] first = new int[n];
        for (int i = 0; i < n; i++) first[i] = i == 0 ? 0 : i % 2 == 1 ? (i + 1) / 2 : n - i / 2;
        int rows = n % 2 == 0 ? n : 2 * n, r = k % rows;
        int[] row = new int[n];
        for (int i = 0; i < n; i++) row[i] = (first[i] + r % n) % n;
        if (r >= n) for (int i = 0; i < n / 2; i++) { int t = row[i]; row[i] = row[n - 1 - i]; row[n - 1 - i] = t; }
        return row;
    }
}
