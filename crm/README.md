# CRM Celery + Celery Beat Setup

This module schedules and generates a **weekly CRM report** summarizing:
- Total customers
- Total orders
- Total revenue

The report is logged at `/tmp/crm_report_log.txt`.

---

## Setup Steps

### Install Redis and dependencies
```bash
sudo apt update && sudo apt install redis-server -y
pip install celery django-celery-beat redis
