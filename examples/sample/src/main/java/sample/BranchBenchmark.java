package sample;

import io.github.retronym.perflab.jmh.IterationLog;
import io.github.retronym.perflab.jmh.Variants;
import org.openjdk.jmh.annotations.*;
import org.openjdk.jmh.infra.IterationParams;
import org.openjdk.jmh.runner.IterationType;

import java.util.Arrays;
import java.util.Random;
import java.util.concurrent.TimeUnit;

/**
 * One op sums the elements of a byte array above a threshold, with a branch the JIT keeps as a branch (the sum differs
 * on each side): on `sorted` data it is taken in one long run and predicted, on `random` data half the time at random.
 * With `variants=sorted=sorted|random=random`, both alternate by iteration within the fork.
 */
@State(Scope.Benchmark)
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Fork(value = 1, jvmArgsAppend = {"-Xms1G", "-Xmx1G"})
@Warmup(iterations = 4, time = 1)
@Measurement(iterations = 6, time = 1)
public class BranchBenchmark {
    @Param({"1048576"})
    public int size;

    @Param({"random"})
    public String data;

    @Param({""})
    public String variants;

    private byte[] sorted, random, values;
    private Variants vs;
    private int iteration;

    @Setup(Level.Trial)
    public void setup() {
        random = new byte[size];
        new Random(42).nextBytes(random);
        sorted = random.clone();
        Arrays.sort(sorted);
        vs = Variants.parse(variants);
        IterationLog.reset(vs.names());
        values = data.equals("sorted") ? sorted : random;
    }

    @Setup(Level.Iteration)
    public void nextVariant(IterationParams ip) {
        if (vs.isEmpty()) return;
        Variants.Variant v = vs.forIteration(iteration++);
        values = v.options().get(0).equals("sorted") ? sorted : random;
        IterationLog.begin(v.name(), ip.getType() == IterationType.MEASUREMENT);
    }

    @TearDown(Level.Iteration)
    public void endVariant() {
        if (!vs.isEmpty()) IterationLog.end();
    }

    @Benchmark
    public long sumAbove() {
        byte[] v = values;
        long above = 0, below = 0;
        for (byte b : v) {
            if (b >= 0) above += b * 3;
            else below ^= b;
        }
        return above + below;
    }
}
