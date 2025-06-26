#!/opt/stat/python3/bin/python3
# Copyright 2024 Hewlett Packard Enterprise Development LP.

import requests
import json
import sys
import os
import getpass
from datetime import datetime, timedelta



url_base = 'https://127.0.0.1:8080/cmu/v1/'
url = url_base+"systemgroups/compute?fields=nodes.name,nodes.aliases"
session_key_file = '/opt/stat/.session_key'

def get_new_session_key():
#    username = input("Enter username: ")
#    password = getpass.getpass("Enter password: ")
    cert = ('/opt/sgi/secrets/CA/cert/admin_client.pem', '/opt/sgi/secrets/CA/private/admin_client.key')

    future_time = datetime.now() + timedelta(days=5*365)

    payload = {
#        "login": username,
#        "password": password,

#        "role": {
#           "permissions" : [ "NODE_GET" ]      },
        "validity": future_time.strftime('%Y-%m-%dT%H:%M:%S.000+0000')
    }

    session_url = url_base + 'sessions'

    response = requests.post(session_url, headers={'Content-Type': 'application/json'}, verify=False)

    if response.status_code == 200:
        session_key = response.json()['token']['code']

        with open(session_key_file, 'w') as file:
            file.write(session_key)

        print("New session key obtained and saved.")
        return session_key
    else:
        print(f"Failed to obtain session key: {response.status_code}, Message: {response.text}")
        sys.exit(1)




if os.path.exists(session_key_file):
    with open(session_key_file, 'r') as file:
        session_key = file.read().strip()
else:
    print("No session key. Enter system login details")
    session_key = get_new_session_key()

headers = {'X-Auth-Token': session_key}
response = requests.get(url, headers=headers, verify=False)

if response.status_code == 403 or response.status_code == 401:  # Unauthorized access, indicating invalid session key
    print("Session key is invalid or expired. Requesting new session key...")
    session_key = get_new_session_key()

    # Retry the request with the new session key
    headers = {'X-Auth-Token': session_key}
    response = requests.get(url, headers=headers, verify=False)

# Check the response
if response.status_code == 200:
    try:
        data = response.json()
        print(json.dumps(data, indent=4))  # Pretty print the JSON response
    except ValueError:
        print("Response is not valid JSON. Raw response:")
        print(response.text)
else:
    print(f"Failed with status code: {response.status_code}, Message: {response.text}")
