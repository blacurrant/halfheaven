"use client";

import { useRef, useState } from "react";

type UploadItem = {
  file: File;
  id: string;
  progress: number; // 0-100
  status: "uploading" | "completed" | "error";
};

function formatKB(bytes: number) {
  return `${Math.round(bytes / 1024)} KB`;
}

function FileIcon({ name, type }: { name: string; type: string }) {
  const isVideo = type.startsWith("video/") || /\.(mp4|mov|m4a|webm)$/i.test(name);
  const isImage = type.startsWith("image/");
  const isPdf = type === "application/pdf" || /\.pdf$/i.test(name);
  if (isVideo) {
    return (
      <span className="w-9 h-9 rounded-lg bg-[#0a0a0f] text-white grid place-items-center shrink-0">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="5" width="14" height="13" rx="2"/><path d="M17 8l4-2v10l-4-2z" fill="currentColor" stroke="none"/><path d="M10 10l4 2-4 2z" fill="white" stroke="none"/></svg>
      </span>
    );
  }
  if (isImage) {
    return (
      <span className="w-9 h-9 rounded-lg bg-[#e8f0ff] text-[#46607B] grid place-items-center shrink-0 border border-black/5">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="M14 15l3-3 3 3"/><path d="M3 17l5-5 4 4"/></svg>
      </span>
    );
  }
  if (isPdf) {
    return (
      <span className="w-9 h-9 rounded-lg bg-white border border-black/10 grid place-items-center shrink-0 relative overflow-hidden">
        <span className="absolute bottom-1 text-[7px] font-bold bg-[#ff3b30] text-white px-1 rounded">PDF</span>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9aa0a6" strokeWidth="1.6"><path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/></svg>
      </span>
    );
  }
  return (
    <span className="w-9 h-9 rounded-lg bg-[#f3f0e8] grid place-items-center shrink-0 border border-black/5">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/></svg>
    </span>
  );
}

export default function Drop({
  onFiles,
  multiple,
  disabled,
  accept = "video/*",
  className = "",
  children,
  showTray = false,
}: {
  onFiles: (files: File[]) => void;
  multiple?: boolean;
  disabled?: boolean;
  accept?: string;
  className?: string;
  children: React.ReactNode;
  showTray?: boolean;
}) {
  const picker = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [url, setUrl] = useState("");
  const [items, setItems] = useState<UploadItem[]>([]);

  const take = (list: FileList | null) => {
    if (!list?.length) return;
    const files = Array.from(list);
    // add to internal tray with fake progress
    const newItems: UploadItem[] = files.map((f) => ({
      file: f,
      id: `${f.name}-${Date.now()}-${Math.random().toString(36).slice(2,6)}`,
      progress: 0,
      status: "uploading" as const,
    }));
    setItems((prev) => [...prev, ...newItems]);
    // simulate upload progress
    newItems.forEach((it) => {
      let p = 0;
      const t = setInterval(() => {
        p += Math.random() * 28 + 12;
        if (p >= 100) {
          p = 100;
          clearInterval(t);
          setItems((prev) => prev.map((x) => (x.id === it.id ? { ...x, progress: 100, status: "completed" as const } : x)));
        } else {
          setItems((prev) => prev.map((x) => (x.id === it.id ? { ...x, progress: Math.min(92, p) } : x)));
        }
      }, 180);
    });
    onFiles(files);
  };

  const choose = () => { if (!disabled) picker.current?.click(); };

  const removeItem = (id: string) => setItems((prev) => prev.filter((x) => x.id !== id));

  // If showTray is false, render simple drop-zone with Tailwind directly
  if (!showTray) {
    return (
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-disabled={disabled || undefined}
        className={`w-full flex flex-col items-center justify-center gap-1 border-[1.5px] border-dashed rounded-[10px] p-6 bg-[var(--card)] text-center cursor-pointer transition-colors ${over ? "border-[var(--accent-ink)] bg-[var(--accent-soft)]" : "border-[var(--line-2)]"} ${disabled ? "opacity-50 cursor-default" : ""} ${className}`}
        onClick={choose}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); choose(); } }}
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault(); setOver(false); if (disabled) return;
          if (e.dataTransfer.files && e.dataTransfer.files.length) take(e.dataTransfer.files);
          else {
            const f = (window as unknown as { __trayFile?: File }).__trayFile;
            if (f) { onFiles([f]); }
          }
        }}
      >
        <input ref={picker} type="file" accept={accept} multiple={multiple} hidden
               onClick={(e) => e.stopPropagation()}
               onChange={(e) => { take(e.target.files); e.target.value = ""; }} />
        {children}
      </div>
    );
  }

  // Full rounded modal as in Image 1
  return (
    <div className={`w-full max-w-[480px] bg-white rounded-[20px] border border-black/5 shadow-[0_12px_40px_rgba(0,0,0,0.12)] overflow-hidden ${className}`}>
      {/* header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-black/5">
        <div className="flex items-center gap-3">
          <span className="w-9 h-9 rounded-full border border-black/10 grid place-items-center text-[#7a7a82]">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 16a4 4 0 0 1-4-4 4 4 0 0 1 4-4"/><path d="M12 12V8"/><path d="M8 12l2 2 2-2"/><path d="M4 14v2a4 4 0 0 0 4 4h8a4 4 0 0 0 4-4v-2"/></svg>
          </span>
          <div>
            <div className="text-[14px] font-bold text-[#0a0a0f]">Upload files</div>
            <div className="text-[12px] text-[#6b7280]">Select and upload the files of your choice</div>
          </div>
        </div>
        <button className="w-7 h-7 grid place-items-center text-[#9aa0a6] hover:text-black" aria-label="Close">✕</button>
      </div>

      {/* drop zone */}
      <div className="p-4">
        <div
          role="button"
          tabIndex={0}
          onClick={choose}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); choose(); } }}
          onDragOver={(e) => { e.preventDefault(); setOver(true); }}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => { e.preventDefault(); setOver(false); take(e.dataTransfer.files); }}
          className={`rounded-[16px] border-[1.5px] border-dashed ${over ? "border-[#46607B] bg-[#DDE6EE]" : "border-black/15 bg-[#fafafa]"} py-8 px-4 flex flex-col items-center text-center gap-2 cursor-pointer transition-colors`}
        >
          <span className="w-8 h-8 rounded-full bg-white border border-black/10 grid place-items-center text-[#0a0a0f]">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 16a5 5 0 0 0 5-5 5 5 0 0 0-5-5"/><path d="M12 12V7"/><path d="M9 9l3-3 3 3"/><path d="M4 16v2a4 4 0 0 0 4 4h8a4 4 0 0 0 4-4v-2"/></svg>
          </span>
          <div className="text-[14px] font-semibold text-[#0a0a0f]">Choose a file or drag & drop it here.</div>
          <div className="text-[12px] text-[#6b7280]">JPEG, PNG, PDF, and MP4 formats, up to 50 MB.</div>
          <button type="button" onClick={(e) => { e.stopPropagation(); choose(); }} className="mt-2 h-8 px-4 rounded-full border border-black/10 bg-white text-[13px] font-semibold hover:bg-black hover:text-white transition-colors">Browse File</button>
          <input ref={picker} type="file" accept={accept} multiple={multiple} hidden onChange={(e) => { take(e.target.files); e.target.value = ""; }} />
        </div>

        {/* file list */}
        {items.length > 0 && (
          <div className="mt-4 space-y-2">
            {items.map((it) => (
              <div key={it.id} draggable onDragStart={(e) => { e.dataTransfer.setData("text/plain", it.file.name); e.dataTransfer.effectAllowed = "copy"; (window as unknown as { __trayFile?: File }).__trayFile = it.file; }} className="flex items-center gap-3 p-3 rounded-[12px] border border-black/5 bg-white cursor-grab active:cursor-grabbing">
                <FileIcon name={it.file.name} type={it.file.type} />
                <div className="flex-1 min-w-0 text-left">
                  <div className="text-[13px] font-semibold text-[#0a0a0f] truncate">{it.file.name}</div>
                  <div className="text-[11px] text-[#6b7280] flex items-center gap-1.5">
                    <span>{it.status === "uploading" ? `0 KB of ${formatKB(it.file.size)}` : `${formatKB(it.file.size)} of ${formatKB(it.file.size)}`}</span>
                    <span className="w-1 h-1 rounded-full bg-black/20" />
                    {it.status === "uploading" ? <span className="text-[#46607B] flex items-center gap-1"><span className="w-3 h-3 rounded-full border-2 border-[#46607B] border-t-transparent animate-spin" /> Uploading…</span> : <span className="text-[#0a7a2e] flex items-center gap-1">✅ Completed</span>}
                  </div>
                  {it.status === "uploading" && (
                    <div className="mt-1.5 h-1.5 rounded-full bg-black/5 overflow-hidden">
                      <div className="h-full bg-[#46607B] transition-all" style={{ width: `${it.progress}%` }} />
                    </div>
                  )}
                </div>
                <button onClick={() => removeItem(it.id)} className="w-7 h-7 grid place-items-center text-[#9aa0a6] hover:text-black">
                  {it.status === "uploading" ? "✕" : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M9 3h6l1 2h4v2H4V5h4z"/><path d="M8 9v10a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2V9"/><path d="M10 13h4"/></svg>}
                </button>
              </div>
            ))}
          </div>
        )}

        {/* OR */}
        <div className="my-4 flex items-center gap-3">
          <div className="h-px flex-1 bg-black/10" />
          <span className="text-[11px] tracking-widest text-[#9aa0a6]">OR</span>
          <div className="h-px flex-1 bg-black/10" />
        </div>

        {/* URL import */}
        <div>
          <div className="text-[13px] font-semibold text-[#0a0a0f] flex items-center gap-1.5">Import from URL Link <span className="w-4 h-4 rounded-full bg-black/5 grid place-items-center text-[10px]">i</span></div>
          <div className="mt-2 flex items-center gap-2 rounded-[10px] border border-black/10 bg-[#fafafa] px-3 py-2">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#9aa0a6" strokeWidth="1.8"><path d="M10 12a5 5 0 0 1 7 0l1 1a5 5 0 0 1-7 7l-1-1"/><path d="M14 12a5 5 0 0 0-7 0l-1 1a5 5 0 0 0 7 7l1-1"/></svg>
            <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="Paste file URL" className="flex-1 bg-transparent outline-none text-[13px] placeholder:text-[#9aa0a6]" />
            {url && <button onClick={() => setUrl("")} className="text-[#9aa0a6] hover:text-black">✕</button>}
          </div>
        </div>
      </div>

      {/* hidden children fallback for simple usage */}
      <div className="hidden">{children}</div>
    </div>
  );
}
