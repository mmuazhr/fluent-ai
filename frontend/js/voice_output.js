/**
 * VoiceOutput — Browser speechSynthesis TTS wrapper.
 * Speaks AI replies aloud using the best available English voice.
 */
class VoiceOutput {
  constructor() {
    this.synth = window.speechSynthesis;
    this.voice = null;
    this.muted = false;
    this.rate = 0.95;
    this.pitch = 1.0;
    this.onStateChange = null;  // callback(isSpeaking)

    this._loadVoices();

    // Voices may load async in some browsers
    if (this.synth.onvoiceschanged !== undefined) {
      this.synth.onvoiceschanged = () => this._loadVoices();
    }
  }

  _loadVoices() {
    const voices = this.synth.getVoices();
    if (!voices.length) return;

    // Prefer: en-US voices, then any en- voice
    const preferred = [
      'Google US English',
      'Samantha',          // macOS
      'Alex',              // macOS
      'Microsoft Zira',    // Windows
    ];

    for (const name of preferred) {
      const found = voices.find(v => v.name.includes(name));
      if (found) {
        this.voice = found;
        return;
      }
    }

    // Fallback: first en-US voice
    this.voice = voices.find(v => v.lang.startsWith('en-US'))
      || voices.find(v => v.lang.startsWith('en'))
      || voices[0];
  }

  speak(text) {
    if (this.muted || !text) return;

    // Cancel any ongoing speech
    this.synth.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    if (this.voice) utterance.voice = this.voice;
    utterance.rate = this.rate;
    utterance.pitch = this.pitch;
    utterance.lang = 'en-US';

    utterance.onstart = () => {
      if (this.onStateChange) this.onStateChange(true);
    };

    utterance.onend = () => {
      if (this.onStateChange) this.onStateChange(false);
    };

    utterance.onerror = () => {
      if (this.onStateChange) this.onStateChange(false);
    };

    this.synth.speak(utterance);
  }

  stop() {
    this.synth.cancel();
    if (this.onStateChange) this.onStateChange(false);
  }

  toggleMute() {
    this.muted = !this.muted;
    if (this.muted) this.stop();
    return this.muted;
  }
}

// Export as global
window.VoiceOutput = VoiceOutput;
