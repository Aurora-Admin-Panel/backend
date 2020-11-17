#!/bin/bash

SUDO=$(if [ $(id -u $whoami) -gt 0 ]; then echo "sudo "; fi)
IFACE=$(ip route show | grep default | awk '{print $5}')
INET=$(ip address show $IFACE scope global |  awk '/inet / {split($2,var,"/"); print var[1]}')
TYPE="ALL"
LOCAL_PORT=0
REMOTE_IP=0
REMOTE_PORT=0

set_forward () {
    if [[ -z $($SUDO cat /etc/sysctl.conf | grep 'net.ipv4.ip_forward = 1') ]]; then
        echo "net.ipv4.ip_forward = 1" | $SUDO tee -a /etc/sysctl.conf
        $SUDO sysctl -p
    fi
}

forward () {
    set_forward
    if [ $TYPE == "ALL" ] || [ $TYPE == "TCP" ]
    then
        $SUDO iptables -t nat -A PREROUTING -p tcp --dport $LOCAL_PORT -j DNAT --to-destination $REMOTE_IP:$REMOTE_PORT  -m comment --comment "FORWARD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
        $SUDO iptables -t nat -A POSTROUTING -d $REMOTE_IP -p tcp --dport $REMOTE_PORT -j SNAT --to-source $INET -m comment --comment "BACKWARD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
        $SUDO iptables -A FORWARD -p tcp -d $REMOTE_IP --dport $REMOTE_PORT -j ACCEPT -m comment --comment "UPLOAD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
        $SUDO iptables -A FORWARD -p tcp -s $REMOTE_IP -j ACCEPT -m comment --comment "DOWNLOAD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
    fi
    if [ $TYPE == "ALL" ] || [ $TYPE == "UDP" ]
    then
        $SUDO iptables -t nat -A PREROUTING -p udp --dport $LOCAL_PORT -j DNAT --to-destination $REMOTE_IP:$REMOTE_PORT  -m comment --comment "FORWARD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
        $SUDO iptables -t nat -A POSTROUTING -d $REMOTE_IP -p udp --dport $REMOTE_PORT -j SNAT --to-source $INET -m comment --comment "BACKWARD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
        $SUDO iptables -A FORWARD -p udp -d $REMOTE_IP --dport $REMOTE_PORT -j ACCEPT -m comment --comment "UPLOAD-UDP $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
        $SUDO iptables -A FORWARD -p udp -s $REMOTE_IP -j ACCEPT -m comment --comment "DOWNLOAD-UDP $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
    fi
    $SUDO iptables-save
}

monitor () {
    set_forward
    if [ $TYPE == "ALL" ] || [ $TYPE == "TCP" ]
    then
        $SUDO iptables -A INPUT -p tcp --dport $LOCAL_PORT -m comment --comment "UPLOAD $LOCAL_PORT->$REMOTE_IP"
        $SUDO iptables -A OUTPUT -p tcp  --sport $LOCAL_PORT -m comment --comment "DOWNLOAD $LOCAL_PORT->$REMOTE_IP"
    fi
    if [ $TYPE == "ALL" ] || [ $TYPE == "UDP" ]
    then
        $SUDO iptables -A INPUT -p udp --dport $LOCAL_PORT -m comment --comment "UPLOAD-UDP $LOCAL_PORT->$REMOTE_IP"
        $SUDO iptables -A OUTPUT -p udp --sport $LOCAL_PORT -m comment --comment "DOWNLOAD-UDP $LOCAL_PORT->$REMOTE_IP"
    fi
    $SUDO iptables-save
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
if [ ! $OPERATION == "forward" ] && [ ! $OPERATION == "monitor" ] && [ ! $OPERATION == "list" ] && [ ! $OPERATION == "delete" ]
then
    echo "Unsupported opertation: $OPERATION" && exit 1
fi
[ -n $2 ] && LOCAL_PORT=$2
[ -z $LOCAL_PORT ] && echo "Illegal port $PORT" && exit 1
[ -n $3 ] && REMOTE_IP=$3
if ([ $OPERATION == "forward" ] || [ $OPERATION == "monitor" ]) && [ -z $REMOTE_IP ]
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
elif [ $OPERATION == "delete" ]; then
    delete
else
    echo "Unrecognized command: $OPERATION"
fi