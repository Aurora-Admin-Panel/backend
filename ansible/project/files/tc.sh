#!/bin/bash

# Get default interface
DEBUG=1
SUDO=$(if [ $(id -u $whoami) -gt 0 ]; then echo "sudo "; fi)
IFACE=$(ip route show | grep default | grep -Po '(?<=dev )(\w+)')
IFB=ifb0
PORT=0
PORT_ID=0
EGRESS_SPEED=""
INGRESS_SPEED=""

function check_tc {
    [ $DEBUG -eq 1 ] && echo "Checking tc..."
    if [[ $($SUDO tc qdisc | grep '^qdisc htb.*dev $IFACE root') ]]; then
        $SUDO tc qdisc del root dev $IFACE
    fi
    if [[ ! $($SUDO tc qdisc | grep '^qdisc htb 1:') ]]; then
        $SUDO tc qdisc add dev $IFACE root handle 1: htb default 0
    fi
    if [[ ! $(ip link show | grep $IFB) ]]; then
	    $SUDO modprobe ifb numifbs=1
    fi
    $SUDO ip link set dev $IFB up
    if [[ $($SUDO tc qdisc | grep '^qdisc htb.*dev $IFB root') ]]; then
        $SUDO tc qdisc del root dev $IFACE
    fi
    if [[ ! $($SUDO tc qdisc | grep '^qdisc htb 2:') ]]; then
	    $SUDO tc qdisc add dev $IFB root handle 2: htb default 0
    fi
    if [[ ! $($SUDO tc qdisc show dev $IFACE | grep '^qdisc ingress ffff:') ]]; then
	    $SUDO tc qdisc add dev $IFACE handle ffff: ingress
    fi
    if [[ ! $($SUDO tc filter show dev $IFACE parent ffff:) ]]; then
	    $SUDO tc filter add dev $IFACE parent ffff: protocol ip u32 match u32 0 0 action mirred egress redirect dev ifb0
    fi
}

function limit_egress {
    [ $DEBUG -eq 1 ] && echo "Limiting egress to $EGRESS_SPEED..."

    TCC="tc class add"
    if [[ $($SUDO tc class show dev $IFACE | grep '^class htb 1:'"$PORT_ID") ]]; then
        TCC="tc class change"
    fi
    $SUDO $TCC dev $IFACE parent 1: classid 1:$PORT_ID htb rate $EGRESS_SPEED ceil $EGRESS_SPEED

    if [[ $($SUDO tc filter show dev $IFACE | grep '^filter parent 1:.*pref '"$PORT") ]]; then
	$SUDO tc filter del dev $IFACE prio $PORT
    fi
    $SUDO tc filter add dev $IFACE parent 1: prio $PORT u32 match ip sport $PORT 0xffff flowid 1:$PORT_ID
}
function remove_egress_limit {
    [ $DEBUG -eq 1 ] && echo "Removing egress limit..."
    if [[ $($SUDO tc filter show dev $IFACE | grep '^filter parent 1:.*pref '"$PORT") ]]; then
	    $SUDO tc filter del dev $IFACE prio $PORT
    fi
    if [[ $($SUDO tc class show dev $IFACE | grep '^class htb 1:'"$PORT_ID") ]]; then
        $SUDO tc class del dev $IFACE classid 1:$PORT_ID
    fi
}

function limit_ingress {
    [ $DEBUG -eq 1 ] && echo "Limiting ingress to $INGRESS_SPEED..."

    TCC="tc class add"
    if [[ $($SUDO tc class show dev $IFB | grep '^class htb 2:'"$PORT_ID") ]]; then
        TCC="tc class change"
    fi
    $SUDO $TCC dev $IFB parent 2: classid 2:$PORT_ID htb rate $INGRESS_SPEED ceil $INGRESS_SPEED

    if [[ $($SUDO tc filter show dev $IFB | grep '^filter parent 1:.*pref '"$PORT") ]]; then
        $SUDO tc filter del dev $IFB prio $PORT
    fi
    $SUDO tc filter add dev $IFB parent 2: prio $PORT u32 match ip dport $PORT 0xffff flowid 2:$PORT_ID
}
function remove_ingress_limit {
    [ $DEBUG -eq 1 ] && echo "Removing ingress limit..."
    if [[ $($SUDO tc filter show dev $IFB | grep '^filter parent 2:.*pref '"$PORT") ]]; then
	    $SUDO tc filter del dev $IFB prio $PORT
    fi
    if [[ $($SUDO tc class show dev $IFB | grep '^class htb 2:'"$PORT_ID") ]]; then
        $SUDO tc class del dev $IFB classid 2:$PORT_ID
    fi
}

for i in "$@"
do
case $i in
    -e=*|--egress=*)
    EGRESS_SPEED="${i#*=}"
    shift
    ;;
    -i=*|--ingress=*)
    INGRESS_SPEED="${i#*=}"
    shift
    ;;
esac
done

[ -n $1 ] && PORT=$1 && PORT_ID=$(printf "%x" $PORT)

[ -z $PORT ] && echo "No PORT specified!" && exit 1

check_tc
if [[ $EGRESS_SPEED ]]; then
    limit_egress
else
    remove_egress_limit
fi
if [[ $INGRESS_SPEED ]]; then
    limit_ingress
else
    remove_ingress_limit
fi
