"""
Follow-Up Question Suggestions for QueryLens
===========================================

This module adds a standalone Streamlit tab that suggests smart follow-up
questions after a query has been run. It uses the existing query history,
re-runs the selected SQL safely, sends a small preview of the result to the
same AI backend, and returns practical next questions the user can ask.

The module is intentionally isolated from the main app logic. It only reads
from st.session_state.history and writes to st.session_state.prefill when the
user clicks a suggestion button.
"""

import json
import re
from typing import List, Dict, Any

import pandas as pd
import streamlit as st

from ai_sql_generator import call_ai_inference_endpoint
from validator import validate_sql
from db import run_sql


DEFAULT_SUGGESTIONS = [
    "Group these results by category.",
    "Show only the highest-rated products from these results.",
    "Compare actual price and discounted price for these products.",
]


def _safe_dataframe_preview(df: pd.DataFrame, max_rows: int = 30) -> str:
    """
    Convert a DataFrame preview into CSV text for the AI prompt.
    Keeps prompts small and avoids sending too many rows to the model.
    """
    if df is None or df.empty:
        return "No rows returned."

    preview_df = df.head(max_rows).copy()
    return preview_df.to_csv(index=False)


def _extract_suggestions(raw_text: str) -> List[Dict[str, str]]:
    """
    Parse AI output into a stable list of suggestion dictionaries.

    Expected format:
    {
      "suggestions": [
        {"question": "...", "reason": "..."}
      ]
    }

    If the AI returns non-JSON text, this function falls back to extracting
    numbered or bulleted lines.
    """
    if not raw_text:
        return [{"question": q, "reason": "Useful next exploration step."} for q in DEFAULT_SUGGESTIONS]

    cleaned = raw_text.strip()
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(cleaned)
        suggestions = parsed.get("suggestions", []) if isinstance(parsed, dict) else []
        parsed_suggestions = []
        for item in suggestions:
            if isinstance(item, dict):
                question = str(item.get("question", "")).strip()
                reason = str(item.get("reason", "")).strip()
            else:
                question = str(item).strip()
                reason = "Useful next exploration step."

            if question:
                parsed_suggestions.append({
                    "question": question[:220],
                    "reason": reason[:280] if reason else "Useful next exploration step.",
                })

        if parsed_suggestions:
            return parsed_suggestions[:5]
    except Exception:
        pass

    # Fallback: extract useful lines from bullets or numbered lists.
    lines = []
    for line in cleaned.splitlines():
        line = line.strip()
        line = re.sub(r"^[-*•]\s*", "", line)
        line = re.sub(r"^\d+[.)]\s*", "", line)
        if line and len(line) > 8:
            lines.append(line)

    fallback = []
    for line in lines[:5]:
        fallback.append({"question": line[:220], "reason": "Suggested by the AI based on your previous query."})

    if fallback:
        return fallback

    return [{"question": q, "reason": "Useful next exploration step."} for q in DEFAULT_SUGGESTIONS]


def generate_followup_suggestions(question: str, sql: str, df: pd.DataFrame) -> List[Dict[str, str]]:
    """
    Generate context-aware follow-up questions for a previous query.

    The prompt asks the model for short, actionable questions that the user can
    ask next. Suggestions should be grounded in the actual result preview and
    the available Amazon table schema.
    """
    csv_preview = _safe_dataframe_preview(df, max_rows=30)
    columns = ", ".join([str(col) for col in df.columns]) if df is not None else "Unknown"

    prompt = f"""
You are a data exploration assistant for an Oracle SQL application.

The user has already asked a question and received query results. Your job is to suggest
high-value follow-up questions that a non-technical user can click next.

Original user question:
{question}

Generated SQL:
{sql}

Result columns:
{columns}

Result preview as CSV:
{csv_preview}

Available source table: amazon
Useful columns include product_id, product_name, category, discounted_price, actual_price,
discount_percentage, rating, rating_count, about_product, user_id, user_name, review_id,
review_title, review_content, img_link, product_link.

Rules:
1. Return exactly 4 follow-up questions.
2. Each question must be short, clear, and directly usable as a natural-language query.
3. Make the questions analytical, not generic.
4. Prefer useful next steps such as filtering, grouping, comparing, sorting, finding outliers, or drilling into categories.
5. Do not suggest anything that requires columns not available in the schema.
6. Do not mention SQL in the question.
7. Include a short reason explaining why each question is useful.
8. Return only raw JSON. Do not include markdown.

Output JSON format:
{{
  "suggestions": [
    {{"question": "...", "reason": "..."}},
    {{"question": "...", "reason": "..."}},
    {{"question": "...", "reason": "..."}},
    {{"question": "...", "reason": "..."}}
  ]
}}
"""

    try:
        raw_text = call_ai_inference_endpoint(prompt)
        return _extract_suggestions(raw_text)
    except Exception:
        return [{"question": q, "reason": "Fallback suggestion because the AI endpoint was unavailable."} for q in DEFAULT_SUGGESTIONS]


def render_followup_suggestions_tab() -> None:
    """
    Render the Follow-Up Suggestions tab.

    Users can select a previous query from session history, generate smart next
    questions, and click one to send it back to the main app's input box.
    """
    st.header("✨ Follow-Up Question Suggestions")
    st.caption(
        "Select a previous query, generate smart next-step questions, then click one to reuse it in the main query box."
    )

    history = st.session_state.get("history", [])
    if not history:
        st.info("Run at least one query first. Suggested follow-up questions will appear here after you have query history.")
        return

    # Use most recent queries first.
    reversed_history = list(reversed(history))
    labels = []
    for item in reversed_history:
        question = str(item.get("question", "Untitled query"))
        run_time = str(item.get("time", ""))
        labels.append(f"{question[:90]} — {run_time}")

    selected_idx = st.selectbox(
        "Choose the query you want to continue exploring",
        options=list(range(len(reversed_history))),
        format_func=lambda i: labels[i],
        key="followup_selected_query",
    )

    selected = reversed_history[selected_idx]
    question = selected.get("question", "")
    sql = selected.get("sql", "")

    with st.expander("Selected query context", expanded=False):
        st.markdown(f"**Question:** {question}")
        st.code(sql, language="sql")

    col_a, col_b = st.columns([1, 1])
    with col_a:
        generate_clicked = st.button("Generate Follow-Up Questions", key="generate_followups_button")
    with col_b:
        clear_clicked = st.button("Clear Suggestions", key="clear_followups_button")

    if clear_clicked:
        st.session_state.pop("followup_suggestions", None)
        st.session_state.pop("followup_source_sql", None)
        st.rerun()

    if generate_clicked:
        with st.spinner("Generating context-aware follow-up questions…"):
            try:
                validate_sql(sql)
                df = run_sql(sql)
            except Exception as e:
                st.error(f"Could not re-run the selected query: {e}")
                return

            suggestions = generate_followup_suggestions(question=question, sql=sql, df=df)
            st.session_state.followup_suggestions = suggestions
            st.session_state.followup_source_sql = sql
            st.session_state.followup_source_question = question

    suggestions = st.session_state.get("followup_suggestions", [])
    if not suggestions:
        st.info("Click Generate Follow-Up Questions to create suggested next questions for the selected query.")
        return

    st.subheader("Suggested Next Questions")

    for i, item in enumerate(suggestions, start=1):
        suggestion = str(item.get("question", "")).strip()
        reason = str(item.get("reason", "")).strip()
        if not suggestion:
            continue

        with st.container(border=True):
            st.markdown(f"**{i}. {suggestion}**")
            if reason:
                st.caption(reason)

            button_col_1, button_col_2 = st.columns([1, 3])
            with button_col_1:
                if st.button("Use this", key=f"use_followup_{i}"):
                    # Quality-of-life feature: put the selected suggestion into
                    # the existing main app input via the app's prefill state.
                    st.session_state.prefill = suggestion
                    st.success("Suggestion copied to the main query input. Scroll to the top and click Run Query.")
                    st.rerun()
            with button_col_2:
                st.code(suggestion, language=None)
