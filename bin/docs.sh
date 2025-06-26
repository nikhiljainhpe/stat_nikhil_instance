#!/usr/bin/bash
# Copyright 2024 Hewlett Packard Enterprise Development LP.

INSTALL_PATH="/opt/stat/system"

usage() {
echo "$0 [-i inputfile] [-path] [-t filetype]
e.g.
Put file 'inputfile' with type 'ini' in wiki with path 'config/slurm/slurm.conf:
  $0 -i slurm.conf -t ini -p config/slurm/slurm.conf"
exit 0
  }


while getopts "hi:t:p:" arg; do
  case $arg in
    h)
      usage; 
      ;;
    i)
      INPUT=${OPTARG}
      ;;
    t)
      TYPE=${OPTARG}
      ;;
    p)
      WIKIPATH=${OPTARG}
      ;;
    *)
      usage;
      ;;
  esac
done

OUT="$(mktemp)"

if [[ -v TYPE ]]
then
	echo '```'${TYPE}>${OUT}
	cat ${INPUT} >>${OUT}
	echo '```' >>${OUT}
else
	cat ${INPUT} >>${OUT}
fi
if [[ `file -i ${INPUT}` != *"binary"* ]] ; 
then  
	/opt/stat/python3/bin/trac-admin ${INSTALL_PATH} wiki import ${WIKIPATH} ${OUT}
fi

rm $OUT
