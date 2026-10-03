# Private Network Service Platform

A two-Mac private network service platform built for the Computer Networks course project.

The project demonstrates DNS resolution, HTTPS, reverse proxying, load balancing, caching, and network traffic analysis on a private LAN.

## Architecture

The project uses two MacBooks connected to the same private Wi-Fi hotspot.

| Mac | IP Address | Role |
|---|---|---|
| Mac 1 | `172.20.10.2` | dnsmasq DNS server |
| Mac 2 | `172.20.10.3` | Nginx edge, TLS, Backend A, Backend B |

Request flow:

```text
Client
   |
   | DNS query
   v
Mac 1 - dnsmasq
172.20.10.2
   |
   | app.team1.test -> 172.20.10.3
   v
Mac 2 - Nginx
172.20.10.3:8443
   |
   +--------> Backend A :3001
   |
   +--------> Backend B :3002
```

## Technologies

- macOS
- Wi-Fi private LAN
- dnsmasq
- Nginx
- Python HTTP Server
- OpenSSL
- curl
- dig
- Wireshark

## DNS

Mac 1 runs dnsmasq and resolves the project domains to Mac 2.

```text
app.team1.test -> 172.20.10.3
api.team1.test -> 172.20.10.3
```

Configuration:

```text
/opt/homebrew/etc/dnsmasq.conf
```

Test:

```bash
dig @172.20.10.2 app.team1.test
```

## Backends

Mac 2 runs two Python HTTP backends.

### Backend A

```text
Port: 3001
File: ~/phase1/backend-a/server.py
```

### Backend B

```text
Port: 3002
File: ~/phase1/backend-b/server.py
```

Both backends provide:

```text
/
 /api/status
```

The `X-Backend` response header identifies which backend handled the request.

## Nginx

Nginx acts as the public entry point and reverse proxy.

Configuration:

```text
/opt/homebrew/etc/nginx/nginx.conf
```

It listens for HTTPS traffic on port `8443` and distributes requests between:

```text
127.0.0.1:3001
127.0.0.1:3002
```

Test load balancing:

```bash
for i in {1..10}; do
  curl -s -D - https://app.team1.test:8443/api/status -o /dev/null | grep X-Backend
done
```

## HTTPS and TLS

TLS is terminated at Nginx using a locally generated certificate for:

```text
app.team1.test
```

Certificate configuration and setup are documented in:

```text
tls/README.md
```

HTTPS can be tested with:

```bash
curl https://app.team1.test:8443/api/status
```

The final test should work without `curl -k`.

## Caching

Backend responses include:

```text
Cache-Control: max-age=60
ETag
```

Inspect the response headers:

```bash
curl -I https://app.team1.test:8443/api/status
```

## Wireshark

Wireshark is used to capture:

- DNS resolution
- TCP connection establishment
- TLS handshake
- HTTPS traffic
- Network ports
- Load-balanced requests

Useful filters:

```text
dns || tcp.port == 8443
```

and:

```text
tcp.port == 8443
```

## Failure Demonstration

The system can be tested by deliberately stopping a backend and observing the effect on requests.

Other tested failure cases include:

- Incorrect DNS configuration
- Incorrect DNS server address
- Backend unavailable
- Both backends unavailable
- Incorrect destination port

## Repository Structure

```text
computer-networks-project/
├── README.md
├── config/
│   ├── dnsmasq.conf
│   ├── nginx.conf
│   └── openssl.cnf
├── backend/
│   ├── backend-a/
│   │   └── server.py
│   └── backend-b/
│       └── server.py
├── tls/
│   ├── server.crt
│   └── README.md
├── evidence/
│   ├── dns-resolution.png
│   ├── https-response.png
│   ├── load-balancing.png
│   ├── cache-control.png
│   ├── tcp-tls-wireshark.png
│   └── failure-demo.png
└── docs/
    ├── topology.png
    └── request-flow.png
```

The TLS private key is intentionally excluded from the repository.

## Running the Project

### Mac 1

Start dnsmasq:

```bash
sudo dnsmasq -C /opt/homebrew/etc/dnsmasq.conf
```

Verify DNS:

```bash
dig @172.20.10.2 app.team1.test
```

### Mac 2

Start Backend A:

```bash
python3 ~/phase1/backend-a/server.py
```

Start Backend B in another terminal:

```bash
python3 ~/phase1/backend-b/server.py
```

Check Nginx:

```bash
nginx -t
```

Then access:

```text
https://app.team1.test:8443
```

## Security Note

Do not commit the Nginx private TLS key to GitHub.

Add the following to `.gitignore`:

```gitignore
server.key
*.key
.DS_Store
__pycache__/
*.pyc
```

This project is intended for a controlled private LAN environment and is not configured as a production internet-facing service.
