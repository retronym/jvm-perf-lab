// Reads a .jfr for perflab (perflab.jfrevents), run as a single-file program: `java JfrEvents.java <mode> <file.jfr> ...`.
//
//   count <file.jfr> <event>...   how many of each event the recording has: {"counts": {event: n}}
//   promotion <file.jfr>          G1's promotion census: bytes promoted per class, to a survivor space or tenured, from
//                                 jdk.PromoteObjectInNewPLAB (one event per new PLAB: its plabSize stands for the bytes
//                                 promoted into it) and jdk.PromoteObjectOutsidePLAB (objectSize); and the survivor
//                                 space's bytes per age from jdk.TenuringDistribution, summed over GCs
//   jit <file.jfr>                the JIT's work from jdk.Compilation, jdk.Deoptimization and jdk.CompilerInlining: per
//                                 tier, per reason, and per method its compilations, deopts and its last C2 compile
//                                 (tier 4, OSR only if it had no other) with that compile's inlining decisions
//   precise <file.jfr> <thread regex>
//                                 per profiler.HardwareSample event (async-profiler's kperf samples) on the matching
//                                 threads: samples and value, and how many of them have a precise PC (the PMU's own,
//                                 so the leaf's line or bci is the instruction that counted): {"events": {event:
//                                 {"samples", "precise", "value", "preciseValue"}}}
//
// JSON on stdout. Events are streamed, so a large recording is never held in memory.
import java.nio.file.Path;
import java.util.*;
import jdk.jfr.consumer.*;

public class JfrEvents {
    static void precise(Path file, java.util.regex.Pattern threads, StringBuilder out) throws Exception {
        Map<String, long[]> byEvent = new TreeMap<>();  // event -> [samples, precise, value, precise value]
        try (RecordingFile rf = new RecordingFile(file)) {
            while (rf.hasMoreEvents()) {
                RecordedEvent e = rf.readEvent();
                if (!e.getEventType().getName().equals("profiler.HardwareSample")) continue;
                RecordedThread t = e.getThread("sampledThread");
                String tn = t == null ? null : t.getJavaName() != null ? t.getJavaName() : t.getOSName();
                if (tn == null || !threads.matcher(tn).find()) continue;
                long[] row = byEvent.computeIfAbsent(e.getString("event"), k -> new long[4]);
                long v = e.getLong("value");
                boolean p = e.getBoolean("precise");
                row[0] += 1;
                row[2] += v;
                if (p) {
                    row[1] += 1;
                    row[3] += v;
                }
            }
        }
        out.append("{\"events\": {");
        int i = 0;
        for (Map.Entry<String, long[]> en : byEvent.entrySet()) {
            long[] r = en.getValue();
            out.append(i++ == 0 ? "" : ", ").append(str(en.getKey())).append(": {\"samples\": ").append(r[0])
               .append(", \"precise\": ").append(r[1]).append(", \"value\": ").append(r[2])
               .append(", \"preciseValue\": ").append(r[3]).append("}");
        }
        out.append("}}");
    }

    public static void main(String[] args) throws Exception {
        String mode = args[0];
        Path file = Path.of(args[1]);
        StringBuilder out = new StringBuilder();
        if (mode.equals("count")) {
            Map<String, Long> counts = new TreeMap<>();
            for (int i = 2; i < args.length; i++) counts.put(args[i], 0L);
            try (RecordingFile rf = new RecordingFile(file)) {
                while (rf.hasMoreEvents()) {
                    String name = rf.readEvent().getEventType().getName();
                    counts.computeIfPresent(name, (k, n) -> n + 1);
                }
            }
            out.append("{\"counts\": ").append(map(counts)).append("}");
        } else if (mode.equals("promotion")) {
            // class -> [survivor bytes, tenured bytes, survivor events, tenured events]
            Map<String, long[]> byClass = new HashMap<>();
            Map<String, Long> events = new TreeMap<>();
            Map<Long, Long> ages = new TreeMap<>();
            Set<Long> gcs = new HashSet<>();
            try (RecordingFile rf = new RecordingFile(file)) {
                while (rf.hasMoreEvents()) {
                    RecordedEvent e = rf.readEvent();
                    String name = e.getEventType().getName();
                    boolean inPlab = name.equals("jdk.PromoteObjectInNewPLAB");
                    if (inPlab || name.equals("jdk.PromoteObjectOutsidePLAB")) {
                        events.merge(name, 1L, Long::sum);
                        RecordedClass c = e.getClass("objectClass");
                        String cls = c == null ? "?" : javaName(c.getName());
                        long bytes = inPlab ? e.getLong("plabSize") : e.getLong("objectSize");
                        int t = e.getBoolean("tenured") ? 1 : 0;
                        long[] row = byClass.computeIfAbsent(cls, k -> new long[4]);
                        row[t] += bytes;
                        row[2 + t] += 1;
                        if (e.hasField("gcId")) gcs.add((long) e.getInt("gcId"));
                    } else if (name.equals("jdk.TenuringDistribution")) {
                        events.merge(name, 1L, Long::sum);
                        ages.merge(e.getLong("age"), e.getLong("size"), Long::sum);
                    }
                }
            }
            out.append("{\"events\": ").append(map(events)).append(", \"gcs\": ").append(gcs.size()).append(", \"classes\": [");
            List<Map.Entry<String, long[]>> rows = new ArrayList<>(byClass.entrySet());
            rows.sort((a, b) -> Long.compare(b.getValue()[0] + b.getValue()[1], a.getValue()[0] + a.getValue()[1]));
            for (int i = 0; i < rows.size(); i++) {
                long[] r = rows.get(i).getValue();
                out.append(i == 0 ? "" : ", ").append("{\"class\": ").append(str(rows.get(i).getKey()))
                   .append(", \"survivorBytes\": ").append(r[0]).append(", \"tenuredBytes\": ").append(r[1])
                   .append(", \"survivorEvents\": ").append(r[2]).append(", \"tenuredEvents\": ").append(r[3]).append("}");
            }
            out.append("], \"tenuringDistribution\": {");
            int i = 0;
            for (Map.Entry<Long, Long> a : ages.entrySet()) {
                out.append(i++ == 0 ? "" : ", ").append("\"").append(a.getKey()).append("\": ").append(a.getValue());
            }
            out.append("}}");
        } else if (mode.equals("jit")) {
            jit(file, out);
        } else if (mode.equals("precise")) {
            precise(file, java.util.regex.Pattern.compile(args[2]), out);
        } else {
            throw new IllegalArgumentException("mode: count, promotion, jit or precise, not " + mode);
        }
        System.out.println(out);
    }

    static final class Compile {
        long id, codeSize, inlinedBytes; int level; boolean osr, ok; double ms;
    }

    static final class Method {
        final List<Compile> compiles = new ArrayList<>();
        final Map<String, Long> deoptReasons = new TreeMap<>();
        long deopts;
        Compile c2() {  // the last tier 4 compile that succeeded, not OSR unless all were
            Compile best = null;
            for (Compile c : compiles)
                if (c.level == 4 && c.ok && (best == null || best.osr || !c.osr)) best = c;
            return best;
        }
    }

    // per decision (caller -> callee): [inlined, not inlined], and the messages
    static final class Decision {
        long inlined, notInlined; final Map<String, Long> messages = new TreeMap<>();
    }

    static void jit(Path file, StringBuilder out) throws Exception {
        Map<String, Long> events = new TreeMap<>();
        Map<String, Method> methods = new HashMap<>();
        // tier -> [compilations, osr, failed, code bytes, inlined bytes], compile ms
        Map<Integer, long[]> tiers = new TreeMap<>();
        Map<Integer, Double> tierMs = new TreeMap<>();
        Map<String, Long> deoptReasons = new TreeMap<>(), deoptActions = new TreeMap<>();
        Map<Long, Map<String, Decision>> inlining = new HashMap<>();  // compileId -> decisions (C2 threads only)
        Map<String, String> names = new HashMap<>();
        try (RecordingFile rf = new RecordingFile(file)) {
            while (rf.hasMoreEvents()) {
                RecordedEvent e = rf.readEvent();
                String name = e.getEventType().getName();
                switch (name) {
                    case "jdk.Compilation" -> {
                        events.merge(name, 1L, Long::sum);
                        Compile c = new Compile();
                        c.id = e.getLong("compileId");
                        c.level = e.getInt("compileLevel");
                        c.osr = e.getBoolean("isOsr");
                        c.ok = e.getBoolean("succeded");
                        c.codeSize = e.getLong("codeSize");
                        c.inlinedBytes = e.getLong("inlinedBytes");
                        c.ms = e.getDuration().toNanos() / 1e6;
                        methods.computeIfAbsent(method(e.getValue("method"), names), k -> new Method()).compiles.add(c);
                        long[] t = tiers.computeIfAbsent(c.level, k -> new long[5]);
                        t[0]++; t[1] += c.osr ? 1 : 0; t[2] += c.ok ? 0 : 1; t[3] += c.codeSize; t[4] += c.inlinedBytes;
                        tierMs.merge(c.level, c.ms, Double::sum);
                    }
                    case "jdk.Deoptimization" -> {
                        events.merge(name, 1L, Long::sum);
                        String reason = e.getString("reason");
                        deoptReasons.merge(reason, 1L, Long::sum);
                        deoptActions.merge(e.getString("action"), 1L, Long::sum);
                        Method m = methods.computeIfAbsent(method(e.getValue("method"), names), k -> new Method());
                        m.deopts++;
                        m.deoptReasons.merge(reason, 1L, Long::sum);
                    }
                    case "jdk.CompilerInlining" -> {
                        events.merge(name, 1L, Long::sum);
                        RecordedThread t = e.getThread();
                        if (t != null && t.getJavaName() != null && t.getJavaName().startsWith("C1")) break;
                        RecordedObject callee = e.getValue("callee");
                        String to = names.computeIfAbsent(javaName(callee.getString("type").replace('/', '.')) + "." + callee.getString("name")
                                                          + callee.getString("descriptor"), k -> k);
                        String key = method(e.getValue("caller"), names) + " -> " + to;
                        Decision d = inlining.computeIfAbsent(e.getLong("compileId"), k -> new HashMap<>()).computeIfAbsent(key, k -> new Decision());
                        if (e.getBoolean("succeeded")) d.inlined++; else d.notInlined++;
                        String msg = e.getString("message");
                        if (msg != null) d.messages.merge(names.computeIfAbsent(msg, k -> k), 1L, Long::sum);
                    }
                    case "jdk.CompilationFailure", "jdk.CodeCacheFull", "jdk.DataLoss" -> events.merge(name, 1L, Long::sum);
                    default -> { }
                }
            }
        }
        out.append("{\"events\": ").append(map(events)).append(", \"tiers\": {");
        int i = 0;
        for (Map.Entry<Integer, long[]> t : tiers.entrySet()) {
            long[] v = t.getValue();
            out.append(i++ == 0 ? "" : ", ").append("\"").append(t.getKey()).append("\": {\"compilations\": ").append(v[0])
               .append(", \"osr\": ").append(v[1]).append(", \"failed\": ").append(v[2]).append(", \"codeBytes\": ").append(v[3])
               .append(", \"inlinedBytes\": ").append(v[4]).append(", \"compileMs\": ").append(String.format("%.3f", tierMs.get(t.getKey()))).append("}");
        }
        out.append("}, \"deopts\": {\"byReason\": ").append(map(deoptReasons)).append(", \"byAction\": ").append(map(deoptActions))
           .append("}, \"methods\": [");
        List<Map.Entry<String, Method>> rows = new ArrayList<>(methods.entrySet());
        rows.sort(Map.Entry.comparingByKey());
        i = 0;
        for (Map.Entry<String, Method> r : rows) {
            Method m = r.getValue();
            Map<String, Long> levels = new TreeMap<>();
            long osr = 0, maxCode = 0;
            for (Compile c : m.compiles) {
                levels.merge(String.valueOf(c.level), 1L, Long::sum);
                osr += c.osr ? 1 : 0;
                maxCode = Math.max(maxCode, c.codeSize);
            }
            out.append(i++ == 0 ? "" : ", ").append("{\"method\": ").append(str(r.getKey())).append(", \"compilations\": ").append(m.compiles.size())
               .append(", \"levels\": ").append(map(levels)).append(", \"osr\": ").append(osr).append(", \"maxCodeSize\": ").append(maxCode)
               .append(", \"deopts\": ").append(m.deopts).append(", \"deoptReasons\": ").append(map(m.deoptReasons)).append(", \"c2\": ");
            Compile c = m.c2();
            if (c == null) {
                out.append("null");
            } else {
                out.append("{\"compileId\": ").append(c.id).append(", \"osr\": ").append(c.osr).append(", \"codeSize\": ").append(c.codeSize)
                   .append(", \"inlinedBytes\": ").append(c.inlinedBytes).append(", \"compileMs\": ").append(String.format("%.3f", c.ms))
                   .append(", \"inlining\": [");
                Map<String, Decision> ds = inlining.getOrDefault(c.id, Map.of());
                List<String> keys = new ArrayList<>(ds.keySet());
                Collections.sort(keys);
                int j = 0;
                for (String k : keys) {
                    Decision d = ds.get(k);
                    int arrow = k.indexOf(" -> ");
                    out.append(j++ == 0 ? "" : ", ").append("{\"caller\": ").append(str(k.substring(0, arrow))).append(", \"callee\": ")
                       .append(str(k.substring(arrow + 4))).append(", \"inlined\": ").append(d.inlined).append(", \"notInlined\": ")
                       .append(d.notInlined).append(", \"messages\": ").append(map(d.messages)).append("}");
                }
                out.append("]}");
            }
            out.append("}");
        }
        out.append("]}");
    }

    // `pkg.Class.name(descriptor)`, a hidden class without its address
    static String method(RecordedMethod m, Map<String, String> names) {
        if (m == null) return "?";
        return names.computeIfAbsent(javaName(m.getType().getName()) + "." + m.getName() + m.getDescriptor(), k -> k);
    }

    // `[Ljava.lang.Object;` as `java.lang.Object[]`, `[B` as `byte[]`; a hidden class without its address in this JVM
    static String javaName(String n) {
        int dims = 0;
        while (dims < n.length() && n.charAt(dims) == '[') dims++;
        String base = n.substring(dims);
        if (dims > 0) {
            switch (base) {
                case "Z": base = "boolean"; break;
                case "B": base = "byte"; break;
                case "C": base = "char"; break;
                case "S": base = "short"; break;
                case "I": base = "int"; break;
                case "J": base = "long"; break;
                case "F": base = "float"; break;
                case "D": base = "double"; break;
                default: base = base.startsWith("L") && base.endsWith(";") ? base.substring(1, base.length() - 1) : base;
            }
        }
        return base.replaceAll("[./]0x[0-9a-f]+$", "") + "[]".repeat(dims);
    }

    static String map(Map<String, Long> m) {
        StringBuilder b = new StringBuilder("{");
        for (Map.Entry<String, Long> e : m.entrySet()) {
            b.append(b.length() == 1 ? "" : ", ").append(str(e.getKey())).append(": ").append(e.getValue());
        }
        return b.append("}").toString();
    }

    static String str(String s) {
        StringBuilder b = new StringBuilder("\"");
        for (char ch : s.toCharArray()) {
            if (ch == '"' || ch == '\\') b.append('\\').append(ch);
            else if (ch < 0x20) b.append(String.format("\\u%04x", (int) ch));
            else b.append(ch);
        }
        return b.append("\"").toString();
    }
}
