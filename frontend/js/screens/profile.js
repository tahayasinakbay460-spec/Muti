// Profil: kapak, istatistikler ve sekmeler (Duvar, Eşyalar, Oyun & Ödüller, Hakkında)
import { api } from '../api.js';
import { DEFAULT_COVER_URL } from '../config.js';
import { esc, icon, avatarImg, formatCount, joinParts, vipBadge, levelBadge, toast, openSheet } from '../ui.js';
import { openEditProfileSheet } from './edit-profile.js';
import { openReportSheet } from './report.js';

const KIND_LABELS = { frame: 'Çerçeve', entry_effect: 'Giriş efekti', chat_bubble: 'Sohbet balonu' };
const daysLeft = (iso) => Math.max(1, Math.ceil((new Date(iso) - Date.now()) / 86400000));

const TABS = [
  { id: 'wall', label: 'Duvar' },
  { id: 'items', label: 'Eşyalar' },
  { id: 'rewards', label: 'Oyun & Ödüller' },
  { id: 'about', label: 'Hakkında' },
];

// Kendi profilimde: seviye ve bir sonraki seviyeye kalan deneyim puanı
function levelProgress(user) {
  const percent = Math.min(100, Math.round((user.experience / Math.max(1, user.next_level_experience)) * 100));
  return `
    <div class="level-progress" title="Hediye gönderdikçe harcadığın her coin 1 deneyim puanı kazandırır">
      <span><b>Lv.${user.level}</b><small>${formatCount(user.experience)} / ${formatCount(user.next_level_experience)} XP</small><b>Lv.${user.level + 1}</b></span>
      <i style="--progress:${percent}%"></i>
    </div>`;
}

export async function renderProfile(root, { params }) {
  const me = await api.getMe();
  const user = params[0] ? await api.getUser(params[0]) : me;
  const [extras, initialItems] = await Promise.all([api.getProfileExtras(user.id), api.listUserItems(user.id)]);
  // Kullanıcının süresi dolmamış mağaza eşyaları (çerçeve, giriş efekti, sohbet balonu)
  let items = initialItems;
  let activeTab = 'wall';

  root.innerHTML = `
    <div class="profile">
      <div class="profile-cover">
        <img src="${esc(user.cover_url || DEFAULT_COVER_URL)}" alt="" />
        <div class="profile-cover-actions">
          ${user.is_me ? '<span></span>' : `<button class="icon-btn icon-btn-glass" data-action="back" aria-label="Geri">${icon('chevron-left', 22)}</button>`}
          <button class="icon-btn icon-btn-glass" data-action="menu" aria-label="Menü">${icon('more', 20)}</button>
        </div>
      </div>

      <div class="profile-head">
        <div class="profile-avatar ${esc(user.frame || '')}" id="profile-avatar">${avatarImg(user)}</div>
        <div class="profile-id">
          <h1>${esc(user.display_name)} ${user.is_verified ? `<span class="verified">${icon('verified', 18)}</span>` : ''}</h1>
          <button class="id-copy" data-action="copy-id">ID ${user.id} ${icon('copy', 13)}</button>
        </div>
        <div class="profile-badges">${vipBadge(user.vip_level)}${levelBadge(user.level)}</div>
      </div>
      ${user.is_me ? levelProgress(user) : ''}

      <p class="profile-meta">${esc(joinParts([user.age && `${user.age} yaş`, user.city, `${user.joined_days} gündür burada`]))}</p>
      <p class="profile-bio">${esc(user.bio)}</p>

      <div class="profile-actions">
        ${user.is_me
          ? `<button class="btn btn-soft" data-action="edit">${icon('edit', 16)} Profili Düzenle</button>
             <a class="btn btn-soft" href="#/wallet">${icon('wallet', 16)} Cüzdan</a>`
          : `<button class="btn ${user.is_following ? 'btn-soft' : 'btn-primary'}" data-action="follow">${user.is_following ? 'Takiptesin' : 'Takip Et'}</button>
             <button class="btn btn-soft" data-action="message">${icon('chat', 16)} Mesaj</button>`}
      </div>

      <div class="stats">
        <div><b>${formatCount(user.followers_count)}</b><small>Takipçi</small></div>
        <div><b>${formatCount(user.following_count)}</b><small>Takip</small></div>
        <div><b>${formatCount(user.friends_count)}</b><small>Arkadaş</small></div>
        <div><b>${formatCount(user.visitors_count)}</b><small>Ziyaretçi</small></div>
      </div>

      <div class="quick-tiles">
        <button data-tab-jump="items"><i>💠</i><span><b>Eşyalar</b><small id="item-count">${items.length}</small></span></button>
        <button data-tab-jump="rewards"><i>🏆</i><span><b>Oyun Ödülleri</b><small>${extras.achievements.length}</small></span></button>
        <button data-tab-jump="rewards"><i>🎖️</i><span><b>Rozetler</b><small>${extras.recent_rewards.length}</small></span></button>
      </div>

      <div class="tabs" id="profile-tabs">
        ${TABS.map((t) => `<button class="${t.id === activeTab ? 'is-active' : ''}" data-tab="${t.id}">${t.label}</button>`).join('')}
      </div>
      <div class="tab-panel" id="tab-panel"></div>
    </div>`;

  const panel = root.querySelector('#tab-panel');
  const avatarEl = root.querySelector('#profile-avatar');

  const panels = {
    wall: () => extras.wall_posts.map((post) => `
      <article class="post">
        <header>${avatarImg(user, 'avatar-sm')}<span><b>${esc(user.display_name)}</b><small>${esc(post.time_label)}</small></span></header>
        <p>${esc(post.text)}</p>
        <div class="post-images post-images-${Math.min(post.image_urls.length, 3)}">
          ${post.image_urls.map((url) => `<img src="${esc(url)}" alt="" loading="lazy" />`).join('')}
        </div>
        <footer>
          <button data-action="like" data-count="${post.like_count}">${icon('heart', 18)} <span>${post.like_count}</span></button>
          <button data-action="soon">${icon('chat', 18)} ${post.comment_count}</button>
          <button data-action="soon">${icon('share', 18)}</button>
        </footer>
      </article>`).join(''),

    items: () => `
      <div class="frame-grid">
        ${items.map((item) => `
          <button class="frame-item ${item.is_equipped ? 'is-active' : ''}" data-owned-item="${item.id}">
            ${item.kind === 'frame'
              ? `<span class="frame-preview ${esc(item.style)}">${avatarImg(user)}</span>`
              : `<span class="owned-icon ${item.kind === 'chat_bubble' ? esc(item.style) : ''}">${item.emoji}</span>`}
            <b>${esc(item.name)}</b>
            <small>${item.is_equipped ? 'Kullanımda' : `${KIND_LABELS[item.kind]} · ${daysLeft(item.owned_until)} gün`}</small>
          </button>`).join('')}
        ${user.is_me ? `<a class="frame-item frame-shop" href="#/store"><span class="owned-icon">🛍️</span><b>Mağaza</b><small>Yeni eşya al</small></a>` : ''}
      </div>
      ${!items.length && !user.is_me ? '<p class="member-empty">Henüz eşyası yok.</p>' : ''}`,

    rewards: () => `
      <h3 class="sub-title">Oyun Başarıları</h3>
      <div class="reward-grid">
        ${extras.achievements.map((a) => `<div class="reward reward-gold"><i>${a.emoji}</i><b>${esc(a.name)}</b><small>${esc(a.detail)}</small></div>`).join('')}
      </div>
      <h3 class="sub-title">Son Kazanılan Ödüller</h3>
      <div class="reward-grid">
        ${extras.recent_rewards.map((r) => `<div class="reward"><i>${r.emoji}</i><b>${esc(r.name)}</b><small>${esc(r.date_label)}</small></div>`).join('')}
      </div>`,

    about: () => `
      <dl class="about">
        <div><dt>Kullanıcı adı</dt><dd>@${esc(user.username)}</dd></div>
        <div><dt>Şehir</dt><dd>${esc(user.city || '—')}</dd></div>
        <div><dt>Yaş</dt><dd>${user.age || '—'}</dd></div>
        <div><dt>Seviye</dt><dd>Lv.${user.level}</dd></div>
        <div><dt>VIP</dt><dd>${user.vip_level ? `VIP ${user.vip_level}` : 'Yok'}</dd></div>
        <div><dt>Üyelik</dt><dd>${user.joined_days} gün</dd></div>
      </dl>`,
  };

  function showTab(tabId) {
    activeTab = tabId;
    root.querySelectorAll('#profile-tabs button').forEach((b) => b.classList.toggle('is-active', b.dataset.tab === tabId));
    panel.innerHTML = panels[tabId]();
  }
  showTab(activeTab);

  function openMenu() {
    const sheet = openSheet(`
      <div class="menu-list">
        <button data-menu="share">${icon('share', 20)} Profili paylaş</button>
        ${user.is_me
          ? `<a href="#/wallet" data-close>${icon('wallet', 20)} Cüzdan</a>
             <a href="#/store" data-close>${icon('crown', 20)} Mağaza</a>
             <a href="#/vip" data-close>👑 VIP</a>
             <a href="#/settings" data-close>${icon('edit', 20)} Ayarlar</a>
             <button data-menu="logout" class="is-danger">${icon('logout', 20)} Çıkış yap</button>`
          : `<button data-menu="block">${icon('lock', 20)} ${user.is_blocked ? 'Engeli kaldır' : 'Engelle'}</button>
             <button data-menu="report" class="is-danger">${icon('close', 20)} Şikâyet et</button>`}
      </div>`);
    sheet.el.addEventListener('click', async (event) => {
      const item = event.target.closest('[data-menu]');
      if (!item) return;
      sheet.close();
      if (item.dataset.menu === 'logout') {
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
        return showTab('items');
      } catch (error) {
        return toast(error.message, 'error');
      }
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
      const { is_following } = await api.toggleFollow(user.id);
      button.textContent = is_following ? 'Takiptesin' : 'Takip Et';
      button.className = `btn ${is_following ? 'btn-soft' : 'btn-primary'}`;
    } else if (action === 'message') {
      const conversationId = await api.openConversationWith(user.id);
      location.hash = `#/chat/${conversationId}`;
    } else if (action === 'like') {
      const liked = button.classList.toggle('is-liked');
      button.querySelector('span').textContent = Number(button.dataset.count) + (liked ? 1 : 0);
    } else if (action === 'edit') {
      // Kaydedilince ekranı yeniden çiz (yönlendirici aynı adresi baştan yükler)
      openEditProfileSheet(user, () => window.dispatchEvent(new HashChangeEvent('hashchange')))
        .catch((error) => toast(error.message, 'error'));
    } else if (action === 'soon') {
      toast('Bu özellik yakında geliyor');
    }
  });
}
