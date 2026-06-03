# def generate_sql(user_question, schema_text):
#     return user_question


# import oci
# from oci.generative_ai_inference import GenerativeAiInferenceClient
# from oci.generative_ai_inference.models import OnDemandServingMode, ChatDetails, CohereChatRequest
# import json

# # 1. Setup the secure instance identification token
# signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()

# # 2. Configure the AI client using the dynamic server signer
# gen_ai_client = GenerativeAiInferenceClient(
#     config={},
#     signer=signer,
#     service_endpoint="https://inference.generativeai.uk-london-1.oci.oraclecloud.com"
# )

# # 3. Setup your structural compartment routing IDs
# compartment_id = "ocid1.tenancy.oc1..aaaaaaaapigjcw7dwdp6onerp5wqcu3z5pzsckmokdiqjezvoodfi2corv6q"
# model_id = "cohere.command-r-plus-08-2024"

# def generate_sql(user_question, schema_text):
#     prompt = f"""
#     You are an expert Oracle SQL generator.
    
#     Your task is to translate the user's natural language question into a valid Oracle SQL query.
    
#     Use ONLY the table and columns listed in the schema.
    

#     Database Schema:
#     Table name: amazon
#     Columns:
#     - product_id (VARCHAR2): Product ID
#     - product_name (VARCHAR2): Product name
#     - category (VARCHAR2): Product category
#     - discounted_price (VARCHAR2): Discounted price
#     - actual_price (VARCHAR2): Original price
#     - discount_percentage (VARCHAR2): Discount percentage
#     - rating (VARCHAR2): Product rating
#     - rating_count (VARCHAR2): Number of ratings/reviews
#     - about_product (VARCHAR2): Product description
#     - user_id (VARCHAR2): User ID
#     - user_name (VARCHAR2): User name
#     - review_id (VARCHAR2): Review ID
#     - review_title (VARCHAR2): Review title
#     - review_content (VARCHAR2): Review content
#     - img_link (VARCHAR2): Product image link
#     - product_link (VARCHAR2): Product page link
        
#     Rules:
#     - Return ONLY the SQL query.
#     - Do not include explanations.
#     - Do not include markdown.
#     - Use Oracle SQL syntax.
#     - Use FETCH FIRST N ROWS ONLY instead of LIMIT.
#     - Generate SELECT queries only.
#     - IMPORTANT FOR NUMBERS: Columns like 'rating' and 'rating_count' may be stored as VARCHAR2. 
#       Always use TO_NUMBER(REGEXP_REPLACE(column_name, '[^0-9.]', '')) when filtering or sorting numeric calculations to safely handle formatting characters like commas or spaces.
    
#     Example:
#     User Query:
#     Retrieve product names where the evaluation count is over 1000.
    
#     SQL Output:
#     SELECT product_name 
#     FROM AMAZON 
#     WHERE TO_NUMBER(REGEXP_REPLACE(rating_count, '[^0-9.]', '')) > 1000
#     ORDER BY TO_NUMBER(REGEXP_REPLACE(rating, '[^0-9.]', '')) DESC
#     FETCH FIRST 5 ROWS ONLY
    
#     Real Task:
#     User Query:
#     {user_question}
    
#     SQL Output:
#     """

#     chat_request = CohereChatRequest()
#     chat_request.message = prompt
#     chat_request.max_tokens = 300
#     chat_request.temperature = 0.0

#     chat_detail = ChatDetails()
#     chat_detail.compartment_id = compartment_id
#     chat_detail.serving_mode = OnDemandServingMode(model_id=model_id)
#     chat_detail.chat_request = chat_request

#     response = gen_ai_client.chat(chat_detail)

#     sql = response.data.chat_response.text.strip()
#     sql = sql.replace("```sql", "").replace("```", "").replace(";", "").strip()
#     return sql

# def process_interactive_query(user_question):
    
#     Sends the user prompt to OCI Generative AI.
#     Returns:
#         status (bool): True if specific (success), False if too general (ambiguous)
#         output (str): The SQL query string OR the follow-up question string
#     """
#     # 1. Establish secure cloud compute server identity tokens
#     signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()

#     # 2. Spin up the dedicated OCI Inference client interface engine
#     gen_ai_client = GenerativeAiInferenceClient(
#         config={},
#         signer=signer,
#         service_endpoint="https://inference.generativeai.uk-london-1.oci.oraclecloud.com"
#     )

#     # 3. Setup global tenancy environment variables
#     compartment_id = "ocid1.tenancy.oc1..aaaaaaaapigjcw7dwdp6onerp5wqcu3z5pzsckmokdiqjezvoodfi2corv6q"
#     model_id = "cohere.command-r-plus-08-2024"

#     # 4. Construct the structured evaluation system prompt template instructions
#     prompt = f"""
#     You are an expert Oracle SQL architect and natural language classifier.
    
#     Your task is to analyze the user's natural language question. You must determine if the question is specific enough to build a definitive Oracle SQL query, or if it is too general/ambiguous (e.g., asking for "sales" or "best items" without specifying if they mean revenue metrics, item units sold, or review counts).
    
#     Database Schema available for use:
#     Table name: amazon
#     Columns:
#     - product_id (VARCHAR2): Product ID
#     - product_name (VARCHAR2): Product name
#     - category (VARCHAR2): Product category
#     - discounted_price (VARCHAR2): Discounted price
#     - actual_price (VARCHAR2): Original price
#     - discount_percentage (VARCHAR2): Discount percentage
#     - rating (VARCHAR2): Product rating
#     - rating_count (VARCHAR2): Number of ratings/reviews
#     - about_product (VARCHAR2): Product description
#     - user_id (VARCHAR2): User ID
#     - user_name (VARCHAR2): User name
#     - review_id (VARCHAR2): Review ID
#     - review_title (VARCHAR2): Review title
#     - review_content (VARCHAR2): Review content
#     - img_link (VARCHAR2): Product image link
#     - product_link (VARCHAR2): Product page link
    
#     Rules for Classification:
#     1. If the prompt is too general or missing clear numeric criteria, set "status": "ambiguous" and provide a helpful, explicit follow-up question in "follow_up_message" asking for clarification. Leave "sql" as null.
#     2. If the prompt is specific enough to map to the schema columns directly, set "status": "success", "follow_up_message": null, and generate the valid Oracle SQL string in "sql".
    
#     SQL Generation Rules (Only if status is success):
#     - Use Oracle SQL syntax.
#     - Use FETCH FIRST N ROWS ONLY instead of LIMIT.
#     - Generate SELECT queries only. No destructive commands.
#     - Columns like 'rating' and 'rating_count' may be stored as VARCHAR2. Always use TO_NUMBER(REGEXP_REPLACE(column_name, '[^0-9.]', '')) when filtering or sorting.
    
#     You MUST respond with a raw JSON object matching this structure exactly. Do not include markdown wraps like ```json:
#     {{
#         "status": "success" or "ambiguous",
#         "follow_up_message": "Clarification question text here if ambiguous, otherwise null",
#         "sql": "The generated SQL query here if success, otherwise null"
#     }}
    
#     Example 1 (Ambiguous):
#     User Query: What were the top items last year?
#     Output:
#     {{
#         "status": "ambiguous",
#         "follow_up_message": "Your request is a bit general. Would you like to rank those top items by their average customer rating, or by their total review activity count?",
#         "sql": null
#     }}
    
#     Example 2 (Specific):
#     User Query: Find product names with a rating over 4.5
#     Output:
#     {{
#         "success",
#         "follow_up_message": null,
#         "sql": "SELECT product_name FROM amazon WHERE TO_NUMBER(REGEXP_REPLACE(rating, '[^0-9.]', '')) > 4.5"
#     }}
    
#     Real Task:
#     User Query: {user_question}
#     Output:
#     """

#     # 5. Package the prompt instructions into Cohere payload configuration structures
#     chat_request = CohereChatRequest()
#     chat_request.message = prompt
#     chat_request.max_tokens = 400
#     chat_request.temperature = 0.0

#     chat_detail = ChatDetails()
#     chat_detail.compartment_id = compartment_id
#     chat_detail.serving_mode = OnDemandServingMode(model_id=model_id)
#     chat_detail.chat_request = chat_request

#     # 6. Execute network invocation call to the AI Endpoint
#     response = gen_ai_client.chat(chat_detail)
#     raw_text = response.data.chat_response.text.strip()
    
#     # 7. Strip out potential diagnostic markdown annotations
#     raw_text = raw_text.replace("```json", "").replace("```", "").strip()
    
#     # 8. Parse the JSON and map it to boolean True/False outputs
#     try:
#         result_data = json.loads(raw_text)
        
#         if result_data.get("status") == "success":
#             # Status is specific (True), return the raw SQL string
#             return True, str(result_data.get("sql", "")).replace(";", "").strip()
#         else:
#             # Status is ambiguous (False), return the clarification question string
#             return False, str(result_data.get("follow_up_message", ""))
            
#     except Exception as e:
#         # Crash fallback: assume success and return whatever raw string text came back
#         return True, str(raw_text).replace(";", "").strip()
# '''


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
