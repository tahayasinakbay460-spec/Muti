// Aileler: liste ve arama, aile kurma, aile sayfası (üyeler, canlı aile sohbeti, yönetim)
import { api } from '../api.js';
import { onInbox } from '../inbox.js';
import { esc, icon, framedAvatar, formatCoins, toast, openSheet } from '../ui.js';

const CREATE_PRICE = 2000;   // backend: family_service.FAMILY_CREATE_PRICE
const BADGES = ['🦁', '🦉', '🐺', '🦅', '🐉', '🔥', '⚡', '🌙', '🎵', '💎', '🌹', '👑'];
const ROLE_LABELS = { owner: 'Kurucu', admin: 'Yönetici', member: 'Üye' };
const ROLE_RANK = { owner: 3, admin: 2, member: 1 };

function familyCard(family) {
  return `
    <a class="family-card" href="#/family/${family.id}">
      <span class="family-badge">${esc(family.badge)}</span>
      <span class="member-info">
        <b>${esc(family.name)} <span class="family-level">Lv.${family.level}</span></b>
        <small>${esc(family.slogan || 'Aileye katıl, birlikte büyüyün')}</small>
        <small>${icon('users', 12)} ${family.member_count}/${family.max_members} · Bu hafta 🪙 ${formatCoins(family.week_coins)}</small>
      </span>
      ${icon('chevron-right', 18)}
    </a>`;
}

function openCreateSheet() {
  let badge = BADGES[0];
  const sheet = openSheet(`
    <h2 class="sheet-title">Aile Kur</h2>
    <form id="family-form">
      <label class="field"><span>Aile adı</span><input name="name" maxlength="24" minlength="2" required placeholder="Örn. Gece Kuşları" /></label>
      <label class="field"><span>Slogan</span><input name="slogan" maxlength="120" placeholder="Ailenizi bir cümleyle anlatın" /></label>
      <div class="field"><span>Rozet</span></div>
      <div class="badge-pick">${BADGES.map((b, i) => `<button type="button" class="${i === 0 ? 'is-active' : ''}" data-badge="${b}">${b}</button>`).join('')}</div>
      <button class="btn btn-primary btn-block" type="submit">Kur · <span class="coin coin-sm"></span> ${formatCoins(CREATE_PRICE)}</button>
    </form>`, { className: 'sheet-dark' });
  sheet.el.addEventListener('click', (event) => {
    const pick = event.target.closest('[data-badge]');
    if (!pick) return;
    badge = pick.dataset.badge;
    sheet.el.querySelectorAll('[data-badge]').forEach((b) => b.classList.toggle('is-active', b === pick));
  });
  sheet.el.querySelector('#family-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.target;
    form.querySelector('[type="submit"]').disabled = true;
    try {
      const family = await api.createFamily({ name: form.elements.name.value, slogan: form.elements.slogan.value, badge });
      sheet.close();
      toast(`${family.badge} ${family.name} kuruldu!`, 'success');
      location.hash = `#/family/${family.id}`;
    } catch (error) {
      toast(error.code === 'insufficient_balance' ? 'Coin bakiyen yetersiz.' : error.message, 'error');
      form.querySelector('[type="submit"]').disabled = false;
    }
  });
}

export async function renderFamilies(root) {
  const mine = await api.getMyFamily();
  root.innerHTML = `
    <header class="topbar">
      <a class="icon-btn icon-btn-plain" href="#/home" aria-label="Geri">${icon('chevron-left', 22)}</a>
      <h1 class="page-title">Aileler</h1>
      <a class="icon-btn icon-btn-plain" href="#/leaderboard?kind=families" aria-label="Aile sıralaması">${icon('trophy', 20)}</a>
    </header>
    <section class="section">
      ${mine
        ? `<div class="section-head"><h2>Ailem</h2></div>${familyCard(mine)}`
        : `<div class="family-empty"><p>Henüz bir ailen yok. Bir aileye katıl ya da kendi aileni kur.</p>
             <button class="btn btn-primary" data-action="create">${icon('plus', 16)} Aile Kur</button></div>`}
    </section>
    <div class="search-box">${icon('search', 18)}<input id="family-search" type="search" placeholder="Aile ara..." autocomplete="off" /></div>
    <section class="section"><div class="family-list" id="family-list"></div></section>`;

  const listEl = root.querySelector('#family-list');
  let requestId = 0;
  async function load(query = '') {
    const id = ++requestId;
    const families = await api.listFamilies(query);
    if (id !== requestId) return;
    listEl.innerHTML = families.length ? families.map(familyCard).join('') : '<p class="member-empty">Aile bulunamadı.</p>';
  }
  await load();

  let debounce;
  root.querySelector('#family-search').addEventListener('input', (event) => {
    clearTimeout(debounce);
    debounce = setTimeout(() => load(event.target.value.trim()), 250);
  });
  root.addEventListener('click', (event) => {
    if (event.target.closest('[data-action="create"]')) openCreateSheet();
  });
  return () => clearTimeout(debounce);
}

function messageLine(message, meId) {
  return `
    <div class="family-msg ${message.sender.id === meId ? 'is-mine' : ''}">
      ${framedAvatar(message.sender, 'avatar-sm')}
      <div><b>${esc(message.sender.display_name)}</b><p>${esc(message.text)}</p></div>
    </div>`;
}

export async function renderFamily(root, { params }) {
  const familyId = Number(params[0]);
  const [me, initial] = await Promise.all([api.getMe(), api.getFamily(familyId)]);
  let family = initial;
  let tab = family.my_role ? 'chat' : 'members';
  let stopChat = null;

  function header() {
    const role = family.my_role;
    const action = !role
      ? (me.family ? '' : '<button class="btn btn-primary" data-action="join">Katıl</button>')
      : role === 'owner'
        ? '<button class="btn btn-soft" data-action="disband">Aileyi Dağıt</button>'
        : '<button class="btn btn-soft" data-action="leave">Ayrıl</button>';
    return `
      <section class="family-hero">
        <span class="family-badge family-badge-lg">${esc(family.badge)}</span>
        <h2>${esc(family.name)} <span class="family-level">Lv.${family.level}</span></h2>
        <p>${esc(family.slogan || '')}</p>
        <div class="family-stats">
          <span><b>${family.member_count}/${family.max_members}</b><small>Üye</small></span>
          <span><b>🪙 ${formatCoins(family.week_coins)}</b><small>Bu hafta</small></span>
        </div>
        <div class="family-actions">
          ${action}
          ${ROLE_RANK[role] >= ROLE_RANK.admin ? '<button class="btn btn-soft" data-action="edit">Sloganı Değiştir</button>' : ''}
        </div>
      </section>`;
  }

  function membersPanel() {
    return family.members.map((m) => `
      <button class="member-row" data-member="${m.user.id}">
        ${framedAvatar(m.user, 'avatar-md')}
        <span class="member-info">
          <b>${esc(m.user.display_name)} ${m.role !== 'member' ? `<span class="mini-role mini-role-${m.role === 'owner' ? 'host' : 'admin'}">${ROLE_LABELS[m.role]}</span>` : ''}</b>
          <small>Bu hafta 🪙 ${formatCoins(m.week_coins)}</small>
        </span>
      </button>`).join('');
  }

  async function chatPanel(panel) {
    const messages = await api.listFamilyMessages(familyId);
    panel.innerHTML = `
      <div class="family-chat" id="family-chat">${messages.map((m) => messageLine(m, me.id)).join('') || '<p class="member-empty">İlk mesajı sen yaz!</p>'}</div>
      <form class="family-input" id="family-input">
        <input name="text" maxlength="500" placeholder="Ailene yaz..." autocomplete="off" />
        <button class="icon-btn icon-btn-gift" aria-label="Gönder">${icon('send', 18)}</button>
      </form>`;
    const chatEl = panel.querySelector('#family-chat');
    const seen = new Set(messages.map((m) => m.id));
    const add = (message) => {
      if (seen.has(message.id)) return;
      seen.add(message.id);
      chatEl.querySelector('.member-empty')?.remove();
      chatEl.insertAdjacentHTML('beforeend', messageLine(message, me.id));
      chatEl.scrollTop = chatEl.scrollHeight;
    };
    chatEl.scrollTop = chatEl.scrollHeight;
    // Diğer üyelerin mesajları kişiye özel kanaldan (/ws/me) anında gelir
    stopChat?.();
    stopChat = onInbox('family:message', ({ family_id: id, message }) => { if (id === familyId) add(message); });
    panel.querySelector('#family-input').addEventListener('submit', async (event) => {
      event.preventDefault();
      const input = event.target.elements.text;
      const text = input.value.trim();
      if (!text) return;
      input.value = '';
      try {
        add(await api.sendFamilyMessage(familyId, text));
      } catch (error) {
        toast(error.message, 'error');
      }
    });
  }

  async function render() {
    root.innerHTML = `
      <header class="topbar">
        <a class="icon-btn icon-btn-plain" href="#/families" aria-label="Geri">${icon('chevron-left', 22)}</a>
        <h1 class="page-title">Aile</h1>
        <span></span>
      </header>
      ${header()}
      <div class="segmented family-tabs">
        <button data-tab="members">Üyeler</button>
        <button data-tab="chat" ${family.my_role ? '' : 'disabled'}>Sohbet</button>
      </div>
      <div id="family-panel" class="section"></div>`;
    root.querySelectorAll('[data-tab]').forEach((b) => b.classList.toggle('is-active', b.dataset.tab === tab));
    const panel = root.querySelector('#family-panel');
    if (tab === 'chat' && family.my_role) await chatPanel(panel);
    else panel.innerHTML = membersPanel();
  }
  await render();

  function openMemberSheet(member) {
    const myRank = ROLE_RANK[family.my_role] || 0;
    const canKick = member.user.id !== me.id && myRank >= ROLE_RANK.admin && myRank > ROLE_RANK[member.role];
    const canPromote = family.my_role === 'owner' && member.role !== 'owner';
    const sheet = openSheet(`
      <div class="menu-list">
        <a href="#/profile/${member.user.id}" data-close>${icon('user', 20)} Profili gör</a>
        ${canPromote ? `<button data-menu="${member.role === 'admin' ? 'demote' : 'promote'}">${icon('crown', 20)} ${member.role === 'admin' ? 'Yöneticiliği al' : 'Yönetici yap'}</button>` : ''}
        ${canKick ? `<button data-menu="kick" class="is-danger">${icon('close', 20)} Aileden çıkar</button>` : ''}
      </div>`);
    sheet.el.addEventListener('click', async (event) => {
      const item = event.target.closest('[data-menu]');
      if (!item) return;
      sheet.close();
      try {
        if (item.dataset.menu === 'kick') family = await api.kickFamilyMember(familyId, member.user.id);
        else family = await api.setFamilyRole(familyId, member.user.id, item.dataset.menu === 'promote' ? 'admin' : 'member');
        toast('Güncellendi', 'success');
        await render();
      } catch (error) {
        toast(error.message, 'error');
      }
    });
  }

  root.addEventListener('click', async (event) => {
    const tabBtn = event.target.closest('[data-tab]');
    if (tabBtn && !tabBtn.disabled && tabBtn.dataset.tab !== tab) {
      tab = tabBtn.dataset.tab;
      return render();
    }
    const memberBtn = event.target.closest('[data-member]');
    if (memberBtn) return openMemberSheet(family.members.find((m) => m.user.id === Number(memberBtn.dataset.member)));

    const action = event.target.closest('[data-action]')?.dataset.action;
    if (!action) return;
    try {
      if (action === 'join') {
        family = await api.joinFamily(familyId);
        me.family = { id: family.id, name: family.name, badge: family.badge };
        tab = 'chat';
        toast(`${family.badge} ${family.name} ailesine katıldın!`, 'success');
      } else if (action === 'leave') {
        await api.leaveFamily();
        family = await api.getFamily(familyId);
        me.family = null;
        tab = 'members';
        toast('Aileden ayrıldın');
      } else if (action === 'disband') {
        if (!confirmInline(event.target.closest('[data-action]'))) return;
        await api.disbandFamily(familyId);
        toast('Aile dağıtıldı');
        location.hash = '#/families';
        return;
      } else if (action === 'edit') {
        const slogan = await askSlogan(family.slogan);
        if (slogan === null) return;
        family = await api.updateFamily(familyId, { slogan });
      }
      await render();
    } catch (error) {
      toast(error.message, 'error');
    }
  });

  return () => stopChat?.();
}

// Geri alınamayan işlem için iki dokunuş: ilk dokunuşta düğme "Emin misin?" olur
function confirmInline(button) {
  if (button.dataset.confirming) return true;
  button.dataset.confirming = '1';
  button.textContent = 'Emin misin? Tekrar dokun';
  setTimeout(() => { delete button.dataset.confirming; button.textContent = 'Aileyi Dağıt'; }, 3000);
  return false;
}

function askSlogan(current) {
  return new Promise((resolve) => {
    const sheet = openSheet(`
      <h2 class="sheet-title">Aile Sloganı</h2>
      <form id="slogan-form">
        <label class="field"><span>Slogan</span><input name="slogan" maxlength="120" value="${esc(current)}" /></label>
        <button class="btn btn-primary btn-block" type="submit">Kaydet</button>
      </form>`, { className: 'sheet-dark' });
    let done = false;
    sheet.el.querySelector('#slogan-form').addEventListener('submit', (event) => {
      event.preventDefault();
      done = true;
      sheet.close();
      resolve(event.target.elements.slogan.value);
    });
    // Kaydetmeden kapatılırsa (arka plana dokunma) vazgeçilmiş sayılır
    const observer = new MutationObserver(() => {
      if (!sheet.el.isConnected) {
        observer.disconnect();
        if (!done) resolve(null);
      }
    });
    observer.observe(document.getElementById('overlay-root'), { childList: true });
  });
}
