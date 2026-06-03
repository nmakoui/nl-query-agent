# def generate_sql(user_question, schema_text):
#     return user_question


import oci
from oci.generative_ai_inference import GenerativeAiInferenceClient
from oci.generative_ai_inference.models import OnDemandServingMode, ChatDetails, CohereChatRequest

# 1. Setup the secure instance identification token
signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()

# 2. Configure the AI client using the dynamic server signer
gen_ai_client = GenerativeAiInferenceClient(
    config={},
    signer=signer,
    service_endpoint="https://inference.generativeai.uk-london-1.oci.oraclecloud.com"
)

# 3. Setup your structural compartment routing IDs
compartment_id = "ocid1.tenancy.oc1..aaaaaaaapigjcw7dwdp6onerp5wqcu3z5pzsckmokdiqjezvoodfi2corv6q"
model_id = "cohere.command-r-plus-08-2024"

def generate_sql(user_question, schema_text):
    prompt = f"""
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
    - Do not generate INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, MERGE, GRANT, or REVOKE statements.
    
    Example:
    User Query:
    Retrieve the IDs and names of the top 3 products with the highest rating.
    
    SQL Output:
    SELECT product_id, product_name
    FROM AMAZON
    ORDER BY rating DESC
    FETCH FIRST 3 ROWS ONLY
    
    Real Task:
    User Query:
    {user_question}
    
    SQL Output:
    """

    chat_request = CohereChatRequest()
    chat_request.message = prompt
    chat_request.max_tokens = 300
    chat_request.temperature = 0.0

    chat_detail = ChatDetails()
    chat_detail.compartment_id = compartment_id
    chat_detail.serving_mode = OnDemandServingMode(model_id=model_id)
    chat_detail.chat_request = chat_request

    response = gen_ai_client.chat(chat_detail)

    sql = response.data.chat_response.text.strip()
    sql = sql.replace("```sql", "").replace("```", "").replace(";", "").strip()
    return sql
