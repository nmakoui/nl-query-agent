"""
Dynamic Charts Tab for QueryLens
================================

This module provides a Streamlit tab that allows users to visualize
the results of previously executed queries using various chart types.
Charts are generated dynamically based on the structure of the data. If
both categorical and numeric columns exist, bar and pie charts are
displayed; if multiple numeric columns exist, a scatter plot is shown;
if a date or time column is detected, a line chart is used to show
trends. If no suitable columns are found, an informative message is
displayed.

The tab interacts with the global `st.session_state.history` to let
users select which query result to visualize. It re‑executes the
chosen query to fetch fresh data, then generates charts using
plotly.express.
"""

from typing import List, Tuple, Optional

import pandas as pd
import streamlit as st
import plotly.express as px

from validator import validate_sql
from db import run_sql


def _infer_numeric_columns(df: pd.DataFrame) -> List[str]:
    """Attempt to infer numeric columns, even if stored as object dtype."""
    numeric_cols: List[str] = []
    for col in df.columns:
        # Skip if dtype is numeric
        if pd.api.types.is_numeric_dtype(df[col]):
            numeric_cols.append(col)
            continue
        # Try to coerce to numeric
        coerced = pd.to_numeric(df[col], errors="coerce")
        # If at least half the values are numeric, treat as numeric
        non_na = coerced.notna().sum()
        if non_na > len(df) / 2:
            df[col] = coerced
            numeric_cols.append(col)
    return numeric_cols


def _infer_categorical_columns(df: pd.DataFrame, numeric_cols: List[str]) -> List[str]:
    """Identify categorical columns by excluding numeric columns."""
    return [col for col in df.columns if col not in numeric_cols]


def _detect_datetime_column(df: pd.DataFrame) -> Optional[str]:
    """Return the name of a datetime-like column if found, otherwise None."""
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            return col
        # Heuristic: column name contains date or time
        name = col.lower()
        if "date" in name or "time" in name or "day" in name:
            try:
                parsed = pd.to_datetime(df[col], errors="coerce")
                if parsed.notna().sum() > len(df) / 2:
                    df[col] = parsed
                    return col
            except Exception:
                continue
    return None


def _generate_charts(df: pd.DataFrame) -> List[Tuple[str, object]]:
    """
    Generate a list of chart specifications from the DataFrame.

    Each chart is returned as a tuple of (title, plotly figure). The
    function determines suitable chart types based on the available
    columns. Charts may include bar charts, pie charts, scatter plots,
    and line charts.
    """
    charts: List[Tuple[str, object]] = []
    if df.empty:
        return charts
    # Make a copy to avoid modifying original
    working_df = df.copy()
    numeric_cols = _infer_numeric_columns(working_df)
    categorical_cols = _infer_categorical_columns(working_df, numeric_cols)
    # Generate bar and pie charts if at least one numeric and one categorical
    if numeric_cols and categorical_cols:
        x_col = categorical_cols[0]
        y_col = numeric_cols[0]
        # Aggregate by first categorical for bar and pie
        try:
            grouped = working_df.groupby(x_col)[y_col].sum().reset_index()
        except Exception:
            # fallback to using raw values (may not aggregate as expected)
            grouped = working_df[[x_col, y_col]].dropna()
        # Bar chart
        fig_bar = px.bar(grouped, x=x_col, y=y_col, title=f"Sum of {y_col} by {x_col}")
        charts.append((f"Bar Chart: {y_col} by {x_col}", fig_bar))
        # Pie chart
        fig_pie = px.pie(grouped, names=x_col, values=y_col, title=f"Distribution of {y_col} by {x_col}")
        charts.append((f"Pie Chart: {y_col} by {x_col}", fig_pie))
    # Generate scatter if at least two numeric cols
    if len(numeric_cols) >= 2:
        x_num = numeric_cols[0]
        y_num = numeric_cols[1]
        fig_scatter = px.scatter(
            working_df,
            x=x_num,
            y=y_num,
            title=f"Scatter Plot: {y_num} vs {x_num}",
            trendline="ols",
        )
        charts.append((f"Scatter: {y_num} vs {x_num}", fig_scatter))
    # Generate line chart if a datetime column exists
    datetime_col = _detect_datetime_column(working_df)
    if datetime_col and numeric_cols:
        y_col_dt = numeric_cols[0]
        # Sort by datetime to make lines monotonic
        dt_sorted = working_df[[datetime_col, y_col_dt]].dropna().sort_values(datetime_col)
        fig_line = px.line(
            dt_sorted,
            x=datetime_col,
            y=y_col_dt,
            title=f"Trend of {y_col_dt} over {datetime_col}",
        )
        charts.append((f"Line Chart: {y_col_dt} over {datetime_col}", fig_line))
    return charts


def render_charts_tab() -> None:
    """
    Render the Dynamic Charts tab in Streamlit.

    The tab allows the user to select any previously executed query from
    the history and visualize the results with various chart types. It
    re‑runs the stored SQL to fetch fresh data and displays multiple
    charts based on the detected column types. If no suitable charts can
    be generated, a message is displayed.
    """
    st.header("📊 Dynamic Charts")
    st.caption(
        "Select a past query to create charts. The assistant will automatically "
        "choose the most suitable visualisations based on the data structure."
    )
    history = st.session_state.get("history", [])  # type: ignore
    if not history:
        st.info("Run at least one query to generate charts.")
        return
    # Prepare selection options
    options = []
    labels = []
    for item in reversed(history):
        options.append(item)
        labels.append(f"{item['question']} (ran at {item['time']})")
    # Use a unique key to avoid duplicate element IDs
    idx = st.selectbox(
        "Choose a query to visualize",
        options=list(range(len(options))),
        format_func=lambda i: labels[i],
        key="charts_query_selectbox",
    )
    selected = options[idx]
    question = selected.get("question", "")
    sql = selected.get("sql", "")
    with st.expander("Show generated SQL", expanded=False):
        st.code(sql, language="sql")
    if st.button("Generate Charts", key="generate_charts_button"):
        with st.spinner("Running query and generating charts…"):
            try:
                validate_sql(sql)
                df = run_sql(sql)
            except Exception as e:
                st.error(f"Failed to execute query: {e}")
                return
            # Generate charts based on data
            charts = _generate_charts(df)
            if not charts:
                st.warning("No suitable numeric or categorical columns found to generate charts.")
                return
            for title, fig in charts:
                st.subheader(title)
                st.plotly_chart(fig, use_container_width=True)