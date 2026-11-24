# Phase 2 Final Report: Harden, Recover, and Troubleshoot

**Course:** Computer Networks
**Team:** Team Pradi
**Date:** 24 November 2026

---

## 1. Overview

Phase 2 extends the private network service platform built in Phase 1. The original system was not rebuilt. Instead, it was made more resilient, more secure, and easier to diagnose. Six extensions were addressed: a backup DNS resolver, DNS TTL behaviour, backend service isolation, high-availability failover, DNS-based edge migration, and preparation for a faculty-injected troubleshooting challenge.

All evidence referenced in this report is stored in `Phase_2/evidence/`.

---

## 2. Environment

| Machine | IP Address | Phase 2 Roles |
|---|---|---|
| Mac 1 | `172.20.10.2` | Primary DNS server (dnsmasq), standby Nginx edge, test client |
| Mac 2 | `172.20.10.3` | Backup DNS server (dnsmasq), primary Nginx edge, Backend A (3001), Backend B (3002) |

Both machines were connected to the same Wi-Fi hotspot (`172.20.10.0/28`, gateway `172.20.10.1`). Both clients were configured to use `172.20.10.2` as the primary resolver and `172.20.10.3` as the backup resolver.

| Domain | Record |
|---|---|
| `app.team1.test` | `172.20.10.3` |
| `api.team1.test` | `172.20.10.3` |

Evidence: `00-network-reconnection/`

---

## 3. Changes from Phase 1

| Area | Phase 1 | Phase 2 |
|---|---|---|
| DNS servers | Single dnsmasq server on Mac 1 | Primary on Mac 1 and backup on Mac 2 with identical records |
| Client resolvers | Mac 1 only | Mac 1 (primary) and Mac 2 (backup) |
| DNS TTL | dnsmasq default (0 seconds) | `local-ttl=30` on the primary server |
| TLS | Original certificate | Certificate and private key regenerated with subject alternative names for the project domains |
| Nginx upstream | Plain round-robin | Passive health checks (`max_fails=1 fail_timeout=5s`) and retry on failure (`proxy_next_upstream`) |
| Backend access | Backend ports reachable from the LAN | Backend ports blocked from the LAN by a pf firewall rule (demonstrated, then rolled back) |
| Edge servers | Single Nginx edge on Mac 2 | Standby Nginx edge on Mac 1, reachable through a DNS cutover |

---

## 4. Extensions: Implementation and Results

### 4.1 Extension A: Backup DNS Resolver

**Implementation.** A second dnsmasq instance was configured on Mac 2 with the same project records, listening on `127.0.0.1` and `172.20.10.3`:

```ini
listen-address=127.0.0.1,172.20.10.3
address=/app.team1.test/172.20.10.3
address=/api.team1.test/172.20.10.3
```

Both Macs were configured to list `172.20.10.2` followed by `172.20.10.3` as DNS servers.

**Test procedure.**
1. Both servers were queried directly and returned `172.20.10.3` for both domains.
2. The primary dnsmasq process on Mac 1 was stopped with `sudo kill -TERM <PID>`.
3. A query to `172.20.10.2` timed out (`connection timed out; no servers could be reached`).
4. Queries to `172.20.10.3` continued to return correct answers for both domains.
5. The primary service was restarted.

**Result.** Passed. Name resolution continued through the backup server while the primary was unavailable.

**Evidence.** `extA-backup-dns/01` to `05`, `backup-dns-query.pcapng`, `backup-dns-after-primary-failure.pcapng`

### 4.2 Extension B: DNS TTL and Controlled Record Change

**Implementation.** `local-ttl=30` was added to `/opt/homebrew/etc/dnsmasq.conf` on Mac 1, giving locally defined records a 30-second TTL.

**Test procedure.**
1. `dig @172.20.10.2 app.team1.test +noall +answer` returned `172.20.10.3` with a TTL of 30.
2. The record was changed to `address=/app.team1.test/172.20.10.99`, and dnsmasq was restarted.
3. The server returned `172.20.10.99` with a TTL of 30.
4. The original record was restored and dnsmasq was restarted. The server again returned `172.20.10.3`.

**Result.** Passed for TTL configuration and controlled record change. An additional observation was that dnsmasq reads its configuration only at startup: after the file was edited but before the restart, the server continued to return the previous answer.

**Evidence.** `extB-dns-ttl/01-dns-ttl-30s.png`, `extB-dns-ttl/02-dns-record-change-and-restore.png`

### 4.3 Extension C: Service Isolation

**Implementation.** Because Nginx and both backends run on Mac 2, Nginx reaches the backends over the loopback interface. External traffic to ports 3001 and 3002 was blocked on the Wi-Fi interface (`en0`) using a pf rule. The original configuration was first backed up to `/etc/pf.conf.team1-backup`. The rule was then appended after the Apple anchor declarations in `/etc/pf.conf`:

```pf
block in quick on en0 inet proto tcp from any to (en0) port { 3001, 3002 }
```

The configuration was validated with `sudo pfctl -nf`, loaded with `sudo pfctl -f`, and confirmed with `sudo pfctl -sr`.

**Test procedure.**
1. From Mac 1, `nc -vz -G 3 172.20.10.3 3001` and `3002` both returned `Operation timed out`.
2. On Mac 2, both backends responded on `127.0.0.1`, and the HTTPS endpoint through Nginx continued to work.
3. The original firewall configuration was restored from the backup after the demonstration.

**Result.** Passed. Clients could not reach the backends directly, while the edge retained access.

**Evidence.** `extC-service-isolation/01` to `08`

### 4.4 Extension D: High-Availability Failover

**Implementation.** The Nginx upstream on Mac 2 was configured with passive health checks and retry behaviour:

```nginx
upstream backend_pool {
    server 127.0.0.1:3001 max_fails=1 fail_timeout=5s;
    server 127.0.0.1:3002 max_fails=1 fail_timeout=5s;
}

proxy_next_upstream error timeout invalid_header http_500 http_502 http_503 http_504;
proxy_next_upstream_tries 2;
proxy_next_upstream_timeout 5s;
```

**Test procedure.**
1. Repeated requests returned responses alternating between Backend A and Backend B.
2. Backend A was stopped, and port 3001 stopped listening. All subsequent requests were served by Backend B without client-visible errors.
3. Backend A was restarted. Requests were again distributed across both backends.

**Result.** Passed.

**Single point of failure.** The Nginx edge on Mac 2 remains a single point of failure. If Mac 2 or its Nginx process fails, neither backend can be reached through the application endpoint. Removing this dependency would require a second edge server combined with a floating IP address (for example, VRRP using keepalived) or an external load balancer.

**Evidence.** `extD-backend-failover/01` to `06`, `single-point-of-failure.txt`

### 4.5 Extension E: Controlled Edge Migration

**Implementation.**
1. Nginx 1.31.9 was installed on Mac 1 using Homebrew.
2. The TLS certificate and private key were transferred from Mac 2 to `/opt/homebrew/etc/nginx/certs/` on Mac 1, with permissions `644` (certificate) and `600` (key).
3. The default Nginx configuration on Mac 1 was backed up as `nginx.conf.original`.
4. Mac 1 was configured as a standby edge listening on port 8443 and forwarding to the backends on Mac 2 (`Phase_2/config/nginx.conf`).

**Test procedure.**
1. The standby edge was tested directly using `curl --resolve app.team1.test:8443:172.20.10.2`, and a valid backend response was returned.
2. The DNS configuration on Mac 1 was backed up as `dnsmasq.conf.before-edge-migration`.
3. The record was changed to `address=/app.team1.test/172.20.10.2`, and dnsmasq was restarted.
4. `app.team1.test` resolved to `172.20.10.2`, and HTTPS requests were served through the standby edge.
5. The original record was restored, and `app.team1.test` again resolved to `172.20.10.3`.

**Result.** Passed. Client traffic was moved between edge servers by changing only the DNS record. No change on the client was required.

**Evidence.** `extE-edge-migration/01` to `06`

### 4.6 Extension F: Faculty-Injected Troubleshooting Challenge

This extension is performed live during evaluation. The team has prepared a systematic, bottom-up diagnosis procedure run from the client:

| Step | Layer | Command | Healthy Result |
|---|---|---|---|
| 1 | DNS | `dig app.team1.test` | Expected IP returned by `.2` or `.3` |
| 2 | TCP | `nc -vz -G 3 172.20.10.3 8443` | Connection succeeded |
| 3 | TLS | `openssl s_client -connect app.team1.test:8443 -servername app.team1.test` | `Verify return code: 0 (ok)` |
| 4 | Application | `curl -i https://app.team1.test:8443/api/status` | `200 OK` with an `X-Backend` header |

Server-side confirmation is performed on Mac 2 using `nginx -t`, `lsof`, `pfctl -sr`, and the Nginx error log at `/opt/homebrew/var/log/nginx/error.log`. Known-good copies of each configuration file are kept so that a fault can be confirmed with `diff` once the affected layer has been identified.

---

## 5. Resilience Test Summary

| Test | Fault Introduced | Expected Behaviour | Observed Behaviour | Result |
|---|---|---|---|---|
| A | Primary DNS stopped | Resolution continues via backup | Backup on `.3` answered all queries | Pass |
| B | Record changed to `.99` | New answer served with 30 s TTL | `172.20.10.99`, TTL 30; restored to `.3` | Pass |
| C | Direct access to backend ports | Connections blocked; edge unaffected | `nc` timed out; HTTPS through Nginx worked | Pass |
| D | Backend A stopped | All traffic served by Backend B | Only `X-Backend: B` returned; balancing resumed after restart | Pass |
| E | Record moved to standby edge | Traffic served by Mac 1 | HTTPS served via Mac 1; record restored | Pass |

---

## 6. Troubleshooting Findings

The following problems occurred while implementing Phase 2. Each was diagnosed by identifying the affected layer.

| Problem | Layer | Cause | Resolution |
|---|---|---|---|
| `curl: Could not resolve host: app.team1.test` | DNS | The DNS setting on the client had reverted after reconnecting to the hotspot, because macOS stores DNS settings per network | Re-entered `172.20.10.2` and `172.20.10.3` as DNS servers and flushed the DNS cache |
| `dig` on Mac 2: `no servers could be reached` | DNS | Mac 2's resolver settings had not been configured, and the backup DNS was not yet running | Configured DNS on Mac 2 and started the backup server |
| `can not read …/dnsmasq-backup.conf` | DNS (configuration) | The backup configuration file had not been created on Mac 2 | Created the file |
| `dnsmasq: bad option at line 2` | DNS (configuration) | Invalid characters introduced when the configuration was pasted | Rewrote the file line by line and verified it with `cat -e` |
| HTTPS connection failure | TLS | The TLS private key had been deleted after Phase 1 | Regenerated the certificate and key with OpenSSL and re-trusted the certificate on the clients |
| `Rules must be in order: options, normalization, queueing, translation, filtering` | Firewall | The pf block rule was placed before the Apple anchor declarations | Moved the rule to the end of `/etc/pf.conf` and validated with `pfctl -nf` |
| Edited DNS record not served | DNS (configuration) | dnsmasq had not been restarted after the edit | Restarted dnsmasq |
| `zsh: parse error near '\n'` | Shell | A placeholder such as `<PID>` was typed literally | Replaced it with the actual process ID |

The main lesson from these findings is that most failures were configuration or state problems rather than network faults. Checking each layer in order (resolver settings, server process, listening port, certificate, application) isolated each one quickly.

---

## 7. Learning Summary

**Extension A: Backup DNS.** DNS is a dependency that comes before every connection: if no resolver answers, the client never attempts a TCP connection, even when the server is healthy. A second resolver with identical records removes this single point of failure. The extension also clarified the difference between a DNS failure, where the name cannot be resolved, and an application failure, where resolution and the connection succeed but the backend cannot respond. It also showed that macOS does not strictly query resolvers in order, so failover may involve a short timeout.

**Extension B: DNS TTL.** The TTL tells clients how long they may cache an answer, which trades lookup efficiency against how quickly changes take effect. Short TTLs are set ahead of planned migrations so that clients pick up a new record quickly. The exercise also showed that a change on the server is not the same as a change seen by clients: the server must reload its configuration, and clients holding a cached answer continue to use it until the TTL expires or the cache is flushed.

**Extension C: Service Isolation.** Restricting which hosts can reach a port is a basic defence-in-depth measure. Even though the backends listen on all interfaces, a packet filter can ensure that only the edge reaches them, so clients must go through the controlled entry point. Working with pf showed that rule order matters and that firewall changes should always be validated before loading and backed up for rollback. Blocked connections time out rather than being refused, which distinguishes a firewall from a stopped service.

**Extension D: High-Availability Failover.** Passive health checks let Nginx detect a failed backend from real request failures and route around it without the client noticing, then return the backend to service automatically. Redundancy at one tier does not remove failure points at another: with two backends but one edge, the edge remains the single point of failure.

**Extension E: Edge Migration.** DNS can move traffic between servers without any client change, which is how many production cutovers and disaster-recovery switches are performed. The standby edge needed the same certificate, because the certificate is tied to the domain name rather than to a specific machine. The approach is manual and limited by caching: clients that cached the old record continue to reach the old edge until the TTL expires.

**Extension F: Troubleshooting.** Systematic, bottom-up diagnosis (DNS, then TCP, then TLS, then the application) is faster and more reliable than restarting services at random. Specific symptoms map to specific layers: an unresolved host points to DNS, a refused connection to a service that is not listening, a timeout to a firewall or unreachable host, a certificate error to TLS, and a 502 response to the backend.

---

## 8. Limitations

- The client-side caching window in Extensions B and E (a client continuing to use a cached answer until the TTL expires) was explained but not captured as separate evidence.
- Extension E provides manual, DNS-based recovery rather than automatic edge failover.
- With only two machines available, the backends, the primary edge, and the backup DNS server all share Mac 2, so a failure of Mac 2 affects all three.

---

## 9. Conclusion

Phase 2 converted a working but fragile single-path system into one that tolerates DNS server failure and backend failure, restricts direct backend access, and supports controlled migration between edge servers. Each extension was tested by deliberately introducing a fault and observing the system's behaviour, and the team developed a layer-by-layer method for diagnosing faults that it will apply during the faculty-injected troubleshooting challenge.
