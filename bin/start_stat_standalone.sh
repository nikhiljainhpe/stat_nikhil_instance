#!/bin/bash
# Copyright 2024 Hewlett Packard Enterprise Development LP.

source /opt/stat/python3/bin/activate
export PYTHON_EGG_CACHE=/opt/stat/system/.egg-cache/
tracd  --basic-auth system,/opt/stat/.htpasswd,trac -s -p 8123 --user jainnikh --group jainnikh /opt/stat/system/ -b localhost
