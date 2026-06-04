import streamlit as st
import json
import time
from datetime import datetime
from ai_sql_generator import call_ai_inference_endpoint
from validator import validate_sql
from db import run_sql
from sql_explanation import sql_explanation

# ── Page Config ──────────────────────────────────────────────────
st.set_page_config(page_title="QueryLens · AI Data Assistant", page_icon="🔍", layout="wide")

# ── Styling (From DemiApp) ───────────────────────────────────────
st.markdown("""
<style>
html, body, [class*="css"] {
    background-color: #0d0f14 !important;
    color: #e2e8f0 !important;
}
[data-testid="stTextInput"] input {
    background-color: #313b57 !important;
    color: #e2e8f0 !important;
    border: 1px solid #252b3b !important;
    border-radius: 8px !important;
}
[data-testid="stButton"] > button {
    background-color: #f0a500 !important;
    color: #0d0f14 !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}
</style>
""", unsafe_allow_html=True)

# ── Session State Tracking ───────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []
if "prefill" not in st.session_state:
    st.session_state.prefill = ""

# ── AI Backend Functions (From core app.py) ──────────────────────
def evaluate_ai_response():
    force_generation = "true" if st.session_state.follow_up_count >= 3 else "false"
    conversation_history = st.session_state.get("conversation_history", "No history yet.")

    prompt_payload = f"""
You are an expert Oracle SQL architect and natural language classifier.

CONVERSATION HISTORY:
{conversation_history}

Do NOT ask about anything already answered in the history above.

DATABASE SCHEMA:
Table name: amazon
Columns:
- product_id (VARCHAR2)
- product_name (VARCHAR2)
- category (VARCHAR2)
- discounted_price (VARCHAR2)
- actual_price (VARCHAR2)
- discount_percentage (VARCHAR2)
- rating (VARCHAR2)
- rating_count (VARCHAR2)
- about_product (VARCHAR2)
- user_id (VARCHAR2)
- user_name (VARCHAR2)
- review_id (VARCHAR2)
- review_title (VARCHAR2)
- review_content (VARCHAR2)
- img_link (VARCHAR2)
- product_link (VARCHAR2)

FORCE RULE: force_generation = {force_generation}
If force_generation is true, you MUST output status "success" with your best-effort SQL.

DECISION RULES:
1. DEFAULT TO AMBIGUOUS first. If ambiguous, set status "ambiguous" and ask ONE specific question to clarify.
2. Only set "success" if it maps directly with no interpretation needed.
3. Use clarification history to finalize SQL.

SQL RULES:
- Oracle syntax only. Use FETCH FIRST N ROWS ONLY, never LIMIT.
- SELECT queries only.
- For rating and rating_count wrap with: TO_NUMBER(REGEXP_REPLACE(column_name, '[^0-9.]', ''))
- To extract top-level category use: SUBSTR(category, 1, INSTR(category || '|', '|') - 1)
- No semicolon at the end of the query.

Respond ONLY with this raw JSON:
{{
    "status": "success" or "ambiguous",
    "follow_up_message": "One specific question if ambiguous, otherwise null",
    "sql": "The SQL query if success, otherwise null"
}}
"""
    try:
        raw_response = call_ai_inference_endpoint(prompt_payload)
        with st.expander("🔍 Debug: Raw AI Response"):
            st.code(raw_response)
        result_data = json.loads(raw_response, strict=False)

        if result_data.get("status") == "success" or force_generation == "true":
            st.session_state.is_ready = True
            sql = result_data.get("sql", "").strip().rstrip(";").strip()
            st.session_state.ai_message = sql
        else:
            st.session_state.is_ready = False
            st.session_state.ai_message = result_data.get("follow_up_message")

    except Exception as e:
        st.session_state.is_ready = True
        st.session_state.ai_message = "SELECT * FROM amazon FETCH FIRST 20 ROWS ONLY"


def manage_clarification(user_input):
    if "current_q" not in st.session_state or st.session_state.get("original_q") != user_input:
        st.session_state.original_q = user_input
        st.session_state.current_q = user_input
        st.session_state.conversation_history = f"Initial User Query: {user_input}"
        st.session_state.follow_up_count = 0
        st.session_state.is_ready = False
        st.session_state.ai_message = None

        with st.spinner("Analyzing request framework..."):
            evaluate_ai_response()

    if st.session_state.is_ready:
        return st.session_state.ai_message

    # Handle clarifying conversation flows elegantly
    st.info(f"🤔 Clarification Required ({st.session_state.follow_up_count + 1}/3): {st.session_state.ai_message}")
    user_answer = st.text_input("Please specify:", key="followup_input")

    if st.button("Submit Clarification") and user_answer:
        st.session_state.conversation_history += (
            f"\nAI Clarification Question Asked: {st.session_state.ai_message}"
            f"\nUser Clarification Answer Provided: {user_answer}"
        )
        st.session_state.follow_up_count += 1

        with st.spinner("Processing insights..."):
            evaluate_ai_response()
        st.rerun()

    return None

# ── App Header UI ────────────────────────────────────────────────
st.markdown("""
<div style="display:flex; align-items:center; gap:12px; padding-bottom:1rem;
            border-bottom:1px solid #252b3b; margin-bottom:1.5rem;">
    <div style="width:38px; height:38px; background:#f0a500; border-radius:8px;
                display:flex; align-items:center; justify-content:center; font-size:20px;">
        🔍
    </div>
    <div>
        <div style="font-size:1.2rem; font-weight:600; letter-spacing:-0.02em;">QueryLens</div>
        <div style="font-size:0.75rem; color:#64748b; margin-top:2px;">AI-Powered Oracle Data Assistant</div>
    </div>
    <div style="margin-left:auto; background:rgba(240,165,0,0.12); border:1px solid rgba(240,165,0,0.25);
                color:#f0a500; font-size:0.65rem; padding:3px 10px; border-radius:99px;
                letter-spacing:0.05em; text-transform:uppercase;">
        AI Agent
    </div>
</div>
""", unsafe_allow_html=True)

# ── Search Input Block ───────────────────────────────────────────
user_question = st.text_input(
    label="Ask a question about Amazon sales data:",
    placeholder="e.g., Show products with rating above 4 sorted by top reviews.",
    value=st.session_state.prefill
)

run_button = st.button("Run Query")

# ── Quick Pick Suggestions ───────────────────────────────────────
SUGGESTIONS = [
    "Highest rated items?",
    "Top 5 products with most reviews?",
    "Discount trends by category?",
    "Products with over 50% off?",
]

st.markdown("<div style='font-size:0.75rem; color:#64748b; margin-bottom:6px;'>Suggested questions</div>", unsafe_allow_html=True)
cols = st.columns(len(SUGGESTIONS))
for col, suggestion in zip(cols, SUGGESTIONS):
    with col:
        if st.button(suggestion, use_container_width=True):
            st.session_state.prefill = suggestion
            st.rerun()

st.divider()

# ── Core App Logic Controller ────────────────────────────────────
if user_question and (run_button or st.session_state.get("original_q") == user_question):
    
    # Process or catch clarification rules
    final_sql = manage_clarification(user_question)
    
    if final_sql:
        STEPS = [
            "🧠  Parsing natural language intent",
            "🗺️  Mapping terms to Oracle schema",
            "✍️  Generating clean Oracle SQL query",
            "⚡  Executing on Live Database",
            "📊  Analyzing result matrix",
            "💬  Composing data summary",
        ]

        with st.status("Agent executing tasks...", expanded=True) as status:
            placeholders = [st.empty() for _ in STEPS]

            # Visual aesthetic progression from DemiApp
            for i, label in enumerate(STEPS):
                placeholders[i].markdown(f"⬜ {label}")
                time.sleep(0.3)
                placeholders[i].markdown(f"✅ {label}")

            try:
                validate_sql(final_sql)
                result_df = run_sql(final_sql)
                error = None
            except Exception as e:
                result_df = None
                error = str(e)

            if error:
                status.update(label="❌ Execution failed", state="error")
                st.error(f"Something went wrong during execution: {error}")
            else:
                status.update(label="✅ Query complete", state="complete")

        if not error and result_df is not None:
            # Capture query instance history
            if not st.session_state.history or st.session_state.history[-1]["question"] != user_question:
                st.session_state.history.append({
                    "question": user_question,
                    "sql": final_sql,
                    "summary": f"Returned {len(result_df)} rows.",
                    "time": datetime.now().strftime("%H:%M:%S"),
                })

            # Tab Layout Rendering
            tab_results, tab_insights, tab_sql = st.tabs(["📋 Results", "💡 Insights", "⌨️ SQL"])

            with tab_results:
                st.dataframe(result_df, use_container_width=True)
                csv = result_df.to_csv(index=False)
                st.download_button(
                    label="⬇️ Download results as CSV",
                    data=csv,
                    file_name="query_results.csv",
                    mime="text/csv"
                )

            with tab_insights:
                st.subheader("Explanation:")
                
                try:
                    explanation_text = sql_explanation(final_sql)
                except Exception as e:
                    explanation_text = None
                    st.warning(f"Could not generate SQL explanation: {e}")
                
                if explanation_text:
                    st.markdown(explanation_text)
                else:
                    st.info("SQL explanation was not available for this query.")
                
                st.divider()

                num_cols = result_df.select_dtypes(include="number").columns.tolist()
                str_cols = result_df.select_dtypes(exclude="number").columns.tolist()

                if num_cols and len(result_df) > 1:
                    st.subheader("Chart Analysis")
                    chart_index = str_cols[0] if str_cols else result_df.columns[0]
                    chart_col = num_cols[0]
                    chart_df = result_df.set_index(chart_index)[[chart_col]]
                    st.bar_chart(chart_df)
                else:
                    st.caption("Chart not available for single-row or non-numeric results.")

                st.divider()

                if num_cols:
                    st.subheader("Descriptive Statistics")
                    st.dataframe(result_df[num_cols].describe().round(2), use_container_width=True)
                else:
                    st.caption("No numeric columns available to summarize.")

            with tab_sql:
                st.subheader("Generated Oracle SQL")
                st.code(final_sql, language="sql")

# ── Sidebar Control Panel History ────────────────────────────────
with st.sidebar:
    st.header("Query History")
    st.metric("Queries Run", len(st.session_state.history))

    if not st.session_state.history:
        st.caption("Your previous questions will appear here.")
    else:
        for i, item in enumerate(reversed(st.session_state.history)):
            with st.expander(item["question"][:50]):
                st.caption(item["time"])
                st.caption("Generated SQL:")
                st.code(item["sql"], language="sql")
                st.caption("Summary:")
                st.write(item["summary"])
                if st.button("Run Again", key=f"rerun_{i}"):
                    st.session_state.prefill = item["question"]
                    st.rerun()

        if st.button("Clear history"):
            st.session_state.history = []   
            st.rerun()
