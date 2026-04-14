"use client";

import { useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { uploadDataset, getUploads } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

interface Upload {
  id: number;
  filename?: string;
  original_filename?: string;
  file_size?: number;
  file_size_bytes?: number;
  row_count: number | null;
  created_at: string;
  upload_status?: string;
}

export default function UploadPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const { data: uploads, refetch } = useQuery({
    queryKey: ["uploads", projectId],
    queryFn: () => getUploads(projectId).then((r) => r.data),
  });

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      await uploadDataset(projectId, file);
      refetch();
      if (fileRef.current) fileRef.current.value = "";
    } catch {
      setError("Upload failed. Ensure file is CSV or XLSX.");
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
            <p className="text-sm text-red-600">{error}</p>
          )}
          <Button onClick={handleUpload} loading={uploading}>
            Upload
          </Button>
        </div>
      </Card>

      <Card title="Uploaded Files">
        {!uploads || (uploads as Upload[]).length === 0 ? (
          <p className="text-sm text-gray-500">No files uploaded yet.</p>
        ) : (
          <div className="space-y-2">
            {(uploads as Upload[]).map((u) => (
              <div key={u.id} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    {u.original_filename ?? u.filename}
                  </p>
                  <p className="text-xs text-gray-400">
                    {((u.file_size_bytes ?? u.file_size ?? 0) / 1024).toFixed(1)} KB
                    {u.row_count ? ` · ${u.row_count} rows` : ""}
                    {u.upload_status ? ` · ${u.upload_status}` : ""}
                    {" · "}{new Date(u.created_at).toLocaleString()}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
