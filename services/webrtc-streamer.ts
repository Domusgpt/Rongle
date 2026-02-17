export class WebRTCStreamer {
  private pc: RTCPeerConnection | null = null;
  private backendUrl: string;

  constructor(backendUrl: string) {
    this.backendUrl = backendUrl.replace(/\/$/, ''); // Remove trailing slash
  }

  async start(stream: MediaStream): Promise<void> {
    if (this.pc) {
      this.stop();
    }

    const config: RTCConfiguration = {
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
    };

    this.pc = new RTCPeerConnection(config);

    // Add tracks
    stream.getTracks().forEach(track => {
      if (this.pc) {
        this.pc.addTrack(track, stream);
      }
    });

    this.pc.onconnectionstatechange = () => {
      console.log(`WebRTC Connection State: ${this.pc?.connectionState}`);
    };

    try {
      const offer = await this.pc.createOffer();
      await this.pc.setLocalDescription(offer);

      await this.waitForIceGathering();

      const response = await fetch(`${this.backendUrl}/offer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sdp: this.pc.localDescription?.sdp,
          type: this.pc.localDescription?.type,
        }),
      });

      if (!response.ok) {
        throw new Error(`Signaling failed: ${response.statusText}`);
      }

      const answer = await response.json();
      await this.pc.setRemoteDescription(new RTCSessionDescription(answer));

    } catch (err) {
      console.error('WebRTC Start Error:', err);
      this.stop();
      throw err;
    }
  }

  stop(): void {
    if (this.pc) {
      this.pc.close();
      this.pc = null;
    }
  }

  private waitForIceGathering(): Promise<void> {
    return new Promise(resolve => {
      if (!this.pc || this.pc.iceGatheringState === 'complete') {
        resolve();
        return;
      }

      const check = () => {
        if (!this.pc || this.pc.iceGatheringState === 'complete') {
          this.pc?.removeEventListener('icegatheringstatechange', check);
          resolve();
        }
      };

      this.pc.addEventListener('icegatheringstatechange', check);
      // Timeout fallback
      setTimeout(() => {
         this.pc?.removeEventListener('icegatheringstatechange', check);
         resolve();
      }, 1000);
    });
  }
}
