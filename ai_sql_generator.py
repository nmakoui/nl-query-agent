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
    
    conversation_history = f"Initial User Query: {initial_prompt}"
    loop_active = True
    follow_up_count = 0  

    while loop_active:
        force_generation = "false"
        if follow_up_count >= 3:
            force_generation = "true"

        prompt_payload = f"""
        You are an expert Oracle SQL architect and natural language classifier.
        
        Your task is to analyze the user's inquiry stream. You must determine if the total context accumulated across the conversation history is specific enough to build a definitive Oracle SQL query.

        
        Database Schema:
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

        HARD GRADUATION RULE:
        Is force_generation equal to true? [Value: {force_generation}]
        If force_generation is true, you MUST set "status": "success" and output your absolute best guess SELECT query using the columns available.
        
        Rules for Classification (If force_generation is false):
        1. If context is missing clear metrics, set "status": "ambiguous" and provide a follow-up question in "follow_up_message". Leave "sql" as null.
        2. If specific enough, set "status": "success", "follow_up_message": null, and generate the valid Oracle SQL string in "sql".
        
        SQL Generation Rules:
        - Use Oracle SQL syntax. FETCH FIRST N ROWS ONLY instead of LIMIT.
        - Always use TO_NUMBER(REGEXP_REPLACE(column_name, '[^0-9.]', '')) when filtering or sorting numeric columns.
        
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
            
            # --- THE HALLUCINATION RADAR ---
            # If the AI hallucinated a bad table or column, we INTERCEPT IT right here 
            # and automatically correct it before your interface or terminal crashes.
            # if result_data.get("sql"):
            #     sql_str = result_data["sql"].upper()
            #     if "FROM AMAZON_SALES" in sql_str:
            #         result_data["sql"] = result_data["sql"].replace("AMAZON_SALES", "amazon").replace("amazon_sales", "amazon")
            #     if "SUM(SALES)" in sql_str or "COUNT(SALES)" in sql_str:
            #         result_data["sql"] = "SELECT COUNT(*) AS total_sales FROM amazon"
            
            if result_data.get("status") == "success" or force_generation == "true":
                print("\n🎉 Success! SQL generated natively.")
                print(f"Generated SQL: {result_data.get('sql')}\n")
                
                conversation_history += f"\nFinal Generated SQL Statement: {result_data.get('sql')}"
                loop_active = False
                return True, conversation_history
                
            else:
                follow_up_count += 1
                print(f"\n🤖 Follow-up Question from AI ({follow_up_count}/3): {result_data.get('follow_up_message')}")
                user_clarification = input("Your response: ")
                conversation_history += f"\nAI Clarification Question Asked: {result_data.get('follow_up_message')}\nUser Clarification Answer Provided: {user_clarification}"
                
        except Exception as e:
            print(f"\n⚠️ Structural Parsing Exception hit: {e}. Defaulting emergency crash exit.")
            return True, conversation_history

if __name__ == "__main__":
    run_conversational_loop()
