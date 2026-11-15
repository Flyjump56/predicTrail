"""Exports du planning, sans dépendance de production à Excel."""
from collections import defaultdict
from datetime import date, datetime, timedelta
from html import escape
from io import BytesIO
import re
from xml.etree.ElementTree import Element, SubElement, tostring
from zipfile import ZIP_DEFLATED, ZipFile


HEADERS = ("Date", "Semaine ISO", "Catégorie", "Séance ou course", "Durée (min)", "Note ou GPX")
WEEK_HEADERS = ("Semaine ISO", "Du lundi", "Séances", "Entraînement (min)", "Références", "Références (min)")
SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"


def report_rows(plan, references, timezone, *, start=None, end=None):
    rows = []

    def append(day, kind, label, minutes, note):
        if (start is not None and day < start) or (end is not None and day > end):
            return
        year, week, _ = day.isocalendar()
        rows.append((day, f"{year}-S{week:02}", kind, label, minutes, note))

    for session in plan.get("sessions", []):
        append(date.fromisoformat(session["date"]), "Entraînement", session["type"],
               session["minutes"], session["note"])
    goal = plan.get("goal")
    if goal:
        append(date.fromisoformat(goal["date"]), "Course objectif", goal["name"], None, goal["filename"])
    for course in references:
        recorded_start = datetime.fromisoformat(course["recordedStart"])
        append(recorded_start.astimezone(timezone).date(), "Course de référence", course["name"],
               round(course["duration"] / 60, 1), f'{course["distance"]/1000:.2f} km'.replace(".", ","))
    rows.sort(key=lambda row: (row[0], row[2], row[3]))

    weekly = defaultdict(lambda: [0, 0, 0, 0])
    for _, week, kind, _, minutes, _ in rows:
        totals = weekly[week]
        if kind == "Entraînement":
            totals[0] += 1
            totals[1] += minutes
        elif kind == "Course de référence":
            totals[2] += 1
            totals[3] += minutes
    recap = []
    for week, totals in weekly.items():
        year, number = week.split("-S")
        totals[3] = round(totals[3], 1)
        recap.append((week, date.fromisocalendar(int(year), int(number), 1), *totals))
    return rows, recap


def worksheet(headers, rows, widths):
    root = Element("worksheet", xmlns=SHEET_NS)
    view = SubElement(SubElement(root, "sheetViews"), "sheetView", workbookViewId="0")
    SubElement(view, "pane", ySplit="1", topLeftCell="A2", activePane="bottomLeft", state="frozen")
    columns = SubElement(root, "cols")
    for index, width in enumerate(widths, 1):
        SubElement(columns, "col", min=str(index), max=str(index), width=str(width), customWidth="1")
    data = SubElement(root, "sheetData")
    for index, values in enumerate([headers, *rows], 1):
        row = SubElement(data, "row", r=str(index))
        for column, value in enumerate(values):
            if value is None:
                continue
            cell = SubElement(row, "c", r=f"{chr(65+column)}{index}")
            if index == 1:
                cell.set("s", "2")
            if isinstance(value, date) and value >= date(1900, 1, 1):
                cell.set("s", "1")
                serial = (value - date(1899, 12, 31)).days + int(value >= date(1900, 3, 1))
                SubElement(cell, "v").text = str(serial)
            elif isinstance(value, (int, float)):
                SubElement(cell, "v").text = str(value)
            else:
                cell.set("t", "inlineStr")
                if isinstance(value, date):
                    value = value.isoformat()
                SubElement(SubElement(cell, "is"), "t", {"xml:space":"preserve"}).text = re.sub(
                    r"[^\x09\x0a\x0d\x20-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]", "", value)
    SubElement(root, "autoFilter", ref=f"A1:{chr(64+len(headers))}{len(rows)+1}")
    return root


def planning_xlsx(rows, recap, types):
    sheets = [
        ("Calendrier", worksheet(HEADERS, rows, (14,14,24,32,16,56))),
        ("Bilan hebdomadaire", worksheet(WEEK_HEADERS, recap, (14,14,12,24,14,24))),
        ("Types de séances", worksheet(("Type", "Durée par défaut (min)"),
                                     [(item["name"], item["minutes"]) for item in types], (34,26))),
    ]
    content = Element("Types", xmlns=CONTENT_NS)
    SubElement(content, "Default", Extension="rels", ContentType="application/vnd.openxmlformats-package.relationships+xml")
    SubElement(content, "Default", Extension="xml", ContentType="application/xml")
    for part, kind in [("/xl/workbook.xml", "sheet.main"), ("/xl/styles.xml", "styles")]:
        SubElement(content, "Override", PartName=part, ContentType=f"application/vnd.openxmlformats-officedocument.spreadsheetml.{kind}+xml")
    package = Element("Relationships", xmlns=PACKAGE_REL_NS)
    SubElement(package, "Relationship", Id="rId1", Type=f"{REL_NS}/officeDocument", Target="xl/workbook.xml")
    workbook = Element("workbook", {"xmlns": SHEET_NS, "xmlns:r": REL_NS})
    index = SubElement(workbook, "sheets")
    links = Element("Relationships", xmlns=PACKAGE_REL_NS)
    SubElement(links, "Relationship", Id="styles", Type=f"{REL_NS}/styles", Target="styles.xml")
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for number, (name, sheet) in enumerate(sheets, 1):
            path = f"worksheets/sheet{number}.xml"
            SubElement(content, "Override", PartName=f"/xl/{path}",
                       ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml")
            SubElement(index, "sheet", name=name, sheetId=str(number), attrib={"r:id": f"rId{number}"})
            SubElement(links, "Relationship", Id=f"rId{number}", Type=f"{REL_NS}/worksheet", Target=path)
            archive.writestr("xl/"+path, tostring(sheet, encoding="utf-8", xml_declaration=True))
        for path, value in [("[Content_Types].xml", content), ("_rels/.rels", package),
                            ("xl/workbook.xml", workbook), ("xl/_rels/workbook.xml.rels", links)]:
            archive.writestr(path, tostring(value, encoding="utf-8", xml_declaration=True))
        archive.writestr("xl/styles.xml", f"""<styleSheet xmlns="{SHEET_NS}">
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>
<borders count="1"><border/></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="14" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>""")
    return buffer.getvalue()


def printed_duration(minutes):
    if minutes is None:
        return "—"
    hours, remainder = divmod(round(minutes), 60)
    return f"{minutes:g} min ({hours} h {remainder:02} min)".replace(".", ",")


def calendar_print(rows, start, end):
    by_day = defaultdict(list)
    for day, _, kind, label, minutes, note in rows:
        duration = f"<br>{printed_duration(minutes)}" if minutes is not None else ""
        extra = f"<br>{escape(note)}" if note else ""
        by_day[day].append(f'<div class="entry"><small>{kind}</small><br><strong>{escape(label)}</strong>{duration}{extra}</div>')
    monday = start - timedelta(days=start.weekday())
    weeks = []
    while monday <= end:
        year, week, _ = monday.isocalendar()
        cells = [f'<th scope="row">{year}-S{week:02}</th>']
        for weekday in range(7):
            day = monday + timedelta(days=weekday)
            content = f'<strong>{day:%d/%m}</strong>' + "".join(by_day[day]) if start <= day <= end else ""
            cells.append(f"<td>{content}</td>")
        weeks.append("<tr>"+"".join(cells)+"</tr>")
        monday += timedelta(days=7)
    headers = "".join(f'<th scope="col">{label}</th>' for label in
                      ("Sem.", "Lun.", "Mar.", "Mer.", "Jeu.", "Ven.", "Sam.", "Dim."))
    return f'<table class="calendar"><thead><tr>{headers}</tr></thead><tbody>{"".join(weeks)}</tbody></table>'


def planning_print(rows, recap, zone, start, end, layout, *, embedded=False):
    def table(headers, values):
        cells = "".join(f'<th scope="col">{escape(title)}</th>' for title in headers)
        entries = []
        for row in values:
            columns = [value.strftime("%d/%m/%Y") if isinstance(value, date) else
                       "—" if value is None else str(value) for value in row]
            entries.append("<tr>"+"".join(f"<td>{escape(value)}</td>" for value in columns)+"</tr>")
        return f"<table><thead><tr>{cells}</tr></thead><tbody>{''.join(entries)}</tbody></table>"

    goal = next((row for row in rows if row[2] == "Course objectif"), None)
    target = f'<p><strong>Course objectif</strong> · {escape(goal[3])} · {goal[0]:%d/%m/%Y}</p>' if goal else ""
    if layout == "calendar":
        detail = calendar_print(rows, start, end)
    elif rows:
        detail = table((*HEADERS[:4], "Durée", HEADERS[5]),
                       ((*row[:4], printed_duration(row[4]), row[5]) for row in rows))
    else:
        detail = "<p>Aucune entrée au calendrier.</p>"
    recap_html = table(WEEK_HEADERS, recap) if recap else "<p>Aucun entraînement ni référence dans le bilan.</p>"
    back = '' if embedded else '<button type="button" onclick="history.back()">Retour au planning</button>'
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Planning de préparation · PrédicTrail</title>
<style>
body {{ font: 15px system-ui,sans-serif; color:#172931; max-width:1000px; margin:28px auto; padding:0 16px }}
table {{ border-collapse:collapse; width:100%; margin-bottom:24px }} th,td {{ padding:7px 8px; border:1px solid #c4cfd5; text-align:left; vertical-align:top; overflow-wrap:anywhere }}
th {{ background:#e8f0f4 }} tr {{ break-inside:avoid }} h2 {{ break-after:avoid }}
td {{ white-space:pre-wrap }}
.calendar {{ table-layout:fixed }} .calendar th:first-child {{ width:5em }}
.calendar td {{ height:4rem }} .entry {{ margin-top:6px; padding-top:4px; border-top:1px solid #c4cfd5 }}
{"@page { size:landscape }" if layout == "calendar" else ""}
@media print {{ .report-actions {{ display:none }} body {{ margin:0; padding:0; font-size:10pt }} thead {{ display:table-header-group }} }}
</style></head><body>
<div class="report-actions">
{back}
<button type="button" onclick="window.print()">Imprimer le planning</button>
</div>
<h1>Planning de préparation</h1>{target}
<p>Du {start:%d/%m/%Y} au {end:%d/%m/%Y} inclus · Références datées dans le fuseau {escape(zone)}.</p>
<h2>Bilan hebdomadaire</h2>{recap_html}
<h2>Détail du calendrier</h2>{detail}
<script>window.addEventListener('load', () => window.print());</script></body></html>""".encode("utf-8")
