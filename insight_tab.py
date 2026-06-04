"""
AI Result Insight Generator Module for QueryLens
================================================

This module introduces functionality to generate high‑level analytical
insights from the results of SQL queries. After a user runs a query in
the main application, they can open the AI Insights tab to select any
previously executed query and ask the assistant to analyze its results.

The assistant uses a prompt‑engineering approach to convert a snippet
of the result table into a CSV string, then asks the LLM to derive
meaningful observations, trends, or anomalies. This keeps the
implementation consistent with the existing architecture built around
`call_ai_inference_endpoint`.

Usage:
    In your Streamlit app, import `render_insight_tab` and call it
    within its own tab. This function expects `st.session_state.history`
    to contain at least one entry with keys 'question' and 'sql'. It
    re‑executes the selected SQL query via `run_sql` to obtain the
    DataFrame, then generates insights from the top rows.

Note:
    This module avoids modifying the core logic of the main app. All
    database execution is read‑only and reuses validated SQL from
    previous runs.
"""

import json
from typing import List

import pandas as pd
import streamlit as st

from ai_sql_generator import call_ai_inference_endpoint
from validator import validate_sql
from db import run_sql


def _generate_insights_from_dataframe(df: pd.DataFrame, question: str, sql: str) -> str:
    """
    Generate human‑readable insights from a pandas DataFrame based on the
    user's original question and the SQL used to retrieve the data.

    The function takes a subset of the DataFrame (up to the first
    100 rows) and converts it into a CSV string. This string, along
    with the question and SQL, is passed to the LLM via
    `call_ai_inference_endpoint` with instructions to extract key
    observations. The response is returned as plain text.

    Parameters
    ----------
    df : pandas.DataFrame
        The DataFrame containing query results.
    question : str
        The natural language question the user asked.
    sql : str
        The SQL query executed to produce the DataFrame.

    Returns
    -------
    str
        The generated insights from the LLM.
    """
    # Take at most the first 100 rows to keep the prompt concise
    preview_df = df.copy()
    if len(preview_df) > 100:
        preview_df = preview_df.head(100)

    # Convert the preview DataFrame to CSV
    csv_data = preview_df.to_csv(index=False)

    # Construct a prompt instructing the LLM to derive insights
    prompt = f"""
You are a professional data analyst tasked with summarizing the results of a database query.

Below is the user's question, the SQL statement that was executed, and a preview of the query
results formatted as CSV. Provide a concise list of 3–5 insightful observations that capture
trends, patterns, outliers, or relationships present in the data. Avoid repeating column names
unnecessarily, and avoid stating the obvious (e.g. that there are 100 rows). If there is
nothing interesting in the preview, say so clearly.

Question: {question}
SQL: {sql}
Preview (CSV):
{csv_data}

Respond with plain text containing a bulleted list of insights. Do not
include any SQL or code in your answer.
"""

    # Invoke the inference endpoint
    raw_response = call_ai_inference_endpoint(prompt)
    # Strip off any leading/trailing whitespace or markdown
    response_text = raw_response.strip()

    # Sometimes the LLM may wrap the response in JSON; attempt to extract
    # a 'insights' field if present
    try:
        parsed = json.loads(response_text)
        if isinstance(parsed, dict) and "insights" in parsed:
            response_text = parsed["insights"]
    except Exception:
        pass

    return response_text


def render_insight_tab() -> None:
    """
    Render the AI Insights tab in the Streamlit application.

    This function presents the user with a list of previously executed queries
    (stored in `st.session_state.history`). The user selects one of these
    queries, and upon clicking the **Generate Insights** button, the
    underlying SQL is re‑executed to fetch the current data. The top rows
    of this result set are analyzed by the LLM to produce a set of
    human‑readable insights.
    """
    st.header("🧠 AI Result Insights")
    st.caption(
        "Select a past query and let the AI highlight interesting patterns and trends "
        "from the result set. The assistant uses only the first 100 rows to ensure concise analysis."
    )

    history: List[dict] = st.session_state.get("history", [])  # type: ignore
    if not history:
        st.info("Run at least one query to generate insights.")
        return

    # Build selection options for the queries: display the question and time
    options = []
    option_labels = []
    for idx, item in enumerate(reversed(history)):
        label = f"{item['question']} (ran at {item['time']})"
        option_labels.append(label)
        options.append(item)

    # Assign a unique key to avoid duplicate element IDs across different tabs
    selected_index = st.selectbox(
        "Choose a query to analyze",
        options=list(range(len(options))),
        format_func=lambda i: option_labels[i],
        key="insights_query_selectbox",
    )

    if selected_index is None:
        return

    selected_entry = options[selected_index]
    question = selected_entry.get("question", "")
    sql = selected_entry.get("sql", "")

    # Display the selected SQL in an expandable section for transparency
    with st.expander("Show generated SQL", expanded=False):
        st.code(sql, language="sql")

    if st.button("Generate Insights", key="generate_insights_button"):
        with st.spinner("Running query and generating insights…"):
            try:
                # Ensure SQL is safe to run again
                validate_sql(sql)
                df = run_sql(sql)
            except Exception as e:
                st.error(f"Could not execute query: {e}")
                return

            # Generate insights from the DataFrame
            try:
                insights = _generate_insights_from_dataframe(df, question=question, sql=sql)
            except Exception as e:
                st.error(f"AI failed to generate insights: {e}")
                return

            # Display the results and the AI insights
            st.subheader("Query Result Preview")
            st.dataframe(df.head(20), use_container_width=True)

            st.subheader("AI‑Generated Insights")
            # If the response contains markdown bullet points, render directly
            st.markdown(insights)
