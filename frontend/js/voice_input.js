/**
 * VoiceInput — Web Speech API wrapper for speech-to-text.
 * Click mic to start, click again to stop and send.
 * Text accumulates while active — no auto-send on pause.
 */
class VoiceInput {
  constructor() {
    this.recognition = null;
    this.isListening = false;
    this.onTranscript = null;       // callback(finalText) — fires on manual stop
    this.onInterim = null;          // callback(interimText) — live preview
    this.onStateChange = null;      // callback(isListening)
    this.supported = false;

    this._accumulated = '';         // text built up while mic is active
    this._init();
  }

  _init() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      console.warn('Web Speech API not supported in this browser');
      return;
    }

    this.supported = true;
    this.recognition = new SpeechRecognition();
    this.recognition.lang = 'en-US';
    this.recognition.interimResults = true;
    this.recognition.continuous = true;
    this.recognition.maxAlternatives = 1;

    this.recognition.onresult = (event) => {
      let interim = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          this._accumulated += (this._accumulated ? ' ' : '') + transcript.trim();
        } else {
          interim += transcript;
        }
      }

      if (this.onInterim) {
        this.onInterim((this._accumulated + (interim ? ' ' + interim : '')).trim());
      }
    };

    this.recognition.onerror = (event) => {
      console.error('Speech recognition error:', event.error);
      if (event.error !== 'aborted') this._stopClean();
    };

    this.recognition.onend = () => {
      if (this.isListening) {
        // Browser ended unexpectedly (timeout/network) — restart to keep active
        try { this.recognition.start(); } catch (_) { this._stopClean(); }
      }
    };
  }

  start() {
    if (!this.supported || this.isListening) return;
    this._accumulated = '';

    try {
      this.recognition.start();
      this.isListening = true;
      if (this.onStateChange) this.onStateChange(true);
    } catch (e) {
      console.error('Failed to start speech recognition:', e);
    }
  }

  stop() {
    if (!this.supported || !this.isListening) return;

    const text = this._accumulated.trim();
    this._stopClean();

    if (text && this.onTranscript) {
      this.onTranscript(text);
    }
  }

  _stopClean() {
    try { this.recognition.stop(); } catch (_) {}
    this.isListening = false;
    this._accumulated = '';
    if (this.onStateChange) this.onStateChange(false);
  }

  toggle() {
    if (this.isListening) this.stop();
    else this.start();
  }
}

window.VoiceInput = VoiceInput;
