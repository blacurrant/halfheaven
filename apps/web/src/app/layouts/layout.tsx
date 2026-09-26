import type { Metadata, Viewport } from "next";
import { Bodoni_Moda, Geist, Geist_Mono } from "next/font/google";

import s from "@/components/studio/studio.module.css";

// The studio's faces and tokens, so this reads as the same product. The serif
// is for the wireframes that call for one (quiet luxury, the magazine cover),
// with the regular weight the root layout's copy of Bodoni doesn't load.
const geist = Geist({ variable: "--font-geist", subsets: ["latin"] });
const mono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });
const serif = Bodoni_Moda({ variable: "--font-wf-serif", subsets: ["latin"], weight: ["400", "700", "900"] });

export const metadata: Metadata = {
  title: "Ad layouts · Halfheaven",
  description: "Describe an ad. Jev picks the layout while you type.",
};

export const viewport: Viewport = { themeColor: "#0A0A0B", colorScheme: "dark" };

export default function LayoutsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className={`${geist.variable} ${mono.variable} ${serif.variable} ${s.root}`}>
      <style>{"html,body{background:#0A0A0B}"}</style>
      {children}
    </div>
  );
}
