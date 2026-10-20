# EON Mesh VPN v2 — ubuntu gateway (no Oracle, no paid VPN)

This is the self-contained bootstrap for using the **existing ubuntu box** as the
EON WireGuard gateway. No Oracle account, no paid VPN, no third-party VPN.

The live kit and its test receipt live on termux1 at `~/eon-tmp/eon-vpn/`.
This repo copy exists so the ubuntu console can fetch the installer with
`curl` (ubuntu SSH is closed; console access is required).

## What it builds

```
phone   10.77.0.2 ─┐
termux2 10.77.0.3 ─┼── WireGuard UDP 51820 ── ubuntu gateway 10.77.0.1
laptop  10.77.0.4 ─┤                         (existing LAN host)
ci      10.77.0.5 ─┘
```

- Private `10.77.0.0/24`, split tunnel (`AllowedIPs = 10.77.0.0/24`).
- Peer-to-peer forwarding through the gateway; no internet NAT.
- Keys generated **on the ubuntu host**, mode 600. No private key is in this repo.
- Script prints no private keys. The QR command is owner-run and contains the
  phone private key — do not screen-share it.

## Run on the ubuntu console

```bash
curl -fsSL https://raw.githubusercontent.com/didicola/eon-opencode-cloud/main/vpn/bootstrap-ubuntu.sh \
  -o /tmp/eon-vpn.sh
sha256sum /tmp/eon-vpn.sh
# expected: ec392eefa8a95f3c17edd7743abcfb88378d2f5b100f3943d731fcdbd3ba12d1

sudo bash /tmp/eon-vpn.sh 192.168.1.72
```

`192.168.1.72` is the ubuntu LAN IP. For remote peers, forward UDP 51820 on the
router and run the script with the public IP/hostname instead.

The script:

1. installs `wireguard`, `wireguard-tools`, `nftables`, `iptables` (and
   `qrencode` if available);
2. generates server + peer keys under `/root/eon-vpn/` (700 dirs, 600 keys);
3. writes `/etc/wireguard/wg0.conf` (600) and enables `wg-quick@wg0`;
4. adds persistent nftables/iptables accept rules for UDP 51820 and `wg0`
   (does not change default policies, so SSH is not locked out);
5. allows UDP 51820 through ufw if ufw is active;
6. prints paths to `phone.conf`, `termux2.conf`, `laptop.conf`, `ci.conf`.

## Import on peers

- **Phone:** install the official WireGuard Android app, import
  `/root/eon-vpn/out/phone.conf` (transfer it securely), activate.
  Print a QR in the ubuntu console with:
  `sudo qrencode -t ansiutf8 < /root/eon-vpn/out/phone.conf`
- **Linux peer:** `sudo wg-quick up ./<name>.conf`.
- **Test:** `ping 10.77.0.1`, then `ping 10.77.0.2` from another peer.

## Android constraint

Android has one VPN slot per user profile. WARP and WireGuard cannot both be
active in the same profile. Split tunnel does not free the slot. Use EON VPN
only when needed, or a work profile / second device. See the local
`ANDROID-WARP.md` in the termux1 kit.

## Dry-run (no root, no changes)

```bash
bash /tmp/eon-vpn.sh --dry-run 192.168.1.72
```

This generates throwaway keys/configs in a temp dir and prints the structure.
It does not touch `/etc`, systemd, or the firewall.

## If ubuntu console is not available

The same script works on any Ubuntu host with root, including a free-tier
GCP e2-micro (1 GB/month egress; not ideal for large transfers). If no host is
available, Cloudflare Tunnel is the free HTTP-only alternative for the
dashboard/web UIs; it is not a full VPN. See the local `cloudflare-tunnel.md`.

## Security

- Do not commit `/root/eon-vpn/` or any `.key`/`.conf` file.
- Open only UDP 51820. Keep SSH key-only and restricted.
- The gateway is private; it does not hide internet traffic or provide
  anonymity. WARP remains the phone's internet-privacy layer.
- If a peer key leaks, regenerate that peer's key, remove the old public key
  from `/etc/wireguard/wg0.conf`, and re-import the new config.
