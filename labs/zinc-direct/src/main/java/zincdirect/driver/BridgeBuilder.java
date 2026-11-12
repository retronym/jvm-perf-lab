package zincdirect.driver;

import sbt.internal.inc.RawCompiler;
import xsbti.compile.ClasspathOptions;

import java.io.File;
import java.io.InputStream;
import java.nio.file.*;
import java.util.*;
import java.util.jar.JarEntry;
import java.util.jar.JarOutputStream;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/** Compiles the compiler bridge from Zinc 1.x's published bridge sources. Zinc 1.x only: see Driver.bridge. */
public final class BridgeBuilder {
    public static void build(Path jar, Path cpDir, String zinc, String scalaV, List<Path> scalaJars) throws Exception {
        Files.createDirectories(jar.getParent());
        List<Path> zincJars = Driver.readPaths(cpDir.resolve("zinc-" + zinc + ".txt"));
        List<Path> bridgeSrc = Driver.readPaths(cpDir.resolve("bridge-src-" + zinc + ".txt"));
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
                    if (!e.isDirectory() && e.getName().startsWith("META-INF/services/")) { // the bridge is found through ServiceLoader
                        Path r = out.resolve(e.getName());
                        Files.createDirectories(r.getParent());
                        try (InputStream in = z.getInputStream(e)) { Files.copy(in, r); }
                        continue;
                    }
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
        Driver.Instance si = new Driver.Instance(scalaV, scalaJars);
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
        Driver.deleteTree(tmp);
    }

}
