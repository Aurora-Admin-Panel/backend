#!/bin/bash

SUDO=$(if [ $(id -u $whoami) -gt 0 ]; then echo "sudo "; fi)

$SUDO iptables -nxvL INPUT | grep '\/\*.*\*\/$'
$SUDO iptables -nxvL FORWARD | grep '\/\*.*\*\/$'