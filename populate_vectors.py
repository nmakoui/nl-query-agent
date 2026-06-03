import json
import oci
import oracledb

# 1. Initialize OCI Generative AI client to get embeddings
signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
gen_ai_client = oci.generative_ai_inference.GenerativeAiInferenceClient(
    config={}, signer=signer, service_endpoint="https://inference.generativeai.uk-london-1.oci.oraclecloud.com"
)

# --- CONFIGURATION HUB ---
COMPARTMENT_ID = "ocid1.tenancy.oc1..aaaaaaaapigjcw7dwdp6onerp5wqcu3z5pzsckmokdiqjezvoodfi2corv6q" # Merged from your sql generator
CONNECTION_STRING = "(description=(retry_count=20)(retry_delay=3)(address=(protocol=tcps)(port=1522)(host=adb.uk-london-1.oraclecloud.com))(connect_data=(service_name=g3611c40115fb3c_amazon_high.adb.oraclecloud.com))(security=(ssl_server_dn_match=yes)))"

print("Connecting to Autonomous Database...")
conn = oracledb.connect(user="ADMIN", password="Password1234", dsn=CONNECTION_STRING)
cursor = conn.cursor()

# Try uppercase table first, filter out rows that already have vectors calculated to allow script resume capability!
TABLE_NAME = "AMAZON"
try:
    cursor.execute(f"SELECT product_id, product_name, about_product FROM {TABLE_NAME} WHERE PRODUCT_VECTOR_CLOB IS NULL")
    rows = cursor.fetchall()
except oracledb.DatabaseError:
    # Fallback to lowercase if uppercase fails
    TABLE_NAME = "amazon"
    cursor.execute(f"SELECT product_id, product_name, about_product FROM {TABLE_NAME} WHERE PRODUCT_VECTOR_CLOB IS NULL")
    rows = cursor.fetchall()

print(f"Targeting table: {TABLE_NAME}")
print(f"Found {len(rows)} records requiring vector calculation processing.")

if not rows:
    print("⚠️ No work to be done! Either table is empty, or all records already have vector embeddings populated.")
    cursor.close()
    conn.close()
    exit()

print("Generating embeddings and syncing vector columns dynamically...")
for idx, row in enumerate(rows):
    prod_id, prod_name, about_prod = row
    
    # Clean up empty or None strings safely
    prod_name_str = str(prod_name or "")
    about_prod_str = str(about_prod or "")
    combined_text = f"{prod_name_str} {about_prod_str[:400]}".strip()
    
    if not combined_text:
        continue

    try:
        # Call OCI Cohere Embedding v3 Model
        embed_request = oci.generative_ai_inference.models.EmbedTextDetails(
            inputs=[combined_text],
            serving_mode=oci.generative_ai_inference.models.OnDemandServingMode(model_id="cohere.embed-english-v3.0"),
            compartment_id=COMPARTMENT_ID,
            input_type="SEARCH_DOCUMENT" # Correct format for text data store mapping
        )
        
        embed_response = gen_ai_client.embed_text(embed_request)
        vector_array = embed_response.data.embeddings[0]
        json_vector_string = json.dumps(vector_array)
        
        # Push vector string block back to 19c CLOB
        cursor.execute(
            f"UPDATE {TABLE_NAME} SET PRODUCT_VECTOR_CLOB = :1 WHERE PRODUCT_ID = :2",
            [json_vector_string, prod_id]
        )
        
        # Batch commit every 10 rows to prevent transactions hanging open
        if idx % 10 == 0:
            conn.commit()
            print(f"Processed and committed batch layer: {idx}/{len(rows)} elements.")
            
    except Exception as e:
        print(f"❌ Error compiling row ID {prod_id}: {str(e)}")
        continue

conn.commit()
print("🎉 Success! Your database vector layer has been calculated and updated securely.")
cursor.close()
conn.close()
