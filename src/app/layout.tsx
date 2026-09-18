import type { Metadata } from "next";
import { Bricolage_Grotesque, Plus_Jakarta_Sans, Bodoni_Moda } from "next/font/google";
import "./globals.css";

const display = Bricolage_Grotesque({ variable: "--font-display", subsets: ["latin"] });
const ui = Plus_Jakarta_Sans({ variable: "--font-ui", subsets: ["latin"] });
// the face the renderer actually uses for stressed words, so the readout can
// show a creator the real thing rather than the word "didone". The landing
// page sets its stressed words in the italic, so that cut is loaded too
// rather than left for the browser to fake by slanting the roman.
const didone = Bodoni_Moda({
  variable: "--font-didone", subsets: ["latin"], weight: ["700", "900"], style: ["normal", "italic"],
});

export const metadata: Metadata = {
  title: "Halfheaven",
  description: "Give your video someone else's edit.",
};

// Runs during HTML parsing, before first paint: a stored choice wins, otherwise
// the device's setting. Setting it any later flashes the other theme on load.
const THEME = `try{var t=localStorage.getItem("theme");if(t!=="light"&&t!=="dark")t=matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";document.documentElement.dataset.theme=t}catch(e){document.documentElement.dataset.theme="light"}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // The script above adds data-theme before React hydrates; the DOM is right.
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME }} />
      </head>
      <body className={`${display.variable} ${ui.variable} ${didone.variable}`}>{children}</body>
    </html>
  );
}
