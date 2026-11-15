package io.github.retronym.perflab.xctrace;

import java.nio.file.Path;
import java.util.*;

/**
 * Re-attributes an existing trace's counters-profile export, to compare the labelled attribution with time on core ×
 * rate: {@code Reattribute <export.xml> <pid> <ops> [periodUs]}. Prints, per thread group of that pid, instructions
 * and cycles per op both ways, and the benchmark's time share and clock per core class.
 */
public class Reattribute {
    public static void main(String[] args) throws Exception {
        Path xml = Path.of(args[0]);
        String self = "pid: " + args[1] + ")";
        double ops = Double.parseDouble(args[2]);
        long periodNs = (args.length > 3 ? Long.parseLong(args[3]) : 1000) * 1000;
        int ins = 0, cyc = 2;   // the ipc template: INST_ALL, INST_BRANCH, CORE_ACTIVE_CYCLE, BRANCH_MISPRED_NONSPEC
        TickAttribution ta = new TickAttribution(4, periodNs);
        Set<String> groups = new TreeSet<>();
        XctraceProfiler.rows(xml, row -> {
            String[] t = row.get("thread"), m = row.get("pmc-events"), core = row.get("core"), st = row.get("sample-time");
            if (t == null || m == null || m[1] == null || t[0] == null || core == null || st == null || st[1] == null) return;
            String[] xs = m[1].trim().split("\\s+");
            if (xs.length != 4) return;
            long[] d = new long[4];
            for (int i = 0; i < 4; i++) d[i] = Long.parseLong(xs[i]);
            List<String> b = new ArrayList<>();
            if (t[0].contains(self)) {
                String g = XctraceProfiler.group(t[0]);
                if (t[0].contains("CompileBenchmark")) g = "bench";
                groups.add(g);
                b.add(g);
            }
            ta.sample(Long.parseLong(st[1].trim()), core[1] == null ? core[0] : core[1].trim(), core[0], t[0], d, b);
        });
        ta.finish();
        System.out.println("group  inst/op(labelled)  inst/op(time x rate)  ratio  cyc/op(labelled)  cyc/op(time x rate)");
        for (String g : groups) {
            long[] l = ta.labelled(g), e = ta.estimate(g);
            System.out.printf("%-6s %10.3fG %10.3fG %6.3f %10.3fG %10.3fG%n", g, l[ins] / ops / 1e9, e[ins] / ops / 1e9,
                e[ins] / (double) Math.max(1, l[ins]), l[cyc] / ops / 1e9, e[cyc] / ops / 1e9);
        }
        long ticks = ta.classes("bench").values().stream().mapToLong(a -> a.ticks).sum();
        for (Map.Entry<String, TickAttribution.Acc> c : ta.classes("bench").entrySet())
            System.out.printf("bench on %s: %.1f%% of time, %.2f GHz, IPC %.2f%n", c.getKey(), 100.0 * c.getValue().ticks / Math.max(1, ticks),
                c.getValue().uni[cyc] / (double) Math.max(1, c.getValue().uniNs), c.getValue().uni[ins] / (double) Math.max(1, c.getValue().uni[cyc]));
    }
}
