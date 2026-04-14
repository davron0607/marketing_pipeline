import axios from "axios";
import Cookies from "js-cookie";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = Cookies.get("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      Cookies.remove("access_token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// ── Auth ──────────────────────────────────────────────────────────────────────
export const login = (email: string, password: string) => {
  const form = new URLSearchParams();
  form.append("username", email);
  form.append("password", password);
  return api.post("/auth/login", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
};

// ── Projects ──────────────────────────────────────────────────────────────────
export const getProjects = () => api.get("/projects");
export const getProject = (id: number) => api.get(`/projects/${id}`);
export const createProject = (data: { name: string; description?: string }) =>
  api.post("/projects", data);

// ── Uploads (new ingestion endpoint) ─────────────────────────────────────────
export const uploadDataset = (projectId: number, file: File) => {
  const form = new FormData();
  form.append("file", file);
  return api.post(`/projects/${projectId}/uploads`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};
export const getUploads = (projectId: number) =>
  api.get(`/projects/${projectId}/uploads`);

// ── Jobs ──────────────────────────────────────────────────────────────────────
export const runAnalysis = (projectId: number, uploadId: number) =>
  api.post("/jobs", { project_id: projectId, upload_id: uploadId, job_type: "full_analysis" });
export const getJobs = (projectId: number) =>
  api.get(`/jobs?project_id=${projectId}`);
export const getJob = (id: number) => api.get(`/jobs/${id}`);

// ── Fraud ─────────────────────────────────────────────────────────────────────
export const getFraudSummary = (projectId: number) =>
  api.get(`/projects/${projectId}/fraud-summary`);

// ── Analytics ─────────────────────────────────────────────────────────────────
export const getAnalytics = (projectId: number) =>
  api.get(`/projects/${projectId}/analytics-summary`);

// ── Reports ───────────────────────────────────────────────────────────────────
export const generateReport = (projectId: number) =>
  api.post(`/projects/${projectId}/generate-report`);
export const getLatestReport = (projectId: number) =>
  api.get(`/projects/${projectId}/reports/latest`);
// Legacy list endpoint (kept for compatibility)
export const getReports = (projectId: number) =>
  api.get(`/reports/project/${projectId}`);
export const downloadReport = (reportId: number) =>
  api.get(`/reports/${reportId}/download`, { responseType: "blob" });
