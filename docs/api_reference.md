# Rongle API Reference

## 1. Operator Protocol (WebSocket)

The Operator exposes a WebSocket interface on `ws://<device-ip>:8000`.

### Handshake
**Direction:** Client -> Server
**Message:**
```json
{
  "type": "AUTH",
  "token": "sk_agent_12345"
}
```
**Response:**
```json
{
  "type": "AUTH_RESULT",
  "status": "SUCCESS" // or "FAILED"
}
```

### Commands

#### EXECUTE_SCRIPT
Executes a Ducky Script payload.

**Request:**
```json
{
  "type": "EXECUTE_SCRIPT",
  "script": "DELAY 500\nSTRING Hello World"
}
```

**Response (Success):**
```json
{
  "type": "EXECUTION_RESULT",
  "status": "SUCCESS",
  "message": "Script executed successfully"
}
```

**Response (Blocked):**
```json
{
  "type": "EXECUTION_RESULT",
  "status": "BLOCKED",
  "message": "Policy Violation: 'rm -rf' is forbidden"
}
```

#### PING/PONG
Heartbeat mechanism.

**Request:** `{"type": "PING"}`
**Response:** `{"type": "PONG"}`

---

## 2. Portal API (REST)

The Portal exposes a RESTful API for management.

**Base URL:** `https://api.rongle.ai/v1`

### Authentication

#### POST /auth/login
Obtain a JWT access token.

**Body:**
```json
{
  "username": "user@example.com",
  "password": "secure_password"
}
```

**Response:**
```json
{
  "access_token": "eyJhbG...",
  "token_type": "bearer"
}
```

### Device Management

#### POST /devices/register
Register a new hardware agent.

**Headers:** `Authorization: Bearer <token>`
**Body:**
```json
{
  "device_id": "hw_pi_001",
  "friendly_name": "Lab Raspberry Pi"
}
```

#### GET /devices/list
List all managed devices.

**Response:**
```json
[
  {
    "id": "hw_pi_001",
    "name": "Lab Raspberry Pi",
    "status": "online",
    "last_seen": "2026-02-03T10:00:00Z"
  }
]
```

### Billing

#### POST /subscription/upgrade
Upgrade the account tier.

**Body:**
```json
{
  "tier": "pro",
  "payment_method": "pm_card_visa"
}
```

---

## 3. Policy Definition (JSON)

The `allowlist.json` defines the security boundaries.

```json
{
  "version": "1.0",
  "rules": [
    {
      "name": "Allow Text Input",
      "pattern": "^STRING [a-zA-Z0-9\\s\\.\\-\\/]+$",
      "action": "ALLOW"
    },
    {
      "name": "Block Destructive Commands",
      "pattern": ".*rm -rf.*",
      "action": "BLOCK"
    },
    {
      "name": "Rate Limit",
      "type": "RATE_LIMIT",
      "max_requests": 60,
      "window_seconds": 60
    }
  ]
}
```
