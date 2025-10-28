import os
from datetime import datetime
import requests
import json

# Logs a heartbeat every 5 minutes
def log_crm_heartbeat():
    """
    Logs a message like:
    28/10/2025-15:45:10 CRM is alive
    to /tmp/crm_heartbeat_log.txt
    """
    log_path = "/tmp/crm_heartbeat_log.txt"
    timestamp = datetime.now().strftime("%d/%m/%Y-%H:%M:%S")
    message = f"{timestamp} CRM is alive\n"

    with open(log_path, "a") as log_file:
        log_file.write(message)

    # Optionally check GraphQL endpoint responsiveness
    try:
        response = requests.post(
            "http://localhost:8000/graphql",
            json={"query": "{ hello }"}
        )
        if response.status_code == 200:
            print(f"[{timestamp}] Heartbeat OK — GraphQL endpoint responded.")
        else:
            print(f"[{timestamp}] Warning — GraphQL returned {response.status_code}.")
    except Exception as e:
        print(f"[{timestamp}] Heartbeat failed: {e}")


# Auto restock low-stock products (used by CRONJOBS)
def update_low_stock():
    """
    Executes the UpdateLowStockProducts GraphQL mutation and logs updates
    to /tmp/low_stock_updates_log.txt
    """
    log_path = "/tmp/low_stock_updates_log.txt"
    timestamp = datetime.now().strftime("%d/%m/%Y-%H:%M:%S")

    query = """
    mutation {
      updateLowStockProducts {
        success
        message
        updatedProducts {
          id
          name
          stock
        }
      }
    }
    """

    try:
        response = requests.post(
            "http://localhost:8000/graphql",
            json={"query": query}
        )

        data = response.json().get("data", {}).get("updateLowStockProducts", {})
        updated_products = data.get("updatedProducts", [])
        message = data.get("message", "No response message.")

        with open(log_path, "a") as log_file:
            log_file.write(f"\n{timestamp} - {message}\n")
            for p in updated_products:
                log_file.write(f"Product: {p['name']}, New stock: {p['stock']}\n")

        print(f"[{timestamp}] Low stock update complete.")

    except Exception as e:
        with open(log_path, "a") as log_file:
            log_file.write(f"\n{timestamp} - Error: {e}\n")
        print(f"[{timestamp}] Low stock update failed: {e}")
