package sample;

import io.github.retronym.perflab.jmh.Announce;
import io.github.retronym.perflab.jmh.IterationLog;
import io.github.retronym.perflab.jmh.Variants;
import one.profiler.Span;
import org.openjdk.jmh.annotations.*;
import org.openjdk.jmh.infra.IterationParams;
import org.openjdk.jmh.runner.IterationType;

import java.util.*;
import java.util.concurrent.TimeUnit;

/**
 * One op counts the words of a generated text, then looks some up. `size` is the number of words. `map` picks the map;
 * or `variants` (e.g. `hash=hash|tree=tree`) alternates maps by iteration within one fork, each variant's options
 * naming its map.
 *
 * Each op marks its two parts, counting and looking up, as async-profiler spans (perflab-spans), so the flame graph's
 * span panel splits the op's samples by part. Without a recording, a span costs a check of a static field.
 */
@State(Scope.Benchmark)
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Fork(value = 1, jvmArgsAppend = {"-Xms1G", "-Xmx1G"})
@Warmup(iterations = 5, time = 1)
@Measurement(iterations = 5, time = 1)
public class WordCountBenchmark {
    @Param({"10000"})
    public int size;

    @Param({"hash"})
    public String map;

    @Param({""})
    public String variants;

    private List<String> words;
    private Variants vs;
    private String impl;
    private int iteration;

    @Setup(Level.Trial)
    public void setup() {
        Announce.jvm("WordCountBenchmark(" + size + ")");
        Random r = new Random(42);
        words = new ArrayList<>(size);
        for (int i = 0; i < size; i++) words.add((r.nextBoolean() ? "W" : "w") + (int) Math.abs(r.nextGaussian() * size / 10));
        vs = Variants.parse(variants);
        IterationLog.reset(vs.names());
        impl = map;
    }

    @Setup(Level.Iteration)
    public void nextVariant(IterationParams ip) {
        if (vs.isEmpty()) return;
        Variants.Variant v = vs.forIteration(iteration++);
        impl = v.options().get(0);
        IterationLog.begin(v.name(), ip.getType() == IterationType.MEASUREMENT);
    }

    @TearDown(Level.Iteration)
    public void endVariant() {
        if (!vs.isEmpty()) IterationLog.end();
    }

    @Benchmark
    public int countAndLookUp() {
        long start = Span.start();  // 0 unless a recording is running
        WordCount wc = new WordCount(impl);
        int n = wc.count(words);
        long counted = Span.start();
        Span.endIfProfiled(start, "count");
        for (int i = 0; i < 100; i++) if (wc.contains(words.get(i))) n++;
        Span.endIfProfiled(counted, "look up");
        return n;
    }
}
