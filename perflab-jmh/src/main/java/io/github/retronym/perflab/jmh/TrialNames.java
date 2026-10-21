package io.github.retronym.perflab.jmh;

import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.runner.BenchmarkList;
import org.openjdk.jmh.runner.BenchmarkListEntry;
import org.openjdk.jmh.runner.format.OutputFormatFactory;
import org.openjdk.jmh.runner.options.CommandLineOptionException;
import org.openjdk.jmh.runner.options.CommandLineOptions;
import org.openjdk.jmh.runner.options.ProfilerConfig;
import org.openjdk.jmh.runner.options.VerboseMode;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.*;

/**
 * JMH's async profiler writes each trial into a directory named after the benchmark, its mode and every parameter
 * ({@code BenchmarkParams.id()}, URL-encoded), and ignores a failed {@code mkdirs}. A name over the file system's
 * limit (255 bytes on APFS and ext4), as a long path in a parameter makes it, leaves async-profiler nowhere to write:
 * with {@code jfrsync} the fork fails with "Could not start master JFR recording", without it the profile is lost.
 * Checked before any fork starts.
 */
final class TrialNames {
    static final int NAME_MAX = 255;

    /** {@code BenchmarkParams.id()}, with {@code %} replaced as JMH's AsyncProfiler does. */
    static String id(String benchmark, Mode mode, SortedMap<String, String> params) {
        StringBuilder sb = new StringBuilder(encode(benchmark)).append('-').append(mode);
        params.forEach((k, v) -> sb.append('-').append(encode(k)).append('-').append(encode(v)));
        return sb.toString().replace("%", "_");
    }

    private static String encode(String s) {
        return URLEncoder.encode(s, StandardCharsets.UTF_8);
    }

    /** The problem with these arguments, if a trial's directory name would be too long for async-profiler's output. */
    static Optional<String> check(List<String> args) {
        CommandLineOptions cmd;
        try {
            cmd = new CommandLineOptions(args.toArray(new String[0]));
        } catch (CommandLineOptionException e) {
            return Optional.empty();  // JMH reports it
        }
        if (cmd.getProfilers().stream().map(ProfilerConfig::getKlass).noneMatch(k -> k.equals("async") || k.endsWith(".AsyncProfiler")))
            return Optional.empty();
        SortedSet<BenchmarkListEntry> benchmarks;
        try {
            benchmarks = BenchmarkList.defaultList().find(OutputFormatFactory.createFormatInstance(System.err, VerboseMode.SILENT),
                cmd.getIncludes(), cmd.getExcludes());
        } catch (RuntimeException e) {
            return Optional.empty();  // no benchmark list (not a benchmarks jar): JMH reports it
        }
        for (BenchmarkListEntry b : benchmarks) {
            // every combination of parameter values is a trial: the longest value of each parameter makes the longest name
            SortedMap<String, String> longest = new TreeMap<>();
            b.getParams().orElse(Map.of()).forEach((k, defaults) -> {
                Collection<String> values = cmd.getParameter(k).orElse(Arrays.asList(defaults));
                longest.put(k, values.stream().max(Comparator.comparingInt(v -> encode(v).length())).orElse(""));
            });
            Collection<Mode> modes = cmd.getBenchModes().isEmpty() ? List.of(b.getMode()) : cmd.getBenchModes();
            for (Mode mode : modes) {
                String id = id(b.getUsername(), mode == Mode.All ? Mode.SingleShotTime : mode, longest);
                if (id.length() > NAME_MAX) {
                    Map.Entry<String, String> worst = Collections.max(longest.entrySet(),
                        Comparator.comparingInt(e -> encode(e.getValue()).length()));
                    return Optional.of(String.format(
                        "%s: async-profiler's output directory for this trial would be named %s (%d bytes), over the file "
                            + "system's %d: JMH names it after the benchmark and every parameter. Shorten the longest "
                            + "parameter value, %s = %s (%d bytes encoded), e.g. by a symlink to a shorter path.",
                        b.getUsername(), id, id.length(), NAME_MAX, worst.getKey(), worst.getValue(),
                        encode(worst.getValue()).length()));
                }
            }
        }
        return Optional.empty();
    }
}
