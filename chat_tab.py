"""
This module implements a conversational chat interface for the QueryLens application.

The chat is designed to behave like a multi‑turn data assistant. It keeps track of
the ongoing dialogue so that follow‑up questions can reference the context of
previous questions and answers. When the user asks a question, the assistant
generates a SQL query (or asks a clarifying question) based on the entire
conversation history. Once a valid SQL query is produced, it executes the query
against the Oracle database, displays the results, and provides a plain‑English
explanation of the SQL statement.

Usage:
    In your Streamlit app, import `render_chat_tab` and call it within a tab
    container. The chat state will persist across reruns thanks to Streamlit's
    session_state.
"""

import json
from typing import Optional

import streamlit as st

from ai_sql_generator import call_ai_inference_endpoint
from validator import validate_sql
from db import run_sql
from sql_explanation import sql_explanation


def _evaluate_chat_response(conversation_history: str, follow_up_count: int) -> dict:
    """
    Given the accumulated conversation history and the number of prior follow‑up
    questions, decide whether the user's request is specific enough to generate
    SQL or if more clarification is needed.

    A JSON‑like dictionary is returned with keys:
        status: "success" or "ambiguous"
        follow_up_message: a clarification question if ambiguous, otherwise None
        sql: the generated SQL when status is success, otherwise None

    The function uses the same core instructions as the rest of the application
    but tailored to our chat context. When the follow‑up count reaches three
    rounds, the assistant is forced to produce its best guess.
    """
    # Determine if we need to force SQL generation after repeated clarifications
    force_generation = "true" if follow_up_count >= 3 else "false"

    prompt_payload = f"""
You are an expert Oracle SQL architect and natural language classifier.

Your task is to analyze the user's inquiry stream. You must determine if the total context
accumulated across the conversation history is specific enough to build a definitive
Oracle SQL query.

CRITICAL RULE: Look at the conversation history carefully. Do not repeat questions that
the user has already answered! Read their previous responses to build your context.
CRITICAL RULE: Do not add ; at the end of the generated SQL code

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

HARD GRADUATION RULE:
Is force_generation equal to true? [Value: {force_generation}]
If force_generation is true, you MUST set "status": "success" and output your absolute best guess SELECT query using the columns available. Do not ask any more questions.

Rules for Classification (If force_generation is false):
1. If context is missing clear metrics, set "status": "ambiguous" and provide a NEW, explicit follow‑up question in "follow_up_message". Leave "sql" as null.
2. If specific enough, set "status": "success", "follow_up_message": null, and generate the valid Oracle SQL string in "sql".

SQL Generation Rules:
- Use Oracle SQL syntax. FETCH FIRST N ROWS ONLY instead of LIMIT.
- Generate SELECT queries only. No destructive commands.
- Always use TO_NUMBER(REGEXP_REPLACE(column_name, '[^0-9.]', '')) when filtering or sorting numeric columns like 'rating' and 'rating_count'.
- To extract top‑level category use: SUBSTR(category, 1, INSTR(category || '|', '|') - 1)
- Do not include a semicolon at the end of the query.

You MUST respond with a raw JSON object matching this structure exactly:
{{
    "status": "success" or "ambiguous",
    "follow_up_message": "Clarification question text here if ambiguous, otherwise null",
    "sql": "The generated SQL query here if success, otherwise null"
}}

[CONVERSATION HISTORY TRACKER]
{conversation_history}

Output:
"""
    # Invoke the AI inference endpoint
    raw_response = call_ai_inference_endpoint(prompt_payload)
    # Clean potential formatting
    raw_response = raw_response.replace("```json", "").replace("```", "").strip()
    # Attempt to parse into JSON; fall back to best effort if parsing fails
    try:
        result = json.loads(raw_response, strict=False)
    except Exception:
        # When parsing fails, assume success and put the raw response into the sql field
        result = {
            "status": "success",
            "follow_up_message": None,
            "sql": raw_response.strip().rstrip(";").strip(),
        }
    # Normalize keys in case the AI returns slightly different casing
    status = result.get("status") or result.get("Status") or "success"
    follow_up_msg = result.get("follow_up_message") or result.get("followUpMessage") or None
    sql = result.get("sql") or result.get("SQL") or None
    return {"status": status, "follow_up_message": follow_up_msg, "sql": sql}


def render_chat_tab() -> None:
    """
    Render a conversational chat interface within a Streamlit tab.

    The UI allows the user to type in natural language queries about the Amazon
    sales data. The assistant either asks a clarifying question or produces a
    SQL query, executes it, and displays the results. Conversation context is
    preserved across turns so the user can ask follow‑up questions without
    restating all criteria.
    """
    st.header("💬 Conversational Query Assistant")
    # Show a short description below the header. Use a single literal string
    # so Python does not misinterpret the newline as an end of line.
    st.caption(
        "Ask questions about the Amazon dataset in plain English. You can refine your search "
        "with follow‑up questions, and the assistant will remember the context."
    )

    # Show a collapsible list of past queries from the main QueryLens interface. This
    # gives the conversational assistant access to the broader question history
    # outside of the chat context. Users can expand this section to review
    # previous questions they asked through the non‑chat interface.
    main_history = st.session_state.get("history", [])
    if main_history:
        with st.expander("Previous Queries", expanded=False):
            for item in main_history:
                q = item.get("question", "").strip()
                if q:
                    st.markdown(f"- {q}")

    # Initialize session state variables for the chat
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []  # list of dicts with keys: role ('user'/'assistant'), content
    if "chat_conversation_history" not in st.session_state:
        st.session_state.chat_conversation_history = ""
    if "chat_follow_up_count" not in st.session_state:
        st.session_state.chat_follow_up_count = 0
    if "chat_waiting_clarification" not in st.session_state:
        st.session_state.chat_waiting_clarification = False
    if "chat_last_sql" not in st.session_state:
        st.session_state.chat_last_sql = None

    # Display existing chat history
    for idx, msg in enumerate(st.session_state.chat_messages):
        role = msg.get("role", "assistant")
        content = msg.get("content", "")
        with st.chat_message(role):
            if isinstance(content, dict):
                # Complex content (results + explanation)
                sql_text = content.get("sql", "")
                result_df = content.get("dataframe")
                explanation = content.get("explanation")
                # Show the SQL query
                if sql_text:
                    st.markdown(f"**Generated SQL:**\n\n```sql\n{sql_text}\n```")
                # Show the result DataFrame if available
                if result_df is not None:
                    st.dataframe(result_df, use_container_width=True)
                # Show the natural language explanation
                if explanation:
                    st.markdown("---")
                    st.markdown("**Explanation**")
                    st.markdown(explanation)
            else:
                # Plain string content
                st.markdown(content)

    # Accept user input from chat_input
    user_input: Optional[str] = st.chat_input("Type your question and press Enter…")
    if user_input:
        # Record the user's message
        st.session_state.chat_messages.append({"role": "user", "content": user_input})

        # Determine if this is an answer to a clarification or a new/follow‑up question
        if st.session_state.chat_waiting_clarification:
            # Append the clarification answer to the conversation history
            last_ai_question = st.session_state.chat_messages[-2]["content"] if len(st.session_state.chat_messages) >= 2 else ""
            st.session_state.chat_conversation_history += (
                f"\nAI Clarification Question Asked: {last_ai_question}\nUser Clarification Answer Provided: {user_input}"
            )
            st.session_state.chat_follow_up_count += 1
            st.session_state.chat_waiting_clarification = False
        else:
            # Either start a new conversation or continue an existing one
            if not st.session_state.chat_conversation_history:
                st.session_state.chat_conversation_history = f"Initial User Query: {user_input}"
            else:
                st.session_state.chat_conversation_history += f"\nFollow‑up User Query: {user_input}"
            # Reset follow‑up count for new queries
            st.session_state.chat_follow_up_count = 0

        # Evaluate the conversation state via the AI endpoint
        with st.spinner("Analyzing your request…"):
            # Build a context string that includes past queries from the main
            # interface along with the current chat conversation history. This
            # allows the assistant to incorporate broader context when
            # generating SQL or clarifications.
            history_context = ""
            main_history = st.session_state.get("history", [])
            if main_history:
                history_context += "Past User Queries:\n"
                for item in main_history:
                    q = item.get("question", "").strip()
                    if q:
                        history_context += f"- {q}\n"
            conversation_input = history_context + st.session_state.chat_conversation_history
            ai_result = _evaluate_chat_response(
                conversation_history=conversation_input,
                follow_up_count=st.session_state.chat_follow_up_count,
            )

        status = (ai_result.get("status") or "success").lower()
        follow_up_msg = ai_result.get("follow_up_message") or None
        sql_query = ai_result.get("sql") or None

        if status == "ambiguous" and follow_up_msg:
            # The AI needs more information; ask the user a clarifying question
            st.session_state.chat_waiting_clarification = True
            st.session_state.chat_messages.append({"role": "assistant", "content": follow_up_msg.strip()})
        else:
            # Success: we have a SQL query (or we were forced to produce one)
            final_sql = (sql_query or "").strip().rstrip(";").strip()
            # Update conversation history with the generated SQL
            st.session_state.chat_conversation_history += f"\nFinal Generated SQL Statement: {final_sql}"
            st.session_state.chat_last_sql = final_sql

            # Attempt to validate and execute the SQL query
            try:
                validate_sql(final_sql)
                result_df = run_sql(final_sql)
                error = None
            except Exception as e:
                result_df = None
                error = str(e)

            # Build assistant message content
            assistant_content: dict
            if error:
                assistant_content = {"sql": final_sql, "dataframe": None, "explanation": f"Execution error: {error}"}
            else:
                explanation = sql_explanation(final_sql)
                assistant_content = {"sql": final_sql, "dataframe": result_df, "explanation": explanation}
            # Append assistant message
            st.session_state.chat_messages.append({"role": "assistant", "content": assistant_content})
            # Reset follow‑up count after successful execution for subsequent follow‑up questions
            st.session_state.chat_follow_up_count = 0

        # Rerun to display the new messages
        st.rerun()
