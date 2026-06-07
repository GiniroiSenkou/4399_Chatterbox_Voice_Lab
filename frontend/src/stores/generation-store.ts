import { create } from "zustand";
import type { Generation } from "@/types/generation";
import { DEFAULT_PARAMS, LANGUAGES, type GenerationParams, type ModelId } from "@/lib/constants";
import { generateApi } from "@/lib/api";
import { useVoiceStore } from "./voice-store";
import { usePlayerStore } from "./player-store";

const GENERATION_DRAFT_KEY = "vl-generation-draft";
const SUPPORTED_LANGUAGE_IDS: ReadonlySet<string> = new Set(LANGUAGES.map(({ id }) => id));
const LANGUAGE_TAG_IDS: ReadonlyMap<string, string> = new Map(
  LANGUAGES.flatMap(({ id, label }) => [
    [id, id],
    [label.toLowerCase(), id],
  ]),
);

type LanguageSelectionMode = "auto" | "manual";

interface GenerationDraftState {
  text: string;
  model: ModelId;
  params: GenerationParams;
  selectedPreset: SelectedPresetRef | null;
  languageMode: LanguageSelectionMode;
}

function readDraftState(): GenerationDraftState {
  if (typeof window === "undefined") {
    return {
      text: "",
      model: "turbo",
      params: { ...DEFAULT_PARAMS },
      selectedPreset: null,
      languageMode: "auto",
    };
  }

  try {
    const raw = window.localStorage.getItem(GENERATION_DRAFT_KEY);
    if (!raw) {
      throw new Error("missing draft");
    }
    const parsed = JSON.parse(raw) as Partial<GenerationDraftState>;
    return {
      text: typeof parsed.text === "string" ? parsed.text : "",
      model: parsed.model === "standard" || parsed.model === "multilingual" ? parsed.model : "turbo",
      params: { ...DEFAULT_PARAMS, ...(parsed.params ?? {}) },
      selectedPreset: parsed.selectedPreset ?? null,
      languageMode:
        parsed.languageMode === "auto" || parsed.languageMode === "manual"
          ? parsed.languageMode
          : parsed.params?.language_id
            ? "manual"
            : "auto",
    };
  } catch {
    return {
      text: "",
      model: "turbo",
      params: { ...DEFAULT_PARAMS },
      selectedPreset: null,
      languageMode: "auto",
    };
  }
}

function persistDraftState(
  state: Pick<GenerationStore, "text" | "model" | "params" | "selectedPreset" | "languageMode">,
): void {
  if (typeof window === "undefined") return;

  const payload: GenerationDraftState = {
    text: state.text,
    model: state.model,
    params: state.params,
    selectedPreset: state.selectedPreset,
    languageMode: state.languageMode,
  };
  window.localStorage.setItem(GENERATION_DRAFT_KEY, JSON.stringify(payload));
}

function normalizeLanguageId(languageId: string | null | undefined): string | null {
  if (!languageId) return null;
  const normalized = languageId.trim().toLowerCase();
  return SUPPORTED_LANGUAGE_IDS.has(normalized) ? normalized : null;
}

function findLanguageIdInTags(tags: string[] | null | undefined): string | null {
  if (!tags?.length) return null;
  for (const tag of tags) {
    const normalized = tag.trim().toLowerCase();
    const languageId = LANGUAGE_TAG_IDS.get(normalized);
    if (languageId) {
      return languageId;
    }
  }
  return null;
}

function getSelectedVoiceLanguageId(): string | null {
  const { voices, selectedVoiceId } = useVoiceStore.getState();
  if (!selectedVoiceId) return null;
  const selectedVoice = voices.find((voice) => voice.id === selectedVoiceId);
  return normalizeLanguageId(selectedVoice?.language) ?? findLanguageIdInTags(selectedVoice?.tags);
}

function resolveLanguageState(
  model: ModelId,
  params: GenerationParams,
  languageMode: LanguageSelectionMode,
): { params: GenerationParams; languageMode: LanguageSelectionMode } {
  if (model !== "multilingual" || languageMode !== "auto") {
    return { params, languageMode };
  }

  const nextLanguageId = getSelectedVoiceLanguageId();
  if (params.language_id === nextLanguageId) {
    return { params, languageMode };
  }

  return {
    params: { ...params, language_id: nextLanguageId },
    languageMode,
  };
}

interface PendingGeneration {
  id: string;
  text: string;
  voice_id: string;
  model: ModelId;
  params: GenerationParams;
  preset_name?: string | null;
}

interface SelectedPresetRef {
  id: string;
  name: string;
}

interface GenerationStore {
  text: string;
  model: ModelId;
  params: GenerationParams;
  selectedPreset: SelectedPresetRef | null;
  languageMode: LanguageSelectionMode;
  activeJobId: string | null;
  activeJobProgress: number;
  activeJobStage: string;
  isGenerating: boolean;
  queue: PendingGeneration[];
  generations: Generation[];
  error: string | null;
  setText: (text: string) => void;
  setModel: (model: ModelId) => void;
  setParam: (key: string, value: unknown) => void;
  setParams: (params: Partial<GenerationParams>) => void;
  setSelectedPreset: (preset: SelectedPresetRef | null) => void;
  generate: () => Promise<void>;
  generateAB: () => Promise<void>;
  processQueue: () => Promise<void>;
  onJobProgress: (jobId: string, progress: number, stage: string) => void;
  onJobComplete: (jobId: string) => void;
  onJobFailed: (jobId: string, error: string) => void;
  fetchHistory: () => Promise<void>;
  deleteGeneration: (id: string) => Promise<void>;
  deleteAllHistory: () => Promise<void>;
}

export const useGenerationStore = create<GenerationStore>((set, get) => ({
  ...readDraftState(),
  activeJobId: null,
  activeJobProgress: 0,
  activeJobStage: "",
  isGenerating: false,
  queue: [],
  generations: [],
  error: null,

  setText: (text) =>
    set((s) => {
      const next = { text };
      persistDraftState({ ...s, ...next });
      return next;
    }),
  setModel: (model) =>
    set((s) => {
      const resolved = resolveLanguageState(model, s.params, s.languageMode);
      const next = {
        model,
        params: resolved.params,
        languageMode: resolved.languageMode,
        selectedPreset: null,
      };
      persistDraftState({ ...s, ...next });
      return next;
    }),
  setParam: (key, value) =>
    set((s) => {
      const nextLanguageMode =
        key === "language_id" ? (normalizeLanguageId(typeof value === "string" ? value : null) ? "manual" : "auto") : s.languageMode;
      const nextParams = (
        key === "language_id"
          ? { ...s.params, language_id: normalizeLanguageId(typeof value === "string" ? value : null) }
          : { ...s.params, [key]: value }
      ) as GenerationParams;
      const resolved = resolveLanguageState(s.model, nextParams, nextLanguageMode);
      const next = {
        params: resolved.params,
        languageMode: resolved.languageMode,
        selectedPreset: null,
      };
      persistDraftState({ ...s, ...next });
      return next;
    }),
  setParams: (params) =>
    set((s) => {
      const hasLanguageId = Object.prototype.hasOwnProperty.call(params, "language_id");
      const nextLanguageMode = hasLanguageId
        ? (normalizeLanguageId(typeof params.language_id === "string" ? params.language_id : null) ? "manual" : "auto")
        : s.languageMode;
      const nextParams = {
        ...s.params,
        ...params,
        ...(hasLanguageId
          ? { language_id: normalizeLanguageId(typeof params.language_id === "string" ? params.language_id : null) }
          : {}),
      } as GenerationParams;
      const resolved = resolveLanguageState(s.model, nextParams, nextLanguageMode);
      const next = {
        params: resolved.params,
        languageMode: resolved.languageMode,
        selectedPreset: null,
      };
      persistDraftState({ ...s, ...next });
      return next;
    }),
  setSelectedPreset: (preset) =>
    set((s) => {
      const next = { selectedPreset: preset };
      persistDraftState({ ...s, ...next });
      return next;
    }),

  generate: async () => {
    const { text, model, params, selectedPreset } = get();
    const voiceId = useVoiceStore.getState().selectedVoiceId;
    if (!voiceId || !text.trim()) return;

    const id = typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

    const queued: PendingGeneration = {
      id,
      text: text.trim(),
      voice_id: voiceId,
      model,
      params: { ...params },
      preset_name: selectedPreset?.name ?? null,
    };

    set((s) => ({ queue: [...s.queue, queued], error: null }));
    await get().processQueue();
  },

  generateAB: async () => {
    const { text, params, selectedPreset } = get();
    const voiceId = useVoiceStore.getState().selectedVoiceId;
    if (!voiceId || !text.trim()) return;
    if (get().isGenerating || get().queue.length > 0) return;

    set({ isGenerating: true, error: null });

    try {
      const res = await generateApi.generateAB({
        text,
        voice_id: voiceId,
        params,
        model_a: "turbo",
        model_b: "multilingual",
        preset_name: selectedPreset?.name ?? null,
      });
      set({ activeJobId: res.data.job_id_a });
    } catch (e: any) {
      set({ isGenerating: false, error: e.message });
    }
  },

  processQueue: async () => {
    const { isGenerating, activeJobId, queue } = get();
    if (isGenerating || activeJobId || queue.length === 0) return;

    const next = queue[0];
    set({ isGenerating: true, error: null, activeJobProgress: 0, activeJobStage: "queued" });

    try {
      const res = await generateApi.generate({
        text: next.text,
        voice_id: next.voice_id,
        model: next.model,
        params: next.params,
        preset_name: next.preset_name ?? null,
      });
      set((s) => ({ activeJobId: res.data.job_id, queue: s.queue.slice(1) }));
    } catch (e: any) {
      set((s) => ({ isGenerating: false, activeJobId: null, error: e.message, queue: s.queue.slice(1) }));
      await get().processQueue();
    }
  },

  onJobProgress: (jobId, progress, stage) => {
    if (get().activeJobId === jobId) {
      set({ activeJobProgress: progress, activeJobStage: stage });
    }
  },

  onJobComplete: (jobId) => {
    set({ isGenerating: false, activeJobId: null, activeJobProgress: 1 });
    // Load audio into player
    const audioUrl = generateApi.getAudioUrl(jobId);
    usePlayerStore.getState().loadAudio(audioUrl);
    // Refresh history then continue queue.
    void (async () => {
      await get().fetchHistory();
      await get().processQueue();
    })();
  },

  onJobFailed: (jobId, error) => {
    if (get().activeJobId === jobId) {
      set({ isGenerating: false, activeJobId: null, error });
      void get().processQueue();
    }
  },

  fetchHistory: async () => {
    try {
      const res = await generateApi.list({ limit: 50 });
      set({ generations: res.data.generations });
    } catch (e: any) {
      console.error("Failed to fetch history:", e);
    }
  },

  deleteGeneration: async (id) => {
    try {
      await generateApi.delete(id);
      set((s) => ({ generations: s.generations.filter((g) => g.id !== id) }));
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  deleteAllHistory: async () => {
    try {
      await generateApi.deleteHistory();
      set((s) => ({
        generations: s.generations.filter((g) => g.status !== "completed"),
      }));
    } catch (e: any) {
      set({ error: e.message });
    }
  },
}));

useVoiceStore.subscribe((voiceState, previousVoiceState) => {
  if (
    voiceState.selectedVoiceId === previousVoiceState.selectedVoiceId
    && voiceState.voices === previousVoiceState.voices
  ) {
    return;
  }

  useGenerationStore.setState((state) => {
    const resolved = resolveLanguageState(state.model, state.params, state.languageMode);
    const languageChanged = resolved.params.language_id !== state.params.language_id;
    if (!languageChanged) {
      return state;
    }

    const nextState = {
      ...state,
      params: resolved.params,
      languageMode: resolved.languageMode,
      selectedPreset: null,
    };
    persistDraftState(nextState);
    return nextState;
  });
});
