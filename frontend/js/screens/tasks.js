// Görevler: 7 günlük giriş ödülü şeridi ve günlük görevler
import { api } from '../api.js';
import { icon, formatCoins, toast, openSheet } from '../ui.js';

// 7 günlük şerit: alınmış günler soluk, bugün vurgulu
function checkinStrip(status) {
  return status.rewards.map((coins, index) => {
    const day = index + 1;
    const done = day < status.day || (day === status.day && status.claimed_today);
    const isToday = day === status.day && !status.claimed_today;
    return `
      <div class="checkin-day ${done ? 'is-done' : ''} ${isToday ? 'is-today' : ''} ${day === 7 ? 'is-big' : ''}">
        <small>${day}. gün</small>
        <i>${done ? icon('check', 16) : day === 7 ? '🎁' : '🪙'}</i>
        <b>${formatCoins(coins)}</b>
      </div>`;
  }).join('');
}

export function checkinCard(status) {
  return `
    <section class="checkin-card">
      <div class="section-head"><h2>Günlük Giriş</h2><small>Art arda gel, ödül büyüsün</small></div>
      <div class="checkin-strip">${checkinStrip(status)}</div>
      <button class="btn ${status.claimed_today ? 'btn-soft' : 'btn-primary'} btn-block" data-action="checkin" ${status.claimed_today ? 'disabled' : ''}>
        ${status.claimed_today ? 'Bugünkü ödülünü aldın · yarın tekrar gel' : `Bugünkü ödülü al · +${formatCoins(status.rewards[status.day - 1])}`}
      </button>
    </section>`;
}

// Ana sayfa açılınca, bugünkü ödül alınmadıysa bir kez gösterilen pencere
export async function maybeShowCheckin() {
  const key = 'muti_checkin_prompt';
  const today = new Date().toISOString().slice(0, 10);
  try {
    if (localStorage.getItem(key) === today) return;
    localStorage.setItem(key, today);
  } catch {
    // Depolama kapalıysa (gizli sekme) pencere her açılışta bir kez gösterilir; sorun değil
  }
  const status = await api.getCheckin().catch(() => null);
  if (!status || status.claimed_today) return;
  const sheet = openSheet(checkinCard(status), { className: 'sheet-dark' });
  sheet.el.querySelector('[data-action="checkin"]').addEventListener('click', async () => {
    try {
      const result = await api.claimCheckin();
      toast(`🎉 ${result.day}. gün ödülü: +${formatCoins(result.coins)} coin`, 'success');
    } catch (error) {
      toast(error.message, 'error');
    }
    sheet.close();
  });
}

function taskRow(task) {
  const percent = Math.round((task.progress / task.target) * 100);
  const done = task.progress >= task.target;
  return `
    <div class="task">
      <span class="task-body">
        <b>${task.title}</b>
        <span class="task-bar"><i style="width:${percent}%"></i></span>
        <small>${task.progress}/${task.target} · <span class="coin coin-sm"></span> ${formatCoins(task.coins)}</small>
      </span>
      ${task.claimed
        ? `<span class="task-claimed">${icon('check', 14)} Alındı</span>`
        : `<button class="btn btn-sm ${done ? 'btn-primary' : 'btn-soft'}" data-task="${task.id}" ${done ? '' : 'disabled'}>${done ? 'Al' : 'Devam'}</button>`}
    </div>`;
}

export async function renderTasks(root) {
  async function render() {
    const [status, tasks] = await Promise.all([api.getCheckin(), api.listTasks()]);
    root.innerHTML = `
      <header class="topbar">
        <a class="icon-btn icon-btn-plain" href="#/home" aria-label="Geri">${icon('chevron-left', 22)}</a>
        <h1 class="page-title">Görevler</h1>
        <span></span>
      </header>
      ${checkinCard(status)}
      <section class="section">
        <div class="section-head"><h2>Günlük Görevler</h2><small>Gece yarısı yenilenir</small></div>
        <div class="task-list">${tasks.map(taskRow).join('')}</div>
      </section>`;
  }
  await render();

  root.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-task], [data-action="checkin"]');
    if (!button || button.disabled) return;
    button.disabled = true;
    try {
      const result = button.dataset.task ? await api.claimTask(button.dataset.task) : await api.claimCheckin();
      toast(`+${formatCoins(result.coins)} coin`, 'success');
      await render();
    } catch (error) {
      toast(error.message, 'error');
      button.disabled = false;
    }
  });
}
