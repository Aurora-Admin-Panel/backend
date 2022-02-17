#! /bin/sh

check_system () {
    [ ! -f /etc/os-release ] && return 0
    source /etc/os-release
    if [ $ID = "centos" ]; then
        OS_FAMILY="centos"
        UPDATE="yum makecache -y"
        INSTALL="yum install -y"
    elif [ $ID = "debian" ] || [ $ID = "ubuntu" ]; then
        OS_FAMILY="debian"
        UPDATE="apt update -y"
        INSTALL="apt install -y --no-install-recommends"
    elif [ $ID = "alpine" ]; then
        OS_FAMILY="alpine"
        UPDATE="apk update"
        INSTALL="apk add --no-cache"
    fi
}

install_bash () {
    echo "Checking bash ..."
    bash --version > /dev/null 2>&1 && return 0
    [ -z $OS_FAMILY ] && return 0
    echo "Installing bash ..."
    $INSTALL bash || ($UPDATE && $INSTALL bash) || (echo "Failed to install bash!" && return 1)
}

install_python3 () {
    echo "Checking python3 ..."
    python3 -V > /dev/null 2>&1 && return 0
    [ -z $OS_FAMILY ] && return 0
    echo "Installing python3 ..."
    $INSTALL python3 || ($UPDATE && $INSTALL python3) || (echo "Failed to install python3!" && return 1)
}

install_python2 () {
    echo "Checking python2 ..."
    (python -V > /dev/null 2>&1 || python2 -V > /dev/null 2>&1) && return 0
    [ -z $OS_FAMILY ] && return 0
    echo "Installing python2 ..."
    if [ $OS_FAMILY = "centos" ] || [ $OS_FAMILY = "debian" ]; then
        $INSTALL python || ($UPDATE && $INSTALL python) || echo "Failed to install python2!"
    elif [ $OS_FAMILY = "alpine" ]; then
        $INSTALL python2 || ($UPDATE && $INSTALL python2) || echo "Failed to install python2!"
    fi
}

install_iptables () {
    echo "Checking iptables ..."
    iptables -V > /dev/null 2>&1 && return 0
    [ -z $OS_FAMILY ] && return 0
    echo "Installing iptables ..."
    $INSTALL iptables || ($UPDATE && $INSTALL iptables) || echo "Failed to install iptables!"
}

install_iproute () {
    echo "Checking iproute ..."
    ip a > /dev/null 2>&1 && return 0
    echo "Installing iproute ..."
    if [ $OS_FAMILY = "centos" ]; then
        $INSTALL iproute || ($UPDATE && $INSTALL iproute) || echo "Failed to install iproute!"
    elif [ $OS_FAMILY = "debian" ]; then
        $INSTALL iproute2 || ($UPDATE && $INSTALL iproute2) || echo "Failed to install iproute2!"
    fi
}

install_systemd () {
    echo "Checking systemd ..."
    systemctl --version > /dev/null 2>&1 && return 0
    [ $OS_FAMILY != "centos" ] && [ $OS_FAMILY != "debian" ] && return 0
    echo "Installing systemd ..."
    $INSTALL systemd || ($UPDATE && $INSTALL systemd) || echo "Failed to install systemd!"
}

check_paths () {
    echo "Checking paths ..."
    [ ! -d /usr/local/bin ] && mkdir -p /usr/local/bin
    [ $OS_FAMILY != "centos" ] && [ $OS_FAMILY != "debian" ] && return 0
    [ ! -d /usr/lib/systemd/system ] && mkdir -p /usr/lib/systemd/system
    [ ! -d /etc/systemd/system ] && mkdir -p /etc/systemd/system
}

delete_service () {
    [ -z $1 ] && return 0 || SERVICE=$1
    systemctl --version > /dev/null 2>&1 || return 0
    echo -e "Disabling $SERVICE ..."
    systemctl is-active --quiet $SERVICE > /dev/null 2>&1 && systemctl stop $SERVICE
    systemctl is-enabled --quiet $SERVICE > /dev/null 2>&1 && systemctl disable $SERVICE
}

disable_firewall () {
    delete_service firewalld.service
    delete_service ufw.service
}

install_deps () {
    install_bash
    install_python3 || install_python2
    install_iptables
    install_iproute
    install_systemd
}

check_system
install_deps
check_paths
disable_firewall
exit 0
