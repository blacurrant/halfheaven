"use client";

/** The glowing lines from the hero's panels to the phone. Drawn from measured
 *  positions rather than fixed coordinates, because the panels are tilted in
 *  3D and their heights move with the font. Each [data-wire] panel in the
 *  parent gets a line from its inner edge to the [data-wire-target] phone. */

import { useEffect, useRef, useState } from "react";

import s from "@/app/landing.module.css";

type Wire = { d: string; x: number; y: number };

export default function HeroWires() {
  const ref = useRef<SVGSVGElement>(null);
  const [wires, setWires] = useState<Wire[]>([]);
  const [size, setSize] = useState<[number, number]>([0, 0]);

  useEffect(() => {
    const root = ref.current?.parentElement;
    if (!root) return;
    const draw = () => {
      const box = root.getBoundingClientRect();
      const phone = root.querySelector<HTMLElement>("[data-wire-target]")?.getBoundingClientRect();
      if (!box.width || !phone) return;
      const midY = phone.top + phone.height / 2 - box.top;
      setWires([...root.querySelectorAll<HTMLElement>("[data-wire]")].map((el) => {
        const r = el.getBoundingClientRect();
        const left = el.dataset.wire === "left";
        const x = (left ? r.right : r.left) - box.left;
        const y = r.top + r.height / 2 - box.top;
        const x2 = (left ? phone.left + 4 : phone.right - 4) - box.left;
        const y2 = y + (midY - y) * 0.3; // bend a little toward the phone's middle
        const mx = (x + x2) / 2;
        return { d: `M${x} ${y}C${mx} ${y} ${mx} ${y2} ${x2} ${y2}`, x, y };
      }));
      setSize([box.width, box.height]);
    };
    draw();
    const ro = new ResizeObserver(draw);
    ro.observe(root);
    document.fonts?.ready.then(draw);
    return () => ro.disconnect();
  }, []);

  const [w, h] = size;
  return (
    <svg ref={ref} className={s.wires} viewBox={`0 0 ${w || 1} ${h || 1}`} fill="none">
      {wires.map((wire) => <path key={wire.d} d={wire.d} className={s.wireHalo} />)}
      {wires.map((wire) => <path key={wire.d} d={wire.d} className={s.wire} pathLength={1} />)}
      {wires.map((wire) => <circle key={wire.d} cx={wire.x} cy={wire.y} r="4.5" className={s.wireEnd} />)}
    </svg>
  );
}
