// Ajans: ajans sahibi için panel (yayıncılar, aylık hedefler, tahmini komisyon), yayıncı için
// ajansı ve bu ayki kazancı, davet edilen için kabul/ret. Ajansı uygulama yöneticisi kurar.
import { api } from '../api.js';
import { esc, icon, avatarImg, formatCoins, toast, openSheet } from '../ui.js';

function progressBar(percent) {
  return `<span class="task-bar"><i style="width:${Math.min(100, percent)}%"></i></span>`;
}

function ownerView(d) {
  return `
    <section class="agency-hero">
      <span class="family-badge family-badge-lg">🏢</span>
      <h2>${esc(d.agency.name)}</h2>
      <div class="family-stats">
        <span><b>${d.agency.member_count}</b><small>Yayıncı</small></span>
        <span><b>💎 ${formatCoins(d.month_diamonds)}</b><small>Bu ay kazanç</small></span>
        <span><b>💎 ${formatCoins(d.estimated_commission)}</b><small>Tahmini komisyon (%${d.agency.commission_percent})</small></span>
      </div>
      <p class="demo-note">Demo: komisyon yalnızca hesaplanıyor, ödeme yapılmıyor.</p>
    </section>
    <section class="section">
      <form class="activity-form" id="invite-form">
        <input name="user_id" type="number" placeholder="Davet edilecek yayıncının ID'si" required />
        <button class="btn btn-sm btn-primary" type="submit">Davet et</button>
      </form>
    </section>
    <section class="section">
      <div class="section-head"><h2>Yayıncılar</h2><small>Bu ayki elmas / hedef</small></div>
      ${d.members.map((m) => `
        <div class="agency-member">
          <a href="#/profile/${m.user.id}">${avatarImg(m.user, 'avatar-md')}</a>
          <span class="task-body">
            <b>${esc(m.user.display_name)} ${m.status === 'invited' ? '<span class="admin-tag">Davet bekliyor</span>' : ''}</b>
            ${m.status === 'active' ? `${progressBar(m.progress_percent)}<small>💎 ${formatCoins(m.month_diamonds)} / ${m.monthly_target ? formatCoins(m.monthly_target) : 'hedef yok'}</small>` : ''}
          </span>
          <button class="icon-btn icon-btn-plain" data-member="${m.user.id}" aria-label="Seçenekler">${icon('more', 18)}</button>
        </div>`).join('') || '<p class="member-empty">Henüz yayıncı yok. ID ile davet et.</p>'}
    </section>`;
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
    </section>`;
}

function noneView(state) {
  if (state.invite) {
    return `
      <section class="agency-hero">
        <span class="family-badge family-badge-lg">✉️</span>
        <h2>${esc(state.invite.name)} seni davet etti</h2>
        <p>Ajans sahibi ${esc(state.invite.owner.display_name)} · ${state.invite.member_count} yayıncı · %${state.invite.commission_percent} komisyon</p>
        <div class="family-actions">
          <button class="btn btn-primary" data-act="accept">Kabul et</button>
          <button class="btn btn-soft" data-act="decline">Reddet</button>
        </div>
      </section>`;
  }
  return `
    <div class="empty">
      <p>🏢 Bir ajansa bağlı değilsin.</p>
      <p class="demo-note">Ajanslar yayıncıları bulur, yönetir ve hedef koyar. Bir ajans seni davet edince burada görünür.
      Ajans kurmak için uygulama yönetimiyle iletişime geç.</p>
    </div>`;
}

export async function renderAgency(root) {
  async function render() {
    const state = await api.getMyAgency();
    root.innerHTML = `
      <header class="topbar">
        <a class="icon-btn icon-btn-plain" href="#/profile" aria-label="Geri">${icon('chevron-left', 22)}</a>
        <h1 class="page-title">Ajans</h1>
        <span></span>
      </header>
      ${state.role === 'owner' ? ownerView(state.dashboard) : state.role === 'member' ? memberView(state) : noneView(state)}`;
    return state;
  }
  let state = await render();

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
        state = await render();
      } catch (error) {
        toast(error.message, 'error');
      }
    });
    sheet.el.querySelector('[data-remove]').addEventListener('click', async () => {
      try {
        await api.removeAgencyMember(userId);
        sheet.close();
        state = await render();
      } catch (error) {
        toast(error.message, 'error');
      }
    });
  }

  root.addEventListener('submit', async (event) => {
    if (event.target.id !== 'invite-form') return;
    event.preventDefault();
    try {
      await api.inviteToAgency(Number(event.target.elements.user_id.value));
      toast('Davet gönderildi', 'success');
      state = await render();
    } catch (error) {
      toast(error.message, 'error');
    }
  });
  root.addEventListener('click', async (event) => {
    const memberBtn = event.target.closest('[data-member]');
    if (memberBtn) return openMemberSheet(Number(memberBtn.dataset.member));
    const act = event.target.closest('[data-act]')?.dataset.act;
    if (!act) return;
    try {
      if (act === 'accept' || act === 'decline') await api.answerAgencyInvite(act === 'accept');
      else if (act === 'leave') await api.leaveAgency();
      if (act === 'accept') toast('🏢 Ajansa katıldın!', 'success');
      state = await render();
    } catch (error) {
      toast(error.message, 'error');
    }
  });
}
