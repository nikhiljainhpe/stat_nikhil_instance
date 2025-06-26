# HPC-STAT
HPC - System Triage and Ticketing tool  - An easy to deploy and manage ticketing and documentation system

Slack channel: [#hpc-stat](https://hpe.enterprise.slack.com/archives/C07NPTWSYQH)

## Quick install guide

1. Download relevent version of HPE_stat rpm from rpm directory
2. Install rpm (built and tested on SLES15-SP5)
3a. On HPCM goto https://admin/stat/
3b. On standalone SLES or RHEL, go to http://SERVER/stat/
Note: for production you should really put this behind SSL.  
4. Follow Quick Start instructions on that page to add a user and get started
5. There is a default user `admin` with password `initial0`, remove/change this on first boot. See Quick Start instructions above. 

## Versions

Update to 0.4.0 recommended as it adds OSRB compliance and has some minor security fixes to python modules. 

| Version      | Built with           | Tested On              |
|--------------|----------------------|------------------------|
|HPE_stat-0.2-1| Python3.6 + Trac 1.5 | SLES15SP4(HPCM)        |
|HPE_stat-0.3-1| Python3.11 + Trac 1.6| RHEL9                  | 
|HPE_stat-0.3.2| Python3.11 + Trac 1.6| RHEL9 + SLES15SP4(HPCM)<br>Ubuntu, OSX, and Windows|
|HPE_stat-0.4.0| Python3.11 + Trac 1.6| RHEL9 + RHEL8(HPCM) +  SLES15SP5(HPCM)<br>Ubuntu, OSX, and Windows|


### Notes for other Versions
#### openSUSE Leap 15.6
* Installs from SLES RPM
* need to remove existing mod_wsgi rpm
```
zypper rm  apache2-mod_wsgi-python3
```
* STAT Apache config need updating to support apache2.4 below, or use RHEL9 [stat.conf](https://github.hpe.com/lee-morecroft/HPC-STAT/blob/main/files/stat.conf.inc.httpd)
```
    Require all granted
    #Order allow,deny 
    #Allow from all
```

## Known issues 

* SELINUX
selinux is disabled in HPCM, but when installing in other versions with selinux enabled you will need to run the following commands after installation (or disable selinux):
```
sudo semanage fcontext -a -t httpd_sys_rw_content_t "/opt/stat(/.*)?"
sudo restorecon -Rv /opt/stat
sudo systemctl restart httpd
```

## Overview 

STAT is one-stop tracker for system documentation plus pinpointing and addressing system repair needs, spanning nodes, cables, switches, to firmware and software updates across HPC systems.

Unlike the scattered tool and methodology spectrum currently in use, this streamlined tracker eradicates the extra legwork per deployment. It paves the way for a unified data collection approach across installations, channeling invaluable insights to supply chain, reliability, and R&D squads. Rooted in the open-source Trac document and issue management framework, it provides trio of user-friendly interfaces: web-based, command line, and API, ensuring a seamless, flexible interaction for end uses and for integration with other tools. 

### Video 
A recorded video from a lunch and learn session is available here: https://hpe-my.sharepoint.com/:v:/p/isa_wazirzada/ES1tKB1c3yhDnFoHhKOk-hkBTrNaCoqN6LdLV10oYiHh1A

### Solution
A locally hosted ticketing and documentation system would help mitigate these shortcomings, making collaboration, issue tracking simple, and creating and maintaining system documentation efficient and quick.

The open source project [Trac](https://trac.edgewall.org/) fulfills these requirements. 
* Robust and configurable ticketing system
* Wiki (and markdown, with installed plugin) documentation system
* Exportable ticket reports in csv format 
* Milestone creation and tracking 
* Command line interface for creating/updating documentation
* Documentation changelogs 
* Syntax highlighting


This is a rename and continuation of https://github.hpe.com/lee-morecroft/HPC-Ticketing-and-Documentation-System

## RPM Building
The src rpm is located in the rpm dir. 
The following rpmbuild command lines were used on each system (change paths if needed)
* RHEL
```
rpmbuild -ba --define "_topdir /root/rpmbuild" ~/rpmbuild/SPECS/stat_0.4.spec
```

* SLES
```
rpmbuild -ba --define "dist .sles15" --define "_topdir /usr/src/packages" /usr/src/packages/SPECS/stat_0.4.spec 
```

## Running stand-alone 
**NOTE: for testing, local machine deployment only, not for production** 

### OSX
* Clone this repo, or download zip file via 'Code' button above
* Unzip and move contents to `/opt/stat` (will probably need to be root)
* Change owner to your user/primary group e.g.
```
chown -R lee:staff /opt/stat
```
* Switch back to your user
* Make sure you have python3.11 installed (I use [homebrew](https://brew.sh/) ) 
* change python executable to point at python3.11
```
cd /opt/stat/python3/bin/
rm python*
ln -s /opt/homebrew/bin/python3.11 python
ln -s python python3
ln -s python python3.11
```
* update modules (some have binary libraries). Choose correct activate file based on your shell. Default is for bash like shells.
```
source /opt/stat/python3/bin/activate 
pip install -r /opt/stat/python3/requirements.txt
```
* Edit /opt/stat/bin/start_stat_standalone.sh and change to your username/group (find with `id`) and port if required. e.g. 
```
#!/bin/bash
source /opt/stat/python3/bin/activate
export PYTHON_EGG_CACHE=/opt/stat/system/.egg-cache/
tracd  --basic-auth system,/opt/stat/.htpasswd,trac -s -p 8123 --user lee --group staff /opt/stat/system/ -b localhost
``` 
* give admin user STAT admin privileges 
```
source /opt/stat/python3/bin/activate
/opt/stat/python3/bin/trac-admin /opt/stat/system permission add admin TRAC_ADMIN
```
* as your user, make executable and run
```
chmod +x /opt/stat/bin/start_stat_standalone.sh
/opt/stat/bin/start_stat_standalone.sh
```
* connect with you web browser to http://localhost:8123

### Linux
If not on SLES or RHEL:
* Clone this repo, or download zip file via 'Code' button above
* Unzip and move contents to `/opt/stat` (will probably need to be root)
* Change owner to your user/primary group, or create stat:stat user/group
* Switch back to your user
* Make sure you have python3.11 installed. For Ubuntu 24.04 I had to:
```
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.11   
```
* make sure python symlinks point at the python 3.11 binary
```
which python3.11
ls -l /opt/stat/python3/bin/python
```
* update modules :

**NOTE: you may need to remove `mod_wsgi` from `requirements.txt`**

**NOTE: if you added the stat user, you will need to sudo to that account**
```
source /opt/stat/python3/bin/activate
pip install -r /opt/stat/python3/requirements.txt
```
* check `/opt/stat/bin/start_stat_standalone.sh` and modify as needed. 
* if owned by your user
```
chmod +x /opt/stat/bin/start_stat_standalone.sh
/opt/stat/bin/start_stat_standalone.sh
```
* if owned by stat
```
sudo chmod +x /opt/stat/bin/start_stat_standalone.sh
sudo /opt/stat/bin/start_stat_standalone.sh
```
* give admin user STAT admin privileges
```
source /opt/stat/python3/bin/activate
/opt/stat/python3/bin/trac-admin /opt/stat/system permission add admin TRAC_ADMIN
```
* connect with your web browser to http://localhost:8123 

### Windows
The easiest way to get this up and running on Windows it to use WSL (Windows Services for Linux) to install linux. 
* Open a terminal and run as administrator
* You can see available linux versions with:
```
wsl -l --online
``` 
* In this example we're install ubuntu 24.04
```
wsl --install -d Ubuntu-24.04
```
* A reboot is required for changes to take effect
* When rebooted launch Ubuntu 24.04. It appears as an app in the start menu.
* Follow the instructions as it installs, creating a user account when asked
* When complete you will be logged into Ubuntu
* Follow the Linux instructions above with the following changes/notes
    * Windows files can be accessed from ubuntu via `/mnt/c` e.g. to copy a file from your download directory.
```
sudo cp /mnt/c/Users/<YOUR_USER_NAME>/Download/HPC-STAT-main.zip /opt/
``` 
   * As the ubuntu WSL image is not exposed to the outside world you can set the user/group to my ubuntu username in `/opt/stat/bin/start_stat_standalone.sh` and remove `-b localhost` from it too, to enable access from Windows.
   * To access STAT once launched find the linux ip address with, should start with 172 
```
ip -o a s dev eth0
```
   * in windows launch your web browser and connect to `http://<IP_ADDRESS_FROM_LINUX>:8123`
 
## Changelog
### Fri Dec 6 2024 Lee Morecroft lee.morecroft@hpe.com - 0.4.0
* Updated rpm spec file to properly support rhel8
* Added plugins for
    * hpcmdb(just adds xnames if hostname set and vice-versa)
    * mattermost sends timeline updates to a mattermost server
* added command line markdownviewer: wikiviewer.py
* added plugin_src for GPL compliance
* updated python modules with latest security patches
* added support for local document repository - see wiki page in STAT
* added some best practices for image building, SAT process etc.
* removed link to 'spicy' site in base TRAC wiki docs.
### Fri Aug 2 2024 Lee Morecroft lee.morecroft@hpe.com - 0.3.2
* Moved sles to python 3.11
* Built custom mod_wsgi for apache2 to support python 3.11 on sles
* Added default .htaccess with admin user
* Added example standalone launch script for tracd in bin/
* Cleaned up rpm spec file
### Wed May 8 2024 Lee Morecroft lee.morecroft@hpe.com - 0.3
* Moved to python 3.11
* Added libpython to venv
* Added support for RHEL 9.x
### Wed Sep 13 2023 Lee Morecroft lee.morecroft@hpe.com -
* Moved from trac to stat naming
* added various plugins
* added additional command line interface
### Sun Mar 19 2023 Lee Morecroft lee.morecroft@hpe.com - 1.0-1
* Initial RPM package

