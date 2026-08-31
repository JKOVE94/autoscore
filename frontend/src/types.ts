export type InputMode = "single_audio" | "presplit_stems" | "score_image";

export interface UploadResponse {
  job_id: string;
  mode: InputMode;
  kind: "audio" | "image";
  stored_files: string[];
  message: string;
}

export interface StemTrack {
  name: string;
  path: string;
  duration_sec: number | null;
}

export interface StemSplitResult {
  job_id: string;
  engine: string;
  source: string;
  tracks: StemTrack[];
  elapsed_sec: number;
}

export interface OMRResult {
  job_id: string;
  source: string;
  musicxml_path: string;
  measure_count: number;
  part_count: number;
  warnings: string[];
  elapsed_sec: number;
}

export interface NoteEvent {
  start_sec: number;
  end_sec: number;
  midi: number;
  velocity: number;
  confidence: number;
}

export interface ChordEvent {
  start_sec: number;
  end_sec: number;
  symbol: string;
  root_pc: number | null;
  quality: string | null;
  confidence: number;
}

export interface AnalysisResponse {
  job_id: string;
  duration_sec: number;
  bpm: number;
  key: string;
  time_signature: string;
  beat_times: number[];
  downbeat_times: number[];
  notes: NoteEvent[];
  chords: ChordEvent[];
  backends: Record<string, string>;
  window_offset_sec: number;
  result_path?: string | null;
}

export interface BuildResponse {
  job_id: string;
  musicxml_path: string;
  measure_count: number;
  note_count: number;
  rest_count: number;
  chord_symbol_count: number;
  dropped_notes: number;
  warnings: string[];
}

export interface MeasureWindow {
  number: number;
  start_sec: number;
  end_sec: number;
}

export interface RegenerateResponse {
  job_id: string;
  changed_measures: number[];
  span_sec: [number, number];
  measure_count: number;
  note_count: number;
  chord_symbol_count: number;
  musicxml: string;
  warnings: string[];
}

export interface CompressResponse {
  job_id: string;
  musicxml_path: string;
  musicxml: string;
  original_measures: number;
  compressed_measures: number;
  operations: string[];
  song_form: string | null;
}

export interface JobStatus {
  job_id: string;
  has_upload: boolean;
  has_stems: boolean;
  has_analysis: boolean;
  has_musicxml: boolean;
}

export interface BackendStatus {
  capabilities: Record<string, boolean>;
  selected: { melody: string; rhythm: string; harmony: string };
}

export interface ApiError {
  error: { code: string; message: string; detail?: unknown };
}
