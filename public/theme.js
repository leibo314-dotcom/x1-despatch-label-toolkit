(() => {
  const storageKey = 'x1-page-theme';
  // Keep the saved Standard key: its user-facing name is now Simple.
  const themes = new Set(['standard', 'original', 'tekapo', 'sakura']);
  let theme = 'tekapo';

  try {
    const saved = localStorage.getItem(storageKey);
    if (themes.has(saved)) theme = saved;
    else if (saved === 'cat') localStorage.setItem(storageKey, theme);
  } catch {
    // The page remains usable when browser storage is unavailable.
  }

  document.documentElement.dataset.theme = theme;

  const bindPicker = () => {
    document.querySelectorAll('[data-theme-select]').forEach((picker) => {
      picker.value = theme;
      picker.addEventListener('change', () => {
        if (!themes.has(picker.value)) return;
        theme = picker.value;
        document.documentElement.dataset.theme = theme;
        try {
          localStorage.setItem(storageKey, theme);
        } catch {
          // Changing the current page does not depend on saving the preference.
        }
      });
    });
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindPicker, { once: true });
  } else {
    bindPicker();
  }
})();
