/**
 * app.js
 * ------
 * Handles all frontend interactivity for the Web Search Agent UI.
 * Communicates with the FastAPI backend at /ask.
 */

'use strict';

// ── DOM refs ────────────────────────────────────────────────────────────────
const queryInput = document.getElementById('queryInput');
const sendBtn = document.getElementById('sendBtn');
const messages = document.getElementById('messages');
const welcome = document.getElementById('welcome');
const clearBtn = document.getElementById('clearBtn');
const statusBadge = document.getElementById('statusBadge');
const statusText = document.getElementById('statusText');

// ── State ───────────────────────────────────────────────────────────────────
let isThinking = false;
let currentConversationId = null;

const newChatBtn = document.getElementById("newChatBtn");

newChatBtn.addEventListener("click", () => {
  // Reset conversation
  currentConversationId = null;

  // Clear UI
  messages.innerHTML = "";
  welcome.style.display = "";

  setStatus('', 'Ready');
});

const toggleBtn = document.getElementById("toggleSidebarBtn");
const appLayout = document.getElementById("appLayout");

toggleBtn.addEventListener("click", () => {
  appLayout.classList.toggle("collapsed");
});

function renderMarkdown(md) {
  if (!md) return '';
  let html = md;

  html = html
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    return `<pre><code class="lang-${lang}">${code.trim()}</code></pre>`;
  });

  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

  // Bold & italic
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

  // Horizontal rule
  html = html.replace(/^---$/gm, '<hr>');

  // Blockquotes
  html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');

  // Unordered lists
  html = html.replace(/^[*\-] (.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>\n?)+/g, m => `<ul>${m}</ul>`);

  // Ordered lists
  html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');

  // Links [text](url)
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener">$1</a>');

  // Paragraphs — wrap lines separated by blank lines
  html = html
    .split(/\n{2,}/)
    .map(block => {
      block = block.trim();
      if (!block) return '';
      // Don't wrap if already a block element
      if (/^<(h[1-6]|ul|ol|li|pre|blockquote|hr)/.test(block)) return block;
      return `<p>${block.replace(/\n/g, '<br>')}</p>`;
    })
    .join('\n');

  return html;
}

// ── Status helpers ───────────────────────────────────────────────────────────
function setStatus(mode, text) {
  statusBadge.className = 'status-badge ' + (mode || '');
  statusText.textContent = text;
}

// ── Auto-resize textarea ─────────────────────────────────────────────────────
function resizeInput() {
  queryInput.style.height = 'auto';
  queryInput.style.height = Math.min(queryInput.scrollHeight, 160) + 'px';
  sendBtn.disabled = queryInput.value.trim().length === 0 || isThinking;
}
queryInput.addEventListener('input', resizeInput);

// ── Send on Enter (Shift+Enter = newline) ────────────────────────────────────
queryInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (!sendBtn.disabled) sendMessage();
  }
});
sendBtn.addEventListener('click', sendMessage);

// ── Suggestion chips ─────────────────────────────────────────────────────────
document.querySelectorAll('.suggestion').forEach(btn => {
  btn.addEventListener('click', () => {
    queryInput.value = btn.dataset.query;
    resizeInput();
    sendMessage();
  });
});

// ── Clear chat ───────────────────────────────────────────────────────────────
clearBtn.addEventListener('click', () => {
  messages.innerHTML = '';
  welcome.style.display = '';
  setStatus('', 'Ready');
  currentConversationId = null;
});

// ── Add message bubble ───────────────────────────────────────────────────────
function addUserMessage(text) {
  const el = document.createElement('div');
  el.className = 'msg msg-user';
  el.innerHTML = `
    <div class="msg-bubble">
      ${text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>')}
    </div>`;
  messages.appendChild(el);
  scrollToBottom();
}

function addThinkingBubble() {
  const el = document.createElement('div');
  el.className = 'msg msg-agent';
  el.id = 'thinking';
  el.innerHTML = `
    <div class="thinking-bubble">
      <div class="thinking-dots">
        <span></span><span></span><span></span>
      </div>
      Thinking…
    </div>`;
  messages.appendChild(el);
  scrollToBottom();
  return el;
}
async function loadHistory() {
  try {
    const res = await fetch('/history');
    const data = await res.json();

    const historyList = document.getElementById('historyList');
    historyList.innerHTML = '';

    data.forEach(conv => {
      const div = document.createElement('div');
      div.className = 'history-item';

      // Show short ID or timestamp
      div.textContent = (conv.first_query || "New Chat").slice(0, 40);

      div.dataset.id = conv.conversation_id;
      div.onclick = () => loadConversation(conv.conversation_id);

      historyList.appendChild(div);
    });

  } catch (err) {
    console.error('Failed to load history:', err);
  }
}

function setActiveConversation(id) {
  document.querySelectorAll('.history-item').forEach(el => {
    el.classList.remove('active');
  });

  const active = document.querySelector(`[data-id="${id}"]`);
  if (active) active.classList.add('active');
}

async function loadConversation(conversationId) {
  try {
    currentConversationId = conversationId;
    setActiveConversation(conversationId);

    const res = await fetch(`/history/${conversationId}`);
    const data = await res.json();

    // Clear current messages
    messages.innerHTML = '';
    welcome.style.display = 'none';

    data.forEach(msg => {
      addUserMessage(msg.query);
      addAgentMessage(msg.answer, msg.source);
    });

  } catch (err) {
    console.error('Failed to load conversation:', err);
  }
}

function addAgentMessage(text, source) {
  const thinking = document.getElementById('thinking');
  if (thinking) thinking.remove();

  const sourceMap = {
    llm: {
      label: '🤖 Internal Knowledge',
      class: 'llm',
      icon: `<svg viewBox="0 0 16 16" fill="currentColor" width="10" height="10">
        <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5" fill="none"/>
        <path d="M8 4v4l2.5 2.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
      </svg>`
    },
    web_search: {
      label: '🌐 Web Search',
      class: 'web_search',
      icon: `<svg viewBox="0 0 16 16" fill="none" width="10" height="10">
        <circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.5"/>
        <path d="M8 1.5C8 1.5 5.5 4 5.5 8s2.5 6.5 2.5 6.5M8 1.5C8 1.5 10.5 4 10.5 8S8 14.5 8 14.5M1.5 8h13" stroke="currentColor" stroke-width="1.2"/>
      </svg>`
    },
    moderation: {
      label: '🚫 Moderation',
      class: 'moderation',
      icon: `<svg viewBox="0 0 16 16" fill="none" width="10" height="10">
        <circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.5"/>
        <line x1="4" y1="4" x2="12" y2="12" stroke="currentColor" stroke-width="1.5"/>
      </svg>`
    }
  };

  const config = sourceMap[source] || {
    label: '❓ Unknown',
    class: 'unknown',
    icon: ''
  };

  const el = document.createElement('div');
  el.className = 'msg msg-agent';

  el.innerHTML = `
    <div class="msg-bubble">${renderMarkdown(text)}</div>
    <span class="source-badge ${config.class}">
      ${config.icon} ${config.label}
    </span>
  `;

  messages.appendChild(el);
  scrollToBottom();
}

function addErrorMessage(text) {
  const thinking = document.getElementById('thinking');
  if (thinking) thinking.remove();

  const el = document.createElement('div');
  el.className = 'msg msg-agent';
  el.innerHTML = `
    <div class="msg-bubble" style="border-color:rgba(248,113,113,0.3);background:rgba(248,113,113,0.08);">
      ⚠️ ${text.replace(/</g, '&lt;')}
    </div>`;
  messages.appendChild(el);
  scrollToBottom();
}

// ── Scroll helper ────────────────────────────────────────────────────────────
function scrollToBottom() {
  const area = document.querySelector('.chat-area');
  area.scrollTo({ top: area.scrollHeight, behavior: 'smooth' });
}

// ── Main send function ───────────────────────────────────────────────────────
async function sendMessage() {
  const query = queryInput.value.trim();
  if (!query || isThinking) return;

  if (welcome.style.display !== 'none') {
    welcome.style.display = 'none';
  }

  queryInput.value = '';
  queryInput.style.height = 'auto';
  sendBtn.disabled = true;
  isThinking = true;

  setStatus('thinking', 'Thinking…');
  addUserMessage(query);
  addThinkingBubble();

  try {
    const res = await fetch('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        conversation_id: currentConversationId
      }),
    });

    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try { detail = (await res.json()).detail || detail; } catch { }
      throw new Error(detail);
    }

    const data = await res.json();
    if (!currentConversationId && data.conversation_id) {
      currentConversationId = data.conversation_id;
    }

    let source = data.source;

    if (!source) {
      source = "moderation";
    }

    if (data.answer && data.answer.toLowerCase().includes("keep it clean")) {
      source = "moderation";
    }

    addAgentMessage(data.answer, source);
    loadHistory();
    setStatus('', 'Ready');

  } catch (err) {
    addErrorMessage(`Request failed: ${err.message}`);
    setStatus('error', 'Error');
  } finally {
    isThinking = false;
    sendBtn.disabled = queryInput.value.trim().length === 0;
  }
}

window.addEventListener('load', () => {
  loadHistory();
});