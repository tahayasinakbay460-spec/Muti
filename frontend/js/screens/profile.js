// Profil (Instagram düzeni): solda avatar, sağda Anı / Takipçi / Takip sayıları (hepsi tıklanır); altında ad,
// rozetler, biyografi ve düğmeler. Kendi profilimde kısayollar: VIP merkezi, Cüzdan, Mağaza, Görevler.
// İki sekme: Paylaştıklarım (anı ızgarası) ve Hakkımda (seviye, başarılar, eşyalar, bilgiler).
import { api } from '../api.js';
import { ADMIN_URL } from '../config.js';
import { esc, icon, avatarImg, formatCoins, formatCount, joinParts, vipBadge, levelBadge, toast, openSheet, daysLeft } from '../ui.js';
import { openEditProfileSheet } from './edit-profile.js';
import { openReportSheet } from './report.js';
import { onInbox } from '../inbox.js';
import { momentTile, bindMomentActions, openComposer } from './moments.js';

const KIND_LABELS = { frame: 'Çerçeve', entry_effect: 'Giriş efekti', chat_bubble: 'Sohbet balonu' };
const tabsFor = (isMe) => [
  { id: 'posts', label: isMe ? 'Paylaştıklarım' : 'Paylaşımlar', icon: 'grid' },
  { id: 'about', label: isMe ? 'Hakkımda' : 'Hakkında', icon: 'user' },
];

// Seviye ve bir sonraki seviyeye kalan deneyim puanı
function levelProgress(user) {
  const percent = Math.min(100, Math.round((user.experience / Math.max(1, user.next_level_experience)) * 100));
  return `
    <div class="level-progress" title="Hediye gönderdikçe harcadığın her coin 1 deneyim puanı kazandırır">
      <span><b>Lv.${user.level}</b><small>${formatCount(user.experience)} / ${formatCount(user.next_level_experience)} XP</small><b>Lv.${user.level + 1}</b></span>
      <i style="--progress:${percent}%"></i>
    </div>`;
}

// Takipçi / Takip listesi: alttan açılan panel, iki sekmeli; her satırda takip et düğmesi
async function openFollowList(user, initialKind, myId) {
  let kind = initialKind;
  const sheet = openSheet(`
    <h2 class="sheet-title">${esc(user.display_name)}</h2>
    <nav class="segmented follow-tabs">
      <button data-kind="followers">${formatCount(user.followers_count)} Takipçi</button>
      <button data-kind="following">${formatCount(user.following_count)} Takip</button>
    </nav>
    <div class="sheet-list follow-list" id="follow-list"></div>`, { className: 'sheet-tall' });
  const list = sheet.el.querySelector('#follow-list');
  let people = [];

  const row = (u) => `
    <div class="member-row">
      <a href="#/profile/${u.id}" data-close>${avatarImg(u, 'avatar-md')}</a>
      <a class="member-info" href="#/profile/${u.id}" data-close><b>${esc(u.display_name)}</b><small>@${esc(u.username)}</small></a>
      ${u.id === myId ? '' : `<button class="btn btn-sm ${u.is_following ? 'btn-soft' : 'btn-primary'}" data-follow-user="${u.id}">${u.is_following ? 'Takiptesin' : 'Takip et'}</button>`}
    </div>`;

  async function load() {
    sheet.el.querySelectorAll('[data-kind]').forEach((b) => b.classList.toggle('is-active', b.dataset.kind === kind));
    list.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    const requested = kind;
    const result = await (kind === 'followers' ? api.listUserFollowers(user.id) : api.listUserFollowing(user.id));
    if (requested !== kind) return;
    people = result;
    list.innerHTML = people.map(row).join('')
      || `<p class="member-empty">${kind === 'followers' ? 'Henüz takipçisi yok.' : 'Henüz kimseyi takip etmiyor.'}</p>`;
  }

  sheet.el.addEventListener('click', async (event) => {
    const tab = event.target.closest('[data-kind]');
    if (tab && tab.dataset.kind !== kind) {
      kind = tab.dataset.kind;
      load().catch((error) => toast(error.message, 'error'));
      return;
    }
    const button = event.target.closest('[data-follow-user]');
    if (!button) return;
    button.disabled = true;
    try {
      const { is_following: isFollowing } = await api.toggleFollow(button.dataset.followUser);
      button.textContent = isFollowing ? 'Takiptesin' : 'Takip et';
      button.className = `btn btn-sm ${isFollowing ? 'btn-soft' : 'btn-primary'}`;
    } catch (error) {
      toast(error.message, 'error');
    } finally {
      button.disabled = false;
    }
  });
  await load();
}

export async function renderProfile(root, { params }) {
  const me = await api.getMe();
  const user = params[0] && Number(params[0]) !== me.id ? await api.getUser(params[0]) : me;
  const [extras, initialItems, initialMoments] = await Promise.all([
    api.getProfileExtras(user.id), api.listUserItems(user.id), api.listUserMoments(user.id),
  ]);
  let items = initialItems;
  let moments = initialMoments;
  let activeTab = 'posts';

  const shortcuts = [
    { href: '#/vip', emoji: '👑', label: 'VIP merkezi', tone: 'gold' },
    { href: '#/wallet', emoji: '🪙', label: 'Cüzdan', detail: formatCoins(user.coin_balance ?? 0), tone: 'amber' },
    { href: '#/store', emoji: '🛍️', label: 'Mağaza', tone: 'pink' },
    { href: '#/tasks', emoji: '🎯', label: 'Görevler', tone: 'violet' },
  ];

  root.innerHTML = `
    <div class="profile-ig">
      <header class="topbar">
        ${user.is_me ? '<span></span>' : `<button class="icon-btn icon-btn-plain" data-action="back" aria-label="Geri">${icon('chevron-left', 22)}</button>`}
        <button class="profile-handle" data-action="copy-id">@${esc(user.username)} <small>ID ${user.id} ${icon('copy', 12)}</small></button>
        <button class="icon-btn icon-btn-plain" data-action="menu" aria-label="Menü">${icon('more', 20)}</button>
      </header>

      <div class="profile-top">
        <div class="profile-avatar ${esc(user.frame || '')}" id="profile-avatar">
          ${avatarImg(user)}${user.is_online ? '<span class="online-dot"></span>' : ''}
        </div>
        <div class="profile-counts">
          <button data-tab-jump="posts"><b id="moment-count">${formatCount(moments.length)}</b><small>Anı</small></button>
          <button data-follow-list="followers"><b>${formatCount(user.followers_count)}</b><small>Takipçi</small></button>
          <button data-follow-list="following"><b>${formatCount(user.following_count)}</b><small>Takip</small></button>
        </div>
      </div>

      <div class="profile-bio-block">
        <h1>${esc(user.display_name)} ${user.is_verified ? `<span class="verified">${icon('verified', 16)}</span>` : ''}</h1>
        <div class="profile-badges">${vipBadge(user.vip_level)}${levelBadge(user.level)}${user.family ? `<a class="family-chip" href="#/family/${user.family.id}">${esc(user.family.badge)} ${esc(user.family.name)}</a>` : ''}</div>
        ${user.bio ? `<p class="profile-bio">${esc(user.bio)}</p>` : ''}
        <p class="profile-meta">${esc(joinParts([user.age && `${user.age} yaş`, user.city, `${user.joined_days} gündür Muti'de`]))}</p>
      </div>

      <div class="profile-actions">
        ${user.is_me
          ? `<button class="btn btn-soft" data-action="edit">Profili düzenle</button>
             <button class="btn btn-soft" data-action="compose">${icon('plus', 16)} Anı paylaş</button>`
          : `<button class="btn ${user.is_following ? 'btn-soft' : 'btn-primary'}" data-action="follow">${user.is_following ? 'Takiptesin' : 'Takip et'}</button>
             <button class="btn btn-soft" data-action="message">${icon('chat', 16)} Mesaj</button>`}
      </div>

      ${user.is_me ? `
        <nav class="profile-shortcuts">
          ${shortcuts.map((s) => `
            <a class="profile-shortcut tone-${s.tone}" href="${s.href}">
              <i>${s.emoji}</i><b>${s.label}</b>${s.detail ? `<small>${s.detail}</small>` : ''}
            </a>`).join('')}
        </nav>` : ''}

      <div id="cp-slot"></div>

      <nav class="profile-tabs" id="profile-tabs">
        ${tabsFor(user.is_me).map((t) => `<button class="${t.id === activeTab ? 'is-active' : ''}" data-tab="${t.id}" aria-label="${t.label}">${icon(t.icon, 20)}<span>${t.label}</span></button>`).join('')}
      </nav>
      <div id="tab-panel"></div>
    </div>`;

  const panel = root.querySelector('#tab-panel');
  const avatarEl = root.querySelector('#profile-avatar');

  const itemsHtml = () => `
    <div class="frame-grid">
      ${items.map((item) => `
        <button class="frame-item ${item.is_equipped ? 'is-active' : ''}" data-owned-item="${item.id}">
          ${item.kind === 'frame'
            ? `<span class="frame-preview ${esc(item.style)}">${avatarImg(user)}</span>`
            : `<span class="owned-icon ${item.kind === 'chat_bubble' ? esc(item.style) : ''}">${item.emoji}</span>`}
          <b>${esc(item.name)}</b>
          <small>${item.is_equipped ? 'Kullanımda' : `${KIND_LABELS[item.kind]} · ${daysLeft(item.owned_until)} gün`}</small>
        </button>`).join('')}
      ${user.is_me ? '<a class="frame-item frame-shop" href="#/store"><span class="owned-icon">🛍️</span><b>Mağaza</b><small>Yeni eşya al</small></a>' : ''}
    </div>
    ${!items.length && !user.is_me ? '<p class="member-empty">Henüz eşyası yok.</p>' : ''}`;

  const panels = {
    posts: () => (moments.length
      ? `<div class="moment-grid">${moments.map(momentTile).join('')}</div>`
      : `<div class="empty">
           <p>${user.is_me ? 'İlk anını paylaş: takipçilerin Anılar sekmesinde görür.' : 'Henüz paylaşımı yok.'}</p>
           ${user.is_me ? '<button class="btn btn-primary" data-action="compose">Anı paylaş</button>' : ''}
         </div>`),

    about: () => `
      ${levelProgress(user)}
      <div class="about-stats">
        <span><b>🪙 ${formatCoins(extras.stats.gifts_sent_coins)}</b><small>Gönderdiği hediye</small></span>
        <span><b>💎 ${formatCoins(extras.stats.gifts_received_diamonds)}</b><small>Aldığı hediye</small></span>
        <span><b>${extras.stats.rooms_count}</b><small>Odası</small></span>
      </div>
      <h3 class="sub-title">Başarılar <small>${extras.achievements.filter((a) => a.is_unlocked).length} / ${extras.achievements.length}</small></h3>
      <div class="achievement-grid">
        ${extras.achievements.map((a) => `
          <div class="achievement ${a.is_unlocked ? 'is-unlocked' : ''}">
            <i>${a.emoji}</i><b>${esc(a.name)}</b><small>${esc(a.detail)}</small>
          </div>`).join('')}
      </div>
      <h3 class="sub-title">Eşyalar <small>${items.length}</small></h3>
      ${itemsHtml()}
      <h3 class="sub-title">Bilgiler</h3>
      <dl class="about">
        <div><dt>Kullanıcı adı</dt><dd>@${esc(user.username)}</dd></div>
        <div><dt>Şehir</dt><dd>${esc(user.city || '—')}</dd></div>
        <div><dt>Yaş</dt><dd>${user.age || '—'}</dd></div>
        <div><dt>VIP</dt><dd>${user.vip_level ? `VIP ${user.vip_level}` : 'Yok'}</dd></div>
        <div><dt>Ziyaretçi</dt><dd>${formatCount(user.visitors_count)}</dd></div>
        <div><dt>Üyelik</dt><dd>${user.joined_days} gün</dd></div>
      </dl>`,
  };

  function showTab(tabId) {
    activeTab = tabId;
    root.querySelectorAll('#profile-tabs button').forEach((b) => b.classList.toggle('is-active', b.dataset.tab === tabId));
    panel.innerHTML = panels[tabId]();
  }
  showTab(activeTab);

  const repaintMoments = (list) => {
    moments = list;
    root.querySelector('#moment-count').textContent = formatCount(moments.length);
    if (activeTab === 'posts') showTab('posts');
  };
  bindMomentActions(root, { getList: () => moments, onChange: repaintMoments });

  // ─── CP (çift) ─────────────────────────────────────────────────────────────
  const cpSlot = root.querySelector('#cp-slot');
  const daysSince = (iso) => Math.max(1, Math.ceil((Date.now() - new Date(iso)) / 86400000));
  // `subtitle` boşsa: "12 gündür CP · 🪙 1.240" (yalnızca kendi CP'mde bu bilgiler var)
  const cpCard = (couple, subtitle = '') => `
    <div class="cp-card">
      <a href="#/profile/${user.id}">${avatarImg(user, 'avatar-md')}</a>
      <span class="cp-heart">💞</span>
      <a href="#/profile/${couple.partner.id}">${avatarImg(couple.partner, 'avatar-md')}</a>
      <span class="member-info">
        <b>${esc(user.display_name)} & ${esc(couple.partner.display_name)}</b>
        <small>${subtitle || `${daysSince(couple.since)} gündür CP · 🪙 ${formatCount(couple.cp_coins)}`}</small>
      </span>
    </div>`;

  async function renderCp() {
    if (!user.is_me) {
      if (!user.cp_partner_id) return;
      const partner = await api.getUser(user.cp_partner_id).catch(() => null);
      if (partner) cpSlot.innerHTML = `<section class="section">${cpCard({ partner }, 'CP 💞')}</section>`;
      return;
    }
    const status = await api.getCouple();
    const requests = [
      ...status.incoming.map((r) => `
        <div class="cp-request">${avatarImg(r.partner, 'avatar-sm')}<span><b>${esc(r.partner.display_name)}</b> sana CP teklif etti 💍</span>
          <button class="btn btn-sm btn-primary" data-cp="accept" data-partner="${r.partner.id}">Kabul</button>
          <button class="btn btn-sm btn-soft" data-cp="decline" data-partner="${r.partner.id}">Reddet</button></div>`),
      ...status.outgoing.map((r) => `
        <div class="cp-request">${avatarImg(r.partner, 'avatar-sm')}<span><b>${esc(r.partner.display_name)}</b> yanıt bekleniyor</span>
          <button class="btn btn-sm btn-soft" data-cp="decline" data-partner="${r.partner.id}">Geri çek</button></div>`),
    ].join('');
    cpSlot.innerHTML = status.active || requests
      ? `<section class="section">
           ${status.active ? `${cpCard(status.active)}<button class="link-btn" data-cp="breakup">CP'yi sonlandır</button>` : ''}
           ${requests}
         </section>`
      : '';
  }
  renderCp();
  const stopCp = user.is_me ? onInbox('couple:updated', renderCp) : null;

  cpSlot.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-cp]');
    if (!button) return;
    button.disabled = true;
    const partnerId = Number(button.dataset.partner);
    try {
      if (button.dataset.cp === 'accept') {
        await api.acceptCouple(partnerId);
        toast("💞 Artık CP'siniz!", 'success');
      } else if (button.dataset.cp === 'decline') {
        await api.declineCouple(partnerId);
      } else {
        await api.breakUpCouple();
        toast('CP sonlandırıldı');
      }
      await renderCp();
    } catch (error) {
      toast(error.message, 'error');
      button.disabled = false;
    }
  });

  function openMenu() {
    const sheet = openSheet(`
      <div class="menu-list">
        <button data-menu="share">${icon('share', 20)} Profili paylaş</button>
        ${user.is_me
          ? `<a href="#/my-rooms" data-close>${icon('mic', 20)} Yayın odam</a>
             <a href="#/agency" data-close>${icon('building', 20)} Ajans</a>
             <a href="#/families" data-close>🛡️ Aileler</a>
             ${user.staff_role ? `<a href="${ADMIN_URL}" target="_blank" rel="noopener" data-close>🛡️ Yönetim paneli (masaüstü)</a>` : ''}
             <a href="#/settings" data-close>${icon('edit', 20)} Ayarlar</a>
             <button data-menu="logout" class="is-danger">${icon('logout', 20)} Çıkış yap</button>`
          : `${!user.cp_partner_id && !me.cp_partner_id ? '<button data-menu="propose">💍 CP teklif et</button>' : ''}
             <button data-menu="block">${icon('lock', 20)} ${user.is_blocked ? 'Engeli kaldır' : 'Engelle'}</button>
             <button data-menu="report" class="is-danger">${icon('close', 20)} Şikâyet et</button>`}
      </div>`);
    sheet.el.addEventListener('click', async (event) => {
      const item = event.target.closest('[data-menu]');
      if (!item) return;
      sheet.close();
      if (item.dataset.menu === 'propose') {
        try {
          await api.proposeCouple(user.id);
          toast(`💍 ${user.display_name} kişisine CP teklif ettin. Reddedilirse coin iade edilir.`, 'success');
        } catch (error) {
          toast(error.code === 'insufficient_balance' ? 'Coin bakiyen yetersiz.' : error.message, 'error');
        }
      } else if (item.dataset.menu === 'logout') {
        await api.logout();
        location.hash = '#/auth';
      } else if (item.dataset.menu === 'report') {
        openReportSheet('user', user.id, user.display_name);
      } else if (item.dataset.menu === 'block') {
        try {
          const { is_blocked: isBlocked } = await api.setBlocked(user.id, !user.is_blocked);
          user.is_blocked = isBlocked;
          toast(isBlocked ? `${user.display_name} engellendi. Birbirinize mesaj ve hediye gönderemezsiniz.` : 'Engel kaldırıldı', 'success');
        } catch (error) {
          toast(error.message, 'error');
        }
      } else {
        navigator.clipboard?.writeText(`${location.origin}${location.pathname}#/profile/${user.id}`).catch(() => {});
        toast('Profil bağlantısı kopyalandı');
      }
    });
  }

  root.addEventListener('click', async (event) => {
    const tab = event.target.closest('[data-tab]');
    if (tab) return showTab(tab.dataset.tab);

    const jump = event.target.closest('[data-tab-jump]');
    if (jump) {
      showTab(jump.dataset.tabJump);
      return root.querySelector('#profile-tabs').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // Kendi eşyama dokununca takılır ya da çıkarılır (aynı türden takılı olan otomatik çıkar)
    const owned = event.target.closest('[data-owned-item]');
    if (owned) {
      if (!user.is_me) return;
      const selected = items.find((i) => i.id === Number(owned.dataset.ownedItem));
      try {
        await api.equipStoreItem(selected.id, !selected.is_equipped);
        items = await api.listUserItems(user.id);
        const frame = items.find((i) => i.kind === 'frame' && i.is_equipped);
        avatarEl.className = `profile-avatar ${frame ? frame.style : ''}`;
        toast(selected.is_equipped ? `${selected.name} çıkarıldı` : `${selected.name} takıldı`, 'success');
        return showTab('about');
      } catch (error) {
        return toast(error.message, 'error');
      }
    }

    const followList = event.target.closest('[data-follow-list]');
    if (followList) {
      openFollowList(user, followList.dataset.followList, me.id).catch((error) => toast(error.message, 'error'));
      return;
    }

    const action = event.target.closest('[data-action]')?.dataset.action;
    if (!action) return;
    const button = event.target.closest('[data-action]');

    if (action === 'back') {
      if (history.length > 1) history.back();
      else location.hash = '#/home';
    } else if (action === 'menu') {
      openMenu();
    } else if (action === 'copy-id') {
      navigator.clipboard?.writeText(String(user.id)).catch(() => {});
      toast('ID kopyalandı');
    } else if (action === 'follow') {
      try {
        const { is_following: isFollowing } = await api.toggleFollow(user.id);
        button.textContent = isFollowing ? 'Takiptesin' : 'Takip et';
        button.className = `btn ${isFollowing ? 'btn-soft' : 'btn-primary'}`;
      } catch (error) {
        toast(error.message, 'error');
      }
    } else if (action === 'message') {
      try {
        const conversationId = await api.openConversationWith(user.id);
        location.hash = `#/chat/${conversationId}`;
      } catch (error) {
        toast(error.message, 'error');
      }
    } else if (action === 'compose') {
      openComposer((moment) => { repaintMoments([moment, ...moments]); showTab('posts'); })
        .catch((error) => toast(error.message, 'error'));
    } else if (action === 'edit') {
      // Kaydedilince ekranı yeniden çiz (yönlendirici aynı adresi baştan yükler)
      openEditProfileSheet(user, () => window.dispatchEvent(new HashChangeEvent('hashchange')))
        .catch((error) => toast(error.message, 'error'));
    }
  });

  return () => stopCp?.();
}
