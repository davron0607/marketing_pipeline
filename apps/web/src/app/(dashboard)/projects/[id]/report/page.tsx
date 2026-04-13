"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { getReports, downloadReport } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

interface Report {
  id: number;
  report_type: string;
  status: string;
  file_path: string | null;
  created_at: string;
}

export default function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);

  const { data, isLoading } = useQuery({
    queryKey: ["reports", projectId],
    queryFn: () => getReports(projectId).then((r) => r.data),
  });

  const handleDownload = async (reportId: number, filename: string) => {
    try {
      const res = await downloadReport(reportId);
      const url = URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert("Download failed.");
    }
  };

  return (
    <div>
      <div className="mb-6">
        <Link href={`/projects/${id}`} className="text-sm text-brand-600 hover:underline">
          ← Project
        </Link>
        <h1 className="text-2xl font-bold text-gray-900 mt-2">Reports</h1>
      </div>

      {isLoading && <p className="text-gray-500">Loading...</p>}

      <Card>
        {!data || (data as Report[]).length === 0 ? (
          <p className="text-sm text-gray-500">No reports yet. Run an analysis to generate reports.</p>
        ) : (
          <div className="space-y-3">
            {(data as Report[]).map((report) => (
              <div key={report.id} className="flex items-center justify-between py-3 border-b border-gray-100 last:border-0">
                <div>
                  <p className="text-sm font-medium text-gray-900">{report.report_type}</p>
                  <p className="text-xs text-gray-400">{new Date(report.created_at).toLocaleString()}</p>
                </div>
                <div className="flex items-center gap-3">
                  <Badge variant={report.status === "completed" ? "success" : "warning"}>
                    {report.status}
                  </Badge>
                  {report.status === "completed" && report.file_path && (
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => handleDownload(report.id, `report-${report.id}.pdf`)}
                    >
                      Download
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
