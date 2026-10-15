package io.github.retronym.perflab.xctrace;

import io.github.retronym.perflab.jmh.IterationLog;
import org.junit.jupiter.api.Test;

import java.io.*;
import java.nio.file.*;
import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

class XctraceProfilerTest {
    @Test
    void threadNamesFoldIdsAndNumbers() {
        assertEquals("Thread-N", XctraceProfiler.threadName("Thread-123 (0x1a2b) (pid: 4242)"));
        assertEquals("GC Thread#N", XctraceProfiler.threadName("GC Thread#3 (0x10)"));
        assertEquals("bench", XctraceProfiler.group("org.Foo.bar-jmh-worker-1 (0xabc)"));
        assertEquals("jit", XctraceProfiler.group("C2 CompilerThread0"));
        assertEquals("gc", XctraceProfiler.group("GC Thread#2"));
        assertEquals("other", XctraceProfiler.group("Thread-7"));
    }

    @Test
    void samplesFallInTheIterationWhoseSpanHoldsThem() {
        List<IterationLog.Entry> measured = List.of(
            new IterationLog.Entry(4, "a", true, 1000, 1999, 0),
            new IterationLog.Entry(5, "b", true, 2005, 3000, 0));
        assertEquals(4, XctraceProfiler.iterationAt(measured, 1000).index());
        assertEquals(4, XctraceProfiler.iterationAt(measured, 1999).index());
        assertNull(XctraceProfiler.iterationAt(measured, 2002), "between iterations");
        assertEquals(5, XctraceProfiler.iterationAt(measured, 2500).index());
        assertNull(XctraceProfiler.iterationAt(measured, 999));
    }

    @Test
    void charactersXmlForbidsAreReplaced() throws Exception {
        Path f = Files.createTempFile("export", ".xml");
        Files.writeString(f, "<trace><row><frame name=\"__block_descriptor_e5_v8\u0001?0l\"/><x>7</x></row></trace>");
        List<Map<String, String[]>> rows = new ArrayList<>();
        XctraceProfiler.rows(f, rows::add);
        assertEquals(1, rows.size());
        assertEquals("7", rows.get(0).get("x")[1]);
    }

    @Test
    void bundledTemplatesAreCopiedOutOfTheJar() throws Exception {
        String ipc = XctraceProfiler.bundled("ipc");
        assertTrue(ipc.endsWith(".template.xml") && Files.size(Path.of(ipc)) > 1000, ipc);
        assertEquals("CPU Counters", XctraceProfiler.bundled("CPU Counters"));
    }
}
