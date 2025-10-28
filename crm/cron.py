import os
from datetime import datetime
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport

# -------------------------
# Log CRM heartbeat
# -------------------------
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


# -------------------------
# Update low-stock products using GraphQL mutation
# -------------------------
def update_low_stock():
    """
    Executes the UpdateLowStockProducts GraphQL mutation and logs updates
    to /tmp/low_stock_updates_log.txt
    """
    log_path = "/tmp/low_stock_updates_log.txt"
    timestamp = datetime.now().strftime("%d/%m/%Y-%H:%M:%S")

    # Configure transport and client
    transport = RequestsHTTPTransport(
        url="http://localhost:8000/graphql",
        verify=False,
        retries=3,
    )
    client = Client(transport=transport, fetch_schema_from_transport=True)

    # GraphQL mutation
    query = gql(
        """
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
    )

    try:
        result = client.execute(query)
        data = result.get("updateLowStockProducts", {})
        message = data.get("message", "No response message.")
        updated_products = data.get("updatedProducts", [])

        with open(log_path, "a") as log_file:
            log_file.write(f"\n{timestamp} - {message}\n")
            for p in updated_products:
                log_file.write(f"Product: {p['name']}, New stock: {p['stock']}\n")

        print(f"[{timestamp}] Low stock update complete.")

    except Exception as e:
        with open(log_path, "a") as log_file:
            log_file.write(f"\n{timestamp} - Error: {e}\n")
        print(f"[{timestamp}] Low stock update failed: {e}")
