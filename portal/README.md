# Portal — Rongle Management API

FastAPI backend providing user authentication, device management, subscription billing, metered VLM proxy, and audit log verification. Devices connect to the portal instead of holding API keys directly.

## Running

```bash
pip install -r portal/requirements.txt

# Required
export JWT_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
export GEMINI_API_KEY=your_key_here

# Optional
export DATABASE_URL=sqlite+aiosqlite:///./rongle.db  # default
export RONGLE_DEBUG=true                              # SQL echo + debug logs

uvicorn portal.app:app --host 0.0.0.0 --port 8000 --reload

# Interactive API docs at http://localhost:8000/docs
```

## Database

SQLAlchemy 2.0 async with aiosqlite (SQLite for MVP). Swap `DATABASE_URL` to `postgresql+asyncpg://...` for production. Tables auto-created on first startup.

### Models

| Model | Key Fields | Relationships |
|-------|-----------|---------------|
| **User** | email (unique), hashed_password, display_name, is_admin | → devices, subscription, usage_records |
| **Device** | name, hardware_type, api_key (`rng_` prefix, unique), is_online, settings_json, policy_json | → owner (User), audit_entries |
| **Subscription** | tier, llm_quota_monthly, llm_used_this_month, max_devices, billing_cycle_start | → user (1:1) |
| **UsageRecord** | action, model, tokens_input, tokens_output, latency_ms | → user |
| **AuditEntry** | sequence, timestamp, action, screenshot_hash, previous_hash, entry_hash | → device (unique on device_id+sequence) |

## Authentication

- **Passwords:** bcrypt with auto-deprecation (passlib)
- **Tokens:** JWT via python-jose, HS256 algorithm
  - Access token: 60 minute expiry, `type: "access"` claim
  - Refresh token: 30 day expiry, `type: "refresh"` claim
- **Device auth:** `X-Device-Key` header with API key (`rng_` prefix)

## API Reference

All endpoints prefixed with `/api`. Authentication via `Authorization: Bearer <token>` unless noted.

### Auth

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/register` | None | Create account. Returns access + refresh tokens. Auto-creates free subscription. |
| POST | `/auth/login` | None | Email + password login. Returns tokens. |
| POST | `/auth/refresh` | None | Exchange refresh token for new token pair. |

### Users

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/users/me` | Bearer | Current user profile. |
| PATCH | `/users/me` | Bearer | Update display_name and/or password. |

### Devices

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/devices/` | Bearer | List user's devices. |
| POST | `/devices/` | Bearer | Register new device. Enforces subscription device limit. |
| GET | `/devices/{id}` | Bearer | Device details (includes API key). |
| DELETE | `/devices/{id}` | Bearer | Remove device. |
| PATCH | `/devices/{id}/settings` | Bearer | Partial JSON merge on device settings. |
| POST | `/devices/{id}/regenerate-key` | Bearer | Rotate device API key. |
| POST | `/devices/{id}/heartbeat` | Device Key | Mark device online, update last_seen. |

### Policies

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/devices/{id}/policy` | Bearer | Get device policy JSON. |
| PUT | `/devices/{id}/policy` | Bearer | Replace entire policy. |
| PATCH | `/devices/{id}/policy` | Bearer | Merge into existing policy. |

### LLM Proxy

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/llm/query` | Bearer | Metered VLM query. Checks quota, proxies to Gemini, records usage. |

**Request body:**
```json
{
  "prompt": "Find the search button",
  "image_base64": "<jpeg base64>",  // optional
  "model": "gemini-2.0-flash",
  "device_id": "abc123"
}
```

**Response:**
```json
{
  "result": "...",
  "tokens_input": 1024,
  "tokens_output": 256,
  "latency_ms": 1850,
  "remaining_quota": 1742
}
```

Returns `429` if quota exceeded.

### Subscriptions

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/subscription/` | Bearer | Current subscription details. |
| PUT | `/subscription/` | Bearer | Change tier. Updates quota + device limits. |
| GET | `/subscription/usage` | Bearer | Current billing cycle usage (calls, tokens). |

**Tier limits:**

| Tier | Quota/month | Max devices |
|------|-------------|-------------|
| free | 100 | 1 |
| starter | 2,000 | 3 |
| pro | 20,000 | 10 |
| enterprise | 999,999,999 | 999,999 |

### Audit

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/devices/{id}/audit` | Bearer | Paginated audit entries (newest first). `?limit=50&offset=0` |
| GET | `/devices/{id}/audit/verify` | Bearer | Server-side Merkle chain verification. Returns `{valid, entries_checked, error}`. |
| POST | `/audit/sync` | Device Key | Batch upload audit entries from device. Skips duplicates by sequence. |

### WebSocket

| Path | Auth | Direction | Description |
|------|------|-----------|-------------|
| `/ws/device/{id}?key=<api_key>` | Device Key | Device → Server | Device sends telemetry JSON. Server can send commands back. Broadcasts to watchers. |
| `/ws/watch/{id}?token=<jwt>` | Bearer | Server → User | User receives live telemetry. Can send commands that relay to device. |

## Middleware

- **RateLimitMiddleware** — Sliding window per client IP. Default 60 requests/minute. Returns `429` with `Retry-After` header.
- **RequestLoggingMiddleware** — Logs method, path, status code, and latency for every request.
- **CORSMiddleware** — Configurable origins via `CORS_ORIGINS` env var.

## Environment Variables

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./rongle.db` | No | Async SQLAlchemy URL |
| `JWT_SECRET` | auto-generated | **Production: Yes** | HMAC signing key |
| `JWT_ALGORITHM` | `HS256` | No | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | No | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | No | Refresh token lifetime |
| `GEMINI_API_KEY` | — | **Yes** | Google Gemini API key |
| `ENCRYPTION_KEY` | — | Production: Yes | Data encryption key |
| `RATE_LIMIT_PER_MINUTE` | `60` | No | Per-IP rate limit |
| `CORS_ORIGINS` | `*` | No | Comma-separated origins |
| `RONGLE_DEBUG` | `false` | No | Debug mode |
