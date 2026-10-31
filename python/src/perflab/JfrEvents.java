// Reads a .jfr for perflab (perflab.jfrevents), run as a single-file program: `java JfrEvents.java <mode> <file.jfr> ...`.
//
//   count <file.jfr> <event>...   how many of each event the recording has: {"counts": {event: n}}
//   promotion <file.jfr>          G1's promotion census: bytes promoted per class, to a survivor space or tenured, from
//                                 jdk.PromoteObjectInNewPLAB (one event per new PLAB: its plabSize stands for the bytes
//                                 promoted into it) and jdk.PromoteObjectOutsidePLAB (objectSize); and the survivor
//                                 space's bytes per age from jdk.TenuringDistribution, summed over GCs
//
// JSON on stdout. Events are streamed, so a large recording is never held in memory.
import java.nio.file.Path;
import java.util.*;
import jdk.jfr.consumer.*;

public class JfrEvents {
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
        } else {
            throw new IllegalArgumentException("mode: count or promotion, not " + mode);
        }
        System.out.println(out);
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
        return base.replaceAll("\\.0x[0-9a-f]+$", "") + "[]".repeat(dims);
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
