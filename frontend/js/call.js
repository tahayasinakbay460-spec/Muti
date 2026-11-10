// Birebir sesli / görüntülü arama ekranı (özel mesajlardaki 📞 ve 🎥).
// Aynı anda tek arama olur. Tam ekran katman, sayfa değişse de kapanmaz (overlay-root'tan ayrı durur).
//
// Akış ve para kuralları sunucuda (backend services/call_service.py): arayan dakika başı öder, her dakika
// peşin kesilir, coin bitince arama kapanır. Bu dosya yalnızca gösterir ve kullanıcının dokunuşlarını iletir.
// Olaylar kişiye özel kanaldan gelir: call:incoming, call:accepted, call:charged, call:ended, call:signal.
import { api } from './api.js';
import { onInbox, sendInbox } from './inbox.js';
import { esc, icon, avatarImg, formatCoins, toast, openSheet } from './ui.js';

const KIND_LABELS = { voice: 'Sesli arama', video: 'Görüntülü arama' };
const END_MESSAGES = {
  hangup: 'Görüşme bitti.',
  declined: 'Arama reddedildi.',
  missed: 'Cevap yok.',
  cancelled: 'Arama iptal edildi.',
  insufficient_balance: 'Coin bittiği için görüşme kapandı.',
  disconnected: 'Bağlantı koptuğu için görüşme kapandı.',
};

let current = null;   // { call, layer, media, unsubscribers, timer, connectedAt }

// ── Başlatma ──────────────────────────────────────────────────────────────────

// Sohbet ekranındaki 📞 / 🎥: önce fiyatı gösterir, onaylanınca arar
export async function startOutgoingCall(peer, kind) {
  if (current) return toast('Zaten bir görüşmedesin.');
  let prices;
  let me;
  try {
    [prices, me] = await Promise.all([api.getCallPrices(), api.getMe()]);
  } catch (error) {
    return toast(error.message, 'error');
  }
  const price = kind === 'video' ? prices.video_per_minute : prices.voice_per_minute;
  const sheet = openSheet(`
    <div class="call-confirm">
      ${avatarImg(peer, 'avatar-xl')}
      <h2 class="sheet-title">${esc(peer.display_name)} · ${KIND_LABELS[kind]}</h2>
      <p>Dakikası <b><span class="coin coin-sm"></span> ${formatCoins(price)}</b>. Her dakikanın başında bakiyenden düşer; coin bitince görüşme kapanır.</p>
      <p class="muted">Bakiyen: ${formatCoins(me.coin_balance)} coin</p>
      <button class="btn btn-primary btn-block" data-call-confirm>${icon(kind === 'video' ? 'video' : 'phone', 18)} Ara</button>
      <button class="btn btn-ghost btn-block" data-close>Vazgeç</button>
    </div>`);
  sheet.el.querySelector('[data-call-confirm]').addEventListener('click', async () => {
    sheet.close();
    if (me.coin_balance < price) {
      toast('Coin bakiyen yetersiz. Cüzdandan coin alabilirsin.', 'error');
      return;
    }
    try {
      const call = await api.startCall(peer.id, kind);
      openLayer(call);
    } catch (error) {
      toast(error.code === 'insufficient_balance' ? 'Coin bakiyen yetersiz. Cüzdandan coin alabilirsin.' : error.message, 'error');
    }
  });
}

// Kişiye özel kanaldan `call:incoming` geldi (inbox.js çağırır)
export function showIncomingCall(call) {
  if (current) return;   // sunucu zaten izin vermez; yine de iki katman açılmasın
  openLayer(call);
  navigator.vibrate?.([400, 200, 400, 200, 400]);
}

// ── Katman ────────────────────────────────────────────────────────────────────

function openLayer(call) {
  const layer = document.createElement('div');
  layer.className = `call-layer call-${call.kind}`;
  document.querySelector('.device').appendChild(layer);
  current = { call, layer, media: null, unsubscribers: [], timer: null, connectedAt: null };

  current.unsubscribers.push(
    onInbox('call:accepted', ({ call: updated, voice }) => {
      if (!isCurrent(updated.id)) return;
      current.call = updated;
      connectMedia(voice);
    }),
    onInbox('call:charged', (payload) => {
      if (!isCurrent(payload.call_id)) return;
      paintCharge(payload);
    }),
    onInbox('call:ended', ({ call_id: id, reason }) => {
      if (!isCurrent(id)) return;
      finish(END_MESSAGES[reason] || 'Görüşme bitti.');
    }),
  );
  paint();
  layer.addEventListener('click', onLayerClick);
}

const isCurrent = (id) => current && current.call.id === id;

function paint() {
  const { call, layer } = current;
  const { peer } = call;
  const ringing = call.status === 'ringing';
  const incoming = ringing && !call.is_caller;
  let status = 'Bağlanıyor…';
  if (incoming) status = `${KIND_LABELS[call.kind]} geliyor`;
  else if (ringing) status = 'Aranıyor…';
  layer.innerHTML = `
    <div class="call-remote" id="call-remote"></div>
    <div class="call-backdrop" style="background-image:url('${esc(peer.avatar_url || '')}')"></div>
    <div class="call-top">
      ${avatarImg(peer, 'avatar-xl call-avatar')}
      <h2>${esc(peer.display_name)}</h2>
      <p id="call-status">${status}</p>
      ${call.is_caller ? `<p class="call-cost" id="call-cost"><span class="coin coin-sm"></span> ${formatCoins(call.price_per_minute)} / dk</p>` : ''}
      <p class="call-warning" id="call-warning" hidden>Coin bitmek üzere. <a href="#/wallet">Coin yükle</a>, yoksa görüşme bir dakika içinde kapanır.</p>
    </div>
    <div class="call-local" id="call-local" ${call.kind === 'video' ? '' : 'hidden'}></div>
    <div class="call-actions">
      ${incoming ? `
        <button class="call-btn call-btn-decline" data-call="decline" aria-label="Reddet">${icon('phone', 26)}</button>
        <button class="call-btn call-btn-accept" data-call="accept" aria-label="Aç">${icon(call.kind === 'video' ? 'video' : 'phone', 26)}</button>` : `
        <button class="call-btn" data-call="mic" aria-label="Mikrofon">${icon('mic', 22)}</button>
        ${call.kind === 'video' ? `<button class="call-btn" data-call="camera" aria-label="Kamera">${icon('video', 22)}</button>` : ''}
        <button class="call-btn call-btn-decline" data-call="hangup" aria-label="Kapat">${icon('phone', 26)}</button>`}
    </div>`;
  // Ücret olayı ekran yeniden çizilmeden önce gelmiş olabilir (ilk dakika "açıldı"dan önce kesilir)
  if (current.charge) paintCharge(current.charge);
}

async function onLayerClick(event) {
  const button = event.target.closest('[data-call]');
  if (!button || !current) return;
  const { call } = current;
  const action = button.dataset.call;
  if (action === 'accept') {
    button.disabled = true;
    try {
      const voice = await api.acceptCall(call.id);
      current.call = { ...call, status: 'active' };
      paint();
      connectMedia(voice);
    } catch (error) {
      finish(error.message);
    }
  } else if (action === 'decline') {
    api.declineCall(call.id).catch(() => {});
    finish('');
  } else if (action === 'hangup') {
    // Sunucu iki tarafa `call:ended` yollar; cevap gelmese de ekran kapanır
    api.endCall(call.id).catch(() => {});
    finish(call.status === 'ringing' ? 'Arama iptal edildi.' : 'Görüşme bitti.');
  } else if (action === 'mic' || action === 'camera') {
    const off = button.classList.toggle('is-off');
    if (action === 'mic') current.media?.setMicEnabled(!off);
    else current.media?.setCameraEnabled(!off);
  }
}

async function connectMedia(info) {
  if (!current || current.media) return;
  const { call, layer } = current;
  current.call = { ...call, status: 'active' };
  if (call.is_caller) paint();   // "Aranıyor" yerine görüşme tuşları
  setStatus('Bağlanıyor…');
  try {
    const { connectCallMedia } = await import('./voice/call-media.js');
    const media = await connectCallMedia({
      info,
      me: { id: await myId() },
      isCaller: call.is_caller,
      video: call.kind === 'video',
      localEl: layer.querySelector('#call-local'),
      remoteEl: layer.querySelector('#call-remote'),
      refreshInfo: () => api.getCallJoin(call.id),
      sendSignal: (data) => sendInbox('call:signal', { call_id: call.id, ...data }),
      onSignal: (handler) => onInbox('call:signal', (signal) => { if (signal.call_id === call.id) handler(signal); }),
      onRemoteVideo: (hasVideo) => layer.classList.toggle('has-remote-video', hasVideo),
      onError: (message) => toast(message, 'error'),
    });
    if (!current || current.call.id !== call.id) { media.close(); return; }
    current.media = media;
    current.connectedAt = Date.now();
    current.timer = setInterval(paintElapsed, 1000);
    paintElapsed();
  } catch (error) {
    toast(error.message, 'error');
    api.endCall(call.id).catch(() => {});
    finish('');
  }
}

let cachedMyId = null;
async function myId() {
  cachedMyId ||= (await api.getMe()).id;
  return cachedMyId;
}

function setStatus(text) {
  const el = current?.layer.querySelector('#call-status');
  if (el) el.textContent = text;
}

function paintElapsed() {
  if (!current?.connectedAt) return;
  const seconds = Math.floor((Date.now() - current.connectedAt) / 1000);
  setStatus(`${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`);
}

function paintCharge({ coins_spent: spent, low_balance: low }) {
  current.charge = { coins_spent: spent, low_balance: low };
  const cost = current.layer.querySelector('#call-cost');
  if (cost) cost.innerHTML = `<span class="coin coin-sm"></span> ${formatCoins(spent)} harcandı · ${formatCoins(current.call.price_per_minute)} / dk`;
  current.layer.querySelector('#call-warning').hidden = !low;
}

function finish(message) {
  if (!current) return;
  const { layer, media, unsubscribers, timer } = current;
  current = null;
  clearInterval(timer);
  unsubscribers.forEach((off) => off());
  media?.close();
  layer.classList.add('is-leaving');
  setTimeout(() => layer.remove(), 250);
  if (message) toast(message);
}
