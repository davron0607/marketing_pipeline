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

// Auth
export const login = (email: string, password: string) =>
  api.post("/auth/login", { username: email, password });

// Projects
export const getProjects = () => api.get("/projects");
export const getProject = (id: number) => api.get(`/projects/${id}`);
export const createProject = (data: { name: string; description?: string }) =>
  api.post("/projects", data);

// Uploads
export const uploadDataset = (projectId: number, file: File) => {
  const form = new FormData();
  form.append("file", file);
  return api.post(`/uploads/project/${projectId}`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};
export const getUploads = (projectId: number) =>
  api.get(`/uploads/project/${projectId}`);

// Jobs
export const runAnalysis = (projectId: number, uploadId: number) =>
  api.post("/jobs", { project_id: projectId, upload_id: uploadId, job_type: "full_analysis" });
export const getJobs = (projectId: number) =>
  api.get(`/jobs?project_id=${projectId}`);
export const getJob = (id: number) => api.get(`/jobs/${id}`);

// Fraud
export const getFraudSummary = (projectId: number) =>
  api.get(`/fraud/project/${projectId}`);

// Analytics
export const getAnalytics = (projectId: number) =>
  api.get(`/analytics/project/${projectId}`);

// Reports
export const getReports = (projectId: number) =>
  api.get(`/reports/project/${projectId}`);
export const downloadReport = (reportId: number) =>
  api.get(`/reports/${reportId}/download`, { responseType: "blob" });
