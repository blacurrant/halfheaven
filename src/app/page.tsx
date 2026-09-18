import type { Metadata } from "next";

import ThemeToggle from "@/components/ThemeToggle";
import Waitlist from "@/components/Waitlist";


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
    <div className={"relative aspect-[9/16] rounded-[calc(var(--w)*0.14)] p-1.5 bg-[var(--theatre)] shadow-[0_30px_60px_-28px_rgba(46,38,48,0.6),0_0_0_1px_rgba(46,38,48,0.08)]"}>
      <div className={`absolute inset-1.5 rounded-[calc(var(--w)*0.11)] overflow-hidden ${tone}`}>
        <div className={"absolute top-[9px] left-[9px] right-[9px] flex gap-0.5"}><i className={"bg-[#FBF7EF]"} /><i className={"bg-[#FBF7EF]"} /><i /><i /></div>
        <div className={"absolute left-1/2 bottom-0 w-[74%] h-[46%] -translate-x-1/2"} />
        <p className={"absolute left-[8%] right-[8%] top-[22%] m-0 text-center text-[#FBF7EF] font-extrabold leading-[1.08] tracking-[-0.01em] text-[calc(var(--w)*0.074)]"}>{line}<b>{word}</b></p>
      </div>
    </div>
  );
}

/* One reference on the left, then a fanned stack of later videos carrying the
   same caption treatment over different footage - the product in one picture. */
function Stage() {
  return (
    <div className={"flex items-center justify-center gap-[clamp(12px,2.6vw,30px)] py-2.5 pb-5"} aria-hidden>
      <div className={"flex flex-col items-center gap-4"}>
        <span className={"text-[11.5px] font-bold tracking-[0.07em] uppercase text-[var(--faint)] whitespace-nowrap"}>The one you love</span>
        <Phone tone={"bg-gradient-to-br from-[#9A8A94] via-[#574B55] to-[#2E2630]"} line="building a brand from" word="zero" />
      </div>
      <div className={"flex flex-col items-center gap-2 mt-7 text-[11px] font-bold tracking-[0.07em] uppercase text-[var(--accent-ink)]"}><span><Arrow /></span><em>Same look</em></div>
      <div className={"flex flex-col items-center gap-4"}>
        <span className={"text-[11.5px] font-bold tracking-[0.07em] uppercase text-[var(--faint)] whitespace-nowrap"}>Every video after</span>
        <div className={"relative"}>
          <Phone tone={"bg-gradient-to-br from-[#C9AE72] via-[#7E5C22] to-[#2E2630]"} line="day 12 of posting" word="daily" />
          <Phone tone={"bg-gradient-to-br from-[#9FB2C6] via-[#46607B] to-[#2E2630]"} line="what nobody tells you about" word="pricing" />
          <Phone tone={"bg-gradient-to-br from-[#9A8A94] via-[#574B55] to-[#2E2630]"} line="how I got my first" word="client" />
        </div>
        <span className={"relative z-[2] -mt-[34px] inline-flex items-center gap-1.5 h-[34px] px-3.5 rounded-full bg-[var(--raised)] border border-[var(--line-2)] shadow-[var(--shadow)] text-xs font-semibold whitespace-nowrap"}><Check /> Same style, every video</span>
      </div>
    </div>
  );
}

// ---- the page ---------------------------------------------------------------

export default function Landing() {
  return (
    <div className={"bg-[var(--paper)] text-[var(--ink)] overflow-x-clip"}>
      <header className={"sticky top-0 z-30 border-b border-[var(--line)] backdrop-blur-xl bg-[color-mix(in_srgb,var(--paper)_86%,transparent)]"}>
        <div className={`w-full max-w-[1140px] mx-auto px-6 h-16 flex items-center gap-7`}>
          <a href="#top" className={`logo text-inherit no-underline`}>
            <span className="w-[22px] h-[22px] rounded-[7px] bg-[var(--accent)] grid place-items-center text-[var(--on-accent)] text-xs font-extrabold">H</span><span className="font-bold text-[17px] tracking-[-0.02em]">Halfheaven</span>
          </a>
          <nav className={"hidden md:flex gap-6 ml-2.5"} aria-label="Sections">
            <a href="#problem">The problem</a>
            <a href="#how">How it works</a>
            <a href="#pricing">Pricing</a>
            <a href="#faq">FAQ</a>
          </nav>
          <div className={"ml-auto flex items-center gap-2"}>
            <ThemeToggle />
            <a href="#waitlist" className="h-8 px-[13px] text-[13.5px] inline-flex items-center gap-1.5 rounded-full font-semibold bg-[var(--accent)] border border-[var(--accent)] text-[var(--on-accent)] hover:bg-[var(--accent-press)] whitespace-nowrap">Join waitlist</a>
          </div>
        </div>
      </header>

      <main id="top">
        <section className={`w-full max-w-[1140px] mx-auto px-6 py-[76px] pb-[100px] grid gap-12 items-center grid-cols-[minmax(0,1.05fr)_minmax(0,.95fr)] max-[980px]:grid-cols-1 max-[980px]:py-[52px] max-[980px]:pb-20 max-[980px]:gap-[52px]`}>
          <div>
            <span className={"inline-flex items-center gap-2 h-8 pl-1 pr-3 rounded-full border border-[var(--line-2)] bg-[var(--card)] text-[13px] font-semibold text-[var(--muted)]"}><i>Early access</i> Made for Indian creators</span>
            <h1 className={"mt-6 font-bold leading-[1.01] tracking-[-0.035em] text-[clamp(42px,6vw,72px)]"}>Your editor’s style, on <em>every</em> video.</h1>
            <p className={"mt-6 text-[18.5px] leading-[1.55] text-[var(--muted)] max-w-[530px]"}>
              Get one video edited the way you love. Halfheaven learns that edit (the cuts, the captions, the
              colour, the pace) and edits every video after it to match, for a fraction of what an editor costs.
            </p>
            <div className={"mt-[34px] flex flex-wrap gap-2.5"}>
              <a href="#waitlist" className="h-[38px] px-4 rounded-full font-semibold text-sm inline-flex items-center gap-1.5 border-[1.5px] bg-[var(--accent)] border-[var(--accent)] text-[var(--on-accent)] hover:bg-[var(--accent-press)] whitespace-nowrap">Join the waitlist</a>
              <a href="#how" className="h-[38px] px-4 rounded-full font-semibold text-sm inline-flex items-center gap-1.5 border-[1.5px] border-[var(--line-2)] bg-[var(--card)] whitespace-nowrap">See how it works</a>
            </div>
            <p className={"mt-[18px] text-[13px] text-[var(--faint)]"}>Early-access prices locked in for waitlist members. No card needed.</p>
          </div>
          <Stage />
        </section>

        <section id="problem" className={`py-28 scroll-mt-16 max-[720px]:py-20 bg-[var(--card)] border-y border-[var(--line)]`}>
          <div className={"w-full max-w-[1140px] mx-auto px-6"}>
            <div className={"max-w-[700px] mb-[52px]"}>
              <span className={"flex items-center gap-2.5 flex-wrap mb-4 text-xs font-bold tracking-[0.08em] uppercase text-[var(--accent-ink)]"}>The problem</span>
              <h2 className={"font-bold leading-[1.04] tracking-[-0.03em] text-[clamp(32px,4.4vw,52px)]"}>Editing is eating your <em>channel</em>.</h2>
              <p className={"mt-4 text-[17px] leading-6 text-[var(--muted)] max-w-[600px]"}>
                Every creator hits the same wall. You pay for editing in rupees or you pay for it in hours. Either
                way it caps how often you can post, and posting often is the whole game.
              </p>
            </div>
            <div className={"grid gap-4 grid-cols-3 max-[880px]:grid-cols-1"}>
              {PAINS.map((p) => (
                <article key={p.title} className={"flex flex-col p-7 px-6 pb-7 rounded-[18px] bg-[var(--card)] border border-[var(--line)]"}>
                  <span className={"w-11 h-11 rounded-xl grid place-items-center mb-7 shrink-0 bg-[var(--accent-soft)] text-[var(--accent-ink)]"}>{p.icon}</span>
                  <p className={"m-0 font-bold leading-[1.05] tracking-[-0.03em] text-[var(--ink)] text-[32px]"}>{p.stat}</p>
                  <h3>{p.title}</h3>
                  <p>{p.body}</p>
                </article>
              ))}
            </div>
            <p className={"mt-6 text-xs text-[var(--faint)]"}>Rates are typical freelance ranges for short-form editing in India.</p>
          </div>
        </section>

        <section className={"py-[100px] bg-[var(--theatre)] text-[#EFE5D2] text-center"}>
          <div className={"w-full max-w-[1140px] mx-auto px-6"}>
            <p className={"mx-auto max-w-[900px] font-bold leading-[1.06] tracking-[-0.03em] text-[clamp(30px,4.6vw,56px)]"}>The hard part isn’t the first great edit. It’s the <em>fiftieth</em>.</p>
            <p className={"mx-auto mt-5 max-w-[560px] text-[17px] text-[rgba(239,229,210,0.7)]"}>Halfheaven makes the fiftieth look exactly like the first.</p>
          </div>
        </section>

        <section id="how" className={"py-28 scroll-mt-16 max-[720px]:py-20"}>
          <div className={"w-full max-w-[1140px] mx-auto px-6"}>
            <div className={"max-w-[700px] mb-[52px]"}>
              <span className={"flex items-center gap-2.5 flex-wrap mb-4 text-xs font-bold tracking-[0.08em] uppercase text-[var(--accent-ink)]"}>How it works</span>
              <h2 className={"font-bold leading-[1.04] tracking-[-0.03em] text-[clamp(32px,4.4vw,52px)]"}>Edit once. Then just <em>post</em>.</h2>
              <p className={"mt-4 text-[17px] leading-6 text-[var(--muted)] max-w-[600px]"}>
                Halfheaven turns one video you love into a style it can repeat on every video you shoot after it.
              </p>
            </div>
            <ol className={"grid gap-9 grid-cols-3 max-[880px]:grid-cols-1 max-[880px]:gap-7"} style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {STEPS.map((step, i) => (
                <li key={step.title} className={"pt-5 border-t-[1.5px] border-[var(--line-2)]"}>
                  <span className={"italic font-bold text-[46px] leading-none text-[var(--accent-ink)]"}>0{i + 1}</span>
                  <h3>{step.title}</h3>
                  <p>{step.body}</p>
                </li>
              ))}
            </ol>
            <div className={"mt-15 flex gap-4 items-start p-6 px-6 rounded-[18px] bg-[var(--accent-soft)] border border-[color-mix(in_srgb,var(--accent-ink)_22%,transparent)]"}>
              <span className={"w-11 h-11 rounded-xl grid place-items-center mb-7 shrink-0 bg-[var(--accent-soft)] text-[var(--accent-ink)]"}><Layers /></span>
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

        <section id="compare" className={`py-28 scroll-mt-16 max-[720px]:py-20 bg-[var(--card)] border-y border-[var(--line)]`}>
          <div className={"w-full max-w-[1140px] mx-auto px-6"}>
            <div className={"max-w-[700px] mb-[52px]"}>
              <span className={"flex items-center gap-2.5 flex-wrap mb-4 text-xs font-bold tracking-[0.08em] uppercase text-[var(--accent-ink)]"}>The choice</span>
              <h2 className={"font-bold leading-[1.04] tracking-[-0.03em] text-[clamp(32px,4.4vw,52px)]"}>What you’re really <em>choosing</em> between.</h2>
              <p className={"mt-4 text-[17px] leading-6 text-[var(--muted)] max-w-[600px]"}>Every creator already pays for editing, one way or another.</p>
            </div>
            <div className={"overflow-x-auto border border-[var(--line)] rounded-[18px] bg-[var(--card)]"}>
              <table className={"w-full min-w-[700px] border-collapse text-[15px]"}>
                <thead>
                  <tr>
                    <th scope="col"><span className="sr-only">Compared on</span></th>
                    <th scope="col">A freelance editor</th>
                    <th scope="col">Doing it yourself</th>
                    <th scope="col" className={"bg-[var(--accent-soft)] text-[var(--ink)] font-semibold"}>Halfheaven</th>
                  </tr>
                </thead>
                <tbody>
                  {COMPARE.map(([row, editor, self, ours]) => (
                    <tr key={row}>
                      <th scope="row">{row}</th>
                      <td data-label="Freelance editor">{editor}</td>
                      <td data-label="Doing it yourself">{self}</td>
                      <td data-label="Halfheaven" className={"bg-[var(--accent-soft)] text-[var(--ink)] font-semibold"}>{ours}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section id="india" className={"py-28 scroll-mt-16 max-[720px]:py-20"}>
          <div className={"w-full max-w-[1140px] mx-auto px-6"}>
            <div className={"max-w-[700px] mb-[52px]"}>
              <span className={"flex items-center gap-2.5 flex-wrap mb-4 text-xs font-bold tracking-[0.08em] uppercase text-[var(--accent-ink)]"}>Built for India <span className={"inline-flex items-center h-6 px-2.5 rounded-full border-[1.5px] border-[var(--gold)] text-[var(--gold)] text-[11px] tracking-[0.05em]"}>Coming at launch</span></span>
              <h2 className={"font-bold leading-[1.04] tracking-[-0.03em] text-[clamp(32px,4.4vw,52px)]"}>Made for how India <em>actually</em> posts.</h2>
              <p className={"mt-4 text-[17px] leading-6 text-[var(--muted)] max-w-[600px]"}>
                Most editing tools are built for English-only creators paying in dollars. We’re not.
              </p>
            </div>
            <div className={"grid gap-4 grid-cols-4 max-[1000px]:grid-cols-2 max-[560px]:grid-cols-1"}>
              {INDIA.map((f) => (
                <article key={f.title} className={"p-6 px-5 pb-7 rounded-[18px] bg-[var(--card)] border border-[var(--line)]"}>
                  <p className={"m-0 mb-5 font-bold leading-none text-[var(--accent-ink)] text-[28px]"} aria-hidden>{f.glyph}</p>
                  <h3>{f.title}</h3>
                  <p>{f.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="editors" className={`py-28 scroll-mt-16 max-[720px]:py-20 bg-[var(--card)] border-y border-[var(--line)]`}>
          <div className={`w-full max-w-[1140px] mx-auto px-6 grid gap-15 items-center grid-cols-[minmax(0,1fr)_minmax(0,.92fr)] max-[880px]:grid-cols-1 max-[880px]:gap-9`}>
            <div className={"max-w-[700px] mb-[52px]"}>
              <span className={"flex items-center gap-2.5 flex-wrap mb-4 text-xs font-bold tracking-[0.08em] uppercase text-[var(--accent-ink)]"}>For editors and agencies</span>
              <h2 className={"font-bold leading-[1.04] tracking-[-0.03em] text-[clamp(32px,4.4vw,52px)]"}>Make the master edit. Let the rest <em>follow</em>.</h2>
              <p className={"mt-4 text-[17px] leading-6 text-[var(--muted)] max-w-[600px]"}>
                Halfheaven doesn’t replace good editors. It multiplies them. Craft a creator’s look once, then take on
                more clients without taking on more hours.
              </p>
              <div className={"mt-[34px] flex flex-wrap gap-2.5"}>
                <a href="#waitlist" className="h-[38px] px-4 rounded-full font-semibold text-sm inline-flex items-center gap-1.5 border-[1.5px] border-[var(--line-2)] bg-[var(--card)] whitespace-nowrap">Join as an editor</a>
              </div>
            </div>
            <ul className={"list-none m-0 p-1.5 rounded-[18px] bg-[var(--card)] border border-[var(--line)]"}>
              {EDITORS.map((e) => (
                <li key={e.title}>
                  <span className={"w-6 h-6 rounded-full shrink-0 grid place-items-center bg-[var(--accent-soft)] text-[var(--accent-ink)]"}><Check /></span>
                  <div><strong>{e.title}</strong><span>{e.body}</span></div>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section id="pricing" className={"py-28 scroll-mt-16 max-[720px]:py-20"}>
          <div className={"w-full max-w-[1140px] mx-auto px-6"}>
            <div className={"max-w-[700px] mb-[52px]"}>
              <span className={"flex items-center gap-2.5 flex-wrap mb-4 text-xs font-bold tracking-[0.08em] uppercase text-[var(--accent-ink)]"}>Pricing</span>
              <h2 className={"font-bold leading-[1.04] tracking-[-0.03em] text-[clamp(32px,4.4vw,52px)]"}>A month of editing for the price of a <em>reel</em>.</h2>
              <p className={"mt-4 text-[17px] leading-6 text-[var(--muted)] max-w-[600px]"}>Early-access prices. Waitlist members lock these in.</p>
            </div>
            <div className={"grid gap-4 grid-cols-3 max-[960px]:grid-cols-1 max-[960px]:max-w-[470px] max-[960px]:mx-auto"}>
              {TIERS.map((t) => (
                <article key={t.name} className={`relative flex flex-col p-8 px-7 pb-7 rounded-[20px] bg-[var(--card)] border border-[var(--line)] ${t.ribbon ? "bg-[var(--raised)] border-[1.5px] border-[var(--accent-ink)] shadow-[var(--shadow)]" : ""}`}>
                  {t.ribbon && <span className={"absolute -top-3 left-6 h-6 px-3 rounded-full inline-flex items-center bg-[var(--accent)] text-[var(--on-accent)] text-[11px] font-bold tracking-[0.05em] uppercase"}>{t.ribbon}</span>}
                  <h3>{t.name}</h3>
                  <p className={"mt-1.5 min-h-11 text-sm leading-[1.55] text-[var(--muted)]"}>{t.for}</p>
                  <p className={"mt-5 flex items-baseline gap-1.5"}><strong>{t.price}</strong><span>{t.per}</span></p>
                  <ul className={"flex-1 list-none my-6 mb-7 p-0 flex flex-col gap-3"}>
                    {t.feats.map((f) => <li key={f}><Check /> {f}</li>)}
                  </ul>
                  <a href="#waitlist" className={`w-[34px] h-8 p-0 justify-center inline-flex items-center rounded-full font-semibold bg-transparent border-transparent text-[var(--muted)] hover:bg-[var(--sunk)] ${t.ribbon ? "primary" : ""} w-full h-[46px] justify-center`}>Join the waitlist</a>
                </article>
              ))}
            </div>
            <p className={"mt-6 text-center text-[13px] text-[var(--faint)]"}>Prices in rupees, billed monthly by UPI Autopay or card. GST extra.</p>
          </div>
        </section>

        <section id="faq" className={`py-28 scroll-mt-16 max-[720px]:py-20 bg-[var(--card)] border-y border-[var(--line)]`}>
          <div className={`w-full max-w-[1140px] mx-auto px-6 grid gap-15 grid-cols-[minmax(0,.8fr)_minmax(0,1.2fr)] max-[880px]:grid-cols-1 max-[880px]:gap-2`}>
            <div className={"max-w-[700px] mb-[52px]"}>
              <span className={"flex items-center gap-2.5 flex-wrap mb-4 text-xs font-bold tracking-[0.08em] uppercase text-[var(--accent-ink)]"}>Questions</span>
              <h2 className={"font-bold leading-[1.04] tracking-[-0.03em] text-[clamp(32px,4.4vw,52px)]"}>Before you <em>ask</em>.</h2>
              <p className={"mt-4 text-[17px] leading-6 text-[var(--muted)] max-w-[600px]"}>The things creators want to know first.</p>
            </div>
            <div className={"border-b border-[var(--line)]"}>
              {FAQS.map((f) => (
                <details key={f.q}>
                  <summary>{f.q}</summary>
                  <p>{f.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section id="waitlist" className={`py-28 scroll-mt-16 max-[720px]:py-20 scroll-mt-[84px]`}>
          <div className={"w-full max-w-[1140px] mx-auto px-6"}>
            <div className={"grid gap-[52px] items-center p-[clamp(28px,6vw,72px)] rounded-[28px] bg-[var(--theatre)] text-[#EFE5D2] grid-cols-[minmax(0,1fr)_minmax(0,440px)] max-[920px]:grid-cols-1 max-[920px]:gap-9"}>
              <div>
                <h2 className={"font-bold leading-[1.04] tracking-[-0.03em] text-[clamp(32px,4.4vw,52px)]"}>Get your <em>evenings</em> back.</h2>
                <p className={"mt-4 text-[17px] leading-6 text-[var(--muted)] max-w-[600px]"}>
                  Join the waitlist and we’ll let you in batch by batch, with early-access pricing locked in.
                </p>
                <ul className={"list-none m-0 mt-7 p-0 flex flex-col gap-3 text-[15px] text-[rgba(239,229,210,0.88)]"}>
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

      <footer className={"py-7 pb-10 border-t border-[var(--line)]"}>
        <div className={`w-full max-w-[1140px] mx-auto px-6 flex flex-wrap items-center gap-3.5 gap-x-7`}>
          <span className="flex items-center gap-[9px] shrink-0"><span className="w-[22px] h-[22px] rounded-[7px] bg-[var(--accent)] grid place-items-center text-[var(--on-accent)] text-xs font-extrabold">H</span><span className="font-bold text-[17px] tracking-[-0.02em]">Halfheaven</span></span>
          <p>© 2026 Halfheaven. Your editor’s style, on every video.</p>
          <nav className={"ml-auto flex gap-5"} aria-label="Footer">
            <a href="#how">How it works</a>
            <a href="#pricing">Pricing</a>
            <a href="#faq">FAQ</a>
          </nav>
        </div>
      </footer>
    </div>
  );
}
