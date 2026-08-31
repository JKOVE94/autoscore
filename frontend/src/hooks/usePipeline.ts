import { useCallback, useState } from "react";
import { ApiRequestError, api } from "../api/client";
import type { AnalysisResponse, BuildResponse } from "../types";

export type Phase = "idle" | "running" | "ready" | "error";
export type StepStatus = "run" | "ok" | "fail" | "skip";

export interface StepLog {
  key: string;
  label: string;
  status: StepStatus;
  detail?: string;
}

interface PipelineState {
  phase: Phase;
  jobId: string | null;
  steps: StepLog[];
  analysis: AnalysisResponse | null;
  build: BuildResponse | null;
  xml: string | null;
  error: string | null;
}

const INITIAL: PipelineState = {
  phase: "idle",
  jobId: null,
  steps: [],
  analysis: null,
  build: null,
  xml: null,
  error: null,
};

export function usePipeline() {
  const [state, setState] = useState<PipelineState>(INITIAL);

  const patch = useCallback((p: Partial<PipelineState>) => {
    setState((s) => ({ ...s, ...p }));
  }, []);

  const setStep = useCallback((key: string, label: string, status: StepStatus, detail?: string) => {
    setState((s) => {
      const rest = s.steps.filter((st) => st.key !== key);
      return { ...s, steps: [...rest, { key, label, status, detail }] };
    });
  }, []);

  const reset = useCallback(() => setState(INITIAL), []);

  const run = useCallback(
    async (
      plan: {
        key: string;
        label: string;
        fn: () => Promise<unknown>;
        onResult?: (r: unknown) => void;
      }[],
    ) => {
      setState({ ...INITIAL, phase: "running" });
      try {
        for (const step of plan) {
          setStep(step.key, step.label, "run");
          try {
            const result = await step.fn();
            step.onResult?.(result);
            setStep(step.key, step.label, "ok");
          } catch (err) {
            const msg =
              err instanceof ApiRequestError
                ? `${err.code}: ${err.message}`
                : err instanceof Error
                  ? err.message
                  : "unknown error";
            setStep(step.key, step.label, "fail", msg);
            patch({ phase: "error", error: msg });
            return;
          }
        }
        patch({ phase: "ready" });
      } catch (err) {
        patch({ phase: "error", error: err instanceof Error ? err.message : "pipeline failed" });
      }
    },
    [patch, setStep],
  );

  const runSingle = useCallback(
    (file: File) => {
      let jobId = "";
      void run([
        {
          key: "upload",
          label: "업로드",
          fn: () => api.upload(file),
          onResult: (r) => {
            jobId = (r as { job_id: string }).job_id;
            patch({ jobId });
          },
        },
        { key: "separate", label: "Stem 분리 (Stemdeck)", fn: () => api.separate(jobId) },
        {
          key: "analyze",
          label: "오디오 분석",
          fn: () => api.analyze(jobId),
          onResult: (r) => patch({ analysis: r as AnalysisResponse }),
        },
        {
          key: "build",
          label: "MusicXML 생성",
          fn: () => api.build(jobId, file.name),
          onResult: (r) => patch({ build: r as BuildResponse }),
        },
        {
          key: "render",
          label: "악보 로드",
          fn: () => api.scoreXml(jobId),
          onResult: (r) => patch({ xml: r as string }),
        },
      ]);
    },
    [run, patch],
  );

  const runStems = useCallback(
    (files: File[]) => {
      let jobId = "";
      void run([
        {
          key: "upload",
          label: `Stem 업로드 (${files.length})`,
          fn: () => api.uploadStems(files),
          onResult: (r) => {
            jobId = (r as { job_id: string }).job_id;
            patch({ jobId });
          },
        },
        {
          key: "analyze",
          label: "오디오 분석",
          fn: () => api.analyze(jobId),
          onResult: (r) => patch({ analysis: r as AnalysisResponse }),
        },
        {
          key: "build",
          label: "MusicXML 생성",
          fn: () => api.build(jobId),
          onResult: (r) => patch({ build: r as BuildResponse }),
        },
        {
          key: "render",
          label: "악보 로드",
          fn: () => api.scoreXml(jobId),
          onResult: (r) => patch({ xml: r as string }),
        },
      ]);
    },
    [run, patch],
  );

  const runImage = useCallback(
    (file: File) => {
      let jobId = "";
      void run([
        {
          key: "upload",
          label: "이미지 업로드",
          fn: () => api.upload(file),
          onResult: (r) => {
            jobId = (r as { job_id: string }).job_id;
            patch({ jobId });
          },
        },
        { key: "omr", label: "OMR (Audiveris)", fn: () => api.omr(jobId) },
        {
          key: "render",
          label: "악보 로드",
          fn: () => api.scoreXml(jobId),
          onResult: (r) => patch({ xml: r as string }),
        },
      ]);
    },
    [run, patch],
  );

  return { ...state, runSingle, runStems, runImage, reset };
}
