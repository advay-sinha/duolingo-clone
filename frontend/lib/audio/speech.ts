/**
 * Text-to-speech, behind one small abstraction.
 *
 * **Why the browser's own API and no backend.** Pronunciation is a rendering
 * concern: the text being spoken is already in the lesson payload, so shipping
 * it to a server to get audio back would add a round trip, a dependency and a
 * cost for something every modern browser does natively and offline. There is
 * no endpoint, no API key, and no audio file.
 *
 * **Why an abstraction rather than calling the API in each renderer.**
 * `speechSynthesis` is a global with real quirks — an utterance queues rather
 * than replacing the last one, availability varies, and voice lists load
 * asynchronously. Five renderers each doing that would be five places to get it
 * wrong. This module is the only code in the app that touches the API.
 *
 * Everything here degrades silently: on a browser without support, `speak()`
 * does nothing and `isSpeechAvailable()` reports false so the UI can hide the
 * control rather than offering a button that does nothing.
 */

/** Language tag for the course's target language. */
export const SPANISH = "es-ES";

/**
 * Whether the browser can speak.
 *
 * Guards on `window` too, because this module is imported by components that
 * are rendered on the server first — touching `speechSynthesis` during SSR
 * would throw.
 */
export function isSpeechAvailable(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

/**
 * Speak `text`, cancelling anything already in progress.
 *
 * The cancel is the important part: `speechSynthesis.speak` *queues*, so
 * tapping a speaker button three times would otherwise play three overlapping
 * utterances back to back. Learners tap these repeatedly, so replacing rather
 * than queueing is the correct behaviour.
 *
 * @param text The text to pronounce.
 * @param lang BCP-47 tag, so the browser picks a Spanish voice rather than
 *   reading Spanish with an English one.
 * @returns true if speech was started, false if unavailable or the text was
 *   empty — callers can use this to show a "not supported" state.
 */
export function speak(text: string, lang: string = SPANISH): boolean {
  if (!isSpeechAvailable()) return false;

  const trimmed = text.trim();
  if (!trimmed) return false;

  try {
    // Replace, do not queue.
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(trimmed);
    utterance.lang = lang;
    // Slightly slower than default: these are single words and short phrases a
    // learner is trying to hear clearly, not prose.
    utterance.rate = 0.9;
    window.speechSynthesis.speak(utterance);
    return true;
  } catch {
    // A browser may expose the API and still refuse (autoplay policies, no
    // voices installed). Failing silently is right: audio is an enhancement,
    // and a thrown error must never interrupt a lesson.
    return false;
  }
}

/** Stop any speech in progress — used when leaving a lesson. */
export function stopSpeaking(): void {
  if (!isSpeechAvailable()) return;
  try {
    window.speechSynthesis.cancel();
  } catch {
    // Nothing useful to do; the page is going away regardless.
  }
}

/**
 * The text a given exercise should pronounce, or `null` if none should.
 *
 * Pure and exported so the decision is testable without a browser — the whole
 * point of isolating the API. It is also the one piece of judgement in this
 * module worth asserting.
 *
 * The rule: **speak the Spanish**, never the English prompt. Which side is
 * Spanish differs per exercise type:
 *
 * - `TYPE_ANSWER` / `TRANSLATE` — the learner is *producing* Spanish, so there
 *   is nothing to pronounce yet. Speaking the English prompt would be pointless
 *   and speaking the answer would give it away.
 * - `MULTIPLE_CHOICE` — the options are Spanish; the prompt is English. Handled
 *   per option by the renderer, not here.
 * - `FILL_BLANK` — the sentence is Spanish with a gap, so it is worth hearing.
 * - `MATCH_PAIRS` — the left column is Spanish; per item, not per exercise.
 */
export function exerciseSpeechText(
  type: string,
  data: Record<string, unknown>,
): string | null {
  if (type === "FILL_BLANK") {
    const sentence = data.sentence;
    // Read the gap as a pause rather than three literal underscores.
    return typeof sentence === "string" ? sentence.replace("___", "…") : null;
  }
  return null;
}
