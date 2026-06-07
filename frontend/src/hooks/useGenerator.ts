/**
 * useGenerator — wraps POST /api/generate and POST /api/generate/select.
 *
 * Exposes:
 *   generate(prompt, minutes)   — calls /api/generate; populates variants + trace
 *   selectVariant(variantId)    — calls /api/generate/select; sets selectedVariant
 *   variants                    — the 3 returned WorkoutVariants
 *   selectedVariant             — the currently chosen variant (or null)
 *   traceSummary                — shared filter trace summary
 *   decisionTrace               — ordered pipeline decision steps
 *   injuryStateUsed             — the InjuryState snapshot that drove filtering
 *   loading                     — true while a request is in-flight
 *   error                       — last error message (null if none)
 *   llmUnconfigured             — true if the backend returned 503 (no API key)
 *   reset                       — clear all state
 */

import { useState, useCallback } from "react";
import {
  postGenerate,
  postGenerateSelect,
  postRegenerate,
  streamGenerate,
  type WorkoutVariant,
  type TraceSummary,
  type DecisionStep,
  type InjuryState,
  type GenStatusEvent,
} from "../lib/api";

interface UseGeneratorResult {
  generate: (prompt: string, minutes: number) => Promise<boolean>;
  generateStream: (
    prompt: string,
    minutes: number,
    engine?: "hybrid" | "llm"
  ) => Promise<boolean>;
  regenerate: (adjustment?: string) => Promise<boolean>;
  selectVariant: (variantId: string) => Promise<void>;
  variants: WorkoutVariant[];
  selectedVariant: WorkoutVariant | null;
  traceSummary: TraceSummary | null;
  decisionTrace: DecisionStep[];
  injuryStateUsed: InjuryState | null;
  loading: boolean;
  genStatus: GenStatusEvent | null;
  error: string | null;
  llmUnconfigured: boolean;
  reset: () => void;
}

export function useGenerator(memberId: string | null): UseGeneratorResult {
  const [variants, setVariants] = useState<WorkoutVariant[]>([]);
  const [selectedVariantId, setSelectedVariantId] = useState<string | null>(null);
  const [traceSummary, setTraceSummary] = useState<TraceSummary | null>(null);
  const [decisionTrace, setDecisionTrace] = useState<DecisionStep[]>([]);
  const [loading, setLoading] = useState(false);
  const [genStatus, setGenStatus] = useState<GenStatusEvent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [llmUnconfigured, setLlmUnconfigured] = useState(false);

  const reset = useCallback(() => {
    setVariants([]);
    setSelectedVariantId(null);
    setTraceSummary(null);
    setDecisionTrace([]);
    setGenStatus(null);
    setError(null);
    setLlmUnconfigured(false);
  }, []);

  const generateStream = useCallback(
    async (
      prompt: string,
      minutes: number,
      engine: "hybrid" | "llm" = "hybrid"
    ): Promise<boolean> => {
      if (!memberId) return false;
      setLoading(true);
      setError(null);
      setLlmUnconfigured(false);
      setVariants([]);
      setSelectedVariantId(null);
      setGenStatus(null);

      let ok = false;
      try {
        await streamGenerate(
          prompt,
          minutes,
          memberId,
          (ev) => {
            const type = ev.type as string;
          if (type === "status") {
            setGenStatus(ev as unknown as GenStatusEvent);
          } else if (type === "complete") {
            const o = ev.output as {
              variants: WorkoutVariant[];
              trace_summary: TraceSummary;
              decision_trace?: DecisionStep[];
              selected_variant_id: string | null;
            };
            setVariants(o.variants);
            setTraceSummary(o.trace_summary);
            setDecisionTrace(o.decision_trace ?? []);
            setSelectedVariantId(o.selected_variant_id);
            ok = true;
          } else if (type === "error") {
            if (ev.status === 503) {
              setLlmUnconfigured(true);
              setError("LLM not configured — set ANTHROPIC_API_KEY and restart the server.");
            } else {
              setError((ev.detail as string) ?? "Generation failed");
            }
          }
          },
          engine
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
        setGenStatus(null);
      }
      return ok;
    },
    [memberId]
  );

  const generate = useCallback(
    async (prompt: string, minutes: number): Promise<boolean> => {
      if (!memberId) return false;
      setLoading(true);
      setError(null);
      setLlmUnconfigured(false);
      setVariants([]);
      setSelectedVariantId(null);

      try {
        const output = await postGenerate(prompt, minutes, memberId);
        setVariants(output.variants);
        setTraceSummary(output.trace_summary);
        setDecisionTrace(output.decision_trace ?? []);
        setSelectedVariantId(output.selected_variant_id);
        return true;
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        if (msg.includes("503")) {
          setLlmUnconfigured(true);
          setError("LLM not configured — set ANTHROPIC_API_KEY and restart the server.");
        } else {
          setError(msg);
        }
        return false;
      } finally {
        setLoading(false);
      }
    },
    [memberId]
  );

  const regenerate = useCallback(
    async (adjustment?: string): Promise<boolean> => {
      if (!memberId) return false;
      setLoading(true);
      setError(null);
      setLlmUnconfigured(false);

      try {
        const output = await postRegenerate(memberId, adjustment);
        setVariants(output.variants);
        setTraceSummary(output.trace_summary);
        setDecisionTrace(output.decision_trace ?? []);
        setSelectedVariantId(output.selected_variant_id);
        return true;
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        if (msg.includes("503")) {
          setLlmUnconfigured(true);
          setError("LLM not configured — set ANTHROPIC_API_KEY and restart the server.");
        } else {
          setError(msg);
        }
        return false;
      } finally {
        setLoading(false);
      }
    },
    [memberId]
  );

  const selectVariant = useCallback(
    async (variantId: string) => {
      if (!memberId) return;
      setLoading(true);
      setError(null);

      try {
        const output = await postGenerateSelect(memberId, variantId);
        setSelectedVariantId(output.selected_variant_id);
        // Update variants in case the backend returned updated data
        if (output.variants.length > 0) {
          setVariants(output.variants);
        }
        setTraceSummary(output.trace_summary);
        setDecisionTrace(output.decision_trace ?? []);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
      } finally {
        setLoading(false);
      }
    },
    [memberId]
  );

  // Derived: which variant is currently selected
  const selectedVariant =
    selectedVariantId != null
      ? (variants.find((v) => v.variant_id === selectedVariantId) ?? null)
      : null;

  // Derived: injury state from the first variant's provenance (all variants share
  // the same filter run, so provenance.injury_state_used is identical across them)
  const injuryStateUsed = variants[0]?.provenance?.injury_state_used ?? null;

  return {
    generate,
    generateStream,
    regenerate,
    selectVariant,
    genStatus,
    variants,
    selectedVariant,
    traceSummary,
    decisionTrace,
    injuryStateUsed,
    loading,
    error,
    llmUnconfigured,
    reset,
  };
}
