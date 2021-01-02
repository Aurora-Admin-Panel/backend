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
    $SUDO iptables-save -c | $SUDO tee /etc/sysconfig/iptables > /dev/null
  else
    $SUDO mkdir -p /etc/iptables
    $SUDO iptables-save -c | $SUDO tee /etc/iptables/rules.v4 > /dev/null
  fi
}


$SUDO iptables -nxvL INPUT | grep '\/\*.*\*\/$'
$SUDO iptables -nxvL FORWARD | grep '\/\*.*\*\/$'
$SUDO iptables -nxvL OUTPUT | grep '\/\*.*\*\/$'
save_iptables
exit 0