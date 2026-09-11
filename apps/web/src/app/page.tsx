import type { Metadata } from "next";

import ThemeToggle from "@/components/ThemeToggle";
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
 */

export const metadata: Metadata = {
  title: "Halfheaven: your editor’s style, on every video",
  description:
    "Get one video edited the way you love. Halfheaven edits every video after it to match - the cuts, captions, " +
    "colour and pace - for a fraction of what an editor costs.",
};

// ---- icons ------------------------------------------------------------------

const Svg = ({ children, size = 20 }: { children: React.ReactNode; size?: number }) => (
  <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.9"
       strokeLinecap="round" strokeLinejoin="round" aria-hidden>{children}</svg>
);
const Check = ({ size = 14 }: { size?: number }) => <Svg size={size}><path d="M5 12.5l4.5 4.5L19 7" /></Svg>;
const Rupee = () => <Svg><path d="M7 5h10M7 9.5h10M8 5c5.5 0 5.5 9 0 9h-1l7 6" /></Svg>;
const Clock = () => <Svg><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></Svg>;
const Loop = () => <Svg><path d="M4 12a8 8 0 0 1 13.7-5.6L20 8.5M20 12a8 8 0 0 1-13.7 5.6L4 15.5" /><path d="M20 4v4.5h-4.5M4 20v-4.5h4.5" /></Svg>;
const Layers = () => <Svg><path d="M12 3.5l8.5 4.5L12 12.5 3.5 8 12 3.5z" /><path d="M3.5 12.5L12 17l8.5-4.5M3.5 16.5L12 21l8.5-4.5" /></Svg>;
const Arrow = () => <Svg><path d="M5 12h14M13 6l6 6-6 6" /></Svg>;

// ---- the words --------------------------------------------------------------

const PAINS = [
  {
    icon: <Rupee />, stat: "₹10–30k a month", title: "The editor bill",
    body: "A good short-form editor charges ₹500–3,000 a reel. Post five times a week and editing can quietly take a third of what you earn.",
  },
  {
    icon: <Clock />, stat: "2–4 hours a reel", title: "The do-it-yourself tax",
    body: "Edit it yourself and a 30-second reel takes an evening. That’s time you’re not shooting, writing or talking to brands.",
  },
  {
    icon: <Loop />, stat: "Back to square one", title: "The editor churn",
    body: "Your look lives in your editor’s head. When they get busy, raise their rates or leave, it goes with them, and the next one takes weeks to get it right.",
  },
];

const STEPS = [
  {
    title: "Pick your reference",
    body: "One video your editor made, or any reel whose style you love. Halfheaven reads it: the cut rhythm, the caption type and placement, the colour, the pace.",
  },
  {
    title: "Drop your raw footage",
    body: "Talk to camera, keep every take, upload. No timeline, no templates, no keyframes.",
  },
  {
    title: "Get it back in your style",
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
    glyph: "अ", title: "Hindi and regional type",
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

// ---- the hero's phones ------------------------------------------------------

function Phone({ tone, line, word }: { tone: string; line: string; word: string }) {
  return (
    <div className={s.phone}>
      <div className={`${s.screen} ${tone}`}>
        <div className={s.bars}><i className={s.on} /><i className={s.on} /><i /><i /></div>
        <div className={s.subject} />
        <p className={s.cap}>{line}<b>{word}</b></p>
      </div>
    </div>
  );
}

/* One reference on the left, then a fanned stack of later videos carrying the
   same caption treatment over different footage - the product in one picture. */
function Stage() {
  return (
    <div className={s.stage} aria-hidden>
      <div className={s.col}>
        <span className={s.phoneLabel}>The one you love</span>
        <Phone tone={s.toneA} line="building a brand from" word="zero" />
      </div>
      <div className={s.bridge}><span><Arrow /></span><em>Same look</em></div>
      <div className={s.col}>
        <span className={s.phoneLabel}>Every video after</span>
        <div className={s.fan}>
          <Phone tone={s.toneC} line="day 12 of posting" word="daily" />
          <Phone tone={s.toneB} line="what nobody tells you about" word="pricing" />
          <Phone tone={s.toneA} line="how I got my first" word="client" />
        </div>
        <span className={s.badge}><Check /> Same style, every video</span>
      </div>
    </div>
  );
}

// ---- the page ---------------------------------------------------------------

export default function Landing() {
  return (
    <div className={s.page}>
      <header className={s.nav}>
        <div className={`${s.wrap} ${s.navInner}`}>
          <a href="#top" className={`logo ${s.logoLink}`}>
            <span className="dot">H</span><span className="name">Halfheaven</span>
          </a>
          <nav className={s.navLinks} aria-label="Sections">
            <a href="#problem">The problem</a>
            <a href="#how">How it works</a>
            <a href="#pricing">Pricing</a>
            <a href="#faq">FAQ</a>
          </nav>
          <div className={s.navRight}>
            <ThemeToggle />
            <a href="#waitlist" className="btn primary sm">Join waitlist</a>
          </div>
        </div>
      </header>

      <main id="top">
        <section className={`${s.wrap} ${s.hero}`}>
          <div>
            <span className={s.pill}><i>Early access</i> Made for Indian creators</span>
            <h1 className={s.h1}>Your editor’s style, on <em>every</em> video.</h1>
            <p className={s.lede}>
              Get one video edited the way you love. Halfheaven learns that edit (the cuts, the captions, the
              colour, the pace) and edits every video after it to match, for a fraction of what an editor costs.
            </p>
            <div className={s.ctas}>
              <a href="#waitlist" className="btn primary">Join the waitlist</a>
              <a href="#how" className="btn">See how it works</a>
            </div>
            <p className={s.fine}>Early-access prices locked in for waitlist members. No card needed.</p>
          </div>
          <Stage />
        </section>

        <section id="problem" className={`${s.section} ${s.alt}`}>
          <div className={s.wrap}>
            <div className={s.head}>
              <span className={s.kicker}>The problem</span>
              <h2 className={s.h2}>Editing is eating your <em>channel</em>.</h2>
              <p className={s.sub}>
                Every creator hits the same wall. You pay for editing in rupees or you pay for it in hours. Either
                way it caps how often you can post, and posting often is the whole game.
              </p>
            </div>
            <div className={s.grid3}>
              {PAINS.map((p) => (
                <article key={p.title} className={s.card}>
                  <span className={s.icon}>{p.icon}</span>
                  <p className={s.stat}>{p.stat}</p>
                  <h3>{p.title}</h3>
                  <p>{p.body}</p>
                </article>
              ))}
            </div>
            <p className={s.foot}>Rates are typical freelance ranges for short-form editing in India.</p>
          </div>
        </section>

        <section className={s.band}>
          <div className={s.wrap}>
            <p className={s.bandLine}>The hard part isn’t the first great edit. It’s the <em>fiftieth</em>.</p>
            <p className={s.bandSub}>Halfheaven makes the fiftieth look exactly like the first.</p>
          </div>
        </section>

        <section id="how" className={s.section}>
          <div className={s.wrap}>
            <div className={s.head}>
              <span className={s.kicker}>How it works</span>
              <h2 className={s.h2}>Edit once. Then just <em>post</em>.</h2>
              <p className={s.sub}>
                Halfheaven turns one video you love into a style it can repeat on every video you shoot after it.
              </p>
            </div>
            <ol className={s.steps} style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {STEPS.map((step, i) => (
                <li key={step.title} className={s.step}>
                  <span className={s.num}>0{i + 1}</span>
                  <h3>{step.title}</h3>
                  <p>{step.body}</p>
                </li>
              ))}
            </ol>
            <div className={s.memory}>
              <span className={s.icon}><Layers /></span>
              <div>
                <strong>Your style is saved, not rebuilt.</strong>
                <p>
                  Every style you make stays in your account. New videos start from it, so your channel looks
                  like your channel every time, whoever is or isn’t editing it this month.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section id="compare" className={`${s.section} ${s.alt}`}>
          <div className={s.wrap}>
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
          </div>
        </section>

        <section id="india" className={s.section}>
          <div className={s.wrap}>
            <div className={s.head}>
              <span className={s.kicker}>Built for India <span className={s.soon}>Coming at launch</span></span>
              <h2 className={s.h2}>Made for how India <em>actually</em> posts.</h2>
              <p className={s.sub}>
                Most editing tools are built for English-only creators paying in dollars. We’re not.
              </p>
            </div>
            <div className={s.grid4}>
              {INDIA.map((f) => (
                <article key={f.title} className={s.feature}>
                  <p className={s.glyph} aria-hidden>{f.glyph}</p>
                  <h3>{f.title}</h3>
                  <p>{f.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="editors" className={`${s.section} ${s.alt}`}>
          <div className={`${s.wrap} ${s.split}`}>
            <div className={s.head}>
              <span className={s.kicker}>For editors and agencies</span>
              <h2 className={s.h2}>Make the master edit. Let the rest <em>follow</em>.</h2>
              <p className={s.sub}>
                Halfheaven doesn’t replace good editors. It multiplies them. Craft a creator’s look once, then take on
                more clients without taking on more hours.
              </p>
              <div className={s.ctas}>
                <a href="#waitlist" className="btn">Join as an editor</a>
              </div>
            </div>
            <ul className={s.list}>
              {EDITORS.map((e) => (
                <li key={e.title}>
                  <span className={s.tick}><Check /></span>
                  <div><strong>{e.title}</strong><span>{e.body}</span></div>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section id="pricing" className={s.section}>
          <div className={s.wrap}>
            <div className={s.head}>
              <span className={s.kicker}>Pricing</span>
              <h2 className={s.h2}>A month of editing for the price of a <em>reel</em>.</h2>
              <p className={s.sub}>Early-access prices. Waitlist members lock these in.</p>
            </div>
            <div className={s.tiers}>
              {TIERS.map((t) => (
                <article key={t.name} className={`${s.tier} ${t.ribbon ? s.featured : ""}`}>
                  {t.ribbon && <span className={s.ribbon}>{t.ribbon}</span>}
                  <h3>{t.name}</h3>
                  <p className={s.for}>{t.for}</p>
                  <p className={s.price}><strong>{t.price}</strong><span>{t.per}</span></p>
                  <ul className={s.feats}>
                    {t.feats.map((f) => <li key={f}><Check /> {f}</li>)}
                  </ul>
                  <a href="#waitlist" className={`btn ${t.ribbon ? "primary" : ""} ${s.full}`}>Join the waitlist</a>
                </article>
              ))}
            </div>
            <p className={s.tiersNote}>Prices in rupees, billed monthly by UPI Autopay or card. GST extra.</p>
          </div>
        </section>

        <section id="faq" className={`${s.section} ${s.alt}`}>
          <div className={`${s.wrap} ${s.faqGrid}`}>
            <div className={s.head}>
              <span className={s.kicker}>Questions</span>
              <h2 className={s.h2}>Before you <em>ask</em>.</h2>
              <p className={s.sub}>The things creators want to know first.</p>
            </div>
            <div className={s.faq}>
              {FAQS.map((f) => (
                <details key={f.q}>
                  <summary>{f.q}</summary>
                  <p>{f.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section id="waitlist" className={`${s.section} ${s.cta}`}>
          <div className={s.wrap}>
            <div className={s.ctaCard}>
              <div>
                <h2 className={s.h2}>Get your <em>evenings</em> back.</h2>
                <p className={s.sub}>
                  Join the waitlist and we’ll let you in batch by batch, with early-access pricing locked in.
                </p>
                <ul className={s.perks}>
                  <li><Check size={16} /> Early-access price, locked in</li>
                  <li><Check size={16} /> Bring one video you love; we do the rest</li>
                  <li><Check size={16} /> No card needed to join</li>
                </ul>
              </div>
              <Waitlist />
            </div>
          </div>
        </section>
      </main>

      <footer className={s.footer}>
        <div className={`${s.wrap} ${s.footInner}`}>
          <span className="logo"><span className="dot">H</span><span className="name">Halfheaven</span></span>
          <p>© 2026 Halfheaven. Your editor’s style, on every video.</p>
          <nav className={s.footLinks} aria-label="Footer">
            <a href="#how">How it works</a>
            <a href="#pricing">Pricing</a>
            <a href="#faq">FAQ</a>
          </nav>
        </div>
      </footer>
    </div>
  );
}
