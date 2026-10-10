"""Builds docs/E-Panchayat_Technical_Handbook.pdf with ReportLab."""

import sys
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, CondPageBreak, Frame, KeepTogether, NextPageTemplate,
    PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle, XPreformatted,
)
from reportlab.platypus.tableofcontents import TableOfContents

OUT = sys.argv[1]

F = "/usr/share/fonts/truetype/dejavu/"
L = "/usr/share/fonts/truetype/liberation/"
pdfmetrics.registerFont(TTFont("Sans", L + "LiberationSans-Regular.ttf"))
pdfmetrics.registerFont(TTFont("Sans-Bold", L + "LiberationSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Sans-Oblique", L + "LiberationSans-Italic.ttf"))
pdfmetrics.registerFont(TTFont("Sans-BoldOblique", L + "LiberationSans-BoldItalic.ttf"))
pdfmetrics.registerFont(TTFont("Serif", F + "DejaVuSerif.ttf"))
pdfmetrics.registerFont(TTFont("Serif-Bold", F + "DejaVuSerif-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Mono", F + "DejaVuSansMono.ttf"))
pdfmetrics.registerFont(TTFont("Mono-Bold", F + "DejaVuSansMono-Bold.ttf"))
from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily("Sans", normal="Sans", bold="Sans-Bold", italic="Sans-Oblique",
                   boldItalic="Sans-BoldOblique")
registerFontFamily("Mono", normal="Mono", bold="Mono-Bold", italic="Mono", boldItalic="Mono-Bold")

NAVY = colors.HexColor("#1B2A4A")
SAFFRON = colors.HexColor("#E8762B")
GREEN = colors.HexColor("#2E7D4F")
INK = colors.HexColor("#22252B")
MUTED = colors.HexColor("#5C6370")
RULE = colors.HexColor("#D5D9E0")
PAPER = colors.HexColor("#F5F6F8")
CODEBG = colors.HexColor("#F3F4F7")
QBG = colors.HexColor("#FFF6EE")

body = ParagraphStyle("body", fontName="Sans", fontSize=9.6, leading=14.2, textColor=INK,
                      spaceAfter=6)
small = ParagraphStyle("small", parent=body, fontSize=8.3, leading=11.5, textColor=MUTED)
h1 = ParagraphStyle("h1", fontName="Serif-Bold", fontSize=20, leading=25, textColor=NAVY,
                    spaceBefore=2, spaceAfter=10)
h2 = ParagraphStyle("h2", fontName="Sans-Bold", fontSize=12.5, leading=16, textColor=NAVY,
                    spaceBefore=12, spaceAfter=5)
h3 = ParagraphStyle("h3", fontName="Sans-Bold", fontSize=10.2, leading=14, textColor=SAFFRON,
                    spaceBefore=8, spaceAfter=3)
bullet = ParagraphStyle("bullet", parent=body, leftIndent=13, bulletIndent=3, spaceAfter=3)
code = ParagraphStyle("code", fontName="Mono", fontSize=7.6, leading=10, textColor=INK)
cell = ParagraphStyle("cell", parent=body, fontSize=8.4, leading=11.3, spaceAfter=0)
cellb = ParagraphStyle("cellb", parent=cell, fontName="Sans-Bold", textColor=colors.white)
qstyle = ParagraphStyle("q", parent=body, fontName="Sans-Bold", textColor=NAVY, spaceAfter=3)
astyle = ParagraphStyle("a", parent=body, spaceAfter=0)

story = []


def P(t, s=body):
    story.append(Paragraph(t, s))


def H1(t, num=None):
    story.append(PageBreak())
    label = f"{num}. {t}" if num else t
    p = Paragraph(label, h1)
    p.toc_level = 0
    p.toc_text = label
    story.append(p)
    story.append(Table([[""]], colWidths=[40 * mm], rowHeights=[2.2],
                       style=[("BACKGROUND", (0, 0), (-1, -1), SAFFRON)], hAlign="LEFT"))
    story.append(Spacer(1, 8))


def H2(t):
    p = Paragraph(t, h2)
    p.toc_level = 1
    p.toc_text = t
    story.append(CondPageBreak(30 * mm))
    story.append(p)


def H3(t):
    story.append(Paragraph(t, h3))


def B(items):
    for it in items:
        story.append(Paragraph(it, bullet, bulletText="•"))
    story.append(Spacer(1, 3))


def CODE(src, title=None):
    flow = XPreformatted(escape(src.strip("\n")), code)
    rows = []
    if title:
        rows.append([Paragraph(title, ParagraphStyle("ct", parent=small, fontName="Sans-Bold",
                                                     textColor=NAVY))])
    rows.append([flow])
    t = Table(rows, colWidths=[170 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODEBG),
        ("LINEBEFORE", (0, 0), (0, -1), 2.2, NAVY),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(KeepTogether([Spacer(1, 2), t, Spacer(1, 7)]))


def TABLE(head, rows, widths):
    data = [[Paragraph(h, cellb) for h in head]]
    data += [[Paragraph(str(c), cell) for c in r] for r in rows]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PAPER]),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(Spacer(1, 2))
    story.append(t)
    story.append(Spacer(1, 8))


def NOTE(t, color=GREEN, bg=colors.HexColor("#EEF6F1")):
    tb = Table([[Paragraph(t, astyle)]], colWidths=[170 * mm])
    tb.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg), ("LINEBEFORE", (0, 0), (0, -1), 3, color),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(tb)
    story.append(Spacer(1, 8))


def QA(q, a, src=None):
    inner = [Paragraph(q, qstyle)]
    if isinstance(a, str):
        a = [a]
    for para in a:
        inner.append(Paragraph(para, astyle))
        inner.append(Spacer(1, 3))
    if src:
        inner.append(XPreformatted(escape(src.strip("\n")), code))
    tb = Table([[inner]], colWidths=[170 * mm])
    tb.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), QBG), ("LINEBEFORE", (0, 0), (0, -1), 3, SAFFRON),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tb)
    story.append(Spacer(1, 7))


# ── Diagrams ────────────────────────────────────────────────────────────────

def box(d, x, y, w, h, title, sub=None, fill=colors.white, stroke=NAVY, tc=NAVY):
    d.add(Rect(x, y, w, h, rx=5, ry=5, fillColor=fill, strokeColor=stroke, strokeWidth=1.1))
    ty = y + h / 2 + (3 if sub else -3)
    d.add(String(x + w / 2, ty, title, fontName="Sans-Bold", fontSize=8.6, fillColor=tc,
                 textAnchor="middle"))
    if sub:
        for i, line in enumerate(sub.split("\n")):
            d.add(String(x + w / 2, y + h / 2 - 9 - i * 9, line, fontName="Sans", fontSize=6.8,
                         fillColor=MUTED, textAnchor="middle"))


def arrow(d, x1, y1, x2, y2, label=None, color=MUTED):
    d.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=1))
    import math
    a = math.atan2(y2 - y1, x2 - x1)
    s = 5
    d.add(Polygon([x2, y2, x2 - s * math.cos(a - 0.4), y2 - s * math.sin(a - 0.4),
                   x2 - s * math.cos(a + 0.4), y2 - s * math.sin(a + 0.4)],
                  fillColor=color, strokeColor=color))
    if label:
        d.add(String((x1 + x2) / 2 + 4, (y1 + y2) / 2 + 3, label, fontName="Sans",
                     fontSize=6.6, fillColor=MUTED))


def arch_diagram():
    d = Drawing(480, 250)
    box(d, 20, 190, 200, 44, "React 19 + TypeScript (Vite)",
        "Tailwind, i18next (EN/MR), Leaflet, Recharts", fill=colors.HexColor("#EEF2FA"))
    box(d, 260, 190, 200, 44, "Render static site", "dist/ served from CDN, never sleeps",
        fill=PAPER, stroke=MUTED, tc=INK)
    arrow(d, 120, 190, 120, 152, "HTTPS + JWT (Authorization: Bearer)")
    box(d, 20, 98, 200, 54, "FastAPI service (Docker)",
        "CORS -> AuditMiddleware -> routers\nRBAC + village scoping in core/deps.py",
        fill=colors.HexColor("#FDF1E7"), stroke=SAFFRON)
    box(d, 260, 104, 200, 44, "Render web service", "alembic upgrade head on boot\nuvicorn, 2 workers",
        fill=PAPER, stroke=MUTED, tc=INK)
    arrow(d, 80, 98, 80, 58, "SQLAlchemy 2.0")
    arrow(d, 175, 98, 300, 58, "httpx (server-side key only)")
    box(d, 20, 14, 140, 44, "PostgreSQL (Supabase)", "session pooler, sslmode=require",
        fill=colors.HexColor("#EEF6F1"), stroke=GREEN)
    box(d, 250, 14, 210, 44, "Google Gemini API", "generateContent + batchEmbedContents\nnever sees a resident record",
        fill=colors.HexColor("#F4EEF9"), stroke=colors.HexColor("#6B4FA0"))
    return d


def rag_diagram():
    d = Drawing(480, 150)
    steps = [
        ("Question", "EN or MR"),
        ("Embed", "Gemini, 768-d"),
        ("Scope", "WHERE village_id\n= caller's scope"),
        ("Rank", "cosine >= 0.55\ntop-k = 6"),
        ("Expand", "walk meta.links\n<= 3 per hit"),
        ("Privacy gate", "personal fact?\nno model call"),
        ("Generate", "facts-only prompt\n+ sources"),
    ]
    w, gap = 58, 9
    for i, (t, s) in enumerate(steps):
        x = 6 + i * (w + gap)
        fill = colors.HexColor("#FDF1E7") if t == "Privacy gate" else colors.HexColor("#EEF2FA")
        box(d, x, 70, w, 52, t, s, fill=fill, stroke=SAFFRON if t == "Privacy gate" else NAVY)
        if i < len(steps) - 1:
            arrow(d, x + w, 96, x + w + gap, 96)
    d.add(String(6, 46, "Fallbacks: no index, no key, embedding failure or zero hits above the floor  ->  "
                 "keyword routing (gather) over the same scoped queries.", fontName="Sans",
                 fontSize=7, fillColor=MUTED))
    d.add(String(6, 32, "Citizen questions: keyword pass runs first so the rule engine's verdicts are "
                 "included; semantic hits are layered on top.", fontName="Sans", fontSize=7,
                 fillColor=MUTED))
    d.add(String(6, 18, "Model unavailable: plain_answer() renders the same retrieved facts as text. "
                 "It degrades; it does not invent.", fontName="Sans", fontSize=7, fillColor=MUTED))
    return d


def elig_diagram():
    d = Drawing(480, 135)
    box(d, 4, 40, 80, 44, "Resident +", "Scheme.criteria", fill=colors.HexColor("#EEF2FA"))
    box(d, 104, 40, 90, 44, "evaluate()", "rule checks,\nany_of recursion")
    arrow(d, 84, 62, 104, 62)
    outs = [("Ineligible", "a rule failed", colors.HexColor("#FBEAEA"), colors.HexColor("#B23B3B")),
            ("Needs Review", "unknown attr /\nmanual_review", colors.HexColor("#FFF6E5"), SAFFRON),
            ("Missing Documents", "check_documents()", colors.HexColor("#EEF2FA"), NAVY),
            ("Eligible", "all verified", colors.HexColor("#EEF6F1"), GREEN)]
    for i, (t, s, f, st) in enumerate(outs):
        x = 220 + (i % 2) * 130
        y = 66 if i < 2 else 10
        box(d, x, y, 118, 44, t, s, fill=f, stroke=st, tc=st)
    arrow(d, 194, 62, 220, 86)
    arrow(d, 194, 62, 220, 34)
    d.add(String(4, 122, "Precedence is fixed in Assessment.status: Ineligible > Needs Review > "
                 "Missing Documents > Eligible", fontName="Sans", fontSize=7.2, fillColor=MUTED))
    return d


# ── Page furniture ──────────────────────────────────────────────────────────

def cover(c, doc):
    W, H = A4
    c.setFillColor(NAVY)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(SAFFRON)
    c.rect(0, H - 9 * mm, W, 3 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.rect(0, H - 12 * mm, W, 3 * mm, fill=1, stroke=0)
    c.setFillColor(GREEN)
    c.rect(0, H - 15 * mm, W, 3 * mm, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#F2B48A"))
    c.setFont("Sans-Bold", 10)
    c.drawString(22 * mm, H - 50 * mm, "TECHNICAL HANDBOOK  ·  DESIGN RATIONALE  ·  INTERVIEW PREPARATION")
    c.setFillColor(colors.white)
    c.setFont("Serif-Bold", 40)
    c.drawString(22 * mm, H - 75 * mm, "E-Panchayat")
    c.setFont("Serif", 16)
    c.drawString(22 * mm, H - 88 * mm, "An AI-assisted decision support system")
    c.drawString(22 * mm, H - 96 * mm, "for Gram Panchayat administration")
    c.setStrokeColor(SAFFRON)
    c.setLineWidth(2)
    c.line(22 * mm, H - 106 * mm, 70 * mm, H - 106 * mm)
    c.setFont("Sans", 10.5)
    c.setFillColor(colors.HexColor("#C9D1E0"))
    lines = [
        "How the system works, how it was built, and why each decision",
        "was made the way it was, followed by the questions a senior",
        "software engineer is likely to ask about it, with worked answers,",
        "algorithms, complexity analysis and code.",
    ]
    for i, l in enumerate(lines):
        c.drawString(22 * mm, H - 120 * mm - i * 6 * mm, l)
    c.setFont("Sans", 9.5)
    c.setFillColor(colors.HexColor("#9AA6BC"))
    meta = [
        "Sem-7 Capstone  ·  Group BCC28",
        "MIT School of Computing, MIT-ADT University, Pune",
        "Guide: Prof. Jyoti Gavhane",
        "Scope: 23 villages of Haveli block, Pune district, Maharashtra",
        "Repository state documented: commit 897818c  ·  October 2026",
    ]
    for i, l in enumerate(meta):
        c.drawString(22 * mm, 52 * mm - i * 6 * mm, l)


def later(c, doc):
    W, H = A4
    c.saveState()
    c.setStrokeColor(RULE)
    c.setLineWidth(0.5)
    c.line(20 * mm, H - 14 * mm, W - 20 * mm, H - 14 * mm)
    c.setFont("Sans", 7.5)
    c.setFillColor(MUTED)
    c.drawString(20 * mm, H - 11.5 * mm, "E-Panchayat  ·  Technical Handbook")
    c.drawRightString(W - 20 * mm, H - 11.5 * mm, "Group BCC28  ·  MIT-ADT University")
    c.line(20 * mm, 14 * mm, W - 20 * mm, 14 * mm)
    c.drawRightString(W - 20 * mm, 9.5 * mm, f"{doc.page}")
    c.restoreState()


class Doc(BaseDocTemplate):
    def afterFlowable(self, f):
        if hasattr(f, "toc_level"):
            key = f"k{id(f)}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(f.toc_text, key, level=f.toc_level, closed=f.toc_level > 0)
            self.notify("TOCEntry", (f.toc_level, f.toc_text, self.page, key))


doc = Doc(OUT, pagesize=A4, title="E-Panchayat Technical Handbook",
          author="Group BCC28, MIT-ADT University",
          subject="Design, implementation and interview preparation for the E-Panchayat system",
          leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=20 * mm)
frame = Frame(20 * mm, 18 * mm, A4[0] - 40 * mm, A4[1] - 38 * mm, id="f")
doc.addPageTemplates([PageTemplate("cover", [frame], onPage=cover),
                      PageTemplate("body", [frame], onPage=later)])

story.append(NextPageTemplate("body"))
story.append(PageBreak())

story.append(Paragraph("Contents", h1))
toc = TableOfContents()
toc.levelStyles = [
    ParagraphStyle("t0", fontName="Sans-Bold", fontSize=10, leading=15, textColor=NAVY,
                   leftIndent=0, spaceBefore=4),
    ParagraphStyle("t1", fontName="Sans", fontSize=8.6, leading=11.5, textColor=INK, leftIndent=14),
]
story.append(toc)

# ════════════════════════════════════════════════════════════════════════════
H1("Reading this handbook", 0)
P("This handbook is written for two readers. The first is anyone who has to understand E-Panchayat "
  "well enough to present it, defend it in a viva, or extend it next semester. The second is the "
  "interviewer sitting across the table, the kind of senior engineer at a company like Google who "
  "will not be satisfied with a feature list and will want to know <i>why</i> the system is shaped "
  "the way it is, what it costs in time and space, and where it breaks.")
P("Every claim here was checked against the code in the repository at commit <font name='Mono'>897818c</font>. "
  "Where the project made a trade-off, the trade-off is stated alongside the decision. That habit runs "
  "through the codebase itself, and it is the single most useful thing to carry into an interview: a "
  "system you can criticise honestly is a system you clearly understand.")
TABLE(["Part", "What it covers", "Use it for"], [
    ["1 to 3", "The problem, the scope, how the project evolved, and the architecture", "The opening five minutes of any presentation"],
    ["4 to 11", "Each subsystem in depth: data model, security, eligibility, retrieval, classifier, document readers, audit, frontend", "Viva questions on a specific module"],
    ["12 to 13", "Testing, deployment and operations", "\"How do you know it works?\" and \"How is it run?\""],
    ["14", "Honest limitations and how the design would scale", "System design follow-ups"],
    ["15 to 18", "Interview question bank: DSA, system design, coding exercises with solutions, behavioural", "Interview preparation"],
    ["19", "Glossary", "Quick reference"],
], [22, 92, 56])

# ════════════════════════════════════════════════════════════════════════════
H1("The problem and the scope", 1)
H2("What a Gram Panchayat actually has to do")
P("A Gram Panchayat is the elected local government of a village, the lowest tier of India's "
  "three-level Panchayati Raj system. In Maharashtra its office keeps the village register, receives "
  "complaints about water, drains, roads and streetlights, runs development works against a budget, "
  "holds the Gram Sabha (the assembly of all adult residents) and records its decisions, and helps "
  "residents claim central and state welfare schemes.")
P("In practice most of that lives in paper registers and spreadsheets. The questions an officer is asked "
  "every day are simple to state and slow to answer: <i>Is this widow eligible for the Sanjay Gandhi "
  "Niradhar pension? Which ward has had the most water complaints this month? How much of the road "
  "budget has been spent? What did the last Gram Sabha decide about the drainage work?</i>")
H2("What E-Panchayat does")
B([
    "<b>Multi-village, permission-scoped records.</b> A real state, district, block and village hierarchy "
    "with official LGD (Local Government Directory) codes for 23 villages of Haveli block, Pune. An officer "
    "sees one Gram Panchayat, an admin sees the block, and a resident sees only their own file.",
    "<b>Welfare eligibility as data.</b> 29 real central and Maharashtra schemes, each with machine-readable "
    "rules. A deterministic engine returns one of four verdicts and explains which rule produced it.",
    "<b>A retrieval-augmented assistant.</b> Questions in English or Marathi are answered from the "
    "Panchayat's own records, scoped to the asker, with sources attached.",
    "<b>Grievance management</b> with automatic categorisation, priority and department routing, plus a full status history.",
    "<b>Document readers</b> that turn Gram Sabha minutes into decisions and action items, and a Government "
    "Resolution into a proposed scheme that waits for officer approval.",
    "<b>Resident sign-up with verification</b>, over-the-counter password reset, an audit trail, analytics "
    "dashboards and a GIS map.",
])
NOTE("<b>All resident data is synthetic.</b> The villages, LGD codes and schemes are real and cited. The ten "
     "residents, their incomes, families and documents are invented. This matters in an interview: it shows "
     "the team understood that real welfare data should never be used to demo a student project.")
H2("Numbers worth remembering")
TABLE(["Item", "Count", "Item", "Count"], [
    ["Villages (with LGD codes)", "23", "Seeded welfare schemes", "29"],
    ["Villages with verified map centre", "18", "Seeded residents (synthetic)", "10"],
    ["Backend tests (all passing)", "284", "Alembic migrations", "10"],
    ["Embedded knowledge chunks", "about 67", "Embedding width", "768 floats"],
    ["Backend source (Python)", "about 8,200 lines", "Frontend source (TSX/TS)", "about 15,000 lines"],
], [55, 30, 55, 30])

# ════════════════════════════════════════════════════════════════════════════
H1("How it was built: the project's evolution", 2)
P("The git history tells a clear story, and it is a better story than \"we designed it and built it\". The "
  "project started as a frontend prototype, ran into the limits of that design, and was rebuilt around a "
  "proper backend. Being able to narrate this is valuable, because interviewers care far more about how "
  "a team reacts to its own mistakes than about a clean first draft.")
H2("Phase 1: a frontend prototype (August 2026)")
P("The first version was a React single-page app styled as a government portal. Data lived in the browser's "
  "<font name='Mono'>localStorage</font> and was synchronised to Supabase on a best-effort basis. The AI "
  "features called Gemini straight from the browser.")
P("When the team looked at it critically, three serious problems surfaced:")
B([
    "<b>Writes were failing silently.</b> Four of the five Supabase tables rejected every write because the SQL "
    "schema and the TypeScript models described different data. The errors were swallowed into "
    "<font name='Mono'>console.warn</font>, so a broken save looked exactly like a successful one.",
    "<b>There was no real authentication.</b> The officer password was compared in client-side JavaScript, and "
    "typing any citizen ID at the login screen opened that resident's file.",
    "<b>The API key was in the bundle.</b> Vite compiles any <font name='Mono'>VITE_</font> variable into the "
    "JavaScript, so the only configuration in which the AI worked was one where anyone could read the key.",
])
H2("Phase 2: a FastAPI backend becomes the source of truth")
P("The rebuild moved every rule to the server. FastAPI, SQLAlchemy 2.0 and Alembic replaced the client-side "
  "store; JWT authentication and role guards replaced the password check in JavaScript; the Gemini key moved "
  "behind the API. The frontend was migrated screen by screen onto a typed client "
  "(<font name='Mono'>src/lib/api.ts</font>) whose failures throw rather than warn.")
H2("Phase 3: hardening, driven by actually running it")
P("The later commits are where the engineering maturity shows. Most of them fix something that only became "
  "visible by using the system as a real officer or resident would:")
TABLE(["Commit theme", "What was found", "What changed"], [
    ["Semantic retrieval, privacy", "Indexing residents would export the village register to a third party on every index run",
     "Residents excluded from the index; personal facts flagged and never sent to the model"],
    ["Meter /auth/login", "Login was an unlimited password oracle", "Database-backed throttling, five failures per email, twenty per IP, per fifteen minutes"],
    ["Password reset", "No email or SMS gateway exists", "Officer-issued one-time codes at the counter, sessions revoked on reset"],
    ["Audit trail", "No record of who opened whose file", "Middleware that records every write and every single-record read"],
    ["Stop the assistant filling the audit trail", "Each question wrote two noise rows", "Read-only POSTs exempted by an explicit allow-list"],
    ["Model health check", "A retired model name returned 404 for days while /health said all was well", "A separate endpoint that makes one real call"],
    ["Close village isolation", "Lists were scoped, but records could still be opened by ID", "A by-ID guard on every route, proven by 24 cross-village tests"],
], [38, 66, 66])
NOTE("<b>The interview line:</b> \"Our tests all passed while the bug existed, because every seeded resident lived in "
     "one village, so 'the neighbouring officer sees an empty list' looked true everywhere. We learned that "
     "tests only prove what your fixtures can express, and we added fixtures specifically to break that assumption.\"",
     color=SAFFRON, bg=QBG)

# ════════════════════════════════════════════════════════════════════════════
H1("Architecture and technology choices", 3)
story.append(arch_diagram())
P("Figure 1. Deployment and request path.", small)
H2("The three tiers")
P("A static React bundle talks to a stateless FastAPI service over HTTPS, carrying a JWT in the "
  "<font name='Mono'>Authorization</font> header. The API owns every rule and every query and is the "
  "only component that talks to PostgreSQL or to Gemini. Because the API is stateless (sessions are tokens, "
  "throttle counters are rows), it can run as several workers or several instances without coordination.")
H2("Why each technology was chosen")
TABLE(["Choice", "Why it was chosen", "What was given up / alternatives considered"], [
    ["<b>FastAPI</b> (Python 3.11)", "Dependency injection makes auth and scoping composable per route; Pydantic validation at the edge; free OpenAPI docs at /docs for demos; async for the LLM calls; Python is where the PDF/DOCX parsing libraries are",
     "Django is heavier and its ORM is less explicit; Node/Express would split the team's language and lacks equivalent document tooling"],
    ["<b>SQLAlchemy 2.0 + Alembic</b>", "Typed <font name='Mono'>Mapped[]</font> models are the single schema source of truth; migrations are versioned and run automatically on boot",
     "The prototype's drift between a hand-written SQL file and TypeScript types is exactly what this prevents"],
    ["<b>PostgreSQL on Supabase</b>", "Relational data with real foreign keys, free hosting, already in use. JSON columns hold scheme criteria and embeddings",
     "SQLite is used in tests for speed; MongoDB would lose joins and constraints the hierarchy depends on"],
    ["<b>React 19 + TypeScript + Vite</b>", "Typed API client catches contract drift at build time; Vite gives fast builds and fingerprinted assets",
     "Next.js would add server rendering the app does not need"],
    ["<b>No Redux, no React Query</b>", "Two small hooks (<font name='Mono'>useQuery</font>, <font name='Mono'>useMutation</font>) cover fetch-on-mount, loading, error and refetch",
     "React Query adds caching and deduplication; worth adopting if screens start sharing data heavily"],
    ["<b>Tailwind 4</b>", "Consistent government-portal styling without a CSS architecture to maintain", "Utility classes make markup longer"],
    ["<b>i18next</b>", "English and Marathi; Marathi is what most residents read", "Only two languages are supported today"],
    ["<b>Leaflet + OpenStreetMap</b>", "No API key, no billing account, no watermark", "Google Maps would need a key and a card"],
    ["<b>Gemini 2.5/3.x Flash</b>", "Free tier, structured JSON output via response schema, embeddings from the same provider",
     "Free tier may use submitted content, which is why personal data never reaches it"],
    ["<b>JWT (HS256) + bcrypt</b>", "Stateless sessions suit a sleeping free-tier server; bcrypt is deliberately slow", "Stateless tokens cannot be revoked, solved with a per-user <font name='Mono'>tokens_valid_from</font> timestamp"],
    ["<b>Render + Docker</b>", "Whole deployment declared in <font name='Mono'>render.yaml</font>; reviewable and rebuildable", "Free API instance sleeps after 15 minutes idle"],
], [32, 72, 66])
H2("Backend layout")
CODE("""
backend/app/
  api/routes/     one module per resource: auth, citizens, schemes, grievances,
                  projects, sabha, documents, villages, analytics, assistant, audit
  core/           config.py (settings), security.py (JWT, bcrypt, reset codes),
                  deps.py (current user, role guards, village scoping)
  services/
    eligibility.py    the rule engine (no model involved)
    retrieval.py      question -> scoped facts, keyword and semantic paths
    graph.py          cosine similarity and graph expansion
    indexer.py        rows -> linked, embeddable chunks (no residents)
    scheme_reader.py  Government Resolution -> pending scheme
    transcript.py     Gram Sabha minutes -> decisions and action items
    classifier.py     grievance -> category, priority, department
    ratelimit.py      sign-in throttling, counted in the database
    audit.py          the audit trail middleware
    llm.py            the only module that talks to Gemini
  models.py       SQLAlchemy models, the single schema source of truth
  schemas.py      Pydantic request/response models (camelCase on the wire)
""", "Where things live")
P("One design rule runs through this layout: <b>each external dependency has exactly one door</b>. Only "
  "<font name='Mono'>llm.py</font> talks to Gemini, only <font name='Mono'>deps.py</font> decides who can "
  "see what, and only <font name='Mono'>graph.semantic_search()</font> knows how vectors are stored. That is "
  "what makes later changes (a new model, pgvector, a new role) a one-file job.")

# ════════════════════════════════════════════════════════════════════════════
H1("The data model", 4)
P("The schema is defined in <font name='Mono'>backend/app/models.py</font> and evolved through ten Alembic "
  "migrations. Primary keys are readable strings such as <font name='Mono'>cit_102</font> or "
  "<font name='Mono'>griev_201</font>, which make demos and logs easy to follow. (As Section 6 explains, "
  "guessable IDs are exactly why every by-ID route needs its own permission check.)")
TABLE(["Group", "Tables", "Notes"], [
    ["Administrative hierarchy", "states, districts, blocks, villages", "Real LGD codes; Census 2011 population; optional lat/lng"],
    ["People", "families, citizens, users, registration_requests", "A user optionally links to one citizen; officers carry a village_id"],
    ["Welfare", "schemes, citizen_documents", "Scheme.criteria is JSON; required_documents is a JSON list"],
    ["Operations", "grievances, grievance_events, projects, facilities", "grievance_events is an append-only status history"],
    ["Gram Sabha", "sabha_meetings, sabha_action_items", "Decisions and assignable action items"],
    ["Retrieval", "knowledge_chunks", "Text, links (JSON), embedding (JSON), village_id, indexed_at"],
    ["Security", "auth_attempts, password_resets, audit_events", "Throttling counters, hashed one-time codes, the audit trail"],
], [38, 62, 70])
H2("Decisions worth defending")
B([
    "<b>Criteria as JSON, not columns.</b> Scheme rules vary wildly in shape. A JSON dictionary lets a new scheme be "
    "an insert rather than a migration, and the rule vocabulary is validated in code (Section 7).",
    "<b>Embeddings as JSON, not pgvector.</b> At about 67 chunks a linear scan takes well under a millisecond. "
    "pgvector would add an extension dependency to every environment for no visible gain. The note on "
    "<font name='Mono'>KnowledgeChunk</font> says exactly when this stops being true (around 100,000 chunks).",
    "<b><font name='Mono'>JSON(none_as_null=True)</font> on the embedding column.</b> By default SQLAlchemy stores Python "
    "<font name='Mono'>None</font> as the JSON value <font name='Mono'>null</font>, which is not SQL NULL, so "
    "<font name='Mono'>embedding IS NOT NULL</font> would match every unindexed row. A test caught this.",
    "<b>A unique constraint on (entity_type, entity_id)</b> plus a deterministic chunk ID "
    "(<font name='Mono'>kc_</font> + first 16 hex characters of SHA-1 of the key) makes re-indexing an idempotent upsert.",
    "<b>Timezone-aware timestamps everywhere,</b> with <font name='Mono'>as_utc()</font> normalising SQLite's naive values. "
    "Without it, a server set to IST would let a revoked token live five and a half hours longer.",
])

# ════════════════════════════════════════════════════════════════════════════
H1("Authentication and sessions", 5)
H2("Tokens")
P("Sign-in returns an access token (60 minutes) and a refresh token (7 days), both HS256 JWTs carrying "
  "<font name='Mono'>sub</font>, <font name='Mono'>type</font>, <font name='Mono'>iat</font> and "
  "<font name='Mono'>exp</font>. The access token also carries role and citizen ID. "
  "<font name='Mono'>decode_token()</font> rejects a token of the wrong type, so a refresh token cannot be "
  "used as an access token.")
H2("Revoking a stateless token")
P("The classic weakness of JWTs is that nothing on the server can end a session. If a password is reset "
  "because someone else had the account, that someone would stay signed in for up to a week. E-Panchayat "
  "solves this with one column: <font name='Mono'>users.tokens_valid_from</font>. Every authenticated request "
  "already loads the user row, so the check costs nothing extra:")
CODE("""
def token_is_revoked(user: User, payload: dict) -> bool:
    valid_from = as_utc(user.tokens_valid_from)
    if valid_from is None:
        return False
    issued_at = payload.get("iat")
    if issued_at is None:
        return True            # cannot be placed in time, so cannot post-date revocation
    return issued_at < valid_from.timestamp()
""", "backend/app/core/deps.py")
P("<font name='Mono'>iat</font> has one-second resolution, so a token minted in the same second as the "
  "revocation survives. That is deliberate: the alternative would reject the fresh token issued by the sign-in "
  "immediately after a reset.")
H2("Sign-in throttling")
P("Without a limit, <font name='Mono'>/auth/login</font> is a password oracle: slow per guess because of "
  "bcrypt, but free to repeat. The limiter counts <i>failures</i> in a fixed lookback window and refuses with "
  "HTTP 429 before bcrypt is ever run.")
TABLE(["Rule", "Value", "Reason"], [
    ["Failures per email per window", "5", "Stops focused guessing against one account"],
    ["Failures per IP per window", "20", "Stops spraying many accounts from one source"],
    ["Window", "15 minutes", "Short enough that a deliberate lockout is bearable"],
    ["Counted outcomes", "bad_password, no_account", "A refusal never extends the lockout, so it always expires"],
    ["Storage", "auth_attempts table", "An in-memory counter would reset on every cold start of the sleeping server"],
], [52, 38, 80])
B([
    "<b>Unknown addresses are throttled exactly like real ones.</b> Otherwise the throttle itself would reveal "
    "which emails are registered.",
    "<b>IP is read from the right-most X-Forwarded-For hop,</b> the one Render's own proxy appended. The left-most "
    "entry is whatever the client chose to send.",
    "<b>Registration responses are identical</b> whether or not the email already exists.",
])
H2("Password reset over the counter")
P("There is no email or SMS gateway, and a reset flow whose message never arrives is worse than none. So the "
  "flow uses the channel a Panchayat actually has: the office counter. An officer verifies the resident "
  "against the register and issues a one-time code, shown once. The resident redeems it for a password of "
  "their own choosing, so the officer never learns the password.")
CODE("""
_CODE_ALPHABET = "ABCDEFGHJKMNPQRTUVWXYZ23456789"   # O I L S 0 1 removed
_CODE_LENGTH = 10                                   # 30^10 ~ 5.9e14 ~ 49 bits

def generate_reset_code() -> str:
    raw = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
    return f"{raw[:5]}-{raw[5:]}"                    # 'K7MPQ-4XRTV'
""", "backend/app/core/security.py")
B([
    "Uses <font name='Mono'>secrets</font>, never <font name='Mono'>random</font>, because Mersenne Twister output is reconstructable.",
    "Stored only as a bcrypt hash, expires in 24 hours, single use, and voided when a new one is issued.",
    "An officer may reset only residents of their own village; only an admin may reset staff. Otherwise one "
    "village login would become a route to the whole block.",
    "Redeeming is metered separately, so failing a code does not lock out a password the user still remembers.",
])

# ════════════════════════════════════════════════════════════════════════════
H1("Authorisation: roles and village isolation", 6)
P("All access control lives in <font name='Mono'>core/deps.py</font> and is applied as FastAPI dependencies. "
  "The frontend hides buttons; the server is what refuses. A route that does not depend on a guard is public, "
  "so the list of guards is the list to audit.")
TABLE(["Role", "Scope", "How it is enforced"], [
    ["admin", "Every village in the block, plus the district rollup", "village_scope() returns None, meaning no filter"],
    ["officer", "One Gram Panchayat", "village_scope() returns the officer's village_id"],
    ["citizen", "Their own record, documents, grievances and eligibility", "assert_can_read_citizen() compares citizen IDs"],
    ["anonymous", "Login, register, refresh, health only", "Every other route depends on get_current_user"],
], [24, 64, 82])
H2("Two layers, and why both are needed")
P("<b>Layer one: scoped lists.</b> Every list endpoint adds <font name='Mono'>WHERE village_id = :scope</font>.")
P("<b>Layer two: by-ID guards.</b> A list that leaves a record out protects nothing if the record can still be "
  "opened by ID, and the seeded IDs are guessable. Every route that opens, edits or deletes one record calls "
  "<font name='Mono'>assert_can_access_village()</font> with that record's village. This is the classic "
  "<b>IDOR</b> (Insecure Direct Object Reference) defence, number one on the OWASP Top 10 as part of Broken Access Control.")
H2("Failing closed")
P("An earlier version returned <font name='Mono'>user.village_id</font> for everyone, and callers treated "
  "<font name='Mono'>None</font> as \"no filter\". An officer with no village assigned therefore saw the "
  "<i>entire block</i>. Now <font name='Mono'>None</font> is the admin's answer and nobody else's; any other "
  "account without a village gets a 403. A missing value should shrink access, never widen it.")
P("One subtle detail: when an officer asks for a resident who does not exist, the guard returns quietly and lets "
  "the route raise 404. Refusing with 403 instead would tell the officer which IDs exist in other villages.")
TABLE(["Test file", "Tests", "What it proves"], [
    ["test_village_isolation.py", "24", "The neighbouring officer can neither read nor change another village's records, route by route"],
    ["test_api.py", "87", "End-to-end behaviour of every resource, including role refusals"],
    ["test_password_reset.py", "28", "Who may reset whom, expiry, single use, session revocation"],
    ["test_rate_limit.py", "13", "Thresholds, non-renewal of lockouts, unknown-email parity"],
], [52, 18, 100])

# ════════════════════════════════════════════════════════════════════════════
H1("The eligibility engine", 7)
story.append(elig_diagram())
P("Figure 2. One resident, one scheme, one verdict.", small)
H2("Rules are data, not code")
P("The prototype hard-coded rules per scheme in a chain of <font name='Mono'>if</font> statements, so an "
  "unknown scheme silently fell through to a bare income test. Now each scheme carries a criteria dictionary:")
CODE("""
# Sanjay Gandhi Niradhar: income under Rs 21,000 OR on the BPL list
{
  "min_age": 18,
  "any_of": [ {"max_income": 21000}, {"requires_bpl": true} ]
}
""", "An example criteria dictionary")
P("The supported vocabulary (age band, income band, gender, marital status, social category, BPL, SECC-2011 listing, "
  "ration card type, land holding, disability percentage, occupation include/exclude, ward, household head, "
  "<font name='Mono'>any_of</font> and <font name='Mono'>manual_review</font>) was widened after reading real scheme "
  "notifications, because almost no real scheme decides on age and income alone.")
H2("Three-valued logic")
P("The most important design idea is that a rule can <b>pass</b>, <b>fail</b> or be <b>unknown</b>. If a scheme needs a "
  "ration card type and the record does not hold one, the engine does not guess. It reports the attribute as unknown "
  "and the verdict becomes <i>Needs Review</i>. Silently passing would promise a benefit; silently failing would deny one.")
H2("How any_of works")
P("<font name='Mono'>any_of</font> is evaluated recursively, so groups can nest. The combination logic is a small "
  "three-valued OR:")
CODE("""
if branches := criteria.get("any_of"):
    results = [evaluate(citizen, branch) for branch in branches]
    if any(r.passed and not r.unknown for r in results):
        pass                                   # a branch is cleanly satisfied
    elif any(r.unknown for r in results):
        out.unknown.extend(sorted({a for r in results for a in r.unknown}))
    else:
        fail("None of the alternative conditions are met (...)", ...)
""", "backend/app/services/eligibility.py")
P("<b>Complexity.</b> For one resident and one scheme, evaluation is O(R) in the number of rule nodes R in the criteria "
  "tree. Screening a village is O(C x S x R) for C residents and S schemes, plus document matching. At 10 residents and "
  "29 schemes that is trivial; at district scale (say 50,000 residents) it is still linear and embarrassingly parallel.")
H2("Document matching")
P("Once criteria pass, required documents are matched against the resident's uploads by normalised name "
  "(lowercase, alphanumerics only) with bidirectional substring checks, preferring a <i>Verified</i> copy if two exist. "
  "This replaced a first-eight-characters trick that matched \"Land ownership 7/12\" against anything beginning \"Land own\".")
H2("Why no LLM in this path")
P("A welfare decision has to be reproducible and auditable. The same inputs must give the same verdict tomorrow, and an "
  "officer must be able to point to the rule that produced it. A generated sentence is neither. "
  "<font name='Mono'>explain()</font> therefore builds the explanation, in English or Marathi, from the very facts the "
  "engine used.")

# ════════════════════════════════════════════════════════════════════════════
H1("The retrieval-augmented assistant", 8)
story.append(rag_diagram())
P("Figure 3. The semantic retrieval pipeline and its fallbacks.", small)
H2("Indexing: records become linked sentences")
P("<font name='Mono'>services/indexer.py</font> renders villages, schemes, projects, facilities, grievances and Gram Sabha "
  "meetings as natural-language sentences, the way a person would describe them, because that is what a question has to "
  "match. Each chunk also carries <font name='Mono'>meta.links</font>: typed edges to related records (\"in village\", "
  "\"filed by\"). These edges turn a flat vector store into a small knowledge graph.")
B([
    "<b>Batching:</b> 32 texts per <font name='Mono'>batchEmbedContents</font> call, with a per-text fallback if the model has no batch endpoint.",
    "<b>Fixed width:</b> 768 dimensions requested explicitly, so a provider default change cannot silently make old and new vectors incomparable.",
    "<b>Incremental:</b> a chunk whose source row has not changed since <font name='Mono'>indexed_at</font> is skipped.",
])
H2("Search: scope first, then rank")
CODE("""
def semantic_search(db, query_vector, user, village_id, limit=6, expand=True):
    visible = _visible_chunks(db, user, village_id)     # permission WHERE clause
    scored = [Hit(c, cosine(query_vector, c.embedding or [])) for c in visible]
    scored = [h for h in scored if h.similarity >= MIN_SIMILARITY]   # 0.55
    scored.sort(key=lambda h: h.similarity, reverse=True)
    top = scored[:limit]
    return top + _expand(db, top, visible) if (top and expand) else top
""", "backend/app/services/graph.py (simplified)")
P("Scoping happens <i>before</i> ranking. If it happened after, a chunk from another village would compete for the top-k "
  "slots and the filter would remove it, returning fewer results. Worse, any bug in the post-filter would leak data. "
  "Filtering the candidate set first means a similar enough vector can never become a route around permissions.")
H2("Graph expansion")
P("For each top hit, up to three linked neighbours are pulled in, but only if they were already in the visible set. The "
  "neighbour is labelled with <i>why</i> it is present (\"included because it is in village ...\"), which stops the model "
  "treating incidental context as the subject of the question. This is a one-hop breadth-first expansion with a fan-out cap.")
H2("The privacy boundary: the model may see the village, never the villager")
P("Google's free-tier terms allow submitted content to be used to improve their products. A resident applying for a "
  "widow's pension cannot meaningfully consent to that. Three mechanisms enforce the boundary in code:")
B([
    "<b>Residents are never indexed.</b> Indexing runs over every row whether or not anyone asks a question, so indexing "
    "residents would export the register as a standing cost of the feature.",
    "<b>Personal facts are flagged at retrieval.</b> <font name='Mono'>Retrieved.has_personal</font> is sticky: a set of facts "
    "is only as shareable as its most sensitive member. The assistant refuses to build a prompt from such a set and answers "
    "from the records directly instead.",
    "<b>The decision was never the model's.</b> Eligibility comes from the rule engine, so withholding the record costs "
    "phrasing and nothing else.",
])
P("Anonymisation was considered and rejected. At village scale \"a 52-year-old female agricultural labourer in ward 3\" "
  "identifies one person in a few hundred; stripping the name leaves the record re-identifiable from its quasi-identifiers. "
  "This is the k-anonymity problem, and it is a strong point to raise in an interview.")
H2("Graceful degradation")
P("If there is no index, no API key, an embedding error or no hit above the 0.55 floor, the assistant falls back to keyword "
  "routing over the same scoped queries. If generation fails, <font name='Mono'>plain_answer()</font> renders the retrieved "
  "facts directly. The UI shows which path ran, so nobody has to guess. A bug found only by running the app: for a citizen, "
  "the semantic path returned scheme descriptions instead of their own eligibility, because it returned before the rule engine "
  "ran. The fix layers semantic hits on top of the keyword pass for citizens.")
H2("Resilient model calls")
P("<font name='Mono'>llm.generate()</font> retries 429, 500, 502, 503 and 504 twice with delays of 0.6 s and 1.8 s, and "
  "treats transport errors the same way. A 404 is deliberately not retried, because a retired model name never recovers. "
  "Errors include Google's own message plus a hint, since a bare \"status 404\" sends people checking their key when the "
  "real problem is the model name. A separate <font name='Mono'>/assistant/model-check</font> endpoint makes one real call, "
  "because <font name='Mono'>/health</font> only knows whether a key is set.")

# ════════════════════════════════════════════════════════════════════════════
H1("Grievance classification", 9)
P("A transparent, rule-based classifier over bilingual (English and Marathi) keyword sets. It is <b>not</b> a trained model, "
  "and the project says so plainly. It runs server-side so the same rules apply whether a complaint arrives from the "
  "citizen portal, an officer's desk or the API.")
B([
    "<b>Category:</b> the keyword set with the most hits wins (Water, Sanitation, Roads, Electricity, Health), ties go to the "
    "first listed, no hits means Other.",
    "<b>Priority:</b> escalation terms first (contamination, collapse, electrocution, outbreak, injury, fire gives Critical; "
    "urgent, overflow, burst, school gives High), then category defaults. Drinking water and health default up, not down.",
    "<b>Routing:</b> each category maps to a department, in both languages.",
    "<b>Explainability:</b> the matched terms are returned, so an officer can see why a complaint was routed where it was.",
])
P("<b>Why rules rather than ML?</b> There is no labelled dataset of Haveli grievances to train on, five categories are a small "
  "closed set, and a misrouted complaint needs a visible reason. The retrieval layer imports the same keyword list, so a word "
  "added for classification immediately helps the assistant find matching complaints, and the two cannot drift apart.")
P("<b>Complexity:</b> naive substring search is O(K x L) for K keywords and text length L. With roughly 100 keywords and "
  "short complaints this is negligible. Aho-Corasick would make it O(L + matches) and is discussed in Section 15.")

# ════════════════════════════════════════════════════════════════════════════
H1("Document readers and resident sign-up", 10)
H2("Gram Sabha transcript reader")
P("Text is extracted from the actual uploaded file (PDF via PyMuPDF, DOCX via python-docx, or plain text), capped at 30,000 "
  "characters, and sent to Gemini with a <b>response schema</b>: title, summary, decisions and action items, each in English "
  "and Marathi. Constraining the output to a JSON schema removes a whole class of parsing failures. The system prompt "
  "forbids inventing names, dates or amounts not in the text. The earlier stub returned the same summary whatever was uploaded.")
H2("Government Resolution to scheme")
P("An officer uploads a GR (a published state order announcing a scheme). The model proposes a scheme record with "
  "machine-readable criteria. Three safeguards make this safe enough to use:")
B([
    "<b>Human approval gate.</b> The proposal is saved as <i>pending</i> and reaches no resident until an officer approves it. "
    "A model that read \"60 years\" as a maximum instead of a minimum would invert the scheme for everyone.",
    "<b>Closed vocabulary.</b> Any criteria key the engine does not understand is stripped and reported, not stored. An "
    "unknown key would be silently ignored at evaluation time, making the scheme look stricter on paper than it behaves.",
    "<b>Confidence capped at medium.</b> Nothing read by a model deserves the standing of a hand-verified scheme.",
])
H2("Resident sign-up and record matching")
P("A resident applies; an officer matches them to the village register from a ranked candidate list and approves. "
  "Applying never creates a working login, and officer accounts are created only by an admin. The ranking is a weighted score:")
TABLE(["Signal", "Weight", "Comment"], [
    ["Applicant quoted this citizen ID", "+1.0", "Strongest signal, still only a suggestion"],
    ["Last 10 phone digits match", "+0.8", "Digits only, so formatting and +91 prefixes do not matter"],
    ["Name similarity >= 0.6", "+0.6 x ratio", "difflib.SequenceMatcher (Ratcliff/Obershelp)"],
    ["Same ward", "+0.15", "Weak tie-breaker"],
    ["Threshold", ">= 0.4", "Top 8 shown, confidence capped at 1.0, existing accounts flagged"],
], [62, 28, 80])
P("The function only ranks; a human decides. An unconvincing list is the correct output when the applicant is not in the register.")

# ════════════════════════════════════════════════════════════════════════════
H1("The audit trail", 11)
P("<font name='Mono'>audit_events</font> answers \"who opened Savita's file, and when?\". The key design decision is that it is "
  "written by <b>middleware</b>, not by calls scattered through the routes. A trail built from per-route calls is only as "
  "complete as the last developer remembered to make it, and the endpoint that gets forgotten is always the new one. Here a "
  "request is recorded because it was served.")
TABLE(["Recorded", "Not recorded, deliberately"], [
    ["Every state change by a signed-in user", "Unauthenticated requests: there is nobody to attribute them to"],
    ["Every read that names one record", "List endpoints: they would bury the events worth finding"],
    ["Refused attempts, with their status code", "Request bodies, ever: no incomes, contents or passwords in a log"],
], [85, 85])
B([
    "<b>Entity detection by ordered regex.</b> Patterns are checked longest-first, so <font name='Mono'>/citizens/{id}/documents</font> "
    "is filed under the citizen rather than swallowed by a shorter pattern.",
    "<b>Default is to record.</b> Read-only POSTs (the assistant's <font name='Mono'>/ask</font> and <font name='Mono'>/context</font>) "
    "must be named explicitly to be exempt, so forgetting the list makes the trail noisier, never emptier.",
    "<b>It can never break a request.</b> Failures to write are logged and swallowed. Losing one audit row is bad; refusing a "
    "grievance because the audit table is full is worse.",
    "<b>Admin-only and append-only.</b> No endpoint edits or deletes an event. <font name='Mono'>prune()</font> drops rows older than a year.",
])

# ════════════════════════════════════════════════════════════════════════════
H1("The frontend", 12)
P("Twenty-two components cover the officer workspace (dashboard, citizens, grievances, projects, Gram Sabha, GIS, analytics, "
  "assistant, registration review, audit trail, district overview) and the citizen portal (own file, schemes, grievances).")
H2("A typed client with one transparent refresh")
P("<font name='Mono'>src/lib/api.ts</font> wraps <font name='Mono'>fetch</font>. Any non-2xx response throws an "
  "<font name='Mono'>ApiError</font> carrying the server's own message, so a failed save looks failed. On a 401 the client "
  "tries the refresh token once and replays the original request; if that also fails, the session-expired handler signs the "
  "user out.")
H2("Two hooks instead of a state library")
CODE("""
export function useQuery<T>(fetcher: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const fetcherRef = useRef(fetcher);  fetcherRef.current = fetcher;

  useEffect(() => {
    let cancelled = false;                       // ignore stale responses
    setLoading(true); setError(null);
    fetcherRef.current()
      .then(r => { if (!cancelled) setData(r); })
      .catch(e => { if (!cancelled) setError(errorMessage(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [...deps, tick]);

  return { data, loading, error, refetch: useCallback(() => setTick(n => n + 1), []) };
}
""", "src/lib/useApi.ts (abridged)")
P("Two details an interviewer may probe: the <b>cancelled flag</b> prevents a slow earlier response from overwriting a newer "
  "one (a race condition when dependencies change quickly), and the <b>fetcher ref</b> lets callers pass inline arrow functions "
  "without triggering an infinite effect loop.")
H2("Maps, charts and language")
B([
    "<b>GIS:</b> Leaflet over OpenStreetMap tiles; markers come from the API's own coordinates. Villages without a verified centre "
    "make the map fit to whatever is plotted, and the screen says so. Wadhu Khurd is left unplaced on purpose because two villages "
    "with near-identical names sit a few hundred metres apart: an unplaced village is honest, a misplaced one is not.",
    "<b>Charts:</b> Recharts for analytics dashboards.",
    "<b>Language:</b> i18next with English and Marathi resource bundles; the backend returns paired fields (name / nameMr).",
])

# ════════════════════════════════════════════════════════════════════════════
H1("Testing, deployment and operations", 13)
H2("Testing")
P("The backend suite has <b>284 tests, all passing</b> (about 53 seconds locally). Tests run against SQLite for speed, which is "
  "why <font name='Mono'>as_utc()</font> and the <font name='Mono'>none_as_null</font> fix exist: dialect differences were caught "
  "by tests rather than by users.")
TABLE(["File", "Focus"], [
    ["test_api.py", "Every resource end to end: create, read, update, role refusals, eligibility verdicts"],
    ["test_semantic_retrieval.py", "Cosine maths, scoping before ranking, expansion limits, fallbacks, no residents in the index"],
    ["test_password_reset.py", "Permissions, expiry, single use, alphabet, session revocation"],
    ["test_village_isolation.py", "The neighbouring officer, route by route"],
    ["test_registration.py", "Applications, candidate ranking, approval, no login before approval"],
    ["test_audit.py", "What is and is not recorded, entity detection, failure isolation"],
    ["test_scheme_reader.py", "Closed vocabulary stripping, pending status, confidence cap"],
    ["test_rate_limit.py", "Thresholds, lockout expiry, unknown-email parity"],
    ["test_llm_retry.py", "Retry on 503, no retry on 404, transport errors"],
    ["test_seed_data.py", "Seed integrity: real LGD codes, coordinates inside the Haveli bounding box"],
], [55, 115])
H2("Deployment")
B([
    "<b>render.yaml</b> declares two services: the API (Docker, Singapore region, health check on /health) and the static site.",
    "<b>Migrations on boot:</b> the container runs <font name='Mono'>alembic upgrade head</font> before uvicorn starts with two workers.",
    "<b>Secrets</b> are marked <font name='Mono'>sync: false</font>, so they live in Render, never in the public repository.",
    "<b>VITE_API_URL</b> is baked in at build time, so changing it needs a rebuild, not a restart.",
    "<b>Fingerprinted assets</b> are cached for a year with <font name='Mono'>immutable</font>.",
    "<b>Keep-alive:</b> the README specifies a GitHub Action (<font name='Mono'>.github/workflows/keepalive.yml</font>) that pings the API every six hours so Supabase does not pause the free project. Note that this workflow file is not yet committed to the repository, so it needs adding before relying on it.",
])
NOTE("<b>The CORS trap.</b> If <font name='Mono'>CORS_ORIGINS</font> is wrong, the site loads, every request fails, the browser "
     "shows a CORS error and the API log shows nothing, because the browser blocked the request before it was sent. Knowing why "
     "the server log is empty is a good sign of real debugging experience.", color=SAFFRON, bg=QBG)

# ════════════════════════════════════════════════════════════════════════════
H1("Honest limitations and how it would scale", 14)
H2("What the system does not have")
B([
    "No trained or fine-tuned model of its own; the classifier is rules, the engine is rules.",
    "No OCR for scanned documents, no Aadhaar or DigiLocker integration, no SMS or payment gateway.",
    "Two languages only. A resident must visit the office to reset a password.",
    "The free API instance sleeps after 15 minutes; the first request after that waits roughly a minute.",
    "Grievance free text and uploaded minutes can still carry names to the model; structured fields are controlled, prose is not.",
])
H2("From one block to a whole state")
TABLE(["Pressure point", "Today", "At district or state scale"], [
    ["Vector search", "Linear cosine scan in Python over about 67 chunks", "pgvector column with an HNSW or IVFFlat index behind the same semantic_search() function"],
    ["Eligibility screening", "On request, O(C x S x R)", "Precompute verdicts in a background job, invalidate on record or scheme change"],
    ["Rate limiting", "COUNT over auth_attempts", "Redis with a sliding-window or token-bucket counter; keep the table for audit"],
    ["Audit trail", "Synchronous insert in middleware", "Write to a queue (Pub/Sub, Kafka) and batch into a partitioned table"],
    ["Sessions", "Stateless JWT + tokens_valid_from", "Same design; add key rotation with a kid header"],
    ["Model calls", "One free key, retries", "Paid tier with data-use guarantees, request queue, per-user quotas, response caching"],
    ["Cold starts", "Free instance sleeps", "Always-on instances behind a load balancer; database read replicas"],
], [35, 58, 77])

# ════════════════════════════════════════════════════════════════════════════
H1("Interview question bank: data structures and algorithms", 15)
P("These are the questions a senior engineer is most likely to build out of this specific project. Each answer is written the "
  "way you would say it out loud: the direct answer first, then the reasoning, then the trade-off.")

QA("Q1. What is the time complexity of your semantic search, and how would you improve it?",
   ["Today it is O(N x d) to score N chunks of dimension d, then O(N log N) to sort. With N about 67 and d = 768 that is around "
    "fifty thousand multiply-adds, well under a millisecond.",
    "Two improvements. First, we only need the top k, so a min-heap of size k gives O(N log k) instead of a full sort. Second, "
    "if vectors are normalised once at index time, cosine becomes a plain dot product, removing two square roots per comparison. "
    "Beyond about 100,000 chunks I would move to approximate nearest neighbour search (HNSW or IVFFlat in pgvector), which is "
    "roughly logarithmic per query at the cost of occasionally missing a true neighbour."],
   """
import heapq
def top_k(query, chunks, k=6, floor=0.55):
    heap = []                                   # min-heap of (score, idx)
    for i, c in enumerate(chunks):
        s = dot(query, c.unit_vec)              # pre-normalised -> cosine
        if s < floor:
            continue
        if len(heap) < k:
            heapq.heappush(heap, (s, i))
        elif s > heap[0][0]:
            heapq.heapreplace(heap, (s, i))
    return sorted(heap, reverse=True)           # O(N log k) overall
""")

QA("Q2. Why cosine similarity and not Euclidean distance?",
   ["Cosine measures direction and ignores magnitude, and for text embeddings the direction carries the meaning. For unit vectors "
    "the two are equivalent for ranking, because ||a - b||^2 = 2 - 2cos(a, b). So normalising and then using either gives the same order."])

QA("Q3. Explain HNSW versus IVFFlat as if I were choosing for this project.",
   ["IVFFlat clusters vectors with k-means into lists and searches only the nearest few lists. It builds quickly and uses little memory, "
    "but recall depends on how many lists you probe and it needs data present before the index is built.",
    "HNSW builds a layered proximity graph and searches it greedily from the top layer down. It has better recall at the same speed and "
    "handles inserts well, at the cost of more memory and slower builds. For a growing index with frequent small updates, like grievances "
    "being filed daily, I would choose HNSW."])

QA("Q4. Your graph expansion: which traversal is it, and what is its cost?",
   ["It is a one-hop breadth-first expansion with a fan-out cap of three links per hit and a visited set. With k hits the cost is "
    "O(k x 3) dictionary lookups after an O(N) pass to build the (type, id) map. The visited set prevents duplicates; the visibility "
    "map prevents expansion becoming a route around permissions. Going to two hops would be a standard BFS with a depth limit, but the "
    "context would grow quickly and dilute relevance, so the cap is a deliberate precision choice."])

QA("Q5. The grievance classifier does substring search for about 100 keywords. How would you make it scale to 10,000 keywords?",
   ["Build an Aho-Corasick automaton: a trie of all keywords with failure links. Matching then takes O(L + z) for text length L and "
    "z matches, independent of the number of keywords, after O(total keyword length) preprocessing. Today's naive approach is O(K x L)."],
   """
from collections import deque
def build(words):
    goto, fail, out = [{}], [0], [set()]
    for w in words:
        s = 0
        for ch in w:
            if ch not in goto[s]:
                goto.append({}); fail.append(0); out.append(set())
                goto[s][ch] = len(goto) - 1
            s = goto[s][ch]
        out[s].add(w)
    q = deque(goto[0].values())
    while q:
        r = q.popleft()
        for ch, s in goto[r].items():
            q.append(s)
            f = fail[r]
            while f and ch not in goto[f]:
                f = fail[f]
            fail[s] = goto[f].get(ch, 0) if goto[f].get(ch, 0) != s else 0
            out[s] |= out[fail[s]]
    return goto, fail, out

def search(text, goto, fail, out):
    s, found = 0, set()
    for ch in text:
        while s and ch not in goto[s]:
            s = fail[s]
        s = goto[s].get(ch, 0)
        found |= out[s]
    return found
""")

QA("Q6. Your rate limiter counts rows in a fixed lookback window. Compare that with a token bucket and a sliding window counter.",
   ["What we have is effectively a <b>sliding log</b>: every attempt is stored with a timestamp and we count those inside the last 15 "
    "minutes. It is exact and doubles as an audit trail, but each check is a COUNT query, O(log n) with an index on (email, created_at).",
    "A <b>fixed window</b> counter is O(1) but allows a burst of 2x the limit across a window boundary. A <b>sliding window counter</b> "
    "approximates the log by weighting the previous window's count, O(1) memory per key. A <b>token bucket</b> refills at a steady rate "
    "and allows controlled bursts, O(1) per key. At scale I would put a token bucket or sliding counter in Redis and keep the table for "
    "audit only."],
   """
import time
class TokenBucket:
    def __init__(self, capacity, refill_per_sec):
        self.cap, self.rate = capacity, refill_per_sec
        self.tokens, self.last = capacity, time.monotonic()
    def allow(self):
        now = time.monotonic()
        self.tokens = min(self.cap, self.tokens + (now - self.last) * self.rate)
        self.last = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False
""")

QA("Q7. Is there a race condition in the throttle? Two wrong guesses arrive at the same instant.",
   ["Yes, a small one. Both requests can read a count of four, both pass the check, both run bcrypt, and both record a failure, so the "
    "attacker gets six guesses instead of five. The window of opportunity is one bcrypt verification long. It is acceptable here because "
    "the goal is to make guessing impractical, not to enforce an exact number. If exactness mattered, I would use an atomic increment "
    "(Redis INCR, or an UPSERT with RETURNING on a counter row) and check the returned value."])

QA("Q8. How many reset codes are possible, and is that enough?",
   ["30 characters over 10 positions gives 30^10, about 5.9 x 10^14, roughly 49 bits. Redemption is limited to a handful of attempts per "
    "window, and the code expires in 24 hours. Even ignoring expiry, at five guesses per 15 minutes an attacker would need on the order "
    "of 10^12 years for a 50 percent chance. The entropy is far larger than the attempt budget, which is the right relationship."])

QA("Q9. You use difflib.SequenceMatcher for name matching. What does it compute, and what would you use instead?",
   ["It is the Ratcliff/Obershelp algorithm: it recursively finds the longest common substring and scores 2M / T, where M is matched "
    "characters and T is the total length. Worst case is roughly quadratic, which is fine for short names.",
    "Alternatives: Levenshtein edit distance (dynamic programming, O(m x n)), Jaro-Winkler, which favours common prefixes and suits personal "
    "names, or a phonetic encoding for Indian names transliterated in different ways (Patil, Paatil). For many candidates I would first "
    "block on ward or phone digits to avoid comparing against everyone."],
   """
def levenshtein(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1,            # deletion
                           cur[j - 1] + 1,         # insertion
                           prev[j - 1] + (ca != cb)))  # substitution
        prev = cur
    return prev[-1]          # O(m*n) time, O(n) space
""")

QA("Q10. The any_of evaluation is recursive. Could that blow the stack?",
   ["In principle a maliciously nested criteria dictionary could exceed Python's default recursion limit of about 1,000. In practice criteria "
    "are written by officers or by the scheme reader, which strips unknown keys. The fix is a depth limit at validation time, or converting "
    "the evaluation to an explicit stack. Real schemes nest at most two levels."])

QA("Q11. Why do you hash the entity key with SHA-1 to make chunk IDs? Isn't SHA-1 broken?",
   ["SHA-1 is broken for collision resistance against an adversary, but here it is not a security primitive. It is a deterministic way to "
    "turn 'grievance:griev_201' into a fixed-length ID, so re-indexing updates the same row instead of creating a duplicate. The inputs are "
    "our own keys, not attacker-controlled, and the unique constraint on (entity_type, entity_id) is the real guarantee. Any stable hash would do."])

QA("Q12. How does the audit middleware decide which record a path refers to, and what is the complexity?",
   ["It tries an ordered list of compiled regular expressions, longest and most specific first, and takes the first match. With P patterns "
    "and a path of length L that is O(P x L) in the worst case, which is tiny. Order matters because the shorter /citizens/{id} pattern would "
    "otherwise capture /citizens/{id}/documents. A trie of path segments would be the scalable alternative, and is essentially what routers use."])

QA("Q13. Document matching uses bidirectional substring checks after normalisation. What can go wrong?",
   ["Very short names can over-match: a document typed as 'ID' is a substring of many requirement names. Mitigations are a minimum length "
    "before substring matching, token-level matching instead of character-level, or a canonical document-type table so uploads choose from "
    "a list rather than free text. The last one is the right long-term fix."])

QA("Q14. What data structures would you use to compute the most complained-about ward per category in real time?",
   ["A hash map from (category, ward) to count gives O(1) updates. For the maximum per category, keep a per-category max-heap with lazy "
    "deletion, or simply recompute the max over the small number of wards, since a village has under twenty. At district scale, a SQL "
    "GROUP BY with an index on (village_id, category, ward), or a materialised view refreshed on write, is simpler than a custom structure."])

# ════════════════════════════════════════════════════════════════════════════
H1("Interview question bank: system design and security", 16)

QA("S1. Design E-Panchayat for all 27,000 Gram Panchayats in Maharashtra.",
   ["<b>Requirements first:</b> roughly 27,000 villages, tens of millions of residents, peak load on scheme deadlines, strict privacy, "
    "unreliable rural connectivity, and Marathi as the primary language.",
    "<b>Data:</b> PostgreSQL partitioned or sharded by district, because almost every query is already scoped to one village and therefore "
    "one district. Village scoping becomes the shard key for free. Read replicas for analytics.",
    "<b>Services:</b> keep the API stateless behind a load balancer and autoscale it. Move the eligibility screening, indexing and audit writes "
    "to asynchronous workers fed by a queue.",
    "<b>Retrieval:</b> pgvector with HNSW per district partition, or a managed vector store, with the same scope-before-rank rule enforced "
    "as a filter in the index query.",
    "<b>AI:</b> a paid, contractually private model tier or a self-hosted open model inside a government cloud, plus a prompt and response "
    "cache for repeated village-level questions.",
    "<b>Offline:</b> a progressive web app with a service worker queue, so an officer can register a grievance without signal and sync later; "
    "conflicts resolved by last-writer-wins on independent fields and an explicit status-history log for grievances."])

QA("S2. Why is scoping before ranking safer than filtering after?",
   ["Post-filtering is a two-step contract where the second step is easy to forget, reorder or break. Pre-filtering makes the forbidden "
    "records simply absent from the computation. It also gives better results, because forbidden records cannot occupy top-k slots that "
    "are then thrown away. The principle is the same as parameterised SQL: make the unsafe state unrepresentable rather than detected."])

QA("S3. JWTs are stateless. How do you log someone out everywhere?",
   ["With a per-user revocation timestamp. Every request already loads the user to check is_active, so comparing the token's iat with "
    "tokens_valid_from costs nothing extra. It revokes all tokens for a user at once, which is exactly what a password reset needs. "
    "Revoking a single device would need a token ID (jti) denylist, typically in Redis with a TTL equal to the token's remaining lifetime."])

QA("S4. Walk me through what happens when an officer of Theur requests GET /citizens/cit_102, a Loni Kalbhor resident.",
   ["The request passes CORS, then the audit middleware wraps it. FastAPI resolves dependencies: the bearer token is decoded, its type "
    "checked, the user loaded, active status and revocation checked. The route calls assert_can_read_citizen, which computes the officer's "
    "scope (Theur), loads cit_102, sees village Loni Kalbhor, and raises 403. The middleware records a refused read against citizen cit_102 "
    "with status 403. The response body says the record belongs to another Gram Panchayat. There is a test for exactly this case."])

QA("S5. What are the main OWASP risks for this system and where are they handled?",
   ["Broken access control (IDOR) by by-ID village guards; cryptographic failures by bcrypt and server-only secrets; injection by SQLAlchemy "
    "parameterised queries; identification and authentication failures by throttling, revocation and identical responses for unknown emails; "
    "security misconfiguration by exact CORS origins and secrets outside the repository; logging and monitoring by the audit trail. One honest "
    "gap: tokens are kept in localStorage, which is readable by any injected script, so a strict Content Security Policy would be the next step, "
    "or moving the refresh token to an HttpOnly cookie."])

QA("S6. Why not let the LLM decide eligibility? It reads the rules better than regex.",
   ["Because the output has to be reproducible, auditable and explainable to the person refused. The same inputs must give the same answer "
    "tomorrow and the officer must point to the rule. LLMs are non-deterministic and can hallucinate a threshold. We use the model where it "
    "is strong (reading a Government Resolution into a draft), and keep a human and a deterministic engine where the decision is made."])

QA("S7. How do you know the assistant is not hallucinating?",
   ["Four layers. The system prompt forbids facts outside the supplied records. Retrieval returns sources with every answer, so a claim can "
    "be checked against its row. A similarity floor of 0.55 keeps weak matches out, because the model treats anything it is given as relevant. "
    "And anything about an individual resident is answered from the records without the model at all. What we do not have, and would add, "
    "is an automated evaluation set of questions with expected source records, measuring retrieval recall and answer faithfulness."])

QA("S8. The free tier returns 503 under load. How did you handle it, and what would you do in production?",
   ["Retries with backoff on 429 and 5xx, no retry on 404, and graceful fallback to a records-only answer that the UI labels. In production: "
    "exponential backoff with jitter to avoid synchronised retries, a circuit breaker so a dead upstream fails fast, a per-user quota, and a "
    "paid tier. We also learned to pin a model version, because 'latest' aliases resolve to the newest and busiest model."])

QA("S9. Why is the audit trail middleware and not a decorator?",
   ["A decorator still has to be remembered on every new route; middleware does not. The failure mode of a forgotten decorator is a silent "
    "gap in the trail, exactly where nobody looks. The middleware default is to record, and exemptions must be named, so the failure mode of "
    "forgetting becomes extra noise rather than missing evidence."])

QA("S10. How would you add a third language, Hindi, without breaking anything?",
   ["Frontend: add a resource bundle to i18next. Backend: the paired name / name_mr columns do not scale, so I would move translatable text "
    "into a translations table keyed by (entity, field, locale) with fallback to English, migrate the Marathi columns into it with Alembic, "
    "and keep the API shape stable by resolving the requested locale server-side."])

# ════════════════════════════════════════════════════════════════════════════
H1("Coding exercises drawn from the project", 17)
P("Interviewers like to take a real component and ask you to write a clean version on the whiteboard. These five are the most likely, each "
  "with a solution and the follow-up you should expect.")

H2("Exercise 1: evaluate nested eligibility criteria")
P("Given a resident as a dictionary and criteria with min_age, max_income, requires_bpl and nested any_of groups, return PASS, FAIL or UNKNOWN.")
CODE("""
PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"

def evaluate(person: dict, crit: dict) -> str:
    verdict = PASS
    def worse(a, b):                       # FAIL beats UNKNOWN beats PASS
        order = {PASS: 0, UNKNOWN: 1, FAIL: 2}
        return a if order[a] >= order[b] else b

    if "min_age" in crit:
        verdict = worse(verdict, PASS if person["age"] >= crit["min_age"] else FAIL)
    if "max_income" in crit:
        verdict = worse(verdict, PASS if person["income"] <= crit["max_income"] else FAIL)
    if crit.get("requires_bpl"):
        bpl = person.get("is_bpl")
        verdict = worse(verdict, UNKNOWN if bpl is None else (PASS if bpl else FAIL))

    if "any_of" in crit:
        results = [evaluate(person, b) for b in crit["any_of"]]
        group = PASS if PASS in results else (UNKNOWN if UNKNOWN in results else FAIL)
        verdict = worse(verdict, group)
    return verdict
""", "Three-valued AND across keys, three-valued OR inside any_of")
P("<b>Follow-up:</b> \"Make it iterative.\" Use an explicit stack of frames (criteria, partial results), or validate depth before evaluating. "
  "<b>Complexity:</b> O(number of rule nodes).")

H2("Exercise 2: a sliding-log rate limiter")
CODE("""
from collections import defaultdict, deque
import time

class SlidingLogLimiter:
    def __init__(self, limit: int, window_s: float):
        self.limit, self.window = limit, window_s
        self.log = defaultdict(deque)          # key -> timestamps of failures

    def allowed(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        q = self.log[key]
        while q and q[0] <= now - self.window:   # evict expired entries
            q.popleft()
        return len(q) < self.limit

    def record_failure(self, key: str, now: float | None = None) -> None:
        self.log[key].append(time.monotonic() if now is None else now)
""", "Amortised O(1) per call; O(limit) memory per key")
P("<b>Follow-up:</b> \"Why record only failures?\" Because counting refusals would renew the window forever. \"How do you stop memory "
  "growing with many keys?\" Periodically drop keys whose deque is empty, or use a TTL cache.")

H2("Exercise 3: single-flight token refresh")
P("Five requests fail with 401 at once. Make sure only one refresh call is made and all five retry with the new token.")
CODE("""
let refreshing: Promise<boolean> | null = null;

async function refreshOnce(): Promise<boolean> {
  if (!refreshing) {
    refreshing = attemptRefresh().finally(() => { refreshing = null; });
  }
  return refreshing;                 // every caller awaits the same promise
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res = await send(path, init);
  if (res.status === 401 && await refreshOnce()) {
    res = await send(path, init);    // one retry with the new token
  }
  if (!res.ok) throw new ApiError(res.status, await messageFrom(res));
  return res.json() as Promise<T>;
}
""", "TypeScript: sharing an in-flight promise")
P("This is an improvement over the current client, which retries once per request and could fire several refreshes in parallel. It is a "
  "good thing to volunteer: it shows you know where your own code could be better.")

H2("Exercise 4: top-k with graph expansion")
CODE("""
import heapq

def retrieve(q, chunks, links, k=6, fanout=3, floor=0.55):
    # chunks: id -> unit vector (already scoped); links: id -> [neighbour ids]
    scored = ((sum(a*b for a, b in zip(q, v)), cid) for cid, v in chunks.items())
    top = heapq.nlargest(k, (s for s in scored if s[0] >= floor))
    seen = {cid for _, cid in top}
    expanded = []
    for score, cid in top:
        for n in links.get(cid, [])[:fanout]:
            if n in chunks and n not in seen:   # must already be visible
                seen.add(n)
                expanded.append((score, n, f"via {cid}"))
    return top, expanded
""", "O(N·d + N log k + k·fanout)")

H2("Exercise 5: merge overlapping project timelines")
P("Given development projects as (start, end) dates, return the periods when at least one project was active, to show on the analytics page.")
CODE("""
def merge(intervals):
    intervals.sort()                         # O(n log n)
    out = []
    for s, e in intervals:
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out
""", "Classic interval merge")
P("<b>Variant:</b> \"Maximum number of projects running at once\" is a sweep line: +1 at each start, -1 at each end, sort events, track the running maximum.")

# ════════════════════════════════════════════════════════════════════════════
H1("Behavioural and viva questions", 18)
P("Senior engineers ask these to see judgement, ownership and honesty. Good answers are specific and include what went wrong.")
QA("B1. Tell me about a bug you are proud of finding.",
   ["The village isolation gap. List endpoints were scoped, so the neighbouring officer saw an empty list and every test passed. But records "
    "could still be opened by ID, and our IDs are guessable. It went unnoticed because all ten seeded residents lived in one village, so the "
    "fixtures could not express the bug. We fixed it centrally in deps.py, so new routes cannot forget it, and wrote 24 tests that sign in "
    "as the officer next door and try every by-ID route."])
QA("B2. Tell me about a decision you would make differently.",
   ["Keeping tokens in localStorage. It was the quickest way to survive a page reload, but it exposes them to any injected script. With more "
    "time I would move the refresh token into an HttpOnly, SameSite cookie and keep the access token in memory only."])
QA("B3. How did you decide what not to build?",
   ["We wrote an honest capability statement in the README and checked every feature against it: no trained model, no OCR, no Aadhaar, no SMS. "
    "Saying 'AI classifier' about a keyword list would have been easy and wrong. Being exact about what the system is protects the people "
    "who would rely on it."])
QA("B4. What was the hardest trade-off?",
   ["Privacy against answer quality in the assistant. Sending a resident's record to the model would produce nicer sentences. We decided the "
    "model may see the village and never the villager, because the eligibility decision was never the model's anyway. We lose some fluency "
    "and gain a guarantee that does not depend on a vendor's terms."])
QA("B5. How did you work as a team?",
   ["Small, reviewable commits with messages that explain why, a README that doubles as the design document, and tests written alongside each "
    "fix so a regression would be caught by someone else's change. Infrastructure is in render.yaml so nothing depends on one person remembering "
    "dashboard settings."])
H2("Quick-fire viva answers")
TABLE(["Question", "One-line answer"], [
    ["What is RAG?", "Retrieve relevant records first, then generate an answer constrained to them, with sources."],
    ["What is an embedding?", "A fixed-length vector (768 floats here) whose direction captures the meaning of a text."],
    ["Why bcrypt?", "Deliberately slow, salted hashing; each guess is expensive and identical passwords hash differently."],
    ["What is LGD?", "The Local Government Directory: official codes for every Indian state, district, block and village."],
    ["Why FastAPI's Depends?", "Composable guards; auth and scoping are declared per route and cannot be skipped by the handler."],
    ["What is CORS?", "A browser rule that blocks cross-origin requests unless the server lists the calling origin."],
    ["What does Alembic do?", "Versioned, reversible database schema migrations, applied automatically on deployment."],
    ["Why HTTP 429?", "Too Many Requests, with a Retry-After header telling the client when to try again."],
    ["What is IDOR?", "Opening another user's record by changing an ID; prevented by checking ownership on every by-ID route."],
    ["What is SECC-2011?", "The Socio-Economic Caste Census, used by PMAY-G and Ayushman Bharat to identify deprived households."],
    ["Why a response schema?", "It forces the model to return valid JSON of a known shape, removing parsing failures."],
    ["Why a similarity floor?", "Weak matches are worse than none; the model treats whatever it receives as relevant."],
], [52, 118])

# ════════════════════════════════════════════════════════════════════════════
H1("Glossary", 19)
TABLE(["Term", "Meaning"], [
    ["Gram Panchayat", "Elected village-level local government in India"],
    ["Gram Sabha", "Assembly of all adult residents of a village; its decisions are public record"],
    ["GR (Shasan Nirnay)", "Government Resolution: a published state order, often announcing or changing a scheme"],
    ["BPL", "Below Poverty Line list, a common eligibility gate"],
    ["Ration card types", "Yellow, Orange, AAY (Antyodaya), Annapurna, White; several health schemes depend on them"],
    ["7/12 extract", "Maharashtra's land record document, used to prove land holding"],
    ["Haveli", "A taluka (block) of Pune district; the project's 23 villages are here"],
    ["Access / refresh token", "Short-lived credential for API calls / longer-lived credential used only to get new access tokens"],
    ["IDOR", "Insecure Direct Object Reference: reaching a record you should not by guessing its ID"],
    ["k-anonymity", "A record is k-anonymous if at least k people share its quasi-identifiers; tiny villages make k small"],
    ["HNSW / IVFFlat", "Approximate nearest-neighbour index types available in pgvector"],
    ["Aho-Corasick", "Multi-pattern string matching in time linear in the text"],
    ["Fail closed", "When something is missing or broken, deny access rather than grant it"],
], [45, 125])
story.append(Spacer(1, 14))
NOTE("This handbook describes the repository at commit 897818c. If the code changes, the section on the module concerned should be "
     "updated in the same pull request, the same way the project keeps its README in step with its code.")

doc.multiBuild(story)
print("ok", OUT)
