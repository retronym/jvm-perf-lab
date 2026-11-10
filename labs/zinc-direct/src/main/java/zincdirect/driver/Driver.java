package zincdirect.driver;

import sbt.internal.inc.PlainVirtualFileConverter;
import sbt.internal.inc.RawCompiler;
import sbt.internal.inc.ZincUtil;
import sbt.internal.inc.javac.JavaTools$;
import xsbti.Logger;
import xsbti.Problem;
import xsbti.Reporter;
import xsbti.VirtualFile;
import xsbti.compile.*;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.PrintStream;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CyclicBarrier;
import java.util.function.Supplier;
import java.util.jar.JarEntry;
import java.util.jar.JarOutputStream;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/**
 * Compiles K copies of one project through Zinc's API at the same time, in this JVM. Loaded by the benchmark in a class
 * loader of the Zinc under test (see ZincDirectBenchmark) and called by reflection with JDK types only, so it
 * must not be referred to by name from the benchmark. Compiled against Zinc 1.12.1; 1.13.0 is API compatible for what it uses.
 *
 * Time is attributed per copy: before the first scalac phase (Zinc's setup: classpath lookup, bridge loading), each
 * scalac phase (CompileProgress marks the phase of each unit; the bridge's `xsbt-api`, `xsbt-dependency` and
 * `xsbt-analyzer` phases are Zinc's own), javac, after the last phase (invalidation, analysis merge), and the analysis
 * store write.
 */
public final class Driver {
    private final Map<String, String> cfg;
    private final int copies;
    private final Path work;
    private final ScalaInstance scalaInstance;
    private final Compilers compilers;
    private final IncrementalCompiler zinc = ZincUtil.defaultIncrementalCompiler();
    private final VirtualFile[] sources;
    private final VirtualFile[] classpath;
    private final String[] scalacOptions;
    private final String[] javacOptions;
    private final TimedJavac javac;
    private final PlainVirtualFileConverter converter = PlainVirtualFileConverter.converter();
    private final Copy[] copy;

    public Driver(Map<String, String> cfg) throws Exception {
        this.cfg = cfg;
        this.copies = Integer.parseInt(cfg.get("copies"));
        this.work = Paths.get(cfg.get("work")).toAbsolutePath();
        Path cpDir = Paths.get(cfg.get("cpDir"));
        Path inputs = Paths.get(cfg.get("inputs"));
        String zincV = cfg.get("zinc"), scalaV = cfg.get("scala");

        List<Path> scalaJars = readPaths(cpDir.resolve("scala-" + scalaV + ".txt"));
        scalaInstance = new Instance(scalaV, scalaJars);
        Path bridge = bridge(zincV, scalaV, cpDir, scalaJars);
        AnalyzingCompilerHolder holder = new AnalyzingCompilerHolder(scalaInstance, bridge);
        javac = new TimedJavac(JavaTools$.MODULE$.directOrFork(scalaInstance, ClasspathOptions.of(false, false, false, false, false), scala.Option.empty()).javac());
        JavaTools tools = new JavaTools() {
            public JavaCompiler javac() { return javac; }
            public Javadoc javadoc() { return JavaTools$.MODULE$.directOrFork(scalaInstance, ClasspathOptions.of(false, false, false, false, false), scala.Option.empty()).javadoc(); }
        };
        compilers = Compilers.of(holder.compiler, tools);

        sources = readPaths(inputs.resolve("sources.txt")).stream().map(p -> converter.toVirtualFile(p)).toArray(VirtualFile[]::new);
        Path scalaLib = scalaInstance.libraryJar().toPath();
        classpath = readPaths(inputs.resolve("classpath.txt")).stream()
            .map(p -> p.getFileName().toString().startsWith("scala-library-") ? scalaLib : p)
            .distinct().map(p -> converter.toVirtualFile(p)).toArray(VirtualFile[]::new);
        scalacOptions = readLines(inputs.resolve("scalac.txt")).toArray(new String[0]);
        javacOptions = readLines(inputs.resolve("javac.txt")).toArray(new String[0]);
        copy = new Copy[copies];
        for (int i = 0; i < copies; i++) copy[i] = new Copy(i);
        log("zinc " + zincV + ", scala " + scalaV + ": " + sources.length + " sources, " + classpath.length + " classpath entries, " + copies + " copies, bridge " + bridge);
    }

    /** Deletes every copy's output and analysis store: the next round is a clean compile. */
    public void clean() throws IOException {
        for (Copy c : copy) c.clean();
    }

    /** One round: K clean compiles at the same time. Returns per-copy means and maxima, in ms, and the problems counted. */
    public Map<String, Double> round() throws Exception {
        CyclicBarrier go = new CyclicBarrier(copies + 1);
        Throwable[] failure = new Throwable[1];
        Thread[] threads = new Thread[copies];
        for (int i = 0; i < copies; i++) {
            Copy c = copy[i];
            threads[i] = new Thread(null, () -> {
                try { go.await(); c.compile(); } catch (Throwable t) { synchronized (failure) { failure[0] = t; } }
            }, "zinc-copy-" + i, 256L << 20);
            threads[i].start();
        }
        go.await();
        long t0 = System.nanoTime();
        for (Thread t : threads) t.join();
        double wall = (System.nanoTime() - t0) / 1e6;
        if (failure[0] != null) throw new IllegalStateException("a copy failed", failure[0]);
        Map<String, Double> out = new TreeMap<>();
        out.put("wallMs", wall);
        Map<String, Double> sum = new TreeMap<>();
        double max = 0;
        for (Copy c : copy) {
            max = Math.max(max, c.totalMs);
            for (Map.Entry<String, Double> e : c.ms.entrySet()) sum.merge(e.getKey(), e.getValue(), Double::sum);
            sum.merge("total", c.totalMs, Double::sum);
        }
        for (Map.Entry<String, Double> e : sum.entrySet()) out.put(e.getKey(), e.getValue() / copies);
        out.put("copyMax", max);
        out.put("errors", (double) Arrays.stream(copy).mapToInt(c -> c.errors).sum());
        out.put("warnings", (double) Arrays.stream(copy).mapToInt(c -> c.warnings).sum());
        return out;
    }

    // ---------------------------------------------------------------------------------------------------------------

    private final class Copy {
        final int index;
        final Path dir, classes, analysisFile;
        final Map<String, Double> ms = new TreeMap<>();
        double totalMs;
        int errors, warnings;

        Copy(int index) {
            this.index = index;
            dir = work.resolve("copy-" + index);
            classes = dir.resolve("classes");
            analysisFile = dir.resolve("inc_compile.zip");
        }

        void clean() throws IOException {
            deleteTree(dir);
            Files.createDirectories(classes);
        }

        void compile() throws Exception {
            Progress progress = new Progress();
            Counting reporter = new Counting();
            TimedJavac.Slot jslot = javac.slot();
            CompileOptions options = CompileOptions.of(classpath, sources, classes, scalacOptions, javacOptions, 100, p -> p, CompileOrder.Mixed);
            Setup setup = Setup.of(new Lookup(), false, analysisFile, CompilerCache.fresh(), IncOptions.of(), reporter,
                Optional.of(progress), new xsbti.T2[0]);
            Inputs inputs = Inputs.of(compilers, options, setup, PreviousResult.of(Optional.empty(), Optional.empty()));
            long t0 = System.nanoTime();
            progress.start(t0);
            CompileResult result = zinc.compile(inputs, new Quiet());
            long t1 = System.nanoTime();
            progress.finish(t1);
            AnalysisStore store = FileAnalysisStore.getDefault(analysisFile.toFile());
            store.set(AnalysisContents.create(result.analysis(), result.setup()));
            long t2 = System.nanoTime();
            totalMs = (t2 - t0) / 1e6;
            ms.clear();
            double javacMs = jslot.ms();
            double scalac = 0;
            for (Map.Entry<String, Double> e : progress.phase.entrySet()) { ms.put("phase:" + e.getKey(), e.getValue()); }
            ms.put("pre", progress.pre);
            ms.put("scalac", progress.scalacMs());
            ms.put("javac", javacMs);
            // after the last phase: invalidation, analysis merge, anything else Zinc does; javac runs there too
            ms.put("post", Math.max(0, progress.post - javacMs));
            ms.put("persist", (t2 - t1) / 1e6);
            errors = reporter.errors;
            warnings = reporter.warnings;
        }
    }

    /** Attributes the time between progress events to the phase that was running. One compile, one thread. */
    private static final class Progress implements CompileProgress {
        final Map<String, Double> phase = new LinkedHashMap<>();
        double pre, post;
        private long last;
        private String current;
        private long end;

        void start(long t) { last = t; current = null; }
        private void tick(String next) {
            long now = System.nanoTime();
            double d = (now - last) / 1e6;
            last = now;
            if (current == null) pre += d; else phase.merge(current, d, Double::sum);
            current = next;
        }
        @Override public void startUnit(String ph, String unit) { tick(ph); }
        @Override public boolean advance(int cur, int total, String prev, String next) { tick(next); return true; }
        void finish(long t) { post = (t - last) / 1e6; if (current != null) { /* the last phase's tail is in post */ } }
        double scalacMs() { return phase.values().stream().mapToDouble(Double::doubleValue).sum(); }
    }

    private static final class Lookup implements PerClasspathEntryLookup {
        private static final Map<String, DefinesClass> defines = new ConcurrentHashMap<>();
        public Optional<CompileAnalysis> analysis(VirtualFile f) { return Optional.empty(); }
        public DefinesClass definesClass(VirtualFile f) {
            // shared by the copies: one index per classpath entry, as sbt's lookup caches
            return defines.computeIfAbsent(f.id(), k -> sbt.internal.inc.Locate.definesClass(f));
        }
    }

    private static final class Counting implements Reporter {
        int errors, warnings;
        public void reset() { errors = 0; warnings = 0; }
        public boolean hasErrors() { return errors > 0; }
        public boolean hasWarnings() { return warnings > 0; }
        public void printSummary() { }
        public Problem[] problems() { return new Problem[0]; }
        public void log(Problem p) {
            switch (p.severity()) {
                case Error: errors++; if (errors <= 10) Driver.log("error: " + p.position().sourcePath().orElse("?") + ":" + p.position().line().orElse(-1) + ": " + p.message()); break;
                case Warn: warnings++; break;
                default: break;
            }
        }
        public void comment(xsbti.Position pos, String msg) { }
    }

    private static final class Quiet implements Logger {
        public void error(Supplier<String> m) { Driver.log("error: " + m.get()); }
        public void warn(Supplier<String> m) { }
        public void info(Supplier<String> m) { }
        public void debug(Supplier<String> m) { }
        public void trace(Supplier<Throwable> t) { }
    }

    /** Times the javac Zinc runs for the mixed sources. One slot per compile (a copy runs on one thread). */
    private static final class TimedJavac implements JavaCompiler {
        private final JavaCompiler delegate;
        private final ThreadLocal<Slot> slots = new ThreadLocal<>();
        TimedJavac(JavaCompiler delegate) { this.delegate = delegate; }
        static final class Slot { long nanos; double ms() { return nanos / 1e6; } }
        Slot slot() { Slot s = new Slot(); slots.set(s); return s; }
        public boolean supportsDirectToJar() { return delegate.supportsDirectToJar(); }
        public boolean run(VirtualFile[] sources, String[] options, Output output, IncToolOptions in, Reporter reporter, Logger log) {
            long t = System.nanoTime();
            try { return delegate.run(sources, options, output, in, reporter, log); }
            finally { Slot s = slots.get(); if (s != null) s.nanos += System.nanoTime() - t; }
        }
    }

    // --- Scala instance and compiler bridge -------------------------------------------------------------------------

    private static final class Instance implements ScalaInstance {
        private final String version;
        private final File[] all, lib, compiler;
        private final ClassLoader libLoader, compilerLoader, loader;

        Instance(String version, List<Path> jars) {
            this.version = version;
            all = jars.stream().map(Path::toFile).toArray(File[]::new);
            lib = jars.stream().filter(p -> p.getFileName().toString().startsWith("scala-library")).map(Path::toFile).toArray(File[]::new);
            compiler = jars.stream().filter(p -> !p.getFileName().toString().startsWith("scala-library")).map(Path::toFile).toArray(File[]::new);
            ClassLoader top = ClassLoader.getPlatformClassLoader();
            libLoader = new URLClassLoader(urls(lib), top);
            compilerLoader = new URLClassLoader(urls(compiler), libLoader);
            loader = compilerLoader;
        }
        public String version() { return version; }
        public ClassLoader loader() { return loader; }
        public ClassLoader loaderCompilerOnly() { return compilerLoader; }
        public ClassLoader loaderLibraryOnly() { return libLoader; }
        public File[] libraryJars() { return lib; }
        public File[] compilerJars() { return compiler; }
        public File[] otherJars() { return new File[0]; }
        public File[] allJars() { return all; }
        public String actualVersion() { return version; }
    }

    private static final class AnalyzingCompilerHolder {
        final ScalaCompiler compiler;
        AnalyzingCompilerHolder(ScalaInstance si, Path bridgeJar) { compiler = ZincUtil.scalaCompiler(si, bridgeJar); }
    }

    private static synchronized Path bridge(String zinc, String scalaV, Path cpDir, List<Path> scalaJars) throws Exception {
        Path jar = cpDir.resolveSibling("bridge").resolve("bridge-" + zinc + "-" + scalaV + ".jar");
        if (Files.exists(jar)) return jar;
        Files.createDirectories(jar.getParent());
        List<Path> zincJars = readPaths(cpDir.resolve("zinc-" + zinc + ".txt"));
        List<Path> bridgeSrc = readPaths(cpDir.resolve("bridge-src-" + zinc + ".txt"));
        Path tmp = Files.createTempDirectory(jar.getParent(), "bridge-build");
        Path src = tmp.resolve("src"), out = tmp.resolve("classes");
        Files.createDirectories(src);
        Files.createDirectories(out);
        List<Path> srcs = new ArrayList<>();
        for (Path sj : bridgeSrc) {
            if (!sj.getFileName().toString().startsWith("compiler-bridge_2.13")) continue;
            try (ZipFile z = new ZipFile(sj.toFile())) {
                for (Enumeration<? extends ZipEntry> en = z.entries(); en.hasMoreElements();) {
                    ZipEntry e = en.nextElement();
                    if (e.isDirectory() || !(e.getName().endsWith(".scala") || e.getName().endsWith(".java"))) continue;
                    Path p = src.resolve(e.getName());
                    Files.createDirectories(p.getParent());
                    try (InputStream in = z.getInputStream(e)) { Files.copy(in, p); }
                    srcs.add(p);
                }
            }
        }
        if (srcs.isEmpty()) throw new IllegalStateException("no compiler-bridge_2.13 sources in " + bridgeSrc);
        List<Path> cp = new ArrayList<>(scalaJars);
        for (Path z : zincJars) {
            String n = z.getFileName().toString();
            if (n.startsWith("compiler-interface") || n.startsWith("util-interface")) cp.add(z);
        }
        Instance si = new Instance(scalaV, scalaJars);
        RawCompiler raw = new RawCompiler(si, ClasspathOptions.of(false, false, false, false, false), sbt.util.Logger.Null());
        scala.collection.Seq<String> noOptions = scala.collection.JavaConverters.asScalaBuffer(new ArrayList<String>());
        raw.apply(scala.collection.JavaConverters.asScalaBuffer(srcs), scala.collection.JavaConverters.asScalaBuffer(cp), out, noOptions);
        Path tmpJar = tmp.resolve("bridge.jar");
        try (JarOutputStream jo = new JarOutputStream(Files.newOutputStream(tmpJar)); Stream<Path> w = Files.walk(out)) {
            for (Path p : w.filter(Files::isRegularFile).sorted().collect(Collectors.toList())) {
                jo.putNextEntry(new JarEntry(out.relativize(p).toString().replace(File.separatorChar, '/')));
                Files.copy(p, jo);
                jo.closeEntry();
            }
        }
        Files.move(tmpJar, jar, StandardCopyOption.ATOMIC_MOVE);
        deleteTree(tmp);
        return jar;
    }

    // --- helpers ------------------------------------------------------------------------------------------------------

    private static URL[] urls(File[] files) {
        return Arrays.stream(files).map(f -> { try { return f.toURI().toURL(); } catch (Exception e) { throw new RuntimeException(e); } }).toArray(URL[]::new);
    }

    private static List<String> readLines(Path p) throws IOException {
        return Files.readAllLines(p).stream().map(String::trim).filter(s -> !s.isEmpty()).collect(Collectors.toList());
    }

    private static List<Path> readPaths(Path p) throws IOException {
        return readLines(p).stream().map(Paths::get).collect(Collectors.toList());
    }

    private static void deleteTree(Path dir) throws IOException {
        if (!Files.exists(dir)) return;
        try (Stream<Path> w = Files.walk(dir)) {
            for (Path p : w.sorted(Comparator.reverseOrder()).collect(Collectors.toList())) Files.deleteIfExists(p);
        }
    }

    private static final PrintStream OUT = System.out;
    private static void log(String s) { OUT.println("[zinc-direct] " + s); }
}
