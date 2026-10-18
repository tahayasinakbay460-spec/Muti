// Uygulama genel ayarları. Marka adı ve API adresi yalnızca buradan değişir.
export const APP_NAME = 'MUTI';

// false: veriler gerçek backend'den gelir (backend çalışıyor olmalı).
// true: backend olmadan, sahte (mock) veriyle çalışır.
export const USE_MOCK = false;

// Sayfa hangi adla açıldıysa (127.0.0.1 ya da localhost) backend'e de aynı adla gidilir
const BACKEND_HOST = `${location.hostname || '127.0.0.1'}:8000`;
export const API_BASE_URL = `http://${BACKEND_HOST}/api/v1`;
export const WS_BASE_URL = `ws://${BACKEND_HOST}/ws`;

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
