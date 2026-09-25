# Version two: captions in any Indian language, romanised

Parked, not started. Written 2026-09-24.

## What version one does, and why it stops here

Captions today go through Groq Whisper twice: once plain, once behind a
Roman-script Hinglish prompt (`groq/asr.py`). `choose_hearing` keeps the
prompted hearing only where it replaced what was heard, which is what happens
when Hindi was being translated into English. Measured: English reels keep
0.994 and 1.000 of the plain hearing's words, a Hinglish talking head 0.56 to
0.82.

That works because Whisper has heard enough Roman-script Hinglish to imitate
it. There is no equivalent for Roman Punjabi or Telugu, and the trick does not
generalise: it would need a prompt per language, a way to know which to use,
and a model that has seen each romanisation. It is a Hindi-only bridge.

Whisper itself is not the lever either. There is no large-v4; large-v3 and
large-v3-turbo (2023, 2024) are the newest open checkpoints, and OpenAI has
moved to API-only transcription models. Waiting on that roadmap is waiting for
something aimed elsewhere.

## The shape that scales

Recognising speech and spelling it the way creators type are different
problems. Splitting them makes the language a parameter rather than a project:

| Stage | Tool | Licence |
|---|---|---|
| Hear it, in the native script | AI4Bharat IndicConformer 600M multilingual, all 22 official languages, one model | MIT |
| Write it as creators type it | AI4Bharat IndicXlit, native to Roman, 21 languages | MIT |
| Keep English words in English | ours, a lookup over the romanised tokens | - |

Both models are MIT, both run locally on the M5. Adding Telugu becomes a
config entry.

Transliteration is one word in, one word out, so **every word timestamp
survives**. That is the difference from the rejected LLM correction pass, which
rewrote phrases and moved words between slots (see the session notes: it also
changed English pronouns, blanked real speech, and hit Groq's 8000 TPM ceiling
on a single 57s clip).

Running locally also removes the per-clip API cost and the rate limit, and
gives us the decoding knobs Groq does not expose - VAD chunking,
`condition_on_previous_text=False`, temperature fallback - which is what caused
`whisper-large-v3` to stop transcribing and write its prompt out mid-clip.

## Open questions, in the order they block

1. **Word timestamps from IndicConformer.** Every caption in this pipeline is
   word-timed. Whisper hands us word timings; IndicConformer's model card does
   not say it does. CTC decoding should make them derivable, RNNT too, but
   until that is checked on a real clip the whole plan is unproven. This is the
   go/no-go and it is about a day's work.
2. **English passthrough.** A Telugu creator says "video"; the ASR writes it in
   Telugu script and the transliterator hands back "veediyo". Romanised tokens
   that are really English need mapping back to English spelling, by dictionary
   and phonetic distance.
3. **Which language a clip is in.** Cheapest reliable answer is asking the
   creator in the UI. Auto-detection (AI4Bharat IndicLID) can come later.
4. **Memory.** 16GB, and segmentation already wants a lot of it. Two models
   resident at once needs measuring.

## What each new language costs

The engineering is once. Per language you need clips with hand-corrected
transcripts, because neither romanisation nor ASR can be judged by reading the
output and nodding - that is how a "fix" shipped that invented a sentence in an
English reel. Judge on word error rate against a canonical phonetic form, not
exact string match: several romanisations of the same word are all correct.

Whisper stays the English path, where it is strong.

## Alternatives considered

- **Sarvam, ElevenLabs Scribe**: good at Indian languages, but a vendor, a key,
  a per-minute cost and speech leaving the machine.
- **IndicWhisper** (AI4Bharat, Whisper-medium fine-tuned on Vistaar, MIT): the
  strongest per-language option, but one model per language, which is the wrong
  memory profile for 16GB when the multilingual conformer covers 22.
- **Fine-tuning our own** on code-switched data: the real moat, a week plus data
  and a rented GPU. Worth revisiting once the eval set from above exists - by
  then we would have the data to do it.

## References

- IndicConformer: https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual
- IndicXlit: https://github.com/AI4Bharat/IndicXlit
- Aksharantar (the transliteration data behind IndicXlit): https://aclanthology.org/2023.findings-emnlp.4/
- Vistaar benchmarks / IndicWhisper: https://github.com/AI4Bharat/vistaar
