## Slack email notification plugin for stat

## Overview

Pushes updates from the stat timeline (ticket, wiki, and revision control, creations, updates, and deletions to slack via email - requires working command line email on host

## Slack setup 
From the channel select 'Send emails to channel' button - paste below

## STAT setup
* copy plugin slack-email-XX.py to `/opt/stat/system/plugins`
* edit `/opt/stat/system/conf/trac.conf` and add:
```
[email]
sender=STATCentral
recipient=<slack-channel-email-alias>
```

* restart apache2


