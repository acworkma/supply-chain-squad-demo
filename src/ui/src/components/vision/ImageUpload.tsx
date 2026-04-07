import { useCallback, useRef, useState } from "react";
import { Upload, AlertTriangle, RotateCcw, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface ScanImageResponse {
  status: "detected";
  closet_id: string;
  closet_name: string;
  scenario_type: string;
  items: Array<{
    name: string;
    sku: string;
    current_quantity: number;
    par_level: number;
    criticality: string;
  }>;
}

interface ImageUploadProps {
  onScanComplete: (result: ScanImageResponse, imageFile: File) => void;
}

export type { ScanImageResponse };

export function ImageUpload({ onScanComplete }: ImageUploadProps) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    async (file: File) => {
      setError(null);
      setUploading(true);
      try {
        const form = new FormData();
        form.append("file", file);
        const res = await fetch("/api/scenario/scan-image", {
          method: "POST",
          body: form,
        });
        if (res.status === 422) {
          const body = await res.json();
          setError(body.error ?? "Supply closet not detected.");
          return;
        }
        if (!res.ok) throw new Error(`Upload failed (HTTP ${res.status})`);
        const data: ScanImageResponse = await res.json();
        onScanComplete(data, file);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed");
      } finally {
        setUploading(false);
      }
    },
    [onScanComplete],
  );

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file && file.type.startsWith("image/")) handleFile(file);
    },
    [handleFile],
  );

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const onDragLeave = useCallback(() => setDragOver(false), []);

  // ── Error state ──
  if (error) {
    return (
      <div className="flex items-center justify-center h-full w-full p-8">
        <div className="w-full max-w-lg rounded-xl border border-tower-error/40 bg-tower-error/5 p-10 text-center">
          <div className="rounded-full bg-tower-error/10 p-4 mx-auto mb-4 w-fit">
            <AlertTriangle className="h-8 w-8 text-tower-error" />
          </div>
          <p className="text-lg font-semibold text-gray-200 mb-1">{error}</p>
          <p className="text-sm text-gray-500 mb-6">
            Try uploading a recognized supply closet image.
          </p>
          <button
            onClick={() => {
              setError(null);
              if (inputRef.current) inputRef.current.value = "";
            }}
            className="inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium bg-tower-accent/10 text-tower-accent border border-tower-accent/30 hover:bg-tower-accent/20 transition-colors"
          >
            <RotateCcw className="h-4 w-4" />
            Try Again
          </button>
        </div>
      </div>
    );
  }

  // ── Upload zone ──
  return (
    <div className="flex items-center justify-center h-full w-full p-8">
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        disabled={uploading}
        className={cn(
          "w-full max-w-lg rounded-xl border-2 border-dashed p-12 text-center transition-all duration-200 cursor-pointer",
          "focus:outline-none focus:ring-2 focus:ring-tower-accent/50 focus:ring-offset-2 focus:ring-offset-tower-bg",
          dragOver
            ? "border-tower-accent bg-tower-accent/10 scale-[1.02]"
            : "border-tower-border hover:border-tower-accent/50 hover:bg-white/[0.02]",
          uploading && "pointer-events-none opacity-60",
        )}
      >
        <div className="flex flex-col items-center gap-4">
          {uploading ? (
            <div className="rounded-full bg-tower-accent/10 p-5">
              <Loader2 className="h-10 w-10 text-tower-accent animate-spin" />
            </div>
          ) : (
            <div className="rounded-full bg-tower-accent/10 p-5">
              <Upload className="h-10 w-10 text-tower-accent" />
            </div>
          )}
          <div>
            <p className="text-lg font-semibold text-gray-200">
              {uploading ? "Uploading…" : "Upload Supply Closet Image"}
            </p>
            <p className="text-sm text-gray-500 mt-1">
              {uploading ? "Sending to vision service" : "Drag and drop or click to browse"}
            </p>
          </div>
        </div>
      </button>

      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={onInputChange}
      />
    </div>
  );
}
