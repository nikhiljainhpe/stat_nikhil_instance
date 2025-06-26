# Changelog
## Fri Dec 6 2024 Lee Morecroft <lee.morecroft@hpe.com> - 0.4.0
- Updated rpm spec file to properly support rhel8
- Added plugins for 
    - hpcmdb(just adds xnames if hostname set and vice-versa)
    - mattermost sends timeline updates to a mattermost server
- added command line markdownviewer: `wikiviewer.py`
- added plugin_src for GPL compliance
- updated python modules with latest security patches
- added support for local document repository - see wiki page in STAT
- added some best practices for image building, SAT process etc.
- removed link to 'spicy' site in base TRAC wiki docs. 
## Fri Aug 2 2024 Lee Morecroft <lee.morecroft@hpe.com> - 0.3.2
- Moved sles to python 3.11
- Built custom mod_wsgi for apache2 to support python 3.11 on sles
- Added default .htaccess with admin user
- Added example standalone launch script for tracd in bin/
- Cleaned up rpm spec file
## Wed May 8 2024 Lee Morecroft <lee.morecroft@hpe.com> - 0.3
- Moved to python 3.11
- Added libpython to venv
- Added support for RHEL 9.x
## Wed Sep 13 2023 Lee Morecroft <lee.morecroft@hpe.com> - 
- Moved from trac to stat naming
- added various plugins
- added additional command line interface
## Sun Mar 19 2023 Lee Morecroft <lee.morecroft@hpe.com> - 1.0-1
- Initial RPM package
