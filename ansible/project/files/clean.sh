#!/bin/bash

SUDO=$(if [ $(id -u $whoami) -gt 0 ]; then echo "sudo "; fi)

clean_services () {
    [[ -z $1 ]] && return 0
    ls /etc/systemd/system/multi-user.target.wants | grep -E $1 | xargs $SUDO systemctl disable --now
    ls /etc/systemd/system | grep -E $1 | xargs -I '{}' $SUDO rm '/etc/systemd/system/{}'
}

clean_iptables () {
    while [[ ! -z "$($SUDO iptables -S | grep -Ee 'DOWNLOAD [0-9]+->' -Ee 'UPLOAD [0-9]+->' -Ee 'FORWARD [0-9]+->' -Ee 'BACKWARD [0-9]+->')" ]]
    do
    	$SUDO iptables -S | grep -Ee 'DOWNLOAD [0-9]+->' -Ee 'UPLOAD [0-9]+->' -Ee 'FORWARD [0-9]+->' -Ee 'BACKWARD [0-9]+->' | awk -v SUDO="$SUDO" '{$1="";$COMMEND=SUDO" iptables -D "$0; system($COMMEND)}'
    done
    while [[ ! -z "$($SUDO iptables -t nat -S | grep -Ee 'DOWNLOAD [0-9]+->' -Ee 'UPLOAD [0-9]+->' -Ee 'FORWARD [0-9]+->' -Ee 'BACKWARD [0-9]+->')" ]]
    do
    	$SUDO iptables -t nat -S | grep -Ee 'DOWNLOAD [0-9]+->' -Ee 'UPLOAD [0-9]+->' -Ee 'FORWARD [0-9]+->' -Ee 'BACKWARD [0-9]+->' | awk -v SUDO="$SUDO" '{$1="";$COMMEND=SUDO" iptables -t nat -D "$0; system($COMMEND)}'
    done
    clean_services "iptables-restore.service"
}

clean_aurora () {
    $SUDO systemctl stop system-aurora.slice
    clean_services "aurora@[0-9]+\.service"
    $SUDO rm -rf /usr/local/etc/aurora
}

clean_scripts () {
    $SUDO rm /usr/local/bin/app.sh
    $SUDO rm /usr/local/bin/iptables.sh
    $SUDO rm /usr/local/bin/tc.sh
    $SUDO rm /usr/local/bin/get_traffic.sh
}

clean_iptables
clean_aurora
clean_scripts
