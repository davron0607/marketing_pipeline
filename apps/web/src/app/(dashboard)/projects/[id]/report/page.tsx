"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { generateReport, getLatestReport } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

interface LatestReport {
  id: number;
  report_type: string;
  status: string;
  storage_key: string | null;
  file_size_bytes: number | null;
  generated_at: string | null;
  created_at: string;
  download_url: string | null;
}

export default function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState("");

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["latest-report", projectId],
    queryFn: () =>
      getLatestReport(projectId)
        .then((r) => r.data as LatestReport)
        .catch(() => null),
    refetchInterval: (query) => {
      const d = query.state.data;
      if (d && d.status === "pending") return 3000;
      return false;
    },
  });

  const handleGenerate = async () => {
    setGenerating(true);
    setGenError("");
    try {
      await generateReport(projectId);
      setTimeout(() => refetch(), 2000);
    } catch {
      setGenError("Failed to start report generation. Run an analysis first.");
    } finally {
      setGenerating(false);
    }
  };

  const handleDownload = (url: string) => {
    // Replace internal Docker hostname with public host port
    const publicUrl = url
      .replace("http://minio:9000", `http://localhost:3503`)
      .replace("https://minio:9000", `http://localhost:3503`);
    window.open(publicUrl, "_blank");
  };

  return (
    <div>
      <div className="mb-6">
        <Link href={`/projects/${id}`} className="text-sm text-brand-600 hover:underline">
          ← Project
        </Link>
        <h1 className="text-2xl font-bold text-gray-900 mt-2">Reports</h1>
      </div>

      <Card className="mb-6">
        <div className="flex items-center gap-4">
          <Button onClick={handleGenerate} loading={generating}>
            Generate PDF Report
          </Button>
          <p className="text-xs text-gray-400">
            Builds a full PDF with fraud cleanup, key findings, and segment comparisons.
          </p>
        </div>
        {genError && <p className="text-sm text-red-600 mt-2">{genError}</p>}
      </Card>

      {isLoading && <p className="text-gray-500">Loading…</p>}

      {!isLoading && !data && (
        <Card>
          <p className="text-sm text-gray-500">No reports yet. Click Generate above to create one.</p>
        </Card>
      )}

      {data && (
        <Card title="Latest Report">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <Badge variant={data.status === "completed" ? "success" : data.status === "failed" ? "danger" : "warning"}>
                  {data.status}
                </Badge>
                <span className="text-sm text-gray-500 uppercase">{data.report_type}</span>
              </div>
              {data.generated_at && (
                <p className="text-xs text-gray-400">
                  Generated: {new Date(data.generated_at).toLocaleString()}
                </p>
              )}
              {data.file_size_bytes && (
                <p className="text-xs text-gray-400">
                  Size: {(data.file_size_bytes / 1024).toFixed(1)} KB
                </p>
              )}
              {data.status === "pending" && (
                <p className="text-sm text-yellow-600 mt-2 animate-pulse">
                  Generating report… this may take 10–30 seconds.
                </p>
              )}
            </div>
            {data.status === "completed" && data.download_url && (
              <Button
                variant="secondary"
                onClick={() => handleDownload(data.download_url!)}
              >
                ↓ Download PDF
              </Button>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
