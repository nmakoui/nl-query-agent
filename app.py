import streamlit as st
from ai_sql_generator import generate_sql, check_query_sufficient
from validator import validate_sql
from db import run_sql

SCHEMA_TEXT = """
Table: AMAZON_SALES
Columns:
- ORDER_ID
- ORDER_DATE
- SHIP_DATE
- REGION
- COUNTRY
- CITY
- CATEGORY
- PRODUCT_NAME
- SALES
- QUANTITY
- PROFIT
- DISCOUNT
"""

def clarification_loop(user_question: str, schema: str) -> str:
    current_question = user_question

    while True:
        is_sufficient, followup = check_query_sufficient(current_question, schema)
        
        if is_sufficient:
            break
        
        st.info(f"🤔 Follow-up: {followup}")
        user_answer = st.text_input("Your answer:", key=f"followup_{len(current_question)}")
        
        if not user_answer:
            st.stop()
        
        current_question = f"{current_question}. {user_answer}"

    return current_question


st.title("Natural Language Query Agent")

user_question = st.text_input("Ask a question about the Amazon sales data:")

if st.button("Run Query"):
    if not user_question:
        st.warning("Please enter a question.")
    else:
        try:
            final_question = clarification_loop(user_question, SCHEMA_TEXT)

            with st.spinner("Generating SQL..."):
                sql = generate_sql(final_question, SCHEMA_TEXT)
            st.subheader("Generated SQL")
            st.code(sql, language="sql")
            validate_sql(sql)
            with st.spinner("Running query on Oracle Database..."):
                result_df = run_sql(sql)
            st.subheader("Query Result")
            st.dataframe(result_df)
        except Exception as e:
            st.error(f"Error: {e}")
