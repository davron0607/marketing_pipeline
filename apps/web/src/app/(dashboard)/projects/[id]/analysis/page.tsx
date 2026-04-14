"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { getAnalytics } from "@/lib/api";
import { Card } from "@/components/ui/Card";

interface SampleQuality { total: number; valid: number; review: number; reject: number; usable: number }
interface DistributionData {
  type: "single_choice" | "numeric" | "text";
  data: Record<string, unknown>;
}
interface AnalyticsSummary {
  sample_quality: SampleQuality;
  insight_texts: string[];
  distributions: Record<string, DistributionData>;
  crosstabs: Array<{ row_var: string; col_var: string; p_value: number | null; table: Record<string, Record<string, number>> }>;
  top_drivers: Array<{ variable: string; target: string; effect_size: number; method: string }>;
}

function QualityBar({ label, count, total, color }: { label: string; count: number; total: number; color: string }) {
  const pct = total > 0 ? (count / total) * 100 : 0;
  return (
    <div className="mb-3">
      <div className="flex justify-between text-xs text-gray-600 mb-1">
        <span>{label}</span>
        <span>{count.toLocaleString()} ({pct.toFixed(1)}%)</span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-2">
        <div className={`${color} h-2 rounded-full`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function SingleChoiceChart({ data }: { data: { counts: Record<string, number>; percentages: Record<string, number>; total: number } }) {
  const entries = Object.entries(data.counts).slice(0, 10);
  const max = Math.max(...entries.map(([, v]) => v));
  return (
    <div className="space-y-1.5">
      {entries.map(([label, count]) => (
        <div key={label} className="flex items-center gap-2 text-xs">
          <span className="w-24 text-right text-gray-600 truncate">{label}</span>
          <div className="flex-1 bg-gray-100 rounded h-4 relative">
            <div
              className="bg-brand-500 h-4 rounded"
              style={{ width: `${(count / max) * 100}%` }}
            />
          </div>
          <span className="w-16 text-gray-500">{count} ({data.percentages[label]?.toFixed(1)}%)</span>
        </div>
      ))}
    </div>
  );
}

function NumericStats({ data }: { data: Record<string, number | null> }) {
  const stats: [string, string][] = [
    ["Mean", data.mean != null ? Number(data.mean).toFixed(2) : "—"],
    ["Median", data.median != null ? Number(data.median).toFixed(2) : "—"],
    ["Std Dev", data.std != null ? Number(data.std).toFixed(2) : "—"],
    ["Min", data.min != null ? String(data.min) : "—"],
    ["Max", data.max != null ? String(data.max) : "—"],
    ["Count", data.count != null ? String(data.count) : "—"],
  ];
  return (
    <div className="grid grid-cols-3 gap-3">
      {stats.map(([k, v]) => (
        <div key={k} className="bg-gray-50 rounded p-2 text-center">
          <p className="text-xs text-gray-500">{k}</p>
          <p className="text-sm font-semibold text-gray-900">{v}</p>
        </div>
      ))}
    </div>
  );
}

export default function AnalysisPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["analytics", projectId],
    queryFn: () => getAnalytics(projectId).then((r) => r.data as AnalyticsSummary),
  });

  return (
    <div>
      <div className="mb-6">
        <Link href={`/projects/${id}`} className="text-sm text-brand-600 hover:underline">
          ← Project
        </Link>
        <h1 className="text-2xl font-bold text-gray-900 mt-2">Analytics Summary</h1>
      </div>

      {isLoading && <p className="text-gray-500">Loading…</p>}
      {isError && <p className="text-red-500">No analytics available yet. Run an analysis first.</p>}

      {data && (
        <div className="space-y-6">
          {/* Sample Quality */}
          <Card title="Sample Quality">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
              {[
                { label: "Total", value: data.sample_quality.total, color: "text-gray-900" },
                { label: "Valid", value: data.sample_quality.valid, color: "text-green-600" },
                { label: "Review", value: data.sample_quality.review, color: "text-yellow-600" },
                { label: "Rejected", value: data.sample_quality.reject, color: "text-red-600" },
              ].map(({ label, value, color }) => (
                <div key={label} className="text-center p-3 bg-gray-50 rounded-lg">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
                  <p className={`text-2xl font-bold ${color} mt-1`}>{value.toLocaleString()}</p>
                </div>
              ))}
            </div>
            <QualityBar label="Valid" count={data.sample_quality.valid} total={data.sample_quality.total} color="bg-green-500" />
            <QualityBar label="Review" count={data.sample_quality.review} total={data.sample_quality.total} color="bg-yellow-400" />
            <QualityBar label="Rejected" count={data.sample_quality.reject} total={data.sample_quality.total} color="bg-red-500" />
          </Card>

          {/* Insights */}
          {data.insight_texts.length > 0 && (
            <Card title="Key Insights">
              <ul className="space-y-2">
                {data.insight_texts.map((txt, i) => (
                  <li key={i} className="flex gap-2 text-sm text-gray-700">
                    <span className="text-brand-500 font-bold mt-0.5">•</span>
                    <span>{txt}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* Distributions */}
          {Object.keys(data.distributions).length > 0 && (
            <Card title="Question Distributions">
              <div className="space-y-6">
                {Object.entries(data.distributions).map(([key, dist]) => (
                  <div key={key}>
                    <h3 className="text-sm font-semibold text-gray-800 mb-2 capitalize">{key.replace(/_/g, " ")}</h3>
                    {dist.type === "single_choice" && dist.data.counts && (
                      <SingleChoiceChart data={dist.data as { counts: Record<string, number>; percentages: Record<string, number>; total: number }} />
                    )}
                    {dist.type === "numeric" && (
                      <NumericStats data={dist.data as Record<string, number | null>} />
                    )}
                    {dist.type === "text" && (
                      <p className="text-xs text-gray-500">
                        {(dist.data as { count?: number }).count ?? 0} responses ·{" "}
                        {(dist.data as { avg_length?: number }).avg_length?.toFixed(0) ?? 0} avg chars
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Top Drivers */}
          {data.top_drivers.length > 0 && (
            <Card title="Top Drivers">
              <div className="space-y-2">
                {data.top_drivers.map((d, i) => (
                  <div key={i} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                    <div>
                      <span className="text-sm font-medium text-gray-900">{d.variable}</span>
                      <span className="text-xs text-gray-400 ml-2">→ {d.target}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-24 bg-gray-100 rounded-full h-2">
                        <div className="bg-brand-500 h-2 rounded-full" style={{ width: `${d.effect_size * 100}%` }} />
                      </div>
                      <span className="text-xs font-semibold text-gray-700 w-10">{(d.effect_size * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Crosstabs */}
          {data.crosstabs.length > 0 && (
            <Card title="Segment Comparisons">
              {data.crosstabs.map((ct, i) => (
                <div key={i} className="mb-4 last:mb-0">
                  <h3 className="text-sm font-semibold text-gray-800 mb-1">
                    {ct.row_var} × {ct.col_var}
                    {ct.p_value != null && (
                      <span className={`ml-2 text-xs font-normal ${ct.p_value < 0.05 ? "text-green-600" : "text-gray-400"}`}>
                        p={ct.p_value.toFixed(3)}{ct.p_value < 0.05 ? " ✓" : ""}
                      </span>
                    )}
                  </h3>
                </div>
              ))}
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
