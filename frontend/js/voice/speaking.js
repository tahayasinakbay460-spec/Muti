// "Kim konuşuyor" göstergesi. Sunucudan gelmez: duyduğumuz her sesin şiddetini
// tarayıcıda ölçeriz (Web Audio API). Böylece sağlayıcıdan bağımsız çalışır ve
// sunucuya saniyede onlarca "konuşuyor" mesajı gitmez.
const LEVEL_THRESHOLD = 0.035;   // bu şiddetin üstü "konuşuyor" sayılır (0-1 arası)
const POLL_MS = 150;
const HOLD_MS = 450;             // kelime aralarında halka yanıp sönmesin diye kısa bir süre açık kalır

export class SpeakingDetector {
  // onChange(Set<kullanıcı id>) yalnızca konuşanlar değişince çağrılır
  constructor(onChange) {
    this.onChange = onChange;
    this.sources = new Map();
    this.lastLoudAt = new Map();
    this.speaking = new Set();
    this.context = null;
    this.timer = null;
  }

  add(userId, stream) {
    this.remove(userId);
    this.context ||= new (window.AudioContext || window.webkitAudioContext)();
    const source = this.context.createMediaStreamSource(stream);
    const analyser = this.context.createAnalyser();
    analyser.fftSize = 512;
    source.connect(analyser);
    this.sources.set(userId, { source, analyser, samples: new Float32Array(analyser.fftSize) });
    this.timer ||= setInterval(() => this.tick(), POLL_MS);
  }

  remove(userId) {
    this.sources.get(userId)?.source.disconnect();
    this.sources.delete(userId);
    this.lastLoudAt.delete(userId);
  }

  // Tarayıcılar sesi ancak kullanıcı bir yere dokunduktan sonra başlatır
  resume() {
    this.context?.resume().catch(() => {});
  }

  tick() {
    const now = Date.now();
    for (const [userId, { analyser, samples }] of this.sources) {
      analyser.getFloatTimeDomainData(samples);
      // RMS: ses dalgasının ortalama büyüklüğü
      let sum = 0;
      for (const value of samples) sum += value * value;
      if (Math.sqrt(sum / samples.length) > LEVEL_THRESHOLD) this.lastLoudAt.set(userId, now);
    }
    const speaking = new Set([...this.lastLoudAt].filter(([, at]) => now - at < HOLD_MS).map(([id]) => id));
    const changed = speaking.size !== this.speaking.size || [...speaking].some((id) => !this.speaking.has(id));
    if (changed) {
      this.speaking = speaking;
      this.onChange(speaking);
    }
  }

  close() {
    clearInterval(this.timer);
    this.sources.forEach(({ source }) => source.disconnect());
    this.sources.clear();
    this.context?.close().catch(() => {});
  }
}
