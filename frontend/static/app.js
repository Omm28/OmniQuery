'use strict';

// ── DOM refs ────────────────────────────────────────────────────────────────
const loginScreen  = document.getElementById('loginScreen');
const userWidget   = document.getElementById('userWidget');
const userAvatar   = document.getElementById('userAvatar');
const userName     = document.getElementById('userName');
const queryInput   = document.getElementById('queryInput');
const sendBtn      = document.getElementById('sendBtn');
const messages     = document.getElementById('messages');
const welcome      = document.getElementById('welcome');
const clearBtn     = document.getElementById('clearBtn');
const statusBadge  = document.getElementById('statusBadge');
const statusText   = document.getElementById('statusText');
const newChatBtn   = document.getElementById('newChatBtn');
const toggleBtn    = document.getElementById('toggleSidebarBtn');
const appLayout    = document.getElementById('appLayout');
const historyList  = document.getElementById('historyList');

// ── State ───────────────────────────────────────────────────────────────────
let isThinking = false;
let currentConversationId = null;

// ── Auth helpers ─────────────────────────────────────────────────────────────

function showLoginScreen() {
  loginScreen.classList.add('visible');
  userWidget.classList.remove('visible');
}

function showApp(user) {
  loginScreen.classList.remove('visible');
  userWidget.classList.add('visible');
  userName.textContent = user.name || user.login;
  if (user.avatar_url) {
    userAvatar.src = user.avatar_url;
    userAvatar.alt = user.login;
  }
}

async function apiFetch(url, options = {}) {
  const res = await fetch(url, { credentials: 'same-origin', ...options });
  if (res.status === 401) {
    showLoginScreen();
    throw new Error('Not authenticated');
  }
  return res;
}

// ── Boot: check auth state ───────────────────────────────────────────────────

async function boot() {
  try {
    const res = await fetch('/auth/me', { credentials: 'same-origin' });
    if (res.status === 401) {
      showLoginScreen();
      return;
    }
    const user = await res.json();
    showApp(user);
    loadHistory();
  } catch {
    showLoginScreen();
  }
}

// ── Sidebar ──────────────────────────────────────────────────────────────────

toggleBtn.addEventListener('click', () => {
  appLayout.classList.toggle('collapsed');
});

newChatBtn.addEventListener('click', () => {
  currentConversationId = null;
  messages.innerHTML = '';
  welcome.style.display = '';
  setStatus('', 'Ready');
});

// ── History ──────────────────────────────────────────────────────────────────

async function loadHistory() {
  try {
    const res = await apiFetch('/history');
    if (!res.ok) return;
    const data = await res.json();

    historyList.innerHTML = '';
    if (data.length === 0) {
      historyList.innerHTML = '<p style="color:rgba(255,255,255,.3);font-size:.8rem;padding:.5rem .25rem">No conversations yet</p>';
      return;
    }

    data.forEach(conv => {
      const div = document.createElement('div');
      div.className = 'history-item';
      div.dataset.id = conv.conversation_id;
      
      const textSpan = document.createElement('div');
      textSpan.className = 'history-item-text';
      textSpan.textContent = (conv.first_query || 'New Chat').slice(0, 40);
      textSpan.onclick = () => loadConversation(conv.conversation_id);
      
      const delBtn = document.createElement('button');
      delBtn.className = 'delete-chat-btn';
      delBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path></svg>';
      delBtn.title = "Delete conversation";
      delBtn.onclick = async (e) => {
        e.stopPropagation();
        await deleteConversation(conv.conversation_id);
      };

      div.appendChild(textSpan);
      div.appendChild(delBtn);
      historyList.appendChild(div);
    });
  } catch {
  }
}

async function deleteConversation(id) {
  try {
    const res = await apiFetch(`/history/${id}`, { method: 'DELETE' });
    if (res.ok) {
      if (currentConversationId === id) {
        currentConversationId = null;
        messages.innerHTML = '';
        welcome.style.display = '';
        setStatus('', 'Ready');
      }
      loadHistory();
    }
  } catch (err) {
    console.error("Failed to delete conversation", err);
  }
}

function setActiveConversation(id) {
  document.querySelectorAll('.history-item').forEach(el => el.classList.remove('active'));
  const active = document.querySelector(`[data-id="${id}"]`);
  if (active) active.classList.add('active');
}

async function loadConversation(conversationId) {
  try {
    currentConversationId = conversationId;
    setActiveConversation(conversationId);

    const res = await apiFetch(`/history/${conversationId}`);
    if (!res.ok) return;
    const data = await res.json();

    messages.innerHTML = '';
    welcome.style.display = 'none';
    data.forEach(msg => {
      addUserMessage(msg.query);
      addAgentMessage(msg.answer, msg.source);
    });
  } catch { }
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

// ── Send on Enter ────────────────────────────────────────────────────────────

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

// ── Message rendering ────────────────────────────────────────────────────────

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
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  html = html.replace(/^---$/gm, '<hr>');
  html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');
  html = html.replace(/^[*\-] (.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>\n?)+/g, m => `<ul>${m}</ul>`);
  html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener">$1</a>');
  html = html
    .split(/\n{2,}/)
    .map(block => {
      block = block.trim();
      if (!block) return '';
      if (/^<(h[1-6]|ul|ol|li|pre|blockquote|hr)/.test(block)) return block;
      return `<p>${block.replace(/\n/g, '<br>')}</p>`;
    })
    .join('\n');

  return html;
}

function addUserMessage(text) {
  const el = document.createElement('div');
  el.className = 'msg msg-user';
  el.innerHTML = `
    <div class="msg-bubble">
      ${text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>')}
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

function addAgentMessage(text, source) {
  const thinking = document.getElementById('thinking');
  if (thinking) thinking.remove();

  const sourceMap = {
    llm: {
      label: '🤖 Internal Knowledge', class: 'llm',
      icon: `<svg viewBox="0 0 16 16" fill="currentColor" width="10" height="10">
        <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5" fill="none"/>
        <path d="M8 4v4l2.5 2.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
      </svg>`
    },
    web_search: {
      label: '🌐 Web Search', class: 'web_search',
      icon: `<svg viewBox="0 0 16 16" fill="none" width="10" height="10">
        <circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.5"/>
        <path d="M8 1.5C8 1.5 5.5 4 5.5 8s2.5 6.5 2.5 6.5M8 1.5C8 1.5 10.5 4 10.5 8S8 14.5 8 14.5M1.5 8h13" stroke="currentColor" stroke-width="1.2"/>
      </svg>`
    },
    moderation: {
      label: '🚫 Moderation', class: 'moderation',
      icon: `<svg viewBox="0 0 16 16" fill="none" width="10" height="10">
        <circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.5"/>
        <line x1="4" y1="4" x2="12" y2="12" stroke="currentColor" stroke-width="1.5"/>
      </svg>`
    }
  };

  const config = sourceMap[source] || { label: '❓ Unknown', class: 'unknown', icon: '' };

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

function scrollToBottom() {
  const area = document.querySelector('.chat-area');
  area.scrollTo({ top: area.scrollHeight, behavior: 'smooth' });
}

// ── Main send function ───────────────────────────────────────────────────────

async function sendMessage() {
  const query = queryInput.value.trim();
  if (!query || isThinking) return;

  if (welcome.style.display !== 'none') welcome.style.display = 'none';

  queryInput.value = '';
  queryInput.style.height = 'auto';
  sendBtn.disabled = true;
  isThinking = true;

  setStatus('thinking', 'Thinking…');
  addUserMessage(query);
  addThinkingBubble();

  try {
    const res = await apiFetch('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, conversation_id: currentConversationId }),
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

    let source = data.source || 'moderation';
    if (data.answer && data.answer.toLowerCase().includes('keep it clean')) {
      source = 'moderation';
    }

    addAgentMessage(data.answer, source);
    loadHistory();
    setStatus('', 'Ready');

  } catch (err) {
    if (err.message !== 'Not authenticated') {
      addErrorMessage(`Request failed: ${err.message}`);
      setStatus('error', 'Error');
    }
  } finally {
    isThinking = false;
    sendBtn.disabled = queryInput.value.trim().length === 0;
  }
}

// ── Init ─────────────────────────────────────────────────────────────────────

window.addEventListener('load', boot);