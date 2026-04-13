"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { getUploads, runAnalysis, getJobs } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { jobStatusBadge } from "@/components/ui/Badge";

interface Upload { id: number; filename: string }
interface Job { id: number; job_type: string; status: string; created_at: string; error_message?: string }

export default function AnalysisPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);
  const queryClient = useQueryClient();
  const [selectedUpload, setSelectedUpload] = useState<number | null>(null);

  const { data: uploads } = useQuery({
    queryKey: ["uploads", projectId],
    queryFn: () => getUploads(projectId).then((r) => r.data),
  });

  const { data: jobs } = useQuery({
    queryKey: ["jobs", projectId],
    queryFn: () => getJobs(projectId).then((r) => r.data),
    refetchInterval: 3000,
  });

  const mutation = useMutation({
    mutationFn: () => runAnalysis(projectId, selectedUpload!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs", projectId] }),
  });

  return (
    <div>
      <div className="mb-6">
        <Link href={`/projects/${id}`} className="text-sm text-brand-600 hover:underline">
          ← Project
        </Link>
        <h1 className="text-2xl font-bold text-gray-900 mt-2">Run Analysis</h1>
      </div>

      <Card className="mb-6">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Select Dataset
            </label>
            <select
              value={selectedUpload ?? ""}
              onChange={(e) => setSelectedUpload(Number(e.target.value))}
              className="block w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="">-- Choose uploaded file --</option>
              {(uploads as Upload[] | undefined)?.map((u) => (
                <option key={u.id} value={u.id}>{u.filename}</option>
              ))}
            </select>
          </div>
          <Button
            onClick={() => mutation.mutate()}
            loading={mutation.isPending}
            disabled={!selectedUpload}
          >
            Start Full Analysis
          </Button>
          {mutation.isSuccess && (
            <p className="text-sm text-green-600">Analysis job queued successfully.</p>
          )}
          {mutation.isError && (
            <p className="text-sm text-red-600">Failed to start analysis. Try again.</p>
          )}
        </div>
      </Card>

      <Card title="Analysis Jobs">
        {!jobs || (jobs as Job[]).length === 0 ? (
          <p className="text-sm text-gray-500">No jobs yet.</p>
        ) : (
          <div className="space-y-3">
            {(jobs as Job[]).map((job) => (
              <div key={job.id} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                <div>
                  <p className="text-sm font-medium">{job.job_type}</p>
                  <p className="text-xs text-gray-400">{new Date(job.created_at).toLocaleString()}</p>
                  {job.error_message && <p className="text-xs text-red-500">{job.error_message}</p>}
                </div>
                {jobStatusBadge(job.status)}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
