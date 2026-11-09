package scala.tools.nsc.compilerlab;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.LongAdder;

/** perflab-agent `hook` for `Types.isSubArgs`: samples, during a `SymbolOps` op only, which argument lists reach it and
 *  which positions are not `eq`. Writes the top entries to `<perflab.cell>/subargs-<pid>.txt` at exit.
 *  {{{
 *  hook subargs at=scala.reflect.internal.Types#isSubArgs call=scala.tools.nsc.compilerlab.SubArgsHook#isSubArgs
 *  }}}
 */
public final class SubArgsHook {
  private SubArgsHook() {}
  private static final AtomicLong calls = new AtomicLong();
  private static final LongAdder inOp = new LongAdder();
  private static final Map<String, LongAdder> seen = new ConcurrentHashMap<>();
  private static final int SAMPLE = Integer.getInteger("compilerlab.subargs.sample", 16);

  static {
    Runtime.getRuntime().addShutdownHook(new Thread(SubArgsHook::dump));
  }

  public static void isSubArgs(Object recv, Object tps1, Object tps2, Object tparams, int depth) {
    if (calls.incrementAndGet() % SAMPLE != 0) return;
    boolean op = StackWalker.getInstance().walk(s -> s.anyMatch(f -> f.getClassName().startsWith("scala.tools.nsc.compilerlab.SymbolOps")));
    if (!op) return;
    inOp.increment();
    StringBuilder sb = new StringBuilder();
    scala.collection.immutable.List<?> a = (scala.collection.immutable.List<?>) tps1, b = (scala.collection.immutable.List<?>) tps2;
    int i = 0;
    while (!a.isEmpty() && !b.isEmpty()) {
      Object x = a.head(), y = b.head();
      if (x != y) sb.append(" #").append(i).append(": ").append(x).append(" [").append(x.getClass().getSimpleName()).append(" ").append(System.identityHashCode(x) == System.identityHashCode(y) ? "" : "").append("] vs ").append(y).append(" [").append(y.getClass().getSimpleName()).append("]").append(x.equals(y) ? " EQUALS" : "");
      a = (scala.collection.immutable.List<?>) a.tail(); b = (scala.collection.immutable.List<?>) b.tail(); i++;
    }
    String key = sb.length() == 0 ? "all eq: " + tps1 : tps1 + "  vs  " + tps2 + "  |" + sb;
    seen.computeIfAbsent(key, k -> new LongAdder()).increment();
  }

  private static void dump() {
    String cell = System.getProperty("perflab.cell", ".");
    var es = new ArrayList<>(seen.entrySet());
    es.sort((x, y) -> Long.compare(y.getValue().sum(), x.getValue().sum()));
    StringBuilder out = new StringBuilder("calls " + calls.get() + ", sampled in op " + inOp.sum() + " (1 in " + SAMPLE + "), distinct " + es.size() + "\n");
    for (int k = 0; k < Math.min(60, es.size()); k++) out.append(es.get(k).getValue().sum()).append("  ").append(es.get(k).getKey()).append('\n');
    try { Files.writeString(Path.of(cell, "subargs-" + ProcessHandle.current().pid() + ".txt"), out); } catch (Exception e) { System.err.println("[subargs] " + e); }
  }
}
