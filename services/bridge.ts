import { LogLevel } from "../types";

type LogCallback = (level: LogLevel, message: string, metadata?: any) => void;

export class AgentBridge {
  private ws: WebSocket | null = null;
  private url: string;
  private onLog: LogCallback;
  private onConnectionChange: (connected: boolean) => void;

  constructor(
    url: string,
    onLog: LogCallback,
    onConnectionChange: (connected: boolean) => void
  ) {
    this.url = url;
    this.onLog = onLog;
    this.onConnectionChange = onConnectionChange;
  }

  connect() {
    try {
      this.onLog(LogLevel.INFO, `Attempting connection to Actuator at ${this.url}...`);
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.onLog(LogLevel.SUCCESS, "Connected to Actuator Bridge");
        this.onConnectionChange(true);
      };

      this.ws.onclose = () => {
        this.onLog(LogLevel.WARNING, "Disconnected from Actuator Bridge");
        this.onConnectionChange(false);
        this.ws = null;
        // Simple reconnect logic could go here
      };

      this.ws.onerror = (error) => {
        this.onLog(LogLevel.ERROR, "WebSocket Error", error);
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "EXECUTION_RESULT") {
             if (data.status === "SUCCESS") {
                this.onLog(LogLevel.SUCCESS, "Actuator: Execution Complete", data);
             } else {
                this.onLog(LogLevel.ERROR, `Actuator: BLOCKED - ${data.message}`, data);
             }
          } else if (data.type === "PONG") {
             // Pong received
          }
        } catch (e) {
          console.error("Failed to parse message", e);
        }
      };

    } catch (e) {
      this.onLog(LogLevel.ERROR, "Failed to create WebSocket", e);
    }
  }

  sendScript(script: string) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.onLog(LogLevel.ERROR, "Cannot send script: Not Connected");
      return;
    }

    this.ws.send(JSON.stringify({
      type: "EXECUTE_SCRIPT",
      script: script
    }));
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
