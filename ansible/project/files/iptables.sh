#!/bin/bash

SUDO=$(if [ $(id -u $whoami) -gt 0 ]; then echo "sudo "; fi)
[ -z $SUDO ] || sudo -n true 2>/dev/null || (echo "Failed to use sudo" && exit 1)
TYPE="ALL"
LOCAL_PORT=65536
REMOTE_IP=""
REMOTE_PORT=65536

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
    [[ -d /run/systemd/system ]] && IS_SYSTEMD=1
    [[ -d /run/openrc ]] && IS_OPENRC=1
}

install_iptables () {
    iptables -V > /dev/null || $INSTALL iptables || ($UPDATE && $INSTALL iptables) || (echo "Failed to install iptables" && exit 1)
}

install_ip6tables () {
    ip6tables -V > /dev/null || $INSTALL ip6tables || ($UPDATE && $INSTALL ip6tables) || (echo "Failed to install ip6tables" && exit 1)
}

install_ip () {
    ip a > /dev/null && return 0
    if [[ $OS_FAMILY == "centos" ]]; then
        $INSTALL iproute || ($UPDATE && $INSTALL iproute) || (echo "Failed to install iproute" && exit 1)
    elif [[ $OS_FAMILY == "debian" ]]; then
        $INSTALL iproute2 || ($UPDATE && $INSTALL iproute2) || (echo "Failed to install iproute2" && exit 1)
    else
        echo "ip command not found" && exit 1
    fi
}

get_ips () {
    install_ip
    IFACE=$(ip route show | grep default | awk -F 'dev ' '{ print $2; }' | awk '{ print $1; }')
    INET=$(ip address show $IFACE scope global |  awk '/inet / {split($2,var,"/"); print var[1]}')
    INET=$(echo $INET | xargs -n 1 | grep -Eo "^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$" | sort -u)
    [[ -z $INET ]] && echo "No valid interface ipv4 addresses found" && exit 1
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
        IPT6_RESTORE_FILE=$IPT_PATH/ip6tables
    elif [[ $OS_FAMILY == "debian" ]]; then
        IPT_RESTORE_FILE=$IPT_PATH/rules.v4
        IPT6_RESTORE_FILE=$IPT_PATH/rules.v6
    fi
    if [[ -n $IPT_RESTORE_FILE && ! -f $IPT_RESTORE_FILE ]]; then
        $SUDO touch $IPT_RESTORE_FILE
    fi
    if [[ -n $IPT6_RESTORE_FILE && ! -f $IPT6_RESTORE_FILE ]]; then
        $SUDO touch $IPT6_RESTORE_FILE
    fi
}

install_ipt_service () {
    # /usr/lib/systemd/system/iptables.service (iptables-services)
    if [[ $OS_FAMILY == "centos" ]]; then
        RULE_PATH="/etc/sysconfig/iptables"
    # /lib/systemd/system/netfilter-persistent.service (iptables-persistent)
    elif [[ $OS_FAMILY == "debian" ]]; then
        RULE_PATH="/etc/iptables/rules.v4"
    fi
    [[ -z $RULE_PATH ]] && return 0
    $SUDO tee /etc/systemd/system/iptables-restore.service > /dev/null <<EOF
[Unit]
Description=Restore iptables rules by Aurora Admin Panel

[Service]
Type=oneshot
ExecStart=/bin/sh -c '/usr/sbin/iptables-restore -c < $RULE_PATH'

[Install]
WantedBy=multi-user.target
EOF
    check_ipt_restore_file
}

install_ipt6_service () {
    # /usr/lib/systemd/system/ip6tables.service (iptables-services)
    if [[ $OS_FAMILY == "centos" ]]; then
        RULE6_PATH="/etc/sysconfig/ip6tables"
    # /lib/systemd/system/netfilter-persistent.service (iptables-persistent)
    elif [[ $OS_FAMILY == "debian" ]]; then
        RULE6_PATH="/etc/iptables/rules.v6"
    fi
    [[ -z $RULE6_PATH ]] && return 0
    $SUDO tee /etc/systemd/system/ip6tables-restore.service > /dev/null <<EOF
[Unit]
Description=Restore ip6tables rules by Aurora Admin Panel

[Service]
Type=oneshot
ExecStart=/bin/sh -c '/usr/sbin/ip6tables-restore -c < $RULE6_PATH'

[Install]
WantedBy=multi-user.target
EOF
    check_ipt_restore_file
}

install_ipt_timer () {
    $SUDO tee /etc/systemd/system/iptables-check.service > /dev/null <<EOF
[Unit]
Description=Update iptables snat rules by Aurora Admin Panel

[Service]
ExecStart=/usr/local/bin/iptables.sh check
EOF
    $SUDO tee /etc/systemd/system/iptables-check.timer > /dev/null <<EOF
[Unit]
Description=Update iptables snat rules by Aurora Admin Panel

[Timer]
OnBootSec=60s
OnUnitActiveSec=60s
Unit=iptables-check.service

[Install]
WantedBy=timers.target
EOF
}

check_ipt_service () {
    if [[ $IS_SYSTEMD -eq 1 ]]; then
        ! systemctl is-enabled --quiet iptables-restore.service > /dev/null 2>&1 && install_ipt_service && \
        $SUDO systemctl daemon-reload && \
        $SUDO systemctl enable iptables-restore.service > /dev/null 2>&1
        # systemctl enable output is stderr, use 2>&1 redirection to ignore it
    fi
    # Not force to exit if the system does not use the systemd
    if [[ $IS_OPENRC -eq 1 ]]; then
        rc-update add iptables > /dev/null
    fi
}

check_ipt6_service () {
    if [[ $IS_SYSTEMD -eq 1 ]]; then
        ! systemctl is-enabled --quiet ip6tables-restore.service > /dev/null 2>&1 && install_ipt6_service && \
        $SUDO systemctl daemon-reload && \
        $SUDO systemctl enable ip6tables-restore.service > /dev/null 2>&1
        # systemctl enable output is stderr, use 2>&1 redirection to ignore it
    fi
    # Not force to exit if the system does not use the systemd
    if [[ $IS_OPENRC -eq 1 ]]; then
        rc-update add ip6tables > /dev/null
    fi
}

check_ipt_timer () {
    [[ $IS_SYSTEMD -ne 1 ]] && return 0
    ! systemctl is-enabled --quiet iptables-check.timer > /dev/null 2>&1 && install_ipt_timer && \
    $SUDO systemctl daemon-reload && \
    $SUDO systemctl enable iptables-check.timer > /dev/null 2>&1 && \
    $SUDO systemctl start iptables-check.timer > /dev/null 2>&1
}

save_iptables () {
    check_ipt_restore_file
    if [[ $OS_FAMILY == "centos" || $OS_FAMILY == "debian" ]]; then
        [[ -f $IPT_RESTORE_FILE ]] && $SUDO iptables-save -c | $SUDO tee $IPT_RESTORE_FILE > /dev/null
        [[ -f $IPT6_RESTORE_FILE ]] && $SUDO ip6tables-save -c | $SUDO tee $IPT6_RESTORE_FILE > /dev/null
    elif [[ $IS_OPENRC -eq 1 ]]; then
        # /etc/iptables/rules-save
        /etc/init.d/iptables save > /dev/null
        # /etc/iptables/rules6-save
        /etc/init.d/ip6tables save > /dev/null
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
    [[ $(cat /proc/sys/net/ipv4/ip_forward) -ne 1 ]] && echo 1 | $SUDO tee /proc/sys/net/ipv4/ip_forward
}

forward () {
    set_forward
    if [ $TYPE == "ALL" ] || [ $TYPE == "TCP" ]
    then
        for SNATIP in $INET; do
            $SUDO iptables -t nat -A POSTROUTING -d $REMOTE_IP -p tcp --dport $REMOTE_PORT -j SNAT --to-source $SNATIP -m comment --comment "BACKWARD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
        done
        $SUDO iptables -t nat -A PREROUTING -p tcp --dport $LOCAL_PORT -j DNAT --to-destination $REMOTE_IP:$REMOTE_PORT  -m comment --comment "FORWARD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
        # for ipt port traffic monitor
        $SUDO iptables -I FORWARD -p tcp -d $REMOTE_IP --dport $REMOTE_PORT -j ACCEPT -m comment --comment "UPLOAD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
        $SUDO iptables -I FORWARD -p tcp -s $REMOTE_IP -j ACCEPT -m comment --comment "DOWNLOAD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
    fi
    if [ $TYPE == "ALL" ] || [ $TYPE == "UDP" ]
    then
        for SNATIP in $INET; do
            $SUDO iptables -t nat -A POSTROUTING -d $REMOTE_IP -p udp --dport $REMOTE_PORT -j SNAT --to-source $SNATIP -m comment --comment "BACKWARD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
        done
        $SUDO iptables -t nat -A PREROUTING -p udp --dport $LOCAL_PORT -j DNAT --to-destination $REMOTE_IP:$REMOTE_PORT  -m comment --comment "FORWARD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
        # for ipt port traffic monitor
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
        $SUDO ip6tables -A INPUT -p tcp --dport $LOCAL_PORT -j ACCEPT -m comment --comment "UPLOAD $LOCAL_PORT->$REMOTE_IP"
        $SUDO ip6tables -A OUTPUT -p tcp  --sport $LOCAL_PORT -j ACCEPT -m comment --comment "DOWNLOAD $LOCAL_PORT->$REMOTE_IP"
    fi
    if [ $TYPE == "ALL" ] || [ $TYPE == "UDP" ]
    then
        $SUDO iptables -A INPUT -p udp --dport $LOCAL_PORT -j ACCEPT -m comment --comment "UPLOAD-UDP $LOCAL_PORT->$REMOTE_IP"
        $SUDO iptables -A OUTPUT -p udp --sport $LOCAL_PORT -j ACCEPT -m comment --comment "DOWNLOAD-UDP $LOCAL_PORT->$REMOTE_IP"
        $SUDO ip6tables -A INPUT -p udp --dport $LOCAL_PORT -j ACCEPT -m comment --comment "UPLOAD-UDP $LOCAL_PORT->$REMOTE_IP"
        $SUDO ip6tables -A OUTPUT -p udp --sport $LOCAL_PORT -j ACCEPT -m comment --comment "DOWNLOAD-UDP $LOCAL_PORT->$REMOTE_IP"
    fi
    save_iptables
}

list () {
    COMMENT="$LOCAL_PORT->"
    $SUDO iptables -nxvL | grep $COMMENT
    $SUDO iptables -t nat -nxvL | grep $COMMENT
    $SUDO ip6tables -nxvL | grep $COMMENT
    $SUDO ip6tables -t nat -nxvL | grep $COMMENT
}

list_all () {
    $SUDO iptables -nxvL INPUT | grep '\/\*.*\*\/$'
    $SUDO iptables -nxvL FORWARD | grep '\/\*.*\*\/$'
    $SUDO iptables -nxvL OUTPUT | grep '\/\*.*\*\/$'
    $SUDO ip6tables -nxvL INPUT | grep '\/\*.*\*\/$'
    $SUDO ip6tables -nxvL FORWARD | grep '\/\*.*\*\/$'
    $SUDO ip6tables -nxvL OUTPUT | grep '\/\*.*\*\/$'
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
    while [[ ! -z "$($SUDO ip6tables -S | grep $COMMENT)" ]]
    do
        $SUDO ip6tables -S | grep $COMMENT | awk -v SUDO="$SUDO" '{$1="";$COMMEND=SUDO" ip6tables -D "$0; system($COMMEND)}'
    done
    while [[ ! -z "$($SUDO iptables -t nat -S | grep $COMMENT)" ]]
    do
        $SUDO iptables -t nat -S | grep $COMMENT | awk -v SUDO="$SUDO" '{$1="";$COMMEND=SUDO" iptables -t nat -D "$0; system($COMMEND)}'
    done
    while [[ ! -z "$($SUDO ip6tables -t nat -S | grep $COMMENT)" ]]
    do
        $SUDO ip6tables -t nat -S | grep $COMMENT | awk -v SUDO="$SUDO" '{$1="";$COMMEND=SUDO" ip6tables -t nat -D "$0; system($COMMEND)}'
    done
    save_iptables
}

check () {
    [[ -z $INET ]] && echo "No valid interface ipv4 addresses found" && exit 1
    # snat update only support one ip for now.
    [[ $(echo $INET | awk '{print NF}') -gt 1 ]] && return 0
    SNAT_RULES=$(iptables -t nat -nL POSTROUTING --line-number | grep -E "BACKWARD [[:digit:]]+->" | awk '{ printf("%s:%s:%s:%s\n", $11,$13,$1,$3); }')
    for SNAT_RULE in $SNAT_RULES; do
        OUTIP=$(echo $SNAT_RULE | awk -F : '{print $4}')
        if [[ -n $OUTIP && $INET != $OUTIP ]]; then
            LOCAL_PORT=$(echo $SNAT_RULE | awk -F '->' '{print $1}')
            REMOTE_IP=$(echo $SNAT_RULE | awk -F '->|:' '{print $2}')
            REMOTE_PORT=$(echo $SNAT_RULE | awk -F '->|:| ' '{print $3}')
            IPT_NUM=$(echo $SNAT_RULE | awk -F '->|:| ' '{print $6}')
            TYPE=$(echo $SNAT_RULE | awk -F '->|:| ' '{print $7}')
            if [[ -n $LOCAL_PORT && -n $REMOTE_IP && -n $REMOTE_PORT && -n $IPT_NUM && -n $TYPE ]]; then
                $SUDO iptables -t nat -R POSTROUTING $IPT_NUM -d $REMOTE_IP -p $TYPE --dport $REMOTE_PORT -j SNAT --to-source $INET -m comment --comment "BACKWARD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT"
            fi
        fi
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

[[ -n $1 ]] && OPERATION=$1
[[ -z $OPERATION ]] && echo "No operation specified" && exit 1
[[ -n $2 ]] && LOCAL_PORT=$2
[[ $OPERATION != "list_all" && "$OPERATION" != "check" && ($LOCAL_PORT -ge 65536 || $LOCAL_PORT -lt 0) ]] && \
echo "Unknow local port for operation $OPERATION" && exit 1
[[ -n $3 ]] && REMOTE_IP=$3
[[ $OPERATION == "forward" && -z $REMOTE_IP ]] && echo "Unknow remote ip for operation $OPERATION" && exit 1
[[ -n $4 ]] && REMOTE_PORT=$4
[[ $OPERATION == "forward" && ($REMOTE_PORT -ge 65536 || $REMOTE_PORT -lt 0) ]] && \
echo "Unknow remote port for operation $OPERATION" && exit 1

check_system
install_iptables
install_ip6tables
disable_firewall
check_ipt_service
check_ipt6_service
check_ipt_timer
if [[ $OPERATION == "forward" ]]; then
    # for ipt/app -> ipt traffic get
    list
    delete
    delete_service
    get_ips
    forward
# for app port traffic monitor
elif [[ $OPERATION == "monitor" ]]; then
    # for ipt/app -> ipt traffic get
    list
    delete
    monitor
# for clean port traffic get
elif [[ $OPERATION == "list" ]]; then
    list
# for traffic schedule task
elif [[ $OPERATION == "list_all" ]]; then
    list_all
elif [[ $OPERATION == "delete_service" ]]; then
    delete_service
elif [[ $OPERATION == "delete" ]]; then
    delete
elif [[ $OPERATION == "reset" ]]; then
    reset
elif [ $OPERATION == "check" ]; then
    get_ips
    check
else
    echo "Unrecognized command: $OPERATION"
    exit 1
fi
exit 0
