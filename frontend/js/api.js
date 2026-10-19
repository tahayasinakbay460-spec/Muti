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
  // Mağaza: eşya id → { expires_at (ms), is_equipped }
  owned_items: {
    2: { expires_at: Date.now() + 30 * 86400000, is_equipped: true },
    1: { expires_at: Date.now() + 7 * 86400000, is_equipped: false },
    102: { expires_at: Date.now() + 30 * 86400000, is_equipped: true },
    201: { expires_at: Date.now() + 7 * 86400000, is_equipped: true },
  },
  vip: { level: 0, expires_at: null, claimed_on: null },
  bought_package_ids: [],
  checkin: { day: 1, claimed_on: null },
  claimed_tasks: [],
  family_id: null,
  cp_partner_id: null,
  cp_declined: false,
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
const DAY_MS = 86400000;
const findItem = (id) => db.storeItems.find((i) => i.id === Number(id));
const isOwned = (id) => (state.owned_items[id]?.expires_at || 0) > Date.now();
const myVipLevel = () => (state.vip.expires_at && state.vip.expires_at > Date.now() ? state.vip.level : 0);
const today = () => new Date().toISOString().slice(0, 10);

// Takılı kozmetikler: { frame, entry_effect, chat_bubble } (backend UserOut ile aynı alanlar)
function myCosmetics() {
  const result = { frame: null, entry_effect: null, chat_bubble: null };
  Object.entries(state.owned_items).forEach(([id, owned]) => {
    const item = findItem(id);
    if (!item || !owned.is_equipped || owned.expires_at <= Date.now()) return;
    if (item.kind === 'entry_effect') result.entry_effect = { name: item.name, style: item.style, emoji: item.emoji };
    else result[item.kind] = item.style;
  });
  return result;
}

function storeItemOut(item) {
  const owned = state.owned_items[item.id];
  const active = isOwned(item.id);
  return {
    ...item,
    is_owned: active,
    owned_until: active ? new Date(owned.expires_at).toISOString() : null,
    is_equipped: active && owned.is_equipped,
  };
}

function unequipKind(kind) {
  Object.entries(state.owned_items).forEach(([id, owned]) => {
    if (findItem(id)?.kind === kind) owned.is_equipped = false;
  });
}

// Eşya verir; süre kalan sürenin üstüne eklenir ve aynı türden takılı olan çıkar
function grantItem(item, { days, until }) {
  const current = Math.max(state.owned_items[item.id]?.expires_at || 0, Date.now());
  const expiresAt = days ? current + days * DAY_MS : Math.max(until, current);
  unequipKind(item.kind);
  state.owned_items[item.id] = { expires_at: expiresAt, is_equipped: true };
}

function mockFamily(id) {
  const family = db.families.find((f) => f.id === id);
  const memberCount = family.member_ids.length + (state.family_id === id ? 1 : 0);
  return {
    id: family.id, name: family.name, badge: family.badge, slogan: family.slogan, owner_id: family.member_ids[0],
    member_count: memberCount, max_members: 50, week_coins: family.week_coins, level: family.level,
    my_role: state.family_id === id ? 'member' : null,
  };
}

function mockFamilyDetail(id) {
  const family = db.families.find((f) => f.id === id);
  const ids = [...family.member_ids, ...(state.family_id === id ? [db.CURRENT_USER_ID] : [])];
  return {
    ...mockFamily(id),
    members: ids.map((uid, i) => ({ user: withMeta(findUser(uid)), role: i === 0 ? 'owner' : 'member', week_coins: Math.max(0, 9000 - i * 1500) })),
  };
}

function mockCoupleStatus() {
  const since = new Date(Date.now() - 12 * DAY_MS).toISOString();
  const partner = state.cp_partner_id ? withMeta(findUser(state.cp_partner_id)) : null;
  return {
    active: partner ? { partner, status: 'active', requested_by_me: false, since, cp_coins: 1240 } : null,
    incoming: partner || state.cp_declined ? [] : [{ partner: withMeta(findUser(2005)), status: 'pending', requested_by_me: false, since, cp_coins: 0 }],
    outgoing: [],
    proposal_price: 520,
  };
}

function vipStatus() {
  const level = myVipLevel();
  return {
    level,
    expires_at: level ? new Date(state.vip.expires_at).toISOString() : null,
    daily_reward_available: Boolean(level) && state.vip.claimed_on !== today(),
    tiers: db.vipTiers.map(({ item_ids: ids, ...tier }) => ({ ...tier, items: ids.map(findItem) })),
  };
}

function withMeta(user) {
  if (!user) return null;
  const isMe = user.id === db.CURRENT_USER_ID;
  return {
    ...user,
    ...(isMe ? state.profile : {}),
    is_me: isMe,
    is_following: state.following_ids.includes(user.id),
    ...(isMe ? {
      coin_balance: state.coin_balance, vip_level: myVipLevel(), ...myCosmetics(),
      cp_partner_id: state.cp_partner_id,
      family: state.family_id ? (({ id, name, badge }) => ({ id, name, badge }))(db.families.find((f) => f.id === state.family_id)) : null,
    } : {}),
  };
}

function expandRoom(room) {
  return {
    ...room,
    is_following: state.followed_room_ids.includes(room.id),
    admin_ids: room.admin_ids || [],
    vip_ids: room.vip_ids || [],
    free_seating: room.free_seating ?? true,
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

  async changePassword() {
    await delay(300);
  },

  async deleteAccount() {
    await delay(300);
    localStorage.removeItem(STORAGE_KEYS.mockState);
    state.is_authenticated = false;
  },

  async searchUsers(query) {
    await delay(120);
    const q = query.trim().toLocaleLowerCase('tr');
    if (!q) return [];
    return db.users
      .filter((u) => u.id !== db.CURRENT_USER_ID && (`${u.display_name} ${u.username} ${u.id}`).toLocaleLowerCase('tr').includes(q))
      .map(withMeta);
  },

  async setBlocked(userId, blocked) {
    await delay(100);
    const id = Number(userId);
    state.blocked_ids = (state.blocked_ids || []).filter((x) => x !== id);
    if (blocked) state.blocked_ids.push(id);
    saveState();
    return { is_blocked: blocked };
  },

  async listBlocked() {
    await delay(80);
    return (state.blocked_ids || []).map((id) => withMeta(findUser(id)));
  },

  async report() {
    await delay(200);
  },

  async listNotifications() {
    await delay(100);
    return db.notifications.map((n) => ({ ...n, actor: n.actor_id ? withMeta(findUser(n.actor_id)) : null }));
  },

  async getNotificationUnreadCount() {
    return db.notifications.filter((n) => !n.is_read).length;
  },

  async markNotificationsRead() {
    db.notifications.forEach((n) => { n.is_read = true; });
  },

  async getIncome() {
    await delay(120);
    return {
      diamond_balance: state.diamond_balance ?? 860, today_diamonds: 120, week_diamonds: 540, total_diamonds: 2310,
      diamond_to_coin_rate: 1, withdrawals_enabled: false,
      top_supporters: [2001, 2012].map((id, i) => ({ user: withMeta(findUser(id)), diamonds: [940, 410][i] })),
    };
  },

  async exchangeDiamonds(diamonds) {
    await delay(200);
    const balance = state.diamond_balance ?? 860;
    if (diamonds > balance) throw new ApiError('insufficient_balance', 'Elmas bakiyen yetersiz.');
    state.diamond_balance = balance - diamonds;
    state.coin_balance += diamonds;
    addTransaction('exchange', `Elmas çevirme (+${diamonds} coin)`, diamonds);
    saveState();
    return { coin_balance: state.coin_balance, diamond_balance: state.diamond_balance, coins_added: diamonds };
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
      list = list.filter((r) => r.title.toLocaleLowerCase('tr').includes(q) || String(r.id) === query.trim());
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
  async setRoomRole(roomId, userId, role) {
    await delay(120);
    const room = mockModeratedRoom(roomId, { hostOnly: role === 'admin' });
    const id = Number(userId);
    room.admin_ids = (room.admin_ids || []).filter((x) => x !== id);
    room.vip_ids = (room.vip_ids || []).filter((x) => x !== id);
    if (role === 'admin') room.admin_ids.push(id);
    if (role === 'vip') room.vip_ids.push(id);
    return expandRoom(room);
  },

  async updateRoom(roomId, changes) {
    await delay(150);
    const room = mockModeratedRoom(roomId);
    Object.assign(room, Object.fromEntries(Object.entries(changes).filter(([, v]) => v != null)));
    return expandRoom(room);
  },

  async closeRoom(roomId) {
    await delay(150);
    mockModeratedRoom(roomId, { hostOnly: true });
    db.rooms.splice(db.rooms.findIndex((r) => r.id === Number(roomId)), 1);
  },

  // Mock'ta "odadakiler" = koltuktakiler (başka bağlantı bilgisi yok)
  async listRoomMembers(roomId) {
    await delay(120);
    const room = expandRoom(db.rooms.find((r) => r.id === Number(roomId)));
    return room.seats.filter((s) => s.user).map((s) => ({
      user: s.user,
      role: s.user.id === room.host_id ? 'host' : room.admin_ids.includes(s.user.id) ? 'admin' : (room.vip_ids || []).includes(s.user.id) ? 'vip' : 'listener',
      seat_index: s.index,
      is_mic_blocked: Boolean(s.is_mic_blocked),
      chat_muted_seconds: 0,
    }));
  },

  async inviteToSeat(roomId) {
    await delay(100);
    mockModeratedRoom(roomId);
  },

  async setMicBlocked(roomId, userId, blocked) {
    await delay(100);
    const room = mockModeratedRoom(roomId);
    const seat = room.seats.find((s) => s.user_id === Number(userId));
    if (seat) Object.assign(seat, { is_mic_blocked: blocked, is_muted: blocked || seat.is_muted });
    return expandRoom(room);
  },

  async setChatMute(roomId) {
    await delay(100);
    mockModeratedRoom(roomId);
  },

  async deleteChatMessage() {
    await delay(80);
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
    // Şanslı hediye: mock'ta basit bir çekiliş (gerçek oranlar backend'de, gift_service.LUCKY_TABLE)
    let luckyWin = 0;
    let luckyMultiplier = 0;
    if (gift.is_lucky) {
      for (let i = 0; i < quantity; i += 1) {
        const roll = Math.random();
        const multiplier = roll < 0.76 ? 0 : roll < 0.91 ? 1 : roll < 0.96 ? 2 : roll < 0.985 ? 5 : 10;
        luckyWin += multiplier * gift.price;
        luckyMultiplier = Math.max(luckyMultiplier, multiplier);
      }
      if (luckyWin) {
        state.coin_balance += luckyWin;
        addTransaction('lucky_win', `Şanslı hediye: ${gift.name} x${luckyMultiplier}`, luckyWin);
      }
    }
    saveState();
    return {
      coin_balance: state.coin_balance, gift, receiver: withMeta(receiver), quantity,
      lucky_win: luckyWin, lucky_multiplier: luckyMultiplier,
    };
  },

  async listCoinPackages() {
    await delay(80);
    return db.coinPackages.map((p) => ({
      ...p,
      item: p.item_id ? findItem(p.item_id) : null,
      is_bought: Boolean(p.is_one_time && state.bought_package_ids.includes(p.id)),
    }));
  },

  async purchaseCoins(packageId) {
    await delay(700);
    const pack = db.coinPackages.find((p) => p.id === packageId);
    if (pack.is_one_time && state.bought_package_ids.includes(pack.id)) {
      throw new ApiError('package_already_bought', 'Bu paketi zaten aldın.');
    }
    const total = pack.coins + pack.bonus;
    state.coin_balance += total;
    state.bought_package_ids.push(pack.id);
    addTransaction('purchase', `${pack.title || 'Coin satın alma'} (${pack.price_label})`, total);
    const item = pack.item_id ? findItem(pack.item_id) : null;
    if (item) grantItem(item, { days: pack.item_days });
    saveState();
    return { coin_balance: state.coin_balance, added: total, item };
  },

  // ── Mağaza ve VIP ──
  async listStoreItems(kind) {
    await delay(80);
    return db.storeItems.filter((i) => !kind || i.kind === kind).map(storeItemOut);
  },

  async purchaseStoreItem(itemId, days) {
    await delay(300);
    const item = findItem(itemId);
    if (item.vip_level_required > myVipLevel()) {
      throw new ApiError('vip_required', `Bu eşya VIP ${item.vip_level_required} ve üstüne özel.`);
    }
    const price = days === 7 ? item.price_7d : item.price_30d;
    if (state.coin_balance < price) throw new ApiError('insufficient_balance', 'Coin bakiyen yetersiz.');
    state.coin_balance -= price;
    addTransaction('store_purchase', `Mağaza: ${item.name} (${days} gün)`, -price);
    grantItem(item, { days });
    saveState();
    return { coin_balance: state.coin_balance, item: storeItemOut(item) };
  },

  async equipStoreItem(itemId, equipped) {
    await delay(100);
    const item = findItem(itemId);
    if (!isOwned(itemId)) throw new ApiError('item_not_owned', 'Bu eşyaya sahip değilsin.');
    if (equipped) unequipKind(item.kind);
    state.owned_items[itemId].is_equipped = equipped;
    saveState();
    return storeItemOut(item);
  },

  async listUserItems(userId) {
    await delay(80);
    // Mock'ta yalnızca ana kullanıcının eşyaları tutuluyor
    if (Number(userId) !== db.CURRENT_USER_ID) return [];
    return db.storeItems.filter((i) => isOwned(i.id)).map(storeItemOut);
  },

  async getVip() {
    await delay(80);
    return vipStatus();
  },

  async purchaseVip(level) {
    await delay(400);
    const tier = db.vipTiers.find((t) => t.level === level);
    const current = myVipLevel();
    if (current > level) throw new ApiError('vip_higher_active', 'Daha yüksek bir VIP üyeliğin zaten var.');
    if (state.coin_balance < tier.price_30d) throw new ApiError('insufficient_balance', 'Coin bakiyen yetersiz.');
    state.coin_balance -= tier.price_30d;
    const start = current === level ? state.vip.expires_at : Date.now();
    state.vip = { ...state.vip, level, expires_at: Math.max(start, Date.now()) + 30 * DAY_MS };
    tier.item_ids.forEach((id) => grantItem(findItem(id), { until: state.vip.expires_at }));
    addTransaction('vip_purchase', `VIP ${level} · ${tier.name} (30 gün)`, -tier.price_30d);
    saveState();
    return { coin_balance: state.coin_balance, status: vipStatus() };
  },

  async claimVipDailyReward() {
    await delay(200);
    const level = myVipLevel();
    if (!level) throw new ApiError('vip_required', 'Günlük ödül VIP üyelere özel.');
    if (state.vip.claimed_on === today()) throw new ApiError('daily_reward_claimed', 'Bugünkü ödülünü zaten aldın.');
    const coins = db.vipTiers.find((t) => t.level === level).daily_coins;
    state.vip.claimed_on = today();
    state.coin_balance += coins;
    addTransaction('vip_daily', `VIP ${level} günlük ödül`, coins);
    saveState();
    return { coins, coin_balance: state.coin_balance };
  },

  // ── Bağlılık (mock: kurallar basitleştirilmiş, asıl kurallar backend'de) ──
  async getCheckin() {
    await delay(60);
    return { day: state.checkin.day, claimed_today: state.checkin.claimed_on === today(), rewards: db.checkinRewards };
  },

  async claimCheckin() {
    await delay(150);
    if (state.checkin.claimed_on === today()) throw new ApiError('checkin_claimed', 'Bugünkü giriş ödülünü zaten aldın.');
    const coins = db.checkinRewards[state.checkin.day - 1];
    state.coin_balance += coins;
    const result = { day: state.checkin.day, coins, coin_balance: state.coin_balance };
    state.checkin = { day: state.checkin.day % 7 + 1, claimed_on: today() };
    addTransaction('daily_checkin', `Günlük giriş ödülü (${result.day}. gün)`, coins);
    saveState();
    return result;
  },

  async listTasks() {
    await delay(80);
    return db.tasks.map((t) => ({ ...t, claimed: state.claimed_tasks.includes(t.id) }));
  },

  async claimTask(taskId) {
    await delay(120);
    const task = db.tasks.find((t) => t.id === taskId);
    if (task.progress < task.target) throw new ApiError('task_not_completed', 'Görev henüz tamamlanmadı.');
    if (state.claimed_tasks.includes(taskId)) throw new ApiError('task_claimed', 'Bu görevin ödülünü bugün zaten aldın.');
    state.claimed_tasks.push(taskId);
    state.coin_balance += task.coins;
    addTransaction('task_reward', `Görev ödülü: ${task.title}`, task.coins);
    saveState();
    return { task_id: taskId, coins: task.coins, coin_balance: state.coin_balance };
  },

  async listFamilies(query = '') {
    await delay(100);
    const q = query.toLocaleLowerCase('tr');
    return db.families.filter((f) => f.name.toLocaleLowerCase('tr').includes(q)).map((f) => mockFamily(f.id));
  },

  async getMyFamily() {
    await delay(60);
    return state.family_id ? mockFamilyDetail(state.family_id) : null;
  },

  async getFamily(id) {
    await delay(80);
    return mockFamilyDetail(Number(id));
  },

  async joinFamily(id) {
    await delay(150);
    if (state.family_id) throw new ApiError('already_in_family', 'Zaten bir ailedesin. Önce ailenden ayrıl.');
    state.family_id = Number(id);
    saveState();
    return mockFamilyDetail(state.family_id);
  },

  async leaveFamily() {
    await delay(120);
    state.family_id = null;
    saveState();
  },

  async createFamily() {
    await delay(200);
    throw new ApiError('mock_only', 'Mock modunda aile kurulamaz; gerçek backend ile dene.');
  },

  async updateFamily(id) { return mockFamilyDetail(Number(id)); },
  async disbandFamily() { throw new ApiError('mock_only', 'Mock modunda desteklenmiyor.'); },
  async kickFamilyMember(id) { return mockFamilyDetail(Number(id)); },
  async setFamilyRole(id) { return mockFamilyDetail(Number(id)); },

  async listFamilyMessages(id) {
    await delay(80);
    return db.familyMessages.filter((m) => m.family_id === Number(id)).map((m) => ({ ...m, sender: withMeta(findUser(m.sender_id)) }));
  },

  async sendFamilyMessage(id, text) {
    await delay(100);
    return { id: Date.now(), sender: withMeta(findUser(db.CURRENT_USER_ID)), text, created_at: new Date().toISOString() };
  },

  async getCouple() {
    await delay(80);
    return mockCoupleStatus();
  },

  async proposeCouple() { throw new ApiError('mock_only', 'Mock modunda CP teklifi gönderilemez.'); },

  async acceptCouple(userId) {
    await delay(150);
    state.cp_partner_id = Number(userId);
    saveState();
    return mockCoupleStatus();
  },

  async declineCouple() {
    await delay(120);
    state.cp_declined = true;
    saveState();
    return mockCoupleStatus();
  },

  async breakUpCouple() {
    await delay(120);
    state.cp_partner_id = null;
    saveState();
    return mockCoupleStatus();
  },

  async getLeaderboard(kind, period) {
    await delay(120);
    const scores = [184500, 126300, 98750, 61200, 40800, 22100, 15400, 9800];
    let entries;
    if (kind === 'rooms') entries = db.rooms.slice(0, 8).map((r, i) => ({ rank: i + 1, score: scores[i], room: { id: r.id, title: r.title, cover_url: r.cover_url } }));
    else if (kind === 'families') entries = db.families.map((f, i) => ({ rank: i + 1, score: scores[i], family: { id: f.id, name: f.name, badge: f.badge, member_count: f.member_ids.length } }));
    else entries = [2001, 2012, 2015, 2003, 2010, 2002, 2005, 2008].map((id, i) => ({ rank: i + 1, score: scores[i], user: withMeta(findUser(id)) }));
    return { kind, period, entries, me: null };
  },

  async listEvents() {
    await delay(80);
    return db.events;
  },

  async getEvent(id) {
    await delay(100);
    const event = db.events.find((e) => e.id === Number(id));
    const entries = [2001, 2012, 2015, 2003, 2010].map((uid, i) => ({ rank: i + 1, score: [48200, 31900, 22400, 9100, 4300][i], user: withMeta(findUser(uid)) }));
    return { ...event, entries, me: null };
  },

  // Oda içi etkinlikler: mock'ta yok (PK, video, karaoke ve oyun masaları sunucu tarafında yönetilir)
  async getActivities() {
    await delay(60);
    return { pk: null, media: null, karaoke: { singer: null, queue: [] }, duels: [] };
  },
  async startPk() { throw new ApiError('mock_only', 'Mock modunda PK yok; gerçek backend ile dene.'); },
  async stopPk() { throw new ApiError('mock_only', 'Mock modunda PK yok.'); },
  async setMedia() { throw new ApiError('mock_only', 'Mock modunda birlikte izleme yok.'); },
  async controlMedia() { throw new ApiError('mock_only', 'Mock modunda birlikte izleme yok.'); },
  async stopMedia() {},
  async joinKaraoke() { throw new ApiError('mock_only', 'Mock modunda karaoke yok.'); },
  async leaveKaraoke() { return { singer: null, queue: [] }; },
  async nextSinger() { throw new ApiError('mock_only', 'Mock modunda karaoke yok.'); },

  // Yönetim paneli ve ajans: mock'ta yok (yetki ve kayıtlar sunucuda); ekranlar boş durum gösterir
  async getMyAgency() { await delay(60); return { role: null, dashboard: null, agency: null, my_month_diamonds: 0, my_target: 0, invite: null }; },
  async answerAgencyInvite() { throw new ApiError('mock_only', 'Mock modunda ajans yok.'); },
  async leaveAgency() { throw new ApiError('mock_only', 'Mock modunda ajans yok.'); },
  async inviteToAgency() { throw new ApiError('mock_only', 'Mock modunda ajans yok.'); },
  async setAgencyTarget() { throw new ApiError('mock_only', 'Mock modunda ajans yok.'); },
  async removeAgencyMember() { throw new ApiError('mock_only', 'Mock modunda ajans yok.'); },
  ...Object.fromEntries(['adminStats', 'adminReports', 'adminResolveReport', 'adminUsers', 'adminUser', 'adminBan', 'adminUnban',
    'adminAdjustBalance', 'adminRooms', 'adminCloseRoom', 'adminAgencies', 'adminCreateAgency']
    .map((name) => [name, async () => { throw new ApiError('admin_only', 'Yönetim paneli mock modunda yok.'); }])),

  // Hazine sandığı: mock'ta hep dolum aşamasında (gerçek dolum ve açılma backend'de)
  async getChest() {
    await delay(60);
    return { chest_id: 'mock', status: 'filling', progress: 3200, target: 10000, ends_at: null, coins_left: 0, claimed_by_me: false };
  },

  async claimChest() {
    await delay(100);
    throw new ApiError('chest_closed', 'Sandık şu an açık değil.');
  },

  async listTransactions(currency = 'coin') {
    await delay(80);
    return currency === 'coin' ? state.transactions : [];
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
  async changePassword(payload) {
    const data = await request('/auth/change-password', { method: 'POST', body: payload });
    storeTokens(data);   // diğer cihazlar kapandı; bu cihaz yeni token ile devam eder
    return data;
  },
  async deleteAccount(password) {
    await request('/users/me', { method: 'DELETE', body: { password: password || null } });
    clearTokens();
  },
  getMe: () => request('/users/me'),
  searchUsers: (query) => request(`/users/search?query=${encodeURIComponent(query)}`),
  setBlocked: (userId, blocked) => request(`/users/${userId}/block`, { method: blocked ? 'PUT' : 'DELETE' }),
  listBlocked: () => request('/users/me/blocks'),
  // target_type: 'user' | 'room'; reason: spam | harassment | inappropriate | underage | fraud | other
  report: (payload) => request('/reports', { method: 'POST', body: payload }),
  listNotifications: () => request('/notifications'),
  getNotificationUnreadCount: async () => (await request('/notifications/unread-count')).unread_count,
  markNotificationsRead: () => request('/notifications/read', { method: 'POST' }),
  getIncome: () => request('/wallet/income'),
  exchangeDiamonds: (diamonds) => request('/wallet/exchange', { method: 'POST', body: { diamonds }, headers: idempotencyHeader() }),
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
  updateRoom: (roomId, changes) => request(`/rooms/${roomId}`, { method: 'PATCH', body: changes }),
  closeRoom: (roomId) => request(`/rooms/${roomId}`, { method: 'DELETE' }),
  listRoomMembers: (roomId) => request(`/rooms/${roomId}/members`),
  // Sesli görüşmeye bağlanma bilgisi; biçimi sunucudaki ses sağlayıcısına göre değişir (bkz. js/voice/)
  getVoiceJoin: (roomId) => request(`/rooms/${roomId}/voice`),
  // role: 'admin' | 'vip' | 'listener' (özel rolü geri al)
  setRoomRole: (roomId, userId, role) => request(`/rooms/${roomId}/roles/${userId}`, { method: 'PUT', body: { role } }),
  setSeatLock: (roomId, seatIndex, locked) => request(`/rooms/${roomId}/seats/${seatIndex}/lock`, { method: locked ? 'PUT' : 'DELETE' }),
  removeFromSeat: (roomId, seatIndex) => request(`/rooms/${roomId}/seats/${seatIndex}/user`, { method: 'DELETE' }),
  inviteToSeat: (roomId, userId) => request(`/rooms/${roomId}/seat-invites/${userId}`, { method: 'POST' }),
  setMicBlocked: (roomId, userId, blocked) => request(`/rooms/${roomId}/mic-blocks/${userId}`, { method: blocked ? 'PUT' : 'DELETE' }),
  // minutes: 5 | 30 | 60 | 1440; null → susturmayı kaldır
  setChatMute: (roomId, userId, minutes) => request(`/rooms/${roomId}/chat-mutes/${userId}`, minutes ? { method: 'PUT', body: { minutes } } : { method: 'DELETE' }),
  deleteChatMessage: (roomId, messageId) => request(`/rooms/${roomId}/messages/${encodeURIComponent(messageId)}`, { method: 'DELETE' }),
  kickFromRoom: (roomId, userId) => request(`/rooms/${roomId}/kicks/${userId}`, { method: 'POST' }),
  listSuggestedUsers: () => request('/users/suggested'),
  listTopGifters: () => request('/leaderboards/gifters'),
  listGifts: () => request('/gifts'),
  sendGift: (payload) => request('/gifts/send', { method: 'POST', body: payload, headers: idempotencyHeader() }),
  listCoinPackages: () => request('/wallet/packages'),
  listStoreItems: (kind) => request(`/store/items${kind ? `?kind=${kind}` : ''}`),
  purchaseStoreItem: (itemId, days) => request(`/store/items/${itemId}/purchase`, { method: 'POST', body: { days }, headers: idempotencyHeader() }),
  equipStoreItem: (itemId, equipped) => request(`/store/items/${itemId}/equip`, { method: 'PUT', body: { equipped } }),
  listUserItems: (userId) => request(`/users/${userId}/items`),
  getVip: () => request('/vip'),
  purchaseVip: (level) => request('/vip/purchase', { method: 'POST', body: { level }, headers: idempotencyHeader() }),
  claimVipDailyReward: () => request('/vip/daily-reward', { method: 'POST' }),
  // ── Bağlılık: günlük giriş, görevler, aile, CP, sıralama, etkinlik ──
  getCheckin: () => request('/rewards/checkin'),
  claimCheckin: () => request('/rewards/checkin', { method: 'POST' }),
  listTasks: () => request('/tasks'),
  claimTask: (taskId) => request(`/tasks/${encodeURIComponent(taskId)}/claim`, { method: 'POST' }),
  listFamilies: (query = '') => request(`/families?query=${encodeURIComponent(query)}`),
  createFamily: (payload) => request('/families', { method: 'POST', body: payload }),
  getMyFamily: () => request('/families/me'),
  getFamily: (id) => request(`/families/${id}`),
  updateFamily: (id, changes) => request(`/families/${id}`, { method: 'PATCH', body: changes }),
  disbandFamily: (id) => request(`/families/${id}`, { method: 'DELETE' }),
  joinFamily: (id) => request(`/families/${id}/join`, { method: 'POST' }),
  leaveFamily: () => request('/families/me/membership', { method: 'DELETE' }),
  kickFamilyMember: (id, userId) => request(`/families/${id}/members/${userId}`, { method: 'DELETE' }),
  setFamilyRole: (id, userId, role) => request(`/families/${id}/members/${userId}/role`, { method: 'PUT', body: { role } }),
  listFamilyMessages: (id) => request(`/families/${id}/messages`),
  sendFamilyMessage: (id, text) => request(`/families/${id}/messages`, { method: 'POST', body: { text } }),
  getCouple: () => request('/couples/me'),
  proposeCouple: (userId) => request(`/couples/${userId}`, { method: 'POST' }),
  acceptCouple: (userId) => request(`/couples/${userId}/accept`, { method: 'POST' }),
  declineCouple: (userId) => request(`/couples/${userId}/request`, { method: 'DELETE' }),
  breakUpCouple: () => request('/couples/me', { method: 'DELETE' }),
  getLeaderboard: (kind, period) => request(`/leaderboards?kind=${kind}&period=${period}`),
  listEvents: () => request('/events'),
  getEvent: (id) => request(`/events/${id}`),
  // ── Oda içi etkinlikler (PK, birlikte izleme, karaoke); iki kişilik oyunlar WebSocket'te ──
  getActivities: (roomId) => request(`/rooms/${roomId}/activities`),
  startPk: (roomId, minutes) => request(`/rooms/${roomId}/pk`, { method: 'POST', body: { minutes } }),
  stopPk: (roomId) => request(`/rooms/${roomId}/pk`, { method: 'DELETE' }),
  setMedia: (roomId, url) => request(`/rooms/${roomId}/media`, { method: 'PUT', body: { url } }),
  controlMedia: (roomId, action, position) => request(`/rooms/${roomId}/media/control`, { method: 'POST', body: { action, position } }),
  stopMedia: (roomId) => request(`/rooms/${roomId}/media`, { method: 'DELETE' }),
  joinKaraoke: (roomId) => request(`/rooms/${roomId}/karaoke/queue`, { method: 'POST' }),
  leaveKaraoke: (roomId) => request(`/rooms/${roomId}/karaoke/queue`, { method: 'DELETE' }),
  nextSinger: (roomId) => request(`/rooms/${roomId}/karaoke/next`, { method: 'POST' }),
  // ── Yönetim paneli (yalnızca yöneticiler) ve ajans ──
  adminStats: () => request('/admin/stats'),
  adminReports: (status = 'open') => request(`/admin/reports?status=${status}`),
  adminResolveReport: (id, action, note = '') => request(`/admin/reports/${id}/resolve`, { method: 'POST', body: { action, note } }),
  adminUsers: (query = '', sort = 'newest') => request(`/admin/users?query=${encodeURIComponent(query)}&sort=${sort}`),
  adminFinance: (days = 14) => request(`/admin/finance?days=${days}`),
  adminTransactions: ({ type = '', userId = '', beforeId = '', limit = 50 } = {}) => request(`/admin/transactions?limit=${limit}${type ? `&type=${type}` : ''}${userId ? `&user_id=${userId}` : ''}${beforeId ? `&before_id=${beforeId}` : ''}`),
  adminConversations: (userId = '') => request(`/admin/conversations${userId ? `?user_id=${userId}` : ''}`),
  adminConversationMessages: (id) => request(`/admin/conversations/${id}/messages`),
  adminRoomMessages: (id) => request(`/admin/rooms/${id}/messages`),
  adminGifts: () => request('/admin/catalog/gifts'),
  adminUpdateGift: (id, changes) => request(`/admin/catalog/gifts/${id}`, { method: 'PATCH', body: changes }),
  adminPackages: () => request('/admin/catalog/packages'),
  adminUpdatePackage: (id, changes) => request(`/admin/catalog/packages/${id}`, { method: 'PATCH', body: changes }),
  adminGrantVip: (id, level, days) => request(`/admin/users/${id}/vip`, { method: 'POST', body: { level, days } }),
  adminBroadcast: (text) => request('/admin/broadcast', { method: 'POST', body: { text } }),
  adminUser: (id) => request(`/admin/users/${id}`),
  adminBan: (id, reason) => request(`/admin/users/${id}/ban`, { method: 'POST', body: { reason } }),
  adminUnban: (id) => request(`/admin/users/${id}/ban`, { method: 'DELETE' }),
  adminAdjustBalance: (id, payload) => request(`/admin/users/${id}/balance`, { method: 'POST', body: payload }),
  adminRooms: () => request('/admin/rooms'),
  adminCloseRoom: (id) => request(`/admin/rooms/${id}`, { method: 'DELETE' }),
  adminAgencies: () => request('/admin/agencies'),
  adminCreateAgency: (payload) => request('/admin/agencies', { method: 'POST', body: payload }),
  getMyAgency: () => request('/agencies/me'),
  answerAgencyInvite: (accept) => request(`/agencies/me/invite/${accept ? 'accept' : 'decline'}`, { method: 'POST' }),
  leaveAgency: () => request('/agencies/me/membership', { method: 'DELETE' }),
  inviteToAgency: (userId) => request(`/agencies/me/members/${userId}`, { method: 'POST' }),
  setAgencyTarget: (userId, monthlyTarget) => request(`/agencies/me/members/${userId}/target`, { method: 'PUT', body: { monthly_target: monthlyTarget } }),
  removeAgencyMember: (userId) => request(`/agencies/me/members/${userId}`, { method: 'DELETE' }),
  getChest: (roomId) => request(`/rooms/${roomId}/chest`),
  claimChest: (roomId) => request(`/rooms/${roomId}/chest/claim`, { method: 'POST' }),
  purchaseCoins: (packageId) => request('/wallet/purchase', { method: 'POST', body: { package_id: packageId }, headers: idempotencyHeader() }),
  listTransactions: (currency = 'coin') => request(`/wallet/transactions?currency=${currency}`),
  listConversations: () => request('/conversations'),
  getConversation: (id) => request(`/conversations/${id}`),
  openConversationWith: async (userId) => (await request('/conversations', { method: 'POST', body: { user_id: userId } })).id,
  sendMessage: (id, text) => request(`/conversations/${id}/messages`, { method: 'POST', body: { text } }),
  markConversationRead: (id) => request(`/conversations/${id}/read`, { method: 'POST' }),
  getUnreadCount: async () => (await request('/conversations/unread-count')).unread_count,
};

export const api = USE_MOCK ? mockApi : httpApi;
