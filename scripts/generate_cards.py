"""Render the profile README cards from a locally cached public snapshot."""
import argparse
from datetime import date
import json
from pathlib import Path
from textwrap import wrap
from xml.sax.saxutils import escape, quoteattr

from fetch_github_data import ROOT, SNAPSHOT
from generate_portrait import ROW_CSS, make_rows, portrait_markup, portrait_svg, source_image

OUT = ROOT / "assets/generated"
FG, MUTED, GREEN, SOFT = "#E6EDF3", "#8B949E", "#39FF88", "#7EE787"
BORDER, PANEL = "#25372F", "#0D1117"
SKILLS = {
    "Frontend": "React · JavaScript · TypeScript · HTML · CSS",
    "Backend": "Node.js · NestJS · Express · Python",
    "Databases": "PostgreSQL · MySQL",
    "Tools": "Docker · Git · GitHub · Linux",
    "Cloud": "AWS",
}
HERO_CSS = """
.command { animation: typing 850ms steps(23) both; }
.cursor-track { animation: advance 850ms steps(23) both; }
.cursor { animation: blink 700ms step-end 4 850ms; }
@keyframes typing { from { width: 0; } to { width: var(--command-width); } }
@keyframes advance { from { transform: translateX(-264px); } to { transform: translateX(0); } }
@keyframes blink { 50% { opacity: 0; } }
@media (prefers-reduced-motion: reduce) { .command, .cursor, .cursor-track { animation: none; } }
"""


def rect(x, y, w, h, fill, radius=0, stroke="none") -> str:
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
            f'fill="{fill}" stroke="{stroke}"/>')


def label(x, y, value, size=18, color=FG, weight="normal") -> str:
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
            f'font-weight="{weight}">{escape(str(value))}</text>')


def card(title: str, width: int, height: int, body: str, css: str = "",
         description: str = "", header: bool = True) -> str:
    chrome = rect(1, 1, width - 2, height - 2, "#05090D", 16, BORDER)
    if header:
        chrome += rect(14, 14, 4, 22, GREEN, 2) + label(27, 31, title, 16, SOFT)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            'role="img" aria-labelledby="title desc" font-family="monospace">'
            f'<title id="title">{escape(title)}</title><desc id="desc">{escape(description or title)}</desc>'
            f'<style>{css}</style>{chrome}{body}</svg>\n')


def hero(rows: list[bytes] | None, mobile: bool, static: bool) -> str:
    width, height = (460, 736 if rows else 510) if mobile else (800, 438)
    px, py, scale = (100, 390, .8) if mobile else (486, 53, .91)
    command_width = 264
    body = rect(22, 57, width - 44 if mobile else 440, 50, PANEL, 8)
    body += ('<defs><clipPath id="typing"><rect class="command" x="34" y="58" '
             f'width="{command_width}" height="47" style="--command-width:{command_width}px"/>'
             '</clipPath></defs><g clip-path="url(#typing)">')
    body += label(34, 88, "stevel@github:~$ whoami", 19, GREEN) + "</g>"
    body += ('<g class="cursor-track"><rect class="cursor" x="300" y="73" '
             'width="9" height="17" rx="2" fill="#39FF88"/></g>')
    body += label(26, 157, "Stevel Iglesias", 38, FG, "bold")
    body += label(27, 190, "Junior Software Developer", 22, SOFT)
    for y, value in (
        (232, "SENA | Software Analysis & Development"),
        (257, "Riwi | Coder"),
        (293, "Full Stack Development"),
        (318, "Cybersecurity & Artificial Intelligence"),
        (354, "Location: Colombia"),
        (379, "Status: Building something awesome..."),
    ):
        body += label(27, y, value, 16, MUTED if y >= 354 else FG)
    portrait = portrait_markup(rows) if rows else (
        rect(0, 0, 320, 115 if mobile else 410, "#000", 10, BORDER)
        + label(24, 44, "./portrait", 18, SOFT)
        + label(24, 78 if mobile else 200, "Source image unavailable", 18, MUTED)
    )
    body += f'<g transform="translate({px} {py}) scale({scale})">{portrait}</g>'
    css = "" if static else HERO_CSS + ROW_CSS
    return card("~/profile", width, height, body, css,
                "Stevel Iglesias, Junior Software Developer in Colombia. SENA student and Riwi Coder.")


def stats(snapshot: dict) -> str:
    data = snapshot.get("repositories", {})
    columns = (("Public repos", "public_repos"), ("Stars earned", "stars"), ("Followers", "followers"))
    body = ""
    for x, (title, key) in zip((22, 202, 382), columns):
        body += rect(x, 54, 168, 78, PANEL, 8)
        body += label(x + 12, 86, data.get(key, "—"), 27, GREEN, "bold")
        body += label(x + 12, 114, title, 15, MUTED)
    languages = list(data.get("languages", {}))[:5]
    body += label(22, 167, "Primary languages across owned repos", 16, SOFT)
    lines = wrap(" · ".join(languages) or "Data unavailable", width=44)
    for index, line in enumerate(lines):
        body += label(22, 194 + index * 20, line, 16)
    y = 222 + (len(lines) - 1) * 20
    body += label(22, y, "Recent public activity (UTC)", 16, SOFT)
    events = snapshot.get("activity")
    if events:
        for index, event in enumerate(events, 1):
            action = event["type"].removesuffix("Event")
            repo = event["repo"].split("/")[-1]
            line = f'{event["date"]}   {action:<12} {repo}'
            body += label(22, y + index * 24, line[:53], 16)
    else:
        body += label(22, y + 24, "Data unavailable" if events is None else "No recent public events", 16, MUTED)
    return card("~/github", 572, y + max(len(events or []), 1) * 24 + 21, body)


def contributions(snapshot: dict) -> str:
    calendar = snapshot.get("calendar", {})
    days = calendar.get("days", {})
    if not days:
        return card("~/contributions", 572, 112, label(22, 80, "Calendar unavailable", 20, MUTED))
    dates = sorted(date.fromisoformat(day) for day in days)
    first, last = dates[0], dates[-1]
    offset = (first.weekday() + 1) % 7
    colors = ("#17251F", "#185D38", "#23874B", "#2DC56D", GREEN)
    total = calendar.get("total")
    headline = f"{total:,} contributions" if total is not None else "GitHub contribution calendar"
    body = label(22, 68, headline, 23, FG, "bold")
    body += label(22, 91, f"{first.isoformat()} — {last.isoformat()}", 15, MUTED)
    for day in dates:
        week, weekday = divmod((day - first).days + offset, 7)
        body += rect(22 + week * 9.9, 110 + weekday * 10, 8, 8, colors[days[day.isoformat()]], 2)
    body += label(22, 202, "Daily activity · GitHub calendar", 15, MUTED)
    body += label(397, 202, "Less", 14, MUTED)
    for index, color in enumerate(colors):
        body += rect(439 + index * 12, 191, 9, 9, color, 2)
    body += label(505, 202, "More", 14, MUTED)
    return card("~/contributions", 572, 221, body, description=headline)


def skills() -> str:
    body = ""
    for index, (name, stack) in enumerate(SKILLS.items()):
        y = 53 + index * 45
        body += rect(22, y, 528, 39, PANEL, 6)
        body += label(33, y + 25, name, 16, SOFT)
        body += label(143, y + 25, stack, 15)
    return card("~/tech-stack", 572, 289, body)


def project(item: dict) -> str:
    body = label(22, 78, item["name"], 23, FG, "bold")
    body += label(22, 109, item["description"], 17)
    body += label(22, 141, item["stack"], 16, SOFT)
    if item.get("stars") is not None:
        body += label(406, 31, f'{item["stars"]} GitHub stars', 15, MUTED)
    return card("~/projects", 572, 162, body,
                description=f'{item["name"]}. {item["description"]} {item["stack"]}.')


def write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static", action="store_true", help="Render only final frames")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    image = source_image(ROOT)
    rows = make_rows(image, (.5, .38)) if image else None
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8")) if SNAPSHOT.exists() else {}
    cards = {
        "hero": hero(rows, False, args.static),
        "hero-mobile": hero(rows, True, args.static),
        "stats": stats(snapshot),
        "contributions": contributions(snapshot),
        "skills": skills(),
    }
    if rows:
        cards["portrait"] = portrait_svg(rows, args.static)
    projects = snapshot.get("repositories", {}).get("projects", [])
    links = []
    for item in projects:
        name = "project-" + item["name"].lower().replace("_", "-")
        cards[name] = project(item)
        alt = f'{item["name"]} — {item["description"]} {item["stack"]}.'
        if item.get("stars") is not None:
            alt += f' GitHub stars: {item["stars"]}.'
        links.append(f'<a href={quoteattr(item["url"])}><img src="./assets/generated/{name}.svg" '
                     f'alt={quoteattr(alt)} width="572"></a>')
    for name, svg in cards.items():
        write(args.output / f"{name}.svg", svg)
    for path in args.output.glob("project-*.svg"):
        if path.stem not in cards:
            path.unlink()
    if args.output == OUT and not args.static:
        readme = ROOT / "README.md"
        before, rest = readme.read_text(encoding="utf-8-sig").split("<!-- projects:start -->", 1)
        _, after = rest.split("<!-- projects:end -->", 1)
        listing = "\n\n".join(links) or "Featured projects unavailable."
        write(readme, f"{before}<!-- projects:start -->\n\n{listing}\n\n<!-- projects:end -->{after}")


if __name__ == "__main__":
    main()
