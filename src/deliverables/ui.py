"""Rendering helpers for the Streamlit demo (app.py). Needs the [demo] extra.

Every widget key is built from key_prefix, which starts with "upload_" or "sample_": both tabs
render on every rerun, so keys must not collide.
"""

import html
import json

import streamlit as st

from deliverables.table import category_label, contract_summary, display_rows

# The one block of injected CSS. Everything else comes from .streamlit/config.toml.
CSS = """
<style>
/* Cap the width on very wide screens; layout="wide" is still needed so all ten table columns fit. */
[data-testid="stMainBlockContainer"] { max-width: 1440px; }

/* Line up digits in metrics and the contract summary (the table is drawn on a canvas, so CSS can't reach it). */
[data-testid="stMetricValue"], .deliv-summary { font-variant-numeric: tabular-nums; }

/* Contract summary: labels left, values right; long values (like 49ers seasons) wrap inside their cell. */
.deliv-summary { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 0.35rem 1.5rem; margin: 0; }
.deliv-summary dt { font-weight: 600; }
.deliv-summary dd { margin: 0; overflow-wrap: anywhere; }
/* On phones, stack each label above its value. */
@media (max-width: 640px) { .deliv-summary { grid-template-columns: 1fr; gap: 0 0; } .deliv-summary dd { margin-bottom: 0.5rem; } }

/* Contract quotes: keep Streamlit's quiet left rule, but full-strength Ink (its default 60% opacity fails AA). */
[data-testid="stMarkdownContainer"] blockquote.deliv-quote { opacity: 1; }

/* Captions: Streamlit draws them at 60% opacity (4.0:1 on Paper, below AA); 75% gives 6.3:1. */
[data-testid="stCaptionContainer"] { opacity: 0.75; }

/* Small bold labels inside the row detail panel (no all caps). */
.deliv-label { font-weight: 600; margin: 0.75rem 0 0.25rem; }

/* "To be agreed" flag. Signal is 4.3:1 on Paper, so it stays at large-text size (19px bold, AA needs 3:1). */
.deliv-tba { color: #A8661A; font-weight: 700; font-size: 1.2rem; margin: 0.75rem 0 0; }
</style>
"""

NO_SELECTION = "Select a row to see the contract text behind it."


def inject_css() -> None:
    st.html(CSS)


def esc(text: str) -> str:
    """Escape for an HTML block in st.markdown: no tags, no LaTeX from '$', newlines kept."""
    return html.escape(text).replace("$", "&#36;").replace("\n", "<br>")


def html_list(items: list[str]) -> str:
    if not items:
        return "<p>None</p>"
    return "<ul>" + "".join(f"<li>{esc(item)}</li>" for item in items) + "</ul>"


def clause_label(section: str | None) -> str:
    """'3' -> 'Clause 3'; labels that name themselves ('Schedule 1, 2(a)') stay as they are."""
    if not section:
        return "Clause not numbered"
    return f"Clause {section}" if section[0].isdigit() else section


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


# ---------- sections ----------

def show_header(result: dict, key_prefix: str, download_name: str | None) -> None:
    """'Contract' heading, with the JSON download (secondary) on the right when given a file name."""
    left, right = st.columns([4, 1], vertical_alignment="bottom")
    left.subheader("Contract")
    if download_name:
        right.download_button("Download JSON", json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                              file_name=download_name, mime="application/json",
                              key=f"{key_prefix}_download", width="stretch")


def show_contract(contract: dict) -> None:
    rows = "".join(f"<dt>{esc(label)}</dt><dd>{esc(value)}</dd>" for label, value in contract_summary(contract))
    st.markdown(f'<dl class="deliv-summary">{rows}</dl>', unsafe_allow_html=True)


def show_eval(evaluation: dict) -> None:
    d, g = evaluation["deliverables"], evaluation["grounding"]
    st.subheader("Checked against the answer key")
    cols = st.columns(3)
    cols[0].metric("Recall", pct(d["recall"]))
    cols[0].caption(f"Found {d['matched']} of {d['gold']} deliverables in the hand-checked answer key.")
    cols[1].metric("Precision", pct(d["precision"]))
    cols[1].caption(f"{d['matched']} of {d['pred']} extracted items match an item in the answer key.")
    cols[2].metric("Grounding", pct(g["rate"]))
    cols[2].caption(f"{g['grounded']} of {g['total']} quotes appear word for word in the contract.")


def show_grounding(grounding: dict, key_prefix: str) -> None:
    st.subheader("Grounding")
    st.metric("Quotes found in the contract", pct(grounding["rate"]))
    st.caption(f"{grounding['grounded']} of {grounding['total']} quotes appear word for word in the PDF text. "
               "With no answer key for an uploaded contract, this is the automatic check.")
    if grounding["ungrounded"]:
        with st.expander(f"Quotes not found in the PDF ({len(grounding['ungrounded'])})",
                         key=f"{key_prefix}_ungrounded"):
            for item in grounding["ungrounded"]:
                st.markdown(f'<p class="deliv-label">{esc(clause_label(item["section"]))}</p>'
                            f'<blockquote class="deliv-quote">{esc(item["source_quote"])}</blockquote>',
                            unsafe_allow_html=True)


# Widths in px add up to about 1270 (with the selection column), which fits the 1440px max width.
COLUMN_CONFIG = {
    "Clause": st.column_config.TextColumn(width=130),
    "Type": st.column_config.TextColumn(width=140),
    "What's owed": st.column_config.TextColumn(width=300),
    "Qty": st.column_config.NumberColumn(width=48),
    "Unit": st.column_config.TextColumn(width=100),
    "When": st.column_config.TextColumn(width=150),
    "Value": st.column_config.NumberColumn(format="$%,d", width=88),
    "To be agreed": st.column_config.CheckboxColumn(width=96, disabled=True,
                                                    help="Dates or specifics are left for both sides to agree"),
    "Conditions": st.column_config.NumberColumn(width=84, help="Approvals or limits; select the row to read them"),
    "Sponsor must": st.column_config.NumberColumn(width=100,
                                                  help="Things the sponsor must do or pay for; select the row to read them"),
}


def show_detail(d: dict) -> None:
    """Contract text, conditions and obligations for one deliverable."""
    head = f"{clause_label(d['section'])} · {category_label(d['category'])}"
    parts = [
        f'<p class="deliv-label">{esc(head)}</p>',
        f"<p>{esc(d['description'])}</p>",
        '<p class="deliv-label">Contract text</p>',
        f'<blockquote class="deliv-quote">{esc(d["source_quote"])}</blockquote>',
        '<p class="deliv-label">Conditions</p>',
        html_list(d["conditions"]),
        '<p class="deliv-label">Sponsor obligations</p>',
        html_list(d["sponsor_obligations"]),
    ]
    if d["details_to_be_agreed"]:
        parts += ['<p class="deliv-tba">To be agreed</p>',
                  "<p>The contract leaves dates or specifics for the team and sponsor to agree.</p>"]
    else:
        parts.append("<p>Details are set in the contract.</p>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def show_deliverables(result: dict, key_prefix: str) -> None:
    deliverables = result["deliverables"]
    st.subheader(f"Deliverables ({len(deliverables)})")

    labels = [category_label(d["category"]) for d in deliverables]
    options = sorted(set(labels), key=labels.index)  # first-appearance order
    chosen = []
    if len(options) > 1:
        chosen = st.pills("Filter by type", options, selection_mode="multi", key=f"{key_prefix}_types") or []
    shown = [d for d, label in zip(deliverables, labels) if not chosen or label in chosen]
    if chosen:
        st.caption(f"Showing {len(shown)} of {len(deliverables)}")

    # The filter is part of the table key, so changing it clears a selection that would point at another row.
    table_key = f"{key_prefix}_table" + ("_" + "-".join(sorted(chosen)) if chosen else "")
    event = st.dataframe(display_rows({"deliverables": shown}), width="stretch", hide_index=True,
                         column_config=COLUMN_CONFIG, placeholder="–", height=min(len(shown), 12) * 35 + 38,
                         on_select="rerun", selection_mode="single-row", key=table_key)

    rows = [i for i in event.selection.rows if i < len(shown)]
    if not rows:
        st.caption(NO_SELECTION)
        return
    with st.container(border=True, key=f"{key_prefix}_detail"):
        show_detail(shown[rows[0]])


def show_result(result: dict, key_prefix: str, evaluation: dict | None = None,
                grounding: dict | None = None, download_name: str | None = None) -> None:
    """Header (with optional download), contract summary, eval or grounding, then the deliverables."""
    show_header(result, key_prefix, download_name)
    show_contract(result["contract"])
    if evaluation:
        show_eval(evaluation)
    if grounding:
        show_grounding(grounding, key_prefix)
    show_deliverables(result, key_prefix)

