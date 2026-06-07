const MIN_MEANINGFUL_MULTILINGUAL_CHARS = 24;
const MIN_MEANINGFUL_MULTILINGUAL_TOKENS = 5;
const TAG_PATTERN = /\[\s*[^\]]+\s*\]/g;
const NON_ALNUM_PATTERN = /[^\p{L}\p{N}\s]/gu;
const TOKEN_PATTERN = /\b[\p{L}\p{N}_]+\b/gu;

export const MULTILINGUAL_SHORT_TEXT_ERROR =
  "Multilingual generation needs a longer prompt to avoid artifact audio. Use at least a short full sentence with about 5 meaningful words or 24 letters/numbers. Italian works best with an Italian reference clip. If you are cloning across languages, lower CFG Weight toward 0.0-0.3.";

export function stripMultilingualNoise(text: string): string {
  return text
    .replace(TAG_PATTERN, " ")
    .replace(NON_ALNUM_PATTERN, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function analyzeMultilingualPrompt(text: string) {
  const cleanedText = stripMultilingualNoise(text);
  const tokens = cleanedText.match(TOKEN_PATTERN) ?? [];
  const meaningfulCharacters = Array.from(cleanedText).filter((char) => /\p{L}|\p{N}/u.test(char)).length;
  return {
    cleanedText,
    meaningfulCharacters,
    meaningfulTokens: tokens.length,
  };
}

export function isMultilingualPromptTooShort(text: string): boolean {
  const analysis = analyzeMultilingualPrompt(text);
  return (
    analysis.meaningfulCharacters < MIN_MEANINGFUL_MULTILINGUAL_CHARS
    || analysis.meaningfulTokens < MIN_MEANINGFUL_MULTILINGUAL_TOKENS
  );
}
