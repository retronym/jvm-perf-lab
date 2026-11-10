package org.apache.pekko.stream.labspec

import scala.annotation.tailrec

final class Spec0[@specialized(Int, Long, Double) A, @specialized(Int, Long, Double) B](val xs: Array[A], val ys: Array[B]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip0(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip1(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip2(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip3(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip4(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip5(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip6(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip7(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip8(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip9(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip10(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip11(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
}

final class Spec1[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec2[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec3[@specialized(Int, Long, Double) A, @specialized(Int, Long, Double) B](val xs: Array[A], val ys: Array[B]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip0(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip1(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip2(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip3(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip4(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip5(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip6(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip7(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip8(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip9(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip10(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip11(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
}

final class Spec4[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec5[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec6[@specialized(Int, Long, Double) A, @specialized(Int, Long, Double) B](val xs: Array[A], val ys: Array[B]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip0(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip1(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip2(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip3(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip4(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip5(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip6(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip7(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip8(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip9(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip10(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip11(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
}

final class Spec7[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec8[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec9[@specialized(Int, Long, Double) A, @specialized(Int, Long, Double) B](val xs: Array[A], val ys: Array[B]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip0(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip1(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip2(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip3(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip4(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip5(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip6(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip7(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip8(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip9(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip10(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip11(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
}

final class Spec10[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec11[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec12[@specialized(Int, Long, Double) A, @specialized(Int, Long, Double) B](val xs: Array[A], val ys: Array[B]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip0(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip1(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip2(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip3(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip4(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip5(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip6(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip7(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip8(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip9(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip10(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip11(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
}

final class Spec13[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec14[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec15[@specialized(Int, Long, Double) A, @specialized(Int, Long, Double) B](val xs: Array[A], val ys: Array[B]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip0(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip1(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip2(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip3(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip4(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip5(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip6(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip7(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip8(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip9(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip10(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip11(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
}

final class Spec16[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec17[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec18[@specialized(Int, Long, Double) A, @specialized(Int, Long, Double) B](val xs: Array[A], val ys: Array[B]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip0(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip1(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip2(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip3(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip4(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip5(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip6(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip7(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip8(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip9(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip10(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip11(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
}

final class Spec19[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec20[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec21[@specialized(Int, Long, Double) A, @specialized(Int, Long, Double) B](val xs: Array[A], val ys: Array[B]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip0(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip1(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip2(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip3(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip4(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip5(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip6(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip7(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip8(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip9(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip10(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip11(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
}

final class Spec22[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec23[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec24[@specialized(Int, Long, Double) A, @specialized(Int, Long, Double) B](val xs: Array[A], val ys: Array[B]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip0(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip1(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip2(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip3(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip4(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip5(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip6(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip7(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip8(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip9(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip10(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip11(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
}

final class Spec25[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec26[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec27[@specialized(Int, Long, Double) A, @specialized(Int, Long, Double) B](val xs: Array[A], val ys: Array[B]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip0(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip1(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip2(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip3(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip4(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip5(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip6(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip7(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip8(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip9(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip10(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip11(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
}

final class Spec28[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec29[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec30[@specialized(Int, Long, Double) A, @specialized(Int, Long, Double) B](val xs: Array[A], val ys: Array[B]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip0(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip1(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip2(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip3(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip4(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip5(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip6(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip7(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip8(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip9(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip10(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip11(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
}

final class Spec31[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec32[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec33[@specialized(Int, Long, Double) A, @specialized(Int, Long, Double) B](val xs: Array[A], val ys: Array[B]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip0(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip1(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip2(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip3(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip4(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip5(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip6(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip7(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip8(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip9(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip10(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip11(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
}

final class Spec34[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec35[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec36[@specialized(Int, Long, Double) A, @specialized(Int, Long, Double) B](val xs: Array[A], val ys: Array[B]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip0(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip1(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip2(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip3(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip4(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip5(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip6(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip7(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip8(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip9(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip10(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip11(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
}

final class Spec37[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec38[@specialized(Int, Long, Double) A](val xs: Array[A]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
}

final class Spec39[@specialized(Int, Long, Double) A, @specialized(Int, Long, Double) B](val xs: Array[A], val ys: Array[B]) {
  def fold0(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count0(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto0(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find0(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip0(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold1(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count1(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto1(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find1(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip1(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold2(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count2(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto2(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find2(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip2(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold3(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count3(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto3(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find3(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip3(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold4(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count4(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto4(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find4(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip4(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold5(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count5(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto5(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find5(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip5(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold6(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count6(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto6(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find6(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip6(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold7(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count7(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto7(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find7(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip7(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold8(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count8(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto8(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find8(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip8(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold9(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count9(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto9(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find9(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip9(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold10(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count10(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto10(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find10(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip10(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
  def fold11(z: A)(f: (A, A) => A): A = { var acc = z; var i = 0; while (i < xs.length) { acc = f(acc, xs(i)); i += 1 }; acc }
  def count11(p: A => Boolean): Int = { var n = 0; var i = 0; while (i < xs.length) { if (p(xs(i))) n += 1; i += 1 }; n }
  def mapInto11(out: Array[A])(f: A => A): Unit = { var i = 0; while (i < xs.length) { out(i) = f(xs(i)); i += 1 } }
  def find11(p: A => Boolean): Option[A] = { @tailrec def go(i: Int): Option[A] = if (i >= xs.length) None else if (p(xs(i))) Some(xs(i)) else go(i + 1); go(0) }
  def zip11(f: (A, B) => A): A = { var acc = xs(0); var i = 0; while (i < xs.length && i < ys.length) { acc = f(acc, ys(i)); i += 1 }; acc }
}
