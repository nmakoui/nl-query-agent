import streamlit as st
import json
from ai_sql_generator import call_ai_inference_endpoint
from validator import validate_sql
from db import run_sql

SCHEMA_TEXT = """
Table: amazon
Columns:
- product_id
- product_name
- category
- discounted_price
- actual_price
- discount_percentage
- rating
- rating_count
- about_product
- user_id
- user_name
- review_id
- review_title
- review_content
- img_link
- product_link
"""

# ==========================================
# HELPER FUNCTION 1: Evaluate AI (Backend Logic)
# ==========================================
def evaluate_ai_response():
    """
    Builds the prompt with conversation history at the top,
    calls OCI Cohere, and updates session state with the result.
    """
    force_generation = "true" if st.session_state.follow_up_count >= 3 else "false"
    conversation_history = st.session_state.get("conversation_history", "No history yet.")

    prompt_payload = f"""
You are an expert Oracle SQL architect and natural language classifier.

CONVERSATION HISTORY (read this first before doing anything else):
{conversation_history}

Do NOT ask about anything already answered in the history above.

DATABASE SCHEMA:
Table name: amazon
Columns:
- product_id (VARCHAR2): Product ID
- product_name (VARCHAR2): Product name
- category (VARCHAR2): Product category (pipe-separated hierarchy e.g. Electronics|Cables&Accessories|Cables)
- discounted_price (VARCHAR2): Discounted price
- actual_price (VARCHAR2): Original price
- discount_percentage (VARCHAR2): Discount percentage
- rating (VARCHAR2): Product rating
- rating_count (VARCHAR2): Number of ratings/reviews
- about_product (VARCHAR2): Product description
- user_id (VARCHAR2): User ID
- user_name (VARCHAR2): User name
- review_id (VARCHAR2): Review ID
- review_title (VARCHAR2): Review title
- review_content (VARCHAR2): Review content
- img_link (VARCHAR2): Product image link
- product_link (VARCHAR2): Product page link

FORCE RULE: force_generation = {force_generation}
If force_generation is true, you MUST output status "success" with your best-effort SQL. No more questions.

DECISION RULES:
1. DEFAULT TO AMBIGUOUS first. If the user's request could mean multiple things
   (e.g. "best products" could mean highest rating OR most reviews), set "ambiguous"
   and ask ONE specific question to clarify.
2. Only set "success" if the request maps directly and unambiguously to the schema
   with no interpretation needed (e.g. "show products with rating above 4").
3. Once the history contains clarification answers, use them to generate SQL.

SQL RULES:
- Oracle syntax only. Use FETCH FIRST N ROWS ONLY, never LIMIT.
- SELECT queries only. No INSERT, UPDATE, or DELETE.
- For rating and rating_count always wrap with: TO_NUMBER(REGEXP_REPLACE(column_name, '[^0-9.]', ''))
- To extract the top-level category use: SUBSTR(category, 1, INSTR(category || '|', '|') - 1)
- No semicolon at the end of the query.

Respond ONLY with this raw JSON, no markdown, no extra text:
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
            sql = result_data.get("sql", "")
            sql = sql.strip().rstrip(";").strip()  # ← add this line
            st.session_state.ai_message = sql
        else:
            st.session_state.is_ready = False
            st.session_state.ai_message = result_data.get("follow_up_message")

    except Exception as e:
        st.session_state.is_ready = True
        st.session_state.ai_message = "SELECT * FROM amazon FETCH FIRST 20 ROWS ONLY"


# ==========================================
# HELPER FUNCTION 2: Managing the Chat Memory
# ==========================================
def manage_clarification(user_input):

    # 1. INITIALIZE — only on a brand new question
    if "current_q" not in st.session_state or st.session_state.get("original_q") != user_input:
        st.session_state.original_q = user_input
        st.session_state.current_q = user_input
        st.session_state.conversation_history = f"Initial User Query: {user_input}"
        st.session_state.follow_up_count = 0
        st.session_state.is_ready = False
        st.session_state.ai_message = None

        with st.spinner("Analyzing request..."):
            evaluate_ai_response()

    # 2. SUCCESS — return the SQL
    if st.session_state.is_ready:
        return st.session_state.ai_message

    # 3. FOLLOW-UP — ask the clarification question
    st.info(f"🤔 Follow-up ({st.session_state.follow_up_count + 1}/3): {st.session_state.ai_message}")

    user_answer = st.text_input("Your answer:", key="followup_input")

    if st.button("Submit Clarification") and user_answer:
        st.session_state.conversation_history += (
            f"\nAI Clarification Question Asked: {st.session_state.ai_message}"
            f"\nUser Clarification Answer Provided: {user_answer}"
        )
        st.session_state.follow_up_count += 1

        with st.spinner("Re-evaluating..."):
            evaluate_ai_response()

        st.rerun()

    return None


# ==========================================
# MAIN APPLICATION
# ==========================================
st.title("Natural Language Query Agent")

user_question = st.text_input("Ask a question about the Amazon sales data:")

if st.button("Run Query") or st.session_state.get("original_q") == user_question:
    if not user_question:
        st.warning("Please enter a question.")
    else:
        try:
            final_sql = manage_clarification(user_question)

            if final_sql:
                st.subheader("Generated SQL")
                st.code(final_sql, language="sql")

                validate_sql(final_sql)

                with st.spinner("Running query on Oracle Database..."):
                    result_df = run_sql(final_sql)

                st.subheader("Query Result")
                st.dataframe(result_df)

        except Exception as e:
            st.error(f"Error: {e}")
