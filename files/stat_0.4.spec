Name: HPE_stat
Version: 0.4
Release: 0%{?dist}
Summary: HPE modified Trac environment with Python venv, binaries, and web server integration
License: Various
URL: https://hpe.com
Source0: HPE_stat_0.4.0.tar.gz

BuildArch: x86_64 

%define _build_id_links none 

#Requires: apache2-mod_wsgi-python3
#Requires: python3-virtualenv

%if 0%{?rhel} == 9
Requires: python3.11-mod_wsgi, httpd
%global apache httpd
%else
%if 0%{?rhel} == 8
Requires: python3.11, httpd
%global apache httpd
%endif
%endif

%if 0%{?suse_version}
Requires: apache2, python311-base
%global apache apache2
%endif
%global config_file "/etc/%{apache}/conf.d/gateway-proxy.conf"

Obsoletes: HPE_trac <= 0.2
#Provides: HPE_trac

%description
This package contains a Trac environment with a Python virtual environment,
miscellaneous binaries, Trac installation, and Trac web server integration for Apache2.

%prep
%autosetup -n stat
%{expand:echo "Detected RHEL version: %{?rhel}"}

%install
# Create directories
mkdir -p %{buildroot}/opt/stat
mkdir -p %{buildroot}/etc/%{apache}/conf.d
mkdir -p %{buildroot}/etc/httpd/conf.modules.d
mkdir -p %{buildroot}/etc/profile.d
mkdir -p %{buildroot}/usr/lib64/httpd/modules


# Copy files
cp -RP apache2 bin .htpasswd COPYING GPLv3 plugin_src python3 system tools %{buildroot}/opt/stat

cp files/stat.conf.inc.%{apache} %{buildroot}/etc/%{apache}/conf.d/stat.conf.inc

cp files/stat.csh files/stat.sh %{buildroot}/etc/profile.d/

%if 0%{?rhel} == 8
cp python3/lib64/python3.11/site-packages/mod_wsgi/server/mod_wsgi-py311.cpython-311-x86_64-linux-gnu.so %{buildroot}/usr/lib64/httpd/modules/mod_wsgi.so
cp files/15-hpe-wsgi.conf %{buildroot}/etc/httpd/conf.modules.d/
%endif

# Set ownership and permissions
chown -R stat:stat %{buildroot}/opt/stat

%pre
getent group stat >/dev/null || groupadd -r stat
getent passwd stat >/dev/null || \
    useradd -r -g stat -d /opt/stat -s /sbin/nologin \
    -c "Stat user" stat

%post
/usr/bin/chown -R stat:stat /opt/stat

if [ -f "%{config_file}" ]; then     
	if ! grep -q 'ProxyPass "/stat" "!"' "%{config_file}"; then         
		sed '/ProxyPass "\/mlflow"/i \
  ProxyPass "/trac" "!"\
  ProxyPassReverse "/trac" "!"\
  ProxyPass "/stat" "!"\
  ProxyPassReverse "/stat" "!" ' "%{config_file}" -i.backup;     
	fi; 
fi

## due to load order issues, need to include stat.conf before we process the reverse proxy stuff ... hence the Include bit here, and renaming config file to .inc so it's not pulled in by usual process

if [ -f "%{config_file}" ]; then     
	if ! grep -q 'Include /etc/%{apache}/conf.d/stat.conf.inc' "%{config_file}"; then         
		sed '/ProxyPreserveHost On/i \
  Include /etc/%{apache}/conf.d/stat.conf.inc' "%{config_file}" -i.backup; 
	fi

else
	ln -s /etc/%{apache}/conf.d/stat.conf.inc /etc/%{apache}/conf.d/stat.conf
fi


%define old_config "/etc/%{apache}/conf.d/trac.conf"

if [ -f "%old_config" ];then  mv %{old_config} %{old_config}.rpmsave; fi 
/usr/bin/systemctl restart %{apache}
/usr/bin/systemctl enable %{apache}


%postun
if [ $1 -eq 0 ] ; then
	/usr/bin/systemctl stop %{apache}
    	userdel stat
	rm /etc/%{apache}/conf.d/stat.conf
	/usr/bin/systemctl start %{apache}
	if [ -f %{config_file} ]; then 
		sed -i '/trac/d' %{config_file}
		sed -i '/stat/d' %{config_file}
	fi
fi

%define __brp_mangle_shebangs %{nil}

%files
/opt/stat
%if 0%{?rhel}
/etc/httpd/conf.d/stat.conf.inc
%endif

%if 0%{?rhel} == 8
/usr/lib64/httpd/modules/mod_wsgi.so
/etc/httpd/conf.modules.d/15-hpe-wsgi.conf
%endif

%if 0%{?suse_version}
/etc/apache2/conf.d/stat.conf.inc
%endif
/etc/profile.d/stat.sh
/etc/profile.d/stat.csh
%config(noreplace) /opt/stat/system/conf/*
%config(noreplace) /opt/stat/system/db/*
%config(noreplace) /opt/stat/.htpasswd

%defattr(-,stat,stat,-)
%attr(0755, stat, stat) %dir /opt/stat
%attr(0755, stat, stat) %dir /opt/stat/python3
%attr(0755, stat, stat) %dir /opt/stat/bin
%attr(0755, stat, stat) %dir /opt/stat/system
%attr(0755, stat, stat) %dir /opt/stat/apache2
%attr(0755, stat, stat) %dir /opt/stat/plugin_src
%attr(0755, stat, stat) %dir /opt/stat/tools
%attr(0755, root, root) %dir /usr/lib64/httpd/modules
%attr(0755, root, root) %dir /etc/httpd/conf.modules.d
/opt/stat/bin/scon

%doc

%changelog
* Wed Dec 4 2024 Lee Morecroft <lee.morecroft@hpe.com> - 0.4 
- added rhel8 
- minor python module security updates
- added hpcmdb plugin
- added mattermost plugin
- added wikiviewer command line tool
* Fri Aug 2 2024 Lee Morecroft <lee.morecroft@hpe.com> - 0.3.2
- Moved sles to python 3.11
- Built custom mod_wsgi for apache2 to support python 3.11
- Added default .htaccess with admin user
- Cleaned up spec file
* Wed May 8 2024 Lee Morecroft <lee.morecroft@hpe.com> - 0.3
- Moved to python 3.11
- Added libpython to venv
- Added support for RHEL 9.x
* Wed Sep 13 2023 Lee Morecroft <lee.morecroft@hpe.com> - 
- Moved from trac to stat naming
- added various plugins
- added additional command line interface
* Sun Mar 19 2023 Lee Morecroft <lee.morecroft@hpe.com> - 1.0-1
- Initial RPM package
