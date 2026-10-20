package io.github.retronym.perflab.costs;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

class CostStackTest {
    static final CostKind PHASE = new CostKind("phase", CostKind.Phases.OWN, false);
    static final CostKind DEF = new CostKind("def", CostKind.Phases.NONE, false);
    static final CostKind IMPLICIT = new CostKind("implicit", CostKind.Phases.ENCLOSING, true);

    static final CostStack.Keys KEYS = new CostStack.Keys() {
        public String name(Object key) { return key.toString(); }
        public String label(Object key) { return key.toString(); }
        public String[] where(Object key) { return new String[]{"", "", ""}; }
        public String phaseName(Object phase) { return phase.toString(); }
    };

    static void spin(long ms) {
        long end = System.nanoTime() + ms * 1_000_000;
        while (System.nanoTime() < end) Thread.onSpinWait();
    }

    /** A completion of `b` inside `a`, behind a transparent (local) frame, is charged to `b`; an implicit search to `b`. */
    @Test
    void selfTimeExcludesNestedFramesThroughTransparentOnes() throws Exception {
        Path out = Files.createTempFile("costs", ".tsv");
        List<String> events = new ArrayList<>();
        CostStack s = new CostStack(List.of(PHASE, DEF, IMPLICIT), KEYS, out, new CostListener() {
            public void enter(CostStack.Frame f) { events.add("+" + f.label()); }
            public void exit(CostStack.Frame f) { events.add("-" + f.label()); }
        });
        s.enter(PHASE, "typer", "typer");
        s.enter(DEF, "a", null);
        spin(20);
        s.enter(DEF, null, null); // a local definition
        s.enter(DEF, "b", null);
        spin(40);
        s.enter(IMPLICIT, null, null);
        spin(10);
        s.exit(IMPLICIT);
        s.exit(DEF);
        s.exit(DEF);
        s.exit(DEF);
        s.exit(PHASE);
        s.finished();
        assertEquals(List.of("+typer", "+a", "+b", "+implicit", "-implicit", "-b", "-a", "-typer"), events);
        Map<String, String[]> rows = new HashMap<>();
        for (String l : Files.readAllLines(out).subList(1, 5)) { String[] c = l.split("\t", -1); rows.put(c[0] + " " + c[1] + " " + c[2], c); }
        assertEquals(Set.of("phase typer typer", "def  a", "def  b", "implicit typer b"), rows.keySet());
        long aSelf = Long.parseLong(rows.get("def  a")[7]), bSelf = Long.parseLong(rows.get("def  b")[7]), aTotal = Long.parseLong(rows.get("def  a")[8]);
        assertTrue(aSelf >= 20_000 && aSelf < 35_000, "a's self time excludes b's: " + aSelf);
        assertTrue(bSelf >= 40_000 && bSelf < 50_000, "b's self time excludes the implicit search: " + bSelf);
        assertTrue(aTotal >= 70_000, "a's total includes b's: " + aTotal);
        assertEquals(1, s.top() == null ? 1 : 0);
    }

    /** An exit unwinds frames whose exit was never reached. */
    @Test
    void exitUnwindsFramesLeftOpen() throws Exception {
        CostStack s = new CostStack(List.of(PHASE, DEF, IMPLICIT), KEYS, null, null);
        s.enter(PHASE, "typer", "typer");
        s.enter(DEF, "a", null);
        s.enter(IMPLICIT, null, null);
        s.exit(DEF);
        assertEquals("typer", s.top().key());
        s.exit(IMPLICIT); // nothing of that kind left: no-op
        assertEquals("typer", s.top().key());
    }
}
