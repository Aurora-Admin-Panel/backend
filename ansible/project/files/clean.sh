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

clean_aurora () {
    $SUDO systemctl stop system-aurora.slice
    ls /etc/systemd/system/multi-user.target.wants | grep -E 'aurora@[0-9]+\.service' | xargs $SUDO systemctl disable
}

clean_scripts () {
    $SUDO systemctl disable iptables-outipcheck.service
    $SUDO systemctl stop iptables-outipcheck.service
    $SUDO systemctl disable iptables-outipcheck.timer
    $SUDO systemctl stop iptables-outipcheck.timer
    $SUDO rm /etc/systemd/system/iptables-outipcheck.service
    $SUDO rm /etc/systemd/system/iptables-outipcheck.timer
    $SUDO rm /usr/local/bin/iptables.sh
    $SUDO rm /usr/local/bin/gost.sh
    $SUDO rm /usr/local/bin/tc.sh
    $SUDO rm /usr/local/bin/get_traffic.sh
}

clean_iptables
clean_aurora
clean_scripts