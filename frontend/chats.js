/* Group chats: read and reply to real WhatsApp groups from the platform.
   Gsure Technologies Private Limited. Loaded after app.js and uses its helpers. */
'use strict';

const zdate = (iso) => new Date(iso + (iso && !iso.endsWith('Z') ? 'Z' : ''));
const hm = (d) => d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
function shortWhen(iso) {
  if (!iso) return '';
  const d = zdate(iso), now = new Date();
  if (d.toDateString() === now.toDateString()) return hm(d);
  const y = new Date(now); y.setDate(now.getDate() - 1);
  if (d.toDateString() === y.toDateString()) return 'Yesterday';
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
}
function dayLabel(d) {
  const now = new Date(), y = new Date(now); y.setDate(now.getDate() - 1);
  if (d.toDateString() === now.toDateString()) return 'Today';
  if (d.toDateString() === y.toDateString()) return 'Yesterday';
  return d.toLocaleDateString('en-IN', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' });
}

S.chat = S.chat || { key: null, gid: null, items: [], sig: '', q: '', kind: '',
                     list: [], canSendRole: false };

VIEWS.chats = {
  title: 'Chats', sub: 'Read and reply to your WhatsApp groups from here',
  async render(c) {
    c.innerHTML = `
      <div class="chat-shell">
        <div class="chat-list">
          <div class="search">
            <div style="display:flex;gap:8px">
              <input type="search" id="chQ" placeholder="Search chats" value="${esc(S.chat.q)}">
              <button class="btn" id="chNew" title="Start a one to one chat" style="width:38px;padding:0;flex:none">${icon('plus', 17)}</button>
            </div>
            <div class="chipbar" style="margin-top:10px">
              ${[['', 'All'], ['group', 'Groups'], ['direct', 'Direct']].map(([k, lb]) =>
                `<button class="chipbtn ${S.chat.kind === k ? 'on' : ''}" data-ck="${k}">${lb}</button>`).join('')}
            </div>
          </div>
          <div class="chat-items" id="chItems"><div class="empty"><span class="spin"></span></div></div>
        </div>
        <div class="convo" id="convo"><div class="convo-empty">Choose a chat on the left,
          or start a new one to one chat with the + button.</div></div>
      </div>`;
    $('#chQ', c).oninput = (e) => { S.chat.q = e.target.value; paintList(); };
    $$('[data-ck]', c).forEach(b => b.onclick = () => {
      S.chat.kind = b.dataset.ck;
      $$('[data-ck]', c).forEach(x => x.classList.toggle('on', x === b));
      loadList();
    });
    const nb = $('#chNew', c);
    if (can('campaign.execute')) nb.onclick = newDirectChat; else nb.classList.add('hidden');
    await loadList();
    if (!S.chat.key && S.chat.list.length) S.chat.key = S.chat.list[0].key;
    if (S.chat.key) openChat(S.chat.key, true);
    every(4000, () => { if (S.view === 'chats' && S.chat.gid) refreshConvo(false); });
    every(12000, () => { if (S.view === 'chats') loadList(); });
  }
};

async function loadList() {
  try {
    const d = await api.get('/api/chats?kind=' + (S.chat.kind || ''));
    S.chat.list = d.chats;
    S.chat.canSendRole = d.can_send;
    paintList();
  } catch (e) {
    const el = $('#chItems');
    if (el) el.innerHTML = `<div class="empty">${esc(e.message)}</div>`;
  }
}

function paintList() {
  const el = $('#chItems');
  if (!el) return;
  const q = S.chat.q.trim().toLowerCase();
  const rows = S.chat.list.filter(x => !q || x.name.toLowerCase().includes(q));
  if (!S.chat.list.length) {
    el.innerHTML = S.chat.kind === 'direct'
      ? `<div class="empty">No one to one chats yet.<br>Use <strong>+</strong> above to start one.</div>`
      : `<div class="empty">No live groups yet.<br>Link WhatsApp and import groups
         from <a href="#" id="toCh">Channels</a>.</div>`;
    const a = $('#toCh'); if (a) a.onclick = (e) => { e.preventDefault(); go('channels'); };
    return;
  }
  el.innerHTML = rows.map(x => `
    <button class="chat-item ${x.key === S.chat.key ? 'active' : ''}" data-k="${esc(x.key)}">
      <div class="row1" style="gap:10px">
        <span class="chat-av ${x.kind}">${x.kind === 'group' ? icon('users', 15) : esc(initials(x.name))}</span>
        <span style="flex:1;min-width:0">
          <span class="row1"><span class="nm">${esc(x.name)}</span>
            <span class="tm">${esc(shortWhen(x.last_ts))}</span></span>
          <span class="row1"><span class="pv" style="flex:1">${x.admins_only && !x.can_send ? '\u{1F512} ' : ''}${esc(x.preview || 'No messages captured yet')}</span>
            ${x.messages_24h ? `<span class="badge" title="Messages in the last 24 hours">${x.messages_24h}</span>` : ''}</span>
        </span>
      </div>
    </button>`).join('') || '<div class="empty">No chat matches.</div>';
  $$('[data-k]', el).forEach(b => b.onclick = () => openChat(b.dataset.k, true));
}

function chatMeta(key) { return S.chat.list.find(x => x.key === key) || {}; }

/* Start a one to one conversation. The number is checked with WhatsApp and
   the conversation is recorded; nothing is sent until you type. */
async function newDirectChat() {
  modal('New one to one chat', `
    <div class="field"><label for="ndName">Name <span class="muted-sm">(optional)</span></label>
      <input id="ndName" placeholder="Priya Sharma" autocomplete="off"></div>
    <div class="field"><label for="ndPhone">WhatsApp number</label>
      <input id="ndPhone" placeholder="+91 98765 43210" inputmode="tel" autocomplete="off"></div>
    <p class="hint">Include the country code. A 10 digit number is treated as Indian (+91).
      The number is checked with WhatsApp before the chat opens; no message is sent.</p>
    <div class="note warn">Opening a chat also records that person's replies in this platform.
      Messaging people who have not saved your number raises the risk of WhatsApp restricting the account.</div>`,
    `<button class="btn" data-xnd>Cancel</button>
     <button class="btn primary" id="ndGo">${icon('message', 15)} Open chat</button>`);
  $('[data-xnd]').onclick = closeModal;
  $('#ndPhone').focus();
  const go_ = async () => {
    const btn = $('#ndGo');
    const phone = $('#ndPhone').value.trim();
    if (!phone) return toast('Enter a WhatsApp number.', true);
    btn.disabled = true; btn.innerHTML = '<span class="spin"></span> Checking';
    try {
      const r = await api.post('/api/chats/direct', { phone, name: $('#ndName').value });
      closeModal();
      S.chat.kind = '';
      await loadList();
      openChat(r.chat.key, true);
      toast('Chat opened with ' + r.chat.name);
    } catch (e) {
      toast(e.message, true);
      btn.disabled = false; btn.innerHTML = icon('message', 15) + ' Open chat';
    }
  };
  $('#ndGo').onclick = go_;
  $('#ndPhone').onkeydown = (e) => { if (e.key === 'Enter') go_(); };
}

function openChat(key, fresh) {
  S.chat.key = key;
  S.chat.gid = key && key.startsWith('g:') ? +key.slice(2) : null;
  S.chat.items = []; S.chat.sig = ''; S.chat.more = null;
  S.replyTo = null; S.attach = null;
  paintList();
  const m = chatMeta(key);
  const isGroup = m.kind !== 'direct';
  const role = S.chat.canSendRole;
  const blocked = !role ? `Your role can read these messages but not send. Ask an administrator for Campaign Manager access.`
                : (m.can_send === false ? 'Only admins can send messages in this group.' : '');
  $('#convo').innerHTML = `
    <div class="convo-head">
      <span class="chat-av ${isGroup ? 'group' : 'direct'}" style="width:38px;height:38px">
        ${isGroup ? icon('users', 17) : esc(initials(m.name || '?'))}</span>
      <div style="min-width:0;flex:1">
        <h2 style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(m.name || 'Chat')}</h2>
        <div class="sub">${esc(m.subtitle || '')}${isGroup && m.admins_only ? ' · admins only can send' : ''}</div>
      </div>
      <button class="btn sm" id="chInfo">${isGroup ? icon('chart', 14) + ' Group insights' : icon('list', 14) + ' Message history'}</button>
    </div>
    <div class="convo-body" id="cvBody"><div class="empty"><span class="spin"></span></div></div>
    ${blocked ? `<div class="composer"><div class="note warn" style="margin:0">${esc(blocked)}</div></div>` : `
    <div class="composer">
      <div class="ctx hidden" id="cvReply"></div>
      <div class="ctx hidden" id="cvFile"></div>
      <div class="row">
        <label class="btn" title="Attach a file" style="height:40px;width:40px;padding:0">${icon('paperclip', 17)}
          <input type="file" id="cvAttach" style="display:none"></label>
        <textarea id="cvText" rows="1" placeholder="Type a message"></textarea>
        <button class="btn primary" id="cvSend" style="height:40px">${icon('send', 15)} Send</button>
      </div>
      <div class="foot"><span>Enter to send, Shift+Enter for a new line</span>
        <span>Sends from your linked WhatsApp number</span></div>
    </div>`}`;

  $('#chInfo').onclick = () => {
    if (isGroup) return openGroup(S.chat.gid);
    S.msgs.type = 'individual'; S.msgs.q = m.number || ''; S.msgs.page = 1;
    S.tab = 'individual';
    go('messages');
  };
  const ta = $('#cvText');
  if (ta) {
    ta.addEventListener('input', () => { ta.style.height = 'auto'; ta.style.height = Math.min(160, ta.scrollHeight) + 'px'; });
    ta.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); sendChat(); }
    });
    $('#cvSend').onclick = sendChat;
    $('#cvAttach').onchange = (e) => {
      const f = e.target.files[0];
      S.attach = f || null;
      paintContext();
    };
    ta.focus();
  }
  refreshConvo(true);
}

function paintContext() {
  const r = $('#cvReply'), f = $('#cvFile');
  if (!r || !f) return;
  if (S.replyTo) {
    r.innerHTML = `<span>Replying to <strong>${esc(S.replyTo.who)}</strong>: ${esc(S.replyTo.text.slice(0, 80))}</span>
      <button title="Cancel reply">✕</button>`;
    r.classList.remove('hidden');
    $('button', r).onclick = () => { S.replyTo = null; paintContext(); };
  } else r.classList.add('hidden');
  if (S.attach) {
    f.innerHTML = `<span>\u{1F4CE} ${esc(S.attach.name)} (${Math.max(1, Math.round(S.attach.size / 1024))} KB). Your text becomes the caption.</span>
      <button title="Remove">✕</button>`;
    f.classList.remove('hidden');
    $('button', f).onclick = () => { S.attach = null; $('#cvAttach').value = ''; paintContext(); };
  } else f.classList.add('hidden');
}

async function refreshConvo(first) {
  const key = S.chat.key;
  let d;
  try { d = await api.get('/api/chats/thread?limit=60&key=' + encodeURIComponent(key)); }
  catch (e) { return; }
  if (key !== S.chat.key) return;                   // switched chats meanwhile
  const latest = d.items.slice().reverse();
  const byId = new Map(S.chat.items.map(m => [m.msg_id, m]));
  latest.forEach(m => byId.set(m.msg_id, m));       // newer data wins
  const merged = [...byId.values()].sort((a, b) => a.ts.localeCompare(b.ts));
  const sig = merged.map(m => `${m.msg_id}:${m.read}:${m.delivered}:${m.reactions.length}`).join('|');
  if (first && S.chat.more === null) S.chat.more = d.next_before;
  if (sig === S.chat.sig && !first) return;
  S.chat.items = merged;
  S.chat.sig = sig;
  paintConvo(first);
}

function ticks(m) {
  if (!m.from_me) return '';
  if (m.read) return `<span class="tick-read" title="Read by ${m.read}" data-rc="${esc(m.msg_id)}" style="cursor:pointer">✓✓</span>`;
  if (m.delivered) return `<span title="Delivered to ${m.delivered}" data-rc="${esc(m.msg_id)}" style="cursor:pointer">✓✓</span>`;
  return '<span title="Sent">✓</span>';
}

function paintConvo(forceBottom) {
  const body = $('#cvBody');
  if (!body) return;
  const nearBottom = body.scrollHeight - body.scrollTop - body.clientHeight < 90;
  let html = '', lastDay = '';
  const isGroup = !!S.chat.gid;
  const top = S.chat.more
    ? `<div style="text-align:center;margin-bottom:8px"><button class="btn sm" id="cvOlder">Load earlier messages</button></div>`
    : (S.chat.items.length && isGroup ? `<div style="text-align:center;margin-bottom:8px">
        <button class="btn sm" id="cvPhone" title="Ask your phone for up to 50 older messages">Fetch older from phone</button></div>` : '');
  for (const m of S.chat.items) {
    const d = zdate(m.ts), day = d.toDateString();
    if (day !== lastDay) { html += `<div class="day-sep"><span>${esc(dayLabel(d))}</span></div>`; lastDay = day; }
    const rx = m.reactions && m.reactions.length;
    html += `
      <div class="msg ${m.from_me ? 'me' : ''} ${rx ? 'has-rx' : ''}">
        <div class="bubble">
          ${!m.from_me ? `<div class="who">${esc(m.sender)}</div>` : ''}
          ${m.quoted ? `<div class="q"><strong>${esc(m.quoted[0])}</strong><br>${esc(m.quoted[1])}</div>` : ''}
          ${m.type !== 'text' ? `<div><span class="chip">${esc(m.type)}</span></div>` : ''}
          <div class="txt">${esc(m.text) || (m.type === 'text' ? '' : '')}</div>
          <div class="meta">
            <button class="act" data-reply="${esc(m.msg_id)}">Reply</button>
            <span>${esc(hm(d))}</span>${ticks(m)}
          </div>
          ${rx ? `<div class="rx">${m.reactions.map(esc).join('')}</div>` : ''}
        </div>
      </div>`;
  }
  body.innerHTML = top + (html || `<div class="convo-empty" style="min-height:260px">
      ${isGroup ? 'No messages captured in this group yet.' : 'No messages in this conversation yet.'}<br>
      New messages appear here as they arrive, and you can send the first one below.</div>`);
  $$('[data-reply]', body).forEach(b => b.onclick = () => {
    const m = S.chat.items.find(x => x.msg_id === b.dataset.reply);
    if (!m) return;
    S.replyTo = { id: m.msg_id, who: m.from_me ? 'You' : m.sender, text: m.text || `[${m.type}]` };
    paintContext();
    const ta = $('#cvText'); if (ta) ta.focus();
  });
  $$('[data-rc]', body).forEach(t => t.onclick = () => receiptModal(t.dataset.rc));
  const older = $('#cvOlder');
  if (older) older.onclick = loadOlder;
  const ph = $('#cvPhone');
  if (ph) ph.onclick = async () => {
    ph.disabled = true;
    try {
      await api.post(`/api/groups/${S.chat.gid}/history`);   // groups only
      toast('Asked your phone for older messages. They appear here within a few seconds.');
      setTimeout(() => refreshAllLoaded(), 6000);
    } catch (e) { toast(e.message, true); ph.disabled = false; }
  };
  if (forceBottom || nearBottom) body.scrollTop = body.scrollHeight;
}

async function loadOlder() {
  const body = $('#cvBody');
  const before = S.chat.more;
  if (!before) return;
  const d = await api.get(`/api/chats/thread?limit=60&key=${encodeURIComponent(S.chat.key)}&before=${encodeURIComponent(before)}`);
  const h0 = body.scrollHeight;
  const byId = new Map(S.chat.items.map(m => [m.msg_id, m]));
  d.items.forEach(m => byId.set(m.msg_id, m));
  S.chat.items = [...byId.values()].sort((a, b) => a.ts.localeCompare(b.ts));
  S.chat.more = d.next_before;
  S.chat.sig = '';
  paintConvo(false);
  body.scrollTop = body.scrollHeight - h0;          // keep the reader's place
}

async function refreshAllLoaded() {
  // history arrives asynchronously; pull a wider window once it has landed
  const d = await api.get(`/api/chats/thread?limit=200&key=${encodeURIComponent(S.chat.key)}`);
  const byId = new Map(S.chat.items.map(m => [m.msg_id, m]));
  d.items.forEach(m => byId.set(m.msg_id, m));
  S.chat.items = [...byId.values()].sort((a, b) => a.ts.localeCompare(b.ts));
  S.chat.more = d.next_before;
  S.chat.sig = '';
  paintConvo(false);
}

async function sendChat() {
  const ta = $('#cvText'), btn = $('#cvSend');
  if (!ta || btn.disabled) return;
  const text = ta.value.trim();
  if (!text && !S.attach) return;
  const fd = new FormData();
  fd.append('key', S.chat.key);
  fd.append('text', text);
  if (S.replyTo) fd.append('reply_to', S.replyTo.id);
  if (S.attach) fd.append('file', S.attach);
  btn.disabled = true; btn.innerHTML = '<span class="spin"></span> Sending';
  try {
    await api.form('/api/chats/send', fd);
    ta.value = ''; ta.style.height = 'auto';
    S.replyTo = null; S.attach = null;
    const fi = $('#cvAttach'); if (fi) fi.value = '';
    paintContext();
    await refreshConvo(false);
    const body = $('#cvBody'); if (body) body.scrollTop = body.scrollHeight;
    loadList();
  } catch (e) {
    toast(e.message, true);
  } finally {
    btn.disabled = false; btn.innerHTML = icon('send', 15) + ' Send';
    ta.focus();
  }
}

// Chats needs the full height, so it hides the page header.
VIEWS.chats.bare = true;
