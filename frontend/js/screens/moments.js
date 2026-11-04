// Anılar: paylaşım akışı. Üstte "Benim" (takip ettiklerim) / "Önerilen" sekmeleri ve zil.
//   Kart: solda avatar; sağda ad + rozetler + yaş/seviye çipleri, takip et (+) ve menü;
//   altında yazı, küçük yuvarlatılmış görsel, zaman; en altta beğeni ve yorum sayıları, sağda "Sohbet".
//   Görsele çift dokununca beğenilir (kalp patlaması). Yorumlar alttan açılan panelde.
//   Sağ altta yüzen + düğmesi yeni anı paylaşır.
// Akış `mountMomentFeed` ile kurulur; Anılar sekmesi onu çizer, profil yalnızca kart ve davranışları kullanır.
import { api } from '../api.js';
import { esc, icon, avatarImg, formatCount, timeAgo, toast, openSheet, vipBadge } from '../ui.js';
import { paintNotificationBadge } from '../inbox.js';

const TABS = [
  { id: 'following', label: 'Benim' },
  { id: 'explore', label: 'Önerilen' },
];
const LONG_TEXT = 140;   // bundan uzun açıklama "devamı" ile kısaltılır

const verifiedMark = (user) => (user.is_verified ? `<span class="verified">${icon('verified', 14)}</span>` : '');

// Kart. Yazı ve görsel avatarın sağındaki sütunda; takip etmediğim kişide "+" takip düğmesi çıkar.
function momentCard(moment) {
  const { user } = moment;
  const isLong = moment.text.length > LONG_TEXT;
  return `
    <article class="post" data-moment="${moment.id}">
      <header class="post-head">
        <a class="post-avatar" href="#/profile/${user.id}">${avatarImg(user, 'avatar-md')}</a>
        <div class="post-author">
          <a href="#/profile/${user.id}"><b>${esc(user.display_name)}</b>${verifiedMark(user)}${vipBadge(user.vip_level)}</a>
          <span class="post-chips">
            ${user.age ? `<i class="chip-age">${user.age}</i>` : ''}<i class="chip-level">Lv.${user.level}</i>
            ${user.family ? `<i class="chip-family">${esc(user.family.badge)} ${esc(user.family.name)}</i>` : ''}
          </span>
        </div>
        ${moment.is_mine || user.is_following ? '' : `<button class="post-follow" data-follow-author="${user.id}" aria-label="Takip et">${icon('user-plus', 17)}</button>`}
        <button class="icon-btn icon-btn-plain" data-moment-menu="${moment.id}" aria-label="Seçenekler">${icon('more', 18)}</button>
      </header>
      <div class="post-content">
        ${moment.text ? `<p class="post-text ${isLong ? 'is-clamped' : ''}">${esc(moment.text)}</p>${isLong ? '<button class="post-more" data-expand>devamı</button>' : ''}` : ''}
        ${moment.image_url ? `
          <div class="post-media" data-double-like="${moment.id}">
            <img src="${esc(moment.image_url)}" alt="" loading="lazy" />
            <span class="post-burst">${icon('heart', 72)}</span>
          </div>` : ''}
        <small class="post-time">${timeAgo(moment.created_at)}</small>
        <div class="post-actions">
          <button class="post-action ${moment.is_liked ? 'is-liked' : ''}" data-like="${moment.id}" aria-label="Beğen">${icon('heart', 22)}<span data-like-count="${moment.id}">${formatCount(moment.like_count)}</span></button>
          <button class="post-action" data-comments="${moment.id}" aria-label="Yorumlar">${icon('comment', 22)}<span data-comment-count="${moment.id}">${formatCount(moment.comment_count)}</span></button>
          ${moment.is_mine ? '' : `<button class="post-chat" data-chat-author="${user.id}">${icon('chat', 16)} Sohbet</button>`}
        </div>
      </div>
    </article>`;
}

// Kareli ızgara hücresi (profildeki Paylaşımlar sekmesi)
export function momentTile(moment) {
  return moment.image_url
    ? `<button class="moment-tile" data-open-moment="${moment.id}"><img src="${esc(moment.image_url)}" alt="" loading="lazy" /></button>`
    : `<button class="moment-tile moment-tile-text" data-open-moment="${moment.id}"><span>${esc(moment.text)}</span></button>`;
}

// Yorum paneli: üstte gönderinin açıklaması, altında yorumlar, en altta yazma kutusu
async function openComments(moment, onCountChange) {
  const me = await api.getMe();
  const sheet = openSheet(`
    <h2 class="sheet-title">Yorumlar</h2>
    <div class="comment-list" id="comment-list"><div class="loading"><div class="spinner"></div></div></div>
    <form class="comment-form" id="comment-form">
      ${avatarImg(me, 'avatar-sm')}
      <input name="text" maxlength="300" placeholder="${esc(moment.user.display_name)} için yorum ekle…" autocomplete="off" />
      <button class="comment-send" type="submit" aria-label="Gönder">Paylaş</button>
    </form>`, { className: 'sheet-comments' });
  const list = sheet.el.querySelector('#comment-list');
  let comments = [];

  const row = (c) => `
    <div class="comment" data-comment="${c.id}">
      <a href="#/profile/${c.user.id}" data-close>${avatarImg(c.user, 'avatar-sm')}</a>
      <p><a href="#/profile/${c.user.id}" data-close><b>${esc(c.user.display_name)}</b></a> ${esc(c.text)}<small>${timeAgo(c.created_at)}</small></p>
      ${c.can_delete ? `<button class="icon-btn icon-btn-plain" data-delete-comment="${c.id}" aria-label="Yorumu sil">${icon('trash', 16)}</button>` : ''}
    </div>`;
  const header = moment.text ? `
    <div class="comment comment-caption">
      ${avatarImg(moment.user, 'avatar-sm')}
      <p><b>${esc(moment.user.display_name)}</b> ${esc(moment.text)}<small>${timeAgo(moment.created_at)}</small></p>
    </div>` : '';
  const paint = () => {
    list.innerHTML = header + (comments.map(row).join('') || '<p class="member-empty">Henüz yorum yok. İlk yorumu sen yaz.</p>');
    list.scrollTop = list.scrollHeight;
  };
  const setCount = (count) => { moment.comment_count = count; onCountChange(moment); };

  try {
    comments = await api.listMomentComments(moment.id);
    paint();
  } catch (error) {
    list.innerHTML = `<p class="member-empty">${esc(error.message)}</p>`;
  }

  const form = sheet.el.querySelector('#comment-form');
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const input = form.elements.text;
    const text = input.value.trim();
    if (!text) return;
    const submit = form.querySelector('[type="submit"]');
    submit.disabled = true;
    try {
      comments.push(await api.addMomentComment(moment.id, text));
      input.value = '';
      paint();
      setCount(moment.comment_count + 1);
    } catch (error) {
      toast(error.message, 'error');
    } finally {
      submit.disabled = false;
    }
  });

  list.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-delete-comment]');
    if (!button) return;
    const id = Number(button.dataset.deleteComment);
    try {
      await api.deleteMomentComment(moment.id, id);
      comments = comments.filter((c) => c.id !== id);
      paint();
      setCount(Math.max(0, moment.comment_count - 1));
    } catch (error) {
      toast(error.message, 'error');
    }
  });
}

// Bir ekranın anı listesine beğen / yorum / paylaş / menü / büyütme davranışını bağlar.
// `getList` güncel listeyi döner, `onChange` liste değişince (silme) ekranı yeniden çizer.
export function bindMomentActions(root, { getList, onChange }) {
  const find = (id) => getList().find((m) => m.id === Number(id));

  // Aynı anı ekranda birden çok yerde olabilir (akış + büyütülmüş kart): hepsini birlikte güncelle
  const paintLike = (moment) => {
    document.querySelectorAll(`[data-like="${moment.id}"]`).forEach((b) => b.classList.toggle('is-liked', moment.is_liked));
    document.querySelectorAll(`[data-like-count="${moment.id}"]`).forEach((el) => { el.textContent = formatCount(moment.like_count); });
  };
  const paintComments = (moment) => {
    document.querySelectorAll(`[data-comment-count="${moment.id}"]`).forEach((el) => { el.textContent = formatCount(moment.comment_count); });
  };

  let liking = false;
  async function like(moment, { onlyLike = false } = {}) {
    if (!moment || liking || (onlyLike && moment.is_liked)) return;
    liking = true;
    try {
      const result = await api.toggleMomentLike(moment.id);
      Object.assign(moment, { is_liked: result.is_liked, like_count: result.like_count });
      paintLike(moment);
    } catch (error) {
      toast(error.message, 'error');
    } finally {
      liking = false;
    }
  }

  // Görsele çift dokunma: Instagram'daki gibi yalnızca beğenir (geri almaz) ve kalp patlatır
  function burst(media) {
    media.classList.remove('is-bursting');
    void media.offsetWidth;   // animasyonu baştan başlatmak için tarayıcıya yeniden ölçtürür
    media.classList.add('is-bursting');
  }

  // Takip et (+): aynı kişinin bütün kartlarındaki düğme kalkar
  async function followAuthor(button) {
    const userId = Number(button.dataset.followAuthor);
    button.disabled = true;
    try {
      const { is_following: isFollowing } = await api.toggleFollow(userId);
      if (!isFollowing) return;
      getList().forEach((m) => { if (m.user.id === userId) m.user.is_following = true; });
      document.querySelectorAll(`[data-follow-author="${userId}"]`).forEach((b) => b.remove());
      toast('Takip ediyorsun', 'success');
    } catch (error) {
      toast(error.message, 'error');
      button.disabled = false;
    }
  }

  async function openChat(userId, closeSheet) {
    try {
      const conversationId = await api.openConversationWith(userId);
      closeSheet?.();
      location.hash = `#/chat/${conversationId}`;
    } catch (error) {
      toast(error.message, 'error');
    }
  }

  function share(moment) {
    const url = `${location.origin}${location.pathname}#/profile/${moment.user.id}`;
    if (navigator.share) {
      navigator.share({ title: moment.user.display_name, text: moment.text, url }).catch(() => {});
    } else {
      navigator.clipboard?.writeText(url).catch(() => {});
      toast('Bağlantı kopyalandı');
    }
  }

  function openMenu(moment) {
    const sheet = openSheet(`
      <div class="menu-list">
        <a href="#/profile/${moment.user.id}" data-close>${icon('user', 20)} Profili gör</a>
        <button data-menu="share">${icon('send', 20)} Paylaş</button>
        ${moment.is_mine ? `<button data-menu="delete" class="is-danger">${icon('trash', 20)} Anıyı sil</button>` : ''}
      </div>`);
    sheet.el.addEventListener('click', async (event) => {
      const action = event.target.closest('[data-menu]')?.dataset.menu;
      if (!action) return;
      sheet.close();
      if (action === 'share') return share(moment);
      try {
        await api.deleteMoment(moment.id);
        toast('Anı silindi', 'success');
        onChange(getList().filter((m) => m.id !== moment.id));
      } catch (error) {
        toast(error.message, 'error');
      }
    });
  }

  // Kartın içindeki tıklamalar (akışta da, büyütülmüş kartta da aynı)
  function handle(event, { closeSheet } = {}) {
    const likeButton = event.target.closest('[data-like]');
    if (likeButton) { like(find(likeButton.dataset.like)); return true; }
    const commentsButton = event.target.closest('[data-comments]');
    if (commentsButton) {
      closeSheet?.();
      openComments(find(commentsButton.dataset.comments), paintComments).catch((error) => toast(error.message, 'error'));
      return true;
    }
    const followButton = event.target.closest('[data-follow-author]');
    if (followButton) { followAuthor(followButton); return true; }
    const chatButton = event.target.closest('[data-chat-author]');
    if (chatButton) { openChat(Number(chatButton.dataset.chatAuthor), closeSheet); return true; }
    const menuButton = event.target.closest('[data-moment-menu]');
    if (menuButton) { closeSheet?.(); openMenu(find(menuButton.dataset.momentMenu)); return true; }
    const expand = event.target.closest('[data-expand]');
    if (expand) {
      expand.previousElementSibling?.classList.remove('is-clamped');
      expand.remove();
      return true;
    }
    return false;
  }

  function bindDoubleTap(el) {
    el.addEventListener('dblclick', (event) => {
      const media = event.target.closest('[data-double-like]');
      if (!media) return;
      burst(media);
      like(find(media.dataset.doubleLike), { onlyLike: true });
    });
  }

  bindDoubleTap(root);
  root.addEventListener('click', (event) => {
    if (handle(event)) return;
    const tile = event.target.closest('[data-open-moment]');
    if (tile) {
      const sheet = openSheet(momentCard(find(tile.dataset.openMoment)), { className: 'sheet-moment' });
      bindDoubleTap(sheet.el);
      sheet.el.addEventListener('click', (e) => handle(e, { closeSheet: sheet.close }));
    }
  });
}

// Paylaşma paneli: yazı + hazır görsellerden biri (görsel yükleme henüz yok)
export async function openComposer(onCreated) {
  const [me, { images }] = await Promise.all([api.getMe(), api.getMomentImageOptions()]);
  let image = null;
  const sheet = openSheet(`
    <h2 class="sheet-title">Yeni anı</h2>
    <form id="moment-form" class="composer">
      <div class="composer-row">
        ${avatarImg(me, 'avatar-sm')}
        <textarea name="text" maxlength="500" rows="4" placeholder="Neler oluyor?"></textarea>
      </div>
      <div class="composer-preview" hidden><img alt="" /><button type="button" data-clear-image aria-label="Görseli kaldır">${icon('close', 14)}</button></div>
      <div class="field">
        <span>Görsel ekle (isteğe bağlı)</span>
        <div class="image-picker">
          ${images.map((url) => `<button type="button" data-image="${esc(url)}"><img src="${esc(url)}" alt="" loading="lazy" /></button>`).join('')}
        </div>
      </div>
      <div class="composer-foot">
        <small data-counter>0 / 500</small>
        <button class="btn btn-primary" type="submit">Paylaş</button>
      </div>
    </form>`);
  const form = sheet.el.querySelector('#moment-form');
  const preview = form.querySelector('.composer-preview');

  const paintImage = () => {
    sheet.el.querySelectorAll('[data-image]').forEach((b) => b.classList.toggle('is-active', b.dataset.image === image));
    preview.hidden = !image;
    if (image) preview.querySelector('img').src = image;
  };
  form.addEventListener('click', (event) => {
    if (event.target.closest('[data-clear-image]')) { image = null; paintImage(); return; }
    const button = event.target.closest('[data-image]');
    if (!button) return;
    image = image === button.dataset.image ? null : button.dataset.image;
    paintImage();
  });
  form.elements.text.addEventListener('input', (event) => {
    form.querySelector('[data-counter]').textContent = `${event.target.value.length} / 500`;
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const text = form.elements.text.value.trim();
    if (!text && !image) return toast('Bir şey yaz ya da bir görsel seç');
    const submit = form.querySelector('[type="submit"]');
    submit.disabled = true;
    try {
      const moment = await api.createMoment({ text, image_url: image });
      sheet.close();
      toast('Anın paylaşıldı', 'success');
      onCreated?.(moment);
    } catch (error) {
      toast(error.message, 'error');
      submit.disabled = false;
    }
  });
}

// Akışı bir kapsayıcıya kurar: sekme düğmeleri `tabsRoot` içine (Benim / Önerilen), kartlar ve aşağı
// indikçe eskilerin yüklenmesi (imleçli sayfalama: son kartın id'si `before_id` olarak gider).
// `{ stop, compose }` döner: stop ekran kapanınca çağrılır, compose paylaşma panelini açar.
async function mountMomentFeed(container, { tabsRoot, initialTab = 'explore' }) {
  let activeTab = initialTab;
  let moments = [];
  let isLoading = false;
  let hasMore = true;

  tabsRoot.innerHTML = TABS.map((t) => `<button class="${t.id === activeTab ? 'is-active' : ''}" data-feed-tab="${t.id}">${t.label}</button>`).join('');
  container.innerHTML = `
    <div class="post-feed" data-feed-list></div>
    <div class="feed-sentinel" data-feed-sentinel></div>`;
  const list = container.querySelector('[data-feed-list]');
  const sentinel = container.querySelector('[data-feed-sentinel]');

  function paint() {
    list.innerHTML = moments.length ? moments.map(momentCard).join('') : `
      <div class="empty">
        <p>${activeTab === 'following' ? 'Takip ettiğin kişiler henüz bir şey paylaşmadı. Önerilen sekmesine göz at.' : 'Henüz anı yok.'}</p>
        <button class="btn btn-primary" data-action="compose">İlk anını paylaş</button>
      </div>`;
  }

  async function loadMore() {
    if (isLoading || !hasMore) return;
    isLoading = true;
    sentinel.innerHTML = '<div class="spinner"></div>';
    try {
      const tab = activeTab;
      const page = await api.listMoments({ feed: tab, beforeId: moments.at(-1)?.id });
      // Sekme bu arada değiştiyse geç gelen sayfayı at
      if (tab !== activeTab) return;
      hasMore = page.length > 0;
      const before = moments.length;
      moments = moments.concat(page);
      if (!before) paint();
      else list.insertAdjacentHTML('beforeend', page.map(momentCard).join(''));
    } catch (error) {
      toast(error.message, 'error');
      hasMore = false;
    } finally {
      isLoading = false;
      sentinel.innerHTML = '';
    }
  }

  async function reset(tab) {
    activeTab = tab;
    moments = [];
    hasMore = true;
    list.innerHTML = '';
    tabsRoot.querySelectorAll('[data-feed-tab]').forEach((b) => b.classList.toggle('is-active', b.dataset.feedTab === tab));
    await loadMore();
  }

  bindMomentActions(container, { getList: () => moments, onChange: (next) => { moments = next; paint(); } });

  const compose = () => openComposer((moment) => { moments = [moment, ...moments]; paint(); }).catch((error) => toast(error.message, 'error'));
  tabsRoot.addEventListener('click', (event) => {
    const tab = event.target.closest('[data-feed-tab]');
    if (tab && tab.dataset.feedTab !== activeTab && !isLoading) reset(tab.dataset.feedTab);
  });
  container.addEventListener('click', (event) => {
    if (event.target.closest('[data-action="compose"]')) compose();
  });

  await loadMore();
  // Sayfanın sonu görünür olunca bir sonraki sayfa gelir
  const observer = new IntersectionObserver((entries) => {
    if (entries.some((e) => e.isIntersecting)) loadMore();
  }, { rootMargin: '400px 0px' });
  observer.observe(sentinel);
  return { stop: () => observer.disconnect(), compose };
}

// Anılar sekmesi: üstte Benim / Önerilen sekmeleri ve zil, altında akış, sağ altta yüzen + (paylaş)
export async function renderMoments(root, { query }) {
  root.innerHTML = `
    <header class="topbar">
      <nav class="head-tabs" id="moment-tabs"></nav>
      <div class="topbar-actions">
        <button class="icon-btn icon-btn-plain" data-action="notifications" aria-label="Bildirimler">${icon('bell', 22)}</button>
      </div>
    </header>
    <section id="moment-feed"></section>
    <button class="fab" data-action="compose" aria-label="Anı paylaş">${icon('edit', 24)}</button>`;
  paintNotificationBadge();
  const feed = await mountMomentFeed(root.querySelector('#moment-feed'), {
    tabsRoot: root.querySelector('#moment-tabs'),
    initialTab: query.tab === 'following' ? 'following' : 'explore',
  });
  root.querySelector('.fab').addEventListener('click', feed.compose);
  root.querySelector('[data-action="notifications"]').addEventListener('click', () => { location.hash = '#/notifications'; });
  return feed.stop;
}
