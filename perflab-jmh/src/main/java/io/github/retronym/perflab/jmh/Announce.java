package io.github.retronym.perflab.jmh;

import java.lang.management.ManagementFactory;

/** First line from a benchmark's JVM: its pid (to attach a profiler or Instruments), JDK and options. */
public final class Announce {
    private Announce() {}

    public static void jvm(String benchmark) {
        System.out.println("\n[perflab] " + benchmark + " in pid " + ProcessHandle.current().pid() + ", JDK "
                + System.getProperty("java.version") + ", options " + ManagementFactory.getRuntimeMXBean().getInputArguments());
    }
}
