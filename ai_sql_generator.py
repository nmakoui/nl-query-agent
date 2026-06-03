# def generate_sql(user_question, schema_text):
#     return user_question


import oci
from oci.generative_ai_inference import GenerativeAiInferenceClient
from oci.generative_ai_inference.models import OnDemandServingMode, ChatDetails, CohereChatRequest

config = oci.config.from_file("~/.oci/config", "DEFAULT")

gen_ai_client = GenerativeAiInferenceClient(
    config=config,
    service_endpoint="https://inference.generativeai.uk-london-1.oci.oraclecloud.com"
)

compartment_id = "ocid1.tenancy.oc1..aaaaaaaapigjcw7dwdp6onerp5wqcu3z5pzsckmokdiqjezvoodfi2corv6q"
model_id = "cohere.command-r-plus-08-2024"

def generate_sql(user_question, schema_text):
    prompt = f"""
    You are an expert Oracle SQL generator.
    
    Your task is to translate the user's natural language question into a valid Oracle SQL query.
    
    Use ONLY the table and columns listed in the schema.
    
    Database Schema:
    {schema_text}
    
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
    Retrieve the IDs and names of the top 3 products with the highest discount percentages.
    
    SQL Output:
    SELECT product_id, product_name
    FROM AMAZON_SALES
    ORDER BY discount_percentage DESC
    FETCH FIRST 3 ROWS ONLY;
    
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
    sql = sql.replace("```sql", "").replace("```", "").strip()

    return sql
