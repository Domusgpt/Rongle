# Security Model

## Threat Model

Rongle operates across trust boundaries with different threat surfaces at each layer.

### Trust Boundaries

```
┌─────────────────────────────────────────────────────────┐
│ TRUST ZONE 1: Target Computer                           │
│ • No Rongle software installed                          │
│ • Sees only USB HID device (keyboard + mouse)           │
│ • Cannot distinguish from human input                   │
│ • THREAT: Rongle injects malicious commands              │
│   MITIGATION: Policy Engine + Audit Trail                │
└─────────────────────────────────────────────────────────┘
          ▲ USB HID (air gap)
┌─────────────────────────────────────────────────────────┐
│ TRUST ZONE 2: Rongle Device (Phone / Pi)                │
│ • Runs agent code and CNN inference                     │
│ • Has camera/HDMI access to target screen               │
│ • THREAT: Compromised agent bypasses policy              │
│   MITIGATION: Policy runs inline, audit is append-only   │
│ • THREAT: Captured frames leak sensitive data             │
│   MITIGATION: Frames are transient, not persisted         │
└─────────────────────────────────────────────────────────┘
          ▲ HTTPS / WSS
┌─────────────────────────────────────────────────────────┐
│ TRUST ZONE 3: Portal (Cloud)                            │
│ • Holds user accounts, API keys, subscription data      │
│ • Proxies VLM queries (receives screenshots)            │
│ • THREAT: Portal compromise exposes all user data        │
│   MITIGATION: bcrypt passwords, JWT tokens, rate limits  │
│ • THREAT: VLM provider sees target screen data           │
│   MITIGATION: User consent at signup, local VLM option   │
└─────────────────────────────────────────────────────────┘
          ▲ HTTPS
┌─────────────────────────────────────────────────────────┐
│ TRUST ZONE 4: VLM Provider (Gemini API)                 │
│ • Receives screen images for analysis                   │
│ • THREAT: Sensitive screen content (passwords, PII)      │
│   MITIGATION: Local VLM alternative, consent required    │
└─────────────────────────────────────────────────────────┘
```

## Defense Layers

### Layer 1: Hardware Isolation

The fundamental security property of Rongle is the **air gap**. The target computer has no network connection to the Rongle device. All interaction happens through the USB HID protocol — the same protocol used by every keyboard and mouse. This means:

- The target cannot install malware on the Rongle device
- The Rongle device cannot exfiltrate data via network from the target
- The target sees no new software, drivers, or network connections
- Visual data flows one-way: target screen → camera/HDMI → Rongle

### Layer 2: Policy Engine

Every command passes through `PolicyGuardian.check_command()` before reaching the HID output. The policy engine enforces:

**Blocked keystroke patterns (regex):**
- `rm\s+-rf` — recursive force delete
- `:()\{.*\|.*&.*\};:` — fork bomb
- `dd\s+if=` — raw disk write
- `mkfs` — filesystem format
- `chmod\s+777` — world-writable permissions
- `curl.*\|.*sh` / `wget.*\|.*sh` — remote code execution
- `python\s+-c` / `powershell\s+-enc` — inline script execution
- `net\s+user.*\/add` — Windows user creation

**Blocked key combos:**
- `CTRL ALT DELETE` — system interrupt

**Region enforcement:**
- Mouse clicks only within configured screen regions
- Default: full screen allowed (configure per-deployment)

**Rate limiting:**
- Max 50 commands/second
- Max 5000 px/second mouse speed
- Sliding window enforcement

### Layer 3: Immutable Audit Trail

The Merkle hash chain provides cryptographic tamper evidence:

```
hash_N = SHA256( timestamp_N | action_N | screenshot_hash_N | hash_{N-1} )
```

**Properties:**
- **Append-only:** Log file opened with `O_APPEND`, flushed with `fsync()` after every entry
- **Tamper-evident:** Modifying any entry breaks the hash chain for all subsequent entries
- **Resumable:** On restart, replays existing log to restore chain state
- **Verifiable:** Portal can independently verify chain integrity
- **Forensic:** Every action includes the SHA-256 of the screen frame at time of action

**What is logged:**
- Every HID command (keystrokes, mouse moves, clicks)
- Policy verdicts (allowed/blocked) with rule name
- Frame captures with SHA-256 hash
- Calibration events
- System start/stop/errors
- Emergency stop activations

### Layer 4: Authentication and Authorization

**Portal authentication:**
- Passwords hashed with bcrypt (auto-deprecation rounds)
- JWT access tokens expire in 60 minutes
- Refresh tokens expire in 30 days
- Tokens include `type` claim to prevent refresh-as-access attacks
- Token rotation on refresh (old refresh token invalidated)

**Device authentication:**
- Devices authenticate via `X-Device-Key` header
- API keys are `rng_` prefixed + 32 bytes from `secrets.token_urlsafe`
- Keys can be rotated (regenerated) per-device
- Devices never hold VLM API keys

### Layer 5: Network Security

- All portal communication over HTTPS (TLS)
- WebSocket connections authenticated (API key for devices, JWT for users)
- Per-IP rate limiting (60 requests/minute sliding window)
- CORS configured per-deployment
- Request logging with timestamps and latency

## Known Limitations

| Risk | Severity | Status | Notes |
|------|----------|--------|-------|
| Gemini API receives screenshots | Medium | By design | Mitigated by local VLM option and user consent |
| Policy bypass via VLM prompt injection | Medium | Open | VLM could be tricked into generating harmful commands that pass regex filters |
| Rate limiter is in-memory | Low | MVP limitation | Switch to Redis for production multi-process |
| JWT secret auto-generated in dev | Low | By design | Must set `JWT_SECRET` env var in production |
| SQLite not suitable for concurrent writes | Low | MVP limitation | Switch to PostgreSQL for production |
| No TLS pinning on portal client | Low | Open | Trust system CA store |
| Frame data transient but in memory | Low | By design | Not persisted to disk; GC cleans up |
| Vite config bakes GEMINI_API_KEY into bundle | High | Open | Should use server-side proxy only; direct mode is dev convenience |

## Recommendations for Production

1. **Never expose `GEMINI_API_KEY` in frontend bundles.** Use portal proxy mode exclusively.
2. **Set `JWT_SECRET` explicitly.** Auto-generated secrets change on restart, invalidating all tokens.
3. **Switch to PostgreSQL.** SQLite async has concurrency limitations.
4. **Deploy portal behind a reverse proxy** (nginx/Caddy) with TLS termination.
5. **Configure CORS origins explicitly.** `*` is for development only.
6. **Enable policy region restrictions** for production deployments. Full-screen default is permissive.
7. **Monitor audit logs.** Set up alerts for blocked commands and emergency stops.
8. **Use hardware emergency stop** on Pi deployments. Software-only is a development convenience.
9. **Rotate device API keys** periodically.
10. **Run portal with rate limiting tuned** to expected device count.

---
[Back to Documentation Index](INDEX.md)
