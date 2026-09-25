// Renders the launch video: every frame of index.html through headless
// Chromium, the synthesised soundtrack baked from the same page, both muxed by
// ffmpeg into out/halfheaven-launch.mp4 (1080x1920, 30fps).
//
//   node render.mjs                  the whole video
//   node render.mjs --out name.mp4   the whole video, under another name in out/
//   node render.mjs --stills 1,9.8   PNGs of those moments, into out/stills/
//   node render.mjs --preview        serve it; open the URL to watch with sound

import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { FPS, TOTAL_FRAMES, W, H } from "./cues.mjs";

const DIR = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(DIR, "out");
const TYPES = { ".html": "text/html", ".mjs": "text/javascript", ".js": "text/javascript" };

const args = process.argv.slice(2);
const flag = (name) => args.indexOf(name);

const server = http.createServer((req, res) => {
  const file = path.join(DIR, decodeURIComponent(new URL(req.url, "http://x").pathname));
  if (!file.startsWith(DIR) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    res.writeHead(404).end();
    return;
  }
  res.writeHead(200, { "content-type": TYPES[path.extname(file)] ?? "application/octet-stream" });
  fs.createReadStream(file).pipe(res);
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const base = `http://127.0.0.1:${server.address().port}/index.html`;

if (flag("--preview") >= 0) {
  console.log(`preview: ${base}?preview   (ctrl+c to stop)`);
} else {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  page.on("pageerror", (e) => { console.error("page error:", e.message); process.exitCode = 1; });
  await page.goto(base);
  await page.waitForSelector("body[data-ready]", { timeout: 30000 });
  const at = (t) => page.evaluate((t) => window.seek(t), t);

  if (flag("--stills") >= 0) {
    const dir = path.join(OUT, "stills");
    fs.mkdirSync(dir, { recursive: true });
    for (const t of args[flag("--stills") + 1].split(",").map(Number)) {
      await at(t);
      await page.screenshot({ path: path.join(dir, `${t.toFixed(2)}.png`) });
    }
    console.log(`stills in ${dir}`);
  } else {
    const wav = path.join(OUT, "soundtrack.wav");
    fs.writeFileSync(wav, Buffer.from(await page.evaluate(() => window.bakeAudio()), "base64"));

    const mp4 = path.join(OUT, flag("--out") >= 0 ? args[flag("--out") + 1] : "halfheaven-launch.mp4");
    const ff = spawn("ffmpeg", [
      "-y", "-loglevel", "error",
      "-f", "image2pipe", "-framerate", String(FPS), "-c:v", "mjpeg", "-i", "-",
      "-i", wav,
      "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", "-profile:v", "high",
      "-af", "alimiter=limit=0.84:level=false", // true-peak headroom after AAC
      "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
      "-shortest", "-movflags", "+faststart", mp4,
    ], { stdio: ["pipe", "inherit", "inherit"] });
    const done = new Promise((r, j) => ff.on("close", (c) => (c ? j(new Error(`ffmpeg exited ${c}`)) : r())));

    const started = Date.now();
    for (let f = 0; f < TOTAL_FRAMES; f++) {
      await at(f / FPS);
      const jpg = await page.screenshot({ type: "jpeg", quality: 95 });
      if (!ff.stdin.write(jpg)) await new Promise((r) => ff.stdin.once("drain", r));
      if (f % 60 === 0) process.stdout.write(`\rframe ${f}/${TOTAL_FRAMES}`);
    }
    ff.stdin.end();
    await done;
    console.log(`\r${TOTAL_FRAMES} frames in ${((Date.now() - started) / 1000).toFixed(0)}s -> ${mp4}`);
  }
  await browser.close();
  server.close();
}
