package zinclab;

import java.io.EOFException;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.PipedInputStream;
import java.io.PipedOutputStream;
import java.nio.channels.Channels;
import java.nio.channels.SocketChannel;
import java.net.UnixDomainSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * An sbt running in this JVM, on a build directory, and a client of its server socket: {@link #run} sends one command
 * line to the warm sbt and returns when it is done.
 *
 * The launcher boots the sbt version the build's {@code project/build.properties} names, in a class loader of its own,
 * so the JVM can host a different sbt (and Zinc) per fork without a classpath per version. sbt's shell reads a pipe
 * that never closes; commands arrive over the server's JSON-RPC (LSP framing) socket. Nothing here calls
 * {@code System.exit}.
 */
final class SbtHost {
    private final InputStream in;
    private final OutputStream out;
    private int ids;

    private SbtHost(InputStream in, OutputStream out) {
        this.in = in;
        this.out = out;
    }

    static SbtHost start(File base, long timeoutMillis) throws Exception {
        System.setProperty("sbt.server.forcestart", "true");
        System.setProperty("sbt.supershell", "false");
        System.setProperty("sbt.color", "false");
        System.setProperty("sbt.log.noformat", "true");
        System.setProperty("sbt.offline", "false");
        // sbt's shell reads System.in: a pipe that never delivers input and never closes
        System.setIn(new PipedInputStream(new PipedOutputStream()));
        Path active = base.toPath().resolve("project/target/active.json");
        Files.deleteIfExists(active);
        Thread boot = new Thread(() -> {
            try {
                Object args = xsbt.boot.Boot$.MODULE$.parseArgs(new String[] {"shell"});
                xsbt.boot.Launch$.MODULE$.apply(base, (xsbt.boot.LauncherArguments) args);
            } catch (Throwable e) {
                e.printStackTrace();
            }
        }, "sbt-host");
        boot.setDaemon(true);
        boot.start();
        long deadline = System.currentTimeMillis() + timeoutMillis;
        while (!Files.exists(active)) {
            if (!boot.isAlive()) throw new IllegalStateException("sbt exited before its server started");
            if (System.currentTimeMillis() > deadline) throw new IllegalStateException("sbt's server did not start in time");
            Thread.sleep(250);
        }
        String json = Files.readString(active);
        String uri = json.replaceAll("(?s).*\"uri\"\\s*:\\s*\"([^\"]*)\".*", "$1");
        if (!uri.startsWith("local://")) throw new IllegalStateException("not a local server uri: " + json);
        SocketChannel ch = SocketChannel.open(UnixDomainSocketAddress.of(uri.substring("local://".length())));
        SbtHost host = new SbtHost(Channels.newInputStream(ch), Channels.newOutputStream(ch));
        host.send("{\"jsonrpc\":\"2.0\",\"id\":\"init\",\"method\":\"initialize\",\"params\":{\"initializationOptions\":{}}}");
        return host;
    }

    /** Runs a command line (`;`-separated commands allowed) in the warm sbt; throws if it fails. */
    void run(String commandLine) throws IOException {
        String id = "c" + (ids++);
        send("{\"jsonrpc\":\"2.0\",\"id\":\"" + id + "\",\"method\":\"sbt/exec\",\"params\":{\"commandLine\":\""
            + commandLine.replace("\\", "\\\\").replace("\"", "\\\"") + "\"}}");
        while (true) {
            String m = read();
            if (!m.contains("\"id\":\"" + id + "\"")) continue; // log events and the like
            if (m.contains("\"error\"") || !m.contains("\"exitCode\":0"))
                throw new IllegalStateException("sbt: `" + commandLine + "` failed: " + m);
            return;
        }
    }

    private void send(String json) throws IOException {
        byte[] b = json.getBytes(StandardCharsets.UTF_8);
        out.write(("Content-Length: " + b.length + "\r\n\r\n").getBytes(StandardCharsets.US_ASCII));
        out.write(b);
        out.flush();
    }

    private String read() throws IOException {
        int len = -1;
        StringBuilder line = new StringBuilder();
        while (true) {
            int c = in.read();
            if (c < 0) throw new EOFException("sbt's server closed the connection");
            if (c == '\n') {
                String l = line.toString().trim();
                line.setLength(0);
                if (l.isEmpty()) break;
                if (l.toLowerCase().startsWith("content-length:")) len = Integer.parseInt(l.substring(15).trim());
            } else line.append((char) c);
        }
        return new String(in.readNBytes(len), StandardCharsets.UTF_8);
    }
}
