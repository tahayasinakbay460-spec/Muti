// Ben sekmesindeki iki panel:
//   "Yayıncı ol" başvurusu (doğum tarihi, tanıtım, 18+ ve kural onayı; panelde moderatör onaylar)
//   "Ajans" tanıtımı: ajans kurmak isteyen müşteri hizmetlerine yazar, yayıncı ajansa katılır.
import { api } from '../api.js';
import { esc, icon, toast, openSheet } from '../ui.js';

const HOST_RULES = [
  '18 yaşından büyük olmak',
  'Çıplaklık, şiddet, nefret söylemi ve reklam yok',
  'Hediye için kimseyi zorlamamak, para istememek',
  'Kişisel bilgi (telefon, adres, banka) paylaşmamak',
];

export function openHostApplySheet(onDone) {
  const maxDate = new Date();
  maxDate.setFullYear(maxDate.getFullYear() - 18);
  const sheet = openSheet(`
    <h2 class="sheet-title">🎙️ Yayıncı ol</h2>
    <p class="sheet-note">Başvurun ekibimiz tarafından incelenir. Onaylanınca profilinde yayıncı rozeti çıkar, ajanslara katılabilirsin; kameralı canlı yayın ve kazanç çekimi de yayıncılara açılacak.</p>
    <form id="host-form">
      <label class="field">
        <span>Doğum tarihin</span>
        <input name="birth_date" type="date" max="${maxDate.toISOString().slice(0, 10)}" required />
      </label>
      <label class="field">
        <span>Kendini tanıt (ne yayını yapacaksın?)</span>
        <textarea name="intro" minlength="10" maxlength="300" rows="3" placeholder="Örn. Akşamları müzik odası açıp şarkı söylüyorum." required></textarea>
      </label>
      <div class="host-rules">
        <b>Yayıncı kuralları</b>
        <ul>${HOST_RULES.map((rule) => `<li>${esc(rule)}</li>`).join('')}</ul>
      </div>
      <label class="check-row"><input type="checkbox" name="accept_rules" required /> <span>18 yaşından büyüğüm, kuralları kabul ediyorum.</span></label>
      <button class="btn btn-primary btn-block" type="submit">Başvur</button>
    </form>`);
  sheet.el.querySelector('#host-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.target;
    const button = form.querySelector('button');
    button.disabled = true;
    try {
      const status = await api.applyHost({
        birth_date: form.elements.birth_date.value,
        intro: form.elements.intro.value.trim(),
        accept_rules: form.elements.accept_rules.checked,
      });
      sheet.close();
      toast('Başvurun alındı. İncelenince bildirim gelecek.', 'success');
      onDone?.(status);
    } catch (error) {
      toast(error.message, 'error');
      button.disabled = false;
    }
  });
}

// Ajans kutusu: ajansı olmayan kişiye. Ajans kurmak iş ortaklığıdır, müşteri hizmetleriyle konuşulur.
export function openAgencyContactSheet({ isHost }) {
  const sheet = openSheet(`
    <h2 class="sheet-title">🏢 Ajans</h2>
    <div class="agency-pitch">
      <p><b>Ajans kur, yayıncılarını yönet, her ay komisyon kazan.</b></p>
      <ul>
        <li>Yayıncılarını davet edersin, aylık hedef koyarsın.</li>
        <li>Yayıncılarının o ay kazandığı elmasın yüzdesi ay sonunda <b>komisyon</b> olarak sana ödenir. Yayıncının kazancından kesilmez.</li>
        <li>Ajans iş ortaklığıdır: ekibimizle görüşüp anlaşırız.</li>
      </ul>
    </div>
    <button class="btn btn-primary btn-block" data-contact>${icon('chat', 18)} Müşteri hizmetlerine yaz</button>
    ${isHost ? `<a class="btn btn-soft btn-block" href="#/agency" data-close>Yayıncı olarak bir ajansa katıl</a>` : ''}`);
  sheet.el.querySelector('[data-contact]').addEventListener('click', async () => {
    try {
      const { support_user_id: supportId } = await api.getAppInfo();
      if (!supportId) {
        toast('Müşteri hizmetleri şu an ulaşılamıyor.', 'error');
        return;
      }
      const chatId = await api.openConversationWith(supportId);
      sheet.close();
      // Sohbet açılınca kutuya hazır mesaj yazılır (chat.js ?draft=)
      location.hash = `#/chat/${chatId}?draft=${encodeURIComponent('Merhaba, ajans kurmak istiyorum.')}`;
    } catch (error) {
      toast(error.message, 'error');
    }
  });
}

// Ben sekmesindeki yayıncılık kutusu (durumuna göre)
export function hostCard(status) {
  if (!status) return '';
  if (status.is_host) {
    return `<div class="host-card is-host"><i>🎙️</i><span><b>Onaylı yayıncısın</b><small>Ajanslara katılabilirsin; kameralı yayın yakında.</small></span></div>`;
  }
  const application = status.application;
  if (application?.status === 'pending') {
    return `<div class="host-card"><i>⏳</i><span><b>Yayıncı başvurun inceleniyor</b><small>Karar verilince bildirim gelecek.</small></span></div>`;
  }
  if (!status.can_apply && !application) {
    return `<div class="host-card"><i>🔒</i><span><b>Yayıncı olmak için hesap oluştur</b><small>Misafir hesaplar başvuramaz.</small></span></div>`;
  }
  if (!status.can_apply) {
    const when = status.reapply_after ? new Date(status.reapply_after).toLocaleDateString('tr-TR') : '';
    return `<div class="host-card"><i>📝</i><span><b>Başvurun reddedildi</b><small>${application?.review_note ? `${esc(application.review_note)} · ` : ''}${when ? `${when} sonra tekrar başvurabilirsin.` : ''}</small></span></div>`;
  }
  return `
    <button class="host-card host-card-cta" data-action="host-apply">
      <i>🎙️</i><span><b>Yayıncı ol</b><small>Başvur, onaylanınca rozet al ve ajanslara katıl.</small></span>${icon('chevron-right', 18)}
    </button>`;
}
