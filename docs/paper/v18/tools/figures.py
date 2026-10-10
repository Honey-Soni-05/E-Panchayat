"""Redraw Figures 1-3 of the v18 manuscript.

Run with matplotlib installed:  python figures.py <output_dir>
Figures 4 and 5 are application screenshots reused from v17.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7})

BLUE = ("#e8eef8", "#4a6fa5")
GREY = ("#f2f2f2", "#7a7a7a")
RED = ("#fbe9e9", "#b04a4a")
AMBER = ("#fdf3e1", "#b8862b")
GREEN = ("#e8f4ea", "#4a8a55")


def box(ax, x, y, w, h, text, col=BLUE, fs=7, bold=False, ls="-", ha="center"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.004,rounding_size=0.012",
                                fc=col[0], ec=col[1], lw=0.9, ls=ls))
    tx = x + w / 2 if ha == "center" else x + 0.012
    ax.text(tx, y + h / 2, text, ha=ha, va="center", fontsize=fs,
            fontweight="bold" if bold else "normal", wrap=True, linespacing=1.25)


def arrow(ax, x1, y1, x2, y2, text=None, ls="-", col="#555", tx=None, ty=None, fs=6):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=col, lw=0.8, ls=ls, shrinkA=0, shrinkB=0))
    if text:
        ax.text(tx if tx is not None else (x1 + x2) / 2 + 0.01,
                ty if ty is not None else (y1 + y2) / 2, text,
                fontsize=fs, color=col, style="italic", va="center")


def diamond(ax, cx, cy, w, h, text, col=AMBER, fs=6.5):
    ax.add_patch(Polygon([(cx - w / 2, cy), (cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2)],
                         closed=True, fc=col[0], ec=col[1], lw=0.9))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs, linespacing=1.2)


def canvas(w, h):
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    return fig, ax


# ── Figure 1: layered architecture and data flows ──────────────────────────
def fig1():
    fig, ax = canvas(3.5, 4.3)
    box(ax, 0.03, 0.935, 0.94, 0.05,
        "Prototype deployment: client and API on Render; PostgreSQL managed by Supabase", GREY, 6.3, True)
    box(ax, 0.10, 0.835, 0.80, 0.075,
        "Client layer: React + TypeScript (Vite, Tailwind)\nbilingual English / Marathi interface", BLUE, 6.6, True)
    arrow(ax, 0.5, 0.835, 0.5, 0.795, "HTTPS, signed JWT", tx=0.515)
    box(ax, 0.10, 0.715, 0.80, 0.08,
        "API layer: FastAPI REST\nrole and village-scope checks declared\nas route dependencies", BLUE, 6.2, True)
    ax.add_patch(FancyBboxPatch((0.03, 0.47), 0.94, 0.225, boxstyle="round,pad=0.004",
                                fc="white", ec="#999", lw=0.7, ls="--"))
    ax.text(0.045, 0.683, "Service layer", fontsize=6, style="italic", color="#666")
    labels = ["Eligibility\nengine\n(rules; no\nmodel call)", "Retrieval and\nlink\nfollowing", "Complaint\nclassifier\n(keyword\nrules)",
              "Work\nlifecycle\nand ledger", "Audit\nlog"]
    for i, t in enumerate(labels):
        box(ax, 0.045 + i * 0.187, 0.485, 0.172, 0.18, t, BLUE, 6.0)
    box(ax, 0.03, 0.30, 0.43, 0.14,
        "PostgreSQL\nresident register, documents,\ncomplaints, works, ledger,\nretrieval index (vectors)", BLUE, 6.0, True)
    box(ax, 0.56, 0.30, 0.41, 0.14,
        "External model provider\n(Google Gemini API)\nembedding + generation", RED, 6.0, True)
    ax.plot([0.51, 0.51], [0.29, 0.47], color=RED[1], lw=1.2, ls=(0, (4, 2)))
    ax.text(0.488, 0.285, "privacy boundary", fontsize=5.4, color=RED[1], style="italic", va="top", ha="center")
    box(ax, 0.03, 0.115, 0.94, 0.14,
        "Crosses to the provider:  (a) text of indexed non-resident records at index time,\n"
        "      including complaint titles and descriptions;  (b) the question text, unless the\n"
        "      name screen fires;  (c) the generation prompt = question + non-personal records.\n"
        "Kept inside by design:  resident rows, eligibility verdicts and reasons, document\n"
        "      files, and any retrieved set containing a fact flagged personal.",
        GREEN, 5.3, ha="left")
    box(ax, 0.03, 0.015, 0.94, 0.08,
        "Not prevented:  a question that identifies a resident by description rather than name,\n"
        "      or personal details typed into complaint text, can still reach the provider.",
        AMBER, 5.3, ha="left")
    fig.savefig(OUT / "fig1_architecture.png", dpi=300)
    plt.close(fig)


# ── Figure 2: development-work lifecycle ───────────────────────────────────
def fig2():
    fig, ax = canvas(3.5, 4.9)
    stages = [
        ("Resident request(s)", GREEN, "classified as development request;\nquantity read where stated"),
        ("Proposed", GREY, "related complaints grouped; priority\nraised by count of distinct residents"),
        ("Verified", AMBER, "officer decision after site check"),
        ("Approved", AMBER, "Panchayat decision, recorded by officer;\nmay cite a Gram Sabha resolution"),
        ("Budget Requested", BLUE, "entering estimate and requested amount\nis the transition"),
        ("Budget Approved", BLUE, "sanctioned amount and funding source\nentered by officer"),
        ("Funds Received", BLUE, "officer records receipt; not checked\nagainst any payment system"),
        ("In Progress", GREY, "units completed and spending entered\nas work proceeds"),
        ("Completed", GREY, "physical and financial progress compared;\na gap is flagged for review"),
        ("Asset registered", RED, "separate asset record placed on map;\nlater complaints can reference it"),
    ]
    top, step, h, x, w = 0.955, 0.078, 0.052, 0.06, 0.38
    for i, (name, col, note) in enumerate(stages):
        y = top - i * step
        box(ax, x, y - h / 2, w, h, name, col, 6.4, bold=(i in (0, 9)))
        ax.text(x + w + 0.03, y, note, fontsize=5.3, va="center", style="italic", color="#444")
        if i < len(stages) - 1:
            arrow(ax, x + w / 2, y - h / 2, x + w / 2, y - step + h / 2,
                  ls="--" if i == 8 else "-")
    red = "#b04a4a"
    ax.plot([0.03, 0.03], [top - 7 * step, top - 1 * step], color=red, lw=0.8, ls=":")
    for k in range(1, 8):
        ax.plot([0.03, x], [top - k * step] * 2, color=red, lw=0.6, ls=":")
    ax.plot([0.03, 0.03], [top - 7 * step, 0.075], color=red, lw=0.8, ls=":")
    ax.plot([0.03, 0.70], [0.075, 0.075], color=red, lw=0.8, ls=":")
    box(ax, 0.47, 0.11, 0.22, 0.045, "Rejected", RED, 6.2, True)
    box(ax, 0.74, 0.11, 0.22, 0.045, "On Hold", AMBER, 6.2, True)
    arrow(ax, 0.58, 0.075, 0.58, 0.11, col=red, ls=":")
    arrow(ax, 0.70, 0.075, 0.85, 0.11, col=red, ls=":")
    ax.text(0.36, 0.030, "Side states are officer decisions; one that closes a\ndoor needs a recorded reason. No stage can be skipped.",
            fontsize=5.0, style="italic", color="#444", va="center")
    lx = 0.07
    for i, (lab, col) in enumerate([("resident", GREEN), ("officer decision", AMBER),
                                     ("money entry", BLUE), ("system state", GREY), ("asset", RED)]):
        yy = 0.205 - i * 0.024
        ax.add_patch(FancyBboxPatch((lx, yy - 0.007), 0.025, 0.014, boxstyle="square,pad=0",
                                    fc=col[0], ec=col[1], lw=0.6))
        ax.text(lx + 0.035, yy, lab, fontsize=5.3, va="center")
    fig.savefig(OUT / "fig2_lifecycle.png", dpi=300)
    plt.close(fig)


# ── Figure 3: assistant query flow and privacy gates ───────────────────────
def fig3():
    fig, ax = canvas(3.5, 5.0)
    cx, bw = 0.40, 0.56
    ax.add_patch(plt.Circle((cx, 0.975), 0.012, color="#3a4a5a"))
    ax.text(cx + 0.03, 0.975, "officer or resident asks a question", fontsize=6, va="center")
    arrow(ax, cx, 0.963, cx, 0.94)
    box(ax, cx - bw / 2, 0.905, bw, 0.035, "Resolve role and village scope", BLUE, 6.4)
    arrow(ax, cx, 0.905, cx, 0.885)
    diamond(ax, cx, 0.85, 0.40, 0.07, "Gate 1: question contains\na recorded resident name?")
    box(ax, 0.72, 0.828, 0.27, 0.045, "Keyword path only;\nno external call", RED, 5.8)
    arrow(ax, cx + 0.20, 0.85, 0.72, 0.85, "yes", tx=0.62, ty=0.86)
    arrow(ax, cx, 0.815, cx, 0.79, "no", tx=cx + 0.01)
    box(ax, cx - bw / 2, 0.75, bw, 0.04, "Select candidate records\n(scoped before ranking)", BLUE, 6.0)
    arrow(ax, cx, 0.75, cx, 0.73)
    box(ax, cx - bw / 2, 0.685, bw, 0.045, "Embed question text at provider\n(question leaves the deployment)", RED, 6.0)
    box(ax, 0.72, 0.69, 0.27, 0.035, "on failure: keyword\npath", GREY, 5.6)
    arrow(ax, cx + bw / 2, 0.707, 0.72, 0.707)
    arrow(ax, cx, 0.685, cx, 0.665)
    box(ax, cx - bw / 2, 0.62, bw, 0.045, "Rank locally (cosine, τ = 0.55); follow up\nto 3 links per hit within scope", BLUE, 6.0)
    arrow(ax, cx, 0.62, cx, 0.60)
    diamond(ax, cx, 0.565, 0.40, 0.07, "Gate 2: any retrieved fact\nflagged personal?")
    box(ax, 0.72, 0.543, 0.27, 0.045, "Template answer;\nno generation call", RED, 5.8)
    arrow(ax, cx + 0.20, 0.565, 0.72, 0.565, "yes", tx=0.62, ty=0.575)
    arrow(ax, cx, 0.53, cx, 0.505, "no", tx=cx + 0.01)
    diamond(ax, cx, 0.47, 0.40, 0.07, "Model key\nconfigured?")
    box(ax, 0.72, 0.448, 0.27, 0.045, "Template answer from\nretrieved records", GREY, 5.8)
    arrow(ax, cx + 0.20, 0.47, 0.72, 0.47, "no", tx=0.62, ty=0.48)
    arrow(ax, cx, 0.435, cx, 0.41, "yes", tx=cx + 0.01)
    box(ax, cx - bw / 2, 0.365, bw, 0.045, "Build prompt: question + non-personal\nrecords + system instructions", BLUE, 6.0)
    arrow(ax, cx, 0.365, cx, 0.345)
    box(ax, cx - bw / 2, 0.31, bw, 0.035, "Call generation model at provider", RED, 6.0)
    arrow(ax, cx, 0.31, cx, 0.29)
    diamond(ax, cx, 0.255, 0.40, 0.07, "Call succeeds?")
    box(ax, 0.72, 0.226, 0.27, 0.058, "Retry twice with\nback-off, then\ntemplate answer", GREY, 5.8)
    arrow(ax, cx + 0.20, 0.255, 0.72, 0.255, "no", tx=0.62, ty=0.265)
    arrow(ax, cx, 0.22, cx, 0.195, "yes", tx=cx + 0.01)
    box(ax, cx - bw / 2, 0.145, bw, 0.05, "Return answer, cited records, and a\nflag naming the path taken", BLUE, 6.0)
    box(ax, 0.02, 0.02, 0.96, 0.09,
        "Gate 1 matches names only (Latin or Devanagari, full name or first+last name).\n"
        "It does not detect descriptions, aliases, misspellings, or a lone given name;\n"
        "such questions follow the normal path and are embedded externally.",
        AMBER, 5.6, ha="left")
    fig.savefig(OUT / "fig3_query_flow.png", dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    fig1(); fig2(); fig3()
    print("written to", OUT)
