package io.github.retronym.perflab.jmh;

import java.util.ArrayList;
import java.util.List;

/**
 * {@code org.openjdk.jmh.Main} with jvm-perf-lab's default profilers: {@code gc} (allocation per op, GC count and time)
 * {@link JitProfiler} (is the JIT still busy?) and {@link PairedProfiler} (time per variant, when variants alternate
 * within the fork; otherwise silent). A default is skipped if given on the command line;
 * {@code -noDefaultProf} drops them all.
 * Arguments: see {@link #arguments}, for build tools that split a command line at {@code ;}.
 */
public class Main {
    static final List<String> DEFAULTS = List.of("gc", JitProfiler.class.getName(), PairedProfiler.class.getName());

    public static void main(String[] argv) throws Exception {
        List<String> args = arguments(List.of(argv));
        boolean defaults = !args.remove("-noDefaultProf");
        // Defaults go last: JMH runs beforeIteration in order and afterIteration in reverse, so JitProfiler's window
        // then excludes other profilers' own setup and analysis (xctrace's start, parsing its export).
        List<String> extra = new ArrayList<>(args);
        if (defaults)
            for (String p : DEFAULTS)
                if (!given(args, p)) { extra.add("-prof"); extra.add(p); }
        org.openjdk.jmh.Main.main(extra.toArray(new String[0]));
    }

    /**
     * The command line, with two ways around build tools that split a typed command at {@code ;} (sbt does), which
     * separates a JMH profiler's options:
     * <ul>
     * <li>{@code @path}: the lines of that file, one argument each, as typed but without any quoting (blank lines and
     * lines starting with {@code #} skipped), so nothing needs escaping, including {@code ;}, spaces and quotes;</li>
     * <li>{@code &} between a profiler's options: {@code -prof "async:output=jfr&dir=out"} is
     * {@code -prof "async:output=jfr;dir=out"}.</li>
     * </ul>
     */
    static List<String> arguments(List<String> argv) throws java.io.IOException {
        List<String> out = new ArrayList<>();
        for (String a : argv) {
            if (a.startsWith("@") && a.length() > 1) {
                for (String line : java.nio.file.Files.readAllLines(java.nio.file.Path.of(a.substring(1))))
                    if (!line.isBlank() && !line.stripLeading().startsWith("#")) out.add(line.strip());
            } else out.add(a);
        }
        for (int i = 0; i + 1 < out.size(); i++)
            if (out.get(i).equals("-prof")) out.set(i + 1, out.get(i + 1).replace('&', ';'));
        return out;
    }

    private static boolean given(List<String> args, String prof) {
        for (int i = 0; i + 1 < args.size(); i++)
            if (args.get(i).equals("-prof") && args.get(i + 1).split(":", 2)[0].equals(prof)) return true;
        return false;
    }
}
