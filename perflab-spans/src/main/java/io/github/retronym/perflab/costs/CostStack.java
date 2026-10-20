package io.github.retronym.perflab.costs;

import java.io.IOException;
import java.lang.management.ManagementFactory;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/**
 * Exclusive cost per key (a definition, a compilation unit, a phase): a stack of frames kept in step with a program's
 * hooks, each frame charged its self time and allocation, i.e. its own minus that of the frames nested in it. If
 * typing `a` completes `b`, `b`'s completion is a frame of its own, and charged to `b`.
 *
 * Every {@link #enter} is matched by an {@link #exit}. A null key enters a transparent frame: no clocks, no row, no
 * listener call, and the time of frames nested in it passes to its parent; so an untracked operation (a local
 * definition) is part of what encloses it, and exits need no key. Only the thread that created the stack is measured.
 *
 * Two consumers: a table (`path`, written by {@link #finished}) in the format `perflab defcosts` reads, and a
 * {@link CostListener}. Clocks and accumulators are kept only for the table.
 */
public final class CostStack {
    /** How a program names its keys, for the table and for spans. */
    public interface Keys {
        /** The row's name: a symbol's full name, a source path, a phase's name */
        String name(Object key);
        /** A frame's short label, for spans: the unqualified name of a symbol */
        String label(Object key);
        /** {file, line, chars}, each possibly empty */
        String[] where(Object key);
        String phaseName(Object phase);
    }

    /** A region on the stack, reused once left. */
    public final class Frame {
        CostKind kind;
        Object key, phase;
        Frame parent;
        boolean transparent;
        Acc acc;
        long startNs, startAlloc, childNs, childAlloc;
        /** For a listener's own use, e.g. when the frame's span started */
        public long listenerData;

        public CostKind kind() { return kind; }
        /** The key, the innermost frame's for a kind that inherits it */
        public Object key() { return key; }
        public Object phase() { return phase; }
        public Frame parent() { return parent; }

        /** A short name: the kind's label for kinds that inherit their key, else the key's label */
        public String label() { return kind.inheritsKey ? kind.label : key == null ? "<outside a definition>" : keys.label(key); }
    }

    static final class Acc {
        final CostKind kind;
        final Object key, phase;
        int calls;
        long selfNs, selfAlloc, totalNs, maxSelfNs;

        Acc(CostKind kind, Object key, Object phase) { this.kind = kind; this.key = key; this.phase = phase; }
    }

    private static final com.sun.management.ThreadMXBean THREADS = (com.sun.management.ThreadMXBean) ManagementFactory.getThreadMXBean();

    private final Thread thread = Thread.currentThread();
    private final Keys keys;
    private final CostListener listener;
    private final Path path;
    private final List<CostKind> kinds;
    // per kind, per phase (null for kinds not per phase), per key
    private final List<IdentityHashMap<Object, IdentityHashMap<Object, Acc>>> accs;
    private Frame[] pool = new Frame[64];
    private int depth;
    private Frame top;
    private long entered;

    /** @param path the table, or null; @param listener or null */
    public CostStack(List<CostKind> kinds, Keys keys, Path path, CostListener listener) {
        this.kinds = List.copyOf(kinds);
        for (int i = 0; i < kinds.size(); i++) kinds.get(i).ordinal = i;
        this.keys = keys;
        this.path = path;
        this.listener = listener;
        if (path == null) accs = null;
        else {
            accs = new ArrayList<>();
            for (int i = 0; i < kinds.size(); i++) accs.add(new IdentityHashMap<>());
        }
    }

    /** Creates a listener by class name, from `loader`. */
    public static CostListener listener(String className, ClassLoader loader) throws ReflectiveOperationException {
        return (CostListener) Class.forName(className, true, loader).getDeclaredConstructor().newInstance();
    }

    /** Frames entered (other than transparent ones), e.g. to check the hooks are woven at all. */
    public long entered() { return entered; }

    /** The innermost frame that is not transparent, or null. */
    public Frame top() {
        Frame f = top;
        while (f != null && f.transparent) f = f.parent;
        return f;
    }

    /**
     * Enters a frame of `kind` for `key`, or a transparent frame if `key` is null (unless the kind inherits its key).
     * `phase` is the frame's phase for {@link CostKind.Phases#OWN} kinds, the fallback for
     * {@link CostKind.Phases#ENCLOSING} ones, and ignored otherwise.
     */
    public void enter(CostKind kind, Object key, Object phase) {
        if (Thread.currentThread() != thread) return;
        if (depth == pool.length) pool = Arrays.copyOf(pool, depth * 2);
        Frame f = pool[depth];
        if (f == null) pool[depth] = f = new Frame();
        f.kind = kind;
        f.parent = top;
        f.childNs = 0;
        f.childAlloc = 0;
        f.listenerData = 0;
        f.acc = null;
        if (kind.inheritsKey) {
            Frame t = top();
            key = t == null ? null : t.key;
        } else if (key == null) {
            f.transparent = true;
            f.key = null;
            depth++;
            top = f;
            return;
        }
        f.transparent = false;
        f.key = key;
        f.phase = switch (kind.phases) {
            case NONE -> null;
            case OWN -> phase;
            case ENCLOSING -> enclosingPhase(phase);
        };
        if (accs != null) {
            f.acc = acc(kind, key, f.phase);
            f.startNs = System.nanoTime();
            f.startAlloc = THREADS.getCurrentThreadAllocatedBytes();
        }
        depth++;
        top = f;
        entered++;
        if (listener != null) {
            boolean ok = false;
            try {
                listener.enter(f);
                ok = true;
            } finally {
                if (!ok) pop(); // the caller's exit never sees this frame
            }
        }
    }

    /**
     * Leaves the innermost frame of `kind`, and any frames entered inside it that were never left (a hook whose exit
     * was not reached). Does nothing if no frame of that kind is on the stack.
     */
    public void exit(CostKind kind) {
        if (Thread.currentThread() != thread) return;
        Frame f = top;
        while (f != null && f.kind != kind) f = f.parent;
        if (f == null) return;
        while (top != f) exitTop();
        exitTop();
    }

    /** Leaves the innermost frame, transparent or not: the exit of a hook around a method. */
    public void exit() {
        if (Thread.currentThread() != thread || top == null) return;
        exitTop();
    }

    private Object enclosingPhase(Object fallback) {
        for (Frame f = top; f != null; f = f.parent)
            if (!f.transparent && f.kind.phases == CostKind.Phases.OWN) return f.phase;
        return fallback;
    }

    private Acc acc(CostKind kind, Object key, Object phase) {
        IdentityHashMap<Object, Acc> byKey = accs.get(kind.ordinal).computeIfAbsent(phase, p -> new IdentityHashMap<>());
        Acc a = byKey.get(key);
        if (a == null) byKey.put(key, a = new Acc(kind, key, phase));
        return a;
    }

    private Frame pop() {
        Frame f = top;
        top = f.parent;
        depth--;
        return f;
    }

    private void exitTop() {
        Frame f = pop();
        Frame parent = f.parent;
        if (f.transparent) {
            if (parent != null) {
                parent.childNs += f.childNs;
                parent.childAlloc += f.childAlloc;
            }
            return;
        }
        Acc a = f.acc;
        if (a != null) {
            long total = System.nanoTime() - f.startNs;
            long alloc = THREADS.getCurrentThreadAllocatedBytes() - f.startAlloc;
            long self = total - f.childNs;
            a.calls++;
            a.selfNs += self;
            a.selfAlloc += alloc - f.childAlloc;
            a.totalNs += total;
            if (self > a.maxSelfNs) a.maxSelfNs = self;
            if (parent != null) {
                parent.childNs += total;
                parent.childAlloc += alloc;
            }
        }
        if (listener != null) listener.exit(f);
    }

    /** Tells the listener, and writes the table if there is one. */
    public void finished() throws IOException {
        if (listener != null) listener.finished();
        if (path != null) write(path);
    }

    /**
     * One row per kind, phase and key, tab-separated, sorted by kind, phase and name: kind, phase (empty for kinds not
     * per phase), name, file, line, chars (the definition's size), calls, self and total time in µs, the longest
     * single self time in µs, and self allocation in bytes.
     */
    public void write(Path out) throws IOException {
        record Row(int kind, String phase, String name, Acc acc) {}
        List<Row> rows = new ArrayList<>();
        for (IdentityHashMap<Object, IdentityHashMap<Object, Acc>> byPhase : accs)
            for (IdentityHashMap<Object, Acc> byKey : byPhase.values())
                for (Acc a : byKey.values())
                    rows.add(new Row(a.kind.ordinal, a.phase == null ? "" : keys.phaseName(a.phase), a.key == null ? "<outside a definition>" : keys.name(a.key), a));
        rows.sort(Comparator.comparingInt(Row::kind).thenComparing(Row::phase).thenComparing(Row::name));
        StringBuilder sb = new StringBuilder("kind\tphase\tsymbol\tfile\tline\tchars\tcalls\tself_us\ttotal_us\tmax_self_us\tself_alloc\n");
        for (Row r : rows) {
            Acc a = r.acc;
            String[] w = a.key == null ? new String[]{"", "", ""} : keys.where(a.key);
            sb.append(a.kind.label).append('\t').append(r.phase).append('\t').append(r.name).append('\t')
              .append(w[0]).append('\t').append(w[1]).append('\t').append(w[2]).append('\t').append(a.calls).append('\t')
              .append(a.selfNs / 1000).append('\t').append(a.totalNs / 1000).append('\t').append(a.maxSelfNs / 1000)
              .append('\t').append(a.selfAlloc).append('\n');
        }
        Files.write(out, sb.toString().getBytes(StandardCharsets.UTF_8));
    }
}
