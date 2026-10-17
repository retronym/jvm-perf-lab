package io.github.retronym.perflab.jmh;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class IterationLogTest {
    @Test
    void anIterationCountsTheBytesAllocatedDuringIt() {
        IterationLog.reset(List.of("a", "b"));
        IterationLog.begin("a", true);
        byte[][] garbage = new byte[64][];
        for (int i = 0; i < garbage.length; i++) garbage[i] = new byte[16 * 1024];
        IterationLog.end();
        IterationLog.Entry e = IterationLog.last();
        assertEquals("a", e.variant());
        assertTrue(e.allocBytes() >= 64 * 16 * 1024, "allocated " + e.allocBytes() + " for " + garbage.length + " arrays");
    }
}
