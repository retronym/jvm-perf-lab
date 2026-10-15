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
}
