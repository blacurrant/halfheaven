/**
 * Twenty ad creative wireframes, as data.
 *
 * Each layout is a frame of a fixed format and a list of blocks placed in
 * percent of that frame (x and w of its width, y and h of its height), so the
 * same spec draws a thumbnail and a full preview. Text sizes are percent of the
 * frame's width (`cqw` in the renderer), for the same reason.
 *
 * Blocks pull their words from a `Copy` object by path (`f`), so the chat can
 * fill a wireframe as it goes; a block with no copy yet draws as skeleton bars.
 *
 * `when` is written for Jev, not for people: it is the criterion Jev reads
 * when choosing a layout for what the user described, so it names the
 * situations a layout fits rather than how it looks.
 */

export type Format = "1:1" | "4:5" | "9:16" | "16:9";

export const RATIO: Record<Format, number> = { "1:1": 1, "4:5": 4 / 5, "9:16": 9 / 16, "16:9": 16 / 9 };

export type Kind =
  | "img" | "scrim" | "box" | "rule" | "text" | "link" | "btn" | "chip" | "logo" | "burst"
  | "stars" | "avatar" | "icon" | "mark" | "knob" | "timer" | "dots" | "progress" | "bars"
  | "qr" | "barcode" | "phone" | "bubble" | "leader";

export type Block = {
  k: Kind;
  /** Left, top, width, height in percent of the frame. Round kinds ignore h. */
  x: number; y: number; w: number; h?: number;
  /** Copy path(s): "headline", "stats.0.value", "{stats.0.value} {stats.0.label}", alternatives split by "|". */
  f?: string;
  /** Literal text, part of the layout itself ("Before", "1/5"). */
  t?: string;
  /** Shown, dimmed, until copy arrives. Without it an empty text block draws skeleton bars. */
  ph?: string;
  /** Text size in percent of frame width. */
  s?: number;
  /** Font weight. */
  wt?: number;
  a?: "l" | "c" | "r";
  /** Text colour: 1 primary, 2 secondary, 3 faint, "dark" for text on light fills. */
  c?: 1 | 2 | 3 | "dark";
  /** Line clamp, and the number of skeleton bars when empty. */
  n?: number;
  caps?: boolean; serif?: boolean; strike?: boolean; mono?: boolean;
  /** Caption style: the words sit on their own solid band, like reel captions. */
  cap?: boolean;
  /** Centre the words vertically in the block. */
  mid?: boolean;
  /** Average glyph width in em, for faces the default estimate gets wrong (a
   *  heavy serif masthead); such blocks may also shrink further to fit. */
  fit?: number;
  /** Letter spacing in em. */
  ls?: number;
  /** Variant: fills for boxes/chips/buttons, glyphs for icons and marks. */
  v?: string;
  /** Placeholder label drawn inside an image. */
  label?: string;
  /** End of a leader line, in percent of the frame. */
  x2?: number; y2?: number;
  /** Corner radius in percent of frame width, where the kind's default is wrong. */
  r?: number;
};

export type Copy = {
  brand?: string; headline?: string; subhead?: string; body?: string; cta?: string;
  offer?: string; price?: string; was?: string; code?: string; badge?: string;
  quote?: string; author?: string; role?: string; rating?: string; rival?: string;
  date?: string; time?: string; place?: string;
  stats?: { value: string; label: string }[];
  steps?: string[];
  points?: string[];
  items?: { name: string; price?: string }[];
  chat?: { me: boolean; text: string }[];
};

export type Layout = {
  id: string;
  name: string;
  format: Format;
  when: string;
  blocks: Block[];
};

// Short constructors keep the twenty specs readable as layouts, not as JSON.
type Opt = Partial<Block>;
const img = (x: number, y: number, w: number, h: number, label?: string, o: Opt = {}): Block =>
  ({ k: "img", x, y, w, h, label, ...o });
const text = (x: number, y: number, w: number, h: number, f: string, o: Opt = {}): Block =>
  ({ k: "text", x, y, w, h, f, ...o });
const lit = (x: number, y: number, w: number, h: number, t: string, o: Opt = {}): Block =>
  ({ k: "text", x, y, w, h, t, ...o });
const bars = (x: number, y: number, w: number, h: number, n = 2, o: Opt = {}): Block =>
  ({ k: "text", x, y, w, h, n, ...o });
const btn = (x: number, y: number, w: number, h: number, o: Opt = {}): Block =>
  ({ k: "btn", x, y, w, h, f: "cta", ph: "Shop now", s: 3.4, wt: 600, ...o });
const chip = (x: number, y: number, w: number, h: number, o: Opt = {}): Block =>
  ({ k: "chip", x, y, w, h, s: 2.6, wt: 600, ...o });
const logo = (x: number, y: number, w: number, h: number, o: Opt = {}): Block =>
  ({ k: "logo", x, y, w, h, f: "brand", s: 2.8, ...o });
const box = (x: number, y: number, w: number, h: number, v = "card", o: Opt = {}): Block =>
  ({ k: "box", x, y, w, h, v, ...o });
const rule = (x: number, y: number, w: number, h: number, o: Opt = {}): Block => ({ k: "rule", x, y, w, h, ...o });
const round = (k: Kind, x: number, y: number, w: number, o: Opt = {}): Block => ({ k, x, y, w, ...o });
const leader = (x: number, y: number, x2: number, y2: number): Block => ({ k: "leader", x, y, w: 0, x2, y2 });

export const LAYOUTS: Layout[] = [
  {
    id: "hero",
    name: "Full-bleed hero",
    format: "4:5",
    when:
      "One striking photo carries the ad with a short headline and one button over it. The safe default for brand awareness, a product launch, fashion, food, travel or lifestyle when the picture sells and there is no special structure (no offer, steps, review, numbers or event).",
    blocks: [
      img(0, 0, 100, 100, "Hero photo", { v: "bg" }),
      { k: "scrim", x: 0, y: 42, w: 100, h: 58 },
      logo(6, 4.5, 22, 5),
      chip(72, 4.8, 22, 4.4, { f: "badge", ph: "New", v: "glass" }),
      text(6, 62, 82, 15, "headline", { s: 8.2, wt: 700, n: 2, ls: -0.03 }),
      text(6, 78, 70, 6, "subhead", { s: 3.4, c: 2, n: 2 }),
      btn(6, 88.5, 34, 6.5),
      text(58, 89.6, 36, 4.5, "price", { s: 4.6, wt: 700, a: "r" }),
    ],
  },
  {
    id: "before-after",
    name: "Before / After",
    format: "1:1",
    when:
      "Shows a transformation side by side: before vs after, results after weeks of use, old vs new, problem photo next to the result. Skincare, haircare, fitness, weight loss, cleaning, renovation, dental, photo or video editing apps.",
    blocks: [
      text(6, 5, 66, 7, "headline", { s: 5.6, wt: 700, n: 1, ls: -0.02 }),
      logo(76, 5, 18, 6),
      img(0, 16, 50, 66, "Before"),
      img(50, 16, 50, 66, "After", { v: "lit" }),
      chip(3.5, 19.5, 17, 5.4, { t: "BEFORE", v: "glass", s: 2.4, ls: 0.12 }),
      chip(79.5, 19.5, 17, 5.4, { t: "AFTER", v: "solid", s: 2.4, ls: 0.12 }),
      rule(49.7, 16, 0.6, 66, { v: "light" }),
      round("knob", 44.5, 44, 11),
      chip(62, 74, 34, 5.2, { f: "badge", ph: "4 weeks later", v: "glass", s: 2.4 }),
      text(6, 86, 56, 8, "body|points.0", { s: 2.8, c: 2, n: 2 }),
      btn(66, 85, 28, 8.5, { s: 3.2 }),
    ],
  },
  {
    id: "product-grid",
    name: "Product grid",
    format: "4:5",
    when:
      "Several products or variants at once, each with a name and price: a collection, a range of flavours, colours or sizes, a catalogue, shop-the-look, bestsellers, a menu. E-commerce with more than one item.",
    blocks: [
      logo(6, 4, 20, 4.5),
      text(6, 10.5, 88, 6, "headline", { s: 6.2, wt: 700, n: 1, ls: -0.025 }),
      text(6, 17, 72, 3.5, "subhead", { s: 3, c: 2, n: 1 }),
      ...[0, 1, 2, 3].flatMap((i) => {
        const x = i % 2 ? 51 : 6, y = i < 2 ? 23.5 : 53;
        return [
          img(x, y, 43, 20, `Product ${i + 1}`),
          text(x, y + 21.4, 27, 3.4, `items.${i}.name`, { s: 3, wt: 500, n: 1 }),
          text(x + 29, y + 21.4, 14, 3.4, `items.${i}.price`, { s: 3, wt: 700, a: "r", n: 1 }),
        ];
      }),
      chip(8.5, 25.5, 19, 4, { f: "badge", ph: "Bestseller", v: "solid", s: 2.2 }),
      btn(6, 85.5, 88, 7.5, { r: 1.2 }),
    ],
  },
  {
    id: "big-offer",
    name: "Big offer",
    format: "1:1",
    when:
      "The deal itself is the hero: a sale, percent off, flat price, buy-one-get-one, festive or Diwali sale, clearance, coupon code, limited-time price drop. Loud, direct-response, discount-led.",
    blocks: [
      logo(6, 6, 20, 6),
      chip(66, 6.3, 28, 5.4, { f: "badge", ph: "Limited time", v: "outline" }),
      text(6, 19, 52, 5, "headline", { s: 4, wt: 600, c: 2, n: 1 }),
      text(6, 24, 52, 28, "offer", { s: 13, wt: 800, n: 2, ls: -0.045, ph: "50% OFF" }),
      img(58, 20, 38, 48, "Product"),
      { k: "burst", x: 72, y: 58, w: 24, f: "price", ph: "₹999", s: 3.8, wt: 800 },
      text(6, 56, 22, 5, "was", { s: 3.6, c: 3, strike: true, n: 1 }),
      text(28, 55.6, 26, 5.5, "price", { s: 4.4, wt: 700, n: 1 }),
      chip(6, 66, 36, 7, { f: "code", ph: "CODE", v: "dashed", s: 3.2, mono: true, ls: 0.08 }),
      btn(6, 81, 40, 9.5, { s: 3.6 }),
      lit(52, 85, 42, 4, "*T&C apply", { s: 2.2, c: 3, a: "r" }),
    ],
  },
  {
    id: "testimonial",
    name: "Testimonial",
    format: "4:5",
    when:
      "A customer review or quote leads: social proof, a star rating, what customers say, a testimonial, an influencer or doctor endorsement, a case-study quote, word of mouth.",
    blocks: [
      logo(6, 5, 20, 4.5),
      { k: "stars", x: 64, y: 5.2, w: 30, h: 4 },
      lit(5, 13, 16, 12, "“", { s: 20, wt: 700, c: 3, serif: true }),
      text(6, 27, 88, 32, "quote", { s: 6, wt: 600, n: 5, ls: -0.02 }),
      rule(6, 62, 10, 0.4, { v: "light" }),
      round("avatar", 6, 66.5, 11),
      text(20, 67.4, 42, 4, "author", { s: 3.4, wt: 600, n: 1 }),
      text(20, 71.6, 42, 3.4, "role", { s: 2.8, c: 3, n: 1, ph: "Verified buyer" }),
      img(62, 77, 32, 18, "Product"),
      btn(6, 86.5, 40, 7),
    ],
  },
  {
    id: "app-showcase",
    name: "App showcase",
    format: "4:5",
    when:
      "Promotes a mobile app, SaaS or digital product by showing its screen inside a phone, with feature callouts and store badges: app install, download, fintech, edtech, games, subscriptions, tools.",
    blocks: [
      text(8, 5, 84, 11, "headline", { s: 6.2, wt: 700, n: 2, a: "c", ls: -0.025 }),
      text(14, 16.5, 72, 3.5, "subhead", { s: 3, c: 2, n: 1, a: "c" }),
      { k: "phone", x: 33, y: 23, w: 34, h: 57 },
      chip(3, 31, 27, 5, { f: "points.0", v: "outline", s: 2.3 }),
      leader(30, 33.5, 37, 38),
      chip(70, 45, 27, 5, { f: "points.1", v: "outline", s: 2.3 }),
      leader(70, 47.5, 63, 52),
      chip(3, 59, 27, 5, { f: "points.2", v: "outline", s: 2.3 }),
      leader(30, 61.5, 37, 66),
      text(20, 82.2, 60, 3.4, "rating", { s: 2.6, c: 2, a: "c", n: 1, ph: "★ 4.8 · 1M+ downloads" }),
      { k: "btn", x: 20, y: 87.5, w: 28.5, h: 6.5, t: "App Store", v: "outline", s: 2.6, wt: 600 },
      { k: "btn", x: 51.5, y: 87.5, w: 28.5, h: 6.5, t: "Google Play", v: "outline", s: 2.6, wt: 600 },
    ],
  },
  {
    id: "countdown",
    name: "Countdown",
    format: "9:16",
    when:
      "Urgency with a clock: a sale or drop that ends soon, launch countdown, flash sale, last chance, early-bird deadline, limited stock, ends tonight. Vertical story or reel format.",
    blocks: [
      { k: "progress", x: 4, y: 1.4, w: 92, h: 0.5 },
      logo(6, 4, 24, 3.4, { s: 3.4 }),
      chip(6, 10.5, 36, 3.4, { f: "badge", ph: "Flash sale", v: "solid", s: 3.2 }),
      text(6, 15.5, 88, 12.5, "headline", { s: 10.5, wt: 800, n: 2, ls: -0.035 }),
      text(6, 28.8, 84, 5, "subhead", { s: 4.2, c: 2, n: 2 }),
      { k: "timer", x: 6, y: 36.5, w: 88, h: 11, s: 9 },
      img(6, 51, 88, 31, "Product"),
      chip(60, 53, 32, 4, { f: "offer", ph: "40% OFF", v: "solid", s: 4, wt: 800 }),
      btn(6, 85.5, 88, 5.6, { s: 4.6 }),
      lit(6, 92.6, 88, 3, "↑  Swipe up", { s: 3.4, c: 3, a: "c" }),
    ],
  },
  {
    id: "three-steps",
    name: "Three steps",
    format: "4:5",
    when:
      "Explains how it works in three simple steps: onboarding, a process, a routine, how to order or book, how to use the product, a service explained, a recipe method, 1-2-3.",
    blocks: [
      logo(6, 5, 20, 4.5),
      text(6, 12, 88, 12, "headline", { s: 6.4, wt: 700, n: 2, ls: -0.025 }),
      text(6, 24, 80, 3.6, "subhead", { s: 3, c: 2, n: 1 }),
      ...[0, 1, 2].flatMap((i) => {
        const y = 32 + i * 15;
        return [
          round("mark", 6, y, 11, { t: String(i + 1), s: 4.4, wt: 700, v: "solid" }),
          text(21, y + 0.8, 44, 4.2, `steps.${i}`, { s: 3.8, wt: 600, n: 1 }),
          bars(21, y + 5.6, 42, 5, 2, { s: 2.6, c: 3 }),
          ...(i < 2 ? [rule(11.35, y + 9.4, 0.3, 5.2)] : []),
        ];
      }),
      img(68, 32, 26, 40, "Product"),
      btn(6, 80, 46, 8),
      text(56, 81.5, 38, 5, "price", { s: 4.4, wt: 700, a: "r", n: 1 }),
      text(6, 91.5, 88, 3, "body", { s: 2.3, c: 3, n: 1 }),
    ],
  },
  {
    id: "ugc-story",
    name: "Creator video",
    format: "9:16",
    when:
      "Looks like a real person's video, not an ad: UGC, a creator or influencer talking to camera, selfie, unboxing, get-ready-with-me, reaction, honest review, day-in-my-life. Reels or TikTok style with burned-in captions.",
    blocks: [
      img(0, 0, 100, 100, "Creator video", { v: "bg" }),
      { k: "progress", x: 3, y: 1.2, w: 94, h: 0.45 },
      round("avatar", 4, 3, 9),
      text(15.5, 3.7, 40, 2.6, "brand", { s: 3.6, wt: 600, n: 1 }),
      chip(70, 3.4, 26, 2.8, { t: "Sponsored", v: "glass", s: 2.8, wt: 500 }),
      text(8, 40, 84, 11, "headline", { s: 7, wt: 800, n: 2, a: "c", cap: true }),
      text(14, 52.5, 72, 5, "subhead", { s: 4.4, wt: 600, n: 1, a: "c", cap: true }),
      round("icon", 86, 56, 9, { v: "heart" }),
      round("icon", 86, 62.5, 9, { v: "chat" }),
      round("icon", 86, 69, 9, { v: "send" }),
      box(4, 78.5, 78, 9.5, "glass"),
      img(6, 79.6, 14, 7.3, undefined, { v: "lit" }),
      text(23, 80.2, 56, 3, "items.0.name|headline", { s: 3.6, wt: 600, n: 1 }),
      text(23, 84, 40, 2.8, "price", { s: 3.4, c: 2, n: 1 }),
      btn(4, 90, 92, 5.6, { s: 4.4 }),
    ],
  },
  {
    id: "carousel",
    name: "Carousel",
    format: "1:1",
    when:
      "A swipeable carousel told card by card: a listicle, '5 reasons', tips, several features or products one per card, a lookbook sequence, a story across frames, educational threads.",
    blocks: [
      box(4, 6, 78, 81, "card"),
      img(4, 6, 78, 47, "Card 1"),
      chip(7, 9, 12, 5, { t: "1/5", v: "glass", s: 2.6, mono: true }),
      text(8, 57, 70, 10, "headline", { s: 5.2, wt: 700, n: 2, ls: -0.02 }),
      text(8, 68, 70, 7, "subhead", { s: 3, c: 2, n: 2 }),
      btn(8, 77.5, 26, 6.2, { s: 2.8, v: "outline" }),
      box(85, 10, 20, 73, "card"),
      img(85, 10, 20, 43),
      round("icon", 76, 39, 10, { v: "arrow-solid" }),
      { k: "dots", x: 34, y: 91, w: 32, h: 3 },
    ],
  },
  {
    id: "luxury-minimal",
    name: "Quiet luxury",
    format: "4:5",
    when:
      "Premium and understated with lots of empty space, one product and very little text: luxury, jewellery, perfume, watches, designer fashion, interiors, fine dining, a high-end brand that should whisper.",
    blocks: [
      box(3, 2.4, 94, 95.2, "outline"),
      text(25, 6.5, 50, 4, "brand", { s: 3.2, wt: 500, a: "c", caps: true, ls: 0.35, n: 1 }),
      rule(46, 12.5, 8, 0.2, { v: "light" }),
      img(28, 20, 44, 46, "Product"),
      text(12, 71, 76, 7, "headline", { s: 5.4, wt: 400, a: "c", serif: true, n: 1, ls: -0.01 }),
      text(22, 79, 56, 3.2, "subhead", { s: 2.6, c: 2, a: "c", n: 1 }),
      { k: "link", x: 36, y: 88, w: 28, h: 3.4, f: "cta", ph: "Discover", s: 2.6, a: "c", caps: true, ls: 0.2 },
    ],
  },
  {
    id: "vs-table",
    name: "Us vs them",
    format: "4:5",
    when:
      "Compares against a competitor or the old way of doing things: us vs them, a comparison table, why switch, with ticks and crosses, better than the rest, alternatives, feature checklist.",
    blocks: [
      logo(40, 4, 20, 4.5),
      text(6, 11, 88, 12, "headline", { s: 6.2, wt: 700, n: 2, a: "c", ls: -0.025 }),
      box(46, 25, 23, 56, "hi"),
      text(46, 27, 23, 4, "brand", { s: 3.2, wt: 700, a: "c", n: 1, ph: "Us" }),
      text(71, 27, 23, 4, "rival", { s: 3.2, c: 2, a: "c", n: 1, ph: "Others" }),
      ...[0, 1, 2, 3, 4].flatMap((i) => {
        const y = 34 + i * 9.2;
        return [
          text(6, y + 2, 38, 4, `points.${i}`, { s: 3, n: 1 }),
          round("mark", 53.5, y + 0.9, 8, { v: "check" }),
          round("mark", 78.5, y + 0.9, 8, { v: "cross" }),
          ...(i < 4 ? [rule(6, y + 8.6, 88, 0.15)] : []),
        ];
      }),
      btn(6, 86, 88, 7.5, { r: 1.2 }),
    ],
  },
  {
    id: "event-poster",
    name: "Event poster",
    format: "4:5",
    when:
      "Promotes an event with a date, time and place: a concert, workshop, meetup, store opening, festival, pop-up, launch party, conference, match screening, tickets or RSVP.",
    blocks: [
      img(0, 0, 100, 48, "Event image"),
      logo(6, 4, 20, 4.5),
      chip(70, 4.2, 24, 4.4, { f: "badge", ph: "Free entry", v: "glass" }),
      box(6, 38, 20, 17, "light"),
      text(7, 38, 18, 17, "date", { s: 5.2, wt: 800, a: "c", c: "dark", n: 2, caps: true, mid: true, ph: "OCT 12" }),
      text(30, 50, 64, 11, "headline", { s: 6.2, wt: 800, n: 2, ls: -0.025 }),
      text(30, 61.5, 64, 3.5, "subhead", { s: 3, c: 2, n: 1 }),
      round("icon", 6, 67.5, 6, { v: "clock" }),
      text(15, 68.2, 50, 3.6, "time", { s: 3.2, n: 1, ph: "7 PM onwards" }),
      round("icon", 6, 74.5, 6, { v: "pin" }),
      text(15, 75.2, 50, 3.6, "place", { s: 3.2, n: 1 }),
      round("qr", 77, 66, 17),
      rule(6, 83, 88, 0.2),
      btn(6, 87, 48, 7, { ph: "Get tickets" }),
      text(60, 88.4, 34, 4.4, "price", { s: 4.2, wt: 700, a: "r", n: 1 }),
    ],
  },
  {
    id: "callouts",
    name: "Feature callouts",
    format: "1:1",
    when:
      "One product in the centre with labelled lines pointing at its parts: what's inside, ingredients, anatomy of the product, tech specs, key benefits around it, materials, how it is made.",
    blocks: [
      text(6, 5, 88, 7, "headline", { s: 5.8, wt: 700, a: "c", n: 1, ls: -0.025 }),
      text(15, 12.5, 70, 4, "subhead", { s: 3, c: 2, a: "c", n: 1 }),
      img(35, 21, 30, 58, "Product"),
      text(4, 25, 26, 9, "points.0", { s: 3, wt: 600, a: "r", n: 2 }),
      leader(31, 28, 40, 33),
      text(4, 57, 26, 9, "points.1", { s: 3, wt: 600, a: "r", n: 2 }),
      leader(31, 60, 40, 56),
      text(70, 31, 26, 9, "points.2", { s: 3, wt: 600, n: 2 }),
      leader(69, 34, 60, 39),
      text(70, 63, 26, 9, "points.3", { s: 3, wt: 600, n: 2 }),
      leader(69, 66, 60, 63),
      logo(4, 88, 16, 5.5),
      btn(34, 84.5, 32, 8.5, { s: 3.2 }),
      text(74, 88, 22, 5, "price", { s: 3.8, wt: 700, a: "r", n: 1 }),
    ],
  },
  {
    id: "listing",
    name: "Listing card",
    format: "4:5",
    when:
      "A listing sold on location, size, specs and price: real estate, flats and villas, rentals, hotels and stays, holiday packages, cars and bikes, co-working. Photo gallery plus key specs.",
    blocks: [
      img(0, 0, 100, 52, "Main photo"),
      chip(5, 4, 24, 4.5, { f: "badge", ph: "Just listed", v: "solid" }),
      chip(5, 44, 36, 6, { f: "price", ph: "₹1.2 Cr", v: "glass", s: 4.4, wt: 700 }),
      img(5, 55, 28.6, 13),
      img(35.7, 55, 28.6, 13),
      img(66.4, 55, 28.6, 13, undefined, { v: "dim" }),
      lit(66.4, 59, 28.6, 5, "+12", { s: 3.8, wt: 600, a: "c" }),
      text(5, 71, 90, 5, "headline", { s: 4.6, wt: 700, n: 1, ls: -0.02 }),
      ...[0, 1, 2].flatMap((i) => [
        round("icon", 5 + i * 30, 77.4, 4.6, { v: ["bed", "bath", "area"][i] }),
        text(11 + i * 30, 77.6, 23, 3.4, `{stats.${i}.value} {stats.${i}.label}`, { s: 2.8, n: 1 }),
      ]),
      text(5, 82.6, 60, 3.2, "place", { s: 2.7, c: 2, n: 1 }),
      rule(5, 87, 90, 0.2),
      round("avatar", 5, 89.2, 7.5),
      text(14.5, 89.6, 40, 3, "author", { s: 2.8, wt: 600, n: 1 }),
      text(14.5, 93, 40, 2.6, "role", { s: 2.4, c: 3, n: 1, ph: "Agent" }),
      btn(60, 89, 35, 7, { s: 3, ph: "Book a visit" }),
    ],
  },
  {
    id: "webinar",
    name: "Webinar / course",
    format: "16:9",
    when:
      "Promotes a webinar, course, masterclass, podcast or talk led by a named expert, coach or founder: free live class, register now, learn a skill, speaker headshot. Also landscape LinkedIn or B2B link ads.",
    blocks: [
      img(62, 0, 38, 100, "Speaker"),
      logo(4, 7, 12, 7.5, { s: 1.5 }),
      chip(4, 20, 24, 7.5, { f: "badge", ph: "Free live masterclass", v: "solid", s: 1.5 }),
      text(4, 31, 54, 22, "headline", { s: 3.6, wt: 800, n: 2, ls: -0.03 }),
      text(4, 54, 52, 9, "subhead", { s: 1.6, c: 2, n: 2 }),
      ...[0, 1, 2].flatMap((i) => [
        round("mark", 4, 65 + i * 7, 2.4, { v: "check" }),
        text(8, 65.4 + i * 7, 48, 5, `points.${i}`, { s: 1.5, n: 1 }),
      ]),
      chip(4, 88, 16, 8, { f: "date", ph: "Sat, Oct 12", v: "outline", s: 1.4 }),
      chip(21.5, 88, 13, 8, { f: "time", ph: "7 PM IST", v: "outline", s: 1.4 }),
      btn(38, 87, 20, 10, { ph: "Register free", s: 1.7 }),
      box(64, 79, 32, 16, "glass"),
      text(66, 81.5, 28, 5.5, "author", { s: 1.7, wt: 600, n: 1 }),
      text(66, 88, 28, 4.5, "role", { s: 1.3, c: 2, n: 1 }),
    ],
  },
  {
    id: "stats",
    name: "Big numbers",
    format: "1:1",
    when:
      "Leads with numbers and proof: results, data, statistics, growth, savings, ROI, '10,000+ customers', clinical results, performance claims, milestones, an infographic of three figures.",
    blocks: [
      logo(6, 6, 18, 5.5),
      text(6, 15, 88, 13, "headline", { s: 5.8, wt: 700, n: 2, ls: -0.025 }),
      ...[0, 1, 2].flatMap((i) => [
        text(6 + i * 31, 33, 26, 11, `stats.${i}.value`, { s: 9, wt: 800, n: 1, ls: -0.04 }),
        text(6 + i * 31, 45, 26, 8, `stats.${i}.label`, { s: 2.7, c: 2, n: 2 }),
        ...(i < 2 ? [rule(34 + i * 31, 33, 0.25, 20)] : []),
      ]),
      { k: "bars", x: 6, y: 60, w: 54, h: 22 },
      img(66, 58, 28, 26, "Product"),
      text(6, 86.5, 56, 3, "body", { s: 2.2, c: 3, n: 1, ph: "Source: internal study, 2026" }),
      btn(66, 87, 28, 7.5, { s: 3 }),
    ],
  },
  {
    id: "chat-thread",
    name: "Chat thread",
    format: "9:16",
    when:
      "Looks like a text or DM conversation: WhatsApp or iMessage chat bubbles, a funny or relatable exchange, a friend recommending the product, a customer asking and the brand replying, dialogue-led humour.",
    blocks: [
      box(0, 0, 100, 9, "card"),
      lit(3, 2.9, 5, 3, "‹", { s: 7, c: 2 }),
      round("avatar", 10, 2.1, 10),
      text(23, 2.6, 50, 2.4, "brand", { s: 3.8, wt: 600, n: 1 }),
      lit(23, 5.2, 40, 2, "online", { s: 2.8, c: 3 }),
      { k: "bubble", x: 5, y: 13, w: 62, h: 6.4, f: "chat.0.text", s: 3.6, n: 2 },
      { k: "bubble", x: 35, y: 21.5, w: 60, h: 5, f: "chat.1.text", v: "me", s: 3.6, n: 2 },
      { k: "bubble", x: 5, y: 28.5, w: 56, h: 8.6, f: "chat.2.text", s: 3.6, n: 3 },
      { k: "bubble", x: 35, y: 39.2, w: 60, h: 6.4, f: "chat.3.text", v: "me", s: 3.6, n: 2 },
      { k: "bubble", x: 5, y: 47.8, w: 50, h: 5, f: "chat.4.text", s: 3.6, n: 2 },
      { k: "bubble", x: 5, y: 57, w: 16, h: 3.6, t: "• • •", s: 3.6 },
      box(35, 63, 60, 21, "card"),
      img(35, 63, 60, 13, undefined, { v: "lit" }),
      text(38, 77.4, 54, 2.6, "headline", { s: 3.4, wt: 600, n: 1 }),
      text(38, 80.6, 40, 2.4, "price", { s: 3, c: 2, n: 1 }),
      btn(5, 88.5, 90, 5.6, { s: 4.4 }),
    ],
  },
  {
    id: "editorial-cover",
    name: "Magazine cover",
    format: "4:5",
    when:
      "Styled like a magazine cover with a huge masthead and cover lines: editorial, fashion, beauty, lifestyle brands, a collab or brand story, founder feature, 'the issue', PR-style storytelling.",
    blocks: [
      img(0, 0, 100, 100, "Cover photo", { v: "bg" }),
      text(3, 2, 94, 15, "brand", { s: 17, wt: 900, a: "c", serif: true, caps: true, n: 1, ls: -0.02, mid: true, fit: 0.78, ph: "MASTHEAD" }),
      text(5, 17.4, 40, 2.6, "date", { s: 2.2, c: 2, caps: true, n: 1, ls: 0.14, ph: "ISSUE 01 · 2026" }),
      ...[0, 1, 2].flatMap((i) => [
        text(5, 29 + i * 12, 42, 4.4, `points.${i}`, { s: 3, wt: 700, n: 1, caps: true, ls: 0.02 }),
        bars(5, 34 + i * 12, 28, 3, 1, { s: 2.4, c: 3 }),
      ]),
      { k: "scrim", x: 0, y: 62, w: 100, h: 38 },
      text(5, 70, 72, 15, "headline", { s: 8, wt: 800, n: 2, serif: true, ls: -0.03 }),
      text(5, 86.5, 62, 3.4, "subhead", { s: 2.9, c: 2, n: 1 }),
      text(80, 82.5, 15, 3, "price", { s: 2.2, c: 2, a: "c", n: 1 }),
      { k: "barcode", x: 80, y: 86.5, w: 15, h: 9 },
    ],
  },
  {
    id: "lookbook",
    name: "Lookbook collage",
    format: "4:5",
    when:
      "A collage or mosaic of several photos: a lookbook, moodboard, outfits, a collection drop, travel moments, behind the scenes, community or customer photos, many looks at once.",
    blocks: [
      img(0, 0, 59, 46, "Look 1"),
      img(60.5, 0, 39.5, 22.25, "Look 2"),
      img(60.5, 23.75, 39.5, 22.25, "Look 3"),
      img(0, 47.5, 29, 25, "Look 4"),
      img(30.5, 47.5, 29, 25, "Look 5"),
      img(61, 47.5, 39, 25, "Look 6"),
      chip(3, 3, 22, 4.2, { f: "badge", ph: "New drop", v: "solid" }),
      text(5, 76.5, 60, 11, "headline", { s: 6.2, wt: 800, n: 2, ls: -0.03 }),
      text(5, 88.5, 58, 3.4, "subhead", { s: 2.8, c: 2, n: 1 }),
      btn(68, 78.5, 27, 7, { s: 3 }),
      text(68, 89.2, 27, 3, "brand", { s: 2.4, c: 3, a: "c", caps: true, ls: 0.2, n: 1 }),
    ],
  },
];

export const BY_ID: Record<string, Layout> = Object.fromEntries(LAYOUTS.map((l) => [l.id, l]));

/** The copy fields a layout draws from, for asking the chat to fill them. */
export function fieldsOf(layout: Layout): (keyof Copy)[] {
  const out = new Set<string>();
  for (const b of layout.blocks) {
    if (!b.f) continue;
    for (const m of b.f.matchAll(/[a-z]+/gi)) {
      if (m[0] in FIELD_HINTS) out.add(m[0]);
    }
  }
  return [...out] as (keyof Copy)[];
}

/** Roughly how many characters a text block holds at its set size, from its
 *  width, type size and line count. Geist averages ~0.56em a glyph. */
export function capacity(b: Block): number {
  const em = b.fit ?? 0.56 + ((b.wt ?? 400) >= 700 ? 0.04 : 0) + (b.caps ? 0.1 : 0) + (b.serif ? 0.04 : 0) + (b.ls ?? 0);
  const pad = b.k === "btn" || b.k === "chip" ? 1.7 : 0;
  const perLine = Math.max(1, Math.floor(b.w / ((b.s ?? 3) * em) - pad));
  return perLine * (b.k === "btn" || b.k === "chip" ? 1 : b.n ?? 1);
}

/** A glyph's rough advance in em for Geist-like faces: wide caps and digits,
 *  narrow lowercase and punctuation. Good enough to predict line breaks. */
function advance(ch: string): number {
  if (ch === " ") return 0.28;
  if (ch === "%" || ch === "@" || ch === "W" || ch === "M" || ch === "m" || ch === "w") return 0.86;
  if (/[A-Z]/.test(ch)) return 0.66;
  if (/[0-9₹$€£]/.test(ch)) return 0.6;
  if (/[a-z]/.test(ch)) return 0.53;
  return 0.34;
}

/** How much to scale a block's type so `text` wraps into its lines: greedy word
 *  wrap at the block's width, shrinking in small steps until it fits. */
export function fitScale(b: Block, text: string): number {
  const one = b.k === "btn" || b.k === "chip" || (b.n ?? 1) === 1;
  const lines = one ? 1 : b.n ?? 1;
  const weight = 1 + ((b.wt ?? 400) - 400) / 4000;
  const shown = b.caps ? text.toUpperCase() : text;
  const words = shown.split(/\s+/).filter(Boolean).map((w) =>
    [...w].reduce((sum, ch) => sum + (b.fit ?? advance(ch)) * weight + (b.ls ?? 0), 0));
  const space = 0.28 * weight;
  const pad = b.k === "btn" || b.k === "chip" ? 1.7 : 0;
  const floor = b.fit ? 0.4 : 0.5;
  for (let k = 1; k > floor; k -= 0.04) {
    // 5% short of the block: the advances are averages, and heavy display cuts run wide.
    const room = (b.w * 0.95) / ((b.s ?? 3) * k) - pad;
    let used = 1, x = 0;
    for (const w of words) {
      if (x && x + space + w > room) { used++; x = w; } else x += (x ? space : 0) + w;
      if (w > room) used += Math.ceil(w / room) - 1;
    }
    if (used <= lines) return k;
  }
  return floor;
}

/** Facts the user gave (a brand, a price, a venue) are never shortened to fit;
 *  the renderer shrinks them instead. */
const FACTS = new Set<string>(["brand", "price", "was", "code", "author", "rival", "date", "time", "place"]);

/** The tightest character budget each written field has in this layout, so
 *  the chat writes copy that fits the frame instead of copy that gets cut. */
export function budgetsOf(layout: Layout): Partial<Record<keyof Copy, number>> {
  const out: Partial<Record<keyof Copy, number>> = {};
  for (const b of layout.blocks) {
    if (!b.f || b.k === "bubble") continue;
    // A template like "{stats.0.value} {stats.0.label}" shares one line; skip it.
    const first = b.f.split("|")[0];
    if (first.includes("{")) continue;
    const key = first.split(".")[0] as keyof Copy;
    if (!(key in FIELD_HINTS) || FACTS.has(key) || first.split(".").length > 2) continue;
    out[key] = Math.min(out[key] ?? Infinity, capacity(b));
  }
  return out;
}

/** What each field is, for the chat model. Also the list of fields that exist. */
export const FIELD_HINTS: Record<keyof Copy, string> = {
  brand: "brand name or @handle, max 18 characters",
  headline: "max 7 words, the main line",
  subhead: "max 12 words, supports the headline",
  body: "fine print or a source line, max 12 words",
  cta: "button text, 1-3 words",
  offer: "the deal in max 3 words, e.g. 40% OFF",
  price: "current price with currency symbol",
  was: "old price before the discount, with currency symbol",
  code: "coupon code, uppercase, no spaces",
  badge: "a 1-3 word tag, e.g. New, Bestseller, Free entry",
  quote: "a customer quote in their voice, max 22 words",
  author: "a person's name (reviewer, speaker, agent)",
  role: "that person's title or context, max 5 words",
  rating: "rating line, e.g. ★ 4.8 · 1M+ downloads",
  rival: "competitor column label; use Others unless the user names one",
  date: "event date, short, e.g. OCT 12",
  time: "event time, e.g. 7 PM IST",
  place: "venue, address or city, max 6 words",
  stats: "array of 3 {value, label}: value max 6 characters, label max 4 words",
  steps: "array of 3 steps, max 4 words each",
  points: "array of 3-5 short points (features, benefits, ingredients, cover lines), max 5 words each",
  items: "array of 4 {name, price}: product names max 3 words",
  chat: "array of 5 {me, text}: a chat thread, me=false is the friend or customer, me=true is the reply; max 12 words each",
};

/** Resolve a dotted path like "stats.0.value" against the copy. */
export function at(copy: Copy, path: string): string | undefined {
  let cur: unknown = copy;
  for (const key of path.split(".")) {
    if (cur == null || typeof cur !== "object") return undefined;
    cur = (cur as Record<string, unknown>)[key];
  }
  if (typeof cur === "string" && cur.trim()) return cur.trim();
  if (typeof cur === "number") return String(cur);
  return undefined;
}

/** A block's words: literal text, else the first copy path that resolves. */
export function wordsOf(b: Block, copy: Copy): { text: string; placeholder: boolean } | null {
  if (b.t) return { text: b.t, placeholder: false };
  if (b.f) {
    for (const alt of b.f.split("|")) {
      if (alt.includes("{")) {
        let missing = false;
        const filled = alt.replace(/\{([^}]+)\}/g, (_, p: string) => {
          const v = at(copy, p);
          if (v === undefined) missing = true;
          return v ?? "";
        });
        if (!missing) return { text: filled.trim(), placeholder: false };
      } else {
        const v = at(copy, alt);
        if (v !== undefined) return { text: v, placeholder: false };
      }
    }
  }
  return b.ph ? { text: b.ph, placeholder: true } : null;
}
