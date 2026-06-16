import sqlite3
import json
import logging

def get_customer_profile(customer_id: str) -> str:
    """Tool T08: SQL lookup for customer KYC and Risk data."""
    logging.info(f"🛠️  [MCP Tool Executed] get_customer_profile (ID: {customer_id})")
    
    try:
        conn = sqlite3.connect('customers.db')
        c = conn.cursor()
        c.execute("SELECT * FROM customers WHERE customer_id=?", (customer_id,))
        row = c.fetchone()
        conn.close()
        
        if row:
            profile = {
                "customer_id": row[0],
                "name": row[1],
                "risk_rating": row[2],
                "kyc_status": row[3],
                "segment": row[4]
            }
            return json.dumps(profile)
        return json.dumps({"error": "Customer not found."})
    except Exception as e:
        return json.dumps({"error": str(e)})
