// Giriş / kayıt ekranı
import { api } from '../api.js';
import { APP_NAME } from '../config.js';
import { toast, icon } from '../ui.js';

export function renderAuth(root) {
  let mode = 'login';

  root.innerHTML = `
    <section class="auth">
      <div class="auth-bg"></div>
      <div class="auth-hero">
        <div class="logo logo-lg"><span class="logo-mark">M</span><span class="logo-text">${APP_NAME}</span></div>
        <h1>Sesini duyur,<br />yeni insanlarla tanış</h1>
        <p>Sesli sohbet odaları, oda içi oyunlar ve hediyeler tek uygulamada.</p>
        <div class="auth-features">
          <span>🎙️ Sesli odalar</span>
          <span>🎲 Oda içi oyunlar</span>
          <span>🎁 Hediyeler</span>
        </div>
      </div>

      <form class="auth-card" id="auth-form" novalidate>
        <div class="segmented" role="tablist">
          <button type="button" class="is-active" data-mode="login">Giriş Yap</button>
          <button type="button" data-mode="register">Kayıt Ol</button>
        </div>
        <label class="field">
          <span>Kullanıcı adı</span>
          <input name="username" autocomplete="username" placeholder="kullanici_adin" maxlength="24" required />
        </label>
        <label class="field" id="email-field" hidden>
          <span>E-posta</span>
          <input name="email" type="email" autocomplete="email" placeholder="ornek@eposta.com" />
        </label>
        <label class="field">
          <span>Şifre</span>
          <input name="password" type="password" autocomplete="current-password" placeholder="••••••••" required />
        </label>
        <button class="btn btn-primary btn-block" type="submit" id="auth-submit">Giriş Yap</button>
        <button class="btn btn-ghost btn-block" type="button" id="guest-btn">${icon('user', 18)} Misafir olarak göz at</button>
        <p class="auth-legal" id="demo-login" hidden></p>
        <p class="auth-legal">Devam ederek <a href="legal.html#terms" target="_blank" rel="noopener">Kullanım Koşulları</a>'nı kabul etmiş ve <a href="legal.html#privacy" target="_blank" rel="noopener">Gizlilik ve KVKK Aydınlatma Metni</a>'ni okumuş olursun. 18 yaş ve üzeri içindir.</p>
      </form>
    </section>`;

  const form = root.querySelector('#auth-form');
  // Örnek veri yüklü yayında (demo/vitrin) denemek isteyene hazır hesap gösterilir
  api.getAppInfo().then(({ demo_login: demo }) => {
    if (!demo) return;
    const hint = root.querySelector('#demo-login');
    hint.innerHTML = `Demo hesabı: <b>${demo.username}</b> / <b>${demo.password}</b>`;
    hint.hidden = false;
  }).catch(() => {});
  const submitBtn = root.querySelector('#auth-submit');
  const emailField = root.querySelector('#email-field');

  root.querySelector('.segmented').addEventListener('click', (event) => {
    const button = event.target.closest('[data-mode]');
    if (!button) return;
    mode = button.dataset.mode;
    root.querySelectorAll('.segmented button').forEach((b) => b.classList.toggle('is-active', b === button));
    emailField.hidden = mode !== 'register';
    submitBtn.textContent = mode === 'login' ? 'Giriş Yap' : 'Hesap Oluştur';
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(form));
    data.username = data.username.trim();
    submitBtn.disabled = true;
    try {
      if (mode === 'login') await api.login(data);
      else await api.register(data);
      location.hash = '#/home';
    } catch (error) {
      toast(error.message, 'error');
    } finally {
      submitBtn.disabled = false;
    }
  });

  root.querySelector('#guest-btn').addEventListener('click', async () => {
    try {
      await api.loginAsGuest();
      location.hash = '#/home';
    } catch (error) {
      toast(error.message, 'error');
    }
  });
}
