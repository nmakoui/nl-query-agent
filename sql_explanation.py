from textwrap import dedent
import re

from ai_sql_generator import call_ai_inference_endpoint


def format_sql_explanation(text: str) -> str:
    """
    Clean and format the AI explanation so Streamlit displays it nicely.
    """

    if not text:
        return "SQL explanation was not available."

    text = text.strip()

    # Remove unwanted leading label if model returns it
    text = re.sub(r"^Explanation:\s*", "", text, flags=re.IGNORECASE)

    # Force section headers onto new lines
    section_headers = [
        "Query Summary:",
        "Step-by-Step Breakdown:",
        "Final Output:",
        "Potential Notes:",
    ]

    for header in section_headers:
        text = text.replace(header, f"\n\n### {header}")

    # Force numbered steps onto separate lines
    text = re.sub(r"\s+(\d+\.)\s+", r"\n\n\1 ", text)

    # Clean excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def sql_explanation(sql_query: str) -> str:
    """
    Generate a plain-English explanation for a SQL query using the same AI backend
    already used by app.py.
    """

    if not sql_query:
        return "SQL explanation was not available because no SQL query was provided."

    prompt_payload = dedent(f"""
    You are an expert SQL explanation assistant.
    
    Your task is to explain a generated SQL query to a non-technical or semi-technical user. Whenever I give you a SQL query, explain what it does clearly and accurately.
    
    Follow these rules:
    
    1. Start with a short one-sentence summary of the query’s purpose.
    2. Break down the query clause by clause.
    3. Explain each important part in plain English.
    4. Mention the table or tables being used.
    5. Explain selected columns, calculated fields, filters, joins, grouping, sorting, and limits.
    6. Do not assume business meaning unless it is clearly visible from the table or column names.
    7. If the query contains aliases, explain what each alias represents.
    8. If the query contains aggregation such as SUM, COUNT, AVG, MIN, or MAX, explain what is being calculated.
    9. If the query contains GROUP BY, explain how rows are being grouped.
    10. If the query contains ORDER BY, explain how the final result is sorted.
    11. If the query contains WHERE or HAVING, explain what data is being filtered.
    12. If the query contains JOINs, explain which tables are being connected and how.
    13. If the query contains subqueries, CTEs, window functions, or CASE statements, explain them step by step.
    14. Use simple language, but do not oversimplify technical logic.
    15. Do not rewrite the SQL unless I specifically ask you to.
    16. If there may be a possible issue, ambiguity, or risk in the SQL, add a short “Potential notes” section.
    17. Keep the explanation structured and easy to scan.
    
    Use this output format:
    
    Query Summary:
    [One clear sentence explaining the overall purpose of the query.]
    
    Step-by-Step Breakdown:
    
    1. [Explain the first major part of the SQL.]
    2. [Explain the next major part.]
    3. [Continue until the whole query is explained.]
    
    Final Output:
    [Explain what the user will see in the final result table.]
    
    Potential Notes:
    [Mention any ambiguity, assumption, possible performance issue, missing filter, duplicate risk, NULL-handling issue, or logic concern. If there are no obvious issues, say: “No obvious issues detected.”]
    
    Example 1:
    
    SQL Query:
    SELECT
    product_name,
    SUM(quantity * unit_price) AS total_revenue
    FROM sales
    WHERE sale_date >= '2024-01-01'
    AND sale_date < '2025-01-01'
    GROUP BY product_name
    ORDER BY total_revenue DESC
    LIMIT 5;
    
    Explanation:
    
    Query Summary:
    This query finds the top 5 products that generated the highest total revenue in 2024.
    
    Step-by-Step Breakdown:
    
    1. The query uses the sales table as the source of data.
    2. It selects product_name, so each result row represents a product.
    3. It calculates total_revenue using SUM(quantity * unit_price), which multiplies the quantity sold by the unit price for each sale, then adds those values together for each product.
    4. The WHERE clause filters the data to include only sales from January 1, 2024 up to, but not including, January 1, 2025.
    5. The GROUP BY product_name clause groups all sales records by product, so revenue can be calculated separately for each product.
    6. The ORDER BY total_revenue DESC clause sorts the products from highest revenue to lowest revenue.
    7. The LIMIT 5 clause returns only the top 5 products.
    
    Final Output:
    The result table will show two columns: product_name and total_revenue. Each row represents one of the five highest-revenue products in 2024.
    
    Potential Notes:
    No obvious issues detected.
    
    Example 2:
    
    SQL Query:
    SELECT
    c.customer_id,
    c.customer_name,
    COUNT(o.order_id) AS total_orders
    FROM customers c
    LEFT JOIN orders o
    ON c.customer_id = o.customer_id
    GROUP BY c.customer_id, c.customer_name
    ORDER BY total_orders DESC;
    
    Explanation:
    
    Query Summary:
    This query lists customers and shows how many orders each customer has placed.
    
    Step-by-Step Breakdown:
    
    1. The query uses the customers table with the alias c.
    2. It also uses the orders table with the alias o.
    3. The LEFT JOIN connects customers to their orders using customer_id.
    4. Because this is a LEFT JOIN, customers will still appear even if they have not placed any orders.
    5. The query selects customer_id and customer_name from the customers table.
    6. It calculates total_orders using COUNT(o.order_id), which counts how many matching orders each customer has.
    7. The GROUP BY clause groups the data by each customer so the order count is calculated separately for every customer.
    8. The ORDER BY total_orders DESC clause sorts customers from the highest number of orders to the lowest.
    
    Final Output:
    The result table will show each customer’s ID, name, and total number of orders. Customers with the most orders will appear first.
    
    Potential Notes:
    Because this query uses LEFT JOIN, customers with no orders should still appear with a total_orders value of 0. This is usually correct if the goal is to include all customers.
    
    Example 3:
    
    SQL Query:
    WITH monthly_sales AS (
    SELECT
    DATE_TRUNC('month', sale_date) AS sales_month,
    SUM(amount) AS monthly_revenue
    FROM sales
    GROUP BY DATE_TRUNC('month', sale_date)
    )
    SELECT
    sales_month,
    monthly_revenue,
    monthly_revenue - LAG(monthly_revenue) OVER (ORDER BY sales_month) AS revenue_change
    FROM monthly_sales
    ORDER BY sales_month;
    
    Explanation:
    
    Query Summary:
    This query calculates monthly revenue and compares each month’s revenue with the previous month.
    
    Step-by-Step Breakdown:
    
    1. The query starts with a CTE named monthly_sales, which creates a temporary result set.
    2. Inside the CTE, the sales table is used as the data source.
    3. DATE_TRUNC('month', sale_date) converts each sale date into its month, so sales can be grouped monthly.
    4. SUM(amount) calculates the total revenue for each month and names it monthly_revenue.
    5. The GROUP BY clause groups sales by month.
    6. The main query selects sales_month and monthly_revenue from the monthly_sales CTE.
    7. The expression LAG(monthly_revenue) OVER (ORDER BY sales_month) gets the previous month’s revenue.
    8. monthly_revenue - LAG(monthly_revenue) calculates the change in revenue compared with the previous month.
    9. The final ORDER BY sales_month sorts the result chronologically by month.
    
    Final Output:
    The result table will show each month, the total revenue for that month, and the revenue change compared with the previous month.
    
    Potential Notes:
    The first month will have a NULL revenue_change because there is no previous month to compare against.
    
    Now explain the following SQL query using the same format:
    
    SQL Query:
    {sql_query}
    
    """).strip()

    try:
        explanation = call_ai_inference_endpoint(prompt_payload)
        return format_sql_explanation(explanation)
    except Exception as e:
        return f"SQL explanation could not be generated: {e}"
