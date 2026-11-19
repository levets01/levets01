"""Render the GitHub profile dashboard from its verified local snapshot."""

import argparse
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from textwrap import wrap
from xml.sax.saxutils import escape, quoteattr

from fetch_github_data import ROOT, SNAPSHOT
from generate_portrait import (
    PORTRAIT_CSS,
    Portrait,
    portrait_svg,
    sample_portrait,
    source_image,
)

OUT = ROOT / "assets/generated"
BG, PANEL = "#05090D", "#0D1117"
FG, MUTED, GREEN, SOFT = "#E6EDF3", "#8B949E", "#00FF88", "#A7F3D0"
RULE, EDGE = "#1A382C", "#286747"
DESKTOP, MOBILE = 920, 390
FONT = "'Cascadia Mono',Consolas,'Liberation Mono',Menlo,monospace"
MOTION = """
@media (prefers-reduced-motion:no-preference) {
 .entry{animation:appear .52s ease-out var(--at,0s) both}
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
    ("Bases de datos", "PostgreSQL · MySQL · Supabase"),
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


def prompt(x, baseline, size, compact=False) -> str:
    # Set glyph advance explicitly so the cursor also tracks fallback fonts.
    step = size * 0.6
    prefix = "$" if compact else "stevel@github:~$"
    start = (len(prefix) + 1) * step
    command = 6 * step
    return (
        f'<g transform="translate({x} {baseline})" font-size="{size}">'
        f'<text fill="{SOFT}" textLength="{len(prefix) * step}" lengthAdjust="spacingAndGlyphs">{prefix}</text>'
        f'<defs><clipPath id="typed"><rect class="command" x="{start}" y="{-size}" '
        f'width="{command}" height="{size * 1.4}"/></clipPath></defs>'
        f'<text clip-path="url(#typed)" x="{start}" fill="{FG}" textLength="{command}" '
        'lengthAdjust="spacingAndGlyphs">whoami</text>'
        f'<g class="cursor-track"><rect class="cursor" x="{start + command + 2}" y="{-size * 0.8}" '
        f'width="5" height="{size}" fill="{GREEN}"/></g></g>'
    )


def appear(content, delay):
    return f'<g class="entry" style="--at:{delay:.2f}s">{content}</g>'


def hero(portrait: Portrait, mobile: bool, static: bool) -> str:
    w, h = (MOBILE, 436) if mobile else (DESKTOP, 366)
    body = frame(w, h) + icon("term", 19, 14, 16)
    body += label(45, 27, "levets01 / profile.sh", 13, MUTED)
    body += icon("pin", w - 111, 13, 15, SOFT) + label(
        w - 18, 26, "Colombia", 13, FG, end=True
    )
    body += line(1, 42, w - 1, 42) + rect(20, 41, 74, 2, GREEN)
    px, py, pw, ph = (17, 57, 167, 184) if mobile else (26, 57, 262, 290)
    scale = min(pw / portrait.width, ph / portrait.height)
    body += (
        '<defs><radialGradient id="phosphor" cx=".50" cy=".45" r=".69">'
        '<stop offset="0" stop-color="#0D2119"/>'
        f'<stop offset="1" stop-color="{BG}"/></radialGradient></defs>'
    )
    body += rect(px, py, pw, ph, "url(#phosphor)", 4)
    for x, y, dx, dy in (
        (px, py, 1, 1),
        (px + pw, py, -1, 1),
        (px, py + ph, 1, -1),
        (px + pw, py + ph, -1, -1),
    ):
        body += (
            f'<path d="M{x + dx * 10} {y}H{x}v{dy * 10}" fill="none" stroke="{SOFT}"/>'
        )
    body += (
        f'<g transform="translate({px + (pw - portrait.width * scale) / 2:.2f} '
        f'{py + (ph - portrait.height * scale) / 2:.2f}) scale({scale:.5f})">{portrait.markup}</g>'
    )
    if not mobile:
        body += line(310, 59, 310, h - 22)
    x = 201 if mobile else 337
    body += prompt(x, 84 if mobile else 87, 15, compact=mobile)
    if mobile:
        name = label(x, 128, "Stevel", 33, FG, 700) + label(
            x, 165, "Iglesias", 33, SOFT, 700
        )
        role = label(x, 202, "Junior Software", 15, GREEN) + label(
            x, 223, "Developer", 15, GREEN
        )
    else:
        name = label(x, 150, "Stevel Iglesias", 51, FG, 700)
        role = label(x, 181, "Junior Software Developer", 21, GREEN)
    body += appear(name, 0.62) + appear(role, 0.83)
    x, y = (18, 273) if mobile else (337, 216)
    body += line(x, y - 15, w - 20, y - 15)
    education = label(x, y + 7, "SENA", 13, SOFT, 700)
    if mobile:
        education += label(x + 52, y + 7, "Tecnología en Análisis y Desarrollo", 13)
        education += label(x + 52, y + 25, "de Software (en formación)", 13)
    else:
        education += label(
            x + 58, y + 7, "Tecnología en Análisis y Desarrollo de Software", 15
        )
        education += label(x + 58, y + 28, "(en formación)", 14, MUTED)
    body += appear(education, 1.02)
    body += appear(
        label(x, y + 56, "Riwi", 13, SOFT, 700)
        + label(x + (52 if mobile else 58), y + 56, "Coder", 15),
        1.19,
    )
    body += line(x, y + 73, w - 20, y + 73)
    interests = (
        [
            "Full Stack · Ciberseguridad defensiva",
            "Inteligencia artificial · Automatización",
            "Cloud computing",
        ]
        if mobile
        else [
            "Full Stack · Ciberseguridad defensiva",
            "Inteligencia artificial · Automatización · Cloud computing",
        ]
    )
    body += appear(
        "".join(
            label(x, y + 97 + i * 21, text, 13 if mobile else 15, SOFT)
            for i, text in enumerate(interests)
        ),
        1.38,
    )
    return svg(
        "Stevel Iglesias",
        w,
        h,
        body,
        "Junior Software Developer en Colombia. SENA y Riwi. Retrato vectorial a partir de su fotografía.",
        "" if static else PORTRAIT_CSS + MOTION,
    )


def stats(snapshot: dict, mobile=False, static=False) -> str:
    data = snapshot.get("repositories", {})
    metrics = (
        ("Repos públicos", data.get("public_repos"), "repo"),
        ("Estrellas", data.get("stars"), "star"),
        ("Seguidores", data.get("followers"), "people"),
        ("Contribuciones", snapshot.get("calendar", {}).get("total"), "branch"),
    )
    w, cols, gap, tile_h = (MOBILE, 2, 8, 76) if mobile else (DESKTOP, 4, 10, 88)
    tile = (w - (cols - 1) * gap) / cols
    body = ""
    for i, (name, value, glyph) in enumerate(metrics):
        x, y = (i % cols) * (tile + gap), (i // cols) * (gap + tile_h)
        body += rect(x + 1, y + 1, tile - 2, tile_h - 2, BG, 9, EDGE)
        body += icon(glyph, x + 14, y + 17, 19)
        body += appear(
            label(x + 46, y + 39, "—" if value is None else value, 31, FG, 700)
            + label(x + 15, y + tile_h - 14, name, 14, MUTED),
            i * 0.12,
        )
    return svg(
        "Estadísticas de GitHub",
        w,
        tile_h * 2 + gap if mobile else tile_h,
        body,
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


def activity_summary(days: dict[str, int]) -> tuple[int, int]:
    active = longest = streak = 0
    previous = None
    for key, level in sorted(days.items()):
        day = date.fromisoformat(key)
        if level:
            active += 1
            streak = streak + 1 if previous == day - timedelta(days=1) else 1
            longest = max(longest, streak)
        else:
            streak = 0
        previous = day
    return active, longest


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
    origin = 46 if mobile else 230
    step = (w - origin - 19) / per_band
    top, band_height = (145, 111) if mobile else (88, 120)
    h = top + band_height * (2 if mobile else 1) + 10
    body = frame(w, h) + section("Contribuciones", "branch", 20, 33)
    count = calendar.get("total")
    active, streak = activity_summary(days)
    summary = f"{count} contribuciones" if count is not None else "Total no disponible"
    summary += f". {active} días activos. Mejor racha de {streak} días en el periodo."
    body += label(
        w - 20,
        32,
        f"{first:%d.%m.%y} – {last:%d.%m.%y}",
        11 if mobile else 14,
        MUTED,
        end=True,
    )
    body += line(20, 47, w - 20, 47)
    if mobile:
        for x, value, caption in (
            (20, count, "Contribuciones"),
            (159, active, "Días activos"),
            (285, f"{streak} d", "Mejor racha"),
        ):
            body += label(
                x,
                84,
                "—" if value is None else value,
                28,
                GREEN if x == 20 else FG,
                700,
            )
            body += label(x, 105, caption, 12, MUTED)
    else:
        body += label(20, 103, "—" if count is None else count, 43, GREEN, 700)
        body += label(20, 130, "contribuciones", 15, MUTED)
        body += line(20, 141, 172, 141) + line(188, 61, 188, h - 18)
        body += label(20, 166, active, 17, FG, 700) + label(
            66, 166, "días activos", 13, MUTED
        )
        body += label(20, 191, f"{streak} d", 16, FG, 700) + label(
            77, 191, "mejor racha", 13, MUTED
        )
    for band in range(2 if mobile else 1):
        y = top + band * band_height
        vertical = 11 if mobile else 14
        for index, dayname in ((1, "Lu"), (3, "Mi"), (5, "Vi")):
            body += label(origin - 28, y + vertical * index + 8, dayname, 11, MUTED)
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
            cells = []
            for k in range(7):
                day = (start + timedelta(days=k)).isoformat()
                if day in days:
                    cells.append(
                        rect(
                            origin + j * step,
                            y + k * vertical,
                            step - 2.8,
                            vertical - 2.5,
                            LEVELS[days[day]],
                            2,
                        )
                    )
            column = "".join(cells)
            body += column if static else appear(column, week * 0.018)
    legend = w - 153
    body += label(legend, h - 13, "Menos", 11, MUTED)
    for i, color in enumerate(LEVELS):
        body += rect(legend + 37 + i * 13, h - 22, 10, 10, color, 2)
    body += label(legend + 105, h - 13, "Más", 11, MUTED)
    css = "" if static else MOTION
    return svg(
        "Contribuciones de GitHub",
        w,
        h,
        body,
        f"Actividad de {first} a {last}. {summary}",
        css,
    )


def technology(snapshot: dict, mobile=False, static=False) -> str:
    w = MOBILE if mobile else DESKTOP
    left = MOBILE if mobile else 472
    right = MOBILE if mobile else w - left - 12
    logos = json.loads(
        (ROOT / "assets/technology-logos.json").read_text(encoding="utf-8")
    )
    stack_panel = section("Tecnologías", "layers", 20, 35)
    y = 63
    for i, (name, stack) in enumerate(STACK):
        stack_panel += label(20, y, name, 13, SOFT, 700)
        x, baseline = 20, y + 24
        for tech in stack.split(" · "):
            width = 24 + len(tech) * 8
            if x + width > left - 14:
                x, baseline = 20, baseline + 25
            logo = logos[tech]
            stack_panel += (
                f'<path aria-hidden="true" transform="translate({x} {baseline - 15}) scale(.75)" '
                f'fill="{logo["color"]}" d="{logo["path"]}"/>'
            )
            stack_panel += label(x + 24, baseline, tech, 13)
            x += width + 11
        y = baseline + 32
        if i + 1 < len(STACK):
            stack_panel += line(20, baseline + 13, left - 20, baseline + 13)
    stack_height = y - 9
    panel_h = 290 if mobile else stack_height
    x2, y2 = (0, stack_height + 10) if mobile else (left + 12, 0)
    body = frame(left, stack_height) + stack_panel
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
        body += label(right - 75, 85, "Repos", 12, MUTED, end=True)
        body += label(right - 17, 85, "Cuota", 12, MUTED, end=True)
        bar_width = right - 225
        for i, (lang, count) in enumerate(items):
            y = 106 + i * ((panel_h - 165) / 5)
            share = count / total
            body += label(20, y, lang, 14, FG)
            body += rect(116, y - 9, bar_width, 7, RULE, 3)
            body += (
                '<g class="bar">'
                + rect(116, y - 9, bar_width * share, 7, GREEN if i == 0 else SOFT, 3)
                + "</g>"
            )
            body += label(right - 17, y, f"{share * 100:.1f}%", 14, FG, end=True)
            body += label(right - 75, y, count, 14, SOFT, end=True)
        body += label(20, panel_h - 31, "% de repositorios públicos propios", 13, MUTED)
        body += label(
            20,
            panel_h - 13,
            "con lenguaje identificado, excluidos los forks.",
            12,
            MUTED,
        )
    return svg(
        "Tecnologías y lenguajes",
        w,
        panel_h + y2,
        body + "</g>",
        css="" if static else MOTION,
    )


def office_drawing(x: int, y: int, scale: float) -> str:
    """Original isometric illustration for Turno's virtual workspace."""
    parts = [
        f'<g transform="translate({x} {y}) scale({scale})" stroke-linejoin="round" stroke-linecap="round">',
        '<path d="m4 72 83-44 86 42-85 49z" fill="#10291D" stroke="#348057"/>',
        '<path d="m4 72 84 47 85-49v5l-85 49L4 77z" fill="#0B1D15" stroke="#286747"/>',
    ]
    for i in range(1, 6):
        parts.append(line(4 + 14 * i, 72 - 7.4 * i, 88 + 14 * i, 119 - 8.1 * i, RULE))
        parts.append(line(4 + 14 * i, 72 + 7.8 * i, 87 + 14 * i, 28 + 7 * i, RULE))
    for dx, dy in ((77, 35), (37, 58), (92, 71)):
        parts.append(f'<g transform="translate({dx} {dy})">')
        # Monitor, terminal prompt, desktop, legs and a small seated robot.
        parts.append(
            '<path d="m0 13 22 11 18-10-22-11z" fill="#19422D" stroke="#7EE787"/>'
            '<path d="M1 14v10m21 0v10m17-19v9" stroke="#62A47C" fill="none"/>'
            '<path d="m8 7 14 7V1L8-6z" fill="#091610" stroke="#9DE5B8"/>'
            '<path d="m10 0 2 2-2 1m5 2 4 2" stroke="#39FF88" fill="none"/>'
            '<path d="m25 4 6-3 6 3-6 4z M25 4v7l6 4V8m6-4v7l-6 4" fill="#193E2A" stroke="#7EE787"/>'
            '<path d="m27 8 1 .5m3 1.5 1 .5" stroke="#E6EDF3"/></g>'
        )
    return "".join(parts) + "</g>"


def project(item: dict, mobile=False, static=False) -> str:
    featured = item["name"] == "Turno_Office"
    w = MOBILE if mobile else DESKTOP
    x = 18 if mobile else (230 if featured else 64)
    width_chars = 40 if mobile else (65 if featured else 76)
    description = wrap(item["description"], width_chars)
    top = (89 if mobile else 77) if featured else (58 if mobile else 62)
    tags_y = top + len(description) * 20 + 9
    language = item.get("language")
    h = tags_y + (55 if language else 33)
    body = frame(w, h)
    if featured:
        body += office_drawing(
            15 if mobile else 17, 4 if mobile else 2, 0.56 if mobile else 1.08
        )
        body += label(126 if mobile else x, 27, "Oficina virtual 3D", 13, SOFT)
        body += label(
            126 if mobile else x, 54, item["name"], 21 if mobile else 28, FG, 700
        )
    else:
        body += icon("repo", 17 if mobile else 23, 16, 19 if mobile else 24)
        body += label(
            45 if mobile else x, 33, item["name"], 16 if mobile else 21, FG, 700
        )
    for i, text_line in enumerate(description):
        body += label(x, top + i * 20, text_line, 14 if mobile else 16, FG)
    for tech in item["stack"].split(" · "):
        tw = len(tech) * 7.9 + 16
        body += rect(x, tags_y - 8, tw, 21, PANEL, 4, RULE)
        body += label(x + 8, tags_y + 7, tech, 13, SOFT)
        x += tw + 6
    if language:
        body += label(
            18 if mobile else (230 if featured else 64),
            tags_y + 36,
            f"Lenguaje principal · {language}",
            13,
            MUTED,
        )
    if item.get("stars") is not None:
        body += icon("star", w - 65, 17, 14, SOFT) + label(
            w - 44, 29, item["stars"], 13, FG
        )
    body += icon("arrow", w - 29, 16, 14, MUTED)
    desc = item["description"] + " " + item["stack"]
    if item.get("stars") is not None:
        desc += f". {item['stars']} GitHub stars."
    return svg(item["name"], w, h, appear(body, 0), desc, "" if static else MOTION)


def picture(name: str, alt: str) -> str:
    base = f"./assets/generated/{name}"
    return (
        f'<picture>\n  <source media="(max-width: 760px)" srcset="{base}-mobile.svg">\n'
        f'  <img src="{base}.svg" width="100%" alt={quoteattr(alt)}>\n</picture>'
    )


def write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def readme_sections(snapshot: dict) -> dict[str, str]:
    data = snapshot.get("repositories", {})
    calendar_alt = "Calendario anual de contribuciones de GitHub, días activos y mejor racha del periodo."
    metrics = picture(
        "stats",
        "Repositorios públicos, estrellas recibidas, seguidores y contribuciones del periodo.",
    )
    activity = snapshot.get("activity")
    events = Counter((e["date"], e["repo"], e["type"]) for e in activity or [])
    events_text = ["<details>", "<summary>Actividad pública reciente</summary>", ""]
    for (day, repo, event), number in events.items():
        event_name = {"PushEvent": "Envío de cambios", "CreateEvent": "Creación"}.get(
            event, event.removesuffix("Event")
        )
        events_text.append(
            f"- {day} UTC · {event_name}{f' ×{number}' if number > 1 else ''} · [{repo}](https://github.com/{repo})"
        )
    if not events:
        events_text.append(
            "Sin eventos recientes." if activity == [] else "Datos no disponibles."
        )
    events_text.extend(["", "</details>"])

    stack_alt = ". ".join(f"{group}: {stack}" for group, stack in STACK)
    projects = []
    for item in data.get("projects", []):
        name = "project-" + item["name"].lower().replace("_", "-")
        alt = f"{item['name']}. {item['description']} {item['stack']}."
        if item.get("language"):
            alt += f" Lenguaje principal: {item['language']}."
        projects.append(
            f"<a href={quoteattr(item['url'])}>\n{picture(name, alt)}\n</a>"
        )
    return {
        "activity": "\n\n".join(
            [metrics, picture("contributions", calendar_alt), "\n".join(events_text)]
        ),
        "stack": picture(
            "skills",
            f"{stack_alt}. Distribución de repositorios propios por lenguaje principal.",
        ),
        "projects": "\n\n".join(projects) or "Proyectos no disponibles.",
    }


def replace_sections(markdown: str, sections: dict[str, str]) -> str:
    for name, body in sections.items():
        start, end = f"<!-- {name}:start -->", f"<!-- {name}:end -->"
        if markdown.count(start) != 1 or markdown.count(end) != 1:
            raise ValueError(f"Expected a single marker pair for {name}")
        before, remainder = markdown.split(start, 1)
        _, after = remainder.split(end, 1)
        markdown = f"{before}{start}\n\n{body}\n\n{end}{after}"
    return markdown


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--static", action="store_true", help="Render final frames without animation"
    )
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    image = source_image(ROOT)
    if image is None:
        parser.error("Portrait source IMG_2087 is missing")
    portrait = sample_portrait(image)
    mobile_portrait = sample_portrait(image, density=0.60)
    snapshot = (
        json.loads(SNAPSHOT.read_text(encoding="utf-8")) if SNAPSHOT.exists() else {}
    )
    data = snapshot.get("repositories", {})
    cards = {}
    projects = data.get("projects", [])
    for mobile, suffix in ((False, ""), (True, "-mobile")):
        cards["hero" + suffix] = hero(
            mobile_portrait if mobile else portrait, mobile, args.static
        )
        cards["stats" + suffix] = stats(snapshot, mobile, args.static)
        cards["contributions" + suffix] = contributions(snapshot, mobile, args.static)
        cards["skills" + suffix] = technology(snapshot, mobile, args.static)
        for item in projects:
            key = "project-" + item["name"].lower().replace("_", "-")
            cards[key + suffix] = project(item, mobile, args.static)
    cards["portrait"] = portrait_svg(portrait, args.static)
    cards["portrait-static"] = portrait_svg(portrait, True)
    for name, source in cards.items():
        write(args.output / f"{name}.svg", source)
    for path in args.output.glob("project-*.svg"):
        if path.stem not in cards:
            path.unlink()
    if args.output == OUT and not args.static:
        readme = ROOT / "README.md"
        write(
            readme,
            replace_sections(
                readme.read_text(encoding="utf-8"), readme_sections(snapshot)
            ),
        )


if __name__ == "__main__":
    main()
