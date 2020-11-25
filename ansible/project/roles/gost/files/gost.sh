#!/bin/bash

SUDO=$(if [ $(id -u $whoami) -gt 0 ]; then echo "sudo "; fi)

save_iptables () {
  if [[ -f /etc/redhat-release ]]; then
    release="centos"
  elif cat /etc/issue | grep -q -E -i "debian"; then
    release="debian"
  elif cat /etc/issue | grep -q -E -i "ubuntu"; then
    release="ubuntu"
  elif cat /etc/issue | grep -q -E -i "centos|red hat|redhat"; then
    release="centos"
  elif cat /proc/version | grep -q -E -i "debian"; then
    release="debian"
  elif cat /proc/version | grep -q -E -i "ubuntu"; then
    release="ubuntu"
  elif cat /proc/version | grep -q -E -i "centos|red hat|redhat"; then
    release="centos"
  fi
  if [ $release = "centos" ]; then
    $SUDO mkdir -p /etc/sysconfig
    $SUDO iptables-save | $SUDO tee /etc/sysconfig/iptables > /dev/null
  else
    $SUDO mkdir -p /etc/iptables
    $SUDO iptables-save | $SUDO tee /etc/iptables/rules.v4 > /dev/null
  fi
}

monitor () {
    $SUDO iptables -I INPUT -p tcp --dport $LOCAL_PORT -j ACCEPT -m comment --comment "UPLOAD $LOCAL_PORT->$REMOTE_IP"
    $SUDO iptables -I OUTPUT -p tcp  --sport $LOCAL_PORT -j ACCEPT -m comment --comment "DOWNLOAD $LOCAL_PORT->$REMOTE_IP"
    $SUDO iptables -I INPUT -p udp --dport $LOCAL_PORT -j ACCEPT -m comment --comment "UPLOAD-UDP $LOCAL_PORT->$REMOTE_IP"
    $SUDO iptables -I OUTPUT -p udp --sport $LOCAL_PORT -j ACCEPT -m comment --comment "DOWNLOAD-UDP $LOCAL_PORT->$REMOTE_IP"
    save_iptables
}

list () {
    COMMENT="$LOCAL_PORT->"
    $SUDO iptables -nxvL | grep $COMMENT
    $SUDO iptables -t nat -nxvL | grep $COMMENT
}

delete () {
    COMMENT="$LOCAL_PORT->"
    while [[ ! -z "$($SUDO iptables -S | grep $COMMENT)" ]]
    do
    	$SUDO iptables -S | grep $COMMENT | awk -v SUDO="$SUDO" '{$1="";$COMMEND=SUDO" iptables -D "$0; system($COMMEND)}'
    done
    while [[ ! -z "$($SUDO iptables -t nat -S | grep $COMMENT)" ]]
    do
	$SUDO iptables -t nat -S | grep $COMMENT | awk -v SUDO="$SUDO" '{$1="";$COMMEND=SUDO" iptables -t nat -D "$0; system($COMMEND)}'
    done
}

LOCAL_PORT=$1
REMOTE_IP=$2
[ -z $LOCAL_PORT ] && echo "Port not specfied" && exit 1

[ -z $(ls /usr/local/bin/gost) ] && echo "gost not found" && exit 1

[ -z $(ls /usr/lib/systemd/system/gost@.service) ] && echo "gost@.service not found" && exit 1

$SUDO mkdir -p /usr/local/etc/gost
list
delete
monitor
