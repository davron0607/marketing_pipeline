"use client";

import { useState, useRef } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { uploadDataset, getUploads } from "@/lib/api";
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

export default function UploadPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  const { data: uploads, refetch } = useQuery({
    queryKey: ["uploads", projectId],
    queryFn: () => getUploads(projectId).then((r) => r.data as Upload[]),
    // Poll while any upload is still processing
    refetchInterval: (query) => {
      const rows = query.state.data;
      if (Array.isArray(rows) && rows.some((u) => u.upload_status === "processing" || u.upload_status === "pending")) {
        return 3000;
      }
      return false;
    },
  });

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setError("Please choose a file first.");
      return;
    }
    setUploading(true);
    setError("");
    setSuccessMsg("");
    try {
      await uploadDataset(projectId, file);
      setSuccessMsg(`"${file.name}" uploaded successfully. Processing will begin shortly.`);
      if (fileRef.current) fileRef.current.value = "";
      refetch();
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Upload failed. Ensure file is .csv or .xlsx and under 100 MB.";
      setError(msg);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      <div className="mb-6">
        <Link href={`/projects/${id}`} className="text-sm text-brand-600 hover:underline">
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
              className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-brand-50 file:text-brand-700 hover:file:bg-brand-100"
            />
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
          )}
          {successMsg && (
            <p className="text-sm text-green-700 bg-green-50 rounded-lg px-3 py-2">✓ {successMsg}</p>
          )}

          <Button onClick={handleUpload} loading={uploading}>
            {uploading ? "Uploading…" : "Upload"}
          </Button>
        </div>
      </Card>

      <Card title="Uploaded Files">
        {!uploads || uploads.length === 0 ? (
          <p className="text-sm text-gray-500">No files uploaded yet.</p>
        ) : (
          <div className="space-y-2">
            {uploads.map((u) => (
              <div
                key={u.id}
                className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0"
              >
                <div>
                  <p className="text-sm font-medium text-gray-900">{u.original_filename}</p>
                  <p className="text-xs text-gray-400">
                    {(u.file_size_bytes / 1024).toFixed(1)} KB
                    {u.row_count ? ` · ${u.row_count.toLocaleString()} rows` : ""}
                    {" · "}{new Date(u.created_at).toLocaleString()}
                  </p>
                </div>
                <Badge variant={statusVariant(u.upload_status)}>
                  {u.upload_status}
                </Badge>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
