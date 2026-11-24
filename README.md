# Private Network Service Platform

Computer Networks Course Project — Team Pradi

A private, fully local network service built on two macOS laptops. A client resolves a private domain through the team's own DNS server, connects over HTTPS to an Nginx edge, and is served by one of two load-balanced backends.

| Phase | Focus |
|---|---|
| Phase 1: Build and Observe | DNS, HTTP, TCP, TLS, reverse proxy, load balancing, caching, packet analysis |
| Phase 2: Harden and Recover | Backup DNS, DNS TTL, service isolation, backend failover, DNS-based edge migration, troubleshooting |

The full Phase 2 write-up is in [`Phase_2/PHASE2_REPORT.md`](Phase_2/PHASE2_REPORT.md).

## Architecture

| Machine | IP Address | Roles |
|---|---|---|
| Mac 1 | `172.20.10.2` | Primary DNS (dnsmasq), standby Nginx edge, test client |
| Mac 2 | `172.20.10.3` | Backup DNS, primary Nginx edge, Backend A (3001), Backend B (3002) |

`app.team1.test` and `api.team1.test` resolve to `172.20.10.3`. Nginx serves HTTPS on port `8443`.

```text
Client --DNS (53)--> Mac 1 primary / Mac 2 backup
       --HTTPS (8443)--> Mac 2 Nginx --> Backend A :3001
                                     --> Backend B :3002
```

## Repository Structure

```text
Phase_1/
  backend/      Backend A and B source (Python)
  config/       dnsmasq, Nginx and OpenSSL configuration
  capture/      Wireshark captures
  docs/         Topology, architecture and request-flow diagrams
  evidence/     DNS, TLS and load-balancing screenshots
  tls/          Public certificate and TLS setup notes
Phase_2/
  PHASE2_REPORT.md
  config/       Standby edge Nginx configuration
  cert/         Regenerated public certificate
  docs/         Final network architecture diagram
  evidence/     Evidence per extension (A to E)
```

## Phase 1 Summary

- Private DNS on Mac 1 resolving the project domains to Mac 2.
- Two Python REST backends returning JSON with an `X-Backend` header.
- Nginx reverse proxy with round-robin load balancing and TLS termination using a locally trusted certificate.
- `Cache-Control` and `ETag` headers for HTTP caching.
- Wireshark evidence of DNS, the TCP handshake, the TLS handshake, and encrypted HTTP.
- Failure demonstrations: wrong DNS server, wrong record, one or both backends stopped, wrong port.

## Phase 2 Summary

| Extension | Result |
|---|---|
| A. Backup DNS | Resolution continued through Mac 2 while Mac 1's DNS was stopped |
| B. DNS TTL | 30-second TTL configured; record changed to `.99` and restored |
| C. Service isolation | pf rule blocked direct access to ports 3001/3002; access through Nginx unaffected |
| D. HA failover | Backend A stopped, all traffic served by B; balancing resumed on restart |
| E. Edge migration | DNS record moved to a standby Nginx on Mac 1, then restored |
| F. Troubleshooting | Layer-by-layer diagnosis: DNS, TCP, TLS, application |

## Running the Project

**Mac 2**
```bash
python3 ~/phase1/backend-a/server.py
python3 ~/phase1/backend-b/server.py
sudo dnsmasq --no-daemon -C ~/CNProject/Phase2/Configs/backup-dnsmasq.conf
nginx -t && sudo nginx
```

**Mac 1**
```bash
sudo dnsmasq -C /opt/homebrew/etc/dnsmasq.conf
```

**Both Macs:** set DNS servers to `172.20.10.2`, then `172.20.10.3`, and flush the cache:
```bash
sudo networksetup -setdnsservers Wi-Fi 172.20.10.2 172.20.10.3
sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder
```

**Verify**
```bash
dig app.team1.test +short
curl -i https://app.team1.test:8443/api/status
```

## Technologies

macOS, dnsmasq, Nginx, Python, OpenSSL, pf, curl, dig, nc, Wireshark.

## Security Note

TLS private keys are excluded from the repository via `.gitignore`. This project is intended for a controlled private LAN and is not configured as an internet-facing service.
