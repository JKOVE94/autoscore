import type {
  AnalysisResponse,
  BackendStatus,
  BuildResponse,
  JobStatus,
  OMRResult,
  StemSplitResult,
  UploadResponse,
} from "../types";

const BASE = import.meta.env.VITE_API_BASE ?? "";

export class ApiRequestError extends Error {
  code: string;
  detail?: unknown;
  status: number;

  constructor(status: number, code: string, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: init?.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...init,
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const err = data?.error ?? {};
    throw new ApiRequestError(
      res.status,
      err.code ?? "http_error",
      err.message ?? res.statusText,
      err.detail,
    );
  }
  return data as T;
}

export const api = {
  upload(file: File): Promise<UploadResponse> {
    const form = new FormData();
    form.append("file", file);
    return request<UploadResponse>("/api/upload", { method: "POST", body: form });
  },

  uploadStems(files: File[]): Promise<UploadResponse> {
    const form = new FormData();
    for (const f of files) form.append("files", f);
    return request<UploadResponse>("/api/upload-stems", { method: "POST", body: form });
  },

  separate(jobId: string): Promise<StemSplitResult> {
    return request<StemSplitResult>(`/api/separate/${jobId}`, { method: "POST" });
  },

  omr(jobId: string): Promise<OMRResult> {
    return request<OMRResult>(`/api/omr/${jobId}`, { method: "POST" });
  },

  analyze(jobId: string, window?: [number, number]): Promise<AnalysisResponse> {
    return request<AnalysisResponse>(`/api/analyze/${jobId}`, {
      method: "POST",
      body: JSON.stringify({ window: window ?? null }),
    });
  },

  build(jobId: string, title?: string): Promise<BuildResponse> {
    return request<BuildResponse>(`/api/build/${jobId}`, {
      method: "POST",
      body: JSON.stringify({ title: title ?? null }),
    });
  },

  jobStatus(jobId: string): Promise<JobStatus> {
    return request<JobStatus>(`/api/jobs/${jobId}`);
  },

  backends(): Promise<BackendStatus> {
    return request<BackendStatus>("/api/analyze/backends");
  },

  async scoreXml(jobId: string): Promise<string> {
    const res = await fetch(`${BASE}/api/score/${jobId}`);
    if (!res.ok) {
      throw new ApiRequestError(res.status, "score_fetch_failed", "Could not load MusicXML");
    }
    return res.text();
  },
};
