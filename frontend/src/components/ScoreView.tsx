import { OpenSheetMusicDisplay } from "opensheetmusicdisplay";
import { useEffect, useRef } from "react";

interface Props {
  xml: string | null;
  onReady?: (osmd: OpenSheetMusicDisplay) => void;
  onError?: (message: string) => void;
}

export function ScoreView({ xml, onReady, onError }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const osmdRef = useRef<OpenSheetMusicDisplay | null>(null);

  useEffect(() => {
    if (!hostRef.current) return;
    const osmd = new OpenSheetMusicDisplay(hostRef.current, {
      autoResize: true,
      drawTitle: true,
      followCursor: true,
      backend: "svg",
    });
    osmdRef.current = osmd;
    return () => {
      try {
        osmd.clear();
      } catch {
        /* noop */
      }
      osmdRef.current = null;
    };
  }, []);

  useEffect(() => {
    const osmd = osmdRef.current;
    if (!osmd || !xml) return;
    let cancelled = false;
    osmd
      .load(xml)
      .then(() => {
        if (cancelled) return;
        osmd.render();
        try {
          osmd.cursor?.show();
        } catch {
          /* cursor optional */
        }
        onReady?.(osmd);
      })
      .catch((err: unknown) => {
        onError?.(err instanceof Error ? err.message : "Failed to render score");
      });
    return () => {
      cancelled = true;
    };
  }, [xml, onReady, onError]);

  return (
    <div className="osmd-container rounded-lg border border-slate-200 bg-white p-4">
      {!xml && (
        <p className="py-16 text-center text-sm text-slate-400">
          악보가 아직 없습니다. 파일을 업로드하고 파이프라인을 실행하세요.
        </p>
      )}
      <div ref={hostRef} />
    </div>
  );
}
