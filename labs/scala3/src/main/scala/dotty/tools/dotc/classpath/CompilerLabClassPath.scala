package dotty.tools.dotc.classpath

import dotty.tools.io.AbstractFile

/** The classpath of `dotty.tools.compilerlab.InMemoryClasspath`, in this package because the classpath classes it builds
 *  on are private to it (scala/scala3#27416).
 */
object CompilerLabClassPath:
  /** The class files in the in-memory directories `roots`, in order, then the sources in `sourcePath`, if not null. */
  def apply(roots: List[AbstractFile], sourcePath: AbstractFile | Null): ClassPath =
    val sources = if sourcePath == null then Nil else List(SourcePath(sourcePath))
    AggregateClassPath(roots.map(NestedVirtualDirectoryClassPath(_)) ::: sources)

  /** `VirtualDirectoryClassPath` that finds nested packages: `DirectoryLookup` asks for `java/lang/`, with a trailing
   *  separator, which `AbstractFile.lookupPath` resolves to an empty last name on a virtual directory, so only the root
   *  package was found.
   */
  private final class NestedVirtualDirectoryClassPath(dir: AbstractFile) extends VirtualDirectoryClassPath(dir):
    override protected def getSubDir(packageDirName: String): Option[AbstractFile] =
      super.getSubDir(packageDirName.stripSuffix(java.io.File.separator))

  /** The sources in an in-memory directory, as `-sourcepath` would find them on disk (`DirectorySourcePath`). */
  private final class SourcePath(protected override val dir: AbstractFile) extends ClassPath with DirectoryLookup[SourceFileEntry]:
    type F = AbstractFile
    protected def getSubDir(packageDirName: String): Option[AbstractFile] =
      dir.lookupPath(packageDirName.stripSuffix(java.io.File.separator), java.io.File.separatorChar, directory = true)
    protected def listChildren(dir: AbstractFile, filter: Option[AbstractFile => Boolean]): Iterable[AbstractFile] =
      filter.fold(dir.iterator.toSeq)(dir.iterator.filter(_).toSeq)
    protected def getName(f: AbstractFile): String = f.name
    protected def toAbstractFile(f: AbstractFile): AbstractFile = f
    protected def isPackage(f: AbstractFile): Boolean = f.isDirectory && FileUtils.mayBeValidPackage(f.name)
    protected def createFileEntry(file: AbstractFile): SourceFileEntry = SourceFileEntry(file)
    protected def isMatchingFile(f: AbstractFile): Boolean = !f.isDirectory && FileUtils.endsSourceExtension(f.name)
    override def sources(inPackage: String): Iterable[SourceFileEntry] = files(inPackage)
    def searchLocations: Iterable[AbstractFile] = Seq(dir)
