"""External Javadoc links: symbols documented on another site's standard Javadoc."""

from __future__ import annotations

from urllib.parse import quote, urlsplit

from sphinx.errors import ExtensionError


def check_mapping(mapping: dict[str, str]) -> None:
    """Validates ``java_external_javadoc`` once, before any link is resolved."""
    for prefix, url in mapping.items():
        if not prefix or urlsplit(url).scheme not in {"http", "https"}:
            raise ExtensionError(
                "java_external_javadoc must map package prefixes to http(s) Javadoc roots."
            )


def external_url(
    target: str, spelling: str, metadata: dict[str, str], mapping: dict[str, str]
) -> str | None:
    """The Javadoc URL for a canonical ``target`` under the longest matching prefix.

    ``metadata`` is the compiler's path, fragment and module for the target; without
    it, the URL is derived from the reference ``spelling``, whose type starts at the
    first capitalized name, or else right after the prefix.
    """
    for prefix, base in sorted(mapping.items(), key=lambda item: -len(item[0])):
        if target != prefix and not target.startswith(prefix.rstrip(".") + "."):
            continue
        if metadata.get("path"):
            path = metadata["path"]
            fragment = metadata.get("fragment", "")
            base = base.replace("{module}", metadata.get("module", ""))
        else:
            if "{module}" in base:
                continue
            owner, _, fragment = spelling.partition("#")
            names = owner.split(".")
            # By Java naming convention, the type starts at the first capitalized name.
            start = next(
                (i for i, name in enumerate(names) if name[:1].isupper()),
                prefix.rstrip(".").count(".") + 1,
            )
            path = "/".join(names[:start] + [".".join(names[start:]) + ".html"])
        url = base.rstrip("/") + "/" + quote(path, safe="/.$")
        if fragment:
            url += "#" + quote(fragment, safe="(),.[]$")
        return url
    return None
