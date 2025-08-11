#!/bin/bash
# Copyright 2024 Hewlett Packard Enterprise Development LP.

# 1) activate your venv
source /opt/stat/python3/bin/activate
export PYTHON_EGG_CACHE=/opt/stat/system/.egg-cache/

# 2) export any Flask‑specific env vars
export FLASK_ENV=production
export PORT=5000
# export SLACK_WEBHOOK_URL="https://hooks.slack.com/triggers/…"
# export ACTIVE_TICKETS_WEBHOOK_URL="https://hooks.slack.com/triggers/…"
# export SET_INTERVAL_TOKEN="your_secret_token"

# 3) start your Flask app (adjust path/to/your_flask_app.py as needed)
#    we use & to background it, and redirect logs
nohup python /opt/stat/python3/lib/python3.11/site-packages/trac/ticket/slack_proxy.py \
     > /opt/stat/system/flask.log 2>&1 &

# 4) now start Trac (foreground)
exec tracd \
     --basic-auth system,/opt/stat/.htpasswd,trac \
     -s -p 8123 \
     --user jainnikh --group jainnikh \
     /opt/stat/system/ \
     -b localhost
