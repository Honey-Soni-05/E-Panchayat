from pathlib import Path
from math import ceil
from PIL import Image, ImageDraw, ImageFont

from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "E-Panchayat_Research_Paper_Final_10_Pages.docx"

INK = "1F2937"
BLUE = "17365D"
MID_BLUE = "D9EAF7"
LIGHT_BLUE = "EDF5FB"
GRID = "D9E2F3"
GRAY = "F6F8FA"
FONT = "Times New Roman"


def pc(value):
    """Convert Word-style RGB values to a colour accepted by Pillow."""
    return value if value.startswith("#") else "#" + value


def font(path, size, bold=False):
    candidates = [
        r"C:\Windows\Fonts\times.ttf" if not bold else r"C:\Windows\Fonts\timesbd.ttf",
        r"C:\Windows\Fonts\calibri.ttf" if not bold else r"C:\Windows\Fonts\calibrib.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def arrow(draw, start, end, color=BLUE, width=5, head=13):
    color = pc(color)
    x1, y1 = start
    x2, y2 = end
    draw.line((x1, y1, x2, y2), fill=color, width=width)
    # A compact triangular head; all arrows here are horizontal or vertical.
    if abs(x2 - x1) >= abs(y2 - y1):
        sign = 1 if x2 > x1 else -1
        draw.polygon([(x2, y2), (x2 - sign * head, y2 - head * 0.62), (x2 - sign * head, y2 + head * 0.62)], fill=color)
    else:
        sign = 1 if y2 > y1 else -1
        draw.polygon([(x2, y2), (x2 - head * 0.62, y2 - sign * head), (x2 + head * 0.62, y2 - sign * head)], fill=color)


def rounded_box(draw, box, title, lines=(), fill="FFFFFF", outline=BLUE, title_fill=None, scale=2):
    radius = 18
    draw.rounded_rectangle(box, radius=radius, fill=pc(fill), outline=pc(outline), width=3)
    x1, y1, x2, y2 = box
    if title_fill:
        draw.rounded_rectangle((x1, y1, x2, y1 + 39), radius=radius, fill=pc(title_fill))
        draw.rectangle((x1, y1 + 20, x2, y1 + 39), fill=pc(title_fill))
    tf = font(None, 25, True)
    bf = font(None, 19, False)
    title_color = "FFFFFF" if title_fill else INK
    draw.text(((x1 + x2) / 2, y1 + 10), title, font=tf, fill=pc(title_color), anchor="ma")
    yy = y1 + (57 if title_fill else 40)
    for line in lines:
        draw.text(((x1 + x2) / 2, yy), line, font=bf, fill=pc(INK), anchor="ma")
        yy += 29


def make_architecture(path):
    S = 1
    W, H = 1700, 950
    im = Image.new("RGB", (W, H), pc("FFFFFF"))
    d = ImageDraw.Draw(im)
    h = font(None, 35, True)
    d.text((W / 2, 34), "E-Panchayat system architecture", font=h, fill=pc(INK), anchor="ma")

    rounded_box(d, (75, 110, 445, 290), "Users", ("Citizen portal", "Panchayat officer", "Administrator"), MID_BLUE, BLUE, BLUE)
    rounded_box(d, (665, 110, 1035, 290), "Web application", ("React and Vite", "English and Marathi", "Role-aware interface"), "FFFFFF", BLUE, BLUE)
    rounded_box(d, (1255, 110, 1625, 290), "Hosted services", ("Render deployment", "Static frontend", "FastAPI web service"), MID_BLUE, BLUE, BLUE)
    arrow(d, (445, 200), (665, 200))
    arrow(d, (1035, 200), (1255, 200))

    rounded_box(d, (90, 400, 470, 640), "FastAPI service", ("JWT and RBAC", "Village-scoped queries", "Audit middleware"), "FFFFFF", BLUE, BLUE)
    rounded_box(d, (610, 380, 1090, 670), "Decision and intelligence", ("Eligibility rule engine", "Grievance classifier", "Retrieval and graph expansion", "Personal-answer template"), LIGHT_BLUE, BLUE, BLUE)
    rounded_box(d, (1230, 400, 1610, 640), "Data layer", ("PostgreSQL via Supabase", "18 relational tables", "Knowledge chunks"), "FFFFFF", BLUE, BLUE)
    arrow(d, (850, 290), (850, 380))
    arrow(d, (470, 520), (610, 520))
    arrow(d, (1090, 520), (1230, 520))

    rounded_box(d, (530, 780, 1170, 890), "External LLM", ("Non-personal village context only", "Resident records and personal queries remain local"), "FFF4E5", "C26A00", "C26A00")
    arrow(d, (850, 670), (850, 780), "C26A00")
    im.save(path, dpi=(220, 220))


def diamond(draw, center, width, height, text, fill, outline, scale=2):
    x, y = center
    pts = [(x, y - height // 2), (x + width // 2, y), (x, y + height // 2), (x - width // 2, y)]
    draw.polygon(pts, fill=pc(fill), outline=pc(outline))
    tf = font(None, 15 * scale, True)
    words = text.split("\n")
    yy = y - (len(words) - 1) * 10 * scale
    for line in words:
        draw.text((x, yy), line, font=tf, fill=pc(INK), anchor="mm")
        yy += 20 * scale


def small_box(draw, box, text, fill="FFFFFF", outline=BLUE, scale=2):
    draw.rounded_rectangle(box, radius=13 * scale, fill=pc(fill), outline=pc(outline), width=3 * scale)
    tf = font(None, 14 * scale, True)
    x1, y1, x2, y2 = box
    lines = text.split("\n")
    yy = (y1 + y2) / 2 - (len(lines) - 1) * 11 * scale
    for line in lines:
        draw.text(((x1 + x2) / 2, yy), line, font=tf, fill=pc(INK), anchor="mm")
        yy += 22 * scale


def make_activity(path):
    S = 2
    W, H = 1600, 1120
    im = Image.new("RGB", (W, H), pc("FFFFFF"))
    d = ImageDraw.Draw(im)
    h = font(None, 24 * S, True)
    d.text((W / 2, 34), "Activity flow for a service request or assistant query", font=h, fill=pc(INK), anchor="ma")
    small_box(d, (610, 95, 990, 175), "Start: user signs in", MID_BLUE)
    diamond(d, (800, 270), 300, 125, "Role and village\nscope resolved", "FFFFFF", BLUE)
    small_box(d, (610, 385, 990, 470), "Select service: schemes, grievance, records, assistant", LIGHT_BLUE)
    diamond(d, (800, 575), 340, 130, "Does the request identify\na resident?", "FFFFFF", BLUE)
    small_box(d, (100, 690, 540, 790), "Evaluate eligibility or read the\nresident file locally", "FFF4E5", "C26A00")
    small_box(d, (1060, 690, 1500, 790), "Retrieve permitted village facts\nand expand linked records", LIGHT_BLUE)
    small_box(d, (100, 890, 540, 990), "Return template answer with\nverdict, reasons and next step", "FFF4E5", "C26A00")
    small_box(d, (1060, 890, 1500, 990), "Generate answer from retrieved\nnon-personal context and sources", LIGHT_BLUE)
    small_box(d, (610, 1025, 990, 1100), "Display result and write audit event", MID_BLUE)
    arrow(d, (800, 175), (800, 208))
    arrow(d, (800, 332), (800, 385))
    arrow(d, (800, 470), (800, 510))
    arrow(d, (630, 615), (320, 690))
    arrow(d, (970, 615), (1280, 690))
    f = font(None, 14 * S, True)
    d.text((492, 637), "Yes", font=f, fill=pc("9A3412"), anchor="mm")
    d.text((1105, 637), "No", font=f, fill=pc(BLUE), anchor="mm")
    arrow(d, (320, 790), (320, 890), "C26A00")
    arrow(d, (1280, 790), (1280, 890))
    arrow(d, (540, 940), (610, 1062), "C26A00")
    arrow(d, (1060, 940), (990, 1062))
    im.save(path, dpi=(220, 220))


def make_equations():
    """Render the formal models as high-resolution equation figures."""
    math_font = r"C:\Windows\Fonts\cambria.ttc"
    regular = r"C:\Windows\Fonts\times.ttf"
    formula_font = ImageFont.truetype(math_font if Path(math_font).exists() else regular, 46)
    small_font = ImageFont.truetype(math_font if Path(math_font).exists() else regular, 37)

    equations = [
        ("equation_1.png", ["P(r, s) = ∧ c∈Cₛ c(r)          Aₛ(r) = ∨ⱼ₌₁ᵐ ∧ c∈Cₛ,ⱼ c(r)"], formula_font),
        ("equation_2.png", ["V(r, s) =  Ineligible, P = 0", "             Needs Review, P = 1 ∧ (U ∨ M)", "             Missing Documents, P = 1 ∧ ¬(U ∨ M) ∧ D = 0", "             Eligible, P = 1 ∧ ¬(U ∨ M) ∧ D = 1"], small_font),
        ("equation_3.png", ["Cᵤ = {k ∈ K | scope(k) ⊆ perm(u)}          S(q, k) = e(q)·e(k) / (||e(q)|| ||e(k)||)"], formula_font),
    ]
    for filename, lines, fnt in equations:
        im = Image.new("RGBA", (2200, 70 + 68 * len(lines)), (255, 255, 255, 0))
        draw = ImageDraw.Draw(im)
        y = 35
        for line in lines:
            draw.text((1100, y), line, font=fnt, fill="#000000", anchor="ma")
            y += 64
        im.save(ROOT / filename, dpi=(300, 300))


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_cell_border(cell, color=GRID, size="6"):
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge in ("top", "left", "bottom", "right"):
        tag = "w:" + edge
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:color"), color)


def set_cell_margins(cell, top=90, start=110, bottom=90, end=110):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for m, v in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn("w:" + m))
        if node is None:
            node = OxmlElement("w:" + m)
            tc_mar.append(node)
        node.set(qn("w:w"), str(v))
        node.set(qn("w:type"), "dxa")


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    node = OxmlElement("w:tblHeader")
    node.set(qn("w:val"), "true")
    tr_pr.append(node)


def set_keep_with_next(paragraph):
    paragraph.paragraph_format.keep_with_next = True


def add_page_field(paragraph):
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(begin); run._r.append(instr); run._r.append(end)


def set_run_font(run, size=11.5, bold=False, italic=False, color=INK):
    run.font.name = FONT
    run._element.rPr.rFonts.set(qn("w:ascii"), FONT)
    run._element.rPr.rFonts.set(qn("w:hAnsi"), FONT)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = RGBColor.from_string(color)


def add_para(doc, text="", *, align=WD_ALIGN_PARAGRAPH.JUSTIFY, first=True, before=0, after=3, size=11.5, italic=False):
    p = doc.add_paragraph()
    p.alignment = align
    pf = p.paragraph_format
    pf.line_spacing = 1.0
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    if first:
        pf.first_line_indent = Cm(0.45)
    run = p.add_run(text)
    set_run_font(run, size=size, italic=italic)
    return p


def add_heading(doc, text, level=1):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    pf = p.paragraph_format
    pf.space_before = Pt(8 if level == 1 else 5)
    pf.space_after = Pt(3)
    pf.keep_with_next = True
    r = p.add_run(text)
    set_run_font(r, size=13 if level == 1 else 11.8, bold=True, color="000000")
    return p


def add_caption(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(5)
    r = p.add_run(text)
    set_run_font(r, size=9.2, italic=True, color="000000")
    return p


def add_table(doc, headers, rows, widths, font_size=8.8):
    tbl = doc.add_table(rows=1, cols=len(headers))
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    tbl.style = "Table Grid"
    header = tbl.rows[0]
    set_repeat_table_header(header)
    for i, text in enumerate(headers):
        cell = header.cells[i]
        cell.width = Inches(widths[i])
        set_cell_shading(cell, BLUE)
        set_cell_border(cell)
        set_cell_margins(cell)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(text)
        set_run_font(r, size=font_size, bold=True, color="FFFFFF")
    for idx, row in enumerate(rows):
        cells = tbl.add_row().cells
        for i, text in enumerate(row):
            cell = cells[i]
            cell.width = Inches(widths[i])
            set_cell_border(cell)
            set_cell_margins(cell)
            if idx % 2 == 1:
                set_cell_shading(cell, GRAY)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if i == 0 and len(text) < 18 else WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 0.95
            r = p.add_run(text)
            set_run_font(r, size=font_size, color=INK)
    for row in tbl.rows:
        row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
    return tbl


def add_bullet(doc, text):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(1)
    p.paragraph_format.line_spacing = 1.0
    r = p.add_run(text)
    set_run_font(r, size=11.0)
    return p


def add_algorithm(doc):
    add_caption(doc, "Algorithm 1. Role-scoped decision and assistant flow")
    steps = [
        ("Input", "authenticated user u, request q, database D"),
        ("1", "Resolve user role and village scope from the access token."),
        ("2", "If q identifies a resident, read only the permitted resident record."),
        ("3", "For an eligibility request, evaluate scheme criteria and document status locally."),
        ("4", "If the answer is personal, return a bilingual template with reasons; do not create an LLM request."),
        ("5", "Otherwise build the candidate set from records inside the user's permitted village scope."),
        ("6", "Rank retrieved knowledge chunks, expand linked records, and assemble non-personal context."),
        ("7", "Generate a grounded answer from that context; fall back to a local response if the model is unavailable."),
        ("8", "Return result and source labels; middleware records the auditable action."),
        ("Output", "role-compliant result, sources, and audit event"),
    ]
    table = doc.add_table(rows=0, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for n, text in steps:
        cells = table.add_row().cells
        cells[0].width = Inches(0.55)
        cells[1].width = Inches(5.95)
        for cell in cells:
            set_cell_border(cell, color="BFCDE0", size="4")
            set_cell_margins(cell, top=55, start=90, bottom=55, end=90)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        if n in ("Input", "Output"):
            set_cell_shading(cells[0], MID_BLUE); set_cell_shading(cells[1], LIGHT_BLUE)
        p = cells[0].paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_after = Pt(0)
        r = p.add_run(n); set_run_font(r, size=8.7, bold=True)
        p = cells[1].paragraphs[0]; p.paragraph_format.space_after = Pt(0)
        r = p.add_run(text); set_run_font(r, size=8.7)
    return table


def add_equation(doc, image_name, width):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    p.add_run().add_picture(str(ROOT / image_name), width=Inches(width))
    return p


def page_break(doc):
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def build():
    make_equations()
    make_architecture(ROOT / "architecture.png")
    make_activity(ROOT / "activity.png")

    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21.0); sec.page_height = Cm(29.7)
    sec.top_margin = Cm(1.55); sec.bottom_margin = Cm(1.45)
    sec.left_margin = Cm(1.95); sec.right_margin = Cm(1.95)
    sec.header_distance = Cm(0.55); sec.footer_distance = Cm(0.7)

    normal = doc.styles["Normal"]
    normal.font.name = FONT
    normal._element.rPr.rFonts.set(qn("w:ascii"), FONT)
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), FONT)
    normal.font.size = Pt(11.5)

    # Minimal, formal footer; no header is used.
    footer = sec.footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fp.paragraph_format.space_before = Pt(0); fp.paragraph_format.space_after = Pt(0)
    rr = fp.add_run("E-Panchayat Research Paper  |  ")
    set_run_font(rr, size=8.0, color="666666")
    add_page_field(fp)
    for run in fp.runs:
        if run.text == "":
            set_run_font(run, size=8.0, color="666666")

    # PAGE 1: title, abstract, and introduction.
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_before = Pt(0); title.paragraph_format.space_after = Pt(6)
    r = title.add_run("E-Panchayat Decision Support System for Gram Panchayat Administration")
    set_run_font(r, size=16, bold=True, color="000000")
    authors = doc.add_paragraph(); authors.alignment = WD_ALIGN_PARAGRAPH.CENTER
    authors.paragraph_format.space_after = Pt(1)
    r = authors.add_run("Honey Soni and Sujal Jagtap")
    set_run_font(r, size=10.5, color="000000")
    aff = doc.add_paragraph(); aff.alignment = WD_ALIGN_PARAGRAPH.CENTER
    aff.paragraph_format.space_after = Pt(10)
    r = aff.add_run("School of Computing, MIT ADT University, Pune, Maharashtra, India")
    set_run_font(r, size=9.8, italic=True, color="000000")
    abstract_label = doc.add_paragraph(); abstract_label.alignment = WD_ALIGN_PARAGRAPH.CENTER
    abstract_label.paragraph_format.space_after = Pt(2)
    r = abstract_label.add_run("Abstract")
    set_run_font(r, size=11.5, bold=True, color="000000")
    abstract = (
        "Gram Panchayats require reliable tools for resident services, welfare guidance, grievance handling, "
        "development-work monitoring and meeting records. E-Panchayat is a web-based decision-support system "
        "for the 23 villages of Haveli taluka, Pune district. It combines a bilingual citizen portal with an "
        "officer dashboard, village-scoped access control, a deterministic welfare eligibility engine, grievance "
        "routing, project and Gram Sabha management, GIS visualization, audit logging and a retrieval-augmented "
        "assistant. The main design principle is that personal resident information remains inside the Panchayat "
        "application: the assistant receives only non-personal village records, while resident-specific decisions "
        "are produced locally by a rule engine. The application is deployed on Render with a FastAPI service, a "
        "React frontend and PostgreSQL persistence. Functional pilot testing was conducted for Loni Kalbhor, Theur, "
        "Wagholi and Uruli Kanchan using representative village configurations and non-personal test records. The "
        "evaluation verified role-scoped access, eligibility assessment, complaint handling, document review, meeting "
        "records, GIS rendering and bilingual assistance. The system provides a practical foundation for transparent, "
        "traceable and privacy-conscious digital administration at the Gram Panchayat level."
    )
    add_para(doc, abstract, first=False, after=6, size=10.3)
    kw = doc.add_paragraph(); kw.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    kw.paragraph_format.space_after = Pt(6)
    r = kw.add_run("Keywords: "); set_run_font(r, size=10.2, bold=True, color="000000")
    r = kw.add_run("E-governance; Gram Panchayat; welfare eligibility; retrieval-augmented generation; role-based access control; rural administration.")
    set_run_font(r, size=10.2, italic=True, color="000000")

    add_heading(doc, "1  Introduction")
    add_para(doc, "The Panchayati Raj system makes the Gram Panchayat the closest administrative institution for many rural residents. At that level, staff must maintain resident records, communicate scheme information, register grievances, monitor development works and preserve Gram Sabha decisions. National services such as e-GramSwaraj, ServicePlus, Common Services Centres and the Digital India programme have digitized important parts of this ecosystem [1-4]. Yet an officer still needs a single operational view that links village data to day-to-day decisions.")
    add_para(doc, "E-Panchayat addresses this operational gap as a multi-village web application. It focuses on the questions that recur at the Panchayat counter: what scheme criteria apply, which documents are pending, where a grievance is routed, which project is relevant and what action was recorded in a Gram Sabha meeting. The system was designed for a block context rather than a single demo village, so access is constrained by both user role and village scope.")
    add_heading(doc, "1.1  Objectives", 2)
    add_bullet(doc, "Digitize citizen, scheme, grievance, project, facility and Gram Sabha information in a single role-aware system.")
    add_bullet(doc, "Evaluate welfare eligibility using transparent, data-driven rules rather than generated guesses.")
    add_bullet(doc, "Provide English and Marathi interfaces for citizens and Panchayat staff.")
    add_bullet(doc, "Add grounded assistance without sending individual resident records outside the application.")
    page_break(doc)

    # PAGE 2: literature review and comparison table.
    add_heading(doc, "2  Literature Review")
    add_para(doc, "Existing government platforms establish the context for this work. e-GramSwaraj supports planning, accounting and progress reporting for Panchayats [1]. ServicePlus provides a configurable service-delivery framework [2], while Common Services Centres and UMANG improve assisted and mobile access to public services [3, 4]. These systems are complementary to E-Panchayat; they do not replace the need for a local interface that connects scheme rules, resident documents and operational village records.")
    add_para(doc, "Research on rural e-governance emphasizes adoption, local capacity and the usability of services for both citizens and officials. Kumar and Best [5] and Madon [6] show that the impact of public-sector information systems depends on institutional context, not simply on the presence of technology. Recent work on retrieval-augmented generation shows how a model can answer with retrieved evidence rather than unsupported language [7-9]. However, village-scale records contain quasi-identifiers and sensitive data, so a system must decide what is safe to retrieve and what is safe to transmit [10, 11].")
    add_caption(doc, "Table 1. Comparison of related platforms and approaches")
    add_table(doc,
              ["Platform / approach", "Primary contribution", "Gap addressed by E-Panchayat"],
              [
                  ["e-GramSwaraj [1]", "Planning, budgeting and reporting", "Counter-level scheme and resident decision support"],
                  ["ServicePlus [2]", "Configurable online services", "Transparent eligibility rules and village-scoped records"],
                  ["CSC / UMANG [3, 4]", "Assisted and mobile service access", "Integrated operational dashboard and grievance workflow"],
                  ["Rural e-governance studies [5, 6]", "Adoption and institutional context", "Concrete implementation for Panchayat workflows"],
                  ["RAG research [7-9]", "Grounded language generation", "Privacy-bounded use of village data"],
              ], [1.55, 2.1, 2.8], font_size=8.6)
    add_para(doc, "The proposed system therefore combines the administrative coverage expected in local governance software with two technical requirements: explainable eligibility assessment and retrieval that respects the user's permissions before information is ranked or presented.")
    add_heading(doc, "2.1  Research Gap", 2)
    add_para(doc, "Many Gram Panchayat proposals list certificates, notices and complaints as isolated modules. E-Panchayat treats the connections between them as the central problem. A complaint is linked to a ward and a village; a project can be linked to the same issue; a scheme decision is linked to explicit criteria and document status. This makes a record useful for a decision, not merely available for storage.")
    page_break(doc)

    # PAGE 3: proposed system overview and architecture.
    add_heading(doc, "3  Proposed System")
    add_heading(doc, "3.1  System Overview", 2)
    add_para(doc, "E-Panchayat provides two connected experiences. Citizens can review their own documents, check scheme status, submit grievances, see notices and use a bilingual helpdesk. Officers and administrators manage residents, schemes, documents, grievances, projects, facilities and Gram Sabha actions. The core service maintains a hierarchy of Maharashtra, Pune district, Haveli block and 23 villages; each village carries its Local Government Directory and Census context [12, 13].")
    add_para(doc, "The application separates operational decisions from language generation. Eligibility and document checks run inside the backend. The assistant retrieves only records that the current user may access, and questions that require a named resident's information are answered locally. This design supports practical assistance while preserving the confidentiality of resident files.")
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_after = Pt(4)
    p.add_run().add_picture(str(ROOT / "architecture.png"), width=Inches(6.55))
    add_caption(doc, "Figure 1. E-Panchayat system architecture")
    add_para(doc, "The deployment separates the browser application, application service and database. The React and Vite frontend is served through Render, and the FastAPI backend is deployed as a web service on Render. PostgreSQL persistence is accessed through a secured database connection, while credentials and API keys are supplied through deployment environment variables rather than embedded in the browser bundle.", first=False, after=2, size=10.6)
    page_break(doc)

    # PAGE 4: models and algorithm.
    add_heading(doc, "3.2  Mathematical Models", 2)
    add_para(doc, "Let r denote a resident record and s a welfare scheme. Each scheme holds a set of mandatory predicates C_s such as age, income, social category, ration-card type, land holding or disability threshold. Some schemes also contain alternative criteria groups C_{s,j}; the engine evaluates these through the any_of operator. The first expression represents the basic predicate and the second represents an alternative eligibility path.")
    add_equation(doc, "equation_1.png", 5.7)
    add_para(doc, "Let U indicate that a required attribute is unknown, M that the scheme requires manual review, and D that all required documents are present and verified. The system returns a four-state verdict instead of compressing incomplete records into a simple yes or no decision. This distinction is important because a missing income certificate is an action to complete, not evidence that a resident is ineligible.")
    add_equation(doc, "equation_2.png", 5.25)
    add_para(doc, "For non-personal assistant questions, K is the set of indexed village knowledge chunks and e(.) is an embedding function. Candidate chunks are restricted to the permissions of user u before cosine similarity is calculated. This order prevents a highly similar record from bypassing village-level access control.")
    add_equation(doc, "equation_3.png", 5.75)
    add_caption(doc, "Table 2. Core modules and design responsibilities")
    add_table(doc,
              ["Module", "Responsibility", "Key control"],
              [
                  ["Access control", "Authenticates admin, officer and citizen roles", "Role and village-scoped backend queries"],
                  ["Eligibility engine", "Evaluates 29 central and state schemes", "Criteria rules and document verification"],
                  ["Assistant", "Answers village information questions", "Retrieval-only personal answers"],
                  ["Audit trail", "Records sensitive reads and state changes", "HTTP middleware without request bodies"],
              ], [1.45, 3.2, 1.8], font_size=8.4)
    add_algorithm(doc)
    page_break(doc)

    # PAGE 5: methodology and activity diagram.
    add_heading(doc, "4  Methodology")
    add_heading(doc, "4.1  Development Approach", 2)
    add_para(doc, "The system was developed through iterative requirements analysis, data modeling, component implementation, integration and test refinement. The requirements were derived from routine Panchayat activities: resident management, welfare support, grievance handling, development projects, Gram Sabha records, document review and public information access. The database model includes 18 relational tables covering the administrative hierarchy, users, citizens, families, schemes, documents, grievances, projects, meetings, facilities, knowledge chunks and security events.")
    add_para(doc, "The frontend was built as a responsive React application with English and Marathi labels. The backend uses FastAPI for REST endpoints, SQLAlchemy and Alembic for persistence and migrations, and JWT-based authentication. A rule-based bilingual classifier assigns grievance categories, priorities and departments. The map uses Leaflet and OpenStreetMap context [18], and the bilingual design follows a record-level approach so key service information can be maintained in both languages. Bhashini is a relevant national language technology initiative for future translation support [19].")
    add_heading(doc, "4.2  Activity Flow", 2)
    add_para(doc, "Figure 2 describes the activity flow used by the application. The first decision occurs when the authenticated user's role and village scope are resolved. The second decision distinguishes a personal request from a village-level question. Personal requests remain in local processing; only permitted non-personal records become context for language-model generation.")
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_after = Pt(4)
    p.add_run().add_picture(str(ROOT / "activity.png"), width=Inches(6.25))
    add_caption(doc, "Figure 2. Activity diagram for a service request or assistant query")
    page_break(doc)

    # PAGE 6: pilot and deployment.
    add_heading(doc, "4.3  Pilot Testing and Deployment", 2)
    add_para(doc, "Functional pilot testing was carried out using representative village configurations for Loni Kalbhor, Theur, Wagholi and Uruli Kanchan in Haveli taluka, Pune district. These locations were selected to verify that the application behaves as a multi-village system rather than as a single-village prototype. The pilot used non-personal test records and focused on completing defined administrative workflows from login to result.")
    add_para(doc, "The test scenarios covered role-scoped access, resident and document management, scheme eligibility assessment, grievance registration and classification, project tracking, Gram Sabha action handling, GIS display and bilingual assistance. Cross-village checks were included to confirm that an officer's view is limited to the assigned Panchayat while an administrator can view the block-level roll-up. The system was also exercised through its API test suite, which contains 260 automated tests over seeded data and security-sensitive paths.")
    add_caption(doc, "Table 3. Functional pilot coverage and verified outcomes")
    add_table(doc,
              ["Test area", "Pilot activity", "Verified outcome"],
              [
                  ["Access and scope", "Login as citizen, officer and admin; change village context", "Permitted records are displayed; cross-village records are blocked"],
                  ["Schemes", "Run criteria and document checks for 29 schemes", "Verdict and reasons are returned as Eligible, Missing Documents, Needs Review or Ineligible"],
                  ["Grievances", "Create and route bilingual complaints", "Category, priority and destination department are assigned"],
                  ["Records and meetings", "Review documents, projects and Gram Sabha actions", "State changes and individual-record reads produce auditable events"],
                  ["Assistant and GIS", "Ask village and personal queries; view village facilities", "Personal queries stay local; village context is retrieved with source labels"],
              ], [1.35, 2.75, 2.35], font_size=8.3)
    add_heading(doc, "4.4  Deployment", 2)
    add_para(doc, "The completed application is deployed on Render. The deployment configuration provisions the frontend and API as separate services, exposes a health endpoint for the backend and uses environment variables for the database URL, authentication secret, model configuration and allowed browser origin. This separation keeps confidential configuration out of the client bundle and supports independent updates to the interface and backend service.")
    page_break(doc)

    # PAGE 7: results.
    add_heading(doc, "5  Results and Discussion")
    add_heading(doc, "5.1  Functional Results", 2)
    add_para(doc, "The pilot confirmed that the primary workflows operate consistently across the four selected village contexts. Citizens are limited to their own files, officers are limited to their assigned village and administrators can access the broader hierarchy. For scheme support, the result includes the decision state and explanation, enabling an officer to distinguish an ineligible resident from an otherwise eligible person who must submit or verify a document.")
    add_para(doc, "The implementation was tested against the same seeded dataset used by the demonstration environment. There are 10 resident records, 29 schemes, five grievances, four development projects, one Gram Sabha meeting with action items, five facilities and 23 villages in the administrative hierarchy. The data is intentionally small enough for repeatable testing, but the rules, permissions and links are the same mechanisms used by the deployed application.")
    add_caption(doc, "Table 4. Measured system results")
    add_table(doc,
              ["Measure", "Result", "Interpretation"],
              [
                  ["Automated tests", "260 passed", "API, access control, audit, password reset, rate limit, registration, scheme and semantic retrieval coverage"],
                  ["REST endpoints", "61", "Services cover authentication, citizens, documents, schemes, grievances, projects, meetings, villages, analytics, audit and assistant queries"],
                  ["Eligibility assessments", "290", "10 residents evaluated against 29 schemes"],
                  ["Eligibility verdicts", "179 Ineligible; 67 Missing Documents; 37 Needs Review; 7 Eligible", "A decision is accompanied by rule- and document-level reasons"],
                  ["Knowledge index", "67 chunks; 0 resident-derived chunks", "Village knowledge is available to retrieval while resident records are not indexed"],
                  ["Pilot coverage", "4 Haveli taluka villages", "Loni Kalbhor, Theur, Wagholi and Uruli Kanchan functional configurations"],
              ], [1.55, 1.75, 3.15], font_size=8.1)
    add_heading(doc, "5.2  Eligibility and Transparency", 2)
    add_para(doc, "The eligibility engine resolves the main ambiguity found in manual scheme guidance: its answer is not merely a label. It returns the failed condition, the unknown attribute, the manual-review requirement or the missing document. For example, Sanjay Gandhi Niradhar provides alternative income and BPL paths [14], Mahatma Jyotirao Phule Jan Arogya Yojana can depend on a Yellow, Orange, AAY or Annapurna ration card [15], PMAY-G uses SECC listing conditions [16], and the Swachh Bharat Mission Gramin incentive includes alternative household conditions [17]. This level of explanation makes a decision reviewable at the Panchayat counter.")
    add_para(doc, "Four schemes in the current configuration use alternative any_of branches, and seven are marked for manual review because a resident record alone cannot decide their conditions. The four-state output keeps these cases visible to the officer instead of forcing a seemingly precise recommendation from incomplete evidence.")
    page_break(doc)

    # PAGE 8: results discussion.
    add_heading(doc, "5.3  Privacy and Retrieval Behaviour", 2)
    add_para(doc, "The assistant follows a retrieve-then-generate workflow for non-personal questions. It retrieves village facts, scheme information, projects, facilities, grievances and Gram Sabha records, then returns an answer with source labels. The 67-chunk index contains 29 scheme chunks, 23 village chunks, five grievance chunks, five facility chunks, four project chunks and one Gram Sabha chunk. No resident-derived chunk is present. This directly supports the design principle that the model may see village context but not an identified resident's record.")
    add_para(doc, "When a question concerns an individual's own record, the system uses local retrieval and a template-based explanation. The rule engine, not the language model, determines eligibility. This is important because the relevant data can include income, social category, disability information and document status. Keeping this path local avoids treating a language model as an eligibility authority and avoids transmitting personal questions for wording assistance.")
    add_heading(doc, "5.4  Operational Discussion", 2)
    add_para(doc, "The pilot also demonstrated the value of treating administration as connected workflows. A grievance can be classified into Water, Sanitation, Roads, Electricity, Health or Other, assigned a priority and routed to the appropriate department. A project record can hold budget and progress context. A Gram Sabha action item is maintained separately from the meeting summary. These links reduce the work needed to move from a citizen request to an accountable response.")
    add_para(doc, "Audit logging is deliberately selective. It records authenticated state-changing actions and reads of individually named records, while avoiding request bodies and passwords. Password reset is issued through a counter-based process, which is suitable for a setting where a universal SMS or email channel cannot be assumed. Together, these features make the system more practical for the office environment than a portal that only collects forms.")
    add_heading(doc, "5.5  Pilot Observations", 2)
    add_para(doc, "Across the Loni Kalbhor, Theur, Wagholi and Uruli Kanchan configurations, the same scenario scripts were completed without changing the access-control or eligibility logic. The village selection changed the records, facilities, projects and map context presented to the user; it did not change the rules that govern who may view a record. This is a useful result for block-level rollout because it validates the administrative hierarchy and per-village filtering as reusable system behaviour.")
    add_para(doc, "The pilot also confirmed a practical separation of responsibilities. Citizens can initiate a grievance or examine their own service information, while Panchayat staff retain the ability to review documents, update workflows and approve sensitive changes. The bilingual interface keeps core labels and explanation states available in English and Marathi. The tested flows are intentionally scenario based: they verify completion, security boundaries and traceability in the deployed application.")
    add_heading(doc, "5.6  Limitations and Future Scope", 2)
    add_para(doc, "The pilot demonstrates functional readiness across four village configurations, but larger field use should include administrative review of every scheme rule, integration with authoritative document systems and a broader user study with officials and residents. Planned extensions include OCR for uploaded records, secure DigiLocker integration, notification channels, a production vector index for larger datasets and support for additional Indian languages. These additions can extend operational reach without changing the core privacy boundary.")
    page_break(doc)

    # PAGE 9: conclusion and acknowledgements.
    add_heading(doc, "6  Conclusion")
    add_para(doc, "E-Panchayat brings together the services that Gram Panchayat staff and citizens use most often: resident records, welfare guidance, documents, grievances, projects, meetings, facilities, maps, analytics and assistance. Its key contribution is to make each decision traceable. Welfare eligibility is evaluated through criteria and documents, grievances are classified through visible rules, and sensitive actions are recorded through an audit trail.")
    add_para(doc, "The four-village functional pilot in Haveli taluka verified the core administrative workflows in Loni Kalbhor, Theur, Wagholi and Uruli Kanchan. The deployed Render application provides a usable platform for further rollout. By combining role-scoped access, a deterministic eligibility engine and privacy-bounded retrieval, the system offers a professional foundation for transparent and accountable Gram Panchayat digitization.")
    add_heading(doc, "6.1  Key Contributions", 2)
    add_bullet(doc, "A multi-village Gram Panchayat platform for 23 Haveli taluka villages with role-based and village-scoped access.")
    add_bullet(doc, "A 29-scheme deterministic eligibility engine with four decision states and explicit reasons.")
    add_bullet(doc, "Privacy-bounded assistance in which resident-specific queries remain within the application.")
    add_bullet(doc, "Functional pilot validation in four village contexts and 260 automated tests across core API workflows.")
    add_heading(doc, "Acknowledgements", 2)
    add_para(doc, "The authors thank Prof. Jyoti Gavhane for guidance and the School of Computing, MIT ADT University, for academic support. The administrative hierarchy and village data draw on public Government of India sources; all resident records used for functional testing are non-personal test data.", first=False, after=5)
    page_break(doc)
    add_heading(doc, "References")
    refs = [
        "Ministry of Panchayati Raj, Government of India: e-GramSwaraj Portal. https://egramswaraj.gov.in (accessed 10 September 2026).",
        "National Informatics Centre: ServicePlus Metadata-based e-Service Delivery Framework. https://serviceonline.gov.in (accessed 10 September 2026).",
        "Ministry of Electronics and Information Technology, Government of India: Common Services Centres Scheme. https://www.csc.gov.in (accessed 10 September 2026).",
        "Government of India: Digital India Programme. https://www.digitalindia.gov.in (accessed 10 September 2026).",
        "Kumar, R., Best, M.L.: Impact and sustainability of e-government services in developing countries: lessons learned from Tamil Nadu, India. The Information Society 22(1), 1-12 (2006).",
        "Madon, S.: Evaluating the developmental impact of e-governance initiatives: an exploratory framework. Electronic Journal of Information Systems in Developing Countries 20(1), 1-13 (2004).",
        "Lewis, P. et al.: Retrieval-augmented generation for knowledge-intensive NLP tasks. In: Advances in Neural Information Processing Systems 33, 9459-9474 (2020).",
        "Karpukhin, V. et al.: Dense passage retrieval for open-domain question answering. In: EMNLP, 6769-6781 (2020).",
        "Edge, D. et al.: From local to global: a Graph RAG approach to query-focused summarization. arXiv:2404.16130 (2024).",
        "Sweeney, L.: k-anonymity: a model for protecting privacy. International Journal of Uncertainty, Fuzziness and Knowledge-Based Systems 10(5), 557-570 (2002).",
        "Narayanan, A., Shmatikov, V.: Robust de-anonymization of large sparse datasets. In: IEEE Symposium on Security and Privacy, 111-125 (2008).",
        "Ministry of Panchayati Raj, Government of India: Local Government Directory. https://lgdirectory.gov.in (accessed 10 September 2026).",
        "Office of the Registrar General and Census Commissioner, India: Census of India 2011. https://censusindia.gov.in (accessed 10 September 2026).",
        "Department of Social Justice and Special Assistance, Government of Maharashtra: Sanjay Gandhi Niradhar Anudan Yojana. https://sjsa.maharashtra.gov.in (accessed 10 September 2026).",
        "Government of Maharashtra: Mahatma Jyotirao Phule Jan Arogya Yojana. https://www.jeevandayee.gov.in (accessed 10 September 2026).",
        "Ministry of Rural Development, Government of India: Pradhan Mantri Awaas Yojana Gramin. https://pmayg.nic.in (accessed 10 September 2026).",
        "Department of Drinking Water and Sanitation, Government of India: Swachh Bharat Mission Gramin. https://swachhbharatmission.gov.in (accessed 10 September 2026).",
        "OpenStreetMap contributors: OpenStreetMap. https://www.openstreetmap.org (accessed 10 September 2026).",
        "Ministry of Electronics and Information Technology, Government of India: Bhashini National Language Translation Mission. https://bhashini.gov.in (accessed 10 September 2026).",
    ]
    for i, ref in enumerate(refs, 1):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.45)
        p.paragraph_format.first_line_indent = Cm(-0.45)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 0.95
        r = p.add_run(f"{i}. {ref}")
        set_run_font(r, size=8.8, color="000000")

    # Remove the automatically created first empty paragraph only if it remains empty.
    doc.core_properties.title = "E-Panchayat Decision Support System for Gram Panchayat Administration"
    doc.core_properties.author = "Honey Soni and Sujal Jagtap"
    doc.core_properties.subject = "Gram Panchayat digital governance research paper"
    doc.core_properties.keywords = "E-governance, Gram Panchayat, welfare eligibility, privacy"
    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build()
