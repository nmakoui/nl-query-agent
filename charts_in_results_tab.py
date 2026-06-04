"""
Dynamic and Aggregated Charts for Result Tabs
============================================

This module defines a function to render both dynamic and aggregated
visualisations within the results tab of the QueryLens application. The
dynamic charts are derived from the current query's DataFrame and
exclude ID columns from grouping. Aggregated charts summarise the
entire `amazon` table to show broader sales patterns.

Charts include:
 - Bar and percentage charts for categorical vs numeric data (dynamic)
 - Line charts for numeric comparisons and time series trends (dynamic)
 - Sales per category and percentage (aggregated)
 - Sales per rating bucket (aggregated)
 - Sales per price range (aggregated)

All charts are rendered using Streamlit's built‑in chart functions.
"""

from typing import List, Optional, Dict, Any

import pandas as pd
import streamlit as st
from db import run_sql
from validator import validate_sql


def _convert_numeric_columns(df: pd.DataFrame) -> List[str]:
    """
    Convert columns to numeric where possible and return the list of
    numeric columns. String columns that can be coerced to floats
    are converted in place.
    """
    numeric_cols: List[str] = []
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            numeric_cols.append(col)
        else:
            # Try to coerce object columns to numeric
            coerced = pd.to_numeric(df[col], errors="coerce")
            if coerced.notna().sum() > 0:
                df[col] = coerced
                numeric_cols.append(col)
    return numeric_cols


def _detect_date_column(df: pd.DataFrame) -> Optional[str]:
    """
    Detect a date/time column by dtype or heuristics in column names.
    Returns the column name or None if not found.
    """
    for col in df.columns:
        # Check dtype directly
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            return col
        # Heuristic: name contains date or time keywords
        name = col.lower()
        if any(keyword in name for keyword in ["date", "time", "day", "month", "year"]):
            # Try to parse at least half of the values
            try:
                parsed = pd.to_datetime(df[col], errors="coerce")
                if parsed.notna().sum() > len(df) / 2:
                    df[col] = parsed
                    return col
            except Exception:
                continue
    return None


def render_charts_in_results(df: pd.DataFrame) -> None:
    """
    Render dynamic and aggregated charts within the results tab.

    This function first produces charts based on the current query result
    (`df`) while ensuring that ID columns (product_id, user_id, review_id)
    are not used as categorical groupings. It then fetches aggregated
    statistics from the full `amazon` table to generate broader
    insights. All charts are displayed in a grid with two charts per
    row.

    Parameters
    ----------
    df : pandas.DataFrame
        The result DataFrame from the user's query. If None or empty,
        only aggregated charts will be displayed.
    """
    # List to collect dynamic chart specifications
    dynamic_chart_specs: List[Dict[str, Any]] = []
    if df is not None and not df.empty:
        # Copy to avoid modifying original DataFrame
        data = df.copy()
        # Identify numeric and categorical columns; exclude ID columns from categorical
        numeric_cols = _convert_numeric_columns(data)
        id_columns = {"product_id", "user_id", "review_id"}
        categorical_cols = [
            col
            for col in data.columns
            if col not in numeric_cols and col.lower() not in id_columns
        ]
        # Dynamic bar and percentage charts based on first categorical and numeric columns
        if numeric_cols and categorical_cols:
            x_col = categorical_cols[0]
            y_col = numeric_cols[0]
            try:
                temp = data[[x_col, y_col]].dropna()
                grouped = temp.groupby(x_col)[y_col].sum().reset_index()
            except Exception:
                grouped = data[[x_col, y_col]].dropna()
            if not grouped.empty:
                bar_df = grouped.set_index(x_col)[y_col]
                dynamic_chart_specs.append({
                    "title": f"Sum of {y_col} by {x_col}",
                    "chart_type": "bar",
                    "data": bar_df,
                })
                total = bar_df.sum()
                if total > 0:
                    percent_series = bar_df / total * 100
                    percent_df = pd.DataFrame({"percentage": percent_series})
                    dynamic_chart_specs.append({
                        "title": f"Percentage distribution of {y_col} by {x_col}",
                        "chart_type": "bar",
                        "data": percent_df,
                    })
        # Dynamic multi‑line chart for first two numeric columns
        if len(numeric_cols) >= 2:
            x_num = numeric_cols[0]
            y_num = numeric_cols[1]
            multi_df = data[[x_num, y_num]].dropna()
            if not multi_df.empty:
                dynamic_chart_specs.append({
                    "title": f"Line chart comparing {x_num} and {y_num}",
                    "chart_type": "line",
                    "data": multi_df[[x_num, y_num]],
                })
        # Dynamic trend chart for first numeric column over a detected date/time column
        date_col = _detect_date_column(data)
        if date_col and numeric_cols:
            y_dt = numeric_cols[0]
            dt_df = data[[date_col, y_dt]].dropna().sort_values(date_col)
            if not dt_df.empty:
                trend_df = dt_df.set_index(date_col)[y_dt]
                dynamic_chart_specs.append({
                    "title": f"Trend of {y_dt} over {date_col}",
                    "chart_type": "line",
                    "data": trend_df,
                })
    # Prepare aggregated charts from the entire amazon table
    aggregated_specs: List[Dict[str, Any]] = []
    # 1. Sales per category and percentages
    query_cat = """
        SELECT category,
               SUM(TO_NUMBER(REGEXP_REPLACE(discounted_price, '[^0-9.]', ''))) AS sales
        FROM amazon
        GROUP BY category
        ORDER BY sales DESC
    """
    try:
        validate_sql(query_cat)
        df_cat = run_sql(query_cat)
        if df_cat is not None and not df_cat.empty:
            df_cat.columns = [c.lower() for c in df_cat.columns]
            df_cat["sales"] = pd.to_numeric(df_cat["sales"], errors="coerce")
            df_cat = df_cat.dropna(subset=["category", "sales"])
            if not df_cat.empty:
                bar_df = df_cat.set_index("category")["sales"]
                aggregated_specs.append({
                    "title": "Sales per Category",
                    "chart_type": "bar",
                    "data": bar_df,
                })
                total_sales = bar_df.sum()
                if total_sales > 0:
                    percent_series = bar_df / total_sales * 100
                    percent_df = pd.DataFrame({"percentage": percent_series})
                    aggregated_specs.append({
                        "title": "Sales per Category (Percentage)",
                        "chart_type": "bar",
                        "data": percent_df,
                    })
    except Exception as e:
        st.warning(f"Could not generate sales per category chart: {e}")
    # 2. Sales per rating bucket
    query_rating = """
        SELECT rating,
               SUM(TO_NUMBER(REGEXP_REPLACE(discounted_price, '[^0-9.]', ''))) AS sales
        FROM amazon
        GROUP BY rating
    """
    try:
        validate_sql(query_rating)
        df_rating = run_sql(query_rating)
        if df_rating is not None and not df_rating.empty:
            df_rating.columns = [c.lower() for c in df_rating.columns]
            df_rating["rating_num"] = pd.to_numeric(df_rating["rating"], errors="coerce")
            df_rating["sales"] = pd.to_numeric(df_rating["sales"], errors="coerce")
            df_rating = df_rating.dropna(subset=["rating_num", "sales"])
            if not df_rating.empty:
                bins = [0, 2, 3, 4, 5, float("inf")]
                labels = ["0–2", "2–3", "3–4", "4–5", "5+"]
                df_rating["rating_bucket"] = pd.cut(df_rating["rating_num"], bins=bins, labels=labels, right=False)
                bucket_df = df_rating.groupby("rating_bucket")["sales"].sum().reset_index().dropna()
                if not bucket_df.empty:
                    chart_df = bucket_df.set_index("rating_bucket")["sales"]
                    aggregated_specs.append({
                        "title": "Sales per Rating Bucket",
                        "chart_type": "bar",
                        "data": chart_df,
                    })
    except Exception as e:
        st.warning(f"Could not generate sales per rating bucket chart: {e}")
    # 3. Sales per price range
    query_price = """
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
    try:
        validate_sql(query_price)
        df_price = run_sql(query_price)
        if df_price is not None and not df_price.empty:
            df_price.columns = [c.lower() for c in df_price.columns]
            df_price["sales"] = pd.to_numeric(df_price["sales"], errors="coerce")
            df_price = df_price.dropna(subset=["price_range", "sales"])
            if not df_price.empty:
                chart_df = df_price.set_index("price_range")["sales"]
                aggregated_specs.append({
                    "title": "Sales per Price Range",
                    "chart_type": "bar",
                    "data": chart_df,
                })
    except Exception as e:
        st.warning(f"Could not generate sales per price range chart: {e}")
    # Combine all chart specs
    all_specs: List[Dict[str, Any]] = dynamic_chart_specs + aggregated_specs
    if not all_specs:
        st.info("No charts available to display.")
        return
    # Display charts in a grid (two charts per row)
    for i in range(0, len(all_specs), 2):
        cols = st.columns(2)
        for j in range(2):
            if i + j < len(all_specs):
                spec = all_specs[i + j]
                with cols[j]:
                    st.subheader(spec["title"])
                    if spec["chart_type"] == "bar":
                        st.bar_chart(spec["data"])
                    elif spec["chart_type"] == "line":
                        st.line_chart(spec["data"])
