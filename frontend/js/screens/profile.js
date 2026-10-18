// Profil: kapak, istatistikler ve sekmeler (Duvar, Çerçeveler, Oyun & Ödüller, Hakkında)
import { api } from '../api.js';
import { DEFAULT_COVER_URL } from '../config.js';
import { esc, icon, avatarImg, formatCount, joinParts, vipBadge, levelBadge, toast, openSheet } from '../ui.js';

const TABS = [
  { id: 'wall', label: 'Duvar' },
  { id: 'frames', label: 'Çerçeveler' },
  { id: 'rewards', label: 'Oyun & Ödüller' },
  { id: 'about', label: 'Hakkında' },
];

export async function renderProfile(root, { params }) {
  const me = await api.getMe();
  const user = params[0] ? await api.getUser(params[0]) : me;
  const extras = await api.getProfileExtras(user.id);
  const ownedFrames = extras.avatar_frames.filter((f) => f.is_owned).length;
  let activeTab = 'wall';
  let activeFrameId = 1;

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
        <div class="profile-avatar frame-classic" id="profile-avatar">${avatarImg(user)}</div>
        <div class="profile-id">
          <h1>${esc(user.display_name)} ${user.is_verified ? `<span class="verified">${icon('verified', 18)}</span>` : ''}</h1>
          <button class="id-copy" data-action="copy-id">ID ${user.id} ${icon('copy', 13)}</button>
        </div>
        <div class="profile-badges">${vipBadge(user.vip_level)}${levelBadge(user.level)}</div>
      </div>

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
        <button data-tab-jump="frames"><i>💠</i><span><b>Çerçeveler</b><small>${ownedFrames}/${extras.avatar_frames.length}</small></span></button>
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

    frames: () => `
      <div class="frame-grid">
        ${extras.avatar_frames.map((f) => `
          <button class="frame-item ${f.id === activeFrameId ? 'is-active' : ''} ${f.is_owned ? '' : 'is-locked'}" data-frame="${f.id}">
            <span class="frame-preview ${f.style}">${avatarImg(user)}${f.is_owned ? '' : `<i class="frame-lock">${icon('lock', 14)}</i>`}</span>
            <b>${esc(f.name)}</b>
            <small>${f.id === activeFrameId ? 'Kullanımda' : f.is_owned ? 'Sahipsin' : 'Kilitli'}</small>
          </button>`).join('')}
      </div>`,

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
          ? `<a href="#/wallet" data-close>${icon('wallet', 20)} Cüzdan</a><button data-menu="logout" class="is-danger">${icon('logout', 20)} Çıkış yap</button>`
          : `<button data-menu="report" class="is-danger">${icon('close', 20)} Şikayet et</button>`}
      </div>`);
    sheet.el.addEventListener('click', async (event) => {
      const item = event.target.closest('[data-menu]');
      if (!item) return;
      sheet.close();
      if (item.dataset.menu === 'logout') {
        await api.logout();
        location.hash = '#/auth';
      } else if (item.dataset.menu === 'report') {
        toast('Şikayetin alındı, incelenecek.');
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

    const frame = event.target.closest('[data-frame]');
    if (frame) {
      const selected = extras.avatar_frames.find((f) => f.id === Number(frame.dataset.frame));
      if (!selected.is_owned) return toast('Bu çerçeve kilitli. Seviye atlayarak veya mağazadan açabilirsin.');
      if (!user.is_me) return;
      activeFrameId = selected.id;
      avatarEl.className = `profile-avatar ${selected.style}`;
      return showTab('frames');
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
    } else if (action === 'edit' || action === 'soon') {
      toast('Bu özellik yakında geliyor');
    }
  });
}
