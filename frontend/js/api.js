// Tüm veri erişimi bu dosyadan geçer. Ekranlar yalnızca `api` nesnesini kullanır;
// mock ile gerçek backend arasındaki geçiş config.js içindeki USE_MOCK ile yapılır.
import { USE_MOCK, API_BASE_URL, STORAGE_KEYS } from './config.js';
import * as db from './mock-data.js';

// ─── MOCK DURUMU (localStorage'da saklanır) ──────────────────────────────────
const DEFAULT_STATE = {
  is_authenticated: false,
  coin_balance: 12450,
  following_ids: [2001, 2003],
  followed_room_ids: [],
  profile: {},
  transactions: [
    { id: 1, type: 'purchase', label: 'Coin satın alma', amount: 3680, time_label: '3 gün önce' },
    { id: 2, type: 'gift_sent', label: 'Hediye: Taç → Merve', amount: -299, time_label: '2 gün önce' },
    { id: 3, type: 'reward', label: 'Günlük giriş ödülü', amount: 50, time_label: 'Dün' },
  ],
};

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.mockState);
    return raw ? { ...DEFAULT_STATE, ...JSON.parse(raw) } : structuredClone(DEFAULT_STATE);
  } catch {
    return structuredClone(DEFAULT_STATE);
  }
}

const state = loadState();

function saveState() {
  try {
    localStorage.setItem(STORAGE_KEYS.mockState, JSON.stringify(state));
  } catch {
    // Depolama kapalıysa (gizli sekme vb.) demo yine de bellekten çalışır
  }
}

// Ağ gecikmesini taklit et ki yükleme durumları gerçekçi görünsün
const delay = (ms = 180) => new Promise((resolve) => setTimeout(resolve, ms));

class ApiError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

const findUser = (id) => db.users.find((u) => u.id === Number(id));

function withMeta(user) {
  if (!user) return null;
  const isMe = user.id === db.CURRENT_USER_ID;
  return {
    ...user,
    ...(isMe ? state.profile : {}),
    is_me: isMe,
    is_following: state.following_ids.includes(user.id),
    ...(isMe ? { coin_balance: state.coin_balance } : {}),
  };
}

function expandRoom(room) {
  return {
    ...room,
    is_following: state.followed_room_ids.includes(room.id),
    admin_ids: room.admin_ids || [],
    host: withMeta(findUser(room.host_id)),
    seats: room.seats.map((s) => ({ ...s, user: s.user_id ? withMeta(findUser(s.user_id)) : null })),
  };
}

function addTransaction(type, label, amount) {
  state.transactions.unshift({ id: Date.now(), type, label, amount, time_label: 'Az önce' });
}

function mockModeratedRoom(roomId, { hostOnly = false } = {}) {
  const room = db.rooms.find((r) => r.id === Number(roomId));
  const isHost = room.host_id === db.CURRENT_USER_ID;
  const isAdmin = (room.admin_ids || []).includes(db.CURRENT_USER_ID);
  if (!isHost && (hostOnly || !isAdmin)) throw new ApiError('not_room_moderator', 'Bu işlem için oda yöneticisi olmalısın.');
  return room;
}

const mockApi = {
  isAuthenticated: () => state.is_authenticated,

  async login({ username, password }) {
    await delay(500);
    if (!username || !password) throw new ApiError('invalid_credentials', 'Kullanıcı adı ve şifre gerekli.');
    state.is_authenticated = true;
    state.profile = { username: username.toLowerCase(), display_name: username };
    saveState();
    return { user: withMeta(findUser(db.CURRENT_USER_ID)) };
  },

  async register({ username, email, password }) {
    await delay(600);
    if (!username || !email || !password) throw new ApiError('validation_error', 'Tüm alanları doldur.');
    if (password.length < 6) throw new ApiError('weak_password', 'Şifre en az 6 karakter olmalı.');
    return this.login({ username, password });
  },

  async loginAsGuest() {
    await delay(300);
    state.is_authenticated = true;
    state.profile = {};
    saveState();
    return { user: withMeta(findUser(db.CURRENT_USER_ID)) };
  },

  async logout() {
    state.is_authenticated = false;
    saveState();
  },

  async getMe() {
    await delay(60);
    return withMeta(findUser(db.CURRENT_USER_ID));
  },

  async getUser(id) {
    await delay();
    const user = withMeta(findUser(id));
    if (!user) throw new ApiError('not_found', 'Kullanıcı bulunamadı.');
    return user;
  },

  async getProfileExtras() {
    await delay(80);
    return {
      wall_posts: db.wallPosts,
      avatar_frames: db.avatarFrames,
      achievements: db.achievements,
      recent_rewards: db.recentRewards,
    };
  },

  async toggleFollow(userId) {
    await delay(120);
    const id = Number(userId);
    const index = state.following_ids.indexOf(id);
    if (index >= 0) state.following_ids.splice(index, 1);
    else state.following_ids.push(id);
    saveState();
    return { is_following: index < 0 };
  },

  async updateProfile(changes) {
    await delay(200);
    if ('display_name' in changes && !changes.display_name?.trim()) {
      throw new ApiError('invalid_display_name', 'Görünen ad boş olamaz.');
    }
    state.profile = { ...state.profile, ...changes };
    saveState();
    return withMeta(findUser(db.CURRENT_USER_ID));
  },

  async getMediaOptions() {
    await delay(60);
    return {
      avatars: ['w', 'm'].flatMap((g) => Array.from({ length: 10 }, (_, i) => `assets/avatars/${g}${i + 1}.jpg`)),
      covers: ['sky', 'coast', 'city', 'night', 'beach', 'cafe', 'canal', 'canyon', 'coffee', 'guitar', 'lighthouse', 'mountain', 'music', 'terrace', 'profile']
        .map((name) => `assets/covers/${name}.jpg`),
    };
  },

  async toggleRoomFollow(roomId) {
    await delay(120);
    const id = Number(roomId);
    const index = state.followed_room_ids.indexOf(id);
    if (index >= 0) state.followed_room_ids.splice(index, 1);
    else state.followed_room_ids.unshift(id);
    saveState();
    return { is_following: index < 0 };
  },

  async listFollowedRooms() {
    await delay();
    return state.followed_room_ids
      .map((id) => db.rooms.find((r) => r.id === id))
      .filter(Boolean)
      .map(expandRoom);
  },

  async listBanners() {
    await delay(60);
    return db.banners;
  },

  async listRooms({ category, query } = {}) {
    await delay();
    let list = db.rooms;
    if (category && category !== 'for_you') list = list.filter((r) => r.category === category);
    if (query) {
      const q = query.toLocaleLowerCase('tr');
      list = list.filter((r) => r.title.toLocaleLowerCase('tr').includes(q));
    }
    return list.map(expandRoom);
  },

  async getRoom(id) {
    await delay();
    const room = db.rooms.find((r) => r.id === Number(id));
    if (!room) throw new ApiError('not_found', 'Oda bulunamadı.');
    return expandRoom(room);
  },

  async createRoom({ title, category }) {
    await delay(400);
    if (!title?.trim()) throw new ApiError('validation_error', 'Oda adı gerekli.');
    const room = {
      id: 120000 + Math.floor(Math.random() * 9999),
      title: title.trim(),
      category,
      cover_url: 'assets/covers/sky.jpg',
      is_live: true,
      listener_count: 1,
      host_id: db.CURRENT_USER_ID,
      hourly_rank: 99,
      announcement: 'Odaya hoş geldin!',
      seats: Array.from({ length: 8 }, (_, index) => ({
        index, user_id: index === 0 ? db.CURRENT_USER_ID : null, is_muted: false, is_locked: false,
      })),
    };
    db.rooms.unshift(room);
    return expandRoom(room);
  },

  async takeSeat(roomId, seatIndex) {
    await delay(120);
    const room = db.rooms.find((r) => r.id === Number(roomId));
    const seat = room.seats[seatIndex];
    if (seat.is_locked) throw new ApiError('seat_locked', 'Bu koltuk kilitli.');
    if (seat.user_id) throw new ApiError('seat_taken', 'Bu koltuk dolu.');
    // Kullanıcı aynı anda tek koltukta oturabilir
    room.seats.forEach((s) => { if (s.user_id === db.CURRENT_USER_ID) s.user_id = null; });
    seat.user_id = db.CURRENT_USER_ID;
    seat.is_muted = false;
    return expandRoom(room);
  },

  async leaveSeat(roomId) {
    await delay(100);
    const room = db.rooms.find((r) => r.id === Number(roomId));
    room.seats.forEach((s) => { if (s.user_id === db.CURRENT_USER_ID) s.user_id = null; });
    return expandRoom(room);
  },

  async toggleMute(roomId) {
    await delay(60);
    const room = db.rooms.find((r) => r.id === Number(roomId));
    const seat = room.seats.find((s) => s.user_id === db.CURRENT_USER_ID);
    if (seat) seat.is_muted = !seat.is_muted;
    return expandRoom(room);
  },

  // Moderasyon (mock): yetki kuralları sadeleştirilmiş halde — oda sahibi ya da yönetici, oda sahibine dokunamaz
  async setRoomAdmin(roomId, userId, makeAdmin) {
    await delay(120);
    const room = mockModeratedRoom(roomId, { hostOnly: true });
    room.admin_ids = (room.admin_ids || []).filter((id) => id !== Number(userId));
    if (makeAdmin) room.admin_ids.push(Number(userId));
    return expandRoom(room);
  },

  async setSeatLock(roomId, seatIndex, locked) {
    await delay(100);
    const room = mockModeratedRoom(roomId);
    const seat = room.seats[seatIndex];
    if (locked && seat.user_id === room.host_id) throw new ApiError('target_outranks_you', 'Bu kişi üzerinde yetkin yok.');
    if (locked) seat.user_id = null;
    seat.is_locked = locked;
    return expandRoom(room);
  },

  async removeFromSeat(roomId, seatIndex) {
    await delay(100);
    const room = mockModeratedRoom(roomId);
    const seat = room.seats[seatIndex];
    if (seat.user_id === room.host_id) throw new ApiError('target_outranks_you', 'Bu kişi üzerinde yetkin yok.');
    seat.user_id = null;
    return expandRoom(room);
  },

  async kickFromRoom(roomId, userId) {
    await this.removeFromSeat(roomId, db.rooms.find((r) => r.id === Number(roomId)).seats.findIndex((s) => s.user_id === Number(userId)));
  },

  async listSuggestedUsers() {
    await delay();
    return db.users.filter((u) => u.id !== db.CURRENT_USER_ID).slice(6, 14).map(withMeta);
  },

  async listTopGifters() {
    await delay();
    const amounts = [184500, 126300, 98750, 61200, 40800];
    return [2001, 2012, 2015, 2003, 2010].map((id, i) => ({ rank: i + 1, user: withMeta(findUser(id)), total_coins: amounts[i] }));
  },

  async listGifts() {
    await delay(60);
    return db.gifts;
  },

  async sendGift({ receiver_id, gift_id, quantity = 1 }) {
    await delay(150);
    const gift = db.gifts.find((g) => g.id === gift_id);
    const receiver = findUser(receiver_id);
    const total = gift.price * quantity;
    if (state.coin_balance < total) throw new ApiError('insufficient_balance', 'Coin bakiyen yetersiz.');
    state.coin_balance -= total;
    addTransaction('gift_sent', `Hediye: ${gift.name} x${quantity} → ${receiver.display_name}`, -total);
    saveState();
    return { coin_balance: state.coin_balance, gift, receiver: withMeta(receiver), quantity };
  },

  async listCoinPackages() {
    await delay(80);
    return db.coinPackages;
  },

  async purchaseCoins(packageId) {
    await delay(700);
    const pack = db.coinPackages.find((p) => p.id === packageId);
    const total = pack.coins + pack.bonus;
    state.coin_balance += total;
    addTransaction('purchase', `Coin satın alma (${pack.price_label})`, total);
    saveState();
    return { coin_balance: state.coin_balance, added: total };
  },

  async listTransactions() {
    await delay(80);
    return state.transactions;
  },

  async listConversations() {
    await delay();
    return db.conversations.map((c) => ({ ...c, user: withMeta(findUser(c.user_id)), last_message: c.messages.at(-1) }));
  },

  async getConversation(id) {
    await delay(100);
    const conversation = db.conversations.find((c) => c.id === Number(id));
    if (!conversation) throw new ApiError('not_found', 'Sohbet bulunamadı.');
    conversation.unread_count = 0;
    return { ...conversation, user: withMeta(findUser(conversation.user_id)) };
  },

  async openConversationWith(userId) {
    await delay(100);
    let conversation = db.conversations.find((c) => c.user_id === Number(userId));
    if (!conversation) {
      conversation = { id: Date.now(), user_id: Number(userId), unread_count: 0, messages: [] };
      db.conversations.unshift(conversation);
    }
    return conversation.id;
  },

  async markConversationRead(conversationId) {
    const conversation = db.conversations.find((c) => c.id === Number(conversationId));
    if (conversation) conversation.unread_count = 0;
  },

  async getUnreadCount() {
    return db.conversations.reduce((sum, c) => sum + (c.unread_count || 0), 0);
  },

  async sendMessage(conversationId, text) {
    await delay(80);
    const conversation = db.conversations.find((c) => c.id === Number(conversationId));
    const message = { from_me: true, text, time: 'Şimdi' };
    conversation.messages.push(message);
    return message;
  },
};

// ─── GERÇEK BACKEND ──────────────────────────────────────────────────────────
function storeTokens({ access_token, refresh_token }) {
  localStorage.setItem(STORAGE_KEYS.accessToken, access_token);
  if (refresh_token) localStorage.setItem(STORAGE_KEYS.refreshToken, refresh_token);
}

function clearTokens() {
  localStorage.removeItem(STORAGE_KEYS.accessToken);
  localStorage.removeItem(STORAGE_KEYS.refreshToken);
}

async function send(path, { method = 'GET', body, headers = {} } = {}) {
  const token = localStorage.getItem(STORAGE_KEYS.accessToken);
  let response;
  try {
    response = await fetch(API_BASE_URL + path, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError('network_error', 'Sunucuya ulaşılamıyor. Backend çalışıyor mu?');
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new ApiError(data.code || 'request_failed', data.detail || 'İstek başarısız oldu.');
    error.status = response.status;
    throw error;
  }
  return data;
}

// Aynı anda birçok istek 401 alabilir; hepsi tek bir yenileme isteğini bekler.
// (Refresh token tek kullanımlıktır: iki kez gönderilirse backend tüm oturumları kapatır.)
let refreshPromise = null;

// Access token'ın süresi dolunca refresh token ile yenisini alır.
// Yenilenemezse oturum kapatılır ve giriş ekranına dönülür.
export function refreshSession() {
  refreshPromise ||= (async () => {
    const refreshToken = localStorage.getItem(STORAGE_KEYS.refreshToken);
    try {
      if (!refreshToken) throw new ApiError('not_authenticated', '');
      storeTokens(await send('/auth/refresh', { method: 'POST', body: { refresh_token: refreshToken } }));
    } catch (error) {
      // Sunucuya ulaşılamadıysa oturumu silme; bağlantı gelince kaldığı yerden devam eder
      if (error.code === 'network_error') throw error;
      clearTokens();
      location.hash = '#/auth';
      throw new ApiError('session_expired', 'Oturumun sona erdi, tekrar giriş yap.');
    }
  })().finally(() => { refreshPromise = null; });
  return refreshPromise;
}

async function request(path, options) {
  try {
    return await send(path, options);
  } catch (error) {
    if (error.status !== 401) throw error;
    await refreshSession();
    return send(path, options);
  }
}

// Para harcayan isteklerde gönderilir: bağlantı kopup istek tekrarlansa bile
// backend aynı anahtarı ikinci kez işlemez (çifte harcama olmaz).
const idempotencyHeader = () => ({
  'Idempotency-Key': crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`,
});

const httpApi = {
  isAuthenticated: () => Boolean(localStorage.getItem(STORAGE_KEYS.accessToken)),
  async login({ username, password }) {
    const data = await send('/auth/login', { method: 'POST', body: { username, password } });
    storeTokens(data);
    return data;
  },
  async register({ username, email, password }) {
    const data = await send('/auth/register', { method: 'POST', body: { username, email, password } });
    storeTokens(data);
    return data;
  },
  async loginAsGuest() {
    const data = await send('/auth/guest', { method: 'POST' });
    storeTokens(data);
    return data;
  },
  async logout() {
    const refreshToken = localStorage.getItem(STORAGE_KEYS.refreshToken);
    clearTokens();
    // Sunucudaki oturumu da kapat; ulaşılamazsa bile bu cihazdan çıkış yapılmış olur
    if (refreshToken) await send('/auth/logout', { method: 'POST', body: { refresh_token: refreshToken } }).catch(() => {});
  },
  getMe: () => request('/users/me'),
  getUser: (id) => request(`/users/${id}`),
  getProfileExtras: (id) => request(`/users/${id}/profile`),
  toggleFollow: (id) => request(`/users/${id}/follow`, { method: 'POST' }),
  updateProfile: (changes) => request('/users/me', { method: 'PATCH', body: changes }),
  getMediaOptions: () => request('/users/me/media-options'),
  toggleRoomFollow: (id) => request(`/rooms/${id}/follow`, { method: 'POST' }),
  listFollowedRooms: () => request('/rooms/followed'),
  listBanners: () => request('/banners'),
  listRooms: ({ category = '', query = '' } = {}) => request(`/rooms?category=${encodeURIComponent(category)}&query=${encodeURIComponent(query)}`),
  getRoom: (id) => request(`/rooms/${id}`),
  createRoom: (payload) => request('/rooms', { method: 'POST', body: payload }),
  takeSeat: (roomId, seatIndex) => request(`/rooms/${roomId}/seats/${seatIndex}`, { method: 'POST' }),
  leaveSeat: (roomId) => request(`/rooms/${roomId}/seats/me`, { method: 'DELETE' }),
  toggleMute: (roomId) => request(`/rooms/${roomId}/seats/me/mute`, { method: 'POST' }),
  setRoomAdmin: (roomId, userId, makeAdmin) => request(`/rooms/${roomId}/admins/${userId}`, { method: makeAdmin ? 'PUT' : 'DELETE' }),
  setSeatLock: (roomId, seatIndex, locked) => request(`/rooms/${roomId}/seats/${seatIndex}/lock`, { method: locked ? 'PUT' : 'DELETE' }),
  removeFromSeat: (roomId, seatIndex) => request(`/rooms/${roomId}/seats/${seatIndex}/user`, { method: 'DELETE' }),
  kickFromRoom: (roomId, userId) => request(`/rooms/${roomId}/kicks/${userId}`, { method: 'POST' }),
  listSuggestedUsers: () => request('/users/suggested'),
  listTopGifters: () => request('/leaderboards/gifters'),
  listGifts: () => request('/gifts'),
  sendGift: (payload) => request('/gifts/send', { method: 'POST', body: payload, headers: idempotencyHeader() }),
  listCoinPackages: () => request('/wallet/packages'),
  purchaseCoins: (packageId) => request('/wallet/purchase', { method: 'POST', body: { package_id: packageId }, headers: idempotencyHeader() }),
  listTransactions: () => request('/wallet/transactions'),
  listConversations: () => request('/conversations'),
  getConversation: (id) => request(`/conversations/${id}`),
  openConversationWith: async (userId) => (await request('/conversations', { method: 'POST', body: { user_id: userId } })).id,
  sendMessage: (id, text) => request(`/conversations/${id}/messages`, { method: 'POST', body: { text } }),
  markConversationRead: (id) => request(`/conversations/${id}/read`, { method: 'POST' }),
  getUnreadCount: async () => (await request('/conversations/unread-count')).unread_count,
};

export const api = USE_MOCK ? mockApi : httpApi;
