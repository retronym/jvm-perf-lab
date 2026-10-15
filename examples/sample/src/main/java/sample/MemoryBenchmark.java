package sample;

import io.github.retronym.perflab.jmh.IterationLog;
import io.github.retronym.perflab.jmh.Variants;
import org.openjdk.jmh.annotations.*;
import org.openjdk.jmh.infra.IterationParams;
import org.openjdk.jmh.runner.IterationType;

import java.util.Random;
import java.util.concurrent.TimeUnit;

/**
 * One op visits every element of an int array once, following a chain of indices: `sequential` visits them in order,
 * `shuffled` in a random cycle, so each load depends on the previous one and misses the caches once the array outgrows
 * them. `size` is the number of elements (4 bytes each). With `variants=seq=sequential|chase=shuffled`, both layouts
 * alternate by iteration within the fork.
 */
@State(Scope.Benchmark)
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Fork(value = 1, jvmArgsAppend = {"-Xms1G", "-Xmx1G"})
@Warmup(iterations = 4, time = 1)
@Measurement(iterations = 6, time = 1)
public class MemoryBenchmark {
    @Param({"4194304"})
    public int size;

    @Param({"shuffled"})
    public String layout;

    @Param({""})
    public String variants;

    private int[] sequential, shuffled, next;
    private Variants vs;
    private int iteration;

    @Setup(Level.Trial)
    public void setup() {
        sequential = new int[size];
        for (int i = 0; i < size; i++) sequential[i] = (i + 1) % size;
        // a single random cycle through all elements (Sattolo's algorithm), so the chase visits each one
        int[] order = new int[size];
        for (int i = 0; i < size; i++) order[i] = i;
        Random r = new Random(42);
        for (int i = size - 1; i > 0; i--) { int j = r.nextInt(i); int t = order[i]; order[i] = order[j]; order[j] = t; }
        shuffled = new int[size];
        for (int i = 0; i < size; i++) shuffled[order[i]] = order[(i + 1) % size];
        vs = Variants.parse(variants);
        IterationLog.reset(vs.names());
        next = layout.equals("sequential") ? sequential : shuffled;
    }

    @Setup(Level.Iteration)
    public void nextVariant(IterationParams ip) {
        if (vs.isEmpty()) return;
        Variants.Variant v = vs.forIteration(iteration++);
        next = v.options().get(0).equals("sequential") ? sequential : shuffled;
        IterationLog.begin(v.name(), ip.getType() == IterationType.MEASUREMENT);
    }

    @TearDown(Level.Iteration)
    public void endVariant() {
        if (!vs.isEmpty()) IterationLog.end();
    }

    @Benchmark
    public long chase() {
        int[] n = next;
        long sum = 0;
        int i = 0;
        for (int k = 0; k < n.length; k++) {
            sum += i;
            i = n[i];
        }
        return sum;
    }
}
