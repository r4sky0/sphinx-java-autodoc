from __future__ import annotations

import pytest
from sphinx.errors import ExtensionError
from test_integration import SOURCES, build, element, project, signature

from sphinx_java_autodoc.domain import anchor
from sphinx_java_autodoc.extractor import extract, read_model
from sphinx_java_autodoc.render import deprecated

ORACLE = "https://docs.oracle.com/en/java/javase/25/docs/api/"


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    root = tmp_path_factory.mktemp("signatures")
    out = root / "html"
    build(project(root), out)
    return out


def method_html(html, symbol):
    start = html.index('id="' + anchor(symbol) + '"')
    return html[start : html.index("</dt>", start)]


def test_signature_tokens_are_extracted(tmp_path):
    root = extract([SOURCES], [], tmp_path / "cache").root
    tokens = element(root, "demo.Widget#combine(int[][],java.lang.String[])")
    sig = tokens.find("sig")
    assert [t.tag for t in sig if t.tag not in {"t"}] == ["k", "r", "n", "params"]
    labels = [p.find("r") for p in sig.find("params")]
    assert labels[0] is None and labels[1].text == "String"
    assert labels[1].get("target") == "java.lang.String"
    assert labels[1].get("module") == "java.base"
    assert "".join(t.text for t in sig.find("params")[1]) == "String... labels"


def test_signatures_use_standard_nodes_and_link_types(site):
    html = (site / "api/type-demo.Widget.html").read_text()
    combine = method_html(html, "demo.Widget#combine(int[][],java.lang.String[])")
    assert '<span class="sig-paren">(</span>' in combine
    assert combine.count('<em class="sig-param">') == 2
    assert f'href="{ORACLE}java.base/java/lang/String.html"' in combine
    assert '<span class="sig-name descname"><span class="pre">combine</span>' in combine
    widget = method_html(html, "demo.Widget")
    assert (
        '<span class="sig-prename descclassname"><span class="pre">demo.</span>'
        in widget
    )
    assert (
        'href="type-demo.Transformer.html#' + anchor("demo.Transformer") + '"' in widget
    )


def test_long_parameter_lists_follow_the_sphinx_option(tmp_path):
    out = tmp_path / "html"
    build(project(tmp_path, extra="java_maximum_signature_line_length = 60\n"), out)
    html = (out / "api/type-demo.Widget.html").read_text()
    long = method_html(html, "demo.Widget#buildIndex(java.util.List,java.util.Map)")
    assert '<dd><em class="sig-param">' in long
    short = method_html(html, "demo.Widget#convert(int)")
    assert "<dd>" not in short


def test_only_annotations_on_the_declaration_mark_it_deprecated(tmp_path):
    source = tmp_path / "p/R.java"
    source.parent.mkdir()
    source.write_text("""package p;
/** A record. */
public record R(@Deprecated int old, int now) {
  /** Not deprecated. @param s text */
  public void m(@Deprecated String s) {}
  /** Not deprecated either. */
  public static final String TAG = "@java.lang.Deprecated";
  /** Deprecated. */
  @Deprecated
  public void gone() {}
}
""")
    root = extract([tmp_path], [], tmp_path / "cache").root
    flagged = {e.get("id") for e in root.iter() if e.get("id") and deprecated(e)}
    assert "p.R#gone()" in flagged
    assert not flagged & {
        "p.R",
        "p.R#<init>(int,int)",
        "p.R#m(java.lang.String)",
        "p.R#TAG",
    }


@pytest.mark.parametrize(
    "sig",
    [
        "<sig><script>x</script></sig>",
        "<sig><r target='java.lang.String)'>String</r></sig>",
        "<sig><r target='java.lang.String'><t>x</t></r></sig>",
        "<sig><params><t>x</t></params></sig>",
    ],
)
def test_models_with_invalid_signature_tokens_are_rejected(tmp_path, sig):
    path = extract([SOURCES], [], tmp_path / "cache").path
    text = path.read_text()
    start = text.index("<sig>")
    model = tmp_path / "bad.xml"
    model.write_text(text[:start] + sig + text[text.index("</sig>", start) + 6 :])
    with pytest.raises(ExtensionError, match="invalid model"):
        read_model(model)


def test_signatures_show_only_documented_annotations(tmp_path):
    source = tmp_path / "p/A.java"
    source.parent.mkdir()
    source.write_text("""package p;
import java.lang.annotation.*;
@Target(ElementType.TYPE_USE) @interface Plain {}
@Documented @Target(ElementType.TYPE_USE) @interface Shown {}
/** Annotated. */
public class A {
  /** Old.
   * @param s s
   * @param t t
   */
  @Deprecated @SuppressWarnings("x") public void m(@Plain String s, @Shown String t) {}
  /** Text. */ @Override public String toString() { return ""; }
}
""")
    root = extract([tmp_path], [], tmp_path / "cache").root
    sig = signature(element(root, "p.A#m(java.lang.String,java.lang.String)"))
    assert "@Deprecated" in sig and "@Shown" in sig
    assert "@SuppressWarnings" not in sig and "@Plain" not in sig
    assert "@Override" not in signature(element(root, "p.A#toString()"))


def test_signature_modifiers_match_standard_doclet(tmp_path):
    (tmp_path / "p").mkdir()
    (tmp_path / "p/M.java").write_text("""package p;
/** M. */
public class M {
  /** I. */ public interface I {
    /** C. */ int C = 1;
    /** A. @return x */ int a();
    /** D. @return x */ default int d() { return 0; }
    /** S. @return x */ static int s() { return 0; }
    /** N. */ interface Nested {}
  }
  /** Ann. */ public @interface Ann { /** V. @return v */ int v() default 1; }
  /** E. */ public enum E { /** X. */ X; /** F. @return f */ public final int f() { return 0; } }
  /** Sealed. */ protected static sealed abstract class S permits T {}
  /** T. */ protected static final class T extends S {}
  /** R. @param x x */ public record R(int x) {
    /** Sm. */ public static synchronized strictfp void m() {}
  }
  /** Nat. */ public native void nat();
  /** Tv. */ public transient volatile int tv;
}
""")
    (tmp_path / "p/Top.java").write_text(
        "package p;\n/** Top. */\npublic abstract interface Top {}\n"
    )
    root = extract([tmp_path], [], tmp_path / "cache").root

    def modifiers(symbol):
        tokens = [t for t in element(root, symbol).find("sig") if t.tag != "t"]
        words = []
        for token in tokens:
            if token.tag != "k" or token.text in {
                "class",
                "interface",
                "enum",
                "record",
                "@interface",
            }:
                break
            words.append(token.text)
        return " ".join(words)

    # As printed by the standard doclet for the same source.
    assert {
        symbol: modifiers(symbol)
        for symbol in (
            "p.M.I",
            "p.M.I#C",
            "p.M.I#a()",
            "p.M.I#d()",
            "p.M.I#s()",
            "p.M.I.Nested",
            "p.M.Ann",
            "p.M.Ann#v()",
            "p.M.E",
            "p.M.E#X",
            "p.M.E#f()",
            "p.M.S",
            "p.M.T",
            "p.M.R",
            "p.M.R#m()",
            "p.M#nat()",
            "p.M#tv",
            "p.Top",
        )
    } == {
        "p.M.I": "public static",
        "p.M.I#C": "static final",
        "p.M.I#a()": "",
        "p.M.I#d()": "default",
        "p.M.I#s()": "static",
        "p.M.I.Nested": "public static",
        "p.M.Ann": "public static",
        "p.M.Ann#v()": "",
        "p.M.E": "public static",
        "p.M.E#X": "public static final",
        "p.M.E#f()": "public final",
        "p.M.S": "protected abstract static sealed",
        "p.M.T": "protected static final",
        "p.M.R": "public static",
        "p.M.R#m()": "public static",
        "p.M#nat()": "public",
        "p.M#tv": "public transient volatile",
        "p.Top": "public",
    }
    assert element(root, "p.M.I#a()").get("visibility") == "public"
