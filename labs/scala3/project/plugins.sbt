addSbtPlugin("pl.project13.scala" % "sbt-jmh" % "0.4.8")
// The checkout's build plugins (ScalaLibraryPlugin) read class files with its ASM (its project/build.sbt); sbt-jmh's
// older one would otherwise win.
libraryDependencies += "org.ow2.asm" % "asm" % "9.9"
