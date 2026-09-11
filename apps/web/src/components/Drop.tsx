"use client";

import { useRef, useState } from "react";

/** Somewhere to drop a video, or click to choose one.
 *  What the tile says is left to the caller, because it depends on what the
 *  slot is waiting for: nothing yet, a file being read, a file that is ready. */
export default function Drop({
  onFiles, multiple, disabled, accept = "video/*", className = "", children,
}: {
  onFiles: (files: File[]) => void;
  multiple?: boolean;
  disabled?: boolean;
  accept?: string;
  className?: string;
  children: React.ReactNode;
}) {
  const picker = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const take = (list: FileList | null) => { if (list?.length) onFiles(Array.from(list)); };
  const choose = () => { if (!disabled) picker.current?.click(); };

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled || undefined}
      className={`drop-zone${over ? " over" : ""} ${className}`}
      onClick={choose}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); choose(); } }}
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); if (!disabled) take(e.dataTransfer.files); }}
    >
      {/* Cleared after each pick so choosing the same file again still fires. */}
      <input ref={picker} type="file" accept={accept} multiple={multiple} hidden
             onClick={(e) => e.stopPropagation()}
             onChange={(e) => { take(e.target.files); e.target.value = ""; }} />
      {children}
    </div>
  );
}
