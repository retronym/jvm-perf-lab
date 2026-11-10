package zincdirect;

/** Runs the benchmark's setup and two rounds without JMH, to check the harness: {@code Check <zinc> <scala> <K> [project]}. */
public final class Check {
    public static void main(String[] a) throws Exception {
        ZincDirectBenchmark b = new ZincDirectBenchmark();
        b.zincVersion = a[0];
        b.scalaVersion = a[1];
        b.copies = Integer.parseInt(a[2]);
        b.project = a.length > 3 ? a[3] : "actor";
        b.setup();
        for (int i = 0; i < 2; i++) {
            b.cleanOutputs();
            b.concurrentCleanCompiles(new ZincDirectBenchmark.Where());
        }
        System.exit(0);
    }
}
