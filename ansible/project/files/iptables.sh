#!/bin/bash

SUDO=$(if [ $(id -u $whoami) -gt 0 ]; then echo "sudo "; fi)
[ -z $SUDO ] || sudo -n true 2>/dev/null || (echo "Failed to use sudo" && exit 1)
IFACE=$(ip route show | grep default | grep -Po '(?<=dev )(\w+)')
INET=$(ip address show $IFACE scope global |  awk '/inet / {split($2,var,"/"); print var[1]}')
# Only support one ip now
INET=$(echo $INET | awk '{print $1}' | grep -Po "^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$")
[ -z $INET ] && echo "No valid interface ipv4 addresses found" && exit 1
TYPE="ALL"
LOCAL_PORT=0
REMOTE_IP=0
REMOTE_PORT=0

check_system () {
    source '/etc/os-release'
    if [[ $ID = "centos" ]]; then
        OS_FAMILY="centos"
        UPDATE="$SUDO yum makecache -y"
        INSTALL="$SUDO yum install -y iptables"
    elif [[ $ID = "debian" || $ID = "ubuntu" ]]; then
        OS_FAMILY="debian"
        UPDATE="$SUDO apt update -y"
        INSTALL="$SUDO apt install -y iptables"
    else
        echo -e "System $ID ${VERSION_ID} is not supported now"
        exit 1
    fi
}

install_ipt () {
    iptables -V > /dev/null || $INSTALL || ($UPDATE && $INSTALL)
    if [ $? -ne 0 ]; then
        echo -e "Failed to install iptables"
        exit 1
    fi
}

disable_firewall () {
    # centos firewall
    systemctl is-active --quiet firewalld.service > /dev/null 2>&1 && $SUDO systemctl stop firewalld.service
    systemctl is-enabled --quiet firewalld.service > /dev/null 2>&1 && $SUDO systemctl disable firewalld.service
    # debian / ubuntu firewall
    systemctl is-active --quiet ufw.service > /dev/null 2>&1 && $SUDO systemctl stop ufw.service
    systemctl is-enabled --quiet ufw.service > /dev/null 2>&1 && $SUDO systemctl disable ufw.service
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
    if [ $OS_FAMILY = "centos" ]; then
        RULE_PATH="/etc/sysconfig/iptables"
    elif [ $OS_FAMILY = "debian" ]; then
        RULE_PATH="/etc/iptables/rules.v4"
    fi
    $SUDO cat > /etc/systemd/system/iptables-restore.service <<EOF
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

install_ipt_out_ip_check_service () {
    $SUDO cat > /etc/systemd/system/iptables-outipcheck.service <<EOF
[Unit]
Description=iptables out ip changed check by Aurora Admin Panel

[Service]
ExecStart=/usr/local/bin/iptables.sh outipcheck 0

EOF
$SUDO cat > /etc/systemd/system/iptables-outipcheck.timer <<EOF
[Unit]
Description=iptables out ip changed check timer by Aurora Admin Panel

[Timer]
OnUnitActiveSec=60s
Unit=iptables-outipcheck.service

[Install]
WantedBy=multi-user.target
EOF
$SUDO systemctl daemon-reload
$SUDO systemctl enable iptables-outipcheck.service
$SUDO systemctl start iptables-outipcheck.service
$SUDO systemctl enable iptables-outipcheck.timer
$SUDO systemctl start iptables-outipcheck.timer
}

check_ipt_service () {
    # add out ip changed check timer for iptable port forward rules
    ! systemctl is-enabled --quiet iptables-outipcheck.service > /dev/null 2>&1 && install_ipt_out_ip_check_service
    # service to support auto save iptable forward rules
    ! systemctl is-enabled --quiet iptables-restore.service > /dev/null 2>&1 && install_ipt_service \
    $SUDO systemctl daemon-reload && \
    $SUDO systemctl enable iptables-restore.service
    ! systemctl is-enabled --quiet iptables-restore.service && \
    echo -e "Failed to install iptables restore service" && exit 1
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
    $SUDO sysctl -p > /dev/null
}

forward () {
    set_forward
    if [ $TYPE == "ALL" ] || [ $TYPE == "TCP" ]
    then
        $SUDO iptables -t nat -A PREROUTING -p tcp --dport $LOCAL_PORT -j DNAT --to-destination $REMOTE_IP:$REMOTE_PORT  -m comment --comment "FORWARD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT" && \
        $SUDO iptables -t nat -A POSTROUTING -d $REMOTE_IP -p tcp --dport $REMOTE_PORT -j SNAT --to-source $INET -m comment --comment "BACKWARD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT" && \
        $SUDO iptables -I FORWARD -p tcp -d $REMOTE_IP --dport $REMOTE_PORT -j ACCEPT -m comment --comment "UPLOAD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT" && \
        $SUDO iptables -I FORWARD -p tcp -s $REMOTE_IP -j ACCEPT -m comment --comment "DOWNLOAD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT" || (echo "Failed to create tcp forward rules" && exit 1)
    fi
    if [ $TYPE == "ALL" ] || [ $TYPE == "UDP" ]
    then
        $SUDO iptables -t nat -A PREROUTING -p udp --dport $LOCAL_PORT -j DNAT --to-destination $REMOTE_IP:$REMOTE_PORT  -m comment --comment "FORWARD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT" && \
        $SUDO iptables -t nat -A POSTROUTING -d $REMOTE_IP -p udp --dport $REMOTE_PORT -j SNAT --to-source $INET -m comment --comment "BACKWARD $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT" && \
        $SUDO iptables -I FORWARD -p udp -d $REMOTE_IP --dport $REMOTE_PORT -j ACCEPT -m comment --comment "UPLOAD-UDP $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT" && \
        $SUDO iptables -I FORWARD -p udp -s $REMOTE_IP -j ACCEPT -m comment --comment "DOWNLOAD-UDP $LOCAL_PORT->$REMOTE_IP:$REMOTE_PORT" || (echo "Failed to create udp forward rules" && exit 1)
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

outipcheck () {
    # echo "start out interface ip check, now is: $INET"
    for snat_info in $(iptables  -t  nat  -nL --line-number|grep SNAT|grep BACKWARD|awk '{printf("%s:%s\n",$11,$13)}');do
        outip=$(echo $snat_info|awk -F: '{print $4}')
        if [ -n "$outip" ]; then
        if [ "$INET" != $outip ]; then
            in_port=$(echo $snat_info|awk -F'->' '{print $1}')
            target_ip=$(echo $snat_info|awk -F'->|:' '{print $2}')
            target_port=$(echo $snat_info|awk -F'->|:| ' '{print $3}')
            if [[ -n $in_port && -n $target_ip && -n $target_port ]]; then
                echo "fix outip from $outip to $INET, $in_port -> $target_ip:$target_port"
                /usr/local/bin/iptables.sh forward $in_port $target_ip $target_port
            fi
        fi
        fi
    done
    # echo "end out interface ip check, now is: $INET"
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
REMOTE_IP=$(echo $REMOTE_IP | grep -Po "^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$")
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
elif [ $OPERATION == "outipcheck" ]; then
    outipcheck
else
    echo "Unrecognized command: $OPERATION"
    exit 1
fi
exit 0
