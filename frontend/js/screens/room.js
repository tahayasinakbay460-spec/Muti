// Sesli oda: koltuklar, canlı sohbet, hediye paneli ve oda içi oyun
import { api } from '../api.js';
import { connectRoom } from '../realtime.js';
import { joinVoice } from '../voice/index.js';
import { openReportSheet } from './report.js';
import { CATEGORY_LABELS } from '../config.js';
import { esc, icon, avatarImg, framedAvatar, formatCoins, vipBadge, levelBadge, toast, openSheet, joinParts } from '../ui.js';

const MAX_CHAT_LINES = 60;
const QUANTITIES = [1, 5, 10, 99];
const DICE_FACES = ['⚀', '⚁', '⚂', '⚃', '⚄', '⚅'];
const DICE_SPIN_MS = 900;
const DICE_COOLDOWN_MS = 1600;
const ROULETTE_COLORS = [
  { id: 'red', label: 'Kırmızı', hint: '18 sayı' },
  { id: 'black', label: 'Siyah', hint: '18 sayı' },
  { id: 'green', label: 'Yeşil', hint: 'yalnızca 0' },
];
const COLOR_LABELS = { red: 'Kırmızı', black: 'Siyah', green: 'Yeşil' };
// Hediyenin toplam değerine (fiyat × adet) göre animasyon büyüklüğü
const GIFT_MEDIUM_FROM = 99;
const GIFT_BIG_FROM = 999;
const GIFT_COMBO_MS = 4000;
const CONFETTI_COLORS = ['#ff4d9d', '#ffc53d', '#8b5cff', '#2ee6a6', '#3d8bff'];
// Şanslı hediyede bu çarpan ve üstü odada büyük duyuruyla gösterilir
const LUCKY_BIG_MULTIPLIER = 10;
const ENTRY_EFFECT_MS = 3200;
const ROLE_RANK = { host: 4, admin: 3, vip: 2, listener: 1 };
const ROLE_LABELS = { host: 'Oda Sahibi', admin: 'Yönetici', vip: 'VIP' };
const CHAT_MUTE_OPTIONS = [
  { minutes: 5, label: '5 dakika' },
  { minutes: 30, label: '30 dakika' },
  { minutes: 60, label: '1 saat' },
  { minutes: 1440, label: '24 saat' },
];

export async function renderRoom(root, { params }) {
  let [room, me, gifts] = await Promise.all([api.getRoom(params[0]), api.getMe(), api.listGifts()]);
  let speakingIndexes = [];
  // Zar atıp sonucunu bekliyorsak, sonuç gelince çağrılacak fonksiyon
  let pendingDiceRoll = null;
  // Odadaki rulet turunun durumu (panel kapalıyken de güncel tutulur; panel açılınca buradan çizilir)
  const roulette = { roundId: null, endsAt: 0, bets: new Map(), last: null };
  let rouletteView = null;   // rulet paneli açıkken { render } nesnesi
  const channel = connectRoom(room, me);
  // Sesli görüşme (WebRTC). Bağlanırken hata olursa oda yine çalışır, yalnızca ses olmaz.
  let voice = null;
  let isDisposed = false;

  const mySeat = () => room.seats.find((s) => s.user?.id === me.id);

  // Roller: oda sahibi > yönetici > VIP > dinleyici. Asıl yetki kontrolü sunucuda; burada yalnızca
  // hangi düğmelerin gösterileceğine karar veriyoruz.
  const roleOf = (userId) => (
    userId === room.host_id ? 'host'
      : room.admin_ids.includes(userId) ? 'admin'
        : room.vip_ids.includes(userId) ? 'vip' : 'listener');
  const isModerator = () => ROLE_RANK[roleOf(me.id)] >= ROLE_RANK.admin;
  const canModerate = (userId) => userId !== me.id && ROLE_RANK[roleOf(me.id)] > ROLE_RANK[roleOf(userId)];
  const audience = room.seats.filter((s) => s.user).slice(0, 3);
  // Sohbette susturulanlar: kullanıcı id → susturmanın bittiği an (ms). Menüde doğru düğmeyi göstermek için.
  const chatMutedUntil = new Map();
  const isChatMuted = (userId) => (chatMutedUntil.get(userId) || 0) > Date.now();
  // Ekrandaki sohbet mesajları: id → mesaj (silme menüsü için)
  const chatMessages = new Map();

  root.innerHTML = `
    <div class="room">
      <img class="room-bg" src="${esc(room.cover_url)}" alt="" />
      <header class="room-header">
        <button class="icon-btn icon-btn-glass" data-action="leave" aria-label="Odadan çık">${icon('chevron-down', 22)}</button>
        <img class="room-thumb" src="${esc(room.cover_url)}" alt="" />
        <div class="room-title">
          <h1 id="room-name">${esc(room.title)}</h1>
          <p>ID ${room.id} • <span id="listener-count">${room.listener_count}</span> kişi • <span id="room-category">${CATEGORY_LABELS[room.category]}</span></p>
        </div>
        <button class="btn btn-sm ${room.is_following ? 'btn-glass' : 'btn-primary'}" data-action="follow-room">${room.is_following ? 'Takipte' : 'Takip Et'}</button>
        <button class="icon-btn icon-btn-glass" data-action="more" aria-label="Menü">${icon('more', 20)}</button>
      </header>

      <div class="room-pills">
        <span class="pill pill-glass">🔥 Saatlik Sıralama ${room.hourly_rank}.</span>
        <button class="pill pill-glass" data-action="announcement">📢 Duyuru</button>
        <button class="chest-pill" id="chest" data-action="chest" aria-label="Hazine sandığı" hidden></button>
        <button class="room-audience" data-action="members" aria-label="Odadakiler">
          <span class="avatar-stack">${audience.map((s) => avatarImg(s.user, 'avatar-xs')).join('')}</span>
          <span class="pill pill-glass" id="audience-more">+${Math.max(0, room.listener_count - audience.length)}</span>
        </button>
      </div>

      <div class="seat-grid" id="seats"></div>

      <div class="room-stream">
        <div class="room-chat" id="chat"></div>
        <div class="gift-feed" id="gift-feed"></div>
      </div>

      <form class="room-bar" id="room-bar">
        <div class="room-input">
          <input name="text" placeholder="Mesaj yaz..." autocomplete="off" maxlength="200" />
          <button type="button" data-action="emoji" aria-label="Emoji">${icon('smile', 20)}</button>
        </div>
        <button type="button" class="icon-btn icon-btn-glass" id="mic-btn" data-action="toggle-mic" aria-label="Mikrofon" hidden></button>
        <button type="button" class="icon-btn icon-btn-gift" data-action="gift" aria-label="Hediye gönder">${icon('gift', 20)}</button>
        <button type="button" class="icon-btn icon-btn-game" data-action="game" aria-label="Oyun">${icon('gamepad', 20)}</button>
      </form>

      <div class="gift-stage" id="gift-stage"></div>
    </div>`;

  const seatsEl = root.querySelector('#seats');
  const chatEl = root.querySelector('#chat');
  const giftFeedEl = root.querySelector('#gift-feed');
  const giftStageEl = root.querySelector('#gift-stage');
  const micBtn = root.querySelector('#mic-btn');

  // ─── KOLTUKLAR ─────────────────────────────────────────────────────────────
  function renderSeats() {
    seatsEl.innerHTML = room.seats.map((seat) => {
      if (seat.is_locked) {
        return `<button class="seat is-locked" data-seat="${seat.index}"><span class="seat-circle">${icon('lock', 22)}</span><b>${seat.index + 1}. Koltuk</b></button>`;
      }
      if (!seat.user) {
        return `<button class="seat is-empty" data-seat="${seat.index}"><span class="seat-circle">${icon('plus', 22)}</span><b>Otur</b></button>`;
      }
      const role = roleOf(seat.user.id);
      const isHost = role === 'host';
      const isSpeaking = speakingIndexes.includes(seat.index) && !seat.is_muted;
      return `
        <button class="seat ${isSpeaking ? 'is-speaking' : ''} ${isHost ? 'is-host' : ''}" data-seat="${seat.index}">
          <span class="seat-circle ${seat.user.frame ? `has-frame ${esc(seat.user.frame)}` : ''}">
            ${isHost ? '<i class="seat-crown">👑</i>' : ''}
            ${avatarImg(seat.user)}
            <i class="seat-mic ${seat.is_muted ? 'is-muted' : ''} ${seat.is_mic_blocked ? 'is-blocked' : ''}" title="${seat.is_mic_blocked ? 'Mikrofonu yönetici kapattı' : ''}">${icon(seat.is_mic_blocked ? 'lock' : seat.is_muted ? 'mic-off' : 'mic', 12)}</i>
          </span>
          <b>${esc(seat.user.display_name)}</b>
          ${ROLE_LABELS[role] ? `<small class="seat-role seat-role-${role}">${ROLE_LABELS[role]}</small>` : ''}
        </button>`;
    }).join('');

    const seat = mySeat();
    micBtn.hidden = !seat;
    if (seat) {
      micBtn.innerHTML = icon(seat.is_muted ? 'mic-off' : 'mic', 20);
      micBtn.classList.toggle('is-muted', seat.is_muted);
    }
  }

  function updateRoom(nextRoom) {
    room = nextRoom;
    channel.room = nextRoom;
    renderSeats();
    voice?.update(room.seats);
  }

  // Konuşan kişilerin koltuğunda halka yanar (ses şiddetini tarayıcı ölçer, bkz. js/voice/speaking.js)
  function setSpeaking(seatIndexes) {
    speakingIndexes = seatIndexes;
    seatsEl.querySelectorAll('.seat').forEach((el) => {
      const seat = room.seats[Number(el.dataset.seat)];
      el.classList.toggle('is-speaking', Boolean(seat.user) && !seat.is_muted && seatIndexes.includes(seat.index));
    });
  }

  joinVoice({
    room, me, channel,
    onSpeaking: (userIds) => setSpeaking(room.seats.filter((s) => userIds.has(s.user_id)).map((s) => s.index)),
    onError: (message) => toast(message, 'error'),
  }).then((client) => {
    if (isDisposed) return client?.close();
    voice = client;
    voice?.update(room.seats);
  }).catch(() => toast('Sese bağlanılamadı; sohbet yine çalışıyor.', 'error'));

  // ─── SOHBET ────────────────────────────────────────────────────────────────
  function addChatLine(html) {
    // Kullanıcı yukarı kaydırıp eski mesajları okuyorsa akışı zorla aşağı çekme
    const nearBottom = chatEl.scrollHeight - chatEl.scrollTop - chatEl.clientHeight < 80;
    chatEl.insertAdjacentHTML('beforeend', html);
    while (chatEl.children.length > MAX_CHAT_LINES) {
      chatMessages.delete(chatEl.firstElementChild.dataset.messageId);
      chatEl.firstElementChild.remove();
    }
    if (nearBottom) chatEl.scrollTop = chatEl.scrollHeight;
  }

  function addMessage(message) {
    const { id, user, text } = message;
    // Yeniden bağlanınca gelen `chat:history` zaten ekrandaki mesajları da içerir
    if (chatMessages.has(id)) return;
    chatMessages.set(id, message);
    const role = roleOf(user.id);
    addChatLine(`
      <div class="chat-line" data-message-id="${esc(id)}">
        ${framedAvatar(user, 'avatar-sm')}
        <div><b>${esc(user.display_name)}${ROLE_LABELS[role] ? ` <span class="mini-role mini-role-${role}">${ROLE_LABELS[role]}</span>` : ''}${user.vip_level ? ` <span class="mini-vip">VIP${user.vip_level}</span>` : ''}${user.family ? ` <span class="family-chip">${esc(user.family.badge)}</span>` : ''}</b><p class="${user.chat_bubble ? `chat-bubble ${esc(user.chat_bubble)}` : ''}">${esc(text)}</p></div>
      </div>`);
  }

  function removeMessage(messageId) {
    chatMessages.delete(messageId);
    chatEl.querySelector(`[data-message-id="${CSS.escape(messageId)}"]`)?.remove();
  }

  const addSystemLine = (html) => addChatLine(`<div class="chat-line chat-system">${html}</div>`);

  const addDiceLine = ({ user, values }) => addSystemLine(`🎲 <b>${esc(user.display_name)}</b> zar attı: ${values.map((v) => DICE_FACES[v - 1]).join(' ')} (toplam ${values[0] + values[1]})`);

  // ─── HEDİYE ────────────────────────────────────────────────────────────────
  // Aynı kişi aynı hediyeyi aynı kişiye art arda gönderirse tek satırda "kombo" olarak sayılır
  let combo = null;
  // Büyük (tam ekran) animasyonlar üst üste binmesin diye sıraya alınır
  const bigGiftQueue = [];
  let isPlayingBigGift = false;

  function showGift({ sender, receiver, gift, quantity, lucky_win: luckyWin = 0, lucky_multiplier: luckyMultiplier = 0 }) {
    addSystemLine(`<b>${esc(sender.display_name)}</b>, <b>${esc(receiver.display_name)}</b> kişisine ${gift.emoji} ${esc(gift.name)} x${quantity} gönderdi`);
    if (luckyWin) {
      addSystemLine(`🍀 <b>${esc(sender.display_name)}</b> şanslı hediyeden <b>x${luckyMultiplier}</b> yakaladı: <b>+${formatCoins(luckyWin)}</b> coin`);
      if (luckyMultiplier >= LUCKY_BIG_MULTIPLIER) playLuckyBanner(sender, luckyMultiplier, luckyWin);
    }

    const total = gift.price * quantity;
    addToGiftFeed({ sender, receiver, gift, quantity });
    if (total >= GIFT_BIG_FROM) {
      bigGiftQueue.push({ sender, receiver, gift, quantity });
      playNextBigGift();
    } else if (total >= GIFT_MEDIUM_FROM) {
      playMediumGift({ sender, receiver, gift, quantity });
    } else {
      playSmallGift(gift);
    }
  }

  function addToGiftFeed({ sender, receiver, gift, quantity }) {
    const key = `${sender.id}:${receiver.id}:${gift.id}`;
    if (combo && combo.key === key && combo.el.isConnected) {
      combo.count += quantity;
      combo.el.querySelector('b').textContent = `x${combo.count}`;
      combo.el.classList.remove('is-combo');
      void combo.el.offsetWidth;   // animasyonu baştan oynatmak için tarayıcıya yeniden hesaplatıyoruz
      combo.el.classList.add('is-combo');
    } else {
      const el = document.createElement('div');
      el.className = 'gift-feed-item';
      el.innerHTML = `<i>${gift.emoji}</i><b>x${quantity}</b>`;
      giftFeedEl.prepend(el);
      while (giftFeedEl.children.length > 4) giftFeedEl.lastElementChild.remove();
      combo = { key, count: quantity, el };
    }
    clearTimeout(combo.timer);
    combo.timer = setTimeout(() => { combo = null; }, GIFT_COMBO_MS);
  }

  // Küçük hediye: sağ alttan yukarı süzülen birkaç emoji
  function playSmallGift(gift) {
    for (let i = 0; i < 3; i += 1) {
      const el = document.createElement('i');
      el.className = 'gift-float';
      el.textContent = gift.emoji;
      el.style.setProperty('--drift', `${Math.round(Math.random() * 60 - 30)}px`);
      el.style.animationDelay = `${i * 140}ms`;
      giftStageEl.appendChild(el);
      setTimeout(() => el.remove(), 2200 + i * 140);
    }
  }

  // Orta hediye: ekranın ortasında patlayan emoji ve isim şeridi
  function playMediumGift({ sender, receiver, gift, quantity }) {
    const burst = document.createElement('div');
    burst.className = 'gift-burst';
    burst.innerHTML = `<i>${gift.emoji}</i><span>${esc(sender.display_name)} → ${esc(receiver.display_name)} <b>x${quantity}</b></span>`;
    giftStageEl.appendChild(burst);
    setTimeout(() => burst.remove(), 2400);
  }

  // Büyük hediye: tam ekran parıltı, konfeti ve üstten kayan duyuru şeridi
  function playNextBigGift() {
    if (isPlayingBigGift || !bigGiftQueue.length) return;
    isPlayingBigGift = true;
    const { sender, receiver, gift, quantity } = bigGiftQueue.shift();

    const confetti = Array.from({ length: 28 }, () => {
      const color = CONFETTI_COLORS[Math.floor(Math.random() * CONFETTI_COLORS.length)];
      return `<span style="left:${Math.round(Math.random() * 100)}%;background:${color};animation-delay:${Math.round(Math.random() * 600)}ms;--spin:${Math.round(Math.random() * 720 - 360)}deg"></span>`;
    }).join('');
    const show = document.createElement('div');
    show.className = 'gift-fullscreen';
    show.innerHTML = `
      <div class="gift-fullscreen-glow"></div>
      <div class="gift-confetti">${confetti}</div>
      <div class="gift-banner">🎉 <b>${esc(sender.display_name)}</b> → <b>${esc(receiver.display_name)}</b> ${esc(gift.name)} x${quantity}</div>
      <i class="gift-fullscreen-emoji">${gift.emoji}</i>`;
    giftStageEl.appendChild(show);
    setTimeout(() => {
      show.remove();
      isPlayingBigGift = false;
      playNextBigGift();
    }, 3400);
  }

  // Şanslı hediyede büyük çarpan: odadaki herkese üstten kayan altın duyuru
  function playLuckyBanner(sender, multiplier, coins) {
    const banner = document.createElement('div');
    banner.className = 'lucky-banner';
    banner.innerHTML = `🍀 <b>${esc(sender.display_name)}</b> x${multiplier} kazandı! <b>+${formatCoins(coins)}</b>`;
    giftStageEl.appendChild(banner);
    setTimeout(() => banner.remove(), 3600);
  }

  // ─── GİRİŞ EFEKTİ ──────────────────────────────────────────────────────────
  // Mağazadan ya da VIP'ten giriş efekti olan kişi odaya girince ekranın ortasından süzülen şerit
  const entryQueue = [];
  let isPlayingEntry = false;

  function playNextEntry() {
    if (isPlayingEntry || !entryQueue.length) return;
    isPlayingEntry = true;
    const user = entryQueue.shift();
    const effect = user.entry_effect;
    const el = document.createElement('div');
    el.className = `entry-effect ${esc(effect.style)}`;
    el.innerHTML = `<i>${effect.emoji}</i>${framedAvatar(user, 'avatar-sm')}<span><b>${esc(user.display_name)}</b> odaya giriş yaptı</span>`;
    giftStageEl.appendChild(el);
    setTimeout(() => {
      el.remove();
      isPlayingEntry = false;
      playNextEntry();
    }, ENTRY_EFFECT_MS);
  }

  function onUserJoined({ user }) {
    addSystemLine(`<b>${esc(user.display_name)}</b> odaya katıldı 👋`);
    if (user.entry_effect) {
      entryQueue.push(user);
      playNextEntry();
    }
  }

  // ─── HAZİNE SANDIĞI ────────────────────────────────────────────────────────
  // Odadaki hediyeler sandığı doldurur; dolunca herkes bir kez kapar. Miktarı sunucu belirler.
  const chestEl = root.querySelector('#chest');
  let chest = null;
  let chestTimer = null;
  // Bu sandıktan aldık mı? (yayın herkese aynı gider; kişiye özel bilgiyi burada tutuyoruz)
  let claimedChestId = null;

  function renderChest() {
    if (!chest) return;
    chestEl.hidden = false;
    clearInterval(chestTimer);
    const isOpen = chest.status === 'open';
    chestEl.classList.toggle('is-open', isOpen && claimedChestId !== chest.chest_id);
    if (!isOpen) {
      const percent = Math.min(100, Math.floor((chest.progress / chest.target) * 100));
      chestEl.innerHTML = `🎁 <span class="chest-bar"><i style="width:${percent}%"></i></span><small>%${percent}</small>`;
      return;
    }
    const tick = () => {
      const seconds = Math.max(0, Math.ceil((new Date(chest.ends_at) - Date.now()) / 1000));
      chestEl.innerHTML = claimedChestId === chest.chest_id
        ? `🎁 <small>Aldın · ${seconds} sn</small>`
        : `🎁 <b>Kap!</b> <small>${seconds} sn</small>`;
    };
    tick();
    chestTimer = setInterval(tick, 1000);
  }

  function updateChest(next) {
    // Sandık bilgisi ekrandan çıktıktan sonra gelirse zamanlayıcı başlatma
    if (isDisposed) return;
    if (next.status === 'open' && chest?.status !== 'open') {
      addSystemLine(`🎁 Hazine sandığı açıldı! İçinde <b>${formatCoins(next.coins_left)}</b> coin var, hemen kap!`);
    }
    if (next.claimed_by_me) claimedChestId = next.chest_id;
    chest = next;
    renderChest();
  }

  async function claimChest() {
    if (!chest) return;
    if (chest.status !== 'open') {
      return toast(`Odada hediye gönderildikçe sandık dolar: ${formatCoins(chest.progress)} / ${formatCoins(chest.target)} coin`);
    }
    if (claimedChestId === chest.chest_id) return toast('Bu sandıktan zaten aldın.');
    try {
      const result = await api.claimChest(room.id);
      claimedChestId = chest.chest_id;
      me.coin_balance = result.coin_balance;
      renderChest();
      toast(`🎁 Sandıktan ${formatCoins(result.coins)} coin kaptın!`, 'success');
    } catch (error) {
      if (error.code === 'chest_already_claimed') claimedChestId = chest.chest_id;
      renderChest();
      toast(error.message, 'error');
    }
  }

  api.getChest(room.id).then(updateChest).catch(() => {});

  function openGiftSheet(preselectedReceiverId) {
    const receivers = room.seats.filter((s) => s.user && s.user.id !== me.id).map((s) => s.user);
    if (!receivers.length) return toast('Koltukta hediye gönderebileceğin kimse yok.');
    let receiverId = preselectedReceiverId || receivers[0].id;
    let giftId = gifts[0].id;
    let quantity = 1;

    const sheet = openSheet(`
      <div class="gift-sheet-head">
        <h2 class="sheet-title">Hediye Gönder</h2>
        <a class="coin-pill" href="#/wallet"><span class="coin"></span><b id="gift-balance">${formatCoins(me.coin_balance)}</b><span class="coin-plus">+</span></a>
      </div>
      <div class="receiver-row" id="receivers">
        ${receivers.map((u) => `<button class="receiver ${u.id === receiverId ? 'is-active' : ''}" data-receiver="${u.id}">${avatarImg(u, 'avatar-md')}<small>${esc(u.display_name)}</small></button>`).join('')}
      </div>
      <div class="gift-grid" id="gift-grid">
        ${gifts.map((g) => `
          <button class="gift-item ${g.id === giftId ? 'is-active' : ''}" data-gift="${g.id}">
            ${g.is_lucky ? '<span class="lucky-tag">Şanslı</span>' : ''}<i>${g.emoji}</i><b>${esc(g.name)}</b><small><span class="coin coin-sm"></span>${formatCoins(g.price)}</small>
          </button>`).join('')}
      </div>
      <div class="gift-sheet-foot">
        <div class="quantity" id="quantities">
          ${QUANTITIES.map((q) => `<button class="${q === quantity ? 'is-active' : ''}" data-quantity="${q}">x${q}</button>`).join('')}
        </div>
        <button class="btn btn-primary" id="gift-send">Gönder</button>
      </div>`, { className: 'sheet-dark' });

    const select = (selector, attr, value) => sheet.el.querySelectorAll(selector).forEach((el) => el.classList.toggle('is-active', el.dataset[attr] === String(value)));

    sheet.el.addEventListener('click', async (event) => {
      const receiver = event.target.closest('[data-receiver]');
      const giftBtn = event.target.closest('[data-gift]');
      const quantityBtn = event.target.closest('[data-quantity]');
      if (receiver) { receiverId = Number(receiver.dataset.receiver); select('[data-receiver]', 'receiver', receiverId); }
      if (giftBtn) { giftId = Number(giftBtn.dataset.gift); select('[data-gift]', 'gift', giftId); }
      if (quantityBtn) { quantity = Number(quantityBtn.dataset.quantity); select('[data-quantity]', 'quantity', quantity); }

      if (event.target.closest('#gift-send')) {
        try {
          const result = await api.sendGift({ room_id: room.id, receiver_id: receiverId, gift_id: giftId, quantity });
          me.coin_balance = result.coin_balance;
          sheet.el.querySelector('#gift-balance').textContent = formatCoins(result.coin_balance);
          // Animasyonu odaya sunucu yayınlar; bu satır yalnızca mock'ta bir şey yapar
          channel.simulateServerEvent('gift:sent', {
            sender: me, receiver: result.receiver, gift: result.gift, quantity,
            lucky_win: result.lucky_win, lucky_multiplier: result.lucky_multiplier,
          });
          if (result.lucky_win) toast(`🍀 x${result.lucky_multiplier} yakaladın! +${formatCoins(result.lucky_win)} coin`, 'success');
          // Büyük hediyede panel kapanır ki tam ekran animasyon görünsün
          if (result.gift.price * quantity >= GIFT_BIG_FROM) sheet.close();
        } catch (error) {
          toast(error.code === 'insufficient_balance' ? 'Coin bakiyen yetersiz. Cüzdandan coin alabilirsin.' : error.message, 'error');
        }
      }
    });
  }

  // ─── OYUN ──────────────────────────────────────────────────────────────────
  function openGameSheet() {
    const sheet = openSheet(`
      <h2 class="sheet-title">Oda Oyunları</h2>
      <div class="segmented game-tabs">
        <button class="is-active" data-game-tab="roulette">🎡 Rulet</button>
        <button data-game-tab="dice">🎲 Zar</button>
      </div>
      <div id="game-panel"></div>`, { className: 'sheet-dark' });

    const panel = sheet.el.querySelector('#game-panel');
    let unmount = null;
    const showTab = (tab) => {
      unmount?.();
      sheet.el.querySelectorAll('[data-game-tab]').forEach((b) => b.classList.toggle('is-active', b.dataset.gameTab === tab));
      unmount = tab === 'roulette' ? mountRoulette(panel) : mountDice(panel);
    };
    sheet.el.querySelector('.game-tabs').addEventListener('click', (event) => {
      const tab = event.target.closest('[data-game-tab]');
      if (tab) showTab(tab.dataset.gameTab);
    });
    showTab('roulette');

    // Panel kapanınca (arka plana dokunma) zamanlayıcıları durdur
    const observer = new MutationObserver(() => {
      if (!sheet.el.isConnected) {
        unmount?.();
        observer.disconnect();
      }
    });
    observer.observe(document.getElementById('overlay-root'), { childList: true });
  }

  // Rulet: turu sunucu yönetir; biz yalnızca "başlat" ve "renk seç" gönderip gelen olayları çizeriz
  function mountRoulette(panel) {
    function render() {
      const active = roulette.roundId !== null;
      const secondsLeft = Math.max(0, Math.ceil((roulette.endsAt - Date.now()) / 1000));
      const myBet = roulette.bets.get(me.id)?.color;
      const last = roulette.last;
      const status = active
        ? (secondsLeft > 0 ? `Renk seç: <b>${secondsLeft} sn</b>` : 'Top dönüyor...')
        : last
          ? `Son tur: <b class="roulette-text-${last.color}">${last.number} ${COLOR_LABELS[last.color]}</b> · ${last.winners.length ? `${last.winners.length} kişi kazandı` : 'kimse bilemedi'}`
          : 'Turu başlat, odadaki herkes 10 saniye içinde renk seçsin.';

      panel.innerHTML = `
        <div class="roulette">
          <div class="roulette-wheel ${active ? 'is-spinning' : ''}">
            <span class="roulette-number ${last && !active ? `roulette-bg-${last.color}` : ''}">${active ? '?' : last ? last.number : '🎡'}</span>
          </div>
          <p class="roulette-status">${status}</p>
          ${active ? `
            <div class="roulette-colors">
              ${ROULETTE_COLORS.map((c) => `
                <button class="roulette-color roulette-bg-${c.id} ${myBet === c.id ? 'is-active' : ''}" data-color="${c.id}" ${secondsLeft > 0 ? '' : 'disabled'}>
                  <b>${c.label}</b><small>${c.hint}</small>
                </button>`).join('')}
            </div>
            <div class="roulette-bets">
              ${[...roulette.bets.values()].map(({ user, color }) => `<span class="roulette-bet roulette-ring-${color}" title="${esc(user.display_name)}">${avatarImg(user, 'avatar-xs')}</span>`).join('')
                || '<small>Henüz kimse seçmedi</small>'}
            </div>`
          : '<button class="btn btn-primary btn-block" data-roulette="start">Turu Başlat</button>'}
        </div>`;
    }

    const onClick = (event) => {
      if (event.target.closest('[data-roulette="start"]')) channel.send('game:roulette_start', {});
      const color = event.target.closest('[data-color]')?.dataset.color;
      if (color) channel.send('game:roulette_bet', { color });
    };
    panel.addEventListener('click', onClick);
    rouletteView = { render };
    render();
    const ticker = setInterval(() => { if (roulette.roundId !== null) render(); }, 500);

    return () => {
      clearInterval(ticker);
      panel.removeEventListener('click', onClick);
      rouletteView = null;
    };
  }

  function mountDice(panel) {
    panel.innerHTML = `
      <div class="dice-game">
        <div class="dice" id="dice"><span>🎲</span><span>🎲</span></div>
        <p id="dice-result">Zarı at, sonucu tüm oda görsün.</p>
        <button class="btn btn-primary btn-block" id="dice-roll">Zar At</button>
      </div>`;

    const diceEl = panel.querySelector('#dice');
    const resultEl = panel.querySelector('#dice-result');
    const rollBtn = panel.querySelector('#dice-roll');

    // Zarı sunucu atar (istemci atsaydı hile yapılabilirdi). Biz yalnızca istek
    // gönderir, sonucu `game:dice_rolled` event'i gelince gösteririz.
    rollBtn.addEventListener('click', () => {
      const startedAt = Date.now();
      rollBtn.disabled = true;
      diceEl.classList.add('is-rolling');

      const finish = () => {
        pendingDiceRoll = null;
        clearTimeout(giveUpTimer);
        diceEl.classList.remove('is-rolling');
        // Sunucu 1.5 saniyede bir zara izin verir; buton o süre dolunca açılır
        setTimeout(() => { rollBtn.disabled = false; }, Math.max(0, DICE_COOLDOWN_MS - (Date.now() - startedAt)));
      };
      const giveUpTimer = setTimeout(() => {
        finish();
        resultEl.textContent = 'Sonuç gelmedi, tekrar dene.';
      }, 4000);

      pendingDiceRoll = (roll) => {
        // Sonuç hemen gelse bile dönme animasyonu bitene kadar bekle
        pendingDiceRoll = null;
        setTimeout(() => {
          finish();
          const [a, b] = roll.values;
          diceEl.innerHTML = roll.values.map((v) => `<span>${DICE_FACES[v - 1]}</span>`).join('');
          resultEl.textContent = `Toplam ${a + b}${a === b ? ' — çift attın!' : ''}`;
          addDiceLine(roll);
        }, Math.max(0, DICE_SPIN_MS - (Date.now() - startedAt)));
      };
      channel.send('game:dice_rolled', {});
    });
    return () => { pendingDiceRoll = null; };
  }

  // ─── KOLTUK / KULLANICI PANELLERİ ──────────────────────────────────────────
  // Kişi paneli. Koltuktan, dinleyici listesinden ya da sohbetten açılır.
  // Yönetim düğmeleri yalnızca yetkimiz olan işlemler için görünür (asıl kontrol sunucuda).
  function openUserSheet(user) {
    const role = roleOf(user.id);
    const amHost = roleOf(me.id) === 'host';
    const seat = room.seats.find((s) => s.user?.id === user.id);
    const seatIndex = seat ? seat.index : null;
    const canAct = canModerate(user.id);
    const actions = [
      isModerator() && user.id !== me.id && seatIndex == null && ['invite', 'mic', 'Koltuğa davet et'],
      canAct && seatIndex != null && ['remove-seat', 'chevron-down', 'Koltuktan indir'],
      canAct && (seat?.is_mic_blocked
        ? ['mic-unblock', 'mic', 'Mikrofon engelini kaldır']
        : ['mic-block', 'mic-off', 'Mikrofonunu kapat']),
      canAct && (isChatMuted(user.id)
        ? ['chat-unmute', 'chat', 'Sohbet susturmasını kaldır']
        : ['chat-mute', 'chat', 'Sohbette sustur']),
      canAct && role !== 'admin' && (role === 'vip' ? ['vip-off', 'crown', "VIP'liğini al"] : ['vip-on', 'crown', 'VIP yap']),
      canAct && amHost && (role === 'admin' ? ['admin-off', 'crown', 'Yöneticilikten al'] : ['admin-on', 'crown', 'Yönetici yap']),
      canAct && ['kick', 'logout', 'Odadan at', 'is-danger'],
    ].filter(Boolean);
    const moderation = actions.length ? `
        <div class="menu-list mod-list">
          ${actions.map(([id, iconName, label, cls = '']) => `<button data-mod="${id}" class="${cls}">${icon(iconName, 20)} ${label}</button>`).join('')}
        </div>` : '';
    const sheet = openSheet(`
      <div class="user-sheet">
        ${avatarImg(user, 'avatar-xl')}
        <h2>${esc(user.display_name)}</h2>
        <div class="profile-badges">${ROLE_LABELS[role] ? `<span class="badge badge-role">${ROLE_LABELS[role]}</span>` : ''}${vipBadge(user.vip_level)}${levelBadge(user.level)}</div>
        <p>${esc(user.bio)}</p>
        ${user.id === me.id ? '' : `
        <div class="user-sheet-actions">
          <a class="btn btn-soft" href="#/profile/${user.id}">Profil</a>
          <button class="btn btn-soft" data-user-action="follow">${user.is_following ? 'Takiptesin' : 'Takip Et'}</button>
          <button class="btn btn-primary" data-user-action="gift">${icon('gift', 16)} Hediye</button>
        </div>`}
      </div>
      ${moderation}`, { className: 'sheet-dark' });

    // Her işlem: sunucuya isteği at, gelen oda durumunu uygula, başarı mesajı göster
    const MOD_ACTIONS = {
      invite: [() => api.inviteToSeat(room.id, user.id), 'Koltuğa davet gönderildi'],
      'remove-seat': [() => api.removeFromSeat(room.id, seatIndex), 'Koltuktan indirildi'],
      'mic-block': [() => api.setMicBlocked(room.id, user.id, true), 'Mikrofonu kapatıldı'],
      'mic-unblock': [() => api.setMicBlocked(room.id, user.id, false), 'Mikrofon engeli kaldırıldı'],
      'chat-unmute': [() => api.setChatMute(room.id, user.id, null), 'Susturma kaldırıldı'],
      'vip-on': [() => api.setRoomRole(room.id, user.id, 'vip'), 'VIP yapıldı'],
      'vip-off': [() => api.setRoomRole(room.id, user.id, 'listener'), "VIP'lik alındı"],
      'admin-on': [() => api.setRoomRole(room.id, user.id, 'admin'), 'Yönetici yapıldı'],
      'admin-off': [() => api.setRoomRole(room.id, user.id, 'listener'), 'Yöneticilik alındı'],
      kick: [() => api.kickFromRoom(room.id, user.id), 'Odadan çıkarıldı'],
    };
    sheet.el.addEventListener('click', async (event) => {
      const mod = event.target.closest('[data-mod]')?.dataset.mod;
      if (mod) {
        sheet.close();
        if (mod === 'chat-mute') return openChatMuteSheet(user);
        const [run, done] = MOD_ACTIONS[mod];
        try {
          const result = await run();
          if (result?.seats) updateRoom(result);
          toast(done, 'success');
        } catch (error) {
          toast(error.message, 'error');
        }
        return;
      }
      const action = event.target.closest('[data-user-action]')?.dataset.userAction;
      if (action === 'gift') {
        sheet.close();
        openGiftSheet(user.id);
      } else if (action === 'follow') {
        const { is_following } = await api.toggleFollow(user.id);
        user.is_following = is_following;
        event.target.closest('button').textContent = is_following ? 'Takiptesin' : 'Takip Et';
      }
    });
  }

  function openChatMuteSheet(user) {
    const sheet = openSheet(`
      <h2 class="sheet-title">${esc(user.display_name)} ne kadar sussun?</h2>
      <div class="menu-list">
        ${CHAT_MUTE_OPTIONS.map((o) => `<button data-minutes="${o.minutes}">${icon('chat', 20)} ${o.label}</button>`).join('')}
      </div>`, { className: 'sheet-dark' });
    sheet.el.addEventListener('click', async (event) => {
      const minutes = Number(event.target.closest('[data-minutes]')?.dataset.minutes);
      if (!minutes) return;
      sheet.close();
      try {
        await api.setChatMute(room.id, user.id, minutes);
        toast('Sohbette susturuldu', 'success');
      } catch (error) {
        toast(error.message, 'error');
      }
    });
  }

  // Dinleyici listesi: odada şu an bulunan herkes. Birine dokununca kişi paneli açılır.
  async function openMembersSheet() {
    const sheet = openSheet(`
      <h2 class="sheet-title">Odadakiler</h2>
      <div class="member-list" id="member-list"><p class="member-empty">Yükleniyor...</p></div>`, { className: 'sheet-dark' });
    const listEl = sheet.el.querySelector('#member-list');
    let members;
    try {
      members = await api.listRoomMembers(room.id);
    } catch (error) {
      listEl.innerHTML = `<p class="member-empty">${esc(error.message)}</p>`;
      return;
    }
    members.forEach((m) => {
      if (m.chat_muted_seconds) chatMutedUntil.set(m.user.id, Date.now() + m.chat_muted_seconds * 1000);
    });
    listEl.innerHTML = members.length ? members.map((m) => `
      <button class="member-row" data-member="${m.user.id}">
        ${avatarImg(m.user, 'avatar-md')}
        <span class="member-info">
          <b>${esc(m.user.display_name)}${m.user.id === me.id ? ' (sen)' : ''}</b>
          <small>${joinParts([
            m.seat_index != null ? `${m.seat_index + 1}. koltuk` : 'Dinleyici',
            m.is_mic_blocked && '🔇 mikrofonu kapalı',
            m.chat_muted_seconds && '💬 susturuldu',
          ])}</small>
        </span>
        ${ROLE_LABELS[m.role] ? `<span class="seat-role seat-role-${m.role}">${ROLE_LABELS[m.role]}</span>` : ''}
      </button>`).join('')
      : '<p class="member-empty">Odada şu an kimse yok.</p>';
    listEl.addEventListener('click', (event) => {
      const id = Number(event.target.closest('[data-member]')?.dataset.member);
      const member = members.find((m) => m.user.id === id);
      if (!member) return;
      sheet.close();
      openUserSheet(member.user);
    });
  }

  // Sohbetteki bir mesaja dokununca: kendi mesajını ya da (yöneticiysek) başkasınınkini silme
  function openMessageSheet(message) {
    const isMine = message.user.id === me.id;
    const canDelete = isMine || canModerate(message.user.id);
    if (!canDelete) return openUserSheet(message.user);
    const sheet = openSheet(`
      <p class="message-preview"><b>${esc(message.user.display_name)}:</b> ${esc(message.text)}</p>
      <div class="menu-list">
        ${canDelete ? `<button data-menu="delete" class="is-danger">${icon('close', 20)} Mesajı sil</button>` : ''}
        ${isMine ? '' : `<button data-menu="user">${icon('user', 20)} ${esc(message.user.display_name)}</button>`}
      </div>`, { className: 'sheet-dark' });
    sheet.el.addEventListener('click', async (event) => {
      const item = event.target.closest('[data-menu]')?.dataset.menu;
      if (!item) return;
      sheet.close();
      if (item === 'user') return openUserSheet(message.user);
      try {
        await api.deleteChatMessage(room.id, message.id);
        // Mock'ta sunucu yayını yok; gerçek backend'de `chat:message_deleted` herkese gelir
        removeMessage(message.id);
      } catch (error) {
        toast(error.message, 'error');
      }
    });
  }

  // Yönetici koltuğa davet etti: ilk boş koltuğa oturmayı teklif et
  function openSeatInviteSheet({ by, expires_in: expiresIn }) {
    const sheet = openSheet(`
      <div class="user-sheet">
        ${avatarImg(by, 'avatar-xl')}
        <h2>Koltuğa davet</h2>
        <p><b>${esc(by.display_name)}</b> seni mikrofona davet ediyor.</p>
        <div class="invite-actions">
          <button class="btn btn-soft" data-close>Şimdi değil</button>
          <button class="btn btn-primary" data-invite="accept">${icon('mic', 16)} Koltuğa otur</button>
        </div>
      </div>`, { className: 'sheet-dark' });
    const expireTimer = setTimeout(() => sheet.close(), expiresIn * 1000);
    sheet.el.addEventListener('click', async (event) => {
      if (!event.target.closest('[data-invite]')) return;
      clearTimeout(expireTimer);
      sheet.close();
      const seat = room.seats.find((s) => !s.user && !s.is_locked);
      if (!seat) return toast('Boş koltuk kalmadı.', 'error');
      try {
        updateRoom(await api.takeSeat(room.id, seat.index));
        toast('Koltuğa oturdun.', 'success');
      } catch (error) {
        toast(error.message, 'error');
      }
    });
  }

  // Oda ayarları (oda sahibi ve yöneticiler): ad, kategori, duyuru, kapak, koltuk kuralı
  async function openRoomSettingsSheet() {
    const { covers } = await api.getMediaOptions();
    let coverUrl = room.cover_url;
    const sheet = openSheet(`
      <h2 class="sheet-title">Oda Ayarları</h2>
      <form id="room-settings-form">
        <label class="field">
          <span>Oda adı</span>
          <input name="title" maxlength="60" value="${esc(room.title)}" required />
        </label>
        <label class="field">
          <span>Duyuru</span>
          <textarea name="announcement" maxlength="300" rows="3">${esc(room.announcement)}</textarea>
        </label>
        <div class="field">
          <span>Kategori</span>
          <div class="chips chips-wrap" data-picker="category">
            ${Object.entries(CATEGORY_LABELS).map(([id, label]) => `<button type="button" class="chip ${id === room.category ? 'is-active' : ''}" data-category="${id}">${label}</button>`).join('')}
          </div>
        </div>
        <div class="field">
          <span>Kapak</span>
          <div class="picker-row" data-picker="cover">
            ${covers.map((url) => `
              <button type="button" class="picker-cover ${url === coverUrl ? 'is-active' : ''}" data-url="${esc(url)}">
                <img src="${esc(url)}" alt="" loading="lazy" />
              </button>`).join('')}
          </div>
        </div>
        <label class="switch-row">
          <span><b>Koltuklar herkese açık</b><small>Kapalıysa yalnızca yönetici, VIP ve davet edilenler oturur.</small></span>
          <input type="checkbox" name="free_seating" ${room.free_seating ? 'checked' : ''} />
        </label>
        <button class="btn btn-primary btn-block" type="submit">Kaydet</button>
      </form>`, { className: 'sheet-dark' });

    let category = room.category;
    sheet.el.querySelector('[data-picker="category"]').addEventListener('click', (event) => {
      const chip = event.target.closest('[data-category]');
      if (!chip) return;
      category = chip.dataset.category;
      chip.parentElement.querySelectorAll('.chip').forEach((el) => el.classList.toggle('is-active', el === chip));
    });
    sheet.el.querySelector('[data-picker="cover"]').addEventListener('click', (event) => {
      const item = event.target.closest('[data-url]');
      if (!item) return;
      coverUrl = item.dataset.url;
      item.parentElement.querySelectorAll('[data-url]').forEach((el) => el.classList.toggle('is-active', el === item));
    });

    const form = sheet.el.querySelector('#room-settings-form');
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const data = new FormData(form);
      const next = {
        title: data.get('title').trim(),
        announcement: data.get('announcement').trim(),
        category,
        cover_url: coverUrl,
        free_seating: data.get('free_seating') === 'on',
      };
      // Yalnızca değişen alanları gönder (PATCH)
      const changes = Object.fromEntries(Object.entries(next).filter(([key, value]) => value !== room[key]));
      if (!Object.keys(changes).length) return sheet.close();
      try {
        applyRoomSettings(await api.updateRoom(room.id, changes));
        sheet.close();
        toast('Oda ayarları kaydedildi', 'success');
      } catch (error) {
        toast(error.message, 'error');
      }
    });
  }

  function applyRoomSettings({ title, category, cover_url: coverUrl, announcement, free_seating: freeSeating }) {
    const announcementChanged = announcement !== room.announcement;
    Object.assign(room, { title, category, cover_url: coverUrl, announcement, free_seating: freeSeating });
    root.querySelector('#room-name').textContent = title;
    root.querySelector('#room-category').textContent = CATEGORY_LABELS[category];
    root.querySelectorAll('.room-bg, .room-thumb').forEach((img) => { img.src = coverUrl; });
    if (announcementChanged) addSystemLine(`📢 ${esc(announcement)}`);
  }

  function openCloseRoomSheet() {
    const sheet = openSheet(`
      <h2 class="sheet-title">Oda kapatılsın mı?</h2>
      <p class="sheet-text">İçerideki herkes odadan çıkarılır ve oda listelerden kalkar. Bu işlem geri alınamaz.</p>
      <div class="invite-actions">
        <button class="btn btn-soft" data-close>Vazgeç</button>
        <button class="btn btn-danger" data-confirm>Odayı kapat</button>
      </div>`, { className: 'sheet-dark' });
    sheet.el.addEventListener('click', async (event) => {
      if (!event.target.closest('[data-confirm]')) return;
      sheet.close();
      try {
        await api.closeRoom(room.id);
        leaveBecauseClosed();
      } catch (error) {
        toast(error.message, 'error');
      }
    });
  }

  function openSeatAdminSheet(seat) {
    const sheet = openSheet(`
      <h2 class="sheet-title">${seat.index + 1}. Koltuk</h2>
      <div class="menu-list">
        ${seat.is_locked
          ? `<button data-menu="unlock">${icon('lock', 20)} Kilidi aç</button>`
          : `<button data-menu="sit">${icon('mic', 20)} Koltuğa otur</button>
             <button data-menu="lock">${icon('lock', 20)} Koltuğu kilitle</button>`}
      </div>`, { className: 'sheet-dark' });
    sheet.el.addEventListener('click', async (event) => {
      const item = event.target.closest('[data-menu]');
      if (!item) return;
      sheet.close();
      try {
        if (item.dataset.menu === 'sit') updateRoom(await api.takeSeat(room.id, seat.index));
        else updateRoom(await api.setSeatLock(room.id, seat.index, item.dataset.menu === 'lock'));
      } catch (error) {
        toast(error.message, 'error');
      }
    });
  }

  function openMySeatSheet() {
    const seat = mySeat();
    const sheet = openSheet(`
      <div class="menu-list">
        <button data-menu="mute">${icon(seat.is_muted ? 'mic' : 'mic-off', 20)} ${seat.is_muted ? 'Mikrofonu aç' : 'Mikrofonu kapat'}</button>
        <button data-menu="leave-seat" class="is-danger">${icon('chevron-down', 20)} Koltuktan kalk</button>
      </div>`, { className: 'sheet-dark' });
    sheet.el.addEventListener('click', async (event) => {
      const item = event.target.closest('[data-menu]');
      if (!item) return;
      sheet.close();
      updateRoom(item.dataset.menu === 'mute' ? await api.toggleMute(room.id) : await api.leaveSeat(room.id));
    });
  }

  function openMoreSheet() {
    const sheet = openSheet(`
      <div class="menu-list">
        <button data-menu="share">${icon('share', 20)} Odayı paylaş</button>
        <button data-menu="announcement">${icon('bell', 20)} Oda duyurusu</button>
        <button data-menu="members">${icon('users', 20)} Odadakiler</button>
        ${isModerator() ? `<button data-menu="settings">${icon('edit', 20)} Oda ayarları</button>` : ''}
        ${roleOf(me.id) === 'host'
          ? `<button data-menu="close-room" class="is-danger">${icon('lock', 20)} Odayı kapat</button>`
          : `<button data-menu="report">${icon('close', 20)} Odayı şikâyet et</button>`}
        <button data-menu="leave" class="is-danger">${icon('logout', 20)} Odadan çık</button>
      </div>`, { className: 'sheet-dark' });
    sheet.el.addEventListener('click', (event) => {
      const item = event.target.closest('[data-menu]');
      if (!item) return;
      sheet.close();
      const { menu } = item.dataset;
      if (menu === 'leave') location.hash = '#/home';
      else if (menu === 'announcement') toast(room.announcement);
      else if (menu === 'members') openMembersSheet();
      else if (menu === 'settings') openRoomSettingsSheet();
      else if (menu === 'close-room') openCloseRoomSheet();
      else if (menu === 'report') openReportSheet('room', room.id, room.title);
      else toast('Oda bağlantısı kopyalandı');
    });
  }

  // ─── OLAYLAR ───────────────────────────────────────────────────────────────
  root.addEventListener('click', async (event) => {
    const seatBtn = event.target.closest('[data-seat]');
    if (seatBtn) {
      const seat = room.seats[Number(seatBtn.dataset.seat)];
      if (!seat.user && isModerator()) return openSeatAdminSheet(seat);
      if (seat.is_locked) return toast('Bu koltuk yönetici tarafından kilitlendi.');
      if (!seat.user) {
        try {
          updateRoom(await api.takeSeat(room.id, seat.index));
          toast('Koltuğa oturdun. Mikrofonun açık.', 'success');
        } catch (error) {
          toast(error.message, 'error');
        }
        return;
      }
      return seat.user.id === me.id ? openMySeatSheet() : openUserSheet(seat.user);
    }

    const chatLine = event.target.closest('[data-message-id]');
    if (chatLine) {
      const message = chatMessages.get(chatLine.dataset.messageId);
      if (message) openMessageSheet(message);
      return;
    }

    const button = event.target.closest('[data-action]');
    if (!button) return;
    const { action } = button.dataset;

    if (action === 'leave') location.hash = '#/home';
    else if (action === 'more') openMoreSheet();
    else if (action === 'gift') openGiftSheet();
    else if (action === 'game') openGameSheet();
    else if (action === 'members') openMembersSheet();
    else if (action === 'announcement') toast(room.announcement);
    else if (action === 'chest') claimChest();
    else if (action === 'toggle-mic') updateRoom(await api.toggleMute(room.id));
    else if (action === 'emoji') {
      const input = root.querySelector('#room-bar input');
      input.value += '😊';
      input.focus();
    } else if (action === 'follow-room') {
      button.disabled = true;
      try {
        const { is_following } = await api.toggleRoomFollow(room.id);
        room.is_following = is_following;
        button.textContent = is_following ? 'Takipte' : 'Takip Et';
        button.classList.toggle('btn-primary', !is_following);
        button.classList.toggle('btn-glass', is_following);
        toast(is_following ? 'Oda takip edildi' : 'Oda takipten çıkarıldı');
      } catch (error) {
        toast(error.message, 'error');
      } finally {
        button.disabled = false;
      }
    }
  });

  root.querySelector('#room-bar').addEventListener('submit', (event) => {
    event.preventDefault();
    const input = event.target.elements.text;
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    channel.send('chat:message', { text });
  });

  channel
    .on('chat:message', addMessage)
    .on('gift:sent', showGift)
    .on('room:user_joined', onUserJoined)
    .on('room:chest_updated', ({ chest: next }) => updateChest(next))
    .on('room:chest_claimed', ({ user, coins }) => {
      if (user.id !== me.id) addSystemLine(`🎁 <b>${esc(user.display_name)}</b> sandıktan ${formatCoins(coins)} coin kaptı`);
    })
    .on('game:dice_rolled', (roll) => {
      if (roll.user.id === me.id && pendingDiceRoll) pendingDiceRoll(roll);
      else addDiceLine(roll);
    })
    .on('room:seats_updated', ({ seats }) => {
      // Yayın herkese aynı gider, kişiye özel `is_following` içermez; bildiğimizi koruyoruz
      const known = new Map(room.seats.filter((s) => s.user).map((s) => [s.user.id, s.user]));
      updateRoom({
        ...room,
        seats: seats.map((s) => (s.user ? { ...s, user: { ...s.user, is_following: Boolean(known.get(s.user.id)?.is_following) } } : s)),
      });
    })
    .on('game:roulette_started', ({ round_id: roundId, started_by: startedBy, betting_seconds: seconds }) => {
      Object.assign(roulette, { roundId, endsAt: Date.now() + seconds * 1000, last: null });
      roulette.bets.clear();
      addSystemLine(`🎡 <b>${esc(startedBy.display_name)}</b> rulet turu başlattı, ${Math.round(seconds)} sn içinde renk seç! <button class="chat-join" data-action="game">Katıl</button>`);
      rouletteView?.render();
    })
    .on('game:roulette_bet_placed', ({ round_id: roundId, user, color }) => {
      if (roundId !== roulette.roundId) return;
      roulette.bets.set(user.id, { user, color });
      rouletteView?.render();
    })
    .on('game:roulette_result', (result) => {
      Object.assign(roulette, { roundId: null, last: result });
      const names = result.winners.map((w) => esc(w.display_name)).join(', ');
      addSystemLine(`🎡 Rulet: <b>${result.number} ${COLOR_LABELS[result.color]}</b> · ${names ? `Kazananlar: <b>${names}</b>` : 'kimse bilemedi'}`);
      if (result.winners.some((w) => w.id === me.id)) toast(`🎉 Rulette kazandın! ${result.number} ${COLOR_LABELS[result.color]}`, 'success');
      rouletteView?.render();
    })
    .on('room:roles_updated', ({ admin_ids, vip_ids }) => {
      updateRoom({ ...room, admin_ids, vip_ids });
    })
    .on('room:user_kicked', ({ user }) => {
      if (user.id === me.id) return leaveBecauseKicked();
      voice?.removePeer(user.id);
      addSystemLine(`<b>${esc(user.display_name)}</b> odadan çıkarıldı`);
    })
    .on('chat:history', ({ messages }) => messages.forEach(addMessage))
    .on('chat:message_deleted', ({ message_id: messageId }) => removeMessage(messageId))
    .on('room:chat_muted', ({ user, seconds }) => {
      if (seconds) chatMutedUntil.set(user.id, Date.now() + seconds * 1000);
      else chatMutedUntil.delete(user.id);
      if (user.id === me.id) toast(seconds ? `Sohbette ${Math.round(seconds / 60)} dakika susturuldun.` : 'Artık yazabilirsin.', seconds ? 'error' : 'success');
      else if (seconds) addSystemLine(`<b>${esc(user.display_name)}</b> sohbette susturuldu`);
    })
    .on('room:seat_invite', openSeatInviteSheet)
    .on('room:updated', applyRoomSettings)
    .on('room:closed', leaveBecauseClosed)
    .on('error', ({ code, detail }) => {
      if (code === 'room_banned') leaveBecauseKicked();
      else toast(detail, 'error');
    })
    .on('room:listener_count', ({ listener_count }) => {
      root.querySelector('#listener-count').textContent = listener_count;
      root.querySelector('#audience-more').textContent = `+${Math.max(0, listener_count - audience.length)}`;
    })
    .on('room:user_left', ({ user_id: userId }) => voice?.removePeer(userId))
    // Yalnızca mock: gerçek backend'de konuşanları js/voice/ hesaplar
    .on('room:speaking', ({ seat_indexes: seatIndexes }) => setSpeaking(seatIndexes));

  // Hem `room:user_kicked` hem bağlantının 4403 ile kapanması buraya gelir; bir kez çalışsın
  let kicked = false;
  function leaveBecauseKicked() {
    if (kicked) return;
    kicked = true;
    toast('Bu odadan çıkarıldın.', 'error');
    location.hash = '#/home';
  }

  // Oda sahibi odayı kapattı (ya da kapatan biziz)
  let closed = false;
  function leaveBecauseClosed() {
    if (closed) return;
    closed = true;
    toast('Oda kapatıldı.');
    location.hash = '#/home';
  }

  renderSeats();
  addSystemLine(`📢 ${esc(room.announcement)}`);

  return () => {
    isDisposed = true;
    clearInterval(chestTimer);
    voice?.close();
    channel.close();
  };
}
