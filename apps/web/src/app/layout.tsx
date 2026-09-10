import type { Metadata } from "next";
import { Bricolage_Grotesque, Plus_Jakarta_Sans, Bodoni_Moda } from "next/font/google";
import "./globals.css";

const display = Bricolage_Grotesque({ variable: "--font-display", subsets: ["latin"] });
const ui = Plus_Jakarta_Sans({ variable: "--font-ui", subsets: ["latin"] });
// the face the renderer actually uses for stressed words, so the readout can
// show a creator the real thing rather than the word "didone"
const didone = Bodoni_Moda({ variable: "--font-didone", subsets: ["latin"], weight: ["700", "900"] });

export const metadata: Metadata = {
  title: "Halfheaven",
  description: "Give your video someone else's edit.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${display.variable} ${ui.variable} ${didone.variable}`}>{children}</body>
    </html>
  );
}
