import { useEffect, useState } from 'react';
import { CheckCircle2 } from 'lucide-react';
import type { AchievementToastDetail } from '../utils/achievementToast';

const HIDE_AFTER_MS = 3200;

export default function AchievementToast() {
  const [achievement, setAchievement] = useState<AchievementToastDetail | null>(null);

  useEffect(() => {
    let hideTimer: ReturnType<typeof setTimeout> | undefined;
    const show = (event: Event) => {
      setAchievement((event as CustomEvent<AchievementToastDetail>).detail);
      if (hideTimer) clearTimeout(hideTimer);
      hideTimer = setTimeout(() => setAchievement(null), HIDE_AFTER_MS);
    };

    window.addEventListener('achievement-toast', show);
    return () => {
      window.removeEventListener('achievement-toast', show);
      if (hideTimer) clearTimeout(hideTimer);
    };
  }, []);

  return (
    <div className={`achievement-toast${achievement ? ' achievement-toast--visible' : ''}`} role="status" aria-live="polite">
      <CheckCircle2 aria-hidden="true" size={20} />
      <div>
        <strong>{achievement?.title ?? ''}</strong>
        {achievement?.message && <span>{achievement.message}</span>}
      </div>
    </div>
  );
}
