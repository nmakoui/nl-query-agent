import json
import oci
import oracledb  # Ensure you are using the modern oracle driver

# 1. Initialize OCI Generative AI client to get embeddings
signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
gen_ai_client = oci.generative_ai_inference.GenerativeAiInferenceClient(
    config={}, signer=signer, service_endpoint="https://inference.generativeai.uk-london-1.oci.oraclecloud.com"
)

# Connect to your Autonomous DB
conn = oracledb.connect(user="ADMIN", password="YourDBPassword", dsn="your_db_dsn")
cursor = conn.cursor()

# Fetch your existing inventory rows
cursor.execute("SELECT product_id, product_name, about_product FROM AMAZON")
rows = cursor.fetchall()

print("Generating embeddings and syncing vector column...")
for row in rows:
    prod_id, prod_name, about_prod = row
    
    # Clean and bundle the text data to create the payload context
    combined_text = f"{prod_name} {str(about_prod)[:400]}"
    
    # Call OCI Cohere Embedding v3 Model
    embed_request = oci.generative_ai_inference.models.EmbedTextDetails(
        inputs=[combined_text],
        serving_mode=oci.generative_ai_inference.models.OnDemandServingMode(model_id="cohere.embed-english-v3.0"),
        compartment_id="your_oci_compartment_ocid",
        input_type="SEARCH_DOCUMENT"
    )
    
    embed_response = gen_ai_client.embed_text(embed_request)
    
    # Extract the raw float array list: [0.012, -0.421, 0.984, ...]
    vector_array = embed_response.data.embeddings[0]
    
    # Turn the float list into a single stringified JSON array block
    json_vector_string = json.dumps(vector_array)
    
    # Push the array string directly into your new CLOB column
    cursor.execute(
        "UPDATE AMAZON SET PRODUCT_VECTOR_CLOB = :1 WHERE PRODUCT_ID = :2",
        [json_vector_string, prod_id]
    )

conn.commit()
print("🎉 Success! Your entire database has been converted to mathematical vectors.")
