import { useCallback } from "react";
import { useGenerationStore } from "@/stores/generation-store";
import { useVoiceStore } from "@/stores/voice-store";
import { useUIStore } from "@/stores/ui-store";
import { MULTILINGUAL_SHORT_TEXT_ERROR, isMultilingualPromptTooShort } from "@/lib/multilingual-validation";

export function useGeneration() {
  const { generate, generateAB, isGenerating, queue, activeJobProgress, activeJobStage, text, model } =
    useGenerationStore();
  const { selectedVoiceId } = useVoiceStore();
  const { addToast } = useUIStore();

  const triggerGenerate = useCallback(async () => {
    if (!selectedVoiceId) {
      addToast({ type: "error", message: "Please select a voice first" });
      return;
    }
    if (model === "multilingual" && isMultilingualPromptTooShort(text)) {
      addToast({ type: "error", message: MULTILINGUAL_SHORT_TEXT_ERROR });
      return;
    }
    const currentlyGenerating = useGenerationStore.getState().isGenerating;
    await generate();
    if (currentlyGenerating) {
      addToast({ type: "info", message: "Added to generation queue" });
    }
  }, [addToast, generate, model, selectedVoiceId, text]);

  const triggerGenerateAB = useCallback(async () => {
    if (!selectedVoiceId) {
      addToast({ type: "error", message: "Please select a voice first" });
      return;
    }
    if (isMultilingualPromptTooShort(text)) {
      addToast({ type: "error", message: MULTILINGUAL_SHORT_TEXT_ERROR });
      return;
    }
    await generateAB();
  }, [addToast, generateAB, selectedVoiceId, text]);

  return {
    triggerGenerate,
    triggerGenerateAB,
    isGenerating,
    queueLength: queue.length,
    progress: activeJobProgress,
    stage: activeJobStage,
    canGenerate: !!selectedVoiceId,
  };
}
