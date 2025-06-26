## Mattermost plugin for stat

## Overview

Pushes updates from the stat timeline (ticket, wiki, and revision control, creations, updates, and deletions to mattermost

![ScreenShot](https://github.hpe.com/lee-morecroft/HPC-STAT/raw/main/plugin_src/mattermost-0.1/images/image.png))

## Mattermost setup

* install mattermost
* from the system console menu :
    * -> Integrations -> Bot Accounts -> Enable Bot Account Creation
* from product menu:
    * -> Integrations -> Bot Accounts -> Add bot account
    * fill in details (stat-bot) 
    * enable `post:all` or `post:channels`
    * generate token
* create channel and get channel id token. (in channel info)  

## STAT setup
* copy plugin mattermost-XX.py to `/opt/stat/system/plugins`
* edit `/opt/stat/system/conf/trac.conf` and add:
```
[mattermost]
api_url = http://<URL>
token = your_access_token_here
channel_id = your_channel_id_here
```

* restart apache2


