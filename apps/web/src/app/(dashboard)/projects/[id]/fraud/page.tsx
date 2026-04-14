"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { getFraudSummary } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

interface LabelCounts { valid?: number; review?: number; reject?: number }
interface TopReason { reason: string; count: number }
interface SuspiciousEntry { respondent_id: string; fraud_score: number; label: string; reasons: string[] }
interface FraudSummary {
  total_scored: number;
  label_counts: LabelCounts;
  label_percentages: Record<string, number>;
  top_reasons: TopReason[];
  top_suspicious: SuspiciousEntry[];
}

const labelVariant = (label: string) => {
  if (label === "reject") return "danger";
  if (label === "review") return "warning";
  return "success";
};

export default function FraudPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["fraud", projectId],
    queryFn: () => getFraudSummary(projectId).then((r) => r.data as FraudSummary),
  });

  return (
    <div>
      <div className="mb-6">
        <Link href={`/projects/${id}`} className="text-sm text-brand-600 hover:underline">
          ← Project
        </Link>
        <h1 className="text-2xl font-bold text-gray-900 mt-2">Fraud Summary</h1>
      </div>

      {isLoading && <p className="text-gray-500">Loading…</p>}
      {isError && (
        <p className="text-red-500">Failed to load fraud summary. Run an analysis first.</p>
      )}

      {data && (
        <>
          {/* KPI cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <Card>
              <p className="text-xs text-gray-500 uppercase tracking-wide">Total Scored</p>
              <p className="text-3xl font-bold text-gray-900 mt-1">{data.total_scored.toLocaleString()}</p>
            </Card>
            <Card>
              <p className="text-xs text-gray-500 uppercase tracking-wide">Valid</p>
              <p className="text-3xl font-bold text-green-600 mt-1">
                {(data.label_counts.valid ?? 0).toLocaleString()}
              </p>
              <p className="text-xs text-gray-400 mt-0.5">
                {data.label_percentages["valid"]?.toFixed(1) ?? 0}%
              </p>
            </Card>
            <Card>
              <p className="text-xs text-gray-500 uppercase tracking-wide">Review</p>
              <p className="text-3xl font-bold text-yellow-600 mt-1">
                {(data.label_counts.review ?? 0).toLocaleString()}
              </p>
              <p className="text-xs text-gray-400 mt-0.5">
                {data.label_percentages["review"]?.toFixed(1) ?? 0}%
              </p>
            </Card>
            <Card>
              <p className="text-xs text-gray-500 uppercase tracking-wide">Rejected</p>
              <p className="text-3xl font-bold text-red-600 mt-1">
                {(data.label_counts.reject ?? 0).toLocaleString()}
              </p>
              <p className="text-xs text-gray-400 mt-0.5">
                {data.label_percentages["reject"]?.toFixed(1) ?? 0}%
              </p>
            </Card>
          </div>

          {/* Top reasons */}
          {data.top_reasons.length > 0 && (
            <Card title="Top Fraud Reasons" className="mb-6">
              <div className="space-y-2">
                {data.top_reasons.map((r, i) => (
                  <div key={i} className="flex items-center justify-between py-1 border-b border-gray-100 last:border-0">
                    <span className="text-sm text-gray-700">{r.reason}</span>
                    <span className="text-sm font-semibold text-red-600">{r.count}×</span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Top suspicious respondents */}
          <Card title="Top Suspicious Respondents">
            {data.top_suspicious.length === 0 ? (
              <p className="text-sm text-gray-500">No suspicious respondents detected.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 text-sm">
                  <thead>
                    <tr className="bg-gray-50">
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Respondent ID</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Score</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Label</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Reasons</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {data.top_suspicious.map((row, i) => (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="px-4 py-3 font-mono text-gray-900">{row.respondent_id}</td>
                        <td className="px-4 py-3 font-bold text-red-600">{row.fraud_score.toFixed(1)}</td>
                        <td className="px-4 py-3">
                          <Badge variant={labelVariant(row.label)}>{row.label}</Badge>
                        </td>
                        <td className="px-4 py-3 text-gray-500 text-xs">
                          {row.reasons.join(" · ") || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
