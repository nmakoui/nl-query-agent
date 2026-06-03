def validate_sql(sql):
    forbidden_words = [
        "insert", "update", "delete", "drop", "alter",
        "create", "truncate", "merge", "grant", "revoke"
    ]

    sql_lower = sql.lower()

    for word in forbidden_words:
        if word in sql_lower:
            raise ValueError(f"Unsafe SQL detected: {word}")

    if not sql_lower.strip().startswith("select"):
        raise ValueError("Only SELECT queries are allowed.")

    return True
