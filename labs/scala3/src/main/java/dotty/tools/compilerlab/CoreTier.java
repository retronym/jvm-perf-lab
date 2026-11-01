package dotty.tools.compilerlab;

import java.io.IOException;
import java.lang.invoke.MethodHandle;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.lang.reflect.Array;
import java.lang.reflect.Method;
import java.util.Optional;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;

/** Where on an Apple Silicon machine the benchmark thread runs, and a request for where it should.
 *
 *  macOS has no CPU affinity on Apple Silicon, and machines like the M5 Pro have two tiers of performance core (6
 *  "Super" cores with a 16 MB L2, 12 "Performance" cores in two clusters with 8 MB each): a fork whose main thread
 *  settles on one tier runs consistently faster or slower than one on the other, with the same instructions.
 *
 *  - `-Dcompilerlab.cores=true`: the benchmark samples the core it is on (`pthread_cpu_number_np`) as each
 *    compilation unit starts a phase, and writes per iteration the samples per cluster of `compilerlab.coresPerCluster`
 *    (default 6) cores to `<perflab.cell>/cores.tsv`.
 *  - `-Dcompilerlab.qos=user-interactive|user-initiated|default|utility|background`: the benchmark thread's QoS class
 *    (`pthread_set_qos_class_self_np`), set as each iteration starts; the scheduler prefers the best cores for the
 *    highest classes, but does not promise them.
 *
 *  Both are off by default, and do nothing where the functions are missing (not macOS) or the JVM has no
 *  `java.lang.foreign` (the lab compiles on JDK 21, where it is a preview API: it is reached by reflection, and runs on
 *  the JDK 22+ that benchmarks use).
 */
public final class CoreTier {
  private CoreTier() {}

  public static final boolean enabled = Boolean.getBoolean("compilerlab.cores");
  private static final String qos = System.getProperty("compilerlab.qos", "");
  private static final int coresPerCluster = Integer.getInteger("compilerlab.coresPerCluster", 6);
  private static final int clusters = 8;

  // int pthread_cpu_number_np(size_t *), as (MemorySegment) -> int
  private static final MethodHandle cpuNumber;
  // int pthread_set_qos_class_self_np(qos_class_t, int), as (int, int) -> int
  private static final MethodHandle setQos;
  // MemorySegment.get(ValueLayout.OfLong, long) on the benchmark thread's buffer for the core number
  private static final MethodHandle readLong;
  private static final Object cpuOut;

  static {
    MethodHandle cn = null, sq = null, rl = null;
    Object out = null;
    try {
      ClassLoader cl = ClassLoader.getSystemClassLoader();
      Class<?> linkerC = Class.forName("java.lang.foreign.Linker");
      Class<?> lookupC = Class.forName("java.lang.foreign.SymbolLookup");
      Class<?> fdC = Class.forName("java.lang.foreign.FunctionDescriptor");
      Class<?> layoutC = Class.forName("java.lang.foreign.MemoryLayout");
      Class<?> vlC = Class.forName("java.lang.foreign.ValueLayout");
      Class<?> ofLongC = Class.forName("java.lang.foreign.ValueLayout$OfLong");
      Class<?> segC = Class.forName("java.lang.foreign.MemorySegment");
      Class<?> arenaC = Class.forName("java.lang.foreign.Arena");
      Class<?> optC = Class.forName("java.lang.foreign.Linker$Option");
      Object linker = linkerC.getMethod("nativeLinker").invoke(null);
      Object lookup = linkerC.getMethod("defaultLookup").invoke(linker);
      Object jInt = vlC.getField("JAVA_INT").get(null);
      Object jLong = vlC.getField("JAVA_LONG").get(null);
      Object address = vlC.getField("ADDRESS").get(null);
      Method of = fdC.getMethod("of", layoutC, layoutC.arrayType());
      Method downcall = linkerC.getMethod("downcallHandle", segC, fdC, optC.arrayType());
      Method find = lookupC.getMethod("find", String.class);
      Object noOpts = Array.newInstance(optC, 0);
      Optional<?> cnSym = (Optional<?>) find.invoke(lookup, "pthread_cpu_number_np");
      if (cnSym.isPresent()) {
        Object args = Array.newInstance(layoutC, 1); Array.set(args, 0, address);
        cn = (MethodHandle) downcall.invoke(linker, cnSym.get(), of.invoke(null, jInt, args), noOpts);
        Object arena = arenaC.getMethod("global").invoke(null);
        out = arenaC.getMethod("allocate", layoutC).invoke(arena, jLong);
        rl = MethodHandles.publicLookup().findVirtual(segC, "get", MethodType.methodType(long.class, ofLongC, long.class))
          .bindTo(out).bindTo(jLong);
        cn = cn.asType(MethodType.methodType(int.class, Object.class));
      }
      Optional<?> sqSym = (Optional<?>) find.invoke(lookup, "pthread_set_qos_class_self_np");
      if (sqSym.isPresent()) {
        Object args = Array.newInstance(layoutC, 2); Array.set(args, 0, jInt); Array.set(args, 1, jInt);
        sq = (MethodHandle) downcall.invoke(linker, sqSym.get(), of.invoke(null, jInt, args), noOpts);
      }
    } catch (ReflectiveOperationException | RuntimeException e) {
      if (enabled || !qos.isEmpty()) System.err.println("[compiler-lab] CoreTier unavailable: " + e);
      cn = null; sq = null; rl = null; out = null;
    }
    cpuNumber = cn; setQos = sq; readLong = rl; cpuOut = out;
  }

  private static final long[] counts = new long[clusters];
  private static int iteration;
  private static boolean measuring;

  private static int qosClass(String name) {
    switch (name) {
      case "user-interactive": return 0x21;
      case "user-initiated": return 0x19;
      case "default": return 0x15;
      case "utility": return 0x11;
      case "background": return 0x09;
      default: throw new IllegalArgumentException("compilerlab.qos=" + name + ": expected user-interactive, user-initiated, default, utility or background");
    }
  }

  /** As an iteration starts, on the benchmark thread: set its QoS class, if asked, and clear the samples. */
  public static void begin(boolean measurement) {
    if (!qos.isEmpty() && setQos != null) {
      try {
        int rc = (int) setQos.invokeExact(qosClass(qos), 0);
        if (rc != 0) System.err.println("[compiler-lab] pthread_set_qos_class_self_np(" + qos + ") = " + rc);
      } catch (Throwable t) { throw new RuntimeException(t); }
    }
    java.util.Arrays.fill(counts, 0);
    measuring = measurement;
  }

  /** One sample of the core the calling thread is on. */
  public static void sample() {
    if (cpuNumber == null) return;
    try {
      int rc = (int) cpuNumber.invokeExact(cpuOut);
      if (rc != 0) return;
      long cpu = (long) readLong.invokeExact(0L);
      counts[(int) Math.min(cpu / coresPerCluster, clusters - 1)]++;
    } catch (Throwable t) { throw new RuntimeException(t); }
  }

  /** As an iteration ends: append its samples per cluster to `<perflab.cell>/cores.tsv`. */
  public static void end() {
    int index = iteration++;
    if (!enabled) return;
    String cell = System.getProperty("perflab.cell");
    if (cell == null) return;
    StringBuilder line = new StringBuilder();
    long total = 0;
    for (long c : counts) total += c;
    line.append(index).append('\t').append(measuring ? "measurement" : "warmup").append('\t').append(total);
    for (long c : counts) line.append('\t').append(c);
    line.append('\n');
    Path out = Path.of(cell, "cores.tsv");
    try {
      if (!Files.exists(out))
        Files.writeString(out, "iteration\tkind\tsamples\tcluster0\tcluster1\tcluster2\tcluster3\tcluster4\tcluster5\tcluster6\tcluster7\n", StandardCharsets.UTF_8);
      Files.writeString(out, line, StandardCharsets.UTF_8, StandardOpenOption.APPEND);
    } catch (IOException e) { throw new RuntimeException(e); }
  }
}
