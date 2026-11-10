package zinclab;

import io.github.retronym.perflab.jmh.Announce;
import org.openjdk.jmh.annotations.*;

import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * One op is one {@code clean; compile} of the whole Pekko build in a warm sbt hosted in this JVM, with sbt's default
 * task parallelism: what a regular sbt user waits for, with several compiler Globals in one JVM.
 *
 * The fork's setup copies a pristine Pekko checkout (clone-on-write on APFS), applies the workload's patch and the
 * lab's overlay, boots the sbt version under test on it, switches the Scala version and compiles once.
 */
@State(Scope.Benchmark)
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.SECONDS)
@Fork(value = 1, jvmArgsAppend = {"-Xms8G", "-Xmx8G", "-Xss4M"})
@Warmup(iterations = 10, time = 1)
@Measurement(iterations = 10, time = 1)
public class SbtCompileBenchmark {

    /** `stock`, or `typednil`: Pekko with typed-`Nil` shape templates (typed-nil.patch). */
    @Param({"stock"})
    public String workload;

    /** The sbt (and so Zinc) under test: 1.12.15 ships Zinc 1.12.1, 1.13.1 ships Zinc 1.13.0. */
    @Param({"1.12.15"})
    public String sbtVersion;

    /** The Scala that compiles the build: a release, or a locally published `2.13.19-bin-<sha>-SNAPSHOT`. */
    @Param({"2.13.18"})
    public String scalaVersion;

    private SbtHost sbt;
    private int ops;

    @Setup(Level.Trial)
    public void setup() throws Exception {
        Announce.jvm("SbtCompileBenchmark(" + workload + ", sbt " + sbtVersion + ", scala " + scalaVersion + ")");
        Path labOut = Paths.get(System.getProperty("zinclab.out", System.getenv().getOrDefault("ZINCLAB_OUT", "out"))).toAbsolutePath();
        Path pekko = Paths.get(System.getProperty("zinclab.pekko", System.getenv().getOrDefault("PEKKO_CHECKOUT", labOut.resolve("pekko").toString()))).toAbsolutePath();
        Path lab = Paths.get(System.getProperty("zinclab.dir", System.getenv().getOrDefault("ZINCLAB_DIR", "."))).toAbsolutePath().normalize();
        if (!Files.isDirectory(pekko.resolve("project"))) throw new IllegalStateException("no Pekko checkout at " + pekko + " (scripts/prepare-pekko.sh)");

        Path ws = labOut.resolve("ws").resolve("fork-" + ProcessHandle.current().pid());
        sh(labOut.toFile(), "rm", "-rf", labOut.resolve("ws").toString());
        Files.createDirectories(ws.getParent());
        // clone-on-write on APFS (cp -c); a plain copy elsewhere
        if (!tryRun(labOut.toFile(), "/bin/cp", "-cR", pekko.toString(), ws.toString())) sh(labOut.toFile(), "cp", "-R", pekko.toString(), ws.toString());
        Runtime.getRuntime().addShutdownHook(new Thread(() -> { try { sh(labOut.toFile(), "rm", "-rf", ws.toString()); } catch (Exception ignored) { } }));
        sh(labOut.toFile(), "cp", "-R", lab.resolve("overlay") + "/.", ws.toString());
        Files.writeString(ws.resolve("project/build.properties"), "sbt.version=" + sbtVersion + "\n");
        switch (workload) {
            case "stock": break;
            case "typednil": sh(ws.toFile(), "git", "apply", lab.resolve("typed-nil.patch").toString()); break;
            default: throw new IllegalArgumentException("workload=" + workload + ": expected stock or typednil");
        }

        System.out.printf("[zinc-lab] cores %d, sbt %s, scala %s, workload %s, workspace %s%n",
            Runtime.getRuntime().availableProcessors(), sbtVersion, scalaVersion, workload, ws);
        long t0 = System.nanoTime();
        sbt = SbtHost.start(ws.toFile(), 600_000);
        System.out.printf("[zinc-lab] sbt up in %.1f s%n", (System.nanoTime() - t0) / 1e9);
        // Pekko builds for JDK 8 unless told otherwise, and there is none; keep sbt's log quiet
        sbt.run("set every targetSystemJdk := true");
        sbt.run("set every logLevel := Level.Warn");
        sbt.run("++" + scalaVersion + "!");
        t0 = System.nanoTime();
        sbt.run("clean; compile");
        System.out.printf("[zinc-lab] first clean; compile %.1f s%n", (System.nanoTime() - t0) / 1e9);
    }

    @Benchmark
    public void cleanCompile() throws Exception {
        long t0 = System.nanoTime();
        sbt.run("clean; compile");
        System.out.printf("[zinc-lab] op %d: %.1f s%n", ++ops, (System.nanoTime() - t0) / 1e9);
    }

    private static boolean tryRun(File dir, String... cmd) throws Exception {
        return new ProcessBuilder(List.of(cmd)).directory(dir).inheritIO().start().waitFor() == 0;
    }

    private static void sh(File dir, String... cmd) throws Exception {
        if (!tryRun(dir, cmd)) throw new IllegalStateException("failed: " + String.join(" ", cmd));
    }
}
