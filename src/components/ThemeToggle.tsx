"use client";

/** Light or dark. The theme is set before first paint by the script in the
 *  root layout; this only flips it and remembers the choice. Both icons are
 *  drawn and CSS shows the right one, so nothing here depends on the theme
 *  while rendering - which is what keeps it free of hydration mismatches. */
export default function ThemeToggle() {
  const flip = () => {
    const root = document.documentElement;
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    // Backgrounds ease but text colour does not, so for a moment every tile
    // would be cream-on-cream. Switch with transitions off, then restore them.
    root.classList.add("theme-switch");
    root.dataset.theme = next;
    requestAnimationFrame(() => requestAnimationFrame(() => root.classList.remove("theme-switch")));
    try { localStorage.setItem("theme", next); } catch { /* private mode: the choice lasts this visit */ }
  };

  return (
    <button className="w-[34px] h-8 p-0 justify-center inline-flex items-center rounded-full font-semibold bg-transparent border-transparent text-[var(--muted)] hover:bg-[var(--sunk)]" aria-label="Switch between light and dark"
            title="Switch between light and dark" onClick={flip}>
      <svg className="moon" viewBox="0 0 24 24" width="16" height="16" aria-hidden>
        <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" fill="currentColor" />
      </svg>
      <svg className="sun" viewBox="0 0 24 24" width="16" height="16" aria-hidden>
        <circle cx="12" cy="12" r="4.2" fill="currentColor" />
        <path d="M12 2.5v2.5M12 19v2.5M2.5 12H5M19 12h2.5M5.3 5.3l1.8 1.8M16.9 16.9l1.8 1.8M5.3 18.7l1.8-1.8M16.9 7.1l1.8-1.8"
              stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    </button>
  );
}
