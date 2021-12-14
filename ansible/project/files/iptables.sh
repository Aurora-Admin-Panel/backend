#!/bin/bash

SUDO=$(if [ $(id -u $whoami) -gt 0 ]; then echo "sudo "; fi)
IFACE=$(ip route show | grep default | grep -Po '(?<=dev )(\w+)')
INET=$(ip address show $IFACE scope global |  awk '/inet / {split($2,var,"/"); print var[1]}')
TYPE="ALL"
LOCAL_PORT=0
REMOTE_IP=0
REMOTE_PORT=0

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
    $SUDO iptables-save -c | $SUDO tee /etc/sysconfig/iptables > /dev/null
  else
    $SUDO mkdir -p /etc/iptables
    $SUDO iptables-save -c | $SUDO tee /etc/iptables/rules.v4 > /dev/null
  fi
}

set_forward () {
    if [[ -z $($SUDO cat /etc/sysctl.conf | grep 'net.ipv4.ip_forward = 1') ]]; then
        echo "net.ipv4.ip_forward = 1" | $SUDO tee -a /etc/sysctl.conf > /dev/null
        $SUDO sysctl -p
    fi
}

forward () {
    set_forward
    if [ $TYPE == "ALL" ] || [ $TYPE == "TCP" ]
    then
        $SUDO iptables -t nat -A PREROUTING -p tcp --dport $LOCAL_PORT -j DNAT --to-destination $REMOTE_IP:$REMOTE_PORT  -m comment --comment "FORWARD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
        $SUDO iptables -t nat -A POSTROUTING -d $REMOTE_IP -p tcp --dport $REMOTE_PORT -j SNAT --to-source $INET -m comment --comment "BACKWARD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
        $SUDO iptables -I FORWARD -p tcp -d $REMOTE_IP --dport $REMOTE_PORT -j ACCEPT -m comment --comment "UPLOAD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
        $SUDO iptables -I FORWARD -p tcp -s $REMOTE_IP -j ACCEPT -m comment --comment "DOWNLOAD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
    fi
    if [ $TYPE == "ALL" ] || [ $TYPE == "UDP" ]
    then
        $SUDO iptables -t nat -A PREROUTING -p udp --dport $LOCAL_PORT -j DNAT --to-destination $REMOTE_IP:$REMOTE_PORT  -m comment --comment "FORWARD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
        $SUDO iptables -t nat -A POSTROUTING -d $REMOTE_IP -p udp --dport $REMOTE_PORT -j SNAT --to-source $INET -m comment --comment "BACKWARD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
        $SUDO iptables -I FORWARD -p udp -d $REMOTE_IP --dport $REMOTE_PORT -j ACCEPT -m comment --comment "UPLOAD-UDP $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
        $SUDO iptables -I FORWARD -p udp -s $REMOTE_IP -j ACCEPT -m comment --comment "DOWNLOAD-UDP $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
    fi
    save_iptables
}

monitor () {
    set_forward
    if [ $TYPE == "ALL" ] || [ $TYPE == "TCP" ]
    then
        $SUDO iptables -A INPUT -p tcp --dport $LOCAL_PORT -j ACCEPT -m comment --comment "UPLOAD $LOCAL_PORT->$REMOTE_IP"
        $SUDO iptables -A OUTPUT -p tcp  --sport $LOCAL_PORT -j ACCEPT -m comment --comment "DOWNLOAD $LOCAL_PORT->$REMOTE_IP"
    fi
    if [ $TYPE == "ALL" ] || [ $TYPE == "UDP" ]
    then
        $SUDO iptables -A INPUT -p udp --dport $LOCAL_PORT -j ACCEPT -m comment --comment "UPLOAD-UDP $LOCAL_PORT->$REMOTE_IP"
        $SUDO iptables -A OUTPUT -p udp --sport $LOCAL_PORT -j ACCEPT -m comment --comment "DOWNLOAD-UDP $LOCAL_PORT->$REMOTE_IP"
    fi
    save_iptables
}

list () {
    COMMENT="$LOCAL_PORT->"
    $SUDO iptables -nxvL | grep $COMMENT
    $SUDO iptables -t nat -nxvL | grep $COMMENT
}

list_all () {
    $SUDO iptables -nxvL INPUT | grep '\/\*.*\*\/$'
    $SUDO iptables -nxvL FORWARD | grep '\/\*.*\*\/$'
    $SUDO iptables -nxvL OUTPUT | grep '\/\*.*\*\/$'
}

reset () {
   COMMENT="$LOCAL_PORT->" 
   $SUDO iptables -L INPUT --line-numbers | grep $COMMENT | awk '{print $1}' | xargs -I{} sudo iptables -Z INPUT {}
   $SUDO iptables -L OUTPUT --line-numbers | grep $COMMENT | awk '{print $1}' | xargs -I{} sudo iptables -Z OUTPUT {}
   $SUDO iptables -L FORWARD --line-numbers | grep $COMMENT | awk '{print $1}' | xargs -I{} sudo iptables -Z FORWARD {}
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

for i in "$@"
do
case $i in
    -t=*|--type=*)
    TYPE="${i#*=}"
    shift
    ;;
esac
done

if [ ! $TYPE == "ALL" ] && [ ! $TYPE == "TCP" ] && [ ! $TYPE == "UDP" ] 
then
    echo "Unsupported forward type: $TYPE" && exit 1
fi

[ -n $1 ] && OPERATION=$1
[ -z $OPERATION ] && echo "No operation specified!" && exit 1
[ -n $2 ] && LOCAL_PORT=$2
[ -z $LOCAL_PORT ] && echo "Illegal port $PORT" && exit 1
[ -n $3 ] && REMOTE_IP=$3
if [ $OPERATION == "forward" ] && [ -z $REMOTE_IP ]
then
    echo "Unknow remote ip for operation $OPERATION" && exit 1
fi
[ -n $4 ] && REMOTE_PORT=$4
if [ $OPERATION == "forward" ] && [ -z $REMOTE_PORT ]
then
    echo "Unknow remote port for operation $OPERATION" && exit 1
fi

if [ $OPERATION == "forward" ]; then
    list
    delete
    forward
elif [ $OPERATION == "monitor" ]; then
    list
    delete
    monitor
elif [ $OPERATION == "list" ]; then
    list
elif [ $OPERATION == "list_all" ]; then
    list_all
elif [ $OPERATION == "delete" ]; then
    delete
elif [ $OPERATION == "reset" ]; then
    reset
else
    echo "Unrecognized command: $OPERATION"
    exit 1
fi
exit 0