// Yayın odam: yayıncının kendi odaları ve kazancı.
//   Üstte: bugüne kadar hediyelerden kazanılan elmas ve "para kazanabilir miyim" açıklaması
//   Ortada: açtığım her oda (takipçi, hediye sayısı, elmas); takipçiye dokununca odayı kim takip ediyor
//   Altta: en çok destek olanlar ve ajans kartı
import { api } from '../api.js';
import { CATEGORY_LABELS } from '../config.js';
import { esc, icon, avatarImg, formatCoins, formatCount, openSheet, toast } from '../ui.js';
import { agencyCard } from './components.js';
import { openCreateRoomSheet } from './create-room.js';

function statBlock(value, label) {
  return `<span class="stat-block"><b>${value}</b><small>${label}</small></span>`;
}

function roomStats({ room, follower_count: followers, gift_count: gifts, gift_diamonds: total, month_gift_diamonds: month }) {
  return `
    <article class="broadcast-room">
      <a class="broadcast-room-head" href="#/room/${room.id}">
        <img src="${esc(room.cover_url)}" alt="" />
        <span class="my-room-info">
          <b>${esc(room.title)}</b>
          <small>${esc(CATEGORY_LABELS[room.category] || '')} · ID ${room.id} · ${formatCount(room.listener_count)} kişi şu an odada</small>
        </span>
        <span class="btn btn-sm btn-primary">Gir</span>
      </a>
      <div class="broadcast-room-stats">
        <button class="stat-block" data-followers="${room.id}"><b>${formatCount(followers)}</b><small>Takipçi ${icon('chevron-right', 11)}</small></button>
        ${statBlock(formatCount(gifts), 'Gelen hediye')}
        ${statBlock(`💎 ${formatCoins(total)}`, 'Toplam')}
        ${statBlock(`💎 ${formatCoins(month)}`, 'Bu ay')}
      </div>
    </article>`;
}

export async function renderMyRooms(root) {
  const [rooms, income, agency] = await Promise.all([
    api.listMyRooms(),
    api.getIncome(),
    api.getMyAgency().catch(() => null),
  ]);

  root.innerHTML = `
    <header class="topbar">
      <a class="icon-btn icon-btn-plain" href="#/home" data-back aria-label="Geri">${icon('chevron-left', 22)}</a>
      <h1 class="page-title">Yayın odam</h1>
      <button class="icon-btn icon-btn-plain" data-action="create-room" aria-label="Yeni oda aç">${icon('plus', 22)}</button>
    </header>

    <button class="create-room-cta" data-action="create-room">
      <span class="feature-icon">${icon('plus', 24)}</span>
      <span class="my-room-info"><b>${rooms.length ? 'Yeni oda oluştur' : 'Kendi odanı oluştur'}</b><small>Ad ve tür seç, odan hemen açılsın</small></span>
      ${icon('chevron-right', 18)}
    </button>

    <section class="earnings-card">
      <small>Yayıncılıktan toplam kazancın</small>
      <b class="earnings-total">💎 ${formatCoins(income.total_diamonds)}</b>
      <div class="earnings-row">
        ${statBlock(`💎 ${formatCoins(income.today_diamonds)}`, 'Bugün')}
        ${statBlock(`💎 ${formatCoins(income.week_diamonds)}`, 'Son 7 gün')}
        ${statBlock(`💎 ${formatCoins(income.diamond_balance)}`, 'Bakiyen')}
      </div>
    </section>

    <section class="section earn-info">
      <h2>Para kazanabilir miyim?</h2>
      <p>Evet. Odanda sana gönderilen her hediye elmas olarak cüzdanına geçer.
      Elmaslarını coine çevirebilirsin (1 elmas = ${income.diamond_to_coin_rate} coin).
      Bir ajansa bağlıysan bu ay topladığın elmasa göre yayıncı seviyen ve ay sonu bonusun hesaplanır.</p>
      ${income.withdrawals_enabled ? '' : '<p class="demo-note">Elmasları paraya çekme beta süresince kapalı.</p>'}
      <a class="btn btn-soft" href="#/wallet">${icon('wallet', 16)} Cüzdana git</a>
    </section>

    <section class="section">
      <div class="section-head"><h2>Odalarım</h2><small>${rooms.length}</small></div>
      ${rooms.map(roomStats).join('') || `
        <div class="empty">
          <p>Henüz bir odan yok. Oda açınca takipçilerin ve gelen hediyeler burada görünür.</p>
          <button class="btn btn-primary" data-action="create-room">Oda aç</button>
        </div>`}
    </section>

    ${income.top_supporters.length ? `
      <section class="section">
        <div class="section-head"><h2>En çok destek olanlar</h2></div>
        ${income.top_supporters.map(({ user, diamonds }, i) => `
          <a class="member-row" href="#/profile/${user.id}">
            <span class="rank-no">${i + 1}</span>
            ${avatarImg(user, 'avatar-md')}
            <span class="member-info"><b>${esc(user.display_name)}</b><small>💎 ${formatCoins(diamonds)}</small></span>
          </a>`).join('')}
      </section>` : ''}

    ${agency ? `<section class="section"><div class="section-head"><h2>Ajans</h2></div>${agencyCard(agency)}</section>` : ''}`;

  root.addEventListener('click', async (event) => {
    if (event.target.closest('[data-action="create-room"]')) {
      openCreateRoomSheet();
      return;
    }
    const button = event.target.closest('[data-followers]');
    if (!button) return;
    try {
      const followers = await api.listRoomFollowers(button.dataset.followers);
      openSheet(`
        <h2 class="sheet-title">Odanı takip edenler</h2>
        <div class="sheet-list">
          ${followers.map((u) => `
            <a class="member-row" href="#/profile/${u.id}" data-close>
              ${avatarImg(u, 'avatar-md')}
              <span class="member-info"><b>${esc(u.display_name)}</b><small>@${esc(u.username)}</small></span>
              ${u.is_online ? '<span class="online-dot"></span>' : ''}
            </a>`).join('') || '<p class="member-empty">Henüz odanı takip eden yok.</p>'}
        </div>`);
    } catch (error) {
      toast(error.message, 'error');
    }
  });
}
