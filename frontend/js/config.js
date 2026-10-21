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

// Yeni kayıt olan kullanıcının henüz görseli yoktur; onun yerine bunlar gösterilir
export const DEFAULT_AVATAR_URL = 'assets/avatars/m10.jpg';
export const DEFAULT_COVER_URL = 'assets/covers/sky.jpg';

export const STORAGE_KEYS = {
  accessToken: 'muti_access_token',
  refreshToken: 'muti_refresh_token',
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
