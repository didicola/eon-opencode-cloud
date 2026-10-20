# EON Cloud VPN — owner guide (plain language)

## What this is

A private VPN whose **exit is a cloud VM**, not your local Ubuntu box.

- The phone talks to the cloud VM over WireGuard (UDP 51820).
- The cloud VM is the only other device with the tunnel keys.
- Cloudflare is **not** in the data path, so Cloudflare cannot see the tunnel or its payload.
- The cloud provider that runs the VM is the new exit and can see unencrypted traffic, like any VPN server. Use HTTPS as usual.

This is the honest limit: a real VPN needs a machine with a network stack and a TUN device. Cloudflare Workers cannot carry raw IP/UDP and cannot host a TUN, so a Worker-only VPN is not possible. Cloudflare WARP is a cloud VPN, but Cloudflare becomes the exit and can see traffic, so it does not meet the "Cloudflare cannot see" condition.

## What you need

1. A cloud VM running **Ubuntu 22.04/24.04 or Debian 12** with:
   - a public IPv4 address,
   - inbound **UDP 51820** allowed in the provider firewall/security group,
   - root/sudo.
2. The **WireGuard** app on the phone (already installed).
3. About 5 minutes.

Free-tier options change often. Check the provider's current page before creating anything. Oracle Always Free is the best fit on paper, but signup is inaccessible here. AWS/GCP/Azure free tiers require a card and have egress limits; a small paid VPS is typically $4–6/month if you prefer no card/free-tier restrictions.

## Install on the cloud VM

Open the provider's browser terminal (or SSH), then run:

```bash
curl -fsSL https://raw.githubusercontent.com/didicola/eon-opencode-cloud/main/vpn/bootstrap-cloud-wg.sh -o /tmp/eon-cloud-vpn.sh
sudo bash /tmp/eon-cloud-vpn.sh
```

The script:

- detects the VM's public IP and default network interface,
- installs WireGuard,
- creates a private `10.88.0.0/24` network,
- enables forwarding + NAT for a full tunnel,
- writes `/root/eon-cloud-vpn/out/phone.conf` (`600`),
- starts `wg-quick@wgcloud`,
- prints a terminal QR code.

Useful options:

```bash
sudo bash /tmp/eon-cloud-vpn.sh --split              # only 10.88.0.0/24 through the VPN
sudo bash /tmp/eon-cloud-vpn.sh --peer laptop        # generate a laptop config instead
sudo bash /tmp/eon-cloud-vpn.sh --no-qr              # no terminal QR
sudo bash /tmp/eon-cloud-vpn.sh --dry-run            # generate in a temp dir, change nothing
```

If auto-detection is wrong:

```bash
sudo bash /tmp/eon-cloud-vpn.sh --endpoint 203.0.113.10
```

## Connect the phone

1. Open the WireGuard app.
2. Add a tunnel → **Create from QR code**.
3. Scan the QR printed by the script.
4. Enable the tunnel.
5. Check:

```bash
ping -c 3 10.88.0.1
curl -4 https://api.ipify.org     # should show the cloud VM's public IP
```

On the VM, verify:

```bash
sudo wg show wgcloud
systemctl is-active wg-quick@wgcloud
ss -lunp | grep 51820
```

## Security

- Private keys are generated on the VM with `umask 077`; the phone config is `600`.
- The QR contains the phone private key. Do not screen-share it or post it.
- After importing, you can delete the copy in Downloads and run:
  `sudo shred -u /root/eon-cloud-vpn/out/phone.conf` (keep a backup only if you need to re-import).
- Do not put Cloudflare WARP in front if the requirement is "Cloudflare cannot see"; WARP terminates at Cloudflare.
- The cloud provider is the exit. It can see unencrypted traffic. Keep HTTPS/HSTS on, and do not send plaintext secrets.

## Encryption and PQC

WireGuard already encrypts the tunnel with ChaCha20-Poly1305, Curve25519, and BLAKE2s. That is strong and fast, but it is not post-quantum.

For PQC later, the practical paths are:

- **MASQUE / HTTP/3** with `sing-box` on the VM and the phone, using TLS 1.3 hybrid `X25519MLKEM768` and optional mTLS with the EON CA. This is the cleanest PQC path, but it needs a separate lab and compatibility testing.
- **strongSwan IKEv2 with ML-KEM**, using Android's built-in VPN client. Android compatibility must be tested on the exact device/ROM before relying on it.
- **Rosenpass** adds a post-quantum PSK to WireGuard on Linux, but the Android WireGuard app does not speak Rosenpass today.

Do not start with PQC. Get the cloud WireGuard tunnel working and measured first; then add PQC without breaking the working path.

## What was verified today

- `bash -n` syntax: OK.
- `--dry-run` twice: full-tunnel and split-tunnel configs generated; keys `600`; dirs `700`; no system changes.
- `eon-world` keyless GPU lane (`gpt-oss-20b` via Pollinations/OVH): HTTP 200, ~29 s, response saved at `~/eon-tmp/eon-vpn/WORLD-GPU-REVIEW-20261020.json`. It confirmed that a VM is the clean zero-cost path and flagged the QR/key handling; its provider free-tier numbers were not used because they conflict with the providers' own pages.
- No live tunnel yet: the phone is on mobile data and no cloud VM exists. `phone.conf` is not deployed, and no WireGuard handshake has been claimed.

## Next action

Create the cloud VM (or provide SSH to an existing one). Then run the one-line installer and scan the QR. After that, the live checks above can be run and a real handshake receipt recorded.
