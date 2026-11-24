# Private Network Service Platform

Computer Networks Course Project — Team Pradi

A private, fully local network service platform built on two macOS laptops connected to a shared Wi-Fi hotspot. A client resolves a private domain name through the team's own DNS server, connects over HTTPS to an Nginx edge server, and receives a response from one of two load-balanced backend services.

The project is delivered in two phases:

| Phase | Title | Focus |
|---|---|---|
| Phase 1 | Build and Observe | DNS, HTTP, TCP, TLS, reverse proxying, load balancing, caching, and packet analysis |
| Phase 2 | Harden and Recover | Backup DNS, DNS TTL behaviour, service isolation, high-availability failover, and DNS-based edge migration |

---

## Table of Contents

1. [Network Architecture](#1-network-architecture)
2. [Repository Structure](#2-repository-structure)
3. [Technologies](#3-technologies)
4. [Phase 1: Build and Observe](#4-phase-1-build-and-observe)
5. [Phase 2: Harden and Recover](#5-phase-2-harden-and-recover)
6. [Evidence Index](#6-evidence-index)
7. [Running the Project](#7-running-the-project)
8. [Troubleshooting Methodology](#8-troubleshooting-methodology)
9. [Known Limitations](#9-known-limitations)
10. [Security Note](#10-security-note)

---

## 1. Network Architecture

Both machines are connected to the same private Wi-Fi hotspot on the `172.20.10.0/28` subnet, with default gateway `172.20.10.1`.

| Machine | IP Address | Phase 1 Role | Phase 2 Role |
|---|---|---|---|
| Mac 1 | `172.20.10.2` | Primary DNS server (dnsmasq), test client | Primary DNS server, standby Nginx edge, test client |
| Mac 2 | `172.20.10.3` | Nginx edge, TLS termination, Backend A, Backend B | Backup DNS server, primary Nginx edge, Backend A, Backend B |

### Private Domain Records

| Domain | Resolves To | Served By |
|---|---|---|
| `app.team1.test` | `172.20.10.3` | Mac 1 (primary), Mac 2 (backup) |
| `api.team1.test` | `172.20.10.3` | Mac 1 (primary), Mac 2 (backup) |

### Service Ports

| Port | Protocol | Service |
|---|---|---|
| 53 | UDP/TCP | DNS (dnsmasq) |
| 8443 | TCP | HTTPS (Nginx edge) |
| 3001 | TCP | Backend A |
| 3002 | TCP | Backend B |

### Request Flow

```text
Client
   |
   | 1. DNS query for app.team1.test (UDP 53)
   v
Mac 1 - Primary DNS (172.20.10.2)
Mac 2 - Backup DNS  (172.20.10.3)
   |
   | 2. Answer: app.team1.test -> 172.20.10.3
   v
Mac 2 - Nginx edge (172.20.10.3:8443)
   |  3. TCP handshake, TLS handshake, HTTPS request
   |
   +--------> Backend A (port 3001)
   |
   +--------> Backend B (port 3002)
```

Architecture diagrams are available in `Phase_1/docs/` and `Phase_2/docs/`.

---

## 2. Repository Structure

```text
CNProject_Team_Pradi/
├── README.md
├── Phase_1/
│   ├── backend/
│   │   ├── backend-a/server.py
│   │   └── backend-b/server.py
│   ├── capture/              Phase 1 Wireshark captures (.pcapng)
│   ├── config/
│   │   ├── dnsmasq.conf
│   │   ├── nginx.conf
│   │   └── openssl.cnf
│   ├── docs/                 Topology, architecture and request-flow diagrams
│   ├── evidence/             DNS, TLS and load-balancing screenshots
│   ├── tls/
│   │   ├── server.crt
│   │   └── TLS_README.md
│   └── requirement.txt
└── Phase_2/
    ├── cert/server.crt       Regenerated public certificate
    ├── config/nginx.conf     Standby edge configuration (Mac 1)
    ├── docs/                 Final network architecture diagram
    └── evidence/
        ├── 00-network-reconnection/
        ├── 01-phase1-verification/
        ├── extA-backup-dns/
        ├── extB-dns-ttl/
        ├── extC-service-isolation/
        ├── extD-backend-failover/
        └── extE-edge-migration/
```

---

## 3. Technologies

| Component | Tool |
|---|---|
| Operating system | macOS |
| Network | Private Wi-Fi hotspot (LAN) |
| DNS server | dnsmasq |
| Reverse proxy and load balancer | Nginx |
| Backend services | Python `http.server` |
| Certificates | OpenSSL |
| Firewall | macOS Packet Filter (pf) |
| Diagnostics | `dig`, `curl`, `nc`, `ping`, `lsof`, `pfctl`, Wireshark |

---

## 4. Phase 1: Build and Observe

### 4.1 Private LAN

Both Macs were connected to the same hotspot. Each machine's IPv4 address, subnet mask, default gateway, interface (`en0`) and MAC address were recorded, and reachability was verified with `ping` in both directions.

### 4.2 Private DNS Server (Mac 1)

dnsmasq on Mac 1 resolves the project domains to the edge server.

```ini
listen-address=127.0.0.1,172.20.10.2
address=/app.team1.test/172.20.10.3
address=/api.team1.test/172.20.10.3
```

Client machines were configured to use `172.20.10.2` as their DNS resolver. Resolution was verified with:

```bash
dig @172.20.10.2 app.team1.test
```

### 4.3 Backend Services (Mac 2)

Two minimal Python REST services run on Mac 2.

| Backend | Port | Source |
|---|---|---|
| A | 3001 | `Phase_1/backend/backend-a/server.py` |
| B | 3002 | `Phase_1/backend/backend-b/server.py` |

Each backend serves `GET /` and `GET /api/status`, returning JSON such as:

```json
{"backend": "A", "status": "ok"}
```

Every response carries an `X-Backend` header identifying the backend that served it.

### 4.4 Reverse Proxy and Load Balancing (Mac 2)

Nginx is the single entry point for clients. It listens on port 8443 and distributes requests across both backends using round-robin load balancing. Clients never connect to the backends directly and do not need to know their addresses.

```nginx
upstream backend_pool {
    server 127.0.0.1:3001;
    server 127.0.0.1:3002;
}
```

Configuration: `Phase_1/config/nginx.conf`

### 4.5 HTTPS and TLS

TLS is terminated at Nginx using a locally generated certificate for `app.team1.test`, created with OpenSSL from `Phase_1/config/openssl.cnf`. The certificate is added to the trust store of each client, so HTTPS requests succeed without bypassing certificate validation.

```bash
curl https://app.team1.test:8443/api/status
```

Certificate setup is documented in `Phase_1/tls/TLS_README.md`.

### 4.6 HTTP Caching

Backend responses include `Cache-Control: max-age=60` and an `ETag` header, inspected with:

```bash
curl -I https://app.team1.test:8443/api/status
```

### 4.7 Packet Analysis

Wireshark captures in `Phase_1/capture/` show the complete protocol flow for a single request:

| Layer | Evidence |
|---|---|
| DNS | Query for `app.team1.test` and response containing `172.20.10.3` |
| TCP | SYN, SYN-ACK, ACK handshake before application data |
| TLS | ClientHello, ServerHello, Certificate and key exchange; encrypted application data |
| HTTP | Request and response headers via `curl -v` |
| Load balancing | Alternating `X-Backend: A` and `X-Backend: B` headers |

Useful display filters: `dns || tcp.port == 8443` and `tcp.port == 8443`.

### 4.8 Failure Demonstrations

| Failure | Observation |
|---|---|
| Wrong DNS server on client | Name resolution fails although IP connectivity remains |
| DNS record points to wrong IP | Resolution succeeds but the client reaches the wrong destination |
| One backend stopped | Nginx continues serving through the remaining backend |
| Both backends stopped | DNS and TLS succeed; Nginx returns `502 Bad Gateway` |
| Wrong destination port | Host is reachable but the TCP connection fails |

---

## 5. Phase 2: Harden and Recover

Phase 2 extends the Phase 1 infrastructure without rebuilding it. Before starting, the LAN was re-established, IP addresses were re-verified, and the TLS certificate and private key were regenerated with subject alternative names for the project domains.

### 5.1 Extension A: Backup DNS Resolver

**Objective:** Keep name resolution working when the primary DNS server fails.

A second dnsmasq instance runs on Mac 2 with the same project records.

```ini
listen-address=127.0.0.1,172.20.10.3
address=/app.team1.test/172.20.10.3
address=/api.team1.test/172.20.10.3
```

```bash
sudo dnsmasq --no-daemon -C ~/CNProject/Phase2/Configs/backup-dnsmasq.conf
```

Clients list both resolvers:

```bash
sudo networksetup -setdnsservers Wi-Fi 172.20.10.2 172.20.10.3
```

**Test:** The primary dnsmasq process on Mac 1 was stopped. Queries to `172.20.10.2` timed out, while queries to `172.20.10.3` continued to return `172.20.10.3` for both domains. The primary service was then restored.

**DNS failure versus application failure:** When DNS fails, the name cannot be translated to an IP address and no connection is attempted. When an application server fails, resolution and the TCP/TLS connection to the edge still succeed, but the edge cannot obtain a response from the backend.

### 5.2 Extension B: DNS TTL and Controlled Record Change

**Objective:** Demonstrate how TTL governs DNS caching and record changes.

A 30-second TTL was configured for locally defined records on Mac 1:

```ini
local-ttl=30
```

```bash
dig @172.20.10.2 app.team1.test +noall +answer
```

**Test:** The record for `app.team1.test` was changed to `172.20.10.99`. After dnsmasq was restarted, the server returned the new address with a TTL of 30 seconds. The original record (`172.20.10.3`) was then restored and verified. dnsmasq reads its configuration only at startup, so a restart is required for record changes to take effect.

**Relevance:** In production, short TTLs are set ahead of a planned migration so that clients pick up a changed record quickly. Clients that already hold a cached answer continue using it until the TTL expires, unless the cache is flushed:

```bash
sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder
```

### 5.3 Extension C: Service Isolation

**Objective:** Allow only the Nginx edge to reach the backend ports.

Because the backends and Nginx share Mac 2, Nginx reaches them over the loopback interface. External traffic to ports 3001 and 3002 on `en0` is blocked with a pf rule appended after the Apple anchor declarations in `/etc/pf.conf`:

```pf
block in quick on en0 inet proto tcp from any to (en0) port { 3001, 3002 }
```

```bash
sudo cp /etc/pf.conf /etc/pf.conf.team1-backup
sudo pfctl -nf /etc/pf.conf
sudo pfctl -f /etc/pf.conf
sudo pfctl -e
sudo pfctl -sr
```

**Test:** From Mac 1, direct connections to the backends timed out:

```bash
nc -vz -G 3 172.20.10.3 3001
nc -vz -G 3 172.20.10.3 3002
```

On Mac 2, both backends and the HTTPS endpoint continued to respond.

**Rollback:** The original configuration was restored after the demonstration:

```bash
sudo cp /etc/pf.conf.team1-backup /etc/pf.conf
sudo pfctl -f /etc/pf.conf
```

### 5.4 Extension D: High-Availability Failover

**Objective:** Route traffic only to healthy backends.

Nginx on Mac 2 was configured with passive health checks and request retry:

```nginx
upstream backend_pool {
    server 127.0.0.1:3001 max_fails=1 fail_timeout=5s;
    server 127.0.0.1:3002 max_fails=1 fail_timeout=5s;
}

location / {
    proxy_pass http://backend_pool;
    proxy_next_upstream error timeout invalid_header http_500 http_502 http_503 http_504;
    proxy_next_upstream_tries 2;
    proxy_next_upstream_timeout 5s;
}
```

**Test:**

1. Repeated requests alternated between Backend A and Backend B.
2. Backend A was stopped. All requests were served by Backend B without client-visible errors.
3. Backend A was restarted, and load balancing resumed across both backends.

**Single point of failure:** The Nginx edge on Mac 2 remains a single point of failure. If Mac 2 or its Nginx service fails, neither backend is reachable through the application endpoint. Eliminating this requires a second edge server combined with a floating IP address (for example, VRRP via keepalived) or an external load balancer. Extension E demonstrates a DNS-based alternative.

### 5.5 Extension E: Controlled Edge Migration

**Objective:** Move client traffic from the primary edge to a standby edge using DNS.

1. Nginx 1.31.9 was installed on Mac 1 via Homebrew.
2. The certificate and private key were transferred from Mac 2 to `/opt/homebrew/etc/nginx/certs/` (certificate `644`, key `600`).
3. The original Nginx configuration was backed up as `nginx.conf.original`.
4. Mac 1's Nginx was configured to listen on 8443 and forward to the backends on Mac 2 (`Phase_2/config/nginx.conf`):

```nginx
upstream backend_pool {
    server 172.20.10.3:3001 max_fails=1 fail_timeout=5s;
    server 172.20.10.3:3002 max_fails=1 fail_timeout=5s;
}
```

5. The standby edge was tested directly:

```bash
curl --cacert /opt/homebrew/etc/nginx/certs/server.crt \
  --resolve app.team1.test:8443:172.20.10.2 \
  https://app.team1.test:8443/api/status
```

6. The DNS configuration was backed up as `dnsmasq.conf.before-edge-migration`, and the record was changed:

```ini
address=/app.team1.test/172.20.10.2
```

7. After dnsmasq was restarted, `app.team1.test` resolved to `172.20.10.2`, and HTTPS requests were served through the standby edge on Mac 1.
8. The original record was restored, and `app.team1.test` again resolved to `172.20.10.3`.

**Relevance:** This mirrors DNS-based traffic cutover in production. Clients with a cached record continue to reach the old edge until the TTL expires, while new lookups reach the standby edge.

### 5.6 Extension F: Troubleshooting Challenge

During evaluation, a fault is introduced into the running system. The team diagnoses it layer by layer, as described in [Section 8](#8-troubleshooting-methodology).

---

## 6. Evidence Index

All Phase 2 evidence is stored in `Phase_2/evidence/`. Files are numbered in the order in which the tests were performed.

### 00-network-reconnection

| File | Description |
|---|---|
| `01-mac1-ip-details.png` | Mac 1 IP address, interface, gateway and MAC address |
| `02-mac1-ping-mac2.png` | Reachability from Mac 1 to Mac 2 |
| `03-mac2-ip-details.png` | Mac 2 IP address, interface, gateway and MAC address |
| `04-mac2-ping-mac1.png` | Reachability from Mac 2 to Mac 1 |
| `05-mac2-ip-and-ping-summary.png` | Mac 2 network summary and ping |

### 01-phase1-verification

| File | Description |
|---|---|
| `dns-phase1.pcapng` | Capture verifying the Phase 1 DNS flow after reconnection |

### extA-backup-dns

| File | Description |
|---|---|
| `01-backup-dns-answers.png` | Backup server on Mac 2 answering for both domains |
| `02-wireshark-backup-dns-query.png` | Wireshark view of queries to and responses from `172.20.10.3` |
| `03-primary-down-dig-timeout.png` | Primary DNS stopped; query to `172.20.10.2` times out |
| `04-primary-down-backup-answers.png` | Backup continues to resolve while primary is down |
| `05-primary-down-backup-answers-retest.png` | Repeat of the failover test |
| `backup-dns-query.pcapng` | Capture of backup DNS queries |
| `backup-dns-after-primary-failure.pcapng` | Capture of DNS traffic after primary failure |

### extB-dns-ttl

| File | Description |
|---|---|
| `01-dns-ttl-30s.png` | `local-ttl=30` configured; answers carry a 30-second TTL |
| `02-dns-record-change-and-restore.png` | Record changed to `172.20.10.99`, then restored to `172.20.10.3` |

### extC-service-isolation

| File | Description |
|---|---|
| `01-service-isolation-before.png` | Backend reachability before isolation |
| `02-firewall-before.png` | Firewall state before changes |
| `03-firewall-enabled.png` | macOS firewall enabled |
| `04-stealth-mode-enabled.png` | macOS stealth mode enabled |
| `05-https-access-after-firewall.png` | HTTPS endpoint still reachable |
| `06-firewall-status-mac2.png` | pf status on Mac 2 |
| `07-services-after-firewall.png` | Backends still serving locally |
| `08-direct-backend-blocked.png` | Direct connections from Mac 1 to ports 3001 and 3002 time out |

### extD-backend-failover

| File | Description |
|---|---|
| `01-nginx-upstream-config.png` | Upstream pool with health-check parameters |
| `02-nginx-config-before-failover.png` | Nginx configuration prior to the test |
| `03-nginx-failover-config-valid.png` | Successful `nginx -t` validation |
| `04-load-balancing-before-failure.png` | Responses alternating between Backend A and B |
| `05-backend-a-stopped-failover.png` | Backend A stopped; all requests served by Backend B |
| `06-backend-a-restored-load-balancing.png` | Backend A restored; load balancing resumed |
| `single-point-of-failure.txt` | Analysis of the edge as a single point of failure |

### extE-edge-migration

| File | Description |
|---|---|
| `01-standby-nginx-installed-cert-dir.png` | Nginx installed on Mac 1; certificate directory created |
| `02-nginx-config-backup.png` | Backup of the original standby configuration |
| `03-standby-edge-https-test.png` | Direct HTTPS test against the standby edge |
| `04-dns-edge-cutover.png` | DNS record changed to `172.20.10.2` |
| `05-https-after-dns-cutover.png` | Application served through the standby edge |
| `06-dns-restoration-verified.png` | Original DNS record restored |

---

## 7. Running the Project

### Mac 1

```bash
# Primary DNS
sudo dnsmasq -C /opt/homebrew/etc/dnsmasq.conf
dig @172.20.10.2 app.team1.test +short
```

### Mac 2

```bash
# Backends (separate terminals)
python3 ~/phase1/backend-a/server.py
python3 ~/phase1/backend-b/server.py

# Backup DNS
sudo dnsmasq --no-daemon -C ~/CNProject/Phase2/Configs/backup-dnsmasq.conf

# Edge
nginx -t
sudo nginx            # or: sudo nginx -s reload
```

### Client DNS Configuration (both Macs)

```bash
sudo networksetup -setdnsservers Wi-Fi 172.20.10.2 172.20.10.3
sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder
```

### Verification

```bash
dig app.team1.test +short
curl -i https://app.team1.test:8443/api/status

for i in {1..10}; do
  curl -s -D - https://app.team1.test:8443/api/status -o /dev/null | grep X-Backend
done
```

---

## 8. Troubleshooting Methodology

Faults are isolated from the lowest dependency upward.

| Step | Layer | Command | Healthy Result |
|---|---|---|---|
| 1 | DNS | `dig app.team1.test` | Answer section contains the expected IP |
| 2 | TCP | `nc -vz 172.20.10.3 8443` | Connection succeeded |
| 3 | TLS | `openssl s_client -connect app.team1.test:8443 -servername app.team1.test` | `Verify return code: 0 (ok)` |
| 4 | Application | `curl -v https://app.team1.test:8443/api/status` | `200 OK` with an `X-Backend` header |

| Symptom | Likely Layer | Typical Cause |
|---|---|---|
| `Could not resolve host` | DNS | dnsmasq stopped, wrong resolver configured, missing record |
| Resolves to an unexpected IP | DNS | Incorrect record or stale cached answer |
| `Connection refused` or timeout | TCP | Nginx stopped, wrong port, firewall rule |
| Certificate verification error | TLS | Untrusted, expired or mismatched certificate |
| `502 Bad Gateway` | Application | Backends stopped or wrong upstream address |

---

## 9. Known Limitations

- The client-side caching window in Extensions B and E (a cached client continuing to use the old answer until the TTL expires) was explained but not captured as separate evidence.
- The Nginx edge on Mac 2 remains a single point of failure; Extension E provides manual DNS-based recovery, not automatic failover.
- Because only two machines were available, the backends share Mac 2 with the primary edge, and the backup DNS server shares Mac 2 as well.

---

## 10. Security Note

TLS private keys are not committed to this repository. The following entries are included in `.gitignore`:

```gitignore
server.key
*.key
.DS_Store
```

This project is intended for a controlled private LAN and is not configured as a production, internet-facing service.
