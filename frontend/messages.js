/* Messages: send to a group or to one person, and inspect each message's
   delivery metadata. Gsure Technologies Private Limited.
   Loaded after app.js and chats.js; uses their helpers. */
'use strict';

const MSG_STATUS = {
  pending:   { cls: '',     icon: '○',        label: 'Pending' },
  sent:      { cls: 'info', icon: '✓',        label: 'Sent' },
  delivered: { cls: 'good', icon: '✓✓',  label: 'Delivered' },
  read:      { cls: 'read', icon: '✓✓',  label: 'Read' },
  failed:    { cls: 'crit', icon: '✕',        label: 'Failed' },
};
const msgPill = (st) => {
  const x = MSG_STATUS[st] || MSG_STATUS.sent;
  return `<span class="pill ${x.cls}">${x.icon} ${x.label}</span>`;
};
const typePill = (t) => t === 'individual'
  ? `<span class="type-pill ind">${icon('user', 13)} Individual</span>`
  : `<span class="type-pill grp">${icon('users', 13)} Group</span>`;
const tsz = (iso) => iso ? when(iso + (iso.endsWith('Z') ? '' : 'Z')) : '—';

S.msgs = S.msgs || { type: '', status: '', q: '', source: '', page: 1 };

VIEWS.messages = {
  title: 'Messages', sub: 'Send to a group or to one person, and track every message to its recipients',
  async render(c) {
    const st = S.msgs;
    if (can('campaign.execute')) {
      setActions(`<button class="btn" id="mNewInd">${icon('user')} Individual message</button>
                  <button class="btn primary" id="mNewGrp">${icon('users')} Group message</button>`);
      $('#mNewGrp').onclick = () => newMessageModal('group');
      $('#mNewInd').onclick = () => newMessageModal('individual');
    }
    if (S.tab === null || !['all', 'group', 'individual'].includes(S.tab)) S.tab = st.type || 'all';
    setTabs([{ key: 'all', label: 'All messages', icon: 'list' },
             { key: 'group', label: 'Group', icon: 'users' },
             { key: 'individual', label: 'Individual', icon: 'user' }], '',
      (k) => { st.type = k === 'all' ? '' : k; st.page = 1; loadMessages(); });

    c.innerHTML = `
      <div class="toolbar">
        <div class="chipbar" id="mStatus"></div>
        <div class="spacer"></div>
        <select id="mSource" aria-label="Sent from">
          <option value="">Sent from anywhere</option>
          <option value="platform" ${st.source === 'platform' ? 'selected' : ''}>Sent from this platform</option>
          <option value="phone" ${st.source === 'phone' ? 'selected' : ''}>Sent from the phone</option>
          <option value="campaign" ${st.source === 'campaign' ? 'selected' : ''}>Campaign despatch</option>
        </select>
        <input type="search" id="mQ" placeholder="Search message, group or number" value="${esc(st.q)}">
      </div>
      <div class="card">
        <h2 data-icon="send">Sent messages</h2>
        <div class="cap">Status and delivery counts belong to each message. Open one to see every recipient.</div>
        <div id="mTable"><div class="empty"><span class="spin"></span></div></div>
      </div>`;
    let deb;
    $('#mQ', c).oninput = e => { clearTimeout(deb); deb = setTimeout(() => { st.q = e.target.value; st.page = 1; loadMessages(); }, 250); };
    $('#mSource', c).onchange = e => { st.source = e.target.value; st.page = 1; loadMessages(); };
    await loadMessages();
    every(5000, () => { if (S.view === 'messages') loadMessages(true); });
  }
};

async function loadMessages(quiet) {
  const st = S.msgs, el = $('#mTable');
  if (!el) return;
  const p = new URLSearchParams({ type: st.type, status: st.status, q: st.q, source: st.source,
                                  page: st.page, size: 25 });
  let d;
  try { d = await api.get('/api/messages?' + p); } catch (e) { if (!quiet) el.innerHTML = `<div class="err">${esc(e.message)}</div>`; return; }
  const counts = d.status_counts || {};
  const all = Object.values(counts).reduce((a, b) => a + b, 0);
  $('#mStatus').innerHTML = [['', 'All', all], ...Object.keys(MSG_STATUS).map(k => [k, MSG_STATUS[k].label, counts[k] || 0])]
    .map(([k, lb, n_]) => `<button class="chipbtn ${st.status === k ? 'on' : ''}" data-st="${k}">${esc(lb)} <span>${n(n_)}</span></button>`).join('');
  $$('[data-st]', $('#mStatus')).forEach(b => b.onclick = () => { st.status = b.dataset.st; st.page = 1; loadMessages(); });

  const pages = Math.max(1, Math.ceil(d.total / d.size));
  el.innerHTML = d.items.length ? `
    <div class="tbl-wrap"><table>
      <thead><tr><th>Type</th><th>To</th><th>Message</th><th>Sent</th><th>Status</th>
        <th class="num">Recipients</th><th class="num">Delivered</th><th class="num">Read</th>
        <th class="num">Pending</th><th class="num">Failed</th><th></th></tr></thead>
      <tbody>${d.items.map(m => `<tr>
        <td>${typePill(m.type)}</td>
        <td><div style="font-weight:500">${esc(m.to || '—')}</div>
          ${m.type === 'individual' && m.to_number && m.to_number !== m.to ? `<div class="mono muted-sm">${esc(m.to_number)}</div>` : ''}
          ${m.sent_via && m.sent_via !== 'platform' ? `<div class="muted-sm">${m.sent_via === 'phone' ? 'sent from the phone' : 'campaign ' + esc(m.campaign || '')}</div>` : ''}</td>
        <td style="max-width:320px"><div class="clip2">${m.mtype && !['conversation', 'extendedText', 'text'].includes(m.mtype) ? `<span class="chip">${esc(m.mtype)}</span>` : ''}${esc(m.text || '')}</div>
          ${m.status === 'failed' && m.error ? `<div class="muted-sm" style="color:var(--critical)">${esc(m.error)}</div>` : ''}</td>
        <td class="nowrap">${tsz(m.sent_at)}</td>
        <td>${msgPill(m.status)}</td>
        <td class="num">${n(m.total)}</td><td class="num">${n(m.delivered)}</td><td class="num">${n(m.read)}</td>
        <td class="num">${n(m.pending_delivery)}</td><td class="num">${n(m.failed)}</td>
        <td class="right"><button class="btn sm" data-md="${esc(m.msg_id)}">${icon('eye', 14)} View details</button></td>
      </tr>`).join('')}</tbody></table></div>
    <div style="display:flex;align-items:center;margin-top:12px">
      <span class="muted-sm">${n(d.total)} messages · page ${d.page} of ${n(pages)}</span><span class="spacer"></span>
      <div class="btn-row"><button class="btn sm" id="mPrev" ${d.page <= 1 ? 'disabled' : ''}>Previous</button>
        <button class="btn sm" id="mNext" ${d.page >= pages ? 'disabled' : ''}>Next</button></div></div>`
    : `<div class="empty">No messages match.${can('campaign.execute') ? ' Use <strong>Group message</strong> or <strong>Individual message</strong> above to send one.' : ''}</div>`;
  $$('[data-md]', el).forEach(b => b.onclick = () => messageDetails(b.dataset.md));
  const pv = $('#mPrev'), nx = $('#mNext');
  if (pv) pv.onclick = () => { st.page--; loadMessages(); };
  if (nx) nx.onclick = () => { st.page++; loadMessages(); };
}

// ------------------------------------------------------------- compose
async function newMessageModal(kind, presetGroupId) {
  let chats = [], templates = [];
  try {
    [chats, templates] = await Promise.all([
      api.get('/api/chats').then(d => d.chats),
      api.get('/api/templates').then(d => d.templates)]);
  } catch (e) { return toast(e.message, true); }
  chats.sort((a, b) => a.name.localeCompare(b.name));

  const m = modal('New message', `
    <div class="seg-toggle" role="radiogroup" aria-label="Message type">
      <button role="radio" data-k="group">${icon('users', 15)} Group</button>
      <button role="radio" data-k="individual">${icon('user', 15)} Individual</button>
    </div>

    <div data-for="group">
      <div class="field"><label for="nmGroup">Group</label>
        <select id="nmGroup">${chats.map(g => `<option value="${g.group_id}" ${g.can_send ? '' : 'disabled'}
          ${g.group_id === presetGroupId ? 'selected' : ''}>${esc(g.name)} (${n(g.members)} members)${g.can_send ? '' : ' — admins only'}</option>`).join('')}</select></div>
    </div>

    <div data-for="individual">
      <div class="grid g2" style="gap:12px">
        <div class="field"><label for="nmName">Recipient name <span class="muted-sm">(optional)</span></label>
          <input id="nmName" placeholder="Priya Sharma" autocomplete="off"></div>
        <div class="field"><label for="nmPhone">WhatsApp number</label>
          <input id="nmPhone" placeholder="+91 98765 43210" inputmode="tel" autocomplete="off"></div>
      </div>
      <p class="hint" style="margin:-6px 0 12px">Include the country code. A 10 digit number is treated as Indian (+91).
        The number is checked with WhatsApp before anything is sent.</p>
    </div>

    <div class="field"><label for="nmTpl">Template</label>
      <select id="nmTpl"><option value="">No template, write my own</option>
        ${templates.map(t => `<option value="${t.id}">${esc(t.name)}</option>`).join('')}</select></div>
    <div class="field"><label for="nmText">Message</label>
      <textarea id="nmText" rows="6" placeholder="Type the message"></textarea>
      <div class="muted-sm" style="display:flex;justify-content:space-between;margin-top:4px">
        <span>Placeholders: <span class="mono">{{name}}</span>, <span class="mono">{{group_name}}</span></span>
        <span id="nmCount">0 / 4096</span></div></div>
    <div class="field"><label for="nmFile">Attachment <span class="muted-sm">(optional; the message becomes its caption)</span></label>
      <input type="file" id="nmFile"></div>

    <div class="note warn" data-for="individual">Sends from your linked WhatsApp number. Messaging people who have not
      saved your number, or who did not expect to hear from you, raises the risk of WhatsApp restricting the account.</div>`,
    `<button class="btn" data-xn>Cancel</button>
     <button class="btn primary" id="nmSend">${icon('send', 15)} Send</button>`);
  $('#modal').style.maxWidth = '640px';
  $('[data-xn]', m).onclick = closeModal;

  let cur = kind;
  const setKind = (k) => {
    cur = k;
    $$('.seg-toggle [data-k]', m).forEach(b => {
      const on = b.dataset.k === k;
      b.classList.toggle('on', on); b.setAttribute('aria-checked', String(on));
    });
    $$('[data-for]', m).forEach(x => x.classList.toggle('hidden', x.dataset.for !== k));
    (k === 'individual' ? $('#nmPhone') : $('#nmGroup')).focus();
  };
  $$('.seg-toggle [data-k]', m).forEach(b => b.onclick = () => setKind(b.dataset.k));
  setKind(kind);

  const ta = $('#nmText');
  const count = () => { $('#nmCount').textContent = `${ta.value.length} / 4096`; };
  ta.oninput = count;
  $('#nmTpl').onchange = (e) => {
    const t = templates.find(x => String(x.id) === e.target.value);
    if (!t) return;
    const grp = chats.find(g => String(g.group_id) === $('#nmGroup').value);
    // Preview with placeholders filled; the server fills them again at send.
    ta.value = t.body.replace(/\{\{name\}\}/g, $('#nmName').value.trim() || '{{name}}')
      .replace(/\{\{group_name\}\}/g, grp ? grp.name : '{{group_name}}')
      .replace(/\{\{campaign_name\}\}/g, '').replace(/[ \t]*\{\{link\}\}[ \t]*/g, '')
      .replace(/\n{3,}/g, '\n\n').trim();
    count();
  };

  $('#nmSend').onclick = async () => {
    const btn = $('#nmSend');
    const fd = new FormData();
    fd.append('type', cur);
    fd.append('text', ta.value);
    if (cur === 'group') {
      if (!$('#nmGroup').value) return toast('Choose a group.', true);
      fd.append('group_id', $('#nmGroup').value);
    } else {
      if (!$('#nmPhone').value.trim()) return toast('Enter a WhatsApp number.', true);
      fd.append('phone', $('#nmPhone').value);
      fd.append('name', $('#nmName').value);
    }
    const f = $('#nmFile').files[0];
    if (f) fd.append('file', f);
    if (!ta.value.trim() && !f) return toast('Type a message or attach a file.', true);
    btn.disabled = true; btn.innerHTML = '<span class="spin"></span> Sending';
    try {
      const r = await api.form('/api/messages/send', fd);
      closeModal();
      toast('Sent. Status stays Pending until WhatsApp acknowledges it.');
      if (S.view === 'messages') loadMessages();
      if (r.msg_id) setTimeout(() => messageDetails(r.msg_id), 400);
    } catch (e) {
      toast(e.message, true);
      if (S.view === 'messages') loadMessages(true);
    } finally {
      btn.disabled = false; btn.innerHTML = icon('send', 15) + ' Send';
    }
  };
}

// ------------------------------------------------------------- details
async function messageDetails(msgId) {
  let d;
  try { d = await api.get(`/api/messages/${encodeURIComponent(msgId)}/details`); }
  catch (e) { return toast(e.message, true); }
  S.detailsId = msgId;
  const isGroup = d.type === 'group';
  const filter = S.detailsFilter || '';
  const rc = d.recipient_counts || {};

  const facts = isGroup ? [
      ['users', 'Group', esc(d.to || '—')],
      ['clock', 'Sent at', tsz(d.sent_at)],
      ['target', 'First delivered', tsz(d.delivered_at)],
      ['eye', 'First read', tsz(d.read_at)],
    ] : [
      ['user', 'Recipient', esc(d.to || '—') + (d.to_number && d.to_number !== d.to ? ` <span class="mono muted-sm">${esc(d.to_number)}</span>` : '')],
      ['clock', 'Sent at', tsz(d.sent_at)],
      ['target', 'Delivered at', tsz(d.delivered_at)],
      ['eye', 'Read at', tsz(d.read_at)],
    ];

  const steps = [['sent', 'Sent', d.sent_at], ['delivered', 'Delivered', d.delivered_at], ['read', 'Read', d.read_at]];
  const rank = { pending: 0, sent: 1, delivered: 2, read: 3, failed: -1 };
  const r0 = rank[d.status] ?? 0;
  const timeline = d.status === 'failed'
    ? `<div class="tl"><div class="tl-step done">${icon('send', 14)}<span>Attempted</span><small>${tsz(d.sent_at)}</small></div>
       <div class="tl-bar fail"></div><div class="tl-step fail">✕<span>Failed</span><small>${esc(d.error || '')}</small></div></div>`
    : `<div class="tl">${steps.map(([k, lb, t], i) => `
        ${i ? `<div class="tl-bar ${r0 >= rank[k] ? 'done' : ''}"></div>` : ''}
        <div class="tl-step ${r0 >= rank[k] ? 'done' : ''} ${k === 'read' && r0 >= 3 ? 'read' : ''}">
          ${k === 'sent' ? '✓' : '✓✓'}<span>${lb}${isGroup && k !== 'sent' ? ' to all' : ''}</span>
          <small>${r0 >= rank[k] ? (k === 'sent' ? tsz(d.sent_at) : (isGroup ? '' : tsz(t))) : (d.status === 'pending' && k === 'sent' ? 'awaiting server' : '—')}</small></div>`).join('')}</div>`;

  const list = (d.recipients || []).filter(x => !filter || x.status === filter);
  const body = `
    <div style="display:flex;gap:8px;align-items:center;margin-bottom:14px">
      ${typePill(d.type)} ${msgPill(d.status)}
      ${d.sent_via && d.sent_via !== 'platform' ? `<span class="pill">${d.sent_via === 'phone' ? 'Sent from the phone' : 'Campaign ' + esc(d.campaign || '')}</span>` : ''}
    </div>
    <div class="msg-quote">${d.mtype && !['conversation', 'extendedText', 'text'].includes(d.mtype) ? `<span class="chip">${esc(d.mtype)}</span>` : ''}${esc(d.text || '(no text)')}</div>

    <div class="fields" style="margin:16px 0">${facts.map(([ic, lb, v]) => fld(ic, lb, v)).join('')}</div>

    ${isGroup ? `<div class="mstats">
      <div><span>Total recipients</span><strong>${n(d.member_total ?? d.total)}</strong></div>
      <div><span>Delivered</span><strong>${n(d.delivered)}</strong></div>
      <div><span>Read</span><strong>${n(d.read)}</strong></div>
      <div><span>Pending delivery</span><strong>${n(d.pending_delivery)}</strong></div>
      <div><span>Delivered, not read</span><strong>${n(d.not_read)}</strong></div>
      <div><span>Failed</span><strong>${n(d.failed)}</strong></div>
    </div><div id="mdSeg" style="margin:14px 0 4px"></div>` : ''}

    <h3 class="md-h">Progress</h3>
    ${timeline}

    <details class="md-rcpt" ${isGroup ? '' : 'open'} ${S.detailsOpen ? 'open' : ''}>
      <summary>${icon('chevronRight', 15)} Recipient level status <span class="muted-sm">(${n((d.recipients || []).length)})</span></summary>
      ${isGroup ? `<div class="chipbar" style="margin:10px 0">
        ${[['', 'All', (d.recipients || []).length], ['read', 'Read', rc.read], ['delivered', 'Delivered', rc.delivered],
           ['pending', 'Pending', rc.pending], ['failed', 'Failed', rc.failed]]
          .map(([k, lb, c]) => `<button class="chipbtn ${filter === k ? 'on' : ''}" data-rf="${k}">${lb} <span>${n(c || 0)}</span></button>`).join('')}
      </div>` : ''}
      ${!d.member_list_synced ? '<div class="note warn" style="margin:8px 0">The member list for this group has not been synced, so members with no receipt yet cannot be listed. Use Refresh on the group page.</div>' : ''}
      <div class="tbl-wrap" style="max-height:320px"><table>
        <thead><tr><th>Recipient</th><th>Status</th><th>Delivered</th><th>Read</th></tr></thead>
        <tbody>${list.length ? list.map(x => `<tr>
          <td>${esc(x.recipient)}${x.former_member ? ' <span class="chip" title="Received the message but is no longer in the member list">former member</span>' : ''}
            ${x.id && x.id !== x.recipient ? `<div class="mono muted-sm">${esc(x.id)}</div>` : ''}</td>
          <td>${msgPill(x.status)}</td>
          <td class="nowrap">${tsz(x.delivered_at)}</td><td class="nowrap">${tsz(x.read_at)}</td></tr>`).join('')
          : '<tr><td colspan="4" class="empty">No recipients in this state.</td></tr>'}</tbody></table></div>
    </details>

    ${(d.notes || []).map(t => `<div class="note" style="margin-top:10px">${esc(t)}</div>`).join('')}
    <p class="hint">Updates arrive from WhatsApp as recipients receive and read the message. This view refreshes itself while open.</p>`;

  const already = $('#modalBg').classList.contains('on') && $('#modal').dataset.md === msgId;
  const scrollTop = already ? $('#modal').scrollTop : 0;
  const mm = modal(isGroup ? 'Group message details' : 'Message details', body,
    `${d.group_id ? `<button class="btn" id="mdGroup">${icon('users', 14)} Open group</button>` : ''}
     <button class="btn" id="mdRefresh">${icon('refresh', 14)} Refresh</button>
     <button class="btn primary" data-xd>Close</button>`);
  $('#modal').dataset.md = msgId;
  $('#modal').style.maxWidth = '820px';
  $('#modal').scrollTop = scrollTop;
  $('[data-xd]', mm).onclick = closeModal;
  $('#mdRefresh').onclick = () => messageDetails(msgId);
  const og = $('#mdGroup'); if (og) og.onclick = () => { closeModal(); openGroup(d.group_id); };
  const det = $('.md-rcpt', mm);
  det.addEventListener('toggle', () => { S.detailsOpen = det.open; });
  $$('[data-rf]', mm).forEach(b => b.onclick = () => { S.detailsFilter = b.dataset.rf; S.detailsOpen = true; messageDetails(msgId); });
  if (isGroup) segBar($('#mdSeg', mm), [
    { label: 'Read', value: d.read, color: css('--primary'), icon: '✓✓' },
    { label: 'Delivered, not read', value: d.not_read, color: css('--good'), icon: '✓✓' },
    { label: 'Pending', value: d.pending_delivery, color: css('--warning'), icon: '○' },
    { label: 'Failed', value: d.failed, color: css('--critical'), icon: '✕' }]);

  // live refresh while this message stays open
  clearInterval(S.detailsTimer);
  S.detailsTimer = setInterval(() => {
    const open = $('#modalBg').classList.contains('on') && $('#modal').dataset.md === msgId;
    if (!open) { clearInterval(S.detailsTimer); S.detailsFilter = ''; S.detailsOpen = false; return; }
    if (S.live !== false && !document.activeElement.closest?.('#modal select, #modal input')) messageDetails(msgId);
  }, 5000);
}

// The older "who read" buttons in Chats and on group pages open this view.
receiptModal = (id) => messageDetails(id);
