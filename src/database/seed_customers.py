import sqlite3
import logging

def setup_customer_db():
    conn = sqlite3.connect('customers.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS customers
                 (customer_id TEXT PRIMARY KEY, name TEXT, risk_rating TEXT, kyc_status TEXT, segment TEXT)''')
    
    c.execute('''DELETE FROM customers''') # Clear old data
    
    users = [
        ("C-1023", "John Doe", "HIGH", "PENDING_EDD", "Corporate_Sanctioned"),
        ("C-1024", "Jane Smith", "LOW", "CLEARED", "Retail")
    ]
    
    c.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", users)
    conn.commit()
    conn.close()
    print("✅ Local SQL Customer DB Seeded.")

if __name__ == "__main__":
    setup_customer_db()
