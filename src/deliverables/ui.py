"""Rendering helpers for the Streamlit demo (app.py). Needs the [demo] extra.

Every widget key is built from key_prefix, which starts with "upload_" or "sample_": both tabs
render on every rerun, so keys must not collide.

Contract-derived text (descriptions, quotes, conditions, file names) is untrusted: uploaded PDFs can
contain anything. Every piece of it that goes into HTML passes through esc() first. The *_html
builders below are pure so tests can check that.
"""

import html
import json
import re

import streamlit as st

from deliverables.table import (
    CHECK_QUOTE,
    TO_BE_AGREED,
    eval_line,
    grounded_flags,
    parties_heading,
    show_value_column,
    summary_parts,
    table_rows,
    type_counts,
)

# The one block of injected CSS. Everything else comes from .streamlit/config.toml.
# Table cells, rows and the header are found by the st-key-<key> class Streamlit puts on keyed containers.
CSS = """
<style>
/* Less empty space above the title (Streamlit's default is about 6rem). */
[data-testid="stMainBlockContainer"] { padding-top: 2.5rem; max-width: 1440px; }

/* Title size from the mockup (~40px). */
h1 { font-size: 2.5rem !important; }

/* Keep the subtitle to a readable line length. */
.deliv-subtitle { max-width: 62ch; }

/* Captions: Streamlit draws them at 60% opacity (4.0:1 on Paper, below AA); 75% gives 6.3:1. */
[data-testid="stCaptionContainer"] { opacity: 0.75; }

/* Secondary text in full-opacity Muted instead of faded Ink. */
.deliv-muted { color: #4A5A56; margin: 0; }

/* Summary and eval lines: line up the digits. */
.deliv-summary, .deliv-cell, .deliv-fact { font-variant-numeric: tabular-nums; }
.deliv-summary { margin: 0; }

/* "Showing N" next to the deliverables heading. */
.deliv-showing { font-family: Barlow, sans-serif; font-size: 1rem; font-weight: 500; color: #4A5A56; margin-left: 0.75rem; }

/* Table: no gap between rows, so header and rows read as one block with a single outer border. */
[class*="_deliv_table"] { gap: 0 !important; border: 1px solid #CFD8D2; border-radius: 0.25rem; overflow: hidden; }

/* Header row on Panel; body rows on White with a Rule divider. */
[class*="_deliv_head"] { background: #E9EEEA; padding: 0.5rem 0.75rem; }
[class*="_deliv_row_"] { background: #FFFFFF; padding: 0.55rem 0.75rem; border-top: 1px solid #CFD8D2; }

/* Tighter gaps between cells than Streamlit's default column gap. */
[class*="_deliv_table"] [data-testid="stHorizontalBlock"] { gap: 0.75rem; }

/* Cell text: no paragraph margins, and no -1rem under each Markdown block (it cancels a margin we removed,
   so without this the text spills over the row divider). Long unbroken strings wrap instead of widening the page. */
[class*="_deliv_table"] [data-testid="stMarkdownContainer"] { margin-bottom: 0; }
[class*="_deliv_table"] [data-testid="stMarkdownContainer"] p { margin: 0; }
.deliv-cell { overflow-wrap: anywhere; line-height: 1.4; }
.deliv-th { font-weight: 600; }

/* Phones: Streamlit stacks the columns, so each row becomes a short card; a stacked header row would just be a list of words. */
@media (max-width: 640px) { [class*="_deliv_head"] { display: none; } }

/* Clause buttons: left-aligned link-style text in Field, no button padding. */
[class*="_deliv_row_"] [data-testid="stBaseButton-tertiary"] {
  padding: 0; min-height: 0; justify-content: flex-start; text-align: left; color: #1F6B47; font-weight: 600; font-size: 1rem;
  font-variant-numeric: tabular-nums; }
[class*="_deliv_row_"] [data-testid="stBaseButton-tertiary"] p { font-size: 1rem; }
[class*="_deliv_row_"] [data-testid="stBaseButton-tertiary"]:hover { text-decoration: underline; }

/* Primary button hover/active: Streamlit darkens primaryColor for hover, which turns Field (#1F6B47) into
   near-black #0E2F20. Use a slightly darker Field instead. */
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primary"]:active {
  background-color: #185A3B; border-color: #185A3B; color: #FFFFFF; }

/* Status. Signal (#8F5512) is 5.9:1 on White, so it passes AA at body size. */
.deliv-tba { color: #8F5512; font-weight: 600; }
.deliv-check { color: #1C2B2A; font-weight: 600; text-decoration: underline dotted; text-underline-offset: 3px; }

/* Dialog on White, like the table body. */
[role="dialog"] { background-color: #FFFFFF; }

/* Dialog: What's owed as a heading. A styled paragraph, because Streamlit shrinks raw h3 tags in dialogs. No tag-like text in this block: st.html drops a style block that contains any. */
.deliv-dialog-title { font-family: "Barlow Semi Condensed", sans-serif; font-size: 1.35rem; font-weight: 600;
  line-height: 1.3; margin: 0.25rem 0 0.5rem; }

/* Dialog: fact labels, quote block and the ungrounded warning. */
.deliv-label { font-weight: 600; margin: 1.25rem 0 0.35rem; }
.deliv-dialog-body { padding-top: 0.5rem; }
.deliv-fact-label { color: #4A5A56; font-size: 0.875rem; margin: 0; }
.deliv-fact { margin: 0; }
/* Quote: quiet Paper block, full-strength Ink (Streamlit's blockquote is faded with a left rule). */
[data-testid="stMarkdownContainer"] blockquote.deliv-quote { background: #F6F7F5; border: none; border-radius: 0.25rem;
  padding: 0.75rem 1rem; margin: 0; color: #1C2B2A; opacity: 1; }
.deliv-warn { color: #8F5512; font-weight: 600; margin: 0.5rem 0 0; }
</style>
"""

NO_SELECTION = "Select a row to see the contract text behind it."
NOT_FOUND = "This text was not found word for word in the PDF. Check it against the contract."
NOT_STATED = "Not stated"
STATUS_BLANK = "Set in the contract"
ALL_TYPES = "__all__"

# Width ratios: What's owed gets most of the room.
BASE_COLUMNS = [("Clause", 1.25), ("Type", 1.25), ("What's owed", 4.5), ("Qty", 1.3), ("When", 1.6)]
VALUE_COLUMN = ("Value", 0.9)
STATUS_COLUMN = ("Status", 1.3)


def inject_css() -> None:
    st.html(CSS)


def esc(text: str) -> str:
    """Escape for an HTML block in st.markdown: no tags, no LaTeX from '$', newlines kept."""
    return html.escape(text).replace("$", "&#36;").replace("\n", "<br>")


def md_label(text: str) -> str:
    """Escape Markdown in text Streamlit renders as Markdown (button labels, st.header): no links, images or LaTeX."""
    return re.sub(r"([\\`*_\[\]<>#~$|])", r"\\\1", text)


def anchor_id(key_prefix: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", key_prefix.lower()) + "-deliverables"


# ---------- pure HTML builders (every contract-derived string goes through esc) ----------

def status_html(status: str) -> str:
    """'To be agreed' in Signal, 'Check quote' in Ink with a dotted underline, both semibold."""
    if not status:
        return ""
    parts = []
    if status.startswith(TO_BE_AGREED):
        parts.append(f'<span class="deliv-tba">{TO_BE_AGREED}</span>')
    if status.lower().endswith(CHECK_QUOTE.lower()):
        label = CHECK_QUOTE.lower() if parts else CHECK_QUOTE
        parts.append(f'<span class="deliv-check">{label}</span>')
    return " · ".join(parts)


def cell_html(text: str) -> str:
    return f'<div class="deliv-cell">{esc(text)}</div>'


def summary_html(contract: dict, grounding: dict, anchor: str) -> str:
    """Summary line; the grounding count links down to the table."""
    term, payments, quotes = summary_parts(contract, grounding)
    return (f'<p class="deliv-summary">{esc(term)} · {esc(payments)} · '
            f'<a href="#{anchor}" target="_self">{esc(quotes)}</a></p>')


def html_list(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{esc(item)}</li>" for item in items) + "</ul>"


def dialog_facts(row: dict, with_value: bool) -> list[tuple[str, str]]:
    """(label, HTML) facts for the dialog: Qty, When, Status, plus Value when the row has one."""
    facts = [("Qty", esc(row["qty"] or NOT_STATED)), ("When", esc(row["when"] or NOT_STATED)),
             ("Status", status_html(row["status"]) or STATUS_BLANK)]
    if with_value and row["value"]:
        facts.insert(2, ("Value", esc(row["value"])))
    return facts


def fact_html(label: str, value_html: str) -> str:
    return f'<p class="deliv-fact-label">{label}</p><p class="deliv-fact">{value_html}</p>'


def dialog_head_html(row: dict) -> str:
    return (f'<p class="deliv-muted">{esc(row["clause"])} · {esc(row["type"])}</p>'
            f'<p class="deliv-dialog-title">{esc(row["whats_owed"])}</p>')


def dialog_body_html(row: dict) -> str:
    """Contract text, the not-found warning, conditions and sponsor obligations."""
    d = row["deliverable"]
    parts = ['<div class="deliv-dialog-body"><p class="deliv-label">Contract text</p>',
             f'<blockquote class="deliv-quote">{esc(d.get("source_quote") or "")}</blockquote>']
    if not row["grounded"]:
        parts.append(f'<p class="deliv-warn">{NOT_FOUND}</p>')
    if d.get("conditions"):
        parts += ['<p class="deliv-label">Conditions</p>', html_list(d["conditions"])]
    if d.get("sponsor_obligations"):
        parts += ['<p class="deliv-label">Sponsor must</p>', html_list(d["sponsor_obligations"])]
    return "".join(parts) + "</div>"


# ---------- sections ----------

@st.dialog("Deliverable", width="large")
def show_dialog(row: dict, with_value: bool) -> None:
    st.markdown(dialog_head_html(row), unsafe_allow_html=True, anchors=False)
    facts = dialog_facts(row, with_value)
    for col, (label, value) in zip(st.columns(len(facts)), facts):
        col.markdown(fact_html(label, value), unsafe_allow_html=True)
    st.markdown(dialog_body_html(row), unsafe_allow_html=True)


def show_header(result: dict, key_prefix: str, grounding: dict, evaluation: dict | None,
                download_name: str) -> None:
    """Parties heading with Download JSON on the right, then the summary line (and eval line)."""
    left, right = st.columns([5, 1], vertical_alignment="center")
    left.header(md_label(parties_heading(result["contract"])), anchor=False)
    right.download_button("Download JSON", json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                          file_name=download_name, mime="application/json",
                          key=f"{key_prefix}_download", width="stretch")
    st.markdown(summary_html(result["contract"], grounding, anchor_id(key_prefix)), unsafe_allow_html=True)
    if evaluation:
        st.markdown(f'<p class="deliv-muted">{esc(eval_line(evaluation))}</p>', unsafe_allow_html=True)


def show_table(rows: list[tuple[int, dict]], key_prefix: str, with_value: bool) -> None:
    """Header row plus one row per deliverable; the Clause button opens that row's dialog."""
    columns = BASE_COLUMNS + ([VALUE_COLUMN] if with_value else []) + [STATUS_COLUMN]
    ratios = [ratio for _, ratio in columns]
    with st.container(key=f"{key_prefix}_deliv_table", gap=None):
        with st.container(key=f"{key_prefix}_deliv_head"):
            for col, (name, _) in zip(st.columns(ratios), columns):
                col.markdown(f'<div class="deliv-th">{name}</div>', unsafe_allow_html=True)
        for i, row in rows:
            with st.container(key=f"{key_prefix}_deliv_row_{i}"):
                cells = st.columns(ratios)
                # Open the dialog only here, on the click, so other reruns never reopen it.
                if cells[0].button(md_label(row["clause"]), type="tertiary", key=f"{key_prefix}_row_{i}"):
                    show_dialog(row, with_value)
                texts = [row["type"], row["whats_owed"], row["qty"], row["when"]]
                if with_value:
                    texts.append(row["value"])
                for col, text in zip(cells[1:], texts):
                    col.markdown(cell_html(text), unsafe_allow_html=True)
                cells[-1].markdown(status_html(row["status"]), unsafe_allow_html=True)


def show_deliverables(result: dict, key_prefix: str, contract_text: str) -> None:
    rows = list(enumerate(table_rows(result, contract_text)))
    counts = type_counts(result)
    labels = {ALL_TYPES: f"All {len(rows)}", **{label: f"{label} {count}" for label, count in counts}}

    heading = st.empty()  # filled after the pills, once the shown count is known
    choice = ALL_TYPES
    if len(counts) > 1:
        choice = st.pills("Filter by type", list(labels), default=ALL_TYPES, format_func=labels.get,
                          required=True, label_visibility="collapsed", key=f"{key_prefix}_types")
    shown = [(i, row) for i, row in rows if choice in (ALL_TYPES, None) or row["type"] == choice]
    showing = f'<span class="deliv-showing">Showing {len(shown)}</span>' if len(shown) < len(rows) else ""
    # Streamlit replaces a heading's id with its own slug, so the link target is a separate empty div.
    heading.markdown(f'<div id="{anchor_id(key_prefix)}"></div><h3>{len(rows)} deliverables{showing}</h3>',
                     unsafe_allow_html=True, anchors=False)

    show_table(shown, key_prefix, show_value_column(result))
    st.caption(NO_SELECTION)


def show_result(result: dict, key_prefix: str, contract_text: str, download_name: str,
                evaluation: dict | None = None) -> None:
    """Summary header (with download and optional eval line), then the filterable table."""
    flags = grounded_flags(result["deliverables"], contract_text)
    grounding = {"grounded": sum(flags), "total": len(flags)}
    show_header(result, key_prefix, grounding, evaluation, download_name)
    show_deliverables(result, key_prefix, contract_text)
