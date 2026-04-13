"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { getFraudSummary } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

interface FraudFlag {
  respondent_id: string;
  flag_type: string;
  confidence: number;
  details: string;
}

interface FraudSummary {
  total_respondents: number;
  flagged_count: number;
  fraud_rate: number;
  flags: FraudFlag[];
}

export default function FraudPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["fraud", projectId],
    queryFn: () => getFraudSummary(projectId).then((r) => r.data),
  });

  const summary = data as FraudSummary | undefined;

  return (
    <div>
      <div className="mb-6">
        <Link href={`/projects/${id}`} className="text-sm text-brand-600 hover:underline">
          ← Project
        </Link>
        <h1 className="text-2xl font-bold text-gray-900 mt-2">Fraud Summary</h1>
      </div>

      {isLoading && <p className="text-gray-500">Loading...</p>}
      {isError && <p className="text-red-500">No fraud analysis available. Run analysis first.</p>}

      {summary && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <Card>
              <p className="text-sm text-gray-500">Total Respondents</p>
              <p className="text-3xl font-bold text-gray-900 mt-1">{summary.total_respondents}</p>
            </Card>
            <Card>
              <p className="text-sm text-gray-500">Flagged</p>
              <p className="text-3xl font-bold text-red-600 mt-1">{summary.flagged_count}</p>
            </Card>
            <Card>
              <p className="text-sm text-gray-500">Fraud Rate</p>
              <p className="text-3xl font-bold text-orange-600 mt-1">
                {(summary.fraud_rate * 100).toFixed(1)}%
              </p>
            </Card>
          </div>

          <Card title="Flagged Respondents">
            {summary.flags.length === 0 ? (
              <p className="text-sm text-gray-500">No fraud flags detected.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead>
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Respondent ID</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Flag Type</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Confidence</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Details</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {summary.flags.map((flag, i) => (
                      <tr key={i}>
                        <td className="px-4 py-3 text-sm font-mono text-gray-900">{flag.respondent_id}</td>
                        <td className="px-4 py-3 text-sm">
                          <Badge variant={flag.confidence > 0.8 ? "danger" : "warning"}>
                            {flag.flag_type}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-600">
                          {(flag.confidence * 100).toFixed(0)}%
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-500">{flag.details}</td>
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
