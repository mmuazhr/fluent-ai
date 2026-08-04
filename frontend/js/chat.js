const API_BASE = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000/ws/chat';
const SESSION_KEY = 'balqis_session_id';

const GOODBYE_PHRASES = [
  'bye', 'goodbye', 'good bye', 'see you', 'see ya', 'see you later',
  'see you next time', 'gotta go', 'got to go', 'have to go', 'i have to go',
  'talk to you later', 'ttyl', 'take care', 'good night', 'goodnight',
  'end session', 'end this session', 'im done', "i'm done",
  'that\'s all', 'thats all', 'until next time', 'ciao',
];

// ── State ──────────────────────────────────────────

let sessionId = null;
let ws = null;
let voiceIn = null;
let voiceOut = null;
let goodbyePending = false;

// ── DOM Elements ───────────────────────────────────

const welcomeScreen    = document.getElementById('welcomeScreen');
const chatArea         = document.getElementById('chatArea');
const inputArea        = document.getElementById('inputArea');
const sessionControls  = document.getElementById('sessionControls');
const textInput        = document.getElementById('textInput');
const sendBtn          = document.getElementById('sendBtn');
const micBtn           = document.getElementById('micBtn');
const muteBtn          = document.getElementById('muteBtn');
const startBtn         = document.getElementById('startBtn');
const endSessionBtn    = document.getElementById('endSessionBtn');
const newSessionBtn    = document.getElementById('newSessionBtn');
const statusDot        = document.getElementById('statusDot');
const statusText       = document.getElementById('statusText');
const typingIndicator  = document.getElementById('typingIndicator');
const transcriptPreview = document.getElementById('transcriptPreview');
const reflectionModal  = document.getElementById('reflectionModal');

// ── Init ───────────────────────────────────────────

function init() {
  voiceIn = new VoiceInput();
  voiceOut = new VoiceOutput();
  localStorage.removeItem(SESSION_KEY);
  updateUsageBar();

  voiceIn.onTranscript = (text) => {
    transcriptPreview.classList.remove('visible');
    if (text.length >= 2) sendMessage(text);
  };
  voiceIn.onInterim = (text) => {
    transcriptPreview.textContent = text;
    transcriptPreview.classList.add('visible');
  };
  voiceIn.onStateChange = (listening) => {
    micBtn.classList.toggle('active', listening);
    if (listening) setStatus('listening', 'Listening...');
    else { transcriptPreview.classList.remove('visible'); setStatus('idle', 'Ready'); }
  };
  voiceOut.onStateChange = (speaking) => {
    setStatus(speaking ? 'speaking' : 'idle', speaking ? 'Speaking...' : 'Ready');
  };

  micBtn.addEventListener('click', () => {
    if (!voiceIn.supported) {
      alert('Speech recognition not supported. Use Chrome or Edge.');
      return;
    }
    voiceIn.toggle();
  });

  document.addEventListener('keydown', (e) => {
    if (e.code === 'Space' && e.target === document.body && sessionId) {
      e.preventDefault(); voiceIn.toggle();
    }
  });

  muteBtn.addEventListener('click', () => {
    const muted = voiceOut.toggleMute();
    muteBtn.textContent = muted ? '🔇' : '🔊';
    muteBtn.classList.toggle('muted', muted);
  });

  sendBtn.addEventListener('click', () => {
    const text = textInput.value.trim();
    if (text) { sendMessage(text); textInput.value = ''; autoResizeInput(); }
  });

  textInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendBtn.click(); }
  });
  textInput.addEventListener('input', autoResizeInput);

  startBtn.addEventListener('click', startSession);
  endSessionBtn.addEventListener('click', () => endSession(false));
  newSessionBtn.addEventListener('click', () => {
    reflectionModal.classList.remove('visible');
    startSession();
  });
}

// ── Usage Bar ──────────────────────────────────────

const usageLabel   = document.getElementById('usageLabel');
const usageBarFill = document.getElementById('usageBarFill');
let usagePollInterval = null;

async function updateUsageBar() {
  try {
    const params = sessionId ? `?session_id=${sessionId}` : '';
    const res = await fetch(`${API_BASE}/analytics/usage${params}`);
    const data = await res.json();
    const pct = Math.min((data.daily_requests / data.daily_request_limit) * 100, 100);
    usageLabel.textContent = `${data.daily_requests} / ${data.daily_request_limit} req`;
    usageBarFill.style.width = `${pct}%`;
    usageBarFill.className = 'usage-bar-fill' + (pct >= 80 ? ' danger' : pct >= 60 ? ' warn' : '');
  } catch (_) {}
}

function startUsagePolling() {
  updateUsageBar();
  usagePollInterval = setInterval(updateUsageBar, 15000);
}
function stopUsagePolling() {
  clearInterval(usagePollInterval);
  usagePollInterval = null;
}

// ── Session Lifecycle ──────────────────────────────

async function tryResumeSession() {
  const savedId = localStorage.getItem(SESSION_KEY);
  if (!savedId) return;

  try {
    const res = await fetch(`${API_BASE}/sessions/${savedId}`);
    if (!res.ok) { localStorage.removeItem(SESSION_KEY); return; }
    const session = await res.json();

    if (session.ended_at) { localStorage.removeItem(SESSION_KEY); return; }

    // Restore session
    sessionId = savedId;
    showChatUI();
    chatArea.innerHTML = '';

    for (const msg of (session.messages || [])) {
      const correction = msg.correction && msg.correction.original ? msg.correction : null;
      addMessage(msg.role === 'user' ? 'user' : 'assistant', msg.content, correction);
    }

    connectWebSocket();
    setStatus('idle', 'Reconnected');
    startUsagePolling();
  } catch (e) {
    localStorage.removeItem(SESSION_KEY);
  }
}

async function startSession() {
  setStatus('thinking', 'Starting...');
  try {
    const res = await fetch(`${API_BASE}/sessions/start`, { method: 'POST' });
    const data = await res.json();
    sessionId = data.session_id;
    localStorage.setItem(SESSION_KEY, sessionId);

    showChatUI();
    chatArea.innerHTML = '';
    connectWebSocket();

    if (data.greeting) {
      addMessage('assistant', data.greeting);
      voiceOut.speak(data.greeting);
    }

    setStatus('idle', 'Ready');
    startUsagePolling();
  } catch (e) {
    console.error('Failed to start session:', e);
    setStatus('idle', 'Error');
    alert('Could not connect to backend. Make sure uvicorn is running on port 8000.');
  }
}

async function endSession(redirectToDashboard = false) {
  if (!sessionId) return;

  const currentSessionId = sessionId;
  setStatus('thinking', 'Wrapping up...');
  voiceIn.stop();
  voiceOut.stop();
  localStorage.removeItem(SESSION_KEY);

  if (ws) { ws.close(); ws = null; }
  sessionId = null;
  stopUsagePolling();
  updateUsageBar();

  try {
    const res = await fetch(`${API_BASE}/sessions/end?session_id=${currentSessionId}`, { method: 'POST' });
    const data = await res.json();

    if (redirectToDashboard) {
      window.location.href = '/analytics.html';
      return;
    }

    if (data.reflection) showReflection(data.reflection);
    else resetToWelcome();
  } catch (e) {
    console.error('Failed to end session:', e);
    if (redirectToDashboard) window.location.href = '/analytics.html';
    else resetToWelcome();
  }
}

function showChatUI() {
  welcomeScreen.style.display = 'none';
  chatArea.style.display = 'flex';
  inputArea.style.display = 'block';
  sessionControls.style.display = 'flex';
}

function resetToWelcome() {
  welcomeScreen.style.display = 'flex';
  chatArea.style.display = 'none';
  inputArea.style.display = 'none';
  sessionControls.style.display = 'none';
  setStatus('idle', 'Ready');
}

// ── Goodbye Detection ──────────────────────────────

function detectGoodbye(text) {
  const lower = text.toLowerCase().trim();
  return GOODBYE_PHRASES.some(p => lower.includes(p));
}

// ── WebSocket ──────────────────────────────────────

function connectWebSocket() {
  ws = new WebSocket(WS_URL);

  ws.onopen = () => console.log('WebSocket connected');

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    switch (data.type) {
      case 'typing':
        typingIndicator.classList.add('visible');
        setStatus('thinking', 'Thinking...');
        scrollToBottom();
        break;

      case 'reply':
        typingIndicator.classList.remove('visible');
        addMessage('assistant', data.text, data.correction);
        voiceOut.speak(data.text);
        setStatus('idle', 'Ready');

        if (goodbyePending) {
          goodbyePending = false;
          // Let user hear/read the goodbye reply, then redirect
          setTimeout(() => endSession(true), 2000);
        }
        break;

      case 'error':
        typingIndicator.classList.remove('visible');
        console.error('Server error:', data.message);
        setStatus('idle', 'Ready');
        break;
    }
  };

  ws.onclose = () => console.log('WebSocket disconnected');
  ws.onerror = (e) => console.error('WebSocket error:', e);
}

// ── Messaging ──────────────────────────────────────

function sendMessage(text) {
  if (!ws || ws.readyState !== WebSocket.OPEN || !sessionId) return;

  if (detectGoodbye(text)) goodbyePending = true;

  addMessage('user', text);
  ws.send(JSON.stringify({ type: 'message', session_id: sessionId, content: text }));
  setStatus('thinking', 'Thinking...');
}

// ── UI Rendering ───────────────────────────────────

function addMessage(role, text, correction = null) {
  const msg = document.createElement('div');
  msg.className = `message ${role}`;

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;
  msg.appendChild(bubble);

  if (role === 'assistant' && correction) {
    const badge = document.createElement('div');
    badge.className = 'correction-badge';
    badge.textContent = '✏️ Natural phrasing';
    msg.appendChild(badge);

    // Build correction detail via DOM + textContent — never innerHTML.
    // correction.* originates from user/LLM text and must not be parsed as HTML (XSS).
    const detail = document.createElement('div');
    detail.className = 'correction-detail';

    const origRow = document.createElement('div');
    const origSpan = document.createElement('span');
    origSpan.className = 'correction-original';
    origSpan.textContent = correction.original ?? '';
    origRow.appendChild(origSpan);

    const impRow = document.createElement('div');
    impRow.append('→ ');
    const impSpan = document.createElement('span');
    impSpan.className = 'correction-improved';
    impSpan.textContent = correction.improved ?? '';
    impRow.appendChild(impSpan);

    const noteRow = document.createElement('div');
    noteRow.className = 'correction-note';
    noteRow.textContent = correction.note ?? '';

    detail.append(origRow, impRow, noteRow);
    msg.appendChild(detail);
    badge.addEventListener('click', () => detail.classList.toggle('visible'));
  }

  const time = document.createElement('div');
  time.className = 'message-time';
  time.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  msg.appendChild(time);

  chatArea.appendChild(msg);
  scrollToBottom();
}

function scrollToBottom() {
  requestAnimationFrame(() => { chatArea.scrollTop = chatArea.scrollHeight; });
}

function setStatus(state, text) {
  statusDot.className = `status-dot ${state === 'idle' ? '' : state}`;
  statusText.textContent = text;
}

function autoResizeInput() {
  textInput.style.height = 'auto';
  textInput.style.height = Math.min(textInput.scrollHeight, 120) + 'px';
}

// ── Reflection Modal ───────────────────────────────

function showReflection(data) {
  document.getElementById('reflectionTitle').textContent = data.session_title || 'Session Summary';

  const score = data.fluency_score || 0;
  document.getElementById('scoreNumber').textContent = score;
  const circumference = 2 * Math.PI * 42;
  const offset = circumference - (score / 10) * circumference;
  const progress = document.getElementById('scoreProgress');
  progress.style.strokeDasharray = circumference;
  setTimeout(() => { progress.style.strokeDashoffset = offset; }, 100);

  const wellList = document.getElementById('wentWellList');
  wellList.innerHTML = '';
  (data.went_well || []).forEach(item => {
    const li = document.createElement('li'); li.textContent = item; wellList.appendChild(li);
  });

  const mistakesList = document.getElementById('mistakesList');
  mistakesList.innerHTML = '';
  (data.recurring_mistakes || []).forEach(item => {
    const li = document.createElement('li');
    li.className = 'mistake-item';
    li.innerHTML = `
      <div><span class="mistake-pattern">${item.pattern || item}</span></div>
      ${item.example ? `<div style="font-size:12px;color:var(--text-muted)">Example: "${item.example}"</div>` : ''}
      ${item.better ? `<div>→ <span class="mistake-better">${item.better}</span></div>` : ''}
    `;
    mistakesList.appendChild(li);
  });

  const vocabList = document.getElementById('vocabList');
  vocabList.innerHTML = '';
  (data.vocab_to_learn || []).forEach(item => {
    const li = document.createElement('li');
    li.innerHTML = `
      <span class="vocab-word">${item.word || item}</span>
      ${item.meaning ? ` — ${item.meaning}` : ''}
      ${item.example ? `<div style="font-size:12px;color:var(--text-muted);margin-top:4px">"${item.example}"</div>` : ''}
    `;
    vocabList.appendChild(li);
  });

  document.getElementById('encouragementText').textContent =
    data.encouragement || "Keep going — you're making great progress!";

  reflectionModal.classList.add('visible');
}

// ── Boot ───────────────────────────────────────────

document.addEventListener('DOMContentLoaded', init);
