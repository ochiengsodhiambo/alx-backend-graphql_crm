import os
import logging
import requests
from datetime import datetime
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
from celery import shared_task

# GraphQL endpoint for internal queries
GRAPHQL_ENDPOINT = "http://localhost:8000/graphql/"

LOG_FILE = "/tmp/crm_report_log.txt"
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
)


@shared_task
def generate_crm_report():
    """
    Fetches CRM summary via GraphQL and logs total customers, orders, and revenue.
    Runs weekly (Monday 6:00 AM via Celery Beat).
    """
    try:
        # GraphQL client setup
        transport = RequestsHTTPTransport(url=GRAPHQL_ENDPOINT, verify=False)
        client = Client(transport=transport, fetch_schema_from_transport=True)

        query = gql("""
        {
            allCustomers {
                totalCount
            }
            allOrders {
                totalCount
                edges {
                    node {
                        totalAmount
                    }
                }
            }
        }
        """)

        result = client.execute(query)

        total_customers = result["allCustomers"]["totalCount"]
        total_orders = result["allOrders"]["totalCount"]
        total_revenue = sum(
            float(order["node"]["totalAmount"]) for order in result["allOrders"]["edges"]
        )

        report_message = (
            f"Report: {total_customers} customers, "
            f"{total_orders} orders, "
            f"{total_revenue:.2f} revenue."
        )

        logging.info(report_message)

        print(f"[CRM Report Generated] {report_message}")

    except Exception as e:
        logging.error(f"Error generating CRM report: {e}")
        print(f"Error generating CRM report: {e}")

# Schedule this task in Celery Beat to run every Monday at 6:00 AM
