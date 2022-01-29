#!/bin/bash

SUDO=$(if [ $(id -u $whoami) -gt 0 ]; then echo "sudo "; fi)
[ -z $SUDO ] || sudo -n true 2>/dev/null || (echo "Failed to use sudo" && exit 1)
TYPE="ALL"
LOCAL_PORT=0
REMOTE_IP=0
REMOTE_PORT=0

check_system () {
    source '/etc/os-release'
    if [[ $ID == "centos" ]]; then
        OS_FAMILY="centos"
        UPDATE="$SUDO yum makecache -y"
        INSTALL="$SUDO yum install -y"
    elif [[ $ID == "debian" || $ID == "ubuntu" ]]; then
        OS_FAMILY="debian"
        UPDATE="$SUDO apt update -y"
        INSTALL="$SUDO apt install -y --no-install-recommends"
    elif [[ $ID == "alpine" ]]; then
        OS_FAMILY="alpine"
        UPDATE="$SUDO apk update"
        INSTALL="$SUDO apk add --no-cache"
    fi
    # Not force to exit if the system is not supported
    systemctl --version > /dev/null 2>&1 && IS_SYSTEMD=1
}

get_ips () {
    IFACE=$(ip route show | grep default | awk -F 'dev ' '{ print $2; }' | awk '{ print $1; }')
    INET=$(ip address show $IFACE scope global |  awk '/inet / {split($2,var,"/"); print var[1]}')
    INET=$(echo $INET | xargs -n 1 | grep -Eo "^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$" | sort -u)
    [ -z $INET ] && echo "No valid interface ipv4 addresses found" && exit 1
}

install_deps () {
    iptables -V > /dev/null || $INSTALL iptables || ($UPDATE && $INSTALL iptables) || (echo "Failed to install iptables" && exit 1)
    ip a > /dev/null && return 0
    if [[ $OS_FAMILY == "centos" ]]; then
        $INSTALL iproute || ($UPDATE && $INSTALL iproute) || (echo "Failed to install iproute" && exit 1)
    elif [[ $OS_FAMILY == "debian" ]]; then
        $INSTALL iproute2 || ($UPDATE && $INSTALL iproute2) || (echo "Failed to install iproute2" && exit 1)
    else
        echo "ip command not found" && exit 1
    fi
}

delete_service () {
    [[ -z $1 ]] && SERVICE="aurora@${LOCAL_PORT}.service" || SERVICE=$1
    if [[ $IS_SYSTEMD -eq 1 ]]; then
        systemctl is-active --quiet $SERVICE > /dev/null 2>&1 && $SUDO systemctl stop $SERVICE
        systemctl is-enabled --quiet $SERVICE > /dev/null 2>&1 && $SUDO systemctl disable $SERVICE
    fi
}

disable_firewall () {
    # centos firewall
    delete_service firewalld.service
    # debian / ubuntu firewall
    delete_service ufw.service
}

check_ipt_restore_file () {
    if [[ $OS_FAMILY == "centos" ]]; then
        IPT_PATH="/etc/sysconfig"
    elif [[ $OS_FAMILY == "debian" ]]; then
        IPT_PATH="/etc/iptables"
    fi
    if [[ -n $IPT_PATH && ! -d $IPT_PATH ]]; then
        $SUDO mkdir -p $IPT_PATH
    fi
    if [[ $OS_FAMILY == "centos" ]]; then
        IPT_RESTORE_FILE=$IPT_PATH/iptables
    elif [[ $OS_FAMILY == "debian" ]]; then
        IPT_RESTORE_FILE=$IPT_PATH/rules.v4
    fi
    if [[ -n $IPT_RESTORE_FILE && ! -f $IPT_RESTORE_FILE ]]; then
        $SUDO touch $IPT_RESTORE_FILE
    fi
}

install_ipt_service () {
    if [[ $OS_FAMILY == "centos" ]]; then
        RULE_PATH="/etc/sysconfig/iptables"
    elif [[ $OS_FAMILY == "debian" ]]; then
        RULE_PATH="/etc/iptables/rules.v4"
    fi
    [[ ! -z $RULE_PATH ]] && $SUDO cat > /etc/systemd/system/iptables-restore.service <<EOF
[Unit]
Description=Restore iptables rule by Aurora Admin Panel

[Service]
Type=oneshot
ExecStart=/bin/sh -c '/usr/sbin/iptables-restore -c < $RULE_PATH'

[Install]
WantedBy=multi-user.target
EOF
    check_ipt_restore_file
}

check_ipt_service () {
    if [[ $IS_SYSTEMD -eq 1 ]]; then
        ! systemctl is-enabled --quiet iptables-restore.service > /dev/null 2>&1 && install_ipt_service \
        $SUDO systemctl daemon-reload && \
        $SUDO systemctl enable iptables-restore.service
        ! systemctl is-enabled --quiet iptables-restore.service && \
        echo "Failed to install iptables restore service"
    fi
    # Not force to exit if the system does not use the systemd
    if [[ $OS_FAMILY == "alpine" ]]; then
        rc-update add iptables > /dev/null
    fi
}

save_iptables () {
    check_ipt_restore_file
    if [[ $OS_FAMILY == "centos" || $OS_FAMILY == "debian" ]]; then
        [[ -f $IPT_RESTORE_FILE ]] && $SUDO iptables-save -c | $SUDO tee $IPT_RESTORE_FILE > /dev/null
    elif [[ $OS_FAMILY == "alpine" ]]; then
        /etc/init.d/iptables save > /dev/null
    fi
}

set_forward () {
    [[ $(cat /proc/sys/net/ipv4/ip_forward) -eq 1 ]] && return 0
    if [[ -z $($SUDO cat /etc/sysctl.conf | grep "net.ipv4.ip_forward") ]]; then
        echo "net.ipv4.ip_forward = 1" | $SUDO tee -a /etc/sysctl.conf > /dev/null
    else
        sed -i "s/.*net.ipv4.ip_forward.*/net.ipv4.ip_forward = 1/g" /etc/sysctl.conf > /dev/null
    fi
    $SUDO sysctl -p > /dev/null
    # check and make sure ip_forward enabled
    [[ $(cat /proc/sys/net/ipv4/ip_forward) -ne 1 ]] && echo "Cannot enable ipv4 forward for iptables" && exit 1
}

forward () {
    set_forward || exit 1
    if [ $TYPE == "ALL" ] || [ $TYPE == "TCP" ]
    then
        for SNATIP in $INET; do
            $SUDO iptables -t nat -A POSTROUTING -d $REMOTE_IP -p tcp --dport $REMOTE_PORT -j SNAT --to-source $SNATIP -m comment --comment "BACKWARD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
        done
        $SUDO iptables -t nat -A PREROUTING -p tcp --dport $LOCAL_PORT -j DNAT --to-destination $REMOTE_IP:$REMOTE_PORT  -m comment --comment "FORWARD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
        $SUDO iptables -I FORWARD -p tcp -d $REMOTE_IP --dport $REMOTE_PORT -j ACCEPT -m comment --comment "UPLOAD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
        $SUDO iptables -I FORWARD -p tcp -s $REMOTE_IP -j ACCEPT -m comment --comment "DOWNLOAD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
    fi
    if [ $TYPE == "ALL" ] || [ $TYPE == "UDP" ]
    then
        for SNATIP in $INET; do
            $SUDO iptables -t nat -A POSTROUTING -d $REMOTE_IP -p udp --dport $REMOTE_PORT -j SNAT --to-source $SNATIP -m comment --comment "BACKWARD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
        done
        $SUDO iptables -t nat -A PREROUTING -p udp --dport $LOCAL_PORT -j DNAT --to-destination $REMOTE_IP:$REMOTE_PORT  -m comment --comment "FORWARD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
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
    save_iptables
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
    save_iptables
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

[[ -n $1 ]] && OPERATION=$1
[[ -z $OPERATION ]] && echo "No operation specified" && exit 1
[[ -n $2 ]] && LOCAL_PORT=$2
[[ $OPERATION != "list_all" && -z $LOCAL_PORT ]] && echo "Unknow local port for operation $OPERATION" && exit 1
[[ -n $3 ]] && REMOTE_IP=$3
REMOTE_IP=$(echo $REMOTE_IP | grep -Eo "^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$")
[[ $OPERATION == "forward" && -z $REMOTE_IP ]] && echo "Unknow remote ip for operation $OPERATION" && exit 1
[[ -n $4 ]] && REMOTE_PORT=$4
[[ $OPERATION == "forward" && -z $REMOTE_PORT ]] && echo "Unknow remote port for operation $OPERATION" && exit 1

check_system
install_deps
disable_firewall
check_ipt_service
if [[ $OPERATION == "forward" ]]; then
    list
    delete
    delete_service
    get_ips
    forward
elif [[ $OPERATION == "monitor" ]]; then
    list
    delete
    monitor
elif [[ $OPERATION == "list" ]]; then
    list
elif [[ $OPERATION == "list_all" ]]; then
    list_all
elif [[ $OPERATION == "delete_service" ]]; then
    delete_service
elif [[ $OPERATION == "delete" ]]; then
    delete
elif [[ $OPERATION == "reset" ]]; then
    reset
else
    echo "Unrecognized command: $OPERATION"
    exit 1
fi
exit 0
