"""Check local README images and self-contained, accessible SVG markup."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from fetch_github_data import ROOT

SVG = "{http://www.w3.org/2000/svg}"
ALLOWED = {"svg", "title", "desc", "style", "rect", "text", "g", "defs", "clipPath", "tspan", "path", "animate"}


def validate(path: Path) -> None:
    if path.stat().st_size > 120_000:
        raise ValueError(f"{path}: SVG exceeds size budget")
    root = ET.parse(path).getroot()
    if root.tag != SVG + "svg" or not root.get("viewBox") or root.find(SVG + "title") is None:
        raise ValueError(f"{path}: missing SVG metadata")
    for node in root.iter():
        if not node.tag.startswith(SVG) or node.tag.removeprefix(SVG) not in ALLOWED:
            raise ValueError(f"{path}: unexpected element {node.tag}")
        if node.tag == SVG + "animate" and node.get("attributeName") not in {"x", "width"}:
            raise ValueError(f"{path}: unexpected animated attribute")
        for key, value in node.attrib.items():
            if key.startswith("on") or "href" in key or re.search(r"url\(\s*[^#]", value):
                raise ValueError(f"{path}: unexpected resource or handler")
        if node.tag == SVG + "style" and re.search(r"url\(|@import", node.text or "", re.I):
            raise ValueError(f"{path}: unexpected CSS resource")


def main() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    refs = re.findall(r'src(?:set)?="(\./assets/generated/[^"]+\.svg)"', readme)
    required = {"hero", "hero-mobile", "stats", "contributions", "skills"}
    if not required <= {Path(ref).stem for ref in refs}:
        raise ValueError("README is missing required cards")
    for path in {ROOT / ref for ref in refs} | set((ROOT / "assets/generated").glob("*.svg")):
        validate(path)
    print("README image references and generated SVGs validated")


if __name__ == "__main__":
    main()
