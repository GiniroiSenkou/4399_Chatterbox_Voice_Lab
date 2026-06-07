export const MODELS = [
  { id: "turbo", label: "Turbo", description: "Fastest, English, paralinguistic tags" },
  { id: "standard", label: "Standard", description: "English, full controls (tags converted to cues)" },
  { id: "multilingual", label: "Multilingual", description: "23+ languages, paralinguistic tags" },
] as const;

export type ModelId = (typeof MODELS)[number]["id"];

export const PARALINGUISTIC_TAGS = [
  { tag: "laugh", label: "Laugh", icon: "😄" },
  { tag: "cough", label: "Cough", icon: "😷" },
  { tag: "chuckle", label: "Chuckle", icon: "😏" },
  { tag: "whisper", label: "Whisper", icon: "🤫" },
  { tag: "sigh", label: "Sigh", icon: "😮‍💨" },
  { tag: "gasp", label: "Gasp", icon: "😲" },
] as const;

export const LANGUAGES = [
  { id: "ar", label: "Arabic" },
  { id: "da", label: "Danish" },
  { id: "de", label: "German" },
  { id: "el", label: "Greek" },
  { id: "en", label: "English" },
  { id: "es", label: "Spanish" },
  { id: "fi", label: "Finnish" },
  { id: "fr", label: "French" },
  { id: "he", label: "Hebrew" },
  { id: "hi", label: "Hindi" },
  { id: "it", label: "Italian" },
  { id: "ja", label: "Japanese" },
  { id: "ko", label: "Korean" },
  { id: "ms", label: "Malay" },
  { id: "nl", label: "Dutch" },
  { id: "no", label: "Norwegian" },
  { id: "pl", label: "Polish" },
  { id: "pt", label: "Portuguese" },
  { id: "ru", label: "Russian" },
  { id: "sv", label: "Swedish" },
  { id: "sw", label: "Swahili" },
  { id: "tr", label: "Turkish" },
  { id: "zh", label: "Chinese" },
] as const;

export const DEFAULT_PARAMS = {
  exaggeration: 0.5,
  cfg_weight: 0.5,
  temperature: 0.7,
  speed: 1.0,
  seed: null as number | null,
  top_p: 0.9,
  top_k: 50,
  min_p: 0.05,
  repetition_penalty: 1.0,
  norm_loudness: true,
  language_id: null as string | null,
};

export type GenerationParams = typeof DEFAULT_PARAMS;
