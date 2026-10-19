// Şikâyet paneli: kullanıcı ya da oda için sebep seçtirir ve sunucuya gönderir.
import { api } from '../api.js';
import { esc, icon, openSheet, toast } from '../ui.js';

// Yönetim paneli de aynı etiketleri kullanır
export const REASONS = [
  { id: 'spam', label: 'Spam veya reklam' },
  { id: 'harassment', label: 'Taciz veya zorbalık' },
  { id: 'inappropriate', label: 'Uygunsuz içerik' },
  { id: 'underage', label: '18 yaşından küçük olabilir' },
  { id: 'fraud', label: 'Dolandırıcılık' },
  { id: 'other', label: 'Diğer' },
];

// targetType: 'user' | 'room'
export function openReportSheet(targetType, targetId, targetName) {
  let reason = null;
  const sheet = openSheet(`
    <h2 class="sheet-title">${esc(targetName)} şikâyet et</h2>
    <form id="report-form">
      <div class="chips chips-wrap" id="report-reasons">
        ${REASONS.map((r) => `<button type="button" class="chip" data-reason="${r.id}">${r.label}</button>`).join('')}
      </div>
      <label class="field">
        <span>Açıklama (isteğe bağlı)</span>
        <textarea name="details" maxlength="500" rows="3" placeholder="Ne oldu?"></textarea>
      </label>
      <button class="btn btn-danger btn-block" type="submit" disabled>${icon('close', 16)} Şikâyet et</button>
    </form>`, { className: 'sheet-dark' });

  const form = sheet.el.querySelector('#report-form');
  const submit = form.querySelector('[type="submit"]');
  sheet.el.querySelector('#report-reasons').addEventListener('click', (event) => {
    const chip = event.target.closest('[data-reason]');
    if (!chip) return;
    reason = chip.dataset.reason;
    chip.parentElement.querySelectorAll('.chip').forEach((el) => el.classList.toggle('is-active', el === chip));
    submit.disabled = false;
  });
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    submit.disabled = true;
    try {
      await api.report({ target_type: targetType, target_id: Number(targetId), reason, details: form.elements.details.value.trim() });
      sheet.close();
      toast('Şikâyetin alındı, incelenecek. Teşekkürler.', 'success');
    } catch (error) {
      toast(error.message, 'error');
      submit.disabled = false;
    }
  });
}
