
import json
import oci
from oci.generative_ai_inference import GenerativeAiInferenceClient
from oci.generative_ai_inference.models import OnDemandServingMode, ChatDetails, CohereChatRequest

def call_ai_inference_endpoint(prompt_payload):
    """
    Internal helper to execute the raw network invocation call to the OCI AI platform.
    """
    signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
    gen_ai_client = GenerativeAiInferenceClient(
        config={},
        signer=signer,
        service_endpoint="https://inference.generativeai.uk-london-1.oci.oraclecloud.com"
    )
    compartment_id = "ocid1.tenancy.oc1..aaaaaaaapigjcw7dwdp6onerp5wqcu3z5pzsckmokdiqjezvoodfi2corv6q"
    model_id = "cohere.command-r-plus-08-2024"

    chat_request = CohereChatRequest()
    chat_request.message = prompt_payload
    chat_request.max_tokens = 500
    chat_request.temperature = 0.0

    chat_detail = ChatDetails()
    chat_detail.compartment_id = compartment_id
    chat_detail.serving_mode = OnDemandServingMode(model_id=model_id)
    chat_detail.chat_request = chat_request

    response = gen_ai_client.chat(chat_detail)
    raw_text = response.data.chat_response.text.strip()
    
    # Clean formatting strings
    raw_text = raw_text.replace("```json", "").replace("```", "").strip()
    raw_text = raw_text.replace("\n", " ").replace("\r", " ")
    return raw_text


def run_conversational_loop():
    print("\n--- Starting Natural Language Query Loop ---")
    initial_prompt = input("Enter your initial database query: ")
    
    # Initialize history tracking
    conversation_history = f"Initial User Query: {initial_prompt}"
    loop_active = True
    
    # --- FIX 2: HARD CAP TURN COUNTER ---
    follow_up_count = 0  

    while loop_active:
        # Check if we need to force the AI to wrap it up
        force_generation = "false"
        if follow_up_count >= 3:
            force_generation = "true"

        # SYSTEM PROMPT STAYS STATIC - history updates dynamically
        prompt payload = f"""
        You are an expert Oracle SQL architect and natural language classifier.
        
        Your task is to analyze the user's inquiry stream. You must determine if the total context accumulated across the conversation history is specific enough to build a definitive Oracle SQL query.
        
        CRITICAL RULE 1: Look at the conversation history carefully. Do not repeat questions that the user has already answered! Read their previous responses to build your context.
        
        CRITICAL RULE 2: You MUST ONLY use the exact table name and columns provided in the schema definition below. Do NOT hallucinate table names like 'AMAZON_SALES' or column names like 'SALES'. 
        
        CRITICAL RULE 3: If the user asks for "total sales", "number of sales", or "sales volume", treat EVERY SINGLE ROW in the table as a separate sale. Therefore, calculate total sales using COUNT(*) from the 'amazon' table.

        Database Schema (USE ONLY THESE):
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
        1. If context is missing clear metrics, set "status": "ambiguous" and provide a NEW, explicit follow-up question in "follow_up_message". Leave "sql" as null.
        2. If specific enough, set "status": "success", "follow_up_message": null, and generate the valid Oracle SQL string in "sql".
        
        SQL Generation Rules:
        - Use Oracle SQL syntax. FETCH FIRST N ROWS ONLY instead of LIMIT.
        - Generate SELECT queries only. No destructive commands.
        - Always use TO_NUMBER(REGEXP_REPLACE(column_name, '[^0-9.]', '')) when filtering or sorting numeric columns like 'rating' and 'rating_count'.
        
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
        try:
            raw_response = call_ai_inference_endpoint(prompt_payload)
            result_data = json.loads(raw_response, strict=False)
            
            if result_data.get("status") == "success" or force_generation == "true":
                print("\n🎉 Success! SQL generated natively.")
                print(f"Generated SQL: {result_data.get('sql')}\n")
                
                conversation_history += f"\nFinal Generated SQL Statement: {result_data.get('sql')}"
                loop_active = False
                return True, conversation_history
                
            else:
                # Increment the follow-up tracker
                follow_up_count += 1
                
                print(f"\n🤖 Follow-up Question from AI ({follow_up_count}/3): {result_data.get('follow_up_message')}")
                user_clarification = input("Your response: ")
                
                # Append the new conversation slice to the ongoing history string block
                conversation_history += f"\nAI Clarification Question Asked: {result_data.get('follow_up_message')}\nUser Clarification Answer Provided: {user_clarification}"
                
        except Exception as e:
            print(f"\n⚠️ Structural Parsing Exception hit: {e}. Defaulting emergency crash exit.")
            return True, conversation_history

if __name__ == "__main__":
    run_conversational_loop()
