import os
import oracledb
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()  # loads variables from a local .env file (never committed)

# We use st.cache_resource to ensure the connection pool is created ONCE
# and shared across all user sessions and reruns.
@st.cache_resource
def get_connection_pool():
    """
    Initializes and caches a secure Oracle connection pool using the provided wallet.
    """
    return oracledb.create_pool(
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        dsn=os.environ["DB_DSN"],
        config_dir=os.environ["WALLET_LOCATION"],
        wallet_location=os.environ["WALLET_LOCATION"],
        wallet_password=os.environ["WALLET_PASSWORD"],
        min=1,     # Minimum number of active connections to keep open
        max=5,     # Maximum connections the pool can scale to
        increment=1
    )

def run_sql(query="SELECT * FROM AMAZON FETCH FIRST 10 ROWS ONLY"):
    """
    Acquires a fresh connection from the pool, executes the query into a DataFrame,
    and safely returns the connection back to the pool automatically.
    """
    # Get our cached connection pool
    pool = get_connection_pool()

    # 'with pool.acquire()' guarantees the connection drops back to the pool
    # even if the query execution fails mid-way.
    with pool.acquire() as conn:
        df = pd.read_sql(query, conn)
        return df
