#!/bin/bash
# Deletes customers with no orders since 1 year ago
# Logs results to /tmp/customer_cleanup_log.txt

TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
LOG_FILE="/tmp/customer_cleanup_log.txt"

cd "$(dirname "$0")/../.."  # Go to project root

# Run Django shell command
DELETED_COUNT=$(python manage.py shell -c "
from django.utils import timezone
from crm.models import Customer
from datetime import timedelta

cutoff = timezone.now() - timedelta(days=365)
inactive_customers = Customer.objects.filter(orders__isnull=True) | Customer.objects.exclude(orders__order_date__gte=cutoff)
inactive_customers = inactive_customers.distinct()
count = inactive_customers.count()
inactive_customers.delete()
print(count)
")

echo \"[$TIMESTAMP] Deleted \$DELETED_COUNT inactive customers\" >> \$LOG_FILE
