// Mesajlar: üstte Arkadaşlık istekleri / Bildirimler / Ziyaretçiler kutucukları, altında sohbet listesi.
// Birebir sohbet ekranında sağ üstteki üç nokta: profili gör, engelle, şikâyet et.
// İkisi de kişiye özel kanaldaki `message:new` olayını dinler: yeni mesaj sayfa yenilemeden görünür.
import { api } from '../api.js';
import { esc, icon, avatarImg, formatCount, timeAgo, openSheet, toast, vipBadge, levelBadge } from '../ui.js';
import { onInbox, getUnreadNotificationCount } from '../inbox.js';
import { openReportSheet } from './report.js';

// Yuvarlak kısayol: renkli daire içinde simge, sağ üstte sayı rozeti, altında ad
function shortcut({ href, iconName, label, count, tone }) {
  return `
    <a class="inbox-shortcut tone-${tone}" href="${href}">
      <span class="inbox-shortcut-icon">${icon(iconName, 22)}${count ? `<i class="tab-badge">${count > 99 ? '99+' : count}</i>` : ''}</span>
      <span>${label}</span>
    </a>`;
}

export async function renderMessages(root) {
  root.innerHTML = `
    <header class="topbar">
      <h1 class="page-title">Mesajlar</h1>
      <div class="topbar-actions"><a class="icon-btn" href="#/explore?mode=people&focus=1" aria-label="Kişi bul">${icon('user-plus', 20)}</a></div>
    </header>
    <div class="inbox-shortcuts" id="inbox-shortcuts"></div>
    <div class="conversation-list" id="conversation-list"></div>`;
  const listEl = root.querySelector('#conversation-list');
  const shortcutsEl = root.querySelector('#inbox-shortcuts');

  async function loadShortcuts() {
    // Sayılar kritik değil: biri gelmezse kutucuk sayısız görünür
    const [followers, visitors, events] = await Promise.all([
      api.listFollowers().catch(() => []),
      api.listVisitors().catch(() => []),
      api.listEvents().catch(() => []),
    ]);
    shortcutsEl.innerHTML = [
      shortcut({ href: '#/requests', iconName: 'user-plus', label: 'Arkadaşlık isteği', count: followers.filter((u) => !u.is_following).length, tone: 'green' }),
      shortcut({ href: '#/events', iconName: 'trophy', label: 'Etkinlik', count: events.filter((e) => e.status === 'active').length, tone: 'blue' }),
      shortcut({ href: '#/notifications', iconName: 'bell', label: 'Bildirim', count: getUnreadNotificationCount(), tone: 'gold' }),
      shortcut({ href: '#/visitors', iconName: 'eye', label: 'Ziyaretçi', count: visitors.length, tone: 'pink' }),
    ].join('');
  }

  let conversations = [];
  async function load() {
    conversations = await api.listConversations();
    // Satırın tamamı sohbete götüren bir bağlantı; sağdaki üç nokta (profil, engelle, şikâyet) onun üstünde durur
    listEl.innerHTML = conversations.length ? conversations.map((c) => `
        <div class="conversation">
          <a class="conversation-link" href="#/chat/${c.id}" aria-label="${esc(c.user.display_name)} ile sohbet"></a>
          <span class="conversation-avatar">${avatarImg(c.user, 'avatar-md')}${c.user.is_online ? '<span class="online-dot"></span>' : ''}</span>
          <span class="conversation-body">
            <b>${esc(c.user.display_name)}${vipBadge(c.user.vip_level)}${levelBadge(c.user.level)}</b>
            <small>${c.last_message ? `${c.last_message.from_me ? 'Sen: ' : ''}${esc(c.last_message.text)}` : 'Sohbeti başlat'}</small>
          </span>
          <span class="conversation-meta">
            <small>${esc(c.last_message?.time || '')}</small>
            ${c.unread_count ? `<i class="unread">${c.unread_count}</i>` : ''}
          </span>
          <button class="conversation-more" data-conversation-menu="${c.id}" aria-label="Seçenekler">${icon('more', 18)}</button>
        </div>`).join('') : '<div class="empty"><p>Henüz mesajın yok. Bir profile girip "Mesaj" ile sohbet başlat.</p></div>';
  }
  await Promise.all([load(), loadShortcuts()]);

  listEl.addEventListener('click', (event) => {
    const button = event.target.closest('[data-conversation-menu]');
    if (!button) return;
    const conversation = conversations.find((c) => c.id === Number(button.dataset.conversationMenu));
    if (conversation) openPeerMenu(conversation.user);
  });

  // Yeni mesaj gelince listeyi sunucudan tazele (sıra, son mesaj ve okunmamış sayısı değişir)
  return onInbox('message:new', () => load());
}

// Üç nokta menüsü (sohbet listesinde ve sohbet ekranında aynı): profili gör, engelle / engeli kaldır, şikâyet et
export function openPeerMenu(user) {
  const sheet = openSheet(`
    <div class="menu-list">
      <a href="#/profile/${user.id}" data-close>${icon('user', 20)} Profili gör</a>
      <button data-menu="block">${icon('lock', 20)} ${user.is_blocked ? 'Engeli kaldır' : 'Engelle'}</button>
      <button data-menu="report" class="is-danger">${icon('close', 20)} Şikâyet et</button>
    </div>`);
  sheet.el.addEventListener('click', async (event) => {
    const item = event.target.closest('[data-menu]');
    if (!item) return;
    sheet.close();
    if (item.dataset.menu === 'report') {
      openReportSheet('user', user.id, user.display_name);
      return;
    }
    try {
      const { is_blocked: isBlocked } = await api.setBlocked(user.id, !user.is_blocked);
      user.is_blocked = isBlocked;
      toast(isBlocked ? `${user.display_name} engellendi. Birbirinize mesaj gönderemezsiniz.` : 'Engel kaldırıldı', 'success');
    } catch (error) {
      toast(error.message, 'error');
    }
  });
}

// ── Arkadaşlık istekleri ve ziyaretçiler ──────────────────────────────────────

function personRow(user, side) {
  return `
    <div class="member-row">
      <a href="#/profile/${user.id}">${avatarImg(user, 'avatar-md')}</a>
      <a class="member-info" href="#/profile/${user.id}"><b>${esc(user.display_name)}</b><small>${side}</small></a>
      ${user.is_following
        ? '<span class="friend-tag">Arkadaş</span>'
        : `<button class="btn btn-sm btn-primary" data-follow-back="${user.id}">Geri takip et</button>`}
    </div>`;
}

const backHeader = (title) => `
  <header class="topbar">
    <a class="icon-btn icon-btn-plain" href="#/messages" data-back aria-label="Geri">${icon('chevron-left', 22)}</a>
    <h1 class="page-title">${title}</h1>
    <span></span>
  </header>`;

// Bizde ayrı "istek" yok: beni takip eden ama benim geri takip etmediğim kişi istek sayılır.
// Geri takip edince karşılıklı takip olur = arkadaş.
export async function renderRequests(root) {
  let followers = await api.listFollowers();
  const paint = () => {
    const pending = followers.filter((u) => !u.is_following);
    const friends = followers.filter((u) => u.is_following);
    root.innerHTML = `
      ${backHeader('Arkadaşlık istekleri')}
      <p class="screen-note">Seni takip edenleri geri takip edince arkadaş olursunuz.</p>
      <section class="section">
        <div class="section-head"><h2>İstekler</h2><small>${pending.length}</small></div>
        ${pending.map((u) => personRow(u, `@${esc(u.username)} seni takip ediyor`)).join('') || '<p class="member-empty">Bekleyen istek yok.</p>'}
      </section>
      ${friends.length ? `
        <section class="section">
          <div class="section-head"><h2>Takipçiler</h2><small>${formatCount(friends.length)}</small></div>
          ${friends.map((u) => personRow(u, `@${esc(u.username)}`)).join('')}
        </section>` : ''}`;
  };
  paint();
  root.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-follow-back]');
    if (!button) return;
    button.disabled = true;
    try {
      const id = Number(button.dataset.followBack);
      const { is_following: isFollowing } = await api.toggleFollow(id);
      followers = followers.map((u) => (u.id === id ? { ...u, is_following: isFollowing } : u));
      if (isFollowing) toast('Artık arkadaşsınız 🤝', 'success');
      paint();
    } catch (error) {
      toast(error.message, 'error');
      button.disabled = false;
    }
  });
}

export async function renderVisitors(root) {
  const visitors = await api.listVisitors();
  root.innerHTML = `
    ${backHeader('Ziyaretçiler')}
    <p class="screen-note">Profiline bakan kişiler, en son bakan en üstte.</p>
    <section class="section">
      ${visitors.map(({ user, visited_at: at }) => `
        <a class="member-row" href="#/profile/${user.id}">
          ${avatarImg(user, 'avatar-md')}
          <span class="member-info"><b>${esc(user.display_name)}</b><small>${timeAgo(at)} baktı</small></span>
          ${user.is_online ? '<span class="online-dot" title="Çevrimiçi"></span>' : ''}
        </a>`).join('') || '<div class="empty"><p>Henüz kimse profiline bakmadı. Bir anı paylaş, odalara katıl.</p></div>'}
    </section>`;
}
