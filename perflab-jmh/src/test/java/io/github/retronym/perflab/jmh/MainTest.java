package io.github.retronym.perflab.jmh;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.*;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class MainTest {
    @Test
    void argumentFilesExpandOneArgumentPerLine(@TempDir Path dir) throws Exception {
        Path f = dir.resolve("prof.args");
        Files.write(f, List.of("# async-profiler, as sbt would never let us type it", "-prof",
            "async:output=jfr;dir=out dir;event=cpu", "", "-p", "variants=a=-Ya -Yb|b="));
        assertEquals(List.of("-wi", "1", "-prof", "async:output=jfr;dir=out dir;event=cpu", "-p", "variants=a=-Ya -Yb|b=", "Bench"),
            Main.arguments(List.of("-wi", "1", "@" + f, "Bench")));
    }

    @Test
    void ampersandSeparatesProfilerOptions() throws Exception {
        assertEquals(List.of("-prof", "async:output=jfr;dir=out", "-p", "x=a&b"),
            Main.arguments(List.of("-prof", "async:output=jfr&dir=out", "-p", "x=a&b")));
    }

    @Test
    void trialIdMatchesJmhsDirectoryName() {
        // the directory JMH 1.37's AsyncProfiler created for a scala3 lab run
        var params = new java.util.TreeMap<>(java.util.Map.of("compiler", "fresh", "corpus", "/Users/u/rcg/wide-k200-m10-c1",
            "gcBetweenIterations", "false", "scalacOptions", "-Yrefchecks-members:several", "variants", ""));
        assertEquals("dotty.tools.compilerlab.CompileBenchmark.compile-AverageTime-compiler-fresh-corpus-_2FUsers_2Fu_2Frcg_2Fwide-k200-m10-c1"
                + "-gcBetweenIterations-false-scalacOptions--Yrefchecks-members_3Aseveral-variants-",
            TrialNames.id("dotty.tools.compilerlab.CompileBenchmark.compile", org.openjdk.jmh.annotations.Mode.AverageTime, params));
    }
}
