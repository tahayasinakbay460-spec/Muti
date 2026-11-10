// Ajans. Diğer sesli sohbet uygulamalarındaki kalıp: yayıncı bir ajansa bağlanır (ajans davet eder ya da
// yayıncı başvurur), ay içinde topladığı elmasa göre bir seviyeye girer, her seviyenin ay sonu bonusu
// vardır; ajans da yayıncılarının kazancından komisyon alır. Bu ekran üç halde:
//   sahip  → yayıncılar, başvurular, hedefler, tahmini komisyon
//   üye    → ajansım, bu ayki kazancım, seviyem ve hedefim
//   ajanssız → davet / başvuru durumu, seviye tablosu, başvurulacak ajans listesi
import { api } from '../api.js';
import { esc, icon, avatarImg, formatCoins, toast, openSheet } from '../ui.js';

function progressBar(percent) {
  return `<span class="task-bar"><i style="width:${Math.min(100, percent)}%"></i></span>`;
}

// Seviye (maaş) tablosu: şu anki seviye vurgulanır, bir sonrakine kalan elmas yazılır.
// Ajans sahibinin kendi seviyesi yok (currentIndex = -1): yalnızca tablo görünür.
function tierTable(tiers, currentIndex, monthDiamonds) {
  const next = tiers[currentIndex + 1];
  const note = currentIndex < 0 ? '' : next
    ? `<p class="screen-note">${next.emoji} ${esc(next.name)} seviyesine 💎 ${formatCoins(next.min_diamonds - monthDiamonds)} kaldı.</p>`
    : '<p class="screen-note">En üst seviyedesin 💎</p>';
  return `
    <section class="section">
      <div class="section-head"><h2>Yayıncı seviyeleri</h2><small>Aylık elmasa göre</small></div>
      ${note}
      <div class="tier-list">
        ${tiers.map((t, i) => `
          <div class="tier ${i === currentIndex ? 'is-current' : ''} ${i < currentIndex ? 'is-passed' : ''}">
            <i>${t.emoji}</i>
            <span class="member-info"><b>${esc(t.name)}</b><small>💎 ${formatCoins(t.min_diamonds)}+ / ay</small></span>
            <span class="tier-bonus">${t.bonus_percent ? `%${t.bonus_percent} bonus` : '—'}</span>
          </div>`).join('')}
      </div>
      <p class="demo-note">Beta: bonus ve komisyon yalnızca hesaplanıyor, ödeme yapılmıyor.</p>
    </section>`;
}

// Ajans sistemi nasıl işler: Bigo, Yalla gibi uygulamalardaki ortak akış üç adımda
function howItWorks() {
  const steps = [
    { emoji: '🤝', title: 'Ajansa bağlan', text: 'Bir ajans seni davet eder ya da sen ajans numarasıyla başvurursun.' },
    { emoji: '🎯', title: 'Aylık hedefini tuttur', text: 'Ajans sana aylık elmas hedefi koyar; odanda aldığın her hediye hedefe sayılır.' },
    { emoji: '💰', title: 'Seviye bonusu kazan', text: 'Ay sonunda topladığın elmasa göre seviyen belirlenir. Ajansın komisyonunu uygulama öder; senin kazancından kesilmez.' },
  ];
  return `
    <section class="section">
      <div class="section-head"><h2>Nasıl çalışır?</h2></div>
      <ol class="how-steps">
        ${steps.map((s) => `<li><i>${s.emoji}</i><span><b>${s.title}</b><small>${s.text}</small></span></li>`).join('')}
      </ol>
    </section>`;
}

function memberRow(m, tiers) {
  const tier = tiers[m.tier_index];
  const tags = { invited: 'Davet bekliyor', applied: 'Başvurdu' };
  return `
    <div class="agency-member">
      <a href="#/profile/${m.user.id}">${avatarImg(m.user, 'avatar-md')}</a>
      <span class="task-body">
        <b>${esc(m.user.display_name)} ${tags[m.status] ? `<span class="admin-tag">${tags[m.status]}</span>` : ''}</b>
        ${m.status === 'active'
          ? `${progressBar(m.progress_percent)}<small>${tier ? `${tier.emoji} ${esc(tier.name)} · ` : ''}💎 ${formatCoins(m.month_diamonds)} / ${m.monthly_target ? formatCoins(m.monthly_target) : 'hedef yok'}</small>`
          : ''}
      </span>
      ${m.status === 'applied'
        ? `<button class="btn btn-sm btn-primary" data-accept="${m.user.id}">Kabul</button>
           <button class="btn btn-sm btn-soft" data-reject="${m.user.id}">Reddet</button>`
        : `<button class="icon-btn icon-btn-plain" data-member="${m.user.id}" aria-label="Seçenekler">${icon('more', 18)}</button>`}
    </div>`;
}

function ownerView(d, tiers) {
  const applications = d.members.filter((m) => m.status === 'applied');
  const others = d.members.filter((m) => m.status !== 'applied');
  return `
    <section class="agency-hero">
      <span class="family-badge family-badge-lg">🏢</span>
      <h2>${esc(d.agency.name)}</h2>
      <p>Ajans no ${d.agency.id} · yayıncılar bu numarayla başvurur</p>
      <div class="family-stats">
        <span><b>${d.agency.member_count}</b><small>Yayıncı</small></span>
        <span><b>💎 ${formatCoins(d.month_diamonds)}</b><small>Bu ay kazanç</small></span>
        <span><b>💎 ${formatCoins(d.estimated_commission)}</b><small>Bu ayın tahmini komisyonu (%${d.agency.commission_percent})</small></span>
      </div>
      <small class="agency-note">Komisyon ay bitince hesabına elmas olarak geçer; yayıncılarının kazancından kesilmez.</small>
    </section>
    ${applications.length ? `
      <section class="section">
        <div class="section-head"><h2>Başvurular</h2><small>${applications.length}</small></div>
        ${applications.map((m) => memberRow(m, tiers)).join('')}
      </section>` : ''}
    <section class="section">
      <form class="activity-form" id="invite-form">
        <input name="user_id" type="number" placeholder="Davet edilecek yayıncının ID'si" required />
        <button class="btn btn-sm btn-primary" type="submit">Davet et</button>
      </form>
    </section>
    <section class="section">
      <div class="section-head"><h2>Yayıncılar</h2><small>Bu ayki elmas / hedef</small></div>
      ${others.map((m) => memberRow(m, tiers)).join('') || '<p class="member-empty">Henüz yayıncı yok. ID ile davet et ya da başvuru bekle. Yalnızca onaylı yayıncılar davet edilebilir.</p>'}
    </section>
    ${d.settlements?.length ? `
      <section class="section">
        <div class="section-head"><h2>Ödenen komisyonlar</h2></div>
        ${d.settlements.map((s) => `
          <div class="agency-member">
            <span class="member-info"><b>${esc(s.month)}</b><small>${s.member_count} yayıncı · 💎 ${formatCoins(s.host_diamonds)} kazanç · %${s.commission_percent}</small></span>
            <b>+💎 ${formatCoins(s.commission_diamonds)}</b>
          </div>`).join('')}
      </section>` : ''}
    ${tierTable(tiers, -1, 0)}`;
}

function memberView(state) {
  const percent = state.my_target ? Math.round((state.my_month_diamonds / state.my_target) * 100) : 0;
  return `
    <section class="agency-hero">
      <span class="family-badge family-badge-lg">🏢</span>
      <h2>${esc(state.agency.name)}</h2>
      <p>Ajans sahibi: <a href="#/profile/${state.agency.owner.id}">${esc(state.agency.owner.display_name)}</a> · ${state.agency.member_count} yayıncı</p>
      <div class="agency-goal">
        <b>Bu ay 💎 ${formatCoins(state.my_month_diamonds)}${state.my_target ? ` / ${formatCoins(state.my_target)}` : ''}</b>
        ${state.my_target ? `${progressBar(percent)}<small>Hedefin %${percent}'i tamam</small>` : '<small>Ajansın sana henüz hedef koymadı.</small>'}
      </div>
      <button class="btn btn-soft" data-act="leave">Ajanstan ayrıl</button>
    </section>
    ${tierTable(state.tiers, state.my_tier_index, state.my_month_diamonds)}`;
}

function noneView(state, agencies, isHost) {
  let status = '';
  if (state.invite) {
    status = `
      <section class="agency-hero">
        <span class="family-badge family-badge-lg">✉️</span>
        <h2>${esc(state.invite.name)} seni davet etti</h2>
        <p>Ajans sahibi ${esc(state.invite.owner.display_name)} · ${state.invite.member_count} yayıncı · %${state.invite.commission_percent} komisyon</p>
        <div class="family-actions">
          <button class="btn btn-primary" data-act="accept">Kabul et</button>
          <button class="btn btn-soft" data-act="decline">Reddet</button>
        </div>
      </section>`;
  } else if (state.application) {
    status = `
      <section class="agency-hero">
        <span class="family-badge family-badge-lg">⏳</span>
        <h2>${esc(state.application.name)} başvurun bekliyor</h2>
        <p>Ajans sahibi kabul edince yayıncısı olursun; bildirim gelir.</p>
        <button class="btn btn-soft" data-act="withdraw">Başvuruyu geri çek</button>
      </section>`;
  } else {
    status = `
      <section class="agency-hero">
        <span class="family-badge family-badge-lg">🏢</span>
        <h2>Bir ajansa katıl</h2>
        <p>Ajanslar yayıncıları destekler, aylık hedef koyar; sen de topladığın elmasa göre seviye atlayıp bonus kazanırsın.</p>
      </section>`;
  }
  // Ajansa yalnızca onaylı yayıncılar katılır (başvuru Odalar > Ben > "Yayıncı ol")
  if (!isHost && !state.invite) {
    status = `
      <section class="agency-hero">
        <span class="family-badge family-badge-lg">🎙️</span>
        <h2>Önce yayıncı ol</h2>
        <p>Ajanslara yalnızca onaylı yayıncılar katılabilir. Odalar › Ben sekmesinden "Yayıncı ol" başvurusu yap.</p>
        <a class="btn btn-primary" href="#/rooms?tab=mine">Yayıncı ol</a>
      </section>`;
  }
  const canApply = isHost && !state.invite && !state.application;
  return `
    ${status}
    ${howItWorks()}
    ${tierTable(state.tiers, state.my_tier_index, state.my_month_diamonds)}
    ${canApply ? `
      <section class="section">
        <div class="section-head"><h2>Ajanslar</h2></div>
        <form class="activity-form" id="agency-search">
          <input name="query" placeholder="Ajans adı ya da numarası" maxlength="40" />
          <button class="btn btn-sm btn-soft" type="submit">${icon('search', 16)}</button>
        </form>
        <div id="agency-list">${agencyList(agencies)}</div>
      </section>` : ''}`;
}

function agencyList(agencies) {
  return agencies.map((a) => `
    <div class="agency-member">
      ${avatarImg(a.owner, 'avatar-md')}
      <span class="member-info"><b>${esc(a.name)}</b><small>No ${a.id} · ${a.member_count} yayıncı · %${a.commission_percent} komisyon</small></span>
      <button class="btn btn-sm btn-primary" data-apply="${a.id}">Başvur</button>
    </div>`).join('') || '<p class="member-empty">Ajans bulunamadı.</p>';
}

export async function renderAgency(root) {
  async function render() {
    const [state, me] = await Promise.all([api.getMyAgency(), api.getMe()]);
    const agencies = me.is_host && state.role === null && !state.invite && !state.application ? await api.listAgencies() : [];
    root.innerHTML = `
      <header class="topbar">
        <a class="icon-btn icon-btn-plain" href="#/home" data-back aria-label="Geri">${icon('chevron-left', 22)}</a>
        <h1 class="page-title">Ajans</h1>
        <span></span>
      </header>
      ${state.role === 'owner' ? ownerView(state.dashboard, state.tiers) : state.role === 'member' ? memberView(state) : noneView(state, agencies, me.is_host)}`;
    return state;
  }
  let state = await render();
  const rerender = async () => { state = await render(); };

  function openMemberSheet(userId) {
    const member = state.dashboard.members.find((m) => m.user.id === userId);
    const sheet = openSheet(`
      <h2 class="sheet-title">${esc(member.user.display_name)}</h2>
      ${member.status === 'active' ? `
        <form id="target-form">
          <label class="field"><span>Aylık elmas hedefi</span><input name="target" type="number" min="0" value="${member.monthly_target}" /></label>
          <button class="btn btn-primary btn-block" type="submit">Hedefi kaydet</button>
        </form>` : ''}
      <button class="btn btn-soft btn-block agency-remove" data-remove>${member.status === 'invited' ? 'Daveti geri çek' : 'Ajanstan çıkar'}</button>`, { className: 'sheet-dark' });
    sheet.el.querySelector('#target-form')?.addEventListener('submit', async (event) => {
      event.preventDefault();
      try {
        await api.setAgencyTarget(userId, Number(event.target.elements.target.value));
        sheet.close();
        await rerender();
      } catch (error) {
        toast(error.message, 'error');
      }
    });
    sheet.el.querySelector('[data-remove]').addEventListener('click', async () => {
      try {
        await api.removeAgencyMember(userId);
        sheet.close();
        await rerender();
      } catch (error) {
        toast(error.message, 'error');
      }
    });
  }

  root.addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      if (event.target.id === 'invite-form') {
        await api.inviteToAgency(Number(event.target.elements.user_id.value));
        toast('Davet gönderildi', 'success');
        await rerender();
      } else if (event.target.id === 'agency-search') {
        root.querySelector('#agency-list').innerHTML = agencyList(await api.listAgencies(event.target.elements.query.value));
      }
    } catch (error) {
      toast(error.message, 'error');
    }
  });

  root.addEventListener('click', async (event) => {
    const memberBtn = event.target.closest('[data-member]');
    if (memberBtn) return openMemberSheet(Number(memberBtn.dataset.member));
    const target = event.target.closest('[data-apply], [data-accept], [data-reject], [data-act]');
    if (!target) return;
    target.disabled = true;
    try {
      if (target.dataset.apply) {
        await api.applyToAgency(Number(target.dataset.apply));
        toast('Başvurun gönderildi', 'success');
      } else if (target.dataset.accept) {
        await api.acceptAgencyApplication(Number(target.dataset.accept));
        toast('Yayıncı ajansa katıldı', 'success');
      } else if (target.dataset.reject) {
        await api.removeAgencyMember(Number(target.dataset.reject));
      } else {
        const act = target.dataset.act;
        if (act === 'accept' || act === 'decline') await api.answerAgencyInvite(act === 'accept');
        else if (act === 'leave') await api.leaveAgency();
        else if (act === 'withdraw') await api.withdrawAgencyApplication();
        if (act === 'accept') toast('🏢 Ajansa katıldın!', 'success');
      }
      await rerender();
    } catch (error) {
      toast(error.message, 'error');
      target.disabled = false;
    }
  });
}
