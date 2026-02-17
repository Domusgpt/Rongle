/**
 * HID Bridge — Abstraction over multiple methods to inject HID
 * (keyboard/mouse) commands from an Android web app.
 *
 * Supported transports:
 *
 *   1. Web Serial API → CH9329 UART-to-HID chip ($3 USB module)
 *      Best for: reliable hardware HID injection via USB OTG
 *
 *   2. WebSocket → Localhost service (Termux/native companion)
 *      Best for: advanced setups with a background service
 *
 *   3. Clipboard fallback → copies Ducky Script for manual use
 *      Best for: testing without any hardware
 */

import type { HIDConnectionState, HIDMode } from '../types';

// USB HID keyboard scancodes (USB HID Usage Tables §10)
const SCANCODE: Record<string, number> = {
  'a':0x04,'b':0x05,'c':0x06,'d':0x07,'e':0x08,'f':0x09,'g':0x0A,'h':0x0B,
  'i':0x0C,'j':0x0D,'k':0x0E,'l':0x0F,'m':0x10,'n':0x11,'o':0x12,'p':0x13,
  'q':0x14,'r':0x15,'s':0x16,'t':0x17,'u':0x18,'v':0x19,'w':0x1A,'x':0x1B,
  'y':0x1C,'z':0x1D,'1':0x1E,'2':0x1F,'3':0x20,'4':0x21,'5':0x22,'6':0x23,
  '7':0x24,'8':0x25,'9':0x26,'0':0x27,'\n':0x28,'\t':0x2B,' ':0x2C,
  '-':0x2D,'=':0x2E,'[':0x2F,']':0x30,'\\':0x31,';':0x33,"'":0x34,
  '`':0x35,',':0x36,'.':0x37,'/':0x38,
};

const SHIFTED: Record<string, number> = {
  '!':0x1E,'@':0x1F,'#':0x20,'$':0x21,'%':0x22,'^':0x23,'&':0x24,'*':0x25,
  '(':0x26,')':0x27,'_':0x2D,'+':0x2E,'{':0x2F,'}':0x30,'|':0x31,':':0x33,
  '"':0x34,'~':0x35,'<':0x36,'>':0x37,'?':0x38,
};

const SPECIAL_KEYS: Record<string, number> = {
  'ENTER':0x28,'RETURN':0x28,'ESCAPE':0x29,'ESC':0x29,'BACKSPACE':0x2A,
  'TAB':0x2B,'SPACE':0x2C,'DELETE':0x4C,'INSERT':0x49,
  'HOME':0x4A,'END':0x4D,'PAGEUP':0x4B,'PAGEDOWN':0x4E,
  'UP':0x52,'DOWN':0x51,'LEFT':0x50,'RIGHT':0x4F,
  'F1':0x3A,'F2':0x3B,'F3':0x3C,'F4':0x3D,'F5':0x3E,'F6':0x3F,
  'F7':0x40,'F8':0x41,'F9':0x42,'F10':0x43,'F11':0x44,'F12':0x45,
  'CAPSLOCK':0x39,'NUMLOCK':0x53,'PRINTSCREEN':0x46,
};

const MOD_KEYS: Record<string, number> = {
  'CTRL':0x01,'CONTROL':0x01,'SHIFT':0x02,'ALT':0x04,
  'GUI':0x08,'WINDOWS':0x08,'COMMAND':0x08,'META':0x08,
};

// CH9329 protocol constants
const CH9329_HEAD = new Uint8Array([0x57, 0xAB]);  // Packet header
const CH9329_CMD_KEYBOARD = 0x02;
const CH9329_CMD_MOUSE    = 0x05;

// ---------------------------------------------------------------------------
// HID Bridge
// ---------------------------------------------------------------------------
export class HIDBridge {
  private state: HIDConnectionState = {
    connected: false,
    mode: 'none',
    deviceName: '',
    error: null,
  };

  private serialPort: unknown = null;        // Web Serial port
  private serialWriter: any = null; // Writers are complex to type without @types/w3c-web-serial
  private ws: WebSocket | null = null;    // WebSocket connection
  private onStateChange: ((s: HIDConnectionState) => void) | null = null;

  constructor(onChange?: (s: HIDConnectionState) => void) {
    this.onStateChange = onChange || null;
  }

  getState(): HIDConnectionState { return { ...this.state }; }

  private updateState(partial: Partial<HIDConnectionState>) {
    Object.assign(this.state, partial);
    this.onStateChange?.(this.getState());
  }

  // -----------------------------------------------------------------------
  // Connection methods
  // -----------------------------------------------------------------------

  /**
   * Connect via Web Serial API to a CH9329 UART-to-USB-HID bridge.
   * Requires user gesture (button click) to trigger the serial picker.
   */
  async connectWebSerial(): Promise<boolean> {
    if (!('serial' in navigator)) {
      this.updateState({ error: 'Web Serial API not supported in this browser' });
      return false;
    }

    try {
      // @ts-ignore — Web Serial API types
      this.serialPort = await navigator.serial.requestPort();
      await this.serialPort.open({ baudRate: 9600 });
      this.serialWriter = this.serialPort.writable.getWriter();

      this.updateState({
        connected: true,
        mode: 'web_serial',
        deviceName: 'CH9329 / Serial HID',
        error: null,
      });
      return true;
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      this.updateState({ error: `Serial connection failed: ${message}` });
      return false;
    }
  }

  /**
   * Connect via WebSocket to a local companion service.
   * The companion (Termux/native) receives JSON commands and injects HID.
   */
  async connectWebSocket(url = 'ws://localhost:8765'): Promise<boolean> {
    return new Promise((resolve) => {
      try {
        this.ws = new WebSocket(url);
        this.ws.onopen = () => {
          this.updateState({
            connected: true,
            mode: 'websocket',
            deviceName: `WS ${url}`,
            error: null,
          });
          resolve(true);
        };
        this.ws.onerror = () => {
          this.updateState({ error: 'WebSocket connection failed' });
          resolve(false);
        };
        this.ws.onclose = () => {
          this.updateState({ connected: false, mode: 'none', deviceName: '' });
        };
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err);
        this.updateState({ error: message });
        resolve(false);
      }
    });
  }

  /**
   * Use clipboard fallback — Ducky Script is copied, not injected.
   */
  enableClipboardMode(): void {
    this.updateState({
      connected: true,
      mode: 'clipboard',
      deviceName: 'Clipboard (manual)',
      error: null,
    });
  }

  async disconnect(): Promise<void> {
    if (this.serialWriter) {
      await this.serialWriter.releaseLock();
      this.serialWriter = null;
    }
    if (this.serialPort) {
      await this.serialPort.close();
      this.serialPort = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.updateState({ connected: false, mode: 'none', deviceName: '', error: null });
  }

  // -----------------------------------------------------------------------
  // Command execution
  // -----------------------------------------------------------------------

  /**
   * Execute a Ducky Script string.
   * Routes to the appropriate transport based on current connection mode.
   */
  async executeDuckyScript(script: string): Promise<void> {
    const lines = script.trim().split('\n');
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('REM')) continue;
      await this.executeLine(trimmed);
    }
  }

  private async executeLine(line: string): Promise<void> {
    // DELAY
    const delayMatch = line.match(/^DELAY\s+(\d+)$/i);
    if (delayMatch) {
      await sleep(parseInt(delayMatch[1]));
      return;
    }

    // STRING / STRINGLN
    const strMatch = line.match(/^STRINGLN?\s+(.+)$/i);
    if (strMatch) {
      const text = strMatch[1] + (line.toUpperCase().startsWith('STRINGLN') ? '\n' : '');
      for (const ch of text) {
        await this.sendKeystroke(ch);
        await sleep(12);
      }
      return;
    }

    // Modifier combos / special keys
    await this.sendCombo(line);
  }

  private async sendKeystroke(ch: string): Promise<void> {
    let modifier = 0;
    let keycode = 0;

    if (ch in SHIFTED) {
      modifier = 0x02; // LEFT_SHIFT
      keycode = SHIFTED[ch];
    } else {
      const lower = ch.toLowerCase();
      keycode = SCANCODE[lower] || 0;
      if (ch !== lower && ch.match(/[A-Z]/)) {
        modifier = 0x02; // LEFT_SHIFT for uppercase
      }
    }

    await this.sendKeyReport(modifier, keycode);
    await sleep(8);
    await this.sendKeyReport(0, 0); // release
    await sleep(4);
  }

  private async sendCombo(line: string): Promise<void> {
    const tokens = line.split(/\s+/);
    let modifier = 0;
    let keycode = 0;

    for (const token of tokens) {
      const upper = token.toUpperCase();
      if (upper in MOD_KEYS) {
        modifier |= MOD_KEYS[upper];
      } else if (upper in SPECIAL_KEYS) {
        keycode = SPECIAL_KEYS[upper];
      } else if (token.length === 1) {
        const lower = token.toLowerCase();
        keycode = SCANCODE[lower] || 0;
        if (token.match(/[A-Z]/)) modifier |= 0x02;
      }
    }

    if (keycode || modifier) {
      await this.sendKeyReport(modifier, keycode);
      await sleep(50);
      await this.sendKeyReport(0, 0); // release
    }
  }

  // -----------------------------------------------------------------------
  // Transport-level sending
  // -----------------------------------------------------------------------

  private async sendKeyReport(modifier: number, keycode: number): Promise<void> {
    switch (this.state.mode) {
      case 'web_serial':
        await this.serialSendKeyboard(modifier, keycode);
        break;
      case 'websocket':
        this.wsSend({ type: 'keyboard', modifier, keycode });
        break;
      case 'clipboard':
        // No-op for clipboard mode
        break;
    }
  }

  async sendMouseMove(dx: number, dy: number): Promise<void> {
    switch (this.state.mode) {
      case 'web_serial':
        await this.serialSendMouse(0, dx, dy, 0);
        break;
      case 'websocket':
        this.wsSend({ type: 'mouse_move', dx, dy });
        break;
    }
  }

  async sendMouseClick(button: 'left' | 'right' | 'middle' = 'left'): Promise<void> {
    const btnCode = button === 'left' ? 1 : button === 'right' ? 2 : 4;
    switch (this.state.mode) {
      case 'web_serial':
        await this.serialSendMouse(btnCode, 0, 0, 0);
        await sleep(50);
        await this.serialSendMouse(0, 0, 0, 0); // release
        break;
      case 'websocket':
        this.wsSend({ type: 'mouse_click', button: btnCode });
        break;
    }
  }

  async releaseAll(): Promise<void> {
    await this.sendKeyReport(0, 0);
    if (this.state.mode === 'web_serial') {
      await this.serialSendMouse(0, 0, 0, 0);
    }
  }

  /**
   * Copy Ducky Script to clipboard (fallback for any mode).
   */
  async copyToClipboard(script: string): Promise<boolean> {
    try {
      await navigator.clipboard.writeText(script);
      return true;
    } catch {
      return false;
    }
  }

  // -----------------------------------------------------------------------
  // CH9329 Serial protocol
  // -----------------------------------------------------------------------

  private async serialSendKeyboard(modifier: number, keycode: number): Promise<void> {
    if (!this.serialWriter) return;
    // CH9329 keyboard packet: HEAD(2) + ADDR(1) + CMD(1) + LEN(1) + DATA(8) + SUM(1)
    const data = new Uint8Array([
      0x57, 0xAB,       // HEAD
      0x00,              // ADDR
      CH9329_CMD_KEYBOARD,
      0x08,              // LEN = 8 bytes
      modifier & 0xFF,   // modifier byte
      0x00,              // reserved
      keycode & 0xFF,    // key 1
      0x00, 0x00, 0x00, 0x00, 0x00, // keys 2-6
    ]);
    // Checksum: sum of all bytes mod 256
    let sum = 0;
    for (const b of data) sum += b;
    const packet = new Uint8Array([...data, sum & 0xFF]);

    await this.serialWriter.write(packet);
  }

  private async serialSendMouse(
    buttons: number, dx: number, dy: number, wheel: number,
  ): Promise<void> {
    if (!this.serialWriter) return;
    // CH9329 relative mouse packet
    const data = new Uint8Array([
      0x57, 0xAB,
      0x00,
      CH9329_CMD_MOUSE,
      0x05,                           // LEN = 5
      0x01,                           // relative mode
      buttons & 0xFF,
      clampInt8(dx) & 0xFF,
      clampInt8(dy) & 0xFF,
      clampInt8(wheel) & 0xFF,
    ]);
    let sum = 0;
    for (const b of data) sum += b;
    const packet = new Uint8Array([...data, sum & 0xFF]);

    await this.serialWriter.write(packet);
  }

  // -----------------------------------------------------------------------
  // WebSocket transport
  // -----------------------------------------------------------------------

  private wsSend(msg: Record<string, unknown>): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function sleep(ms: number): Promise<void> {
  return new Promise(r => setTimeout(r, ms));
}

function clampInt8(n: number): number {
  return Math.max(-127, Math.min(127, Math.round(n)));
}
