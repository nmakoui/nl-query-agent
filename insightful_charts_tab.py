"""
Additional Insightful Charts Module for QueryLens
================================================

This module defines a Streamlit tab renderer that provides additional
aggregated visualisations beyond the immediate query result. The charts
are derived from the full `amazon` dataset and offer a broader context
for understanding overall sales patterns. The following charts are
generated:

1. **Sales per Category (Bar Chart)** – Shows the total sales (sum of
   discounted_price) for each product category.
2. **Sales per Category Percentage (Bar Chart)** – Illustrates each
   category's share of overall sales as a percentage. This bar chart
   effectively replaces a pie chart given the limitations of the
   environment.
3. **Sales per Rating Bucket (Bar Chart)** – Groups products into rating
   ranges (0–2, 2–3, 3–4, 4–5, and 5+) and sums sales within each
   bucket.
4. **Sales per Price Range (Bar Chart)** – Buckets the discounted price
   into ranges (0–50, 50–100, 100–200, 200–500, 500+) and shows total
   sales for each range.

All charts use Streamlit's built‑in chart components (bar_chart) to
ensure compatibility in environments without external plotting
libraries. When a query fails or no data is available for a chart, a
message is displayed instead of raising an exception.

Usage:
    Within your Streamlit app, import `render_insightful_charts_tab` and
    call it inside a new tab. This will execute the necessary SQL
    queries against the Oracle database (via run_sql) and display
    the resulting charts.
"""

from typing import Optional

import pandas as pd
import streamlit as st

from db import run_sql
from validator import validate_sql


def _execute_query(sql: str) -> Optional[pd.DataFrame]:
    """
    Execute a SQL query against the Oracle database and return a DataFrame.

    If validation or execution fails, returns None and displays an error
    message. Queries are validated via `validate_sql` before execution.

    Parameters
    ----------
    sql : str
        The SQL query to execute.

    Returns
    -------
    pandas.DataFrame or None
        DataFrame of query results, or None if an error occurred.
    """
    try:
        # Ensure the query is syntactically valid Oracle SQL
        validate_sql(sql)
    except Exception as e:
        st.error(f"SQL validation failed: {e}")
        return None
    try:
        return run_sql(sql)
    except Exception as e:
        st.error(f"Error executing query: {e}")
        return None


def _sales_by_category() -> None:
    """Render sales per category and percentage charts."""
    query = """
        SELECT category,
               SUM(TO_NUMBER(REGEXP_REPLACE(discounted_price, '[^0-9.]', ''))) AS sales
        FROM amazon
        GROUP BY category
        ORDER BY sales DESC
    """
    df = _execute_query(query)
    if df is None or df.empty:
        st.warning("No data available for sales per category.")
        return
    # Normalize column names to lowercase
    df.columns = [c.lower() for c in df.columns]
    # Ensure numeric conversion
    try:
        df["sales"] = pd.to_numeric(df["sales"], errors="coerce")
    except Exception:
        pass
    # Drop rows with missing category or sales
    df = df.dropna(subset=["category", "sales"])
    if df.empty:
        st.warning("Sales data is empty after cleaning.")
        return
    # Display bar chart for absolute sales
    st.subheader("Sales per Category")
    # Set category as index for bar_chart
    bar_df = df.set_index("category")["sales"]
    st.bar_chart(bar_df)
    # Compute percentage distribution
    total_sales = bar_df.sum()
    if total_sales > 0:
        percent_series = (bar_df / total_sales) * 100
        percent_df = pd.DataFrame({"percentage": percent_series})
        st.subheader("Sales per Category (Percentage)")
        st.bar_chart(percent_df)
    else:
        st.info("Total sales are zero; percentage distribution cannot be computed.")


def _sales_by_rating_bucket() -> None:
    """Render sales aggregated by rating buckets."""
    query = """
        SELECT rating,
               SUM(TO_NUMBER(REGEXP_REPLACE(discounted_price, '[^0-9.]', ''))) AS sales
        FROM amazon
        GROUP BY rating
    """
    df = _execute_query(query)
    if df is None or df.empty:
        st.warning("No data available for sales by rating.")
        return
    df.columns = [c.lower() for c in df.columns]
    # Convert rating to numeric where possible
    df["rating_num"] = pd.to_numeric(df["rating"], errors="coerce")
    df["sales"] = pd.to_numeric(df["sales"], errors="coerce")
    # Drop rows without sales or rating
    df = df.dropna(subset=["rating_num", "sales"])
    if df.empty:
        st.warning("No valid rating data after cleaning.")
        return
    # Define rating buckets: [0,2), [2,3), [3,4), [4,5), [5, inf]
    bins = [0, 2, 3, 4, 5, float("inf")]
    labels = ["0–2", "2–3", "3–4", "4–5", "5+"]
    df["rating_bucket"] = pd.cut(df["rating_num"], bins=bins, labels=labels, right=False)
    # Aggregate sales by bucket
    bucket_df = df.groupby("rating_bucket")["sales"].sum().reset_index()
    # Drop any NaN buckets
    bucket_df = bucket_df.dropna()
    if bucket_df.empty:
        st.warning("No rating buckets available to plot.")
        return
    st.subheader("Sales per Rating Bucket")
    chart_df = bucket_df.set_index("rating_bucket")["sales"]
    st.bar_chart(chart_df)


def _sales_by_price_range() -> None:
    """Render sales aggregated by price ranges."""
    # Use SQL to group prices into ranges. Strings representing numbers are
    # converted to numeric using TO_NUMBER and REGEXP_REPLACE.
    query = """
        SELECT
            CASE
                WHEN TO_NUMBER(REGEXP_REPLACE(discounted_price, '[^0-9.]', '')) < 50  THEN '0–50'
                WHEN TO_NUMBER(REGEXP_REPLACE(discounted_price, '[^0-9.]', '')) < 100 THEN '50–100'
                WHEN TO_NUMBER(REGEXP_REPLACE(discounted_price, '[^0-9.]', '')) < 200 THEN '100–200'
                WHEN TO_NUMBER(REGEXP_REPLACE(discounted_price, '[^0-9.]', '')) < 500 THEN '200–500'
                ELSE '500+' END AS price_range,
            SUM(TO_NUMBER(REGEXP_REPLACE(discounted_price, '[^0-9.]', ''))) AS sales
        FROM amazon
        GROUP BY
            CASE
                WHEN TO_NUMBER(REGEXP_REPLACE(discounted_price, '[^0-9.]', '')) < 50  THEN '0–50'
                WHEN TO_NUMBER(REGEXP_REPLACE(discounted_price, '[^0-9.]', '')) < 100 THEN '50–100'
                WHEN TO_NUMBER(REGEXP_REPLACE(discounted_price, '[^0-9.]', '')) < 200 THEN '100–200'
                WHEN TO_NUMBER(REGEXP_REPLACE(discounted_price, '[^0-9.]', '')) < 500 THEN '200–500'
                ELSE '500+' END
    """
    df = _execute_query(query)
    if df is None or df.empty:
        st.warning("No data available for sales by price range.")
        return
    df.columns = [c.lower() for c in df.columns]
    df["sales"] = pd.to_numeric(df["sales"], errors="coerce")
    df = df.dropna(subset=["price_range", "sales"])
    if df.empty:
        st.warning("No price range data after cleaning.")
        return
    st.subheader("Sales per Price Range")
    chart_df = df.set_index("price_range")["sales"]
    st.bar_chart(chart_df)


def render_insightful_charts_tab() -> None:
    """
    Render the additional insightful charts tab.

    This tab executes a series of SQL queries to summarise the `amazon`
    table and then displays each summarisation as a bar chart. The
    function should be called within its own tab context in the
    Streamlit app.
    """
    st.header("📈 Additional Insightful Charts")
    st.caption(
        "These charts provide broader context by analysing the full "
        "Amazon dataset. They show how sales are distributed across "
        "categories, rating buckets, and price ranges."
    )
    # Display charts in sequence
    _sales_by_category()
    st.divider()
    _sales_by_rating_bucket()
    st.divider()
    _sales_by_price_range()