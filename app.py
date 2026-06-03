import streamlit as st
#from ai_sql_generator import generate_sql
#from validator import validate_sql
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

st.title("Natural Language Query Agent")

user_question = st.text_input("Ask a question about the Amazon sales data:")

if st.button("Run Query"):
    if not user_question:
        st.warning("Please enter a question.")
    else:
        try:
            with st.spinner("Generating SQL..."):
                #sql = generate_sql(user_question, SCHEMA_TEXT)
            st.subheader("Generated SQL")
            #st.code(sql, language="sql")
            #validate_sql(sql)
            with st.spinner("Running query on Oracle Database..."):
                result_df = run_sql()
            st.subheader("Query Result")
            st.dataframe(result_df)
        except Exception as e:
            st.error(f"Error: {e}")      
