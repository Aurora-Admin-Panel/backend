#!/bin/bash

SUDO=$(if [ $(id -u $whoami) -gt 0 ]; then echo "sudo "; fi)
[ -z $SUDO ] || sudo -n true 2>/dev/null || (echo "Failed to use sudo" && exit 1)
IFACE=$(ip route show | grep default | grep -Po '(?<=dev )(\w+)')
INET=$(ip address show $IFACE scope global |  awk '/inet / {split($2,var,"/"); print var[1]}')
# Only support one ip now
INET=$(echo $INET | grep -Po "^(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|[1-9])(\.(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|\d)){3}$")
[ -z $INET ] && echo "No ip address found" && exit 1
TYPE="ALL"
LOCAL_PORT=0
REMOTE_IP=0
REMOTE_PORT=0

check_system () {
    source '/etc/os-release'
    if [ $ID = "centos" ]; then
        OS_FAMILY="centos"
        UPDATE="$SUDO yum makecache -y"
        INSTALL="$SUDO yum install -y iptables"
    elif  [ $ID = "debian" ] || [ $ID = "ubuntu" ]; then
        OS_FAMILY="debian"
        UPDATE="$SUDO apt update -y"
        INSTALL="$SUDO apt install -y iptables"
    else
        echo -e "System $ID ${VERSION_ID} is not supported now"
        exit 1
    fi
}

install_ipt () {
    iptables -V || $INSTALL || ($UPDATE && $INSTALL)
    if [ $? -ne 0 ]; then
        echo -e "Failed to install iptables"
        exit 1
    fi
}

disable_firewall () {
    if [ $OS_FAMILY = "centos" ]; then
        if [[ -n $(systemctl list-unit-files --all | grep "firewalld.service" | grep "enabled") ]]; then
            $SUDO systemctl stop firewalld.service && \
            $SUDO systemctl disable firewalld.service
	fi
    else
        if [[ -n $(systemctl list-unit-files --all | grep "ufw.service" | grep "enabled") ]]; then
            $SUDO systemctl stop ufw.service && \
            $SUDO systemctl disable ufw.service
	fi
    fi
}

check_ipt_restore_file () {
    if [ $OS_FAMILY = "centos" ]; then
        IPT_PATH="/etc/sysconfig"
    else
        IPT_PATH="/etc/iptables"
    fi
    if [ ! -d $IPT_PATH ]; then
        $SUDO mkdir -p $IPT_PATH
    fi
    if [ $OS_FAMILY = "centos" ]; then
        IPT_RESTORE_FILE=$IPT_PATH/iptables
    else
        IPT_RESTORE_FILE=$IPT_PATH/rules.v4
    fi
    if [ ! -f $IPT_RESTORE_FILE ]; then
        $SUDO touch $IPT_RESTORE_FILE
    fi
}

install_ipt_service () {
    IPT_SERVICE_PATH="/etc/systemd/system/iptables-restore.service"
    if [ ! -f $IPT_SERVICE_PATH ]; then
        $SUDO touch $IPT_SERVICE_PATH
    fi
    if [ $OS_FAMILY = "centos" ]; then
        $SUDO cat > $IPT_SERVICE_PATH <<EOF
[Unit]
Description=Restore iptables rule by Aurora Admin Panel

[Service]
Type=oneshot
ExecStart=/bin/sh -c '/usr/sbin/iptables-restore -c < /etc/sysconfig/iptables'

[Install]
WantedBy=multi-user.target
EOF
    else
        $SUDO cat > $IPT_SERVICE_PATH <<EOF
[Unit]
Description=Restore iptables rule by Aurora Admin Panel

[Service]
Type=oneshot
ExecStart=/bin/sh -c '/usr/sbin/iptables-restore -c < /etc/iptables/rules.v4'

[Install]
WantedBy=multi-user.target
EOF
    fi
    check_ipt_restore_file
}

check_ipt_service () {
    IPT_SERVICE="iptables-restore.service"
    if [[ -z $(systemctl list-unit-files --all | grep "$IPT_SERVICE" | grep "enabled") ]]; then
        install_ipt_service
    fi
    $SUDO systemctl daemon-reload && \
    $SUDO systemctl enable $IPT_SERVICE
    if [ $? -ne 0 ]; then
        echo -e "Failed to install iptables restore service"
        exit 1
    fi
}

save_iptables () {
    check_ipt_restore_file
    $SUDO iptables-save -c | $SUDO tee $IPT_RESTORE_FILE > /dev/null
}

set_forward () {
    if [[ -z $($SUDO cat /etc/sysctl.conf | grep "net.ipv4.ip_forward") ]]; then
        echo "net.ipv4.ip_forward = 1" | $SUDO tee -a /etc/sysctl.conf > /dev/null
    elif [[ -n $($SUDO cat /etc/sysctl.conf | grep "net.ipv4.ip_forward" | grep "0") ]]; then
        sed -i "s/.*net.ipv4.ip_forward.*/net.ipv4.ip_forward = 1/g" /etc/sysctl.conf > /dev/null
    fi
    $SUDO sysctl -p
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
   $SUDO iptables -L INPUT --line-numbers | grep $COMMENT | awk '{print $1}' | xargs -I{} $SUDO iptables -Z INPUT {}
   $SUDO iptables -L OUTPUT --line-numbers | grep $COMMENT | awk '{print $1}' | xargs -I{} $SUDO iptables -Z OUTPUT {}
   $SUDO iptables -L FORWARD --line-numbers | grep $COMMENT | awk '{print $1}' | xargs -I{} $SUDO iptables -Z FORWARD {}
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

check_system
install_ipt
disable_firewall
check_ipt_service
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
