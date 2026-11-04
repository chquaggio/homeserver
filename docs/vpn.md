# qBittorrent over Proton VPN

qBittorrent sends and receives all of its traffic through a WireGuard tunnel to Proton VPN, which the `gluetun` container opens and keeps alive.
The tunnel applies only to containers that share gluetun's network namespace (the isolated network stack a container runs in), and since
qBittorrent is the only container that does, `cloudflared`, Tailscale and every other service keep using the home connection as before.

## Why it exists

Every peer in a public BitTorrent swarm sees the IP address of the clients it exchanges data with, and the agencies that monitor copyrighted
content join swarms in order to collect those addresses. Behind the tunnel, the address they collect is that of a Proton server.

The tunnel covers a single container because a VPN configured on the whole host, or on the router, would also send `cloudflared` and Tailscale
through Proton, which adds latency to the published apps and conflicts with Tailscale's own routing, while the other services gain nothing from
a different public address.

Proton was chosen because it forwards an incoming port on its P2P servers and gluetun supports that natively. Without a forwarded port, other
peers cannot open connections to qBittorrent, which can still download but finds fewer peers and seeds poorly. Mullvad stopped forwarding ports
in 2023, and Proton's free plan does not allow P2P traffic, so the setup requires a paid Proton VPN Plus subscription (Proton Unlimited includes
it).

## How traffic flows

| Traffic | Path |
|---|---|
| Torrent traffic (peers, trackers, DHT) | qBittorrent → gluetun's tunnel interface → Proton P2P server → internet. When the tunnel is down, gluetun's firewall drops the traffic |
| Incoming peer connections | internet → port forwarded on the Proton server → tunnel → qBittorrent. The home router has no rule for qBittorrent |
| WebUI from the LAN or the tailnet | `http://quoggioserver:8585`, published by gluetun, since qBittorrent has no network of its own |
| WebUI and API from other containers | `http://qbittorrent:8585`, which resolves to gluetun through a network alias on `qnet` |
| Every other container, `cloudflared`, Tailscale | home connection, unchanged |

Proton picks the forwarded port at random and usually assigns a new one whenever the tunnel reconnects, so qBittorrent cannot keep a fixed
listening port. Gluetun requests the port through NAT-PMP (the protocol a client uses to ask the VPN server to forward a port to it), renews the
mapping while the tunnel is up, and after each assignment runs `VPN_PORT_FORWARDING_UP_COMMAND`. That command calls qBittorrent's WebUI API on
`127.0.0.1:8585` and sets the listening port and the network interface. When the tunnel goes down, `VPN_PORT_FORWARDING_DOWN_COMMAND` sets the
listening port to 0, because a qBittorrent bug otherwise keeps it from re-establishing the forwarded port after a disconnect. Both commands
reach qBittorrent on localhost because the two containers share one network stack, and for the same reason qBittorrent has to accept
unauthenticated requests from localhost.

Since the port is opened on Proton's side, the home router needs no forwarding rule, and incoming connections work even if the ISP places the
line behind CGNAT (carrier-grade NAT, where several customers share one public IP address and no rule on the home router can open a port).

## Compose definition

`roles/containers/tasks/gluetun.yml` defines the tunnel and `roles/containers/tasks/qbittorrent.yml` attaches qBittorrent to it. The keys below
are the ones whose purpose the files do not explain on their own.

**gluetun**

- `cap_add: [NET_ADMIN]` and `devices: [/dev/net/tun]` let gluetun create the tunnel interface and the firewall rules that act as a kill switch.
- `networks: qnet` with `aliases: [qbittorrent]` keeps the address `qbittorrent:8585` valid, so Sonarr, Radarr and the Homepage widget need no
  change.
- `ports: 8585:8585` publishes qBittorrent's WebUI. Port 6881 is not published anywhere, because the listening port is the one Proton forwards.
- `VPN_SERVICE_PROVIDER=protonvpn` and `VPN_TYPE=wireguard` select the provider. `WIREGUARD_PRIVATE_KEY` comes from the vault as
  `protonvpn_wireguard_key`.
- `VPN_PORT_FORWARDING=on` enables the NAT-PMP request, and `PORT_FORWARD_ONLY=on` restricts server selection to Proton's P2P servers, which are
  the only ones that forward ports.
- `VPN_PORT_FORWARDING_UP_COMMAND` and `VPN_PORT_FORWARDING_DOWN_COMMAND` push the port into qBittorrent as described above. They follow the
  example in the [gluetun wiki](https://github.com/qdm12/gluetun-wiki/blob/main/setup/advanced/vpn-port-forwarding.md), with the WebUI port
  changed from 8080 to 8585.

**qbittorrent**

- `network_mode: "service:gluetun"` makes qBittorrent join gluetun's network namespace, which leaves it the tunnel as its only route to the
  internet. Compose rejects `networks` and `ports` alongside `network_mode`, so qBittorrent declares neither.
- `depends_on` with `condition: service_healthy` and `restart: true` starts qBittorrent only after the tunnel is healthy and makes Compose
  restart it whenever Compose restarts gluetun.

## One-time setup

1. Subscribe to Proton VPN Plus.
2. On account.protonvpn.com, under Downloads → WireGuard configuration, generate a configuration for GNU/Linux with
   **NAT-PMP (Port Forwarding) on** and **Moderate NAT off**, because Proton does not allow both at once. Leave VPN Accelerator on. NetShield
   can stay off, because gluetun runs its own DNS resolver and Proton's DNS filtering therefore never sees the queries. Any P2P server will do,
   since the private key works on all Proton servers.
3. Copy the `PrivateKey` value into the vault with `ansible-vault edit group_vars/all/vault.yml` as `PROTONVPN_KEY`.
   `group_vars/all/services.yml` maps it to `protonvpn_key`.
4. In qBittorrent, under Tools → Options → Web UI, enable "Bypass authentication for clients on localhost". Under Connection, disable "Use UPnP
   / NAT-PMP port forwarding from my router", because it conflicts with Proton's forwarding.
5. If the home router forwards port 6881 to the server, or has UPnP enabled only for qBittorrent, remove the rule or disable UPnP, since neither
   serves a purpose any longer.
6. Deploy with `ansible-playbook site.yml -t containers -e compose_services=gluetun,qbittorrent`.

## Verifying

```bash
# The tunnel is up and Proton assigned a port
docker logs gluetun 2>&1 | grep -i "port forward"

# qBittorrent's public address belongs to Proton; compare with `curl -s ifconfig.me` on the host
docker exec qbittorrent curl -s https://ipinfo.io/ip
```

In the WebUI, the listening port under Tools → Options → Connection must match the port in gluetun's log, and the connection icon in the status
bar must not show "firewalled" once peers start connecting.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| The gluetun log shows no forwarded port | The configuration was generated without NAT-PMP, or with Moderate NAT enabled, or gluetun picked a non-P2P server because `PORT_FORWARD_ONLY` is missing. Regenerate the configuration or fix the environment |
| WebUI unreachable after gluetun restarted | When the Docker daemon restarts a crashed gluetun, Compose is not involved and qBittorrent stays attached to the old, dead namespace. `docker restart qbittorrent` reattaches it |
| qBittorrent reports "firewalled" | The listening port differs from the forwarded one, usually because localhost authentication bypass is off and the up command was rejected. The gluetun log shows the HTTP error from the command |
| Downloads stop entirely | The tunnel is down and the kill switch is blocking traffic. The gluetun log shows why the tunnel dropped, for example an expired subscription or a Proton server under maintenance |
