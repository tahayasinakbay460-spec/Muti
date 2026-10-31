// Geçici hatalarda artan aralıkla yeniden deneme (ör. ağ bir anlığına gitti).
export const RETRY_DELAYS_MS = [1000, 2000, 4000];

// `task` başarılı olana ya da denemeler bitene kadar çalışır; son hatayı olduğu gibi fırlatır.
// `shouldStop` true dönerse artık gerek kalmamıştır (ör. kişi koltuktan kalktı).
export async function retried(task, { delays = RETRY_DELAYS_MS, shouldStop = () => false } = {}) {
  for (let attempt = 0; ; attempt += 1) {
    try {
      return await task();
    } catch (error) {
      if (attempt >= delays.length || shouldStop()) throw error;
      await new Promise((resolve) => setTimeout(resolve, delays[attempt]));
      if (shouldStop()) throw error;
    }
  }
}
