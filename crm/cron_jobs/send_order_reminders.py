#!/usr/bin/env python3
import datetime
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport

LOG_FILE = "/tmp/order_reminders_log.txt"

def main():
    # Define the GraphQL endpoint
    transport = RequestsHTTPTransport(
        url="http://localhost:8000/graphql",
        verify=True,
        retries=3,
    )
    client = Client(transport=transport, fetch_schema_from_transport=True)

    # Define the query
    query = gql("""
    query RecentOrders {
        orders(orderDate_Gte: "%s") {
            id
            customer {
                email
            }
        }
    }
    """ % (datetime.date.today() - datetime.timedelta(days=7)))

    # Execute query
    try:
        result = client.execute(query)
        orders = result.get("orders", [])
    except Exception as e:
        orders = []
        log_message(f"Error querying GraphQL: {e}")

    # Log results
    if orders:
        for order in orders:
            log_message(f"Order ID: {order['id']}, Customer Email: {order['customer']['email']}")
    else:
        log_message("No orders found in the last 7 days.")

    print("Order reminders processed!")

def log_message(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as log_file:
        log_file.write(f"[{timestamp}] {message}\n")

if __name__ == "__main__":
    main()
