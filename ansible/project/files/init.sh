#! /bin/bash

SUDO=$(if [ $(id -u $whoami) -gt 0 ]; then echo "sudo "; fi)
[ -z $SUDO ] || sudo -n true 2>/dev/null || (echo "Failed to use sudo" && exit 1)

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
}

install_python3 () {
    echo "Checking python3 ..."
    python3 -V > /dev/null 2>&1 && return 0
    [[ -z $OS_FAMILY ]] && return 0
    echo "Installing python3 ..."
    $INSTALL python3 || ($UPDATE && $INSTALL python3) || (echo "Failed to install python3!" && return 1)
}

install_python2 () {
    echo "Checking python2 ..."
    (python -V > /dev/null 2>&1 || python2 -V > /dev/null 2>&1) && return 0
    [[ -z $OS_FAMILY ]] && return 0
    echo "Installing python2 ..."
    if [[ $OS_FAMILY == "centos" || $OS_FAMILY == "debian" ]]; then
        $INSTALL python || ($UPDATE && $INSTALL python) || echo "Failed to install python2!"
    elif [[ $OS_FAMILY == "alpine" ]]; then
        $INSTALL python2 || ($UPDATE && $INSTALL python2) || echo "Failed to install python2!"
    fi
}

install_iptables () {
    echo "Checking iptables ..."
    iptables -V > /dev/null 2>&1 && return 0
    [[ -z $OS_FAMILY ]] && return 0
    echo "Installing iptables ..."
    $INSTALL iptables || ($UPDATE && $INSTALL iptables) || echo "Failed to install iptables!"
}

install_iproute () {
    echo "Checking iproute ..."
    ip a > /dev/null 2>&1 && return 0
    echo "Installing iproute ..."
    if [[ $OS_FAMILY == "centos" ]]; then
        $INSTALL iproute || ($UPDATE && $INSTALL iproute) || echo "Failed to install iproute!"
    elif [[ $OS_FAMILY == "debian" ]]; then
        $INSTALL iproute2 || ($UPDATE && $INSTALL iproute2) || echo "Failed to install iproute2!"
    fi
}

install_systemd () {
    echo "Checking systemd ..."
    systemctl --version > /dev/null 2>&1 && return 0
    [[ $OS_FAMILY != "centos" && $OS_FAMILY != "debian" ]] && return 0
    echo "Installing systemd ..."
    $INSTALL systemd || ($UPDATE && $INSTALL systemd) || echo "Failed to install systemd!"
}

check_paths () {
    echo "Checking paths ..."
    [[ ! -d /usr/local/bin ]] && $SUDO mkdir -p /usr/local/bin
    systemctl --version > /dev/null 2>&1 || return 0
    [[ ! -d /usr/lib/systemd/system ]] && $SUDO mkdir -p /usr/lib/systemd/system
    [[ ! -d /etc/systemd/system ]] && $SUDO mkdir -p /etc/systemd/system
}

check_envs () {
    echo "Checking envs ..."
    ENV_PATH=$(env | grep PATH | grep "\/usr\/local\/bin")
    [[ -n $ENV_PATH ]] && return 0
    echo "Adding local bin ..."
    echo "export PATH=/usr/local/bin:$PATH" >> /etc/environment
}

delete_service () {
    [[ -z $1 ]] && return 0 || SERVICE=$1
    systemctl --version > /dev/null 2>&1 || return 0
    echo -e "Disabling $SERVICE ..."
    systemctl is-active --quiet $SERVICE > /dev/null 2>&1 && $SUDO systemctl stop $SERVICE
    systemctl is-enabled --quiet $SERVICE > /dev/null 2>&1 && $SUDO systemctl disable $SERVICE
}

disable_firewall () {
    delete_service firewalld.service
    delete_service ufw.service
}

install_deps () {
    install_python3 || install_python2
    install_iptables
    install_iproute
    install_systemd
}

check_system
install_deps
check_paths
check_envs
disable_firewall
exit 0
