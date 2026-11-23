# TLS Configuration

This folder contains the TLS configuration and public certificate used by Nginx.

## Files

- `server.crt` — public TLS certificate
- `openssl.cnf` — OpenSSL configuration used to generate the certificate

The private key (`server.key`) is kept locally and is not included in the repository.

## Certificate

The certificate is generated for:

```text
app.team1.test
```

Nginx uses the certificate on port `8443` for HTTPS.

## Generate Certificate

```bash
openssl req -x509 -nodes -days 365 \
-newkey rsa:2048 \
-keyout server.key \
-out server.crt \
-config openssl.cnf
```

## Test

```bash
curl https://app.team1.test:8443/api/status
```

Certificate verification should work without using `-k`.

## Security

Never commit `server.key` or any other private key to GitHub.
