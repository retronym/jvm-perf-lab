package zincdirect;

import io.github.retronym.perflab.jmh.Announce;
import org.openjdk.jmh.annotations.*;

import java.lang.reflect.Method;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * One op is one round of K concurrent clean compiles of one project (K copies, each with its own output directory and
 * analysis store) through Zinc's API in this JVM. The Zinc under test is loaded in a class loader of its own
 * (zincdirect.driver.Driver, called by reflection), so a fork can host either version. The score is the round's wall
 * time; the counters are per-copy means, in ms, by where Zinc's time goes (README.md).
 */
@State(Scope.Benchmark)
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.SECONDS)
@Fork(value = 1, jvmArgsAppend = {"-Xms16G", "-Xmx16G", "-Xss4M"})
@Warmup(iterations = 2, time = 1)
@Measurement(iterations = 3, time = 1)
public class ZincDirectBenchmark {

    /** The project under test: a directory of out/inputs (scripts/extract-inputs.sh), e.g. `stream`, `actor`. */
    @Param({"actor"})
    public String project;

    /** `1.12.1` or `1.13.0`: Zinc's own jars (scripts/prepare-classpaths.sh). */
    @Param({"1.12.1"})
    public String zincVersion;

    @Param({"2.13.18"})
    public String scalaVersion;

    /** `default`, or `clean`: IncOptions.enabled = false, a compile with no analysis (Zinc 2.x with the clean build mode). */
    @Param({"default"})
    public String mode;

    /** K: copies compiled at the same time. */
    @Param({"1"})
    public int copies;

    private Object driver;
    private Method clean, round;
    private int ops;

    /** Per-copy means over the round, ms: a copy's total is pre + the phases + post + persist. */
    @AuxCounters(AuxCounters.Type.EVENTS)
    @State(Scope.Thread)
    public static class Where {
        public double copyMeanMs, copyMaxMs;
        /** Zinc before the first phase: classpath lookup, loading the bridge */
        public double preMs;
        /** scalac, parser to the phase before the backend, without Zinc's own phases */
        public double frontMs;
        /** the `jvm` phase */
        public double backendMs;
        /** Zinc's `xsbt-api` (API extraction, name hashing) and `xsbt-dependency` phases */
        public double apiMs;
        /** Zinc's `xsbt-analyzer` phase (class file and product callbacks) and its analysis of javac's output */
        public double analyzerMs;
        public double javacMs;
        /** after the last phase: invalidation and the analysis merge */
        public double postMs;
        /** writing the analysis store */
        public double persistMs;
        public double errors, warnings;
    }

    @Setup(Level.Trial)
    public void setup() throws Exception {
        Announce.jvm("ZincDirectBenchmark(" + project + ", zinc " + zincVersion + ", scala " + scalaVersion + ", " + mode + ", K=" + copies + ")");
        Path out = Paths.get(System.getProperty("zincdirect.out", System.getenv().getOrDefault("ZINCDIRECT_OUT", "out"))).toAbsolutePath();
        Path work = out.resolve("work").resolve("fork-" + ProcessHandle.current().pid());
        Files.createDirectories(work);
        Runtime.getRuntime().addShutdownHook(new Thread(() -> deleteTree(work)));

        Path cpDir = out.resolve("cp");
        URL self = ZincDirectBenchmark.class.getProtectionDomain().getCodeSource().getLocation();
        java.util.List<URL> urls = new java.util.ArrayList<>();
        // a Zinc without 1.12.1's API (2.x) brings its own build of the driver (scripts/prepare-zinc-dev.sh)
        Path driverDir = cpDir.resolve("driver-" + zincVersion);
        urls.add(Files.isDirectory(driverDir) ? driverDir.toUri().toURL() : self);
        for (String line : Files.readAllLines(cpDir.resolve("zinc-" + zincVersion + ".txt"))) if (!line.isBlank()) urls.add(Paths.get(line.trim()).toUri().toURL());
        // the platform loader as parent: nothing of the benchmark's own classpath is visible to the Zinc under test
        URLClassLoader loader = new URLClassLoader(urls.toArray(new URL[0]), ClassLoader.getPlatformClassLoader());
        Class<?> c = loader.loadClass("zincdirect.driver.Driver");
        Map<String, String> cfg = new HashMap<>();
        cfg.put("zinc", zincVersion);
        cfg.put("scala", scalaVersion);
        cfg.put("copies", Integer.toString(copies));
        cfg.put("mode", mode);
        cfg.put("cpDir", cpDir.toString());
        cfg.put("inputs", out.resolve("inputs").resolve(project).toString());
        cfg.put("work", work.toString());
        System.out.printf("[zinc-direct] cores %d, zinc %s, scala %s, project %s, K=%d%n", Runtime.getRuntime().availableProcessors(), zincVersion, scalaVersion, project, copies);
        long t0 = System.nanoTime();
        driver = c.getConstructor(Map.class).newInstance(cfg);
        clean = c.getMethod("clean");
        round = c.getMethod("round");
        System.out.printf("[zinc-direct] driver up in %.1f s%n", (System.nanoTime() - t0) / 1e9);
        // one round outside the measurement: loads classes and shows the cost of a cold first compile
        clean.invoke(driver);
        t0 = System.nanoTime();
        Map<String, Double> m = result(round.invoke(driver));
        System.out.printf("[zinc-direct] first round %.1f s: %s%n", (System.nanoTime() - t0) / 1e9, m);
    }

    @Setup(Level.Invocation)
    public void cleanOutputs() throws Exception {
        clean.invoke(driver);
    }

    @Benchmark
    public void concurrentCleanCompiles(Where w) throws Exception {
        Map<String, Double> m = result(round.invoke(driver));
        System.out.printf("[zinc-direct] op %d: wall %.1f s, per copy mean %.1f s, max %.1f s; ms per copy: %s%n",
            ++ops, m.get("wallMs") / 1e3, m.get("total") / 1e3, m.get("copyMax") / 1e3, m);
        if (m.get("errors") > 0) throw new IllegalStateException("compile errors: " + m.get("errors"));
        w.copyMeanMs += m.get("total");
        w.copyMaxMs += m.get("copyMax");
        w.preMs += m.get("pre");
        w.postMs += m.get("post");
        w.persistMs += m.get("persist");
        w.errors += m.get("errors");
        w.warnings += m.get("warnings");
        for (Map.Entry<String, Double> e : m.entrySet()) {
            if (!e.getKey().startsWith("phase:")) continue;
            String p = e.getKey().substring(6);
            switch (p) {
                case "jvm": w.backendMs += e.getValue(); break;
                case "xsbt-api": case "xsbt-dependency": w.apiMs += e.getValue(); break;
                case "Java compilation": w.javacMs += e.getValue(); break;
                case "xsbt-analyzer": case "Java analysis": w.analyzerMs += e.getValue(); break;
                default: w.frontMs += e.getValue();
            }
        }
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Double> result(Object o) { return (Map<String, Double>) o; }

    private static void deleteTree(Path dir) {
        try (var w = Files.walk(dir)) {
            w.sorted(java.util.Comparator.reverseOrder()).forEach(p -> p.toFile().delete());
        } catch (Exception ignored) { }
    }
}
