"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getProject, getJobs } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { jobStatusBadge } from "@/components/ui/Badge";

interface Job {
  id: number;
  job_type: string;
  status: string;
  created_at: string;
}

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);

  const { data: project, isLoading } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId).then((r) => r.data),
  });

  const { data: jobs } = useQuery({
    queryKey: ["jobs", projectId],
    queryFn: () => getJobs(projectId).then((r) => r.data),
    refetchInterval: 5000,
  });

  if (isLoading) return <p className="text-gray-500">Loading...</p>;

  return (
    <div>
      <div className="mb-6">
        <Link href="/projects" className="text-sm text-brand-600 hover:underline">
          ← Projects
        </Link>
        <h1 className="text-2xl font-bold text-gray-900 mt-2">{project?.name}</h1>
        {project?.description && (
          <p className="text-gray-500 mt-1">{project.description}</p>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <Link href={`/projects/${id}/upload`}>
          <Card className="hover:shadow-md cursor-pointer text-center">
            <div className="text-2xl mb-2">📁</div>
            <p className="font-medium">Upload Dataset</p>
          </Card>
        </Link>
        <Link href={`/projects/${id}/analysis`}>
          <Card className="hover:shadow-md cursor-pointer text-center">
            <div className="text-2xl mb-2">▶</div>
            <p className="font-medium">Run Analysis</p>
          </Card>
        </Link>
        <Link href={`/projects/${id}/fraud`}>
          <Card className="hover:shadow-md cursor-pointer text-center">
            <div className="text-2xl mb-2">🔍</div>
            <p className="font-medium">Fraud Summary</p>
          </Card>
        </Link>
        <Link href={`/projects/${id}/report`}>
          <Card className="hover:shadow-md cursor-pointer text-center">
            <div className="text-2xl mb-2">📄</div>
            <p className="font-medium">View Reports</p>
          </Card>
        </Link>
      </div>

      <Card title="Recent Jobs">
        {!jobs || (jobs as Job[]).length === 0 ? (
          <p className="text-gray-500 text-sm">No jobs yet. Upload a dataset and run analysis.</p>
        ) : (
          <div className="space-y-3">
            {(jobs as Job[]).map((job) => (
              <div key={job.id} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                <div>
                  <p className="text-sm font-medium text-gray-900">{job.job_type}</p>
                  <p className="text-xs text-gray-400">{new Date(job.created_at).toLocaleString()}</p>
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
