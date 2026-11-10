// Tam ekran kameralı canlı yayın (#/live/:id) — Bigo / TikTok canlısı gibi.
// Yayıncının yüzü bütün ekranı kaplar; üstte yayıncı + izleyici sayısı, altta yarı saydam sohbet,
// mesaj kutusu ve hediye tuşu. Koltuk yok.
//
// Sohbet, hediye ve izleyici sayısı oda kanalından (WebSocket) gelir; ses + görüntü ayrı bir
// bağlantıdır (js/voice/live-video.js). "Şu an yayında mı?" bilgisinin sahibi sunucu
// (`room:camera_updated`); ekran yalnızca ona göre bağlanıp kopar.
import { api } from '../api.js';
import { connectRoom } from '../realtime.js';
import { connectLiveVideo, startPreview } from '../voice/live-video.js';
import { openGiftSheet } from './gift-sheet.js';
import { openReportSheet } from './report.js';
import { esc, icon, avatarImg, formatCoins, formatCount, toast, openSheet, goBack } from '../ui.js';

const MAX_CHAT_LINES = 40;
const END_REASONS = {
  stopped: 'Yayın bitti.',
  left: 'Yayıncı yayından ayrıldı.',
  moderator: 'Yayın kapatıldı.',
  staff: 'Yayın kurallara aykırı bulunduğu için kapatıldı.',
};

export async function renderLive(root, { params }) {
  const [room, me, gifts] = await Promise.all([api.getRoom(params[0]), api.getMe(), api.listGifts()]);
  // Sesli oda bağlantısıyla gelindiyse doğru ekrana geç
  if (room.kind !== 'live') {
    location.replace(`#/room/${room.id}`);
    return () => {};
  }
  const isOwner = room.host_id === me.id;
  const host = room.host;
  let liveUserId = room.camera_user_id ?? null;
  let joined = false;          // sunucu bizi yayın odasına ekledi mi (bağlanmadan önce şart)
  let media = null;            // ses + görüntü bağlantısı
  let connecting = null;
  let preview = null;          // yayıncının yayın öncesi önizlemesi
  let micOn = true;
  let disposed = false;
  let startedAt = null;
  let giftCoins = 0;           // bu yayında yayıncıya gelen hediyelerin coin değeri (özet için)
  const seenMessages = new Set();
  const channel = connectRoom(room);

  root.innerHTML = `
    <div class="live">
      <div class="live-screen" id="live-screen"></div>
      <div class="live-shade"></div>

      <header class="live-top">
        <div class="live-host">
          ${avatarImg(host, 'avatar-sm')}
          <span><b>${esc(host.display_name)}</b><small id="live-title">${esc(room.title)}</small></span>
          ${isOwner ? '' : `<button class="btn btn-sm ${host.is_following ? 'btn-glass' : 'btn-primary'}" data-action="follow">${host.is_following ? 'Takipte' : 'Takip et'}</button>`}
        </div>
        <span class="live-viewers">${icon('users', 14)} <b id="viewer-count">${formatCount(room.listener_count)}</b></span>
        <button class="icon-btn icon-btn-glass" data-action="close" aria-label="Çık">${icon('close', 20)}</button>
      </header>
      <span class="live-badge" id="live-badge" hidden>● CANLI</span>

      <div class="live-overlay" id="live-overlay" hidden></div>
      <button class="btn btn-sm btn-glass live-unmute" id="unmute" hidden>🔊 Sesi aç</button>
      <div class="live-gift-stage" id="gift-stage"></div>

      <div class="live-bottom">
        <div class="live-chat" id="chat"></div>
        <form class="live-bar" id="live-bar">
          <input name="text" placeholder="Bir şey yaz..." autocomplete="off" maxlength="200" />
          ${isOwner ? `
            <button type="button" class="icon-btn icon-btn-glass" data-action="mic" id="mic-btn" aria-label="Mikrofon" hidden>${icon('mic', 20)}</button>
            <button type="button" class="icon-btn icon-btn-glass" data-action="flip" id="flip-btn" aria-label="Kamerayı çevir" hidden>🔄</button>
            <button type="button" class="btn btn-sm btn-danger" data-action="end" id="end-btn" hidden>Bitir</button>`
          : `
            <button type="button" class="icon-btn icon-btn-glass" data-action="more" aria-label="Menü">${icon('more', 20)}</button>
            <button type="button" class="icon-btn icon-btn-gift" data-action="gift" aria-label="Hediye gönder">${icon('gift', 20)}</button>`}
        </form>
      </div>
    </div>`;

  const screenEl = root.querySelector('#live-screen');
  const overlayEl = root.querySelector('#live-overlay');
  const chatEl = root.querySelector('#chat');
  const giftStageEl = root.querySelector('#gift-stage');
  const unmuteBtn = root.querySelector('#unmute');

  // ─── SOHBET ────────────────────────────────────────────────────────────────
  function addLine(html) {
    chatEl.insertAdjacentHTML('beforeend', `<div class="live-line">${html}</div>`);
    while (chatEl.children.length > MAX_CHAT_LINES) chatEl.firstElementChild.remove();
    chatEl.scrollTop = chatEl.scrollHeight;
  }

  function addMessage({ id, user, text }) {
    if (seenMessages.has(id)) return;
    seenMessages.add(id);
    addLine(`<b>${esc(user.display_name)}${user.id === host.id ? ' <span class="mini-role mini-role-host">Yayıncı</span>' : ''}</b> ${esc(text)}`);
  }

  // ─── HEDİYE ────────────────────────────────────────────────────────────────
  function showGift({ sender, receiver, gift, quantity }) {
    if (receiver.id === host.id) giftCoins += gift.price * quantity;
    addLine(`🎁 <b>${esc(sender.display_name)}</b> ${gift.emoji} ${esc(gift.name)} x${quantity} gönderdi`);
    const el = document.createElement('div');
    el.className = `live-gift ${gift.price * quantity >= 1000 ? 'is-big' : ''}`;
    el.innerHTML = `<i>${gift.emoji}</i><span><b>${esc(sender.display_name)}</b><small>${esc(gift.name)} x${quantity}</small></span>`;
    giftStageEl.append(el);
    setTimeout(() => el.remove(), 3200);
  }

  function sendGiftSheet() {
    if (!liveUserId) return toast('Yayın şu an kapalı.');
    openGiftSheet({
      gifts, balance: me.coin_balance, receivers: [host],
      async send({ giftId, quantity }) {
        const result = await api.sendGift({ room_id: room.id, receiver_id: host.id, gift_id: giftId, quantity });
        me.coin_balance = result.coin_balance;
        // Animasyonu odaya sunucu yayınlar (`gift:sent`); büyük hediyede panel kapansın ki görünsün
        return { ...result, closeSheet: result.gift.price * quantity >= 1000 };
      },
    });
  }

  // ─── SES + GÖRÜNTÜ ─────────────────────────────────────────────────────────
  function closeMedia() {
    media?.close();
    media = null;
    screenEl.replaceChildren();
  }

  function stopPreview() {
    preview?.stop();
    preview = null;
  }

  async function connect() {
    if (!joined || !liveUserId || media || connecting) return;
    stopPreview();
    const forUser = liveUserId;
    connecting = (async () => {
      try {
        const info = await api.getCameraJoin(room.id);
        if (disposed || forUser !== liveUserId) return;
        const next = await connectLiveVideo({
          info, me, stageEl: screenEl, channel,
          refreshInfo: () => api.getCameraJoin(room.id),
          onError: (message) => toast(message, 'error'),
          onNeedsTap: (resume) => {
            unmuteBtn.hidden = false;
            unmuteBtn.onclick = () => { unmuteBtn.hidden = true; resume?.(); };
          },
        });
        if (disposed || forUser !== liveUserId) return next.close();
        media = next;
      } catch (error) {
        if (disposed) return;
        toast(error.message, 'error');
        // Yayıncının kamerası açılamadıysa yayını kapat: izleyiciler boş ekrana bakmasın
        if (isOwner) api.stopCamera(room.id).catch(() => {});
      } finally {
        connecting = null;
      }
    })();
    await connecting;
  }

  // ─── EKRAN DURUMU ──────────────────────────────────────────────────────────
  function renderState(reason = '') {
    const live = Boolean(liveUserId);
    root.querySelector('#live-badge').hidden = !live;
    if (isOwner) {
      ['#mic-btn', '#flip-btn', '#end-btn'].forEach((s) => { root.querySelector(s).hidden = !live; });
    }
    if (live) {
      overlayEl.hidden = true;
      return;
    }
    overlayEl.hidden = false;
    if (isOwner) {
      // Yayın öncesi: kendini önizle, başlığı yaz, yayına çık
      overlayEl.innerHTML = `
        <div class="live-start">
          ${reason ? `<p class="live-end-note">${esc(END_REASONS[reason] || 'Yayın bitti.')}</p>` : ''}
          <input class="live-title-input" id="title-input" maxlength="60" value="${esc(room.title)}" placeholder="Yayın başlığı" />
          <button class="btn btn-primary btn-block" data-action="go-live">🎥 Yayını başlat</button>
          <small>Yüzün ve sesin bu odadaki herkese gider. Kurallara aykırı yayın anında kapatılır.</small>
        </div>`;
      if (!preview) {
        startPreview(screenEl).then((p) => {
          if (disposed || liveUserId) return p.stop();
          preview = p;
        }).catch((error) => toast(error.message, 'error'));
      }
    } else {
      overlayEl.innerHTML = `
        <div class="live-offline">
          ${avatarImg(host, 'avatar-xl')}
          <b>${esc(host.display_name)}</b>
          <p>${esc(reason ? END_REASONS[reason] || 'Yayın bitti.' : 'Şu an yayında değil.')}</p>
          <p class="demo-note">Takip edersen yayına başlayınca bildirim gelir.</p>
          <a class="btn btn-soft" href="#/rooms?tab=live">Diğer yayınlar</a>
        </div>`;
    }
  }

  function apply(nextUserId, reason = '') {
    const wasLive = Boolean(liveUserId);
    liveUserId = nextUserId;
    if (liveUserId && !startedAt) startedAt = Date.now();
    if (!liveUserId) {
      closeMedia();
      if (wasLive && isOwner && reason) showSummary(reason);
    }
    renderState(reason);
    if (liveUserId) connect();
  }

  // Yayıncı yayını bitirince kısa özet
  function showSummary(reason) {
    const minutes = startedAt ? Math.max(1, Math.round((Date.now() - startedAt) / 60000)) : 0;
    startedAt = null;
    const sheet = openSheet(`
      <div class="sheet-body live-summary">
        <h2>${esc(END_REASONS[reason] || 'Yayın bitti.')}</h2>
        <div class="income-stats">
          <div><b>${minutes} dk</b><small>Süre</small></div>
          <div><b>${formatCoins(giftCoins)}</b><small>Hediye (coin)</small></div>
        </div>
        <a class="btn btn-primary btn-block" href="#/wallet?tab=income" data-close>Kazancıma bak</a>
        <button class="btn btn-soft btn-block" data-close>Kapat</button>
      </div>`, { className: 'sheet-dark' });
    giftCoins = 0;
    return sheet;
  }

  async function goLive() {
    const title = root.querySelector('#title-input')?.value.trim();
    const button = overlayEl.querySelector('[data-action="go-live"]');
    if (button) button.disabled = true;
    try {
      if (title && title !== room.title) {
        room.title = (await api.openMyStream(title)).title;
        root.querySelector('#live-title').textContent = room.title;
      }
      if (!joined) throw new Error('Bağlanıyor, birkaç saniye sonra tekrar dene.');
      apply((await api.startCamera(room.id)).user_id);
    } catch (error) {
      toast(error.message, 'error');
      if (button) button.disabled = false;
    }
  }

  function confirmEnd() {
    const sheet = openSheet(`
      <div class="sheet-body">
        <h2>Yayını bitir?</h2>
        <button class="btn btn-danger btn-block" data-confirm>Bitir</button>
        <button class="btn btn-soft btn-block" data-close>Devam et</button>
      </div>`, { className: 'sheet-dark' });
    sheet.el.querySelector('[data-confirm]').addEventListener('click', async () => {
      sheet.close();
      try {
        await api.stopCamera(room.id);
        apply(null, 'stopped');
      } catch (error) {
        toast(error.message, 'error');
      }
    });
  }

  function leave() {
    if (isOwner && liveUserId) return confirmEnd();
    goBack('#/rooms?tab=live');
  }

  // ─── OLAYLAR ───────────────────────────────────────────────────────────────
  root.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-action]');
    if (!button) return;
    const { action } = button.dataset;
    if (action === 'close') leave();
    else if (action === 'gift') sendGiftSheet();
    else if (action === 'go-live') goLive();
    else if (action === 'end') confirmEnd();
    else if (action === 'flip') media?.switchCamera?.();
    else if (action === 'mic') {
      micOn = !micOn;
      await media?.setMicEnabled?.(micOn);
      button.classList.toggle('is-off', !micOn);
      toast(micOn ? 'Mikrofon açık' : 'Mikrofon kapalı');
    } else if (action === 'more') {
      openReportSheet('room', room.id, room.title);
    } else if (action === 'follow') {
      button.disabled = true;
      try {
        const { is_following: following } = await api.toggleFollow(host.id);
        button.textContent = following ? 'Takipte' : 'Takip et';
        button.classList.toggle('btn-primary', !following);
        button.classList.toggle('btn-glass', following);
      } catch (error) {
        toast(error.message, 'error');
      } finally {
        button.disabled = false;
      }
    }
  });

  root.querySelector('#live-bar').addEventListener('submit', (event) => {
    event.preventDefault();
    const input = event.target.elements.text;
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    channel.send('chat:message', { text });
  });

  let closedByServer = false;
  function exit(message) {
    if (closedByServer) return;
    closedByServer = true;
    if (message) toast(message, 'error');
    goBack('#/rooms?tab=live');
  }

  channel
    .on('chat:history', ({ messages }) => {
      messages.forEach(addMessage);
      // Sunucu bizi odaya ekledikten sonra bunu gönderir; görüntü izni de odada olmayı şart koşuyor
      if (!joined) {
        joined = true;
        if (liveUserId) connect();
      }
    })
    .on('chat:message', addMessage)
    .on('gift:sent', showGift)
    .on('room:user_joined', ({ user }) => addLine(`<span class="live-join">${esc(user.display_name)} yayına katıldı</span>`))
    .on('room:listener_count', ({ listener_count: count }) => {
      root.querySelector('#viewer-count').textContent = formatCount(count);
    })
    .on('room:camera_updated', ({ camera, reason }) => apply(camera?.user_id ?? null, camera ? '' : reason))
    .on('room:closed', () => exit('Yayın kapatıldı.'))
    .on('connection:reopened', async () => {
      // Bağlantı koptu-geldi: arada yayın başlamış ya da bitmiş olabilir
      const activities = await api.getActivities(room.id).catch(() => null);
      if (activities && !disposed) apply(activities.camera?.user_id ?? null, activities.camera ? '' : 'stopped');
    })
    .on('error', ({ code, detail }) => {
      if (code === 'room_banned' || code === 'session_replaced') exit(detail);
      else toast(detail, 'error');
    });

  renderState();

  return () => {
    disposed = true;
    stopPreview();
    closeMedia();
    channel.close();
  };
}
