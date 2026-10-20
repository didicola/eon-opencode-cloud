#!/usr/bin/env bash
# EON Mesh VPN v3 - self-contained Ubuntu gateway bootstrap.
# Uses eonwg0 + UDP 51821 so an existing wg0/51820 on the host is never touched.
# No Oracle, no paid VPN.
#
# On ubuntu (console, root):
#   sudo bash bootstrap-ubuntu-eonwg.sh [endpoint]
#   endpoint defaults to 192.168.1.72 (ubuntu LAN IP)
#
# Dry-run on any machine with wireguard-tools:
#   bash bootstrap-ubuntu-eonwg.sh --dry-run [endpoint]
#
# The script generates keys locally. It prints no private keys. The only
# private-key output is the optional QR command the owner can run themselves.
set -euo pipefail
umask 077

usage() {
  cat <<'EOF'
Usage: bootstrap-ubuntu-eonwg.sh [--dry-run] [--qr] [endpoint]

  endpoint   gateway address peers use (default 192.168.1.72)
  --dry-run  generate keys/configs in a temp dir; do not install
  --qr       also print a terminal QR for phone.conf (contains private key)
EOF
}

DRY=0
QR=0
ENDPOINT=""
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --qr) QR=1 ;;
    -h|--help) usage; exit 0 ;;
    --*) echo "ERROR: unknown option $arg" >&2; usage; exit 2 ;;
    *)
      if [ -z "$ENDPOINT" ]; then ENDPOINT="$arg"; else echo "ERROR: unexpected arg $arg" >&2; exit 2; fi
      ;;
  esac
done
ENDPOINT="${ENDPOINT:-192.168.1.72}"

if ! [[ "$ENDPOINT" =~ ^[A-Za-z0-9.-]+$ ]]; then
  echo "ERROR: endpoint must be a hostname or IPv4 (no scheme/port)." >&2
  exit 2
fi

if [ "$DRY" -eq 0 ] && [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run as root (sudo bash bootstrap-ubuntu-eonwg.sh ...) or use --dry-run." >&2
  exit 1
fi

if ! command -v wg >/dev/null 2>&1; then
  if [ "$DRY" -eq 1 ]; then
    echo "ERROR: wg not installed. Install wireguard-tools for dry-run." >&2
    exit 1
  fi
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y wireguard wireguard-tools nftables iptables
  apt-get install -y qrencode || true
fi

if [ "$DRY" -eq 1 ]; then
  WORK="$(mktemp -d "${TMPDIR:-/tmp}/eon-vpn-dry.XXXXXX")"
else
  WORK="/root/eon-vpn"
fi
mkdir -p "$WORK/keys" "$WORK/out"
chmod 700 "$WORK" "$WORK/keys" "$WORK/out"

names=(server phone termux2 laptop ci)
for name in "${names[@]}"; do
  wg genkey > "$WORK/keys/$name.key"
  chmod 600 "$WORK/keys/$name.key"
  wg pubkey < "$WORK/keys/$name.key" > "$WORK/keys/$name.pub"
  chmod 644 "$WORK/keys/$name.pub"
done

server_key="$(cat "$WORK/keys/server.key")"
server_pub="$(cat "$WORK/keys/server.pub")"

{
  echo "[Interface]"
  echo "Address = 10.77.0.1/24"
  echo "ListenPort = 51821"
  echo "PrivateKey = $server_key"
  echo "MTU = 1280"
  echo
} > "$WORK/out/server-eonwg0.conf"

declare -A peer_ip=( [phone]=10.77.0.2 [termux2]=10.77.0.3 [laptop]=10.77.0.4 [ci]=10.77.0.5 )

for name in phone termux2 laptop ci; do
  pub="$(cat "$WORK/keys/$name.pub")"
  {
    echo "[Peer]"
    echo "# $name"
    echo "PublicKey = $pub"
    echo "AllowedIPs = ${peer_ip[$name]}/32"
    echo
  } >> "$WORK/out/server-eonwg0.conf"
done
chmod 600 "$WORK/out/server-eonwg0.conf"

for name in phone termux2 laptop ci; do
  key="$(cat "$WORK/keys/$name.key")"
  ip="${peer_ip[$name]}"
  {
    echo "[Interface]"
    echo "PrivateKey = $key"
    echo "Address = $ip/32"
    echo "MTU = 1280"
    echo
    echo "[Peer]"
    echo "PublicKey = $server_pub"
    echo "Endpoint = $ENDPOINT:51821"
    echo "AllowedIPs = 10.77.0.0/24"
    echo "PersistentKeepalive = 25"
    echo
  } > "$WORK/out/$name.conf"
  chmod 600 "$WORK/out/$name.conf"
done

{
  echo "endpoint=$ENDPOINT"
  echo "server_public=$server_pub"
  echo
  for name in phone termux2 laptop ci; do
    echo "$name ip=${peer_ip[$name]} public=$(cat "$WORK/keys/$name.pub")"
  done
} > "$WORK/out/manifest.txt"
chmod 644 "$WORK/out/manifest.txt"

if [ "$DRY" -eq 1 ]; then
  echo "DRY RUN complete: $WORK"
  echo "server:   $WORK/out/server-eonwg0.conf"
  echo "peers:    $WORK/out/{phone,termux2,laptop,ci}.conf"
  echo "manifest: $WORK/out/manifest.txt (public keys only)"
  echo "structure:"
  grep -hE '^\[|^Address|^ListenPort|^MTU|^AllowedIPs|^Endpoint|^PersistentKeepalive' \
    "$WORK/out/server-eonwg0.conf" "$WORK/out/phone.conf" || true
  exit 0
fi

install -d -m 700 /etc/wireguard
install -m 600 "$WORK/out/server-eonwg0.conf" /etc/wireguard/eonwg0.conf

cat > /etc/sysctl.d/99-eon-vpn.conf <<'EOF'
net.ipv4.ip_forward = 1
EOF
sysctl --system >/dev/null

cat > /usr/local/sbin/eon-vpn-firewall.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
nft list table inet eon_vpn >/dev/null 2>&1 && nft delete table inet eon_vpn || true
nft -f - <<'NFT'
table inet eon_vpn {
  chain input {
    type filter hook input priority 0; policy accept;
    iifname "eonwg0" accept
    udp dport 51821 accept
  }
  chain forward {
    type filter hook forward priority 0; policy accept;
    iifname "eonwg0" oifname "eonwg0" accept
  }
}
NFT
if command -v iptables >/dev/null 2>&1; then
  iptables -C INPUT -p udp --dport 51821 -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -p udp --dport 51821 -j ACCEPT
  iptables -C INPUT -i eonwg0 -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -i eonwg0 -j ACCEPT
  iptables -C FORWARD -i eonwg0 -o eonwg0 -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -i eonwg0 -o eonwg0 -j ACCEPT
fi
EOF
chmod 700 /usr/local/sbin/eon-vpn-firewall.sh

cat > /etc/systemd/system/eon-vpn-firewall.service <<'EOF'
[Unit]
Description=EON VPN firewall rules
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/eon-vpn-firewall.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now eon-vpn-firewall.service
/usr/local/sbin/eon-vpn-firewall.sh

if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
  ufw allow 51821/udp || true
fi

# clean any stale eonwg0 from a previous partial run (never touches the existing wg0)
wg-quick down eonwg0 >/dev/null 2>&1 || true
ip link delete eonwg0 >/dev/null 2>&1 || true

systemctl enable wg-quick@eonwg0
if ! systemctl restart wg-quick@eonwg0; then
  echo "ERROR: wg-quick@eonwg0 failed. Logs:" >&2
  systemctl status wg-quick@eonwg0 --no-pager || true
  journalctl -u wg-quick@eonwg0 -n 40 --no-pager || true
  exit 1
fi
sleep 1
wg show eonwg0 || true

echo
echo "EON VPN gateway is up."
echo "  VPN: 10.77.0.1/24, UDP 51821"
echo "  Endpoint: $ENDPOINT:51821"
echo "  Configs: $WORK/out/{phone,termux2,laptop,ci}.conf (600)"
echo "  Server:  /etc/wireguard/eonwg0.conf (600)"
echo
echo "Phone QR (contains the phone private key; do not screen-share):"
echo "  sudo qrencode -t ansiutf8 < $WORK/out/phone.conf"
if [ "$QR" -eq 1 ]; then
  qrencode -t ansiutf8 < "$WORK/out/phone.conf"
fi
echo
echo "LAN peers: import the matching .conf."
echo "Remote peers: forward UDP 51821 on the router to this host and"
echo "re-render the endpoint with the public IP/hostname."
