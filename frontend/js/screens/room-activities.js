// Oda içi etkinlikler: PK (takım hediye yarışı), birlikte izleme (YouTube), karaoke sırası ve
// iki kişilik oyun masaları (Dört Bağla, Taş-Kağıt-Makas). Oda ekranı (room.js) bu modülü bağlar.
// Durumun sahibi sunucu: burada yalnızca gelen olayları çiziyor ve istekleri gönderiyoruz.
import { api } from '../api.js';
import { esc, avatarImg, formatCoins, toast, openSheet } from '../ui.js';

const PK_MINUTES = [1, 3, 5, 10];
const TEAM_LABELS = { red: 'Kırmızı', blue: 'Mavi' };
const RPS = [
  { id: 'rock', emoji: '✊', label: 'Taş' },
  { id: 'paper', emoji: '✋', label: 'Kağıt' },
  { id: 'scissors', emoji: '✌️', label: 'Makas' },
];
const RPS_EMOJI = Object.fromEntries(RPS.map((r) => [r.id, r.emoji]));
const COLUMNS = 7;

// ─── YouTube oynatıcı ─────────────────────────────────────────────────────────
// YouTube'un resmi "IFrame Player API"si: videoyu durdurup belirli saniyeye götürebilmek için gerekli.
let youtubeReady = null;
function loadYouTubeApi() {
  youtubeReady ||= new Promise((resolve) => {
    window.onYouTubeIframeAPIReady = () => resolve(window.YT);
    const script = document.createElement('script');
    script.src = 'https://www.youtube.com/iframe_api';
    document.head.appendChild(script);
  });
  return youtubeReady;
}

// Videonun şu an hangi saniyede olması gerektiği. Sunucu ile tarayıcının saati farklı olabilir;
// sunucunun gönderdiği saat (server_time) ile aradaki farkı düzeltiyoruz.
function expectedPosition(media, clockOffsetMs) {
  if (media.paused || !media.started_at) return media.position;
  return (Date.now() + clockOffsetMs - new Date(media.started_at)) / 1000;
}

export function mountRoomActivities({ root, getRoom, me, channel, isModerator, addSystemLine }) {
  const room = () => getRoom();
  const state = { pk: null, media: null, karaoke: { singer: null, queue: [] }, duels: new Map() };
  const pkEl = root.querySelector('#pk-bar');
  const mediaEl = root.querySelector('#media-slot');
  let pkTimer = null;
  let pkHideTimer = null;
  let player = null;
  let playerVideoId = null;
  let clockOffsetMs = 0;
  let disposed = false;
  // Açık panel varsa (oyun masaları, etkinlikler) yeni olay gelince yeniden çizmek için
  let duelView = null;
  let activitiesView = null;

  // ─── PK ────────────────────────────────────────────────────────────────────
  function teamOfSeat(index) {
    if (!state.pk || state.pk.status !== 'running') return null;
    if (state.pk.red_seats.includes(index)) return 'red';
    return state.pk.blue_seats.includes(index) ? 'blue' : null;
  }

  function decorateSeats() {
    root.querySelectorAll('#seats .seat').forEach((el) => {
      const team = teamOfSeat(Number(el.dataset.seat));
      el.classList.toggle('pk-red', team === 'red');
      el.classList.toggle('pk-blue', team === 'blue');
    });
  }

  function renderPk() {
    clearInterval(pkTimer);
    const pk = state.pk;
    pkEl.hidden = !pk;
    if (!pk) return decorateSeats();
    const total = pk.red + pk.blue;
    const redPercent = total ? Math.round((pk.red / total) * 100) : 50;
    const tick = () => {
      const seconds = Math.max(0, Math.ceil((new Date(pk.ends_at) - Date.now()) / 1000));
      const label = pk.status === 'running'
        ? `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
        : pk.winner === 'draw' ? 'Berabere' : `${TEAM_LABELS[pk.winner]} kazandı`;
      pkEl.innerHTML = `
        <span class="pk-score pk-score-red">${formatCoins(pk.red)}</span>
        <span class="pk-track"><i style="width:${redPercent}%"></i></span>
        <span class="pk-score pk-score-blue">${formatCoins(pk.blue)}</span>
        <span class="pk-clock">⚔️ ${label}</span>`;
    };
    tick();
    if (pk.status === 'running') pkTimer = setInterval(tick, 1000);
    decorateSeats();
  }

  function onPk({ pk }) {
    const isNew = state.pk?.pk_id !== pk.pk_id;
    const wasRunning = !isNew && state.pk.status === 'running';
    if (pk.status === 'running' && isNew) {
      addSystemLine('⚔️ PK başladı! Kırmızı ve mavi takım koltuklarına hediye gönder, takımını kazandır.');
    }
    if (pk.status === 'ended' && wasRunning) {
      const result = pk.winner === 'draw' ? 'berabere bitti' : `<b>${TEAM_LABELS[pk.winner]}</b> takım kazandı`;
      addSystemLine(`🏁 PK ${result} (${formatCoins(pk.red)} - ${formatCoins(pk.blue)})${pk.mvp ? ` · MVP: <b>${esc(pk.mvp.user.display_name)}</b>` : ''}`);
      // Sonuç bir süre ekranda kalsın, sonra çubuk kapansın
      clearTimeout(pkHideTimer);
      pkHideTimer = setTimeout(() => { if (state.pk?.pk_id === pk.pk_id) { state.pk = null; renderPk(); } }, 15000);
    }
    state.pk = pk;
    renderPk();
  }

  // ─── Birlikte izleme ve karaoke ────────────────────────────────────────────
  function renderMediaSlot() {
    const { media, karaoke } = state;
    const singer = karaoke.singer
      ? `<div class="karaoke-singer">🎤 Şimdi söylüyor: <b>${esc(karaoke.singer.display_name)}</b>${karaoke.queue.length ? ` · sırada ${karaoke.queue.length} kişi` : ''}</div>`
      : '';
    if (!media) {
      player?.destroy?.();
      player = null;
      playerVideoId = null;
      mediaEl.innerHTML = singer;
      mediaEl.hidden = !singer;
      return;
    }
    mediaEl.hidden = false;
    if (!mediaEl.querySelector('#yt-player-wrap')) {
      mediaEl.innerHTML = `<div class="media-frame" id="yt-player-wrap"><div id="yt-player"></div></div>${singer}`;
      player = null;
      playerVideoId = null;
    } else {
      mediaEl.querySelector('.karaoke-singer')?.remove();
      if (singer) mediaEl.insertAdjacentHTML('beforeend', singer);
    }
    syncPlayer();
  }

  async function syncPlayer() {
    const media = state.media;
    if (!media) return;
    const YT = await loadYouTubeApi();
    if (disposed || state.media !== media) return;
    const target = expectedPosition(media, clockOffsetMs);
    if (!player || playerVideoId !== media.video_id) {
      player?.destroy?.();
      playerVideoId = media.video_id;
      player = new YT.Player('yt-player', {
        videoId: media.video_id,
        playerVars: { autoplay: media.paused ? 0 : 1, start: Math.floor(target), playsinline: 1, rel: 0 },
        events: { onReady: () => applyState() },
      });
      return;
    }
    applyState();
  }

  function applyState() {
    const media = state.media;
    if (!media || !player?.seekTo) return;
    const target = expectedPosition(media, clockOffsetMs);
    // 2 saniyeden az fark varsa atlama yapma: herkesin videosu sürekli zıplamasın
    if (Math.abs((player.getCurrentTime?.() || 0) - target) > 2) player.seekTo(target, true);
    if (media.paused) player.pauseVideo();
    else player.playVideo();
  }

  function onMedia({ media }) {
    const opened = media && (!state.media || state.media.video_id !== media.video_id);
    if (media) clockOffsetMs = new Date(media.server_time) - Date.now();
    if (opened) addSystemLine(`🎬 <b>${esc(media.set_by.display_name)}</b> birlikte izlemek için bir video açtı`);
    state.media = media;
    renderMediaSlot();
  }

  function onKaraoke({ karaoke }) {
    const newSinger = karaoke.singer && karaoke.singer.id !== state.karaoke.singer?.id;
    if (newSinger) addSystemLine(`🎤 Sıra <b>${esc(karaoke.singer.display_name)}</b>'de! Mikrofon onun.`);
    state.karaoke = karaoke;
    renderMediaSlot();
    activitiesView?.render();
  }

  // ─── Etkinlik paneli (PK, video, karaoke) ──────────────────────────────────

  function openActivitiesSheet() {
    const sheet = openSheet('<h2 class="sheet-title">Oda Etkinlikleri</h2><div id="activities-panel"></div>', { className: 'sheet-dark' });
    const panel = sheet.el.querySelector('#activities-panel');
    const render = () => {
      const mod = isModerator();
      const pk = state.pk;
      const running = pk?.status === 'running';
      const inQueue = state.karaoke.queue.some((u) => u.id === me.id);
      panel.innerHTML = `
        <section class="activity-block">
          <h3>⚔️ PK — Takım Hediye Yarışı</h3>
          <p>Koltukların ilk yarısı kırmızı, ikinci yarısı mavi takım. Süre bitince en çok hediye alan takım kazanır.</p>
          ${mod
            ? running
              ? '<button class="btn btn-soft btn-block" data-act="pk-stop">PK\'yi şimdi bitir</button>'
              : `<div class="activity-options">${PK_MINUTES.map((m) => `<button class="btn btn-sm btn-primary" data-act="pk-start" data-minutes="${m}">${m} dk</button>`).join('')}</div>`
            : `<small>${running ? 'PK sürüyor, takımına hediye gönder!' : 'PK\'yi oda sahibi ya da yönetici başlatır.'}</small>`}
        </section>
        <section class="activity-block">
          <h3>🎬 Birlikte İzle</h3>
          ${mod
            ? `<form class="activity-form" id="media-form">
                 <input name="url" placeholder="YouTube bağlantısı yapıştır" autocomplete="off" />
                 <button class="btn btn-sm btn-primary" type="submit">Aç</button>
               </form>
               ${state.media ? `<div class="activity-options">
                 <button class="btn btn-sm btn-soft" data-act="media-${state.media.paused ? 'play' : 'pause'}">${state.media.paused ? '▶ Oynat' : '⏸ Durdur'}</button>
                 <button class="btn btn-sm btn-soft" data-act="media-stop">Kapat</button></div>` : ''}`
            : `<small>${state.media ? 'Video odadaki herkese aynı anda oynuyor.' : 'Videoyu oda sahibi ya da yönetici açar.'}</small>`}
        </section>
        <section class="activity-block">
          <h3>🎤 Karaoke Sırası</h3>
          ${state.karaoke.singer ? `<p>Şimdi: <b>${esc(state.karaoke.singer.display_name)}</b></p>` : ''}
          <div class="karaoke-queue">${state.karaoke.queue.map((u, i) => `<span>${i + 1}. ${avatarImg(u, 'avatar-xs')} ${esc(u.display_name)}</span>`).join('') || '<small>Sırada kimse yok</small>'}</div>
          <div class="activity-options">
            <button class="btn btn-sm ${inQueue ? 'btn-soft' : 'btn-primary'}" data-act="${inQueue ? 'karaoke-leave' : 'karaoke-join'}">${inQueue ? 'Sıradan çık' : 'Sıraya gir'}</button>
            ${mod ? '<button class="btn btn-sm btn-soft" data-act="karaoke-next">Sıradakine geç</button>' : ''}
          </div>
        </section>`;
    };
    render();
    activitiesView = { render };

    panel.addEventListener('submit', async (event) => {
      event.preventDefault();
      try {
        await api.setMedia(room().id, event.target.elements.url.value);
        sheet.close();
      } catch (error) {
        toast(error.message, 'error');
      }
    });
    panel.addEventListener('click', async (event) => {
      const button = event.target.closest('[data-act]');
      if (!button) return;
      button.disabled = true;
      const id = room().id;
      try {
        const act = button.dataset.act;
        if (act === 'pk-start') await api.startPk(id, Number(button.dataset.minutes));
        else if (act === 'pk-stop') await api.stopPk(id);
        else if (act === 'media-play' || act === 'media-pause') {
          await api.controlMedia(id, act.slice(6), act === 'media-pause' ? expectedPosition(state.media, clockOffsetMs) : undefined);
        } else if (act === 'media-stop') await api.stopMedia(id);
        else if (act === 'karaoke-join') await api.joinKaraoke(id);
        else if (act === 'karaoke-leave') await api.leaveKaraoke(id);
        else if (act === 'karaoke-next') await api.nextSinger(id);
        if (act.startsWith('pk') || act.startsWith('media')) sheet.close();
      } catch (error) {
        toast(error.message, 'error');
      }
      button.disabled = false;
    });
    const observer = new MutationObserver(() => {
      if (!sheet.el.isConnected) {
        activitiesView = null;
        observer.disconnect();
      }
    });
    observer.observe(document.getElementById('overlay-root'), { childList: true });
  }

  // ─── İki kişilik oyunlar ───────────────────────────────────────────────────
  function playerChip(user, index, table) {
    const isTurn = table.game === 'connect4' && table.status === 'playing' && table.turn === index;
    const isWinner = table.status === 'finished' && table.winner === index;
    return `<span class="duel-player duel-p${index + 1} ${isTurn ? 'is-turn' : ''} ${isWinner ? 'is-winner' : ''}">${avatarImg(user, 'avatar-sm')}<b>${esc(user.display_name)}</b></span>`;
  }

  function resultText(table) {
    if (table.status === 'waiting') return 'Rakip bekleniyor...';
    if (table.status === 'playing') {
      if (table.game === 'connect4') return table.players[table.turn]?.id === me.id ? '<b>Sıra sende!</b> Bir sütuna dokun.' : 'Rakibin hamlesi bekleniyor';
      return 'Seçimini yap: üç turdan ikisini alan kazanır.';
    }
    if (table.winner === null || table.winner === undefined) return 'Berabere!';
    const name = esc(table.players[table.winner].display_name);
    return table.reason === 'forfeit' ? `${name} hükmen kazandı` : `🏆 ${name} kazandı!`;
  }

  function connect4Board(table) {
    const mine = table.players.findIndex((p) => p.id === me.id);
    const canPlay = table.status === 'playing' && mine === table.turn;
    // Hücreler satır satır; dokunulan hücrenin sütununa taş atılır (en alta düşer)
    return `
      <div class="c4-board ${canPlay ? 'can-play' : ''}">
        ${table.board.map((row) => row.map((cell, column) => `<button class="c4-cell c4-${cell}" data-column="${column}" ${canPlay ? '' : 'disabled'} aria-label="${column + 1}. sütun"></button>`).join('')).join('')}
      </div>`;
  }

  function rpsPanel(table) {
    const mine = table.players.findIndex((p) => p.id === me.id);
    const canChoose = table.status === 'playing' && mine >= 0 && !table.chosen?.[mine];
    const last = table.last_round;
    return `
      <div class="rps">
        <div class="rps-score">${table.scores?.[0] ?? 0} — ${table.scores?.[1] ?? 0}</div>
        ${last ? `<div class="rps-last">${RPS_EMOJI[last.choices[0]]} vs ${RPS_EMOJI[last.choices[1]]} · ${last.winner === null ? 'berabere' : `${esc(table.players[last.winner].display_name)} aldı`}</div>` : ''}
        ${table.status === 'playing' ? `<div class="rps-chosen">${table.players.map((p, i) => `${esc(p.display_name)}: ${table.chosen?.[i] ? '✔ seçti' : '…'}`).join(' · ')}</div>` : ''}
        ${canChoose ? `<div class="rps-choices">${RPS.map((r) => `<button data-rps="${r.id}"><i>${r.emoji}</i>${r.label}</button>`).join('')}</div>` : ''}
      </div>`;
  }

  function tableCard(table) {
    const isPlayer = table.players.some((p) => p.id === me.id);
    return `
      <div class="duel-table" data-table="${table.table_id}">
        <div class="duel-players">${table.players.map((p, i) => playerChip(p, i, table)).join('<span class="duel-vs">VS</span>')}</div>
        <p class="duel-status">${resultText(table)}</p>
        ${table.status !== 'waiting' ? (table.game === 'connect4' ? connect4Board(table) : rpsPanel(table)) : ''}
        <div class="activity-options">
          ${table.status === 'waiting' && !isPlayer ? '<button class="btn btn-sm btn-primary" data-duel="join">Rakip ol</button>' : ''}
          ${isPlayer && table.status !== 'finished' ? '<button class="btn btn-sm btn-soft" data-duel="leave">Masadan kalk</button>' : ''}
        </div>
      </div>`;
  }

  function mountDuel(panel, game) {
    const render = () => {
      const tables = [...state.duels.values()].filter((t) => t.game === game);
      panel.innerHTML = `
        <div class="duel-list">${tables.map(tableCard).join('') || `<p class="member-empty">Açık masa yok. İlk masayı sen aç, odadan biri rakip olsun!</p>`}</div>
        <button class="btn btn-primary btn-block" data-duel="create">Yeni masa aç</button>`;
    };
    const onClick = (event) => {
      const tableEl = event.target.closest('[data-table]');
      const tableId = tableEl?.dataset.table;
      const action = event.target.closest('[data-duel]')?.dataset.duel;
      const column = event.target.closest('[data-column]');
      const rps = event.target.closest('[data-rps]');
      if (action === 'create') channel.send('game:duel_create', { game });
      else if (action === 'join') channel.send('game:duel_join', { table_id: tableId });
      else if (action === 'leave') channel.send('game:duel_leave', { table_id: tableId });
      else if (column && !column.disabled) channel.send('game:duel_move', { table_id: tableId, move: Number(column.dataset.column) });
      else if (rps) channel.send('game:duel_move', { table_id: tableId, move: rps.dataset.rps });
    };
    panel.addEventListener('click', onClick);
    render();
    duelView = { render };
    return () => {
      panel.removeEventListener('click', onClick);
      duelView = null;
    };
  }

  function onDuel({ table }) {
    const previous = state.duels.get(table.table_id);
    state.duels.set(table.table_id, table);
    const names = table.players.map((p) => esc(p.display_name));
    const gameName = table.game === 'connect4' ? 'Dört Bağla' : 'Taş-Kağıt-Makas';
    if (!previous && table.status === 'waiting') {
      addSystemLine(`🎮 <b>${names[0]}</b> ${gameName} masası açtı, rakip arıyor! <button class="chat-join" data-action="game">Katıl</button>`);
    } else if (previous?.status !== 'finished' && table.status === 'finished') {
      addSystemLine(`🎮 ${gameName}: ${resultText(table)}`);
    }
    duelView?.render();
  }

  function onDuelClosed({ table_id: tableId }) {
    state.duels.delete(tableId);
    duelView?.render();
  }

  channel
    .on('room:pk_updated', onPk)
    .on('room:media_updated', onMedia)
    .on('room:karaoke_updated', onKaraoke)
    .on('game:duel_updated', onDuel)
    .on('game:duel_closed', onDuelClosed);

  // Odaya girişte güncel durum (sonrası olaylarla güncellenir)
  api.getActivities(room().id).then((snapshot) => {
    if (disposed) return;
    state.pk = snapshot.pk;
    state.karaoke = snapshot.karaoke;
    snapshot.duels.forEach((t) => state.duels.set(t.table_id, t));
    renderPk();
    if (snapshot.media) onMedia({ media: snapshot.media });
    else renderMediaSlot();
  }).catch(() => {});

  return {
    openActivitiesSheet,
    mountDuel,
    decorateSeats,
    dispose() {
      disposed = true;
      clearInterval(pkTimer);
      clearTimeout(pkHideTimer);
      player?.destroy?.();
    },
  };
}
