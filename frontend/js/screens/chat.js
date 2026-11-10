// Birebir sohbet ekranı (#/chat/:id).
//   Üst: geri · kişi · 📞 sesli arama · 🎥 görüntülü arama · ⋯
//   Orta: mesajlar. Her balonun altında saat; araya gün değişince ya da uzun boşlukta tarih çizgisi girer
//         ("Bugün 17:22", "Dün 09:10", "07.11 17:22"). Türler: yazı, sesli mesaj, hediye, arama izi.
//   Alt: [🎁] [ Bir şey söyle… ] [🎤 / ➤] — kutu boşken mikrofon, yazınca gönder tuşu (WhatsApp gibi).
import { api } from '../api.js';
import { startOutgoingCall } from '../call.js';
import { onInbox, setOpenConversation, refreshUnread } from '../inbox.js';
import { clock, duration, needsSeparator, separatorLabel } from '../chat-format.js';
import { esc, icon, avatarImg, toast } from '../ui.js';
import { choosePhoto } from '../photo-upload.js';
import { openGiftSheet } from './gift-sheet.js';

const VOICE_MAX_SECONDS = 60;
const CALL_LABELS = { voice: 'Sesli arama', video: 'Görüntülü arama' };

function bubbleBody(m) {
  if (m.kind === 'image') {
    // Fotoğraf token ister: önce yer tutucu çizilir, dosya api ile çekilip yerleştirilir (loadPhotos)
    return `<button class="chat-photo" data-photo="${esc(m.media_url)}" aria-label="Fotoğrafı aç"><span class="spinner"></span></button>`;
  }
  if (m.kind === 'voice') {
    return `
      <button class="voice-note" data-voice="${esc(m.media_url)}" aria-label="Sesli mesajı çal">
        <i class="voice-note-icon">${icon('play', 16)}</i>
        <span class="voice-note-bars"><span class="voice-note-progress"></span></span>
        <small>${duration(m.duration_seconds || 0)}</small>
      </button>`;
  }
  if (m.kind === 'gift' && m.gift) {
    return `<div class="gift-note"><i>${m.gift.emoji}</i><span><b>${esc(m.gift.name)}</b><small>x${m.quantity} · hediye ${m.from_me ? 'gönderdin' : 'gönderdi'}</small></span></div>`;
  }
  return `<p>${esc(m.text)}</p>`;
}

function messageHtml(m) {
  const time = clock(new Date(m.created_at));
  if (m.kind === 'call') {
    const label = CALL_LABELS[m.call_kind] || 'Arama';
    let text = `${label} · ${duration(m.duration_seconds || 0)}`;
    if (m.call_status === 'missed') text = `Cevapsız ${label.toLowerCase()}`;
    else if (m.call_status === 'declined') text = `${label} reddedildi`;
    return `<div class="call-note ${m.call_status !== 'ended' ? 'is-missed' : ''}" ${m.id ? `data-id="${m.id}"` : ''}>${icon(m.call_kind === 'video' ? 'video' : 'phone', 14)} ${esc(text)} <small>${time}</small></div>`;
  }
  // data-id: aynı mesaj hem POST cevabı hem de kanal üzerinden (diğer sekmeler için) gelebilir; iki kez basılmasın
  return `
    <div class="bubble bubble-${m.kind} ${m.from_me ? 'is-mine' : ''}" ${m.id ? `data-id="${m.id}"` : ''}>
      ${bubbleBody(m)}
      <small class="bubble-time">${time}</small>
    </div>`;
}

export async function renderChat(root, { params, query = {} }) {
  const conversation = await api.getConversation(params[0]);
  const { user } = conversation;
  let lastAt = null;   // ekrandaki son mesajın zamanı (tarih çizgisi için)

  const withSeparator = (m) => {
    const at = new Date(m.created_at);
    const separator = needsSeparator(lastAt, at) ? `<div class="chat-date">${separatorLabel(at)}</div>` : '';
    lastAt = at;
    return separator + messageHtml(m);
  };

  root.innerHTML = `
    <div class="chat-screen">
      <header class="topbar topbar-solid">
        <a class="icon-btn" href="#/messages" data-back aria-label="Geri">${icon('chevron-left', 22)}</a>
        <a class="chat-peer" href="#/profile/${user.id}">
          ${avatarImg(user, 'avatar-sm')}
          <span><b>${esc(user.display_name)}</b><small>${user.is_online ? 'Çevrimiçi' : 'Çevrimdışı'}</small></span>
        </a>
        <button class="icon-btn icon-btn-plain" data-action="call-voice" aria-label="Sesli ara">${icon('phone', 21)}</button>
        <button class="icon-btn icon-btn-plain" data-action="call-video" aria-label="Görüntülü ara">${icon('video', 22)}</button>
        <button class="icon-btn icon-btn-plain" data-action="chat-menu" aria-label="Seçenekler">${icon('more', 20)}</button>
      </header>
      <div class="chat-thread" id="thread">${conversation.messages.map(withSeparator).join('') || '<p class="chat-empty">İlk mesajı sen yaz 👋</p>'}</div>
      <form class="chat-composer" id="composer">
        <button type="button" class="chat-composer-btn chat-composer-gift" data-action="gift" aria-label="Hediye gönder">🎁</button>
        <button type="button" class="chat-composer-btn chat-composer-photo" data-action="photo" aria-label="Fotoğraf gönder">${icon('image', 19)}</button>
        <input name="text" placeholder="Bir şey söyle…" autocomplete="off" maxlength="300" value="${esc(query.draft || '')}" />
        <button type="button" class="chat-composer-btn" data-action="record" aria-label="Sesli mesaj">${icon('mic', 20)}</button>
        <button type="submit" class="chat-composer-btn chat-composer-send" aria-label="Gönder" hidden>${icon('send', 18)}</button>
      </form>
      <div class="chat-recorder" id="recorder" hidden>
        <button type="button" class="chat-composer-btn" data-action="record-cancel" aria-label="Vazgeç">${icon('trash', 19)}</button>
        <span class="chat-recorder-dot"></span>
        <b id="record-time">0:00</b>
        <small>Kaydediliyor… en fazla ${VOICE_MAX_SECONDS} sn</small>
        <button type="button" class="chat-composer-btn chat-composer-send" data-action="record-send" aria-label="Gönder">${icon('send', 18)}</button>
      </div>
    </div>`;

  const thread = root.querySelector('#thread');
  const form = root.querySelector('#composer');
  const input = form.elements.text;
  const micButton = form.querySelector('[data-action="record"]');
  const sendButton = form.querySelector('.chat-composer-send');
  const scrollDown = () => { thread.scrollTop = thread.scrollHeight; };
  scrollDown();

  // Fotoğraflar ve sesli mesajlar token ister; bir kez indirilip tarayıcı içi adresle (blob:) gösterilir
  const mediaUrls = new Map();
  const mediaBlobUrl = async (source) => {
    if (!mediaUrls.has(source)) mediaUrls.set(source, URL.createObjectURL(await api.getMessageMedia(source)));
    return mediaUrls.get(source);
  };
  async function loadPhotos() {
    for (const holder of thread.querySelectorAll('[data-photo]:not([data-loaded])')) {
      holder.dataset.loaded = '1';
      try {
        holder.innerHTML = `<img src="${await mediaBlobUrl(holder.dataset.photo)}" alt="Fotoğraf" />`;
      } catch {
        holder.textContent = 'Fotoğraf açılamadı';
      }
    }
  }
  loadPhotos();

  const appendMessage = (message) => {
    if (message.id && thread.querySelector(`[data-id="${message.id}"]`)) return;
    thread.querySelector('.chat-empty')?.remove();
    thread.insertAdjacentHTML('beforeend', withSeparator(message));
    scrollDown();
    if (message.kind === 'image') loadPhotos().then(scrollDown);
  };

  // Yazı varken gönder, yokken mikrofon tuşu görünür
  const syncButtons = () => {
    const hasText = Boolean(input.value.trim());
    sendButton.hidden = !hasText;
    micButton.hidden = hasText;
  };
  input.addEventListener('input', syncButtons);
  syncButtons();   // hazır yazı (?draft=) geldiyse gönder tuşu görünsün

  // Fotoğraf: profil/anı ile aynı akış (izin paneli → galeri/kamera → küçült), sonra mesaj olarak gider.
  // Gönderilirken tuş kilitlenir: iki kez basılıp aynı fotoğraf iki kez gitmesin.
  async function sendPhoto(button) {
    if (button?.disabled) return;
    try {
      const blob = await choosePhoto('chat');
      if (!blob) return;
      if (button) button.disabled = true;
      appendMessage(await api.sendConversationImage(conversation.id, blob));
    } catch (error) {
      toast(error.message, 'error');
    } finally {
      if (button) button.disabled = false;
    }
  }

  // Fotoğrafa dokununca tam ekran
  function openPhoto(src) {
    const viewer = document.createElement('div');
    viewer.className = 'photo-viewer';
    viewer.innerHTML = `<img src="${src}" alt="Fotoğraf" /><button aria-label="Kapat">${icon('close', 22)}</button>`;
    viewer.addEventListener('click', () => viewer.remove());
    document.querySelector('.device').appendChild(viewer);
  }

  // Bu sohbet açıkken gelen mesaj anında görünür ve okundu sayılır (bildirim çıkmaz)
  setOpenConversation(conversation.id);
  refreshUnread();
  const stopListening = onInbox('message:new', ({ conversation_id: conversationId, message }) => {
    if (conversationId !== conversation.id) return;
    appendMessage(message);
    if (!message.from_me) api.markConversationRead(conversation.id).catch(() => {});
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    syncButtons();
    try {
      // Karşı tarafın cevabı kişiye özel kanaldan (`message:new`) gelir
      appendMessage(await api.sendMessage(conversation.id, text));
    } catch (error) {
      input.value = text;
      syncButtons();
      toast(error.message, 'error');
    }
  });

  // ── Hediye ──
  let gifts = null;
  async function openGifts() {
    try {
      const [list, me] = await Promise.all([gifts || api.listGifts(), api.getMe()]);
      gifts = list;
      openGiftSheet({
        gifts, balance: me.coin_balance, receivers: [user],
        async send({ giftId, quantity }) {
          const result = await api.sendConversationGift(conversation.id, giftId, quantity);
          if (result.message) appendMessage(result.message);
          return { ...result, closeSheet: true };
        },
      });
    } catch (error) {
      toast(error.message, 'error');
    }
  }

  // ── Sesli mesaj kaydı ──
  // Dokun: kayıt başlar; gönder tuşu: biter ve gider; çöp kutusu: vazgeç. 60 sn dolunca kendiliğinden gider.
  const recorderBar = root.querySelector('#recorder');
  let recording = null;   // { recorder, stream, chunks, startedAt, timer, cancelled }

  async function startRecording() {
    if (recording) return;
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      toast('Bu tarayıcı ses kaydını desteklemiyor.', 'error');
      return;
    }
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    } catch {
      toast('Mikrofon izni verilmedi.', 'error');
      return;
    }
    // Sunucunun kabul ettiği türlerden tarayıcının desteklediği ilki (Safari mp4 üretir)
    const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4']
      .find((type) => MediaRecorder.isTypeSupported?.(type));
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    recording = { recorder, stream, chunks: [], startedAt: Date.now(), cancelled: false };
    recorder.addEventListener('dataavailable', (event) => { if (event.data.size) recording?.chunks.push(event.data); });
    recorder.addEventListener('stop', finishRecording);
    recorder.start();
    form.hidden = true;
    recorderBar.hidden = false;
    const timeEl = recorderBar.querySelector('#record-time');
    recording.timer = setInterval(() => {
      const seconds = Math.floor((Date.now() - recording.startedAt) / 1000);
      timeEl.textContent = duration(seconds);
      if (seconds >= VOICE_MAX_SECONDS) stopRecording(false);
    }, 250);
  }

  function stopRecording(cancel) {
    if (!recording || recording.recorder.state === 'inactive') return;
    recording.cancelled = cancel;
    recording.recorder.stop();
  }

  async function finishRecording() {
    const { stream, chunks, startedAt, timer, cancelled, recorder } = recording;
    recording = null;
    clearInterval(timer);
    stream.getTracks().forEach((track) => track.stop());
    recorderBar.hidden = true;
    form.hidden = false;
    const seconds = Math.min(VOICE_MAX_SECONDS, Math.round((Date.now() - startedAt) / 1000));
    if (cancelled) return;
    if (seconds < 1) { toast('Kayıt çok kısa.'); return; }
    const blob = new Blob(chunks, { type: (recorder.mimeType || 'audio/webm').split(';')[0] });
    try {
      appendMessage(await api.sendVoiceMessage(conversation.id, blob, seconds));
    } catch (error) {
      toast(error.message, 'error');
    }
  }

  // ── Sesli mesaj çalma ──
  let playing = null;   // { audio, button }

  async function toggleVoice(button) {
    if (playing?.button === button) {
      if (playing.audio.paused) playing.audio.play(); else playing.audio.pause();
      return;
    }
    playing?.audio.pause();
    const source = button.dataset.voice;
    let url;
    try {
      url = await mediaBlobUrl(source);
    } catch (error) {
      toast(error.message, 'error');
      return;
    }
    const audio = new Audio(url);
    const iconEl = button.querySelector('.voice-note-icon');
    const progress = button.querySelector('.voice-note-progress');
    audio.addEventListener('play', () => { iconEl.innerHTML = icon('pause', 16); });
    audio.addEventListener('pause', () => { iconEl.innerHTML = icon('play', 16); });
    audio.addEventListener('timeupdate', () => {
      if (Number.isFinite(audio.duration)) progress.style.width = `${(audio.currentTime / audio.duration) * 100}%`;
    });
    audio.addEventListener('ended', () => { progress.style.width = '0%'; playing = null; });
    playing = { audio, button };
    audio.play().catch(() => toast('Ses çalınamadı.', 'error'));
  }

  root.addEventListener('click', (event) => {
    const action = event.target.closest('[data-action]')?.dataset.action;
    const voice = event.target.closest('[data-voice]');
    const photo = event.target.closest('[data-photo] img');
    if (voice) toggleVoice(voice);
    else if (photo) openPhoto(photo.src);
    else if (action === 'photo') sendPhoto(event.target.closest('[data-action]'));
    else if (action === 'chat-menu') import('./messages.js').then(({ openPeerMenu }) => openPeerMenu(user));
    else if (action === 'call-voice') startOutgoingCall(user, 'voice');
    else if (action === 'call-video') startOutgoingCall(user, 'video');
    else if (action === 'gift') openGifts();
    else if (action === 'record') startRecording();
    else if (action === 'record-send') stopRecording(false);
    else if (action === 'record-cancel') stopRecording(true);
  });

  return () => {
    stopListening();
    setOpenConversation(null);
    stopRecording(true);
    playing?.audio.pause();
    mediaUrls.forEach((url) => URL.revokeObjectURL(url));
  };
}
