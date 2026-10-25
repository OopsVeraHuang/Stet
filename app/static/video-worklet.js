/* Streaming mono resampling to 16 kHz, 20 ms PCM packets; nothing is retained. */
class AgentMicrophone extends AudioWorkletProcessor {
  constructor() { super(); this.phase=0; this.sum=0; this.count=0; this.packet=new Int16Array(320); this.offset=0; }
  process(inputs) {
    const samples=inputs[0]?.[0]; if(!samples) return true;
    for(const sample of samples) {
      this.sum+=sample; this.count++; this.phase+=16000;
      if(this.phase>=sampleRate) {
        const value=Math.max(-1,Math.min(1,this.sum/this.count));
        this.packet[this.offset++]=value<0?value*32768:value*32767;
        this.phase-=sampleRate; this.sum=0; this.count=0;
        if(this.offset===320) { this.port.postMessage(this.packet.buffer,[this.packet.buffer]); this.packet=new Int16Array(320); this.offset=0; }
      }
    }
    return true;
  }
}
registerProcessor('continuity-microphone',AgentMicrophone);
