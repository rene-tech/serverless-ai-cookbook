/* AudioWorklet runs off the UI thread. Area-average resampling retains phase
 * across render quanta; no 48 kHz packets are mislabeled as 16 kHz. */
class ScientificPCM extends AudioWorkletProcessor {
  constructor() {
    super(); this.ratio = sampleRate / 16000; this.weight = 0; this.sum = 0; this.frame = [];
    this.port.onmessage = (event) => {
      if (event.data === 'flush') { this.flush(); this.port.postMessage({ flushed: true }); }
    };
  }
  flush() {
    if (!this.frame.length) return;
    const bytes = new ArrayBuffer(this.frame.length * 2);
    const view = new DataView(bytes);
    this.frame.forEach((value, index) => view.setInt16(index * 2, value, true));
    this.frame = []; this.port.postMessage(bytes, [bytes]);
  }
  process(inputs) {
    const channels = inputs[0];
    if (!channels?.length) return true;
    for (let i = 0; i < channels[0].length; i++) {
      let sample = 0;
      for (const channel of channels) sample += channel[i] / channels.length;
      let remaining = 1;
      while (remaining > 1e-8) {
        const amount = Math.min(remaining, this.ratio - this.weight);
        this.sum += sample * amount; this.weight += amount; remaining -= amount;
        if (this.weight >= this.ratio - 1e-8) {
          const value = Math.max(-1, Math.min(1, this.sum / this.ratio));
          this.frame.push(Math.round(value * (value < 0 ? 32768 : 32767)));
          this.weight = 0; this.sum = 0;
          if (this.frame.length === 1600) this.flush();
        }
      }
    }
    return true;
  }
}
registerProcessor('scientific-pcm', ScientificPCM);
