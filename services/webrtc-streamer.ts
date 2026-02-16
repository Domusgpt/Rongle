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

    // Handle ICE candidates?
    // In a simple LAN setup with aiortc, we often just exchange SDP once.
    // aiortc handles trickle ICE or full ICE in SDP.
    // We'll assume the initial offer/answer contains enough candidates or mDNS.

    this.pc.onconnectionstatechange = () => {
      console.log(`WebRTC Connection State: ${this.pc?.connectionState}`);
    };

    try {
      const offer = await this.pc.createOffer();
      await this.pc.setLocalDescription(offer);

      // Wait for ICE gathering to complete?
      // Or just send what we have. aiortc usually works with the initial offer.
      // But robustly, we should wait for 'iceGatheringState' === 'complete' if we don't trickle.
      // Let's implement a simple wait or just send.
      // For now, let's wait a bit or use a promise for ice gathering.

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
