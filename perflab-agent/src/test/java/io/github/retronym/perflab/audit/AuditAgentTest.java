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

    public static class HookFixture {
        public long target(String s, long n, int[] xs) {
            if (s == null) throw new IllegalStateException("boom");
            try { Integer.parseInt(s); } catch (NumberFormatException e) { n += 100; } // the method's own handler wins
            return n + xs.length;
        }
    }

    public static class Hooks {
        static final List<String> events = new ArrayList<>();
        public static void enter(Object self, Object s, long n, Object xs) { events.add("enter " + s + " " + n + " " + ((int[]) xs).length + " " + (self != null)); }
        public static void exit() { events.add("exit"); }
    }

    /** Weave a hook with an exit into HookFixture#target: entry gets the receiver and arguments, exit runs on return and throw. */
    @Test
    void hookCallsEnterAndExitOnReturnAndThrow() throws Exception {
        String owner = HookFixture.class.getName(), self = Hooks.class.getName();
        Path spec = Files.createTempFile("x", ".audit");
        Files.write(spec, List.of("hook h at=" + owner + "#target call=" + self + "#enter exit=" + self + "#exit"));
        int id = Audit.register(Spec.read(spec).lines().get(0));
        byte[] bytes;
        try (InputStream in = HookFixture.class.getResourceAsStream("AuditAgentTest$HookFixture.class")) { bytes = in.readAllBytes(); }
        byte[] w = AuditAgent.weave(bytes, List.of(id), new TreeSet<>());
        Class<?> c = new ClassLoader(getClass().getClassLoader()) {
            Class<?> define() { return defineClass(owner, w, 0, w.length); }
        }.define();
        Object o = c.getConstructor().newInstance();
        var m = c.getMethod("target", String.class, long.class, int[].class);
        Hooks.events.clear();
        assertEquals(3L, m.invoke(o, "1", 1L, new int[2]));
        assertEquals(102L, m.invoke(o, "x", 1L, new int[1]));
        var ex = assertThrows(java.lang.reflect.InvocationTargetException.class, () -> m.invoke(o, null, 5L, new int[0]));
        assertEquals("boom", ex.getCause().getMessage());
        assertEquals(List.of("enter 1 1 2 true", "exit", "enter x 1 1 true", "exit", "enter null 5 0 true", "exit"), Hooks.events);
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
