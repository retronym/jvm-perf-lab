import os, sys, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from perflab import jmh


def fake_jdk(version):
    home = tempfile.mkdtemp()
    os.makedirs(os.path.join(home, "bin"))
    open(os.path.join(home, "bin", "java"), "w").close()
    with open(os.path.join(home, "release"), "w") as f:
        f.write(f'IMPLEMENTOR="X"\nJAVA_VERSION="{version}"\n')
    return os.path.join(home, "bin", "java")


class QuietJdkWarningsTest(unittest.TestCase):
    def test_by_the_forks_jdk(self):
        self.assertEqual(jmh.quiet_jdk_warnings(fake_jdk("1.8.0_412")), "")
        self.assertEqual(jmh.quiet_jdk_warnings(fake_jdk("21.0.12")), "")
        self.assertEqual(jmh.quiet_jdk_warnings(fake_jdk("22")), "--enable-native-access=ALL-UNNAMED")
        self.assertEqual(jmh.quiet_jdk_warnings(fake_jdk("25.0.4")), "--enable-native-access=ALL-UNNAMED --sun-misc-unsafe-memory-access=allow")
        self.assertEqual(jmh.quiet_jdk_warnings(None), "")  # no -jvm: the build tool's java, not known
        self.assertEqual(jmh.quiet_jdk_warnings("/nonexistent/bin/java"), "")
        # the spec's own setting wins
        self.assertEqual(jmh.quiet_jdk_warnings(fake_jdk("25"), "-Xmx1g --sun-misc-unsafe-memory-access=warn"), "--enable-native-access=ALL-UNNAMED")

    def test_in_the_args_file(self):
        out = tempfile.mkdtemp()
        try:
            jmh.prepare(out, "none", ["-jvm", fake_jdk("25"), "B"], jvm_append="-Xmx1g", built="x")
        except Exception:  # its command, from a build that is not there: jmh.args is written before
            pass
        args = open(os.path.join(out, "jmh.args")).read().splitlines()
        self.assertEqual(args[args.index("-jvmArgsAppend") + 1], "--enable-native-access=ALL-UNNAMED --sun-misc-unsafe-memory-access=allow -Xmx1g")


if __name__ == "__main__":
    unittest.main()
