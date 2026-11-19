"""Render the GitHub profile dashboard from its verified local snapshot."""

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from fetch_github_data import ROOT, SNAPSHOT
from generate_portrait import (
    ROW_CSS,
    make_rows,
    portrait_markup,
    portrait_svg,
    source_image,
)

OUT = ROOT / "assets/generated"
BG, PANEL = "#05090D", "#0D1117"
FG, MUTED, GREEN, SOFT = "#E6EDF3", "#8B949E", "#39FF88", "#7EE787"
RULE, EDGE = "#1A382C", "#286747"
DESKTOP, MOBILE = 920, 390
FONT = "'Cascadia Mono',Consolas,'Liberation Mono',Menlo,monospace"
MOTION = """
@media (prefers-reduced-motion:no-preference) {
 .entry{animation:appear .46s ease-out both}
 .bar{transform-box:fill-box;transform-origin:left;animation:grow .65s ease-out both}
 .command{animation:type .64s steps(6,end) both}
 .cursor-track{animation:advance .64s steps(6,end) both}
 .cursor{animation:blink .8s step-end 4 .64s}
}
@keyframes appear{from{opacity:0}to{opacity:1}}
@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes type{from{width:0}to{width:3.6em}}
@keyframes advance{from{transform:translateX(-3.6em)}to{transform:translateX(0)}}
@keyframes blink{50%{opacity:0}}
"""
ICONS = {
    "term": "M3 5l6 6-6 6 M12 17h8",
    "repo": "M5 3h14v18H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2 M4 17h15 M9 4v6l2-1 2 1V4",
    "star": "m12 2 3.1 6.4 7 .9-5 4.9 1.1 7-6.2-3.3-6.2 3.3 1.1-7-5-4.9 7-.9z",
    "people": "M13 8a4 4 0 1 1-8 0 4 4 0 1 1 8 0 M2 20v-2a6 6 0 0 1 12 0v2 M16 4a4 4 0 0 1 0 8 M17 15q5 0 5 5",
    "pin": "M12 21S4 13 4 9a8 8 0 0 1 16 0c0 4-8 12-8 12z M14.5 9a2.5 2.5 0 1 1-5 0 2.5 2.5 0 1 1 5 0",
    "branch": "M6 8v9 M9 16c8 0 9-3 9-7 M8 5a2.5 2.5 0 1 1-5 0 2.5 2.5 0 1 1 5 0 M8 20a2.5 2.5 0 1 1-5 0 2.5 2.5 0 1 1 5 0 M20 6a2.5 2.5 0 1 1-5 0 2.5 2.5 0 1 1 5 0",
    "layers": "m2 7 10-5 10 5-10 5z M2 12l10 5 10-5 M2 17l10 5 10-5",
    "bars": "M3 5h17 M3 11h13 M3 17h7",
    "arrow": "M5 18 18 5 M6 5h12v12",
}
STACK = [
    ("Frontend", "React · JavaScript · TypeScript · HTML · CSS"),
    ("Backend", "Node.js · NestJS · Express · Python"),
    ("Datos", "PostgreSQL · MySQL · Supabase"),
    ("DevOps", "Docker · Git · GitHub · Linux · AWS"),
    ("Herramientas", "Postman"),
]


def rect(x, y, w, h, fill, radius=0, stroke="none") -> str:
    return (
        f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="{radius}" '
        f'fill="{fill}" stroke="{stroke}"/>'
    )


def label(x, y, value, size=16, color=FG, weight=400, end=False) -> str:
    anchor = "end" if end else "start"
    return (
        f'<text x="{x:g}" y="{y:g}" fill="{color}" font-size="{size}" '
        f'font-weight="{weight}" text-anchor="{anchor}">{escape(str(value))}</text>'
    )


def line(x1, y1, x2, y2, color=RULE) -> str:
    return f'<path d="M{x1:g} {y1:g}L{x2:g} {y2:g}" fill="none" stroke="{color}"/>'


def icon(name, x, y, size=18, color=GREEN) -> str:
    return (
        f'<path d="{ICONS[name]}" transform="translate({x:g} {y:g}) scale({size / 24:.4f})" '
        f'fill="none" stroke="{color}" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round"/>'
    )


def svg(title, width, height, body, description="", css="") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-labelledby="title desc" font-family="{FONT}">'
        f'<title id="title">{escape(title)}</title><desc id="desc">{escape(description or title)}</desc>'
        f"<style>{css}</style>{body}</svg>\n"
    )


def frame(w, h) -> str:
    return rect(1, 1, w - 2, h - 2, BG, 12, EDGE)


def section(title, glyph, x, y) -> str:
    return icon(glyph, x, y - 16, 18) + label(x + 28, y, title, 20, FG, 700)


def prompt(x, baseline, size) -> str:
    # Set glyph advance explicitly so the cursor also tracks fallback fonts.
    step = size * 0.6
    start = 17 * step
    command = 6 * step
    return (
        f'<g transform="translate({x} {baseline})" font-size="{size}">'
        f'<text fill="{SOFT}" textLength="{16 * step}" lengthAdjust="spacingAndGlyphs">stevel@github:~$</text>'
        f'<defs><clipPath id="typed"><rect class="command" x="{start}" y="{-size}" '
        f'width="{command}" height="{size * 1.4}"/></clipPath></defs>'
        f'<text clip-path="url(#typed)" x="{start}" fill="{FG}" textLength="{command}" '
        'lengthAdjust="spacingAndGlyphs">whoami</text>'
        f'<g class="cursor-track"><rect class="cursor" x="{start + command + 2}" y="{-size * 0.8}" '
        f'width="5" height="{size}" fill="{GREEN}"/></g></g>'
    )


def hero(rows: list[bytes] | None, mobile: bool, static: bool) -> str:
    w, h = (MOBILE, 311) if mobile else (DESKTOP, 303)
    body = (
        frame(w, h)
        + icon("term", 19, 13, 17)
        + label(45, 26, "levets01 / profile.sh", 13, MUTED)
    )
    body += icon("pin", w - 115, 12, 15, SOFT) + label(
        w - 21, 25, "Colombia", 13, FG, end=True
    )
    body += line(1, 39, w - 1, 39)
    px, py, scale = (17, 57, 0.44) if mobile else (37, 64, 0.82)
    pw, ph = 224 * scale, 246 * scale
    for x, y, dx, dy in [
        (px, py, 1, 1),
        (px + pw, py, -1, 1),
        (px, py + ph, 1, -1),
        (px + pw, py + ph, -1, -1),
    ]:
        body += f'<path d="M{x + dx * 10:g} {y:g}H{x:g}v{dy * 10}" fill="none" stroke="#39FF88" stroke-opacity=".75"/>'
    if rows:
        body += f'<g transform="translate({px} {py}) scale({scale})">{portrait_markup(rows)}</g>'
    if not mobile:
        body += label(px, 285, "IMG_2087.jpg", 12, MUTED) + line(244, 59, 244, 280)
    x = 131 if mobile else 276
    body += prompt(x, 79 if mobile else 83, 13 if mobile else 16)
    body += '<g class="entry">'
    body += label(
        x, 114 if mobile else 143, "Stevel Iglesias", 25 if mobile else 48, FG, 700
    )
    body += label(
        x,
        140 if mobile else 174,
        "Junior Software Developer",
        14 if mobile else 21,
        GREEN,
    )
    x = 19 if mobile else x
    y = 198 if mobile else 211
    body += label(x, y, "SENA", 14, SOFT, 700) + label(
        x + 56, y, "Tecnólogo en formación en ADSO", 15
    )
    body += label(x, y + 24, "Riwi", 14, SOFT, 700) + label(x + 56, y + 24, "Coder", 15)
    body += line(x, y + 39, w - 22, y + 39)
    if mobile:
        body += label(x, 263, "Full Stack Development", 14, FG)
        body += label(x, 286, "Cybersecurity & Artificial Intelligence", 14, FG)
    else:
        body += label(x, 278, "Full Stack Development", 15, FG)
        body += label(x + 219, 278, "/", 15, GREEN) + label(
            x + 242, 278, "Cybersecurity & Artificial Intelligence", 15, FG
        )
    return svg(
        "Stevel Iglesias",
        w,
        h,
        body + "</g>",
        "Junior Software Developer en Colombia. SENA ADSO y Riwi Coder.",
        "" if static else ROW_CSS + MOTION,
    )


def stats(snapshot: dict, mobile=False, static=False) -> str:
    data = snapshot.get("repositories", {})
    w, h = (MOBILE, 92) if mobile else (DESKTOP, 88)
    gap = 8 if mobile else 12
    tile = (w - 2 * gap) / 3
    parts = []
    for i, (name, key, glyph) in enumerate(
        [
            ("Repos públicos", "public_repos", "repo"),
            ("Estrellas", "stars", "star"),
            ("Seguidores", "followers", "people"),
        ]
    ):
        x = i * (tile + gap)
        parts.append(rect(x + 1, 1, tile - 2, h - 2, BG, 10, EDGE))
        if not mobile:
            parts.append(rect(x + 11, 13, 42, 42, PANEL, 8, RULE))
        parts.append(
            icon(
                glyph,
                x + 13 if mobile else x + 20,
                15 if mobile else 22,
                16 if mobile else 23,
            )
        )
        parts.append(
            label(
                x + 13 if mobile else x + 60,
                56 if mobile else 47,
                data.get(key, "—"),
                29 if mobile else 34,
                FG,
                700,
            )
        )
        parts.append(
            label(
                x + 13 if mobile else x + 61,
                77 if mobile else 69,
                name,
                12 if mobile else 15,
                MUTED,
            )
        )
    return svg(
        "Estadísticas de GitHub",
        w,
        h,
        '<g class="entry">' + "".join(parts) + "</g>",
        css="" if static else MOTION,
    )


MONTHS = [
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
]
LEVELS = ("#14251D", "#16452F", "#20794B", "#28B965", GREEN)


def contributions(snapshot: dict, mobile=False, static=False) -> str:
    calendar = snapshot.get("calendar", {})
    days = calendar.get("days", {})
    w = MOBILE if mobile else DESKTOP
    if not days:
        return svg(
            "Contribuciones",
            w,
            94,
            frame(w, 94) + label(20, 54, "Calendario no disponible"),
        )
    dates = sorted(date.fromisoformat(day) for day in days)
    first, last = dates[0], dates[-1]
    sunday = first - timedelta(days=(first.weekday() + 1) % 7)
    weeks = (last - sunday).days // 7 + 1
    per_band = (weeks + 1) // 2 if mobile else weeks
    step = (w - (64 if mobile else 86)) / per_band
    top, band_height = (93, 122) if mobile else (93, 135)
    h = top + band_height * (2 if mobile else 1) + 10
    body = frame(w, h) + section("Contribuciones", "branch", 20, 33)
    count = calendar.get("total")
    body += label(
        20,
        57,
        f"{count:,} contribuciones" if count is not None else "Calendario público",
        14,
        SOFT,
    )
    body += label(
        w - 20,
        57 if mobile else 34,
        f"{first:%d.%m.%y} – {last:%d.%m.%y}",
        12 if mobile else 14,
        MUTED,
        end=True,
    )
    for band in range(2 if mobile else 1):
        y = top + band * band_height
        origin = 46 if mobile else 54
        vertical = 11 if mobile else 14
        for index, dayname in ((1, "Lu"), (3, "Mi"), (5, "Vi")):
            body += label(
                17 if mobile else 21, y + vertical * index + 8, dayname, 11, MUTED
            )
        prior = None
        last_label = -4
        for j in range(min(per_band, weeks - band * per_band)):
            week = j + band * per_band
            start = sunday + timedelta(weeks=week)
            mid = max(start, first)
            if prior != mid.month and j - last_label >= 3 and j < per_band - 1:
                body += label(
                    origin + step * j, y - 8, MONTHS[mid.month - 1], 11, MUTED
                )
                last_label = j
            prior = mid.month
            for k in range(7):
                day = (start + timedelta(days=k)).isoformat()
                if day in days:
                    body += rect(
                        origin + j * step,
                        y + k * vertical,
                        step - 2.8,
                        vertical - 2.5,
                        LEVELS[days[day]],
                        2,
                    )
        if not static:
            # Uncover the existing data. Zero base width is the motionless fallback.
            span = step * min(per_band, weeks - band * per_band)
            body += (
                f'<rect class="calendar-reveal" x="{origin}" y="{y}" width="0" '
                f'height="{7 * vertical}" fill="{BG}" opacity=".72">'
                f'<animate attributeName="x" from="{origin}" to="{origin + span:g}" dur=".9s"/>'
                f'<animate attributeName="width" from="{span:g}" to="0" dur=".9s"/></rect>'
            )
    body += label(20, h - 13, "Menos", 11, MUTED)
    for i, color in enumerate(LEVELS):
        body += rect(59 + i * 13, h - 22, 10, 10, color, 2)
    body += label(130, h - 13, "Más", 11, MUTED)
    css = (
        ""
        if static
        else "@media (prefers-reduced-motion:reduce){.calendar-reveal{display:none}}"
    )
    return svg(
        "Contribuciones de GitHub", w, h, body, f"Actividad de {first} a {last}", css
    )


def technology(snapshot: dict, mobile=False, static=False) -> str:
    w = MOBILE if mobile else DESKTOP
    left = MOBILE if mobile else 472
    right = MOBILE if mobile else w - left - 12
    panel_h = 290
    x2, y2 = (0, panel_h + 10) if mobile else (left + 12, 0)
    body = frame(left, panel_h) + section("Tecnologías", "layers", 20, 35)
    for i, (name, stack) in enumerate(STACK):
        y = 63 + i * 46
        body += label(20, y, name, 12, SOFT, 700) + label(
            20, y + 19, stack, 14 if mobile else 15
        )
        if i < len(STACK) - 1:
            body += line(20, y + 27, left - 20, y + 27)
    body += (
        f'<g transform="translate({x2} {y2})">'
        + frame(right, panel_h)
        + section("Lenguajes", "bars", 20, 35)
    )
    counts = snapshot.get("repositories", {}).get("languages", {})
    total = sum(counts.values())
    items = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    if len(items) > 6:
        items = items[:5] + [("Otros", sum(n for _, n in items[5:]))]
    body += label(
        20,
        61,
        f"Lenguaje principal · {total} repos con datos"
        if total
        else "Datos no disponibles",
        13,
        MUTED,
    )
    if total:
        bar_width = right - 195
        for i, (lang, count) in enumerate(items):
            y = 91 + i * 27
            share = count / total
            body += label(20, y, lang, 14, FG)
            body += rect(116, y - 9, bar_width, 7, RULE, 3)
            body += (
                '<g class="bar">'
                + rect(116, y - 9, bar_width * share, 7, GREEN if i == 0 else SOFT, 3)
                + "</g>"
            )
            body += label(right - 17, y, f"{share * 100:.1f}%", 14, FG, end=True)
        body += label(20, 259, "% de repositorios públicos propios", 13, MUTED)
        body += label(
            20, 277, "con lenguaje identificado, excluidos los forks.", 12, MUTED
        )
    return svg(
        "Tecnologías y lenguajes",
        w,
        panel_h + y2,
        body + "</g>",
        css="" if static else MOTION,
    )


def project(item: dict, mobile=False) -> str:
    w, h = (MOBILE, 118) if mobile else (DESKTOP, 91)
    body = frame(w, h)
    body += icon(
        "repo", 17 if mobile else 22, 18 if mobile else 30, 18 if mobile else 26
    )
    x = 44 if mobile else 67
    body += label(x, 32 if mobile else 38, item["name"], 16 if mobile else 21, FG, 700)
    body += label(
        17 if mobile else x,
        59 if mobile else 65,
        item["description"],
        14 if mobile else 15,
        MUTED,
    )
    stack = item["stack"].split(" · ")
    if mobile:
        body += label(17, 92, " · ".join(stack), 13, SOFT)
    else:
        body += label(w - 86, 64, " · ".join(stack), 13, SOFT, end=True)
    if item.get("stars") is not None:
        body += icon("star", w - 65, 17, 14, SOFT) + label(
            w - 44, 29, item["stars"], 13, FG
        )
    body += icon("arrow", w - 29, 16, 14, MUTED)
    desc = item["description"] + " " + item["stack"]
    if item.get("stars") is not None:
        desc += f". {item['stars']} GitHub stars."
    return svg(item["name"], w, h, body, desc)


def picture(name: str, alt: str) -> str:
    base = f"./assets/generated/{name}"
    return (
        f'<picture>\n  <source media="(max-width: 760px)" srcset="{base}-mobile.svg">\n'
        f'  <img src="{base}.svg" width="100%" alt={quoteattr(alt)}>\n</picture>'
    )


def write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--static", action="store_true", help="Render final frames without animation"
    )
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    image = source_image(ROOT)
    rows = make_rows(image, (0.5, 0.38)) if image else None
    mobile_rows = make_rows(image, (0.5, 0.38), (60, 66)) if image else None
    snapshot = (
        json.loads(SNAPSHOT.read_text(encoding="utf-8")) if SNAPSHOT.exists() else {}
    )
    data = snapshot.get("repositories", {})
    cards = {}
    projects = data.get("projects", [])
    for mobile, suffix in ((False, ""), (True, "-mobile")):
        cards["hero" + suffix] = hero(
            mobile_rows if mobile else rows, mobile, args.static
        )
        cards["stats" + suffix] = stats(snapshot, mobile, args.static)
        cards["contributions" + suffix] = contributions(snapshot, mobile, args.static)
        cards["skills" + suffix] = technology(snapshot, mobile, args.static)
        for item in projects:
            key = "project-" + item["name"].lower().replace("_", "-")
            cards[key + suffix] = project(item, mobile)
    if rows:
        cards["portrait"] = portrait_svg(rows, args.static)
        cards["portrait-static"] = portrait_svg(rows, True)
    for name, source in cards.items():
        write(args.output / f"{name}.svg", source)
    for path in args.output.glob("project-*.svg"):
        if path.stem not in cards:
            path.unlink()
    if args.output == OUT and not args.static:
        readme = ROOT / "README.md"
        before, rest = readme.read_text(encoding="utf-8").split(
            "<!-- dashboard:start -->", 1
        )
        _, after = rest.split("<!-- dashboard:end -->", 1)
        total = snapshot.get("calendar", {}).get("total")
        stack_alt = ". ".join(f"{category}: {names}" for category, names in STACK)
        views = [
            picture(
                "hero",
                "Stevel Iglesias | Junior Software Developer | SENA ADSO en formación | Riwi Coder | Full Stack & Cybersecurity | Colombia.",
            ),
            picture(
                "stats",
                f"Repositorios públicos: {data.get('public_repos', '—')}. Estrellas recibidas: {data.get('stars', '—')}. Seguidores: {data.get('followers', '—')}.",
            ),
            picture(
                "contributions",
                f"Calendario anual de GitHub. Contribuciones: {total if total is not None else 'dato no disponible'}.",
            ),
            picture(
                "skills",
                stack_alt
                + ". Repositorios públicos propios sin forks por lenguaje principal: "
                + ", ".join(
                    f"{lang} ({n})" for lang, n in data.get("languages", {}).items()
                )
                + ".",
            ),
            "### Proyectos destacados",
        ]
        for item in projects:
            name = "project-" + item["name"].lower().replace("_", "-")
            alt = f"{item['name']}. {item['description']} {item['stack']}."
            if item.get("stars") is not None:
                alt += f" {item['stars']} GitHub stars."
            views.append(
                f"<a href={quoteattr(item['url'])}>\n{picture(name, alt)}\n</a>"
            )
        if not projects:
            views.append("Proyectos no disponibles.")
        activity = snapshot.get("activity")
        details = ["<details>", "<summary>Actividad pública reciente</summary>", ""]
        for event in activity or []:
            details.append(
                f"- {event['date']} UTC · {event['type'].removesuffix('Event')} · {escape(event['repo'])}"
            )
        if not activity:
            details.append(
                "Sin eventos recientes." if activity == [] else "Datos no disponibles."
            )
        views.append("\n".join([*details, "", "</details>"]))
        write(
            readme,
            before
            + "<!-- dashboard:start -->\n\n"
            + "\n\n".join(views)
            + "\n\n<!-- dashboard:end -->"
            + after,
        )


if __name__ == "__main__":
    main()
