#!/bin/bash
# Copyright 2024 Hewlett Packard Enterprise Development LP.

curl -k -s  --cert /opt/sgi/secrets/CA/cert/admin_client.pem --key /opt/sgi/secrets/CA/private/admin_client.key https://admin:8080/cmu/v1/sessions/ |jq -r '.[] | select(.name == "user_client") | .token.code' > /opt/stat/.session_key

chown stat:stat /opt/stat/.session_key
chmod 600 /opt/stat/.session_key
