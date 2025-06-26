#!/usr/bin/bash
# Copyright 2024 Hewlett Packard Enterprise Development LP.

DEST=$1
mkdir -p ${DEST}
/opt/stat/python3/bin/trac-admin /opt/stat/system/ wiki dump $DEST >/dev/null

cd $DEST
rm -rf Trac* Wiki* Other*

for f in `ls *%2*`; 
do 
	to=`echo $f | sed -e 's/%2F/\//g'`
	mkdir -p `dirname ${to}`
	mv $f ${to}.md

done
