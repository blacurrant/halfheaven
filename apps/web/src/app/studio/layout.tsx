import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import s from "@/components/studio/studio.module.css";

// The studio's own faces. Scoped to this layout, so the landing page keeps its type.
const geist = Geist({ variable: "--font-geist", subsets: ["latin"] });
const mono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Studio · Halfheaven",
  description: "Point at a reel you love. Get your footage edited the same way.",
};

// Dark all the way to the browser's own chrome, so the footage is the lit thing.
export const viewport: Viewport = { themeColor: "#0A0A0B", colorScheme: "dark" };

export default function StudioLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className={`${geist.variable} ${mono.variable} ${s.root}`}>
      {/* Overscroll and the area behind the address bar show the page background.
          A plain <style> unmounts with this layout, so it cannot leak into / . */}
      <style>{"html,body{background:#0A0A0B}"}</style>
      {children}
    </div>
  );
}
