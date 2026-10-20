#!/usr/bin/env bash
# EON Cloud VPN — WireGuard gateway for a cloud VM (no local host, full tunnel).
#
# What it does
#   - installs WireGuard on a Debian/Ubuntu cloud VM
#   - creates a private 10.88.0.0/24 network
#   - enables IPv4 forwarding + NAT so the phone can use the VM as its internet exit
#   - writes a phone config (full tunnel) and prints a QR code
#
# The cloud VM is the only device that can decrypt the tunnel. Cloudflare is not
# in the path, so Cloudflare sees nothing. (Do not put WARP in front if the goal
# is "Cloudflare cannot see"; WARP terminates at Cloudflare.)
#
# Usage on the cloud VM (root):
#   curl -fsSL https://raw.githubusercontent.com/didicola/eon-opencode-cloud/main/vpn/bootstrap-cloud-wg.sh -o /tmp/eon-cloud-vpn.sh
#   sudo bash /tmp/eon-cloud-vpn.sh
#
# Options:
#   --endpoint <ip-or-host>  public IP/hostname of this VM (auto-detected by default)
#   --port <udp-port>        WireGuard UDP port (default 51820)
#   --peer <name>            peer name (default phone)
#   --dns <ip>               DNS pushed to the phone (default 9.9.9.9)
#   --iface <name>           override the default network interface (auto-detected)
#   --split                  split tunnel: only 10.88.0.0/24 goes through the VPN
#   --no-psk                 disable the optional WireGuard preshared key (PQ hedge)
#   --no-qr                  do not print the terminal QR
#   --dry-run                generate keys/configs in a temp dir, change nothing
#   -h, --help
#
# Security: keys are generated on the VM with umask 077; private keys are never
# printed. The QR contains the phone private key and PSK — do not screen-share it.
# The optional PresharedKey is supported by the Android WireGuard app and gives a
# symmetric post-quantum hedge: an attacker who breaks Curve25519 still needs it.
set -euo pipefail
umask 077

PORT=51820
PEER=phone
ENDPOINT=""
DNS=9.9.9.9
SPLIT=0
PSK=1
QR=1
DRY=0
IFACE=""
NET=10.88.0.0/24
SERVER_IP=10.88.0.1
PEER_IP=10.88.0.2

usage() {
  sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

while [ $# -gt 0 ]; do
  case "$1" in
    --endpoint) ENDPOINT="${2:-}"; shift 2 ;;
    --port) PORT="${2:-}"; shift 2 ;;
    --peer) PEER="${2:-}"; shift 2 ;;
    --dns) DNS="${2:-}"; shift 2 ;;
    --iface) IFACE="${2:-}"; shift 2 ;;
    --split) SPLIT=1; shift ;;
    --no-psk) PSK=0; shift ;;
    --no-qr) QR=0; shift ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) usage ;;
    *) echo "ERROR: unknown option $1" >&2; exit 2 ;;
  esac
done

if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
  echo "ERROR: --port must be 1..65535" >&2
  exit 2
fi
if ! [[ "$PEER" =~ ^[a-zA-Z0-9_-]{1,24}$ ]]; then
  echo "ERROR: --peer must be 1-24 chars (letters, digits, _ or -)" >&2
  exit 2
fi
if [ "$DRY" -eq 0 ] && [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run as root (sudo bash $0 ...) or use --dry-run." >&2
  exit 1
fi

if [ "$DRY" -eq 1 ]; then
  if ! command -v wg >/dev/null 2>&1; then
    echo "ERROR: wg not installed. Install wireguard-tools for --dry-run." >&2
    exit 1
  fi
  if ! command -v curl >/dev/null 2>&1; then
    echo "ERROR: curl not installed. Install curl for --dry-run." >&2
    exit 1
  fi
else
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y wireguard wireguard-tools nftables iptables iproute2 qrencode curl
fi

if [ -z "$ENDPOINT" ]; then
  ENDPOINT="$(curl -4 -fsS --max-time 8 https://api.ipify.org 2>/dev/null || true)"
  [ -n "$ENDPOINT" ] || ENDPOINT="$(curl -4 -fsS --max-time 8 https://ifconfig.me/ip 2>/dev/null || true)"
fi
if [ -z "$ENDPOINT" ]; then
  if [ "$DRY" -eq 1 ]; then
    ENDPOINT="203.0.113.10"
    echo "WARN: no public IP detected; dry-run uses $ENDPOINT" >&2
  else
    echo "ERROR: cannot detect public IP. Re-run with: --endpoint <public-ip-or-host>" >&2
    exit 1
  fi
fi
if ! [[ "$ENDPOINT" =~ ^[A-Za-z0-9.:-]+$ ]]; then
  echo "ERROR: --endpoint must be a hostname or IP (no scheme/path)." >&2
  exit 2
fi

if [ -z "$IFACE" ]; then
  IFACE="$(ip -4 route show default 2>/dev/null | awk '{print $5; exit}' || true)"
fi
if [ -z "$IFACE" ]; then
  if [ "$DRY" -eq 1 ]; then
    IFACE=eth0
    echo "WARN: no default interface detected; dry-run uses $IFACE" >&2
  else
    echo "ERROR: cannot detect the default network interface." >&2
    exit 1
  fi
fi

if [ "$DRY" -eq 1 ]; then
  WORK="$(mktemp -d "${TMPDIR:-/tmp}/eon-cloud-vpn.XXXXXX")"
else
  WORK=/root/eon-cloud-vpn
fi
mkdir -p "$WORK/keys" "$WORK/out"
chmod 700 "$WORK" "$WORK/keys" "$WORK/out"

# Keys (never print private keys)
wg genkey > "$WORK/keys/server.key"
wg pubkey < "$WORK/keys/server.key" > "$WORK/keys/server.pub"
wg genkey > "$WORK/keys/$PEER.key"
wg pubkey < "$WORK/keys/$PEER.key" > "$WORK/keys/$PEER.pub"
chmod 600 "$WORK/keys/server.key" "$WORK/keys/$PEER.key"
chmod 644 "$WORK/keys/server.pub" "$WORK/keys/$PEER.pub"

# Optional preshared key: a symmetric post-quantum hedge supported by the
# Android WireGuard app. Same value on both ends; never printed.
PSK_LINE=""
if [ "$PSK" -eq 1 ]; then
  wg genpsk > "$WORK/keys/psk.key"
  chmod 600 "$WORK/keys/psk.key"
  PSK_LINE="PresharedKey = $(cat "$WORK/keys/psk.key")"
fi

if [ "$SPLIT" -eq 1 ]; then
  ALLOWED="$NET"
else
  ALLOWED="0.0.0.0/0, ::/0"
fi

cat > "$WORK/out/wgcloud.conf" <<EOF
[Interface]
Address = $SERVER_IP/24
ListenPort = $PORT
PrivateKey = $(cat "$WORK/keys/server.key")
MTU = 1280
PostUp = /usr/local/sbin/eon-cloud-vpn-fw.sh up
PostDown = /usr/local/sbin/eon-cloud-vpn-fw.sh down

[Peer]
# $PEER
PublicKey = $(cat "$WORK/keys/$PEER.pub")
$PSK_LINE
AllowedIPs = $PEER_IP/32
EOF
chmod 600 "$WORK/out/wgcloud.conf"

cat > "$WORK/out/$PEER.conf" <<EOF
[Interface]
PrivateKey = $(cat "$WORK/keys/$PEER.key")
Address = $PEER_IP/32
DNS = $DNS
MTU = 1280

[Peer]
PublicKey = $(cat "$WORK/keys/server.pub")
$PSK_LINE
Endpoint = $ENDPOINT:$PORT
AllowedIPs = $ALLOWED
PersistentKeepalive = 25
EOF
chmod 600 "$WORK/out/$PEER.conf"

cat > "$WORK/out/manifest.txt" <<EOF
EON Cloud VPN
endpoint: $ENDPOINT
udp_port: $PORT
network: $NET
server: $SERVER_IP
peer: $PEER = $PEER_IP
split_tunnel: $SPLIT
psk: $PSK
dns: $DNS
created: $(date -u +%Y-%m-%dT%H:%M:%SZ)
server_pub: $(cat "$WORK/keys/server.pub")
peer_pub: $(cat "$WORK/keys/$PEER.pub")
EOF
chmod 644 "$WORK/out/manifest.txt"

if [ "$DRY" -eq 0 ]; then
  # Idempotent forwarding/NAT helper (baked with the detected interface).
  cat > /usr/local/sbin/eon-cloud-vpn-fw.sh <<EOF
#!/usr/bin/env bash
set -euo pipefail
IFACE="$IFACE"
case "\${1:-}" in
  up)
    sysctl -w net.ipv4.ip_forward=1 >/dev/null
    # -I 1 puts our accept ahead of ufw's forward chain.
    iptables -C FORWARD -i wgcloud -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -i wgcloud -j ACCEPT
    iptables -C FORWARD -o wgcloud -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -o wgcloud -j ACCEPT
    iptables -t nat -C POSTROUTING -o "\$IFACE" -j MASQUERADE 2>/dev/null || iptables -t nat -I POSTROUTING 1 -o "\$IFACE" -j MASQUERADE
    if command -v ip6tables >/dev/null 2>&1 && ip -6 route show default 2>/dev/null | grep -q .; then
      sysctl -w net.ipv6.conf.all.forwarding=1 >/dev/null
      ip6tables -C FORWARD -i wgcloud -j ACCEPT 2>/dev/null || ip6tables -I FORWARD 1 -i wgcloud -j ACCEPT
      ip6tables -C FORWARD -o wgcloud -j ACCEPT 2>/dev/null || ip6tables -I FORWARD 1 -o wgcloud -j ACCEPT
      ip6tables -t nat -C POSTROUTING -o "\$IFACE" -j MASQUERADE 2>/dev/null || ip6tables -t nat -I POSTROUTING 1 -o "\$IFACE" -j MASQUERADE
    fi
    ;;
  down)
    iptables -D FORWARD -i wgcloud -j ACCEPT 2>/dev/null || true
    iptables -D FORWARD -o wgcloud -j ACCEPT 2>/dev/null || true
    iptables -t nat -D POSTROUTING -o "\$IFACE" -j MASQUERADE 2>/dev/null || true
    if command -v ip6tables >/dev/null 2>&1; then
      ip6tables -D FORWARD -i wgcloud -j ACCEPT 2>/dev/null || true
      ip6tables -D FORWARD -o wgcloud -j ACCEPT 2>/dev/null || true
      ip6tables -t nat -D POSTROUTING -o "\$IFACE" -j MASQUERADE 2>/dev/null || true
    fi
    ;;
  *) echo "usage: \$0 up|down" >&2; exit 2 ;;
esac
EOF
  chmod 700 /usr/local/sbin/eon-cloud-vpn-fw.sh

  echo 'net.ipv4.ip_forward=1' > /etc/sysctl.d/99-eon-cloud-vpn.conf
  sysctl --system >/dev/null

  install -d -m 700 /etc/wireguard
  install -m 600 "$WORK/out/wgcloud.conf" /etc/wireguard/wgcloud.conf

  # Re-run safety: remove a stale interface from a previous partial run.
  wg-quick down wgcloud >/dev/null 2>&1 || true
  ip link delete wgcloud >/dev/null 2>&1 || true

  if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
    ufw allow "$PORT"/udp || true
    ufw route allow in on wgcloud out on "$IFACE" || true
    ufw route allow in on "$IFACE" out on wgcloud || true
  fi

  systemctl enable wg-quick@wgcloud >/dev/null 2>&1 || true
  if ! systemctl restart wg-quick@wgcloud; then
    echo "ERROR: wg-quick@wgcloud failed. Logs:" >&2
    systemctl status wg-quick@wgcloud --no-pager || true
    journalctl -u wg-quick@wgcloud -n 40 --no-pager || true
    exit 1
  fi

  # Open the UDP port in the cloud provider's security group/firewall too.
  echo
  echo "=== EON Cloud VPN is up ==="
  wg show wgcloud || true
  echo
  echo "Cloud firewall: allow UDP $PORT inbound to this VM."
  echo "Phone config:   $WORK/out/$PEER.conf (600)"
  echo "Server config:  /etc/wireguard/wgcloud.conf (600)"
  echo "Manifest:       $WORK/out/manifest.txt"
  echo
  echo "Import the phone config into the WireGuard app, enable it, then:"
  echo "  ping 10.88.0.1"
  echo "  curl -4 https://api.ipify.org   # should show $ENDPOINT"
  echo
  if [ "$QR" -eq 1 ] && command -v qrencode >/dev/null 2>&1; then
    echo "QR (contains the phone private key — do not screen-share):"
    qrencode -t ansiutf8 < "$WORK/out/$PEER.conf" || true
  fi
else
  echo "=== DRY RUN (no system changes) ==="
  echo "work dir: $WORK"
  ls -l "$WORK/out"
  echo "server: $SERVER_IP/24 udp/$PORT iface=$IFACE endpoint=$ENDPOINT"
  echo "peer:   $PEER = $PEER_IP  allowed=$ALLOWED"
  echo "files:  wgcloud.conf, $PEER.conf, manifest.txt"
fi
