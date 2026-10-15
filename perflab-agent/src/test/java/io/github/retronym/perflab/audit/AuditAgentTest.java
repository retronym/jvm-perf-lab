package io.github.retronym.perflab.audit;

import org.junit.jupiter.api.Test;

import java.io.InputStream;
import java.nio.file.*;
import java.util.*;

import static org.junit.jupiter.api.Assertions.*;

class AuditAgentTest {
    public static class Fixture {
        public int target(int x) { return x + 1; }
        public int viaA() { return target(1); }
        public int viaB() { return target(2); }
    }

    @Test
    void specLinesParse() throws Exception {
        Path f = Files.createTempFile("x", ".audit");
        Files.write(f, List.of("# comment",
            "count c at=a.B#m from=a.C#n onStack=x:a.X,y:a.Y  # trailing",
            "tag t at=a.B#<init> exit when=a.P#p depth=6 skip=^a\\.B\\.",
            "sites s at=a.B#m(I depth=2 qualify=class,tag sample=10"));
        Spec s = Spec.read(f);
        assertEquals(3, s.lines().size());
        Spec.Line c = s.lines().get(0);
        assertEquals(Spec.Kind.COUNT, c.kind());
        assertEquals("a.C#n", c.from());
        assertEquals(List.of("x", "y"), List.copyOf(c.onStack().keySet()));
        assertTrue(s.lines().get(1).exit());
        assertEquals("(I", s.lines().get(2).descPrefix());
        assertEquals(10, s.lines().get(2).sample());
        Files.write(f, List.of("tag t at=a.B#<init>"));
        assertThrows(IllegalArgumentException.class, () -> Spec.read(f), "a constructor probe needs exit");
    }

    /** Weave a count probe into Fixture#target, called only from viaA, and run the woven class. */
    @Test
    void wovenProbeCountsCallsFromItsCaller() throws Exception {
        String owner = Fixture.class.getName();
        Path spec = Files.createTempFile("x", ".audit");
        Files.write(spec, List.of("count fromA at=" + owner + "#target from=" + owner + "#viaA"));
        int id = Audit.register(Spec.read(spec).lines().get(0));
        byte[] bytes;
        try (InputStream in = Fixture.class.getResourceAsStream("AuditAgentTest$Fixture.class")) { bytes = in.readAllBytes(); }
        Set<String> woven = new TreeSet<>();
        byte[] w = AuditAgent.weave(bytes, List.of(id), woven);
        assertEquals(Set.of("fromA target(I)I"), woven);
        Class<?> c = new ClassLoader(getClass().getClassLoader()) {
            Class<?> define() { return defineClass(owner, w, 0, w.length); }
        }.define();
        Object o = c.getConstructor().newInstance();
        for (int i = 0; i < 3; i++) c.getMethod("viaA").invoke(o);
        c.getMethod("viaB").invoke(o);
        assertEquals(3, Audit.counter("fromA"));
    }
}
