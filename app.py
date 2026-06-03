import streamlit as st
import json
# We only import the raw network caller from the backend's new file
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
    This recreates the backend team's new prompt logic, including the 
    hard cap counter and the conversation history tracker.
    """
    # Check if we hit the limit of 3 follow-ups
    force_generation = "true" if st.session_state.follow_up_count >= 3 else "false"
    
    # prompt_payload = f"""
    # You are an expert Oracle SQL architect and natural language classifier.
    
    # Your task is to analyze the user's inquiry stream. You must determine if the total context accumulated across the conversation history is specific enough to build a definitive Oracle SQL query.
    
    # CRITICAL RULE: Look at the conversation history carefully. Do not repeat questions that the user has already answered! Read their previous responses to build your context.

    # Database Schema:
    # Table name: amazon
    # Columns:
    # - product_id (VARCHAR2): Product ID
    # - product_name (VARCHAR2): Product name
    # - category (VARCHAR2): Product category
    # - discounted_price (VARCHAR2): Discounted price
    # - actual_price (VARCHAR2): Original price
    # - discount_percentage (VARCHAR2): Discount percentage
    # - rating (VARCHAR2): Product rating
    # - rating_count (VARCHAR2): Number of ratings/reviews
    # - about_product (VARCHAR2): Product description
    # - user_id (VARCHAR2): User ID
    # - user_name (VARCHAR2): User name
    # - review_id (VARCHAR2): Review ID
    # - review_title (VARCHAR2): Review title
    # - review_content (VARCHAR2): Review content
    # - img_link (VARCHAR2): Product image link
    # - product_link (VARCHAR2): Product page link

    # HARD GRADUATION RULE:
    # Is force_generation equal to true? [Value: {force_generation}]
    # If force_generation is true, you MUST set "status": "success" and output your absolute best guess SELECT query using the columns available. Do not ask any more questions.
    
    # Rules for Classification (If force_generation is false):
    # 1. If context is missing clear metrics, set "status": "ambiguous" and provide a NEW, explicit follow-up question in "follow_up_message". Leave "sql" as null.
    # 2. If specific enough, set "status": "success", "follow_up_message": null, and generate the valid Oracle SQL string in "sql".
    
    # SQL Generation Rules:
    # - Use Oracle SQL syntax. FETCH FIRST N ROWS ONLY instead of LIMIT.
    # - Generate SELECT queries only. No destructive commands.
    # - Always use TO_NUMBER(REGEXP_REPLACE(column_name, '[^0-9.]', '')) when filtering or sorting numeric columns like 'rating' and 'rating_count'.
    
    # You MUST respond with a raw JSON object matching this structure exactly:
    # {{
    #     "status": "success" or "ambiguous",
    #     "follow_up_message": "Clarification question text here if ambiguous, otherwise null",
    #     "sql": "The generated SQL query here if success, otherwise null"
    # }}

    # Note: Dont add ; at the end of the SQL Query.
    
    # [CONVERSATION HISTORY TRACKER]
    # {conversation_history if "conversation_history" in locals() else ""}
    
    # Output:
    # """
     prompt_payload = f"""
        You are an expert Oracle SQL generator.
        
        Your task is to translate the user's natural language question into a valid Oracle SQL query.
        
        Use ONLY the table and columns listed in the schema.
        
    
        Database Schema:
        Table name: amazon
        Columns:
        - product_id (VARCHAR2): Product ID
        - product_name (VARCHAR2): Product name
        - category (VARCHAR2): Product category
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
            
        Rules:
        - Return ONLY the SQL query.
        - Do not include explanations.
        - Do not include markdown.
        - Use Oracle SQL syntax.
        - Use FETCH FIRST N ROWS ONLY instead of LIMIT.
        - Generate SELECT queries only.
        - IMPORTANT FOR NUMBERS: Columns like 'rating' and 'rating_count' may be stored as VARCHAR2. 
          Always use TO_NUMBER(REGEXP_REPLACE(column_name, '[^0-9.]', '')) when filtering or sorting numeric calculations to safely handle formatting characters like commas or spaces.
        
        Example:
        User Query:
        Retrieve product names where the evaluation count is over 1000.
        
        SQL Output:
        SELECT product_name 
        FROM AMAZON 
        WHERE TO_NUMBER(REGEXP_REPLACE(rating_count, '[^0-9.]', '')) > 1000
        ORDER BY TO_NUMBER(REGEXP_REPLACE(rating, '[^0-9.]', '')) DESC
        FETCH FIRST 5 ROWS ONLY
        
        Real Task:
        User Query:
        {user_question}
        
        SQL Output:
        """
  
    
    try:
        # Call the backend team's OCI function
        raw_response = call_ai_inference_endpoint(prompt_payload)
        result_data = json.loads(raw_response, strict=False)
        
        if result_data.get("status") == "success" or force_generation == "true":
            st.session_state.is_ready = True
            st.session_state.ai_message = result_data.get('sql')
        else:
            st.session_state.is_ready = False
            st.session_state.ai_message = result_data.get('follow_up_message')
            
    except Exception as e:
        # Crash fallback
        st.session_state.is_ready = True
        st.session_state.ai_message = f"SELECT * FROM amazon FETCH FIRST 10 ROWS ONLY; -- Fallback Error: {e}"

# ==========================================
# HELPER FUNCTION 2: Managing the Chat Memory
# ==========================================
def manage_clarification(user_input):
    
    # 1. INITIALIZE MEMORY (Now including the backend team's new trackers)
    if "current_q" not in st.session_state or st.session_state.get("original_q") != user_input:
        st.session_state.original_q = user_input
        st.session_state.current_q = user_input
        
        # Setup the conversation history and turn counter!
        st.session_state.conversation_history = f"Initial User Query: {user_input}"
        st.session_state.follow_up_count = 0
        
        with st.spinner("Analyzing request..."):
            evaluate_ai_response()

    # 2. SUCCESS SCENARIO
    if st.session_state.is_ready:
        return st.session_state.ai_message 

    # 3. FOLLOW-UP SCENARIO
    # We display the turn counter so the user knows they only have 3 tries
    st.info(f"🤔 Follow-up ({st.session_state.follow_up_count + 1}/3): {st.session_state.ai_message}")
    
    user_answer = st.text_input("Your answer:", key="followup_input")
    
    if st.button("Submit Clarification") and user_answer:
        # Append the new slice to the history string block exactly like the backend did
        st.session_state.conversation_history += f"\nAI Clarification Question Asked: {st.session_state.ai_message}\nUser Clarification Answer Provided: {user_answer}"
        
        # Increase the counter
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
            # 1. The simple function call handles everything (History + Counting + API)
            final_sql = manage_clarification(user_question)

            # 2. Only proceed to OCI if the function successfully returned the SQL
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
