package dotty.tools.compilerlab;

import com.sun.management.HotSpotDiagnosticMXBean;
import java.lang.management.ManagementFactory;
import java.nio.file.Files;
import java.nio.file.Path;
import javax.management.ObjectName;

/** Hooks for perflab-agent's caller audit (`hook` probes, woven into the compiler as it loads) that capture the live
 *  heap at the same point of a compilation in two builds: at the end of the typer (`TyperPhase.runOn`) of the
 *  `compilerlab.heapdump.at`-th compile of the fork (default 20), a class histogram of the live objects and a heap dump
 *  of them, to `compilerlab.heapdump.file` (`%p` the pid; `.histo.txt` and `.hprof` appended).
 *
 *  {{{
 *  hook heapdump at=dotty.tools.dotc.typer.TyperPhase#runOn call=dotty.tools.compilerlab.HeapDumpHook#typerEnter exit=dotty.tools.compilerlab.HeapDumpHook#typerExit
 *  }}}
 */
public final class HeapDumpHook {
  private HeapDumpHook() {}

  private static int typerRuns;

  public static void typerEnter(Object phase, Object units, Object ctx) {}

  public static void typerExit() {
    int n = ++typerRuns;
    if (n != Integer.getInteger("compilerlab.heapdump.at", 20)) return;
    String file = System.getProperty("compilerlab.heapdump.file");
    if (file == null) return;
    String base = file.replace("%p", Long.toString(ProcessHandle.current().pid()));
    try {
      // the histogram forces a full GC, so it and the dump both see the live objects only
      String histo = (String) ManagementFactory.getPlatformMBeanServer().invoke(
          new ObjectName("com.sun.management:type=DiagnosticCommand"), "gcClassHistogram",
          new Object[] {new String[0]}, new String[] {String[].class.getName()});
      Files.writeString(Path.of(base + ".histo.txt"), histo);
      ManagementFactory.getPlatformMXBean(HotSpotDiagnosticMXBean.class).dumpHeap(base + ".hprof", true);
      System.err.println("[heapdump] typer run " + n + ": " + base + ".{histo.txt,hprof}");
    } catch (Exception e) {
      System.err.println("[heapdump] failed: " + e);
    }
  }
}
