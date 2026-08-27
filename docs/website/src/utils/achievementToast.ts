export interface AchievementToastDetail {
  title: string;
  message?: string;
}

export const showAchievementToast = (detail: AchievementToastDetail) => {
  window.dispatchEvent(new CustomEvent<AchievementToastDetail>('achievement-toast', { detail }));
};
