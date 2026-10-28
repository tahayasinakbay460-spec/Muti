// Uygulama genel ayarları. Marka adı ve API adresi yalnızca buradan değişir.
export const APP_NAME = 'Muti';

// false: veriler gerçek backend'den gelir (backend çalışıyor olmalı).
// true: backend olmadan, sahte (mock) veriyle çalışır.
export const USE_MOCK = false;

// Geliştirmede sayfa 5500 portundan (python -m http.server), backend 8000'den açılır.
// Canlıda backend sayfayı da kendisi sunar: API aynı adrestedir. Sayfa https ile
// açıldıysa WebSocket de şifreli (wss) olur; tarayıcı karışık bağlantıya izin vermez.
export const IS_DEV_SERVER = location.port === '5500' || location.protocol === 'file:';
const BACKEND_ORIGIN = IS_DEV_SERVER
  ? `http://${location.hostname || '127.0.0.1'}:8000`
  : location.origin;
export const API_BASE_URL = `${BACKEND_ORIGIN}/api/v1`;
export const WS_BASE_URL = `${BACKEND_ORIGIN.replace(/^http/, 'ws')}/ws`;

// Yönetim paneli uygulamadan AYRI bir adreste açılır (güvenlik: panelin tek kapısı, ileride IP kısıtı).
// Oturumların karışmaması buna bağlı değil; o iş aşağıdaki STORAGE_KEYS'te.
//   Canlıda:       uygulama https://mutishow.tech, panel https://admin.mutishow.tech (bkz. deploy/Caddyfile)
//   Geliştirmede:  uygulama http://127.0.0.1:5500, panel http://localhost:5500 (tarayıcı bunları da ayrı sayar)
function siteOrigins() {
  if (IS_DEV_SERVER) {
    const port = location.port ? `:${location.port}` : '';
    // Telefondan (192.168.x.x) ya da dosyadan açıldıysa ayrı adres yok; panel aynı adreste kalır.
    if (!['127.0.0.1', 'localhost'].includes(location.hostname)) return { app: location.origin, panel: location.origin };
    return { app: `http://127.0.0.1${port}`, panel: `http://localhost${port}` };
  }
  const host = location.hostname.replace(/^(admin|www)\./, '');
  return { app: `${location.protocol}//${host}`, panel: `${location.protocol}//admin.${host}` };
}
const SITE = siteOrigins();
export const APP_URL = SITE.app;                 // uygulamanın kökü (sonunda / yok)
export const ADMIN_URL = `${SITE.panel}/admin.html`;

// Yeni kayıt olan kullanıcının henüz görseli yoktur; onun yerine bunlar gösterilir
export const DEFAULT_AVATAR_URL = 'assets/avatars/m10.jpg';
export const DEFAULT_COVER_URL = 'assets/covers/sky.jpg';

// Yönetim paneli girişini uygulamanınkinden AYRI anahtarlarda saklar. Tarayıcı localStorage'ı adrese
// göre ayırır; panel ile uygulama aynı adresten açılırsa (ör. 127.0.0.1:5500/admin.html) ortak
// anahtarda uygulamaya giren kişi paneldekinin üstüne yazılıyordu. Ayrı anahtarla adres ne olursa
// olsun iki oturum birbirini bozmaz.
const IS_ADMIN_PAGE = location.pathname.endsWith('/admin.html');
const TOKEN_PREFIX = IS_ADMIN_PAGE ? 'muti_panel_' : 'muti_';

export const STORAGE_KEYS = {
  accessToken: `${TOKEN_PREFIX}access_token`,
  refreshToken: `${TOKEN_PREFIX}refresh_token`,
  // Yönetim paneli oturumu: sessionStorage'da (sekme kapanınca silinir), bkz. api.js
  staffToken: 'muti_staff_token',
  mockState: 'muti_mock_state',
};

export const ROOM_CATEGORIES = [
  { id: 'for_you', label: 'Sana Özel' },
  { id: 'chat', label: 'Sohbet' },
  { id: 'music', label: 'Müzik' },
  { id: 'game', label: 'Oyun' },
  { id: 'new_people', label: 'Yeni İnsanlar' },
];

export const CATEGORY_LABELS = {
  chat: 'Sohbet',
  music: 'Müzik',
  game: 'Oyun',
  new_people: 'Yeni İnsanlar',
};
