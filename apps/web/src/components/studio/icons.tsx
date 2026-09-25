/* The studio's icons: one stroke weight, drawn inline so they take the text
   colour of whatever they sit in. */

type P = { size?: number; className?: string };

const Svg = ({ size = 20, className, children }: P & { children: React.ReactNode }) => (
  <svg viewBox="0 0 24 24" width={size} height={size} className={className} fill="none" stroke="currentColor"
       strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{children}</svg>
);

/** A ring with its upper half lit: half heaven. */
export const Mark = ({ size = 22 }: P) => (
  <svg viewBox="0 0 22 22" width={size} height={size} aria-hidden="true">
    <circle cx="11" cy="11" r="9.25" fill="none" stroke="currentColor" strokeWidth="1.5" />
    <path d="M1.75 11a9.25 9.25 0 0 1 18.5 0z" fill="var(--accent)" />
  </svg>
);

export const Plus = (p: P) => <Svg {...p}><path d="M12 5v14M5 12h14" /></Svg>;
export const Arrow = (p: P) => <Svg {...p}><path d="M5 12h14M13 6l6 6-6 6" /></Svg>;
export const Check = (p: P) => <Svg {...p}><path d="M5 12.5l4.5 4.5L19 7" /></Svg>;
export const Bolt = (p: P) => <Svg {...p}><path d="M13 3L5 14h6l-1 7 8-11h-6l1-7z" /></Svg>;
export const Close = (p: P) => <Svg {...p}><path d="M6 6l12 12M18 6L6 18" /></Svg>;
export const Up = (p: P) => <Svg {...p}><path d="M12 19V5M6 11l6-6 6 6" /></Svg>;
export const Download = (p: P) => <Svg {...p}><path d="M12 4v11M7 10l5 5 5-5M5 20h14" /></Svg>;
export const Share = (p: P) => <Svg {...p}><path d="M12 15V4M8 8l4-4 4 4M5 13v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5" /></Svg>;
export const Undo = (p: P) => <Svg {...p}><path d="M9 14L4 9l5-5" /><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11" /></Svg>;
export const Touch = (p: P) => <Svg {...p}><circle cx="12" cy="12" r="3" /><circle cx="12" cy="12" r="8" /></Svg>;
export const Music = (p: P) => <Svg {...p}><path d="M9 18V6l11-2v12" /><circle cx="6.5" cy="18" r="2.5" /><circle cx="17.5" cy="16" r="2.5" /></Svg>;
export const Sliders = (p: P) => <Svg {...p}><path d="M4 7h10M18 7h2M4 17h4M12 17h8" /><circle cx="16" cy="7" r="2" /><circle cx="10" cy="17" r="2" /></Svg>;
export const Play = (p: P) => <Svg {...p}><path d="M8 5.5v13l10.5-6.5z" fill="currentColor" stroke="none" /></Svg>;
export const Pause = (p: P) => <Svg {...p}><path d="M8 5v14M16 5v14" strokeWidth="3" /></Svg>;
export const Film = (p: P) => <Svg {...p}><rect x="4" y="3" width="16" height="18" rx="3" /><path d="M10 9.5l5 2.5-5 2.5z" /></Svg>;
export const Sound = ({ on, ...p }: P & { on: boolean }) => (
  <Svg {...p}>
    <path d="M4 9v6h4l5 4V5L8 9H4z" fill="currentColor" stroke="none" />
    {on ? <path d="M16 8.5a5 5 0 0 1 0 7M18.5 6a8.5 8.5 0 0 1 0 12" />
        : <path d="M16 9.5l5 5M21 9.5l-5 5" />}
  </Svg>
);
export const More = (p: P) => (
  <Svg {...p}>
    <circle cx="5" cy="12" r="1.6" fill="currentColor" stroke="none" />
    <circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none" />
    <circle cx="19" cy="12" r="1.6" fill="currentColor" stroke="none" />
  </Svg>
);
