// Sesli oda: koltuklar, canlı sohbet, hediye paneli ve oda içi oyun
import { api } from '../api.js';
import { connectRoom } from '../realtime.js';
import { CATEGORY_LABELS } from '../config.js';
import { esc, icon, avatarImg, formatCoins, vipBadge, levelBadge, toast, openSheet } from '../ui.js';

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

export async function renderRoom(root, { params }) {
  let [room, me, gifts] = await Promise.all([api.getRoom(params[0]), api.getMe(), api.listGifts()]);
  let speakingIndexes = [];
  // Zar atıp sonucunu bekliyorsak, sonuç gelince çağrılacak fonksiyon
  let pendingDiceRoll = null;
  // Odadaki rulet turunun durumu (panel kapalıyken de güncel tutulur; panel açılınca buradan çizilir)
  const roulette = { roundId: null, endsAt: 0, bets: new Map(), last: null };
  let rouletteView = null;   // rulet paneli açıkken { render } nesnesi
  const channel = connectRoom(room, me);

  const mySeat = () => room.seats.find((s) => s.user?.id === me.id);

  // Roller: oda sahibi > yönetici > dinleyici. Asıl yetki kontrolü sunucuda; burada yalnızca
  // hangi düğmelerin gösterileceğine karar veriyoruz.
  const RANK = { host: 3, admin: 2, listener: 1 };
  const roleOf = (userId) => (userId === room.host_id ? 'host' : room.admin_ids.includes(userId) ? 'admin' : 'listener');
  const isModerator = () => roleOf(me.id) !== 'listener';
  const canModerate = (userId) => userId !== me.id && RANK[roleOf(me.id)] > RANK[roleOf(userId)];
  const audience = room.seats.filter((s) => s.user).slice(0, 3);

  root.innerHTML = `
    <div class="room">
      <img class="room-bg" src="${esc(room.cover_url)}" alt="" />
      <header class="room-header">
        <button class="icon-btn icon-btn-glass" data-action="leave" aria-label="Odadan çık">${icon('chevron-down', 22)}</button>
        <img class="room-thumb" src="${esc(room.cover_url)}" alt="" />
        <div class="room-title">
          <h1>${esc(room.title)}</h1>
          <p>ID ${room.id} • <span id="listener-count">${room.listener_count}</span> kişi • ${CATEGORY_LABELS[room.category]}</p>
        </div>
        <button class="btn btn-sm ${room.is_following ? 'btn-glass' : 'btn-primary'}" data-action="follow-room">${room.is_following ? 'Takipte' : 'Takip Et'}</button>
        <button class="icon-btn icon-btn-glass" data-action="more" aria-label="Menü">${icon('more', 20)}</button>
      </header>

      <div class="room-pills">
        <span class="pill pill-glass">🔥 Saatlik Sıralama ${room.hourly_rank}.</span>
        <button class="pill pill-glass" data-action="announcement">📢 Duyuru</button>
        <span class="room-audience">
          <span class="avatar-stack">${audience.map((s) => avatarImg(s.user, 'avatar-xs')).join('')}</span>
          <span class="pill pill-glass" id="audience-more">+${Math.max(0, room.listener_count - audience.length)}</span>
        </span>
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
          <span class="seat-circle">
            ${isHost ? '<i class="seat-crown">👑</i>' : ''}
            ${avatarImg(seat.user)}
            <i class="seat-mic ${seat.is_muted ? 'is-muted' : ''}">${icon(seat.is_muted ? 'mic-off' : 'mic', 12)}</i>
          </span>
          <b>${esc(seat.user.display_name)}</b>
          ${isHost ? '<small class="seat-role">Oda Sahibi</small>' : ''}
          ${role === 'admin' ? '<small class="seat-role seat-role-admin">Yönetici</small>' : ''}
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
  }

  // ─── SOHBET ────────────────────────────────────────────────────────────────
  function addChatLine(html) {
    // Kullanıcı yukarı kaydırıp eski mesajları okuyorsa akışı zorla aşağı çekme
    const nearBottom = chatEl.scrollHeight - chatEl.scrollTop - chatEl.clientHeight < 80;
    chatEl.insertAdjacentHTML('beforeend', html);
    while (chatEl.children.length > MAX_CHAT_LINES) chatEl.firstElementChild.remove();
    if (nearBottom) chatEl.scrollTop = chatEl.scrollHeight;
  }

  const addMessage = ({ user, text }) => addChatLine(`
    <div class="chat-line">
      ${avatarImg(user, 'avatar-sm')}
      <div><b>${esc(user.display_name)}${user.vip_level ? ` <span class="mini-vip">VIP${user.vip_level}</span>` : ''}</b><p>${esc(text)}</p></div>
    </div>`);

  const addSystemLine = (html) => addChatLine(`<div class="chat-line chat-system">${html}</div>`);

  const addDiceLine = ({ user, values }) => addSystemLine(`🎲 <b>${esc(user.display_name)}</b> zar attı: ${values.map((v) => DICE_FACES[v - 1]).join(' ')} (toplam ${values[0] + values[1]})`);

  // ─── HEDİYE ────────────────────────────────────────────────────────────────
  // Aynı kişi aynı hediyeyi aynı kişiye art arda gönderirse tek satırda "kombo" olarak sayılır
  let combo = null;
  // Büyük (tam ekran) animasyonlar üst üste binmesin diye sıraya alınır
  const bigGiftQueue = [];
  let isPlayingBigGift = false;

  function showGift({ sender, receiver, gift, quantity }) {
    addSystemLine(`<b>${esc(sender.display_name)}</b>, <b>${esc(receiver.display_name)}</b> kişisine ${gift.emoji} ${esc(gift.name)} x${quantity} gönderdi`);

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
            <i>${g.emoji}</i><b>${esc(g.name)}</b><small><span class="coin coin-sm"></span>${formatCoins(g.price)}</small>
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
          channel.simulateServerEvent('gift:sent', { sender: me, receiver: result.receiver, gift: result.gift, quantity });
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
  function openUserSheet(user, seatIndex) {
    const role = roleOf(user.id);
    const amHost = roleOf(me.id) === 'host';
    const moderation = canModerate(user.id) ? `
        <div class="menu-list mod-list">
          ${seatIndex != null ? `<button data-mod="remove-seat">${icon('chevron-down', 20)} Koltuktan indir</button>` : ''}
          ${amHost ? `<button data-mod="toggle-admin">${icon('crown', 20)} ${role === 'admin' ? 'Yöneticilikten al' : 'Yönetici yap'}</button>` : ''}
          <button data-mod="kick" class="is-danger">${icon('logout', 20)} Odadan at</button>
        </div>` : '';
    const sheet = openSheet(`
      <div class="user-sheet">
        ${avatarImg(user, 'avatar-xl')}
        <h2>${esc(user.display_name)}</h2>
        <div class="profile-badges">${{ host: '<span class="badge badge-role">Oda Sahibi</span>', admin: '<span class="badge badge-role">Yönetici</span>' }[role] || ''}${vipBadge(user.vip_level)}${levelBadge(user.level)}</div>
        <p>${esc(user.bio)}</p>
        <div class="user-sheet-actions">
          <a class="btn btn-soft" href="#/profile/${user.id}">Profil</a>
          <button class="btn btn-soft" data-user-action="follow">${user.is_following ? 'Takiptesin' : 'Takip Et'}</button>
          <button class="btn btn-primary" data-user-action="gift">${icon('gift', 16)} Hediye</button>
        </div>
      </div>
      ${moderation}`, { className: 'sheet-dark' });

    const MOD_DONE = {
      'remove-seat': 'Koltuktan indirildi',
      'toggle-admin': role === 'admin' ? 'Yöneticilik alındı' : 'Yönetici yapıldı',
      kick: 'Odadan çıkarıldı',
    };
    sheet.el.addEventListener('click', async (event) => {
      const mod = event.target.closest('[data-mod]')?.dataset.mod;
      if (mod) {
        sheet.close();
        try {
          if (mod === 'remove-seat') updateRoom(await api.removeFromSeat(room.id, seatIndex));
          else if (mod === 'toggle-admin') updateRoom(await api.setRoomAdmin(room.id, user.id, role !== 'admin'));
          else await api.kickFromRoom(room.id, user.id);
          toast(MOD_DONE[mod], 'success');
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
        <button data-menu="leave" class="is-danger">${icon('logout', 20)} Odadan çık</button>
      </div>`, { className: 'sheet-dark' });
    sheet.el.addEventListener('click', (event) => {
      const item = event.target.closest('[data-menu]');
      if (!item) return;
      sheet.close();
      if (item.dataset.menu === 'leave') location.hash = '#/home';
      else if (item.dataset.menu === 'announcement') toast(room.announcement);
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
      return seat.user.id === me.id ? openMySeatSheet() : openUserSheet(seat.user, seat.index);
    }

    const button = event.target.closest('[data-action]');
    if (!button) return;
    const { action } = button.dataset;

    if (action === 'leave') location.hash = '#/home';
    else if (action === 'more') openMoreSheet();
    else if (action === 'gift') openGiftSheet();
    else if (action === 'game') openGameSheet();
    else if (action === 'announcement') toast(room.announcement);
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
    .on('room:user_joined', ({ user }) => addSystemLine(`<b>${esc(user.display_name)}</b> odaya katıldı 👋`))
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
    .on('room:roles_updated', ({ admin_ids }) => {
      updateRoom({ ...room, admin_ids });
    })
    .on('room:user_kicked', ({ user }) => {
      if (user.id === me.id) leaveBecauseKicked();
      else addSystemLine(`<b>${esc(user.display_name)}</b> odadan çıkarıldı`);
    })
    .on('error', ({ code, detail }) => {
      if (code === 'room_banned') leaveBecauseKicked();
      else toast(detail, 'error');
    })
    .on('room:listener_count', ({ listener_count }) => {
      root.querySelector('#listener-count').textContent = listener_count;
      root.querySelector('#audience-more').textContent = `+${Math.max(0, listener_count - audience.length)}`;
    })
    .on('room:speaking', ({ seat_indexes }) => {
      speakingIndexes = seat_indexes;
      seatsEl.querySelectorAll('.seat').forEach((el) => {
        const seat = room.seats[Number(el.dataset.seat)];
        el.classList.toggle('is-speaking', Boolean(seat.user) && !seat.is_muted && seat_indexes.includes(seat.index));
      });
    });

  // Hem `room:user_kicked` hem bağlantının 4403 ile kapanması buraya gelir; bir kez çalışsın
  let kicked = false;
  function leaveBecauseKicked() {
    if (kicked) return;
    kicked = true;
    toast('Bu odadan çıkarıldın.', 'error');
    location.hash = '#/home';
  }

  renderSeats();
  addSystemLine(`📢 ${esc(room.announcement)}`);

  return () => channel.close();
}
