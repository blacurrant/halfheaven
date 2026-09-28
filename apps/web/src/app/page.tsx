import type { Metadata } from "next";
import Image from "next/image";
import { Caveat, Inter, Playfair_Display, Tiro_Devanagari_Hindi } from "next/font/google";

import HeroShowcase from "@/components/HeroShowcase";
import StepArt, { SourceChips } from "@/components/StepArt";
import Waitlist from "@/components/Waitlist";

import s from "./landing.module.css";

/**
 * The pitch, at the root. The studio it sells lives at /studio.
 *
 * It argues the problem before the product: a small creator pays for editing
 * either in rupees or in evenings, and when an editor leaves, their look leaves
 * with them. Nothing here is invented - no user counts, no testimonials, no
 * real creator's reel in the hero - and the India features that are not built
 * yet say "coming at launch" rather than pretending.
 *
 * The look follows apps/web/DESIGN.md. It is light-only: the page never reads
 * the site theme, so there is no toggle here.
 */

export const metadata: Metadata = {
  title: "Halfheaven: see a reel you love? Your videos can look like that",
  description:
    "Point Halfheaven at any reel you love. It edits your raw footage to match - the cuts, captions, colour and " +
    "pace - and keeps that look for every video after, for a fraction of what an editor costs.",
};

// Loaded here rather than in the root layout so /studio doesn't download them.
// Playfair stands in for Perfectly Nineties, which isn't licensed yet.
const serif = Playfair_Display({ variable: "--font-serif", subsets: ["latin"], style: ["normal", "italic"] });
const sans = Inter({ variable: "--font-sans", subsets: ["latin"] });
const deva = Tiro_Devanagari_Hindi({ variable: "--font-deva", subsets: ["devanagari"], weight: "400" });
// the handwritten notes in the hero and beside "How it works"
const hand = Caveat({ variable: "--font-hand", subsets: ["latin"], weight: "500" });

// ---- icons ------------------------------------------------------------------

const Svg = ({ children, size = 20, stroke = 1.9 }: { children: React.ReactNode; size?: number; stroke?: number }) => (
  <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth={stroke}
       strokeLinecap="round" strokeLinejoin="round" aria-hidden>{children}</svg>
);
const Check = ({ size = 16 }: { size?: number }) => <Svg size={size} stroke={2.2}><path d="M5 12.5l4.5 4.5L19 7" /></Svg>;
const Arrow = ({ size = 18 }: { size?: number }) => <Svg size={size}><path d="M5 12h14M13 6l6 6-6 6" /></Svg>;

const Brand = () => (
  <span className={s.brand}><span className={s.mark}><Arrow size={13} /></span>Halfheaven</span>
);

// ---- the words --------------------------------------------------------------

const PAINS = [
  {
    stat: "₹10–30k a month", title: "The editor bill",
    body: "A good short-form editor charges ₹500–3,000 a reel. Post five times a week and editing can quietly take a third of what you earn.",
  },
  {
    stat: "2–4 hours a reel", title: "The do-it-yourself tax",
    body: "Edit it yourself and a 30-second reel takes an evening. That’s time you’re not shooting, writing or talking to brands.",
  },
  {
    stat: "Back to square one", title: "The editor churn",
    body: "Your look lives in your editor’s head. When they get busy, raise their rates or leave, it goes with them, and the next one takes weeks to get it right.",
  },
];

// each title is plain words then the step's point, set in italic
const STEPS = [
  {
    title: "Pick your", mark: "reference",
    body: "One video your editor made, or any reel whose style you love. Halfheaven reads it: the cut rhythm, the caption type and placement, the colour, the pace.",
  },
  {
    title: "Drop your", mark: "raw footage",
    body: "Talk to camera, keep every take, upload. No timeline, no templates, no keyframes.",
  },
  {
    title: "Get it back", mark: "in your style",
    body: "Cut, captioned and graded to match. Want something different? Say it in plain words (“bigger captions”, “cut it tighter”) and it redoes the edit.",
  },
];

// what it costs you, three ways
const COMPARE: [string, string, string, string][] = [
  ["Cost", "₹10,000–30,000 a month", "Free, plus your evenings", "From ₹499 a month"],
  ["Turnaround", "1–3 days a video", "2–4 hours a reel", "Minutes, not days"],
  ["The same look every time", "Only while they stay", "Only on good days", "Saved to your account"],
  ["When they’re busy or leave", "Start over with someone new", "It stops when you stop", "Your style stays with you"],
  ["Asking for changes", "Another round on WhatsApp", "Back into the timeline", "Say it in plain words"],
];

const INDIA = [
  {
    glyph: "yeh", title: "Hinglish that reads right",
    body: "Code-mixed speech (“bhai, yeh game-changer hai”) captioned the way you said it, not mangled into one language.",
  },
  {
    glyph: "अ", deva: true, title: "Hindi and regional type",
    body: "Devanagari and other Indian scripts, set in typefaces drawn for them rather than a fallback font.",
  },
  {
    glyph: "₹", title: "Pay with UPI",
    body: "Monthly plans on UPI Autopay. No international card, no dollar pricing.",
  },
  {
    glyph: "9:16", title: "Reels and Shorts first",
    body: "Vertical by default, with captions kept clear of the Instagram and YouTube buttons.",
  },
];

const EDITORS = [
  { title: "One saved style per client", body: "Build a creator’s signature look once. Every video after follows it." },
  { title: "Review before it posts", body: "Fix any caption card by card, or send the client a link to approve." },
  { title: "More clients, same hours", body: "Spend your time on the edits that need taste, not the ones that need patience." },
];

const TIERS = [
  {
    name: "Creator", price: "₹499", per: "/month", for: "For creators posting a few times a week.",
    feats: ["1 saved style", "20 videos a month", "Cuts, captions and colour, matched",
            "English, Hindi and Hinglish captions", "Changes in plain words"],
  },
  {
    name: "Pro", price: "₹1,499", per: "/month", for: "For creators who post every day.", ribbon: "For daily posters",
    feats: ["5 saved styles", "60 videos a month", "Everything in Creator",
            "Every Indian language we support", "A music bed that ducks under your voice", "Priority rendering"],
  },
  {
    name: "Agency", price: "₹4,999", per: "/seat/month", for: "For editors and teams handling several creators.",
    feats: ["Unlimited client styles", "200 videos a month per seat", "Everything in Pro",
            "Review links for clients", "Styles shared across the team"],
  },
];

const FAQS = [
  {
    q: "Is this copying someone else’s content?",
    a: "No. Halfheaven copies a style: how a video is cut, captioned, coloured and paced. It never reuses anyone’s footage, music or words. Your video is made entirely from your own footage.",
  },
  {
    q: "Will it replace my editor?",
    a: "It can, if editing is only a cost for you. Many creators will keep their editor for the big videos and let Halfheaven handle the everyday ones in the same style. Editors use it to take on more clients.",
  },
  {
    q: "Which languages does it support?",
    a: "English, Hindi and Hinglish at launch, with more Indian languages following. Tell us yours when you join the waitlist.",
  },
  {
    q: "What if I don’t like the edit?",
    a: "Tell it what to change in plain words, or fix a caption yourself, card by card. You only export what you’re happy with.",
  },
  {
    q: "What if I don’t have a reference video?",
    a: "Start from one of the built-in looks, or point at any public reel whose style you like. Halfheaven takes the style, never the content.",
  },
  {
    q: "Who owns my videos?",
    a: "You do. Your footage and your edits are yours. We never publish or share them, and we’ll ask before using anything to improve the product.",
  },
  {
    q: "When does it launch?",
    a: "We’re letting waitlist members in batch by batch. Join and you’ll hear from us first, with your early-access price locked in.",
  },
];

// ---- the page ---------------------------------------------------------------

export default function Landing() {
  return (
    <div className={`${s.page} ${serif.variable} ${sans.variable} ${deva.variable} ${hand.variable}`}>
      <header className={s.nav}>
        <a href="#top" className={s.logoLink}><Brand /></a>
        <nav className={s.navLinks} aria-label="Sections">
          <a href="#problem">The problem</a>
          <a href="#how">How it works</a>
          <a href="#pricing">Pricing</a>
          <a href="#faq">FAQ</a>
        </nav>
        <a href="#waitlist" className={`${s.btn} ${s.primary} ${s.sm}`}>Join waitlist</a>
      </header>

      <main id="top">
        <section className={s.hero}>
          <Image src="/landing/backdrop.jpg" alt="" fill priority sizes="100vw" className={s.heroPhoto} />
          <span className={s.heroShade} />
          <div className={s.heroCopy}>
            <span className={s.pill}>Early access · Made for Indian creators</span>
            <h1 className={s.h1}>
              <span className={s.h1Ask}>See a reel you love?</span>
              Your videos can look like <em>that</em>.
            </h1>
            <p className={s.lede}>
              Point Halfheaven at any reel, or one your editor made. It reads the cuts, the captions, the colour
              and the pace, and edits your raw footage to match. Save the look and every video after it matches
              too, for a fraction of what an editor costs.
            </p>
            <div className={s.ctas}>
              <a href="#waitlist" className={`${s.btn} ${s.primary}`}>Join the waitlist</a>
              <a href="#how" className={`${s.btn} ${s.ghostDusk}`}>See how it works</a>
            </div>
            <p className={s.fine}>Early-access prices locked in for waitlist members. No card needed.</p>
          </div>
          <HeroShowcase />
        </section>

        <section id="problem" className={s.section}>
          <div className={s.head}>
            <span className={s.kicker}>The problem</span>
            <h2 className={s.h2}>Editing is eating your <em>channel</em>.</h2>
            <p className={s.sub}>
              Every creator hits the same wall. You pay for editing in rupees or you pay for it in hours. Either
              way it caps how often you can post, and posting often is the whole game.
            </p>
          </div>
          <div className={s.pains}>
            {PAINS.map((p) => (
              <article key={p.title} className={s.pain}>
                <p className={s.stat}>{p.stat}</p>
                <div>
                  <h3>{p.title}</h3>
                  <p>{p.body}</p>
                </div>
              </article>
            ))}
          </div>
          <p className={s.foot}>Rates are typical freelance ranges for short-form editing in India.</p>
        </section>

        <section className={s.band}>
          <p className={s.bandLine}>The hard part isn’t the first great edit. <span>It’s the <em>fiftieth</em>.</span></p>
          <p className={s.bandSub}>Halfheaven makes the fiftieth look exactly like the first.</p>
        </section>

        <section id="how" className={`${s.section} ${s.wide} ${s.airy}`}>
          <div className={`${s.head} ${s.center}`}>
            <span className={s.kicker}>How it works</span>
            <h2 className={s.h2}>Edit once. Then just <em>post</em>.</h2>
            <p className={s.sub}>
              Halfheaven turns one video you love into a style it can repeat on every video you shoot after it.
            </p>
          </div>
          <ol className={s.steps}>
            {STEPS.map((step, i) => (
              <li key={step.mark} className={s.step}>
                <div className={s.stepText}>
                  <span className={s.num}>0{i + 1}</span>
                  <h3>{step.title} <em>{step.mark}</em></h3>
                  <p>{step.body}</p>
                  {i === 1 && <SourceChips />}
                </div>
                <StepArt step={i} />
              </li>
            ))}
          </ol>
        </section>

        <section id="compare" className={`${s.section} ${s.wide}`}>
          <div className={s.head}>
            <span className={s.kicker}>The choice</span>
            <h2 className={s.h2}>What you’re really <em>choosing</em> between.</h2>
            <p className={s.sub}>Every creator already pays for editing, one way or another.</p>
          </div>
          <div className={s.tableWrap}>
            <table className={s.table}>
              <thead>
                <tr>
                  <th scope="col"><span className="sr-only">Compared on</span></th>
                  <th scope="col">A freelance editor</th>
                  <th scope="col">Doing it yourself</th>
                  <th scope="col" className={s.ours}>Halfheaven</th>
                </tr>
              </thead>
              <tbody>
                {COMPARE.map(([row, editor, self, ours]) => (
                  <tr key={row}>
                    <th scope="row">{row}</th>
                    <td data-label="Freelance editor">{editor}</td>
                    <td data-label="Doing it yourself">{self}</td>
                    <td data-label="Halfheaven" className={s.ours}>{ours}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section id="india" className={s.section}>
          <div className={s.head}>
            <span className={s.kicker}>Built for India <span className={s.soon}>Coming at launch</span></span>
            <h2 className={s.h2}>Made for how India <em>actually</em> posts.</h2>
            <p className={s.sub}>
              Most editing tools are built for English-only creators paying in dollars. We’re not.
            </p>
          </div>
          <div className={s.features}>
            {INDIA.map((f) => (
              <article key={f.title} className={s.feature}>
                <p className={`${s.glyph} ${f.deva ? s.deva : ""}`} aria-hidden>{f.glyph}</p>
                <div>
                  <h3>{f.title}</h3>
                  <p>{f.body}</p>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section id="editors" className={`${s.section} ${s.tight}`}>
          <div className={s.head}>
            <span className={s.kicker}>For editors and agencies</span>
            <h2 className={s.h2}>Make the master edit. Let the rest <em>follow</em>.</h2>
            <p className={s.sub}>
              Halfheaven doesn’t replace good editors. It multiplies them. Craft a creator’s look once, then take on
              more clients without taking on more hours.
            </p>
          </div>
          <ul className={s.list}>
            {EDITORS.map((e) => (
              <li key={e.title}>
                <Check />
                <div><strong>{e.title}</strong><span>{e.body}</span></div>
              </li>
            ))}
          </ul>
          <a href="#waitlist" className={`${s.btn} ${s.ghost}`}>Join as an editor</a>
        </section>

        <section id="pricing" className={`${s.section} ${s.wide} ${s.airy}`}>
          <div className={`${s.head} ${s.center}`}>
            <span className={s.kicker}>Pricing</span>
            <h2 className={s.h2}>A month of editing for the price of a <em>reel</em>.</h2>
            <p className={s.sub}>Early-access prices. Waitlist members lock these in.</p>
          </div>
          <div className={s.tiers}>
            {TIERS.map((t) => (
              <article key={t.name} className={`${s.tier} ${t.ribbon ? s.featured : ""}`}>
                <div className={s.tierHead}>
                  <h3>{t.name}{t.ribbon && <span className={s.ribbon}>{t.ribbon}</span>}</h3>
                  <p className={s.for}>{t.for}</p>
                </div>
                <p className={s.price}><strong>{t.price}</strong><span>{t.per}</span></p>
                <ul className={s.feats}>
                  {t.feats.map((f) => <li key={f}><Check /> {f}</li>)}
                </ul>
                <a href="#waitlist" className={`${s.btn} ${s.primary} ${s.full}`}>Join the waitlist</a>
              </article>
            ))}
          </div>
          <p className={s.tiersNote}>Prices in rupees, billed monthly by UPI Autopay or card. GST extra.</p>
        </section>

        <section id="faq" className={s.section}>
          <div className={s.head}>
            <span className={s.kicker}>Questions</span>
            <h2 className={s.h2}>Before you <em>ask</em>.</h2>
            <p className={s.sub}>The things creators want to know first.</p>
          </div>
          <div className={s.faq}>
            {FAQS.map((f, i) => (
              <details key={f.q} open={i === 0}>
                <summary>{f.q}</summary>
                <p>{f.a}</p>
              </details>
            ))}
          </div>
        </section>

        <section id="waitlist" className={`${s.section} ${s.wide} ${s.cta}`}>
          <div className={s.ctaCard}>
            <div className={s.ctaCopy}>
              <span className={s.kicker}>Early access</span>
              <h2 className={s.display}>Get your <em>evenings</em> back.</h2>
              <p className={s.sub}>
                Join the waitlist and we’ll let you in batch by batch, with early-access pricing locked in.
              </p>
              <ul className={s.perks}>
                {["Early-access price, locked in", "Bring one video you love; we do the rest", "No card needed to join"].map((p) => (
                  <li key={p}><span className={s.perkTick}><Check size={14} /></span>{p}</li>
                ))}
              </ul>
            </div>
            <Waitlist />
          </div>
        </section>
      </main>

      <footer className={s.footer}>
        <Brand />
        <p>© 2026 Halfheaven. Your editor’s style, on every video.</p>
        <nav className={s.footLinks} aria-label="Footer">
          <a href="#how">How it works</a>
          <a href="#pricing">Pricing</a>
          <a href="#faq">FAQ</a>
        </nav>
      </footer>
    </div>
  );
}
