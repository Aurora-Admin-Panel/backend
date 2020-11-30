#!/bin/bash

SUDO=$(if [ $(id -u $whoami) -gt 0 ]; then echo "sudo "; fi)

clean_iptables () {
    while [[ ! -z "$($SUDO iptables -S | grep -Ee 'DOWNLOAD [0-9]+->' -Ee 'UPLOAD [0-9]+->' -Ee 'FORWARD [0-9]+->' -Ee 'BACKWARD [0-9]+->')" ]]
    do
    	$SUDO iptables -S | grep -Ee 'DOWNLOAD [0-9]+->' -Ee 'UPLOAD [0-9]+->' -Ee 'FORWARD [0-9]+->' -Ee 'BACKWARD [0-9]+->' | awk -v SUDO="$SUDO" '{$1="";$COMMEND=SUDO" iptables -D "$0; system($COMMEND)}'
    done
    while [[ ! -z "$($SUDO iptables -t nat -S | grep -Ee 'DOWNLOAD [0-9]+->' -Ee 'UPLOAD [0-9]+->' -Ee 'FORWARD [0-9]+->' -Ee 'BACKWARD [0-9]+->')" ]]
    do
    	$SUDO iptables -t nat -S | grep -Ee 'DOWNLOAD [0-9]+->' -Ee 'UPLOAD [0-9]+->' -Ee 'FORWARD [0-9]+->' -Ee 'BACKWARD [0-9]+->' | awk -v SUDO="$SUDO" '{$1="";$COMMEND=SUDO" iptables -t nat -D "$0; system($COMMEND)}'
    done
}

clean_gost () {
    $SUDO systemctl stop system-gost.slice
    ls /etc/systemd/system/multi-user.target.wants | grep -E 'gost@[0-9]+\.service' | xargs $SUDO systemctl disable
}

clean_iptables
clean_gost