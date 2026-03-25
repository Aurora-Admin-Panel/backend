#!/bin/sh
# aurora-system-probe v1.0.5 (POSIX /bin/sh)
# Emits tagged lines on stdout only.

# ---- predictable output/exit ----
export LC_ALL=C LANG=C PATH="/usr/sbin:/usr/bin:/sbin:/bin"
exec 2>/dev/null   # swallow all stderr

# ---- filters (override via env) ----
: "${MOUNT_EXCLUDE:=^/(dev|proc|sys|run|var/lib/docker/.+|var/lib/kubelet/.+)($|/)}"
: "${IFACE_INCLUDE:=^(eth.*|en.*|em.*|bond.*|team.*|wlan.*|tailscale0)$}"
: "${IFACE_EXCLUDE:=^(lo|veth.*|br-.*|docker.*|cni.*|flannel.*|kube.*|zt.*|ztr.*|tun.*|tap.*)$}"

# OS release (fallback to uname)
if [ -r /etc/os-release ]; then
  os_release=$(
    awk -F= '/^(NAME|VERSION_ID)=/ { gsub(/"/,"",$2); printf "%s ", $2 } END{print ""}' /etc/os-release
  )
else
  os_release="$(uname -srm || echo unknown)"
fi

# Load averages
if [ -r /proc/loadavg ]; then
  set -- $(cat /proc/loadavg)
  l1="$1"; l5="$2"; l15="$3"
else
  l1=0 l5=0 l15=0
fi

# Uptime
if [ -r /proc/uptime ]; then
  uptime_s=$(cut -d' ' -f1 /proc/uptime)
else
  uptime_s=0
fi

# CPU% using 2-sample /proc/stat (busy = 1 - idle/total)
read cpu a b c d e f g h i j < /proc/stat
t1=$((a+b+c+d+e+f+g+h+i+j)); i1=$d
sleep 0.2
read cpu a b c d e f g h i j < /proc/stat
t2=$((a+b+c+d+e+f+g+h+i+j)); i2=$d
dt=$((t2 - t1)); di=$((i2 - i1))
if [ -z "$dt" ] || [ "$dt" -le 0 ]; then
  cpu_pct="0.00"
else
  cpu_pct=$(awk -v dt="$dt" -v di="$di" 'BEGIN{ printf "%.2f", (1 - di/dt)*100 }')
fi

# Memory (bytes) — read KB, convert in shell to avoid scientific notation
mem_total_kb=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
mem_avail_kb=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
[ -z "$mem_total_kb" ] && mem_total_kb=0
[ -z "$mem_avail_kb" ] && mem_avail_kb=0
mem_total=$((mem_total_kb * 1024))
mem_used=$(((mem_total_kb - mem_avail_kb) * 1024))

swap_total_kb=$(awk '/SwapTotal/ {print $2}' /proc/meminfo)
swap_free_kb=$(awk '/SwapFree/ {print $2}' /proc/meminfo)
[ -z "$swap_total_kb" ] && swap_total_kb=0
[ -z "$swap_free_kb" ] && swap_free_kb=0
swap_total=$((swap_total_kb * 1024))
swap_used=$(((swap_total_kb - swap_free_kb) * 1024))

# Disk sizes via df -P; prefer bytes if supported, else KiB
USE_BYTES=0
if df -P -B1 / >/dev/null 2>&1; then
  DF_CMD="df -P -B1"
  USE_BYTES=1
elif df -P -k / >/dev/null 2>&1; then
  DF_CMD="df -P -k"
else
  DF_CMD="df -P"
fi

# Filter mountpoints with MOUNT_EXCLUDE; print only selected mounts
DISKS=$(
  $DF_CMD | awk -v use_bytes="$USE_BYTES" -v MEX="$MOUNT_EXCLUDE" '
    NR>1 {
      mount=$NF
      if (mount ~ MEX) next
      total_col=$(NF-4)
      used_col=$(NF-3)
      total=total_col+0
      used=used_col+0
      if (use_bytes==0) { total*=1024; used*=1024 }
      printf "DSK|%s|%.0f|%.0f\n", mount, total, used
    }
  '
)

# Default-route interfaces (fixed quoting)
DEFAULT_IFACES="$(
  awk '$1!="Iface" && $2=="00000000"{print $1}' /proc/net/route | sort -u | tr '\n' ' '
)"

# NIC counters (bytes), filtered
NICS=""
for n in /sys/class/net/*; do
  [ -e "$n" ] || continue
  iface=$(basename "$n")

  # exclude by name
  if echo "$iface" | grep -Eq "$IFACE_EXCLUDE"; then
    continue
  fi

  include=0

  # 1) default route iface(s)
  case " $DEFAULT_IFACES " in
    *" $iface "*) include=1 ;;
  esac

  # 2) allowlist names (eth*/en*/em*/bond*/team*/wlan*/tailscale0)
  if [ $include -eq 0 ] && echo "$iface" | grep -Eq "$IFACE_INCLUDE"; then
    include=1
  fi

  # 3) physical device (has /device symlink)
  if [ $include -eq 0 ] && [ -e "$n/device" ]; then
    include=1
  fi

  [ $include -eq 1 ] || continue

  if [ -r "$n/statistics/rx_bytes" ] && [ -r "$n/statistics/tx_bytes" ]; then
    rx=$(cat "$n/statistics/rx_bytes")
    tx=$(cat "$n/statistics/tx_bytes")
    NICS="${NICS}
NIC|${iface}|${rx}|${tx}"
  fi
done

# Emit results
printf "OS|%s\n" "$os_release"
printf "LOAD|%s|%s|%s\n" "$l1" "$l5" "$l15"
printf "UPTIME|%s\n" "$uptime_s"
printf "CPU|%s\n" "$cpu_pct"
printf "MEM|%s|%s|%s|%s\n" "$mem_total" "$mem_used" "$swap_total" "$swap_used"
[ -n "$DISKS" ] && printf "%s\n" "$DISKS"
[ -n "$NICS"  ] && printf "%s\n" "$NICS"

exit 0
