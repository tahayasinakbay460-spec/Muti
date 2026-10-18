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

export async function renderRoom(root, { params }) {
  let [room, me, gifts] = await Promise.all([api.getRoom(params[0]), api.getMe(), api.listGifts()]);
  let speakingIndexes = [];
  // Zar atıp sonucunu bekliyorsak, sonuç gelince çağrılacak fonksiyon
  let pendingDiceRoll = null;
  const channel = connectRoom(room, me);

  const mySeat = () => room.seats.find((s) => s.user?.id === me.id);
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
        <button class="btn btn-primary btn-sm" data-action="follow-room">Takip Et</button>
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
      const isHost = seat.user.id === room.host_id;
      const isSpeaking = speakingIndexes.includes(seat.index) && !seat.is_muted;
      return `
        <button class="seat ${isSpeaking ? 'is-speaking' : ''} ${isHost ? 'is-host' : ''}" data-seat="${seat.index}">
          <span class="seat-circle">
            ${isHost ? '<i class="seat-crown">👑</i>' : ''}
            ${avatarImg(seat.user)}
            <i class="seat-mic ${seat.is_muted ? 'is-muted' : ''}">${icon(seat.is_muted ? 'mic-off' : 'mic', 12)}</i>
          </span>
          <b>${esc(seat.user.display_name)}</b>
          ${isHost ? '<small class="seat-role">Yönetici</small>' : ''}
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
  function showGift({ sender, receiver, gift, quantity }) {
    addSystemLine(`<b>${esc(sender.display_name)}</b>, <b>${esc(receiver.display_name)}</b> kişisine ${gift.emoji} ${esc(gift.name)} x${quantity} gönderdi`);

    const feedItem = document.createElement('div');
    feedItem.className = 'gift-feed-item';
    feedItem.innerHTML = `<i>${gift.emoji}</i><b>x${quantity}</b>`;
    giftFeedEl.prepend(feedItem);
    while (giftFeedEl.children.length > 4) giftFeedEl.lastElementChild.remove();

    const burst = document.createElement('div');
    burst.className = `gift-burst ${gift.price >= 999 ? 'is-big' : ''}`;
    burst.innerHTML = `<i>${gift.emoji}</i><span>${esc(sender.display_name)} → ${esc(receiver.display_name)} <b>x${quantity}</b></span>`;
    giftStageEl.appendChild(burst);
    setTimeout(() => burst.remove(), 2400);
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
          if (result.gift.price >= 999) sheet.close();
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
      <div class="dice-game">
        <div class="dice" id="dice"><span>🎲</span><span>🎲</span></div>
        <p id="dice-result">Zarı at, sonucu tüm oda görsün.</p>
        <button class="btn btn-primary btn-block" id="dice-roll">Zar At</button>
      </div>
      <div class="game-list">
        <div class="game-tile"><i>🎡</i><b>Şans Çarkı</b><small>Yakında</small></div>
        <div class="game-tile"><i>🀄</i><b>Okey</b><small>Yakında</small></div>
        <div class="game-tile"><i>🎯</i><b>Ludo</b><small>Yakında</small></div>
        <div class="game-tile"><i>🃏</i><b>Pişti</b><small>Yakında</small></div>
      </div>`, { className: 'sheet-dark' });

    const diceEl = sheet.el.querySelector('#dice');
    const resultEl = sheet.el.querySelector('#dice-result');
    const rollBtn = sheet.el.querySelector('#dice-roll');

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
  }

  // ─── KOLTUK / KULLANICI PANELLERİ ──────────────────────────────────────────
  function openUserSheet(user) {
    const sheet = openSheet(`
      <div class="user-sheet">
        ${avatarImg(user, 'avatar-xl')}
        <h2>${esc(user.display_name)}</h2>
        <div class="profile-badges">${vipBadge(user.vip_level)}${levelBadge(user.level)}</div>
        <p>${esc(user.bio)}</p>
        <div class="user-sheet-actions">
          <a class="btn btn-soft" href="#/profile/${user.id}">Profil</a>
          <button class="btn btn-soft" data-user-action="follow">${user.is_following ? 'Takiptesin' : 'Takip Et'}</button>
          <button class="btn btn-primary" data-user-action="gift">${icon('gift', 16)} Hediye</button>
        </div>
      </div>`, { className: 'sheet-dark' });

    sheet.el.addEventListener('click', async (event) => {
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
      const following = button.classList.toggle('is-following');
      button.textContent = following ? 'Takipte' : 'Takip Et';
      button.classList.toggle('btn-primary', !following);
      button.classList.toggle('btn-glass', following);
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
    .on('error', ({ detail }) => toast(detail, 'error'))
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

  renderSeats();
  addSystemLine(`📢 ${esc(room.announcement)}`);

  return () => channel.close();
}
