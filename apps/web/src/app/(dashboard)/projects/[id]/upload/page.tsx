"use client";

import { useState, useRef } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { uploadDatasetWithProgress, getUploads, deleteUpload } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

interface Upload {
  id: number;
  original_filename: string;
  file_size_bytes: number;
  row_count: number | null;
  upload_status: string;
  created_at: string;
}

const statusVariant = (s: string) => {
  if (s === "done") return "success";
  if (s === "failed") return "danger";
  if (s === "processing") return "warning";
  return "default";
};

function ProgressBar({ pct }: { pct: number }) {
  return (
    <div className="w-full">
      <div className="flex justify-between text-xs text-gray-500 mb-1">
        <span>Uploading…</span>
        <span>{pct}%</span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-2.5 overflow-hidden">
        <div
          className="bg-brand-500 h-2.5 rounded-full transition-all duration-200"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function UploadPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);

  const [progress, setProgress] = useState<number | null>(null); // null = idle
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const { data: uploads } = useQuery({
    queryKey: ["uploads", projectId],
    queryFn: () => getUploads(projectId).then((r) => r.data as Upload[]),
    refetchInterval: (query) => {
      const rows = query.state.data;
      if (
        Array.isArray(rows) &&
        rows.some(
          (u) => u.upload_status === "processing" || u.upload_status === "pending"
        )
      )
        return 3000;
      return false;
    },
  });

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setError("Please choose a file first.");
      return;
    }
    setError("");
    setSuccessMsg("");
    setProgress(0);
    try {
      await uploadDatasetWithProgress(projectId, file, setProgress);
      setSuccessMsg(`"${file.name}" uploaded. Processing will start shortly.`);
      if (fileRef.current) fileRef.current.value = "";
      queryClient.invalidateQueries({ queryKey: ["uploads", projectId] });
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Upload failed. Ensure the file is .csv or .xlsx and under 100 MB.";
      setError(msg);
    } finally {
      setProgress(null);
    }
  };

  const handleDelete = async (uploadId: number) => {
    if (!confirm("Delete this file and all associated data?")) return;
    setDeletingId(uploadId);
    try {
      await deleteUpload(projectId, uploadId);
      queryClient.invalidateQueries({ queryKey: ["uploads", projectId] });
    } catch {
      alert("Delete failed. Please try again.");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div>
      <div className="mb-6">
        <Link
          href={`/projects/${id}`}
          className="text-sm text-brand-600 hover:underline"
        >
          ← Project
        </Link>
        <h1 className="text-2xl font-bold text-gray-900 mt-2">Upload Dataset</h1>
      </div>

      <Card className="mb-6">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Select CSV or XLSX file
            </label>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              disabled={progress !== null}
              className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-brand-50 file:text-brand-700 hover:file:bg-brand-100 disabled:opacity-50"
            />
          </div>

          {progress !== null && <ProgressBar pct={progress} />}

          {error && (
            <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
          {successMsg && (
            <p className="text-sm text-green-700 bg-green-50 rounded-lg px-3 py-2">
              ✓ {successMsg}
            </p>
          )}

          <Button onClick={handleUpload} loading={progress !== null} disabled={progress !== null}>
            {progress !== null ? `Uploading… ${progress}%` : "Upload"}
          </Button>
        </div>
      </Card>

      <Card title="Uploaded Files">
        {!uploads || uploads.length === 0 ? (
          <p className="text-sm text-gray-500">No files uploaded yet.</p>
        ) : (
          <div className="divide-y divide-gray-100">
            {uploads.map((u) => (
              <div
                key={u.id}
                className="flex items-center justify-between py-3"
              >
                <div className="min-w-0 flex-1 pr-4">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {u.original_filename}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {(u.file_size_bytes / 1024).toFixed(1)} KB
                    {u.row_count
                      ? ` · ${u.row_count.toLocaleString()} rows`
                      : ""}
                    {" · "}
                    {new Date(u.created_at).toLocaleString()}
                  </p>
                  {/* Processing spinner hint */}
                  {(u.upload_status === "processing" ||
                    u.upload_status === "pending") && (
                    <p className="text-xs text-yellow-600 mt-0.5 animate-pulse">
                      Pipeline running — fraud detection &amp; analytics in progress…
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-3 shrink-0">
                  <Badge variant={statusVariant(u.upload_status)}>
                    {u.upload_status}
                  </Badge>
                  <button
                    onClick={() => handleDelete(u.id)}
                    disabled={deletingId === u.id}
                    className="text-xs text-red-500 hover:text-red-700 disabled:opacity-40 transition-colors px-2 py-1 rounded hover:bg-red-50"
                    title="Delete file"
                  >
                    {deletingId === u.id ? "…" : "Delete"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
