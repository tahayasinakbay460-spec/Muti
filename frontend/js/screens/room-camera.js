// Kameralı canlı yayın: oda ekranının üstündeki görüntü alanı (room.js bağlar).
// "Kimin kamerası açık?" bilgisinin sahibi sunucu (room:camera_updated); burada yalnızca görüntü
// bağlantısını açıp kapatıyoruz. Ses her zamanki gibi koltuktan gider.
import { api } from '../api.js';
import { connectLiveVideo } from '../voice/live-video.js';
import { toast } from '../ui.js';

const STOP_REASONS = {
  left: 'Yayıncı odadan ayrıldı, yayın bitti.',
  moderator: 'Yayın oda yöneticisi tarafından kapatıldı.',
  staff: 'Yayın yönetim tarafından kapatıldı.',
};

export function mountRoomCamera({ root, getRoom, me, channel }) {
  const stage = root.querySelector('#live-stage');
  const view = stage.querySelector('.live-video');
  let cameraUserId = getRoom().camera_user_id ?? null;
  let video = null;
  let connecting = null;
  let disposed = false;
  // Görüntü kanalına ancak sunucu bizi odaya ekledikten sonra bağlanılır (yoksa 403 not_in_room).
  // Sunucu katılım bitince `chat:history` gönderir; ses de aynı işareti bekliyor.
  let joined = false;

  const isStreamer = () => cameraUserId === me.id;
  // Kamerayı yalnızca oda sahibi, onaylı yayıncıysa açabilir (asıl kontrol sunucuda)
  const canStream = () => getRoom().host_id === me.id && me.is_host;

  function closeVideo() {
    video?.close();
    video = null;
    view.replaceChildren();
  }

  async function connect() {
    closeVideo();
    const forUser = cameraUserId;
    try {
      const info = await api.getCameraJoin(getRoom().id);
      if (disposed || forUser !== cameraUserId) return;
      video = await connectLiveVideo({
        info, me, stageEl: view, channel,
        refreshInfo: () => api.getCameraJoin(getRoom().id),
        onError: (message) => toast(message, 'error'),
      });
      if (disposed || forUser !== cameraUserId) closeVideo();
    } catch (error) {
      if (disposed) return;
      toast(error.message, 'error');
      // Yayıncının kamerası açılamadıysa yayını kapatırız: izleyiciler boş ekrana bakmasın
      if (isStreamer()) api.stopCamera(getRoom().id).catch(() => {});
    }
  }

  function apply(nextUserId) {
    if (nextUserId === cameraUserId && (video || connecting)) return;
    cameraUserId = nextUserId;
    stage.hidden = !cameraUserId;
    stage.querySelector('[data-action="camera-stop"]').hidden = !isStreamer();
    root.querySelector('.room')?.classList.toggle('has-camera', Boolean(cameraUserId));
    if (!cameraUserId) return closeVideo();
    if (!joined) return;
    connecting = connect().finally(() => { connecting = null; });
  }

  const onUpdated = ({ camera, reason }) => {
    const wasStreaming = isStreamer();
    apply(camera?.user_id ?? null);
    if (!camera && STOP_REASONS[reason] && !(wasStreaming && reason === 'stopped')) toast(STOP_REASONS[reason]);
  };
  // Bağlantı koptu-geldi: arada yayın başlamış ya da bitmiş olabilir
  const onReopened = async () => {
    const activities = await api.getActivities(getRoom().id).catch(() => null);
    if (activities && !disposed) apply(activities.camera?.user_id ?? null);
  };
  const onJoined = () => {
    if (joined) return;
    joined = true;
    if (cameraUserId && !video && !connecting) connecting = connect().finally(() => { connecting = null; });
  };
  channel.on('room:camera_updated', onUpdated).on('connection:reopened', onReopened).on('chat:history', onJoined);

  stage.addEventListener('click', (event) => {
    if (event.target.closest('[data-action="camera-stop"]')) toggle();
  });

  async function toggle() {
    try {
      if (isStreamer()) await api.stopCamera(getRoom().id);
      else apply((await api.startCamera(getRoom().id)).user_id);
    } catch (error) {
      toast(error.message, 'error');
    }
  }

  apply(cameraUserId);
  return {
    canStream,
    isStreaming: isStreamer,
    toggle,
    dispose() {
      disposed = true;
      channel.off('room:camera_updated', onUpdated);
      channel.off('connection:reopened', onReopened);
      channel.off('chat:history', onJoined);
      closeVideo();
    },
  };
}
