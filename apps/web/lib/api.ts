export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

export type Experience = {
  id?: string;
  kind: string;
  title: string;
  organization: string;
  start_date: string;
  end_date: string;
  description: string;
  tags: string[];
  confirmed: boolean;
};

export type Profile = {
  id: string;
  owner_id: string;
  full_name: string;
  current_school: string;
  current_major: string;
  degree: string;
  gpa: number | null;
  gpa_scale: number | null;
  language_scores: Record<string, number>;
  target_countries: string[];
  target_fields: string[];
  intake: string;
  budget: number | null;
  preferences: Record<string, unknown>;
  confirmed: boolean;
  experiences: Experience[];
  updated_at: string;
};

export type ParsedDocument = {
  id: string;
  filename: string;
  mime_type: string;
  kind: string;
  parse_status: string;
  extracted_data: Record<string, unknown>;
  created_at: string;
};

export type Requirement = {
  deadline_raw: string;
  deadline: string | null;
  deadlines: Array<{ date: string; raw: string; round?: string; source_id?: string; url?: string }>;
  min_gpa: number | null;
  language: Record<string, number>;
  prerequisites: string[];
  materials: string[];
  fees: Record<string, number | string>;
  source_ids: string[];
  verified: boolean;
};

export type Program = {
  id: string;
  university: string;
  name: string;
  degree: string;
  country: string;
  city: string;
  field: string;
  duration_months: number | null;
  tuition: number | null;
  currency: string;
  official_url: string;
  summary: string;
  requirement: Requirement | null;
  sources: { id: string; url: string; title: string; status: string; fetched_at: string }[];
  evidence: { id: string; source_id: string; field: string; quote: string; locator: string; confidence: number }[];
};

export type ProgramRecommendation = {
  program: Program;
  score: number;
  reasons: string[];
};

export type Shortlist = {
  id: string;
  name: string;
  rationale: string;
  created_at: string;
  items: {
    id: string;
    program: Program;
    tier: "reach" | "target" | "safer";
    score: number;
    rationale: string;
    risks: string[];
  }[];
};

export type MaterialPlan = {
  id: string;
  program_id: string;
  checklist: { name: string; required: boolean; status: string; source_verified: boolean }[];
  cv_plan: Record<string, unknown>;
  ps_plan: Record<string, unknown>;
  gaps: string[];
  created_at: string;
};

export type MaterialArtifact = {
  id: string;
  document_id: string;
  program_id: string | null;
  kind: "cv" | "ps";
  scope: "general" | "program";
  version_name: string;
  language: string;
  status: "draft" | "ready" | "submitted";
  notes: string;
  filename: string;
  parse_status: string;
  created_at: string;
  updated_at: string;
};

export type MaterialPreflight = {
  ready_to_upload: boolean;
  artifact_id: string;
  program_id: string;
  checks: { name: string; passed: boolean }[];
  warnings: string[];
};

export type MaterialDraft = {
  id: string;
  program_id: string | null;
  slot_key: string;
  parent_id: string | null;
  derived_from_id: string | null;
  root_id: string | null;
  version_number: number;
  revision_type: "generated" | "derived" | "ai_revision" | "manual_edit" | "restored";
  change_summary: string;
  kind: "cv" | "ps" | "recommendation";
  title: string;
  language: "English" | "Chinese";
  prompt: string;
  content: string;
  source_experience_ids: string[];
  warnings: string[];
  model_info: { provider?: string; model?: string; conversation_id?: string; [key: string]: unknown };
  status: "draft" | "reviewed";
  created_at: string;
  updated_at: string;
};

export type PackageMaterial = {
  material_key: string;
  slot_key?: string;
  category?: string;
  official_name?: string;
  generatable?: boolean;
  name: string;
  required: boolean;
  status: "ready" | "needs_edit" | "unverified" | "missing" | "manual_review";
  source_verified: boolean;
  candidate_assets: {
    type: string;
    id: string;
    label: string;
    program_id?: string | null;
    scope?: "general" | "current_program" | "other_program";
    status?: "draft" | "reviewed";
  }[];
  selected_asset_type: string;
  selected_asset_id: string;
  note: string;
};

export type WritingMessage = { id: string; role: "user" | "assistant"; content: string; sources: Array<Record<string, unknown>>; created_at: string };
export type WritingConversation = {
  id: string; title: string; program_id: string; slot_key: string;
  material_kind: "cv" | "ps" | "recommendation"; resource_ids: string[];
  messages: WritingMessage[]; latest_draft: MaterialDraft | null;
  created_at: string; updated_at: string;
};

export type AssistantConversation = {
  id: string; title: string; scene: "application" | "material";
  program_id: string | null; program_label: string; slot_key: string; material_kind: string;
  pinned: boolean;
  resource_ids: string[];
  messages: WritingMessage[]; created_at: string; updated_at: string;
};

export type ApplicationPackage = {
  id: string;
  program: Program;
  shortlist_id: string | null;
  official_verified: boolean;
  checklist: PackageMaterial[];
  gaps: string[];
  ready: boolean;
  plan_confirmed: boolean;
  status: "needs_official_verification" | "materials_in_progress" | "ready";
  created_at: string;
  updated_at: string;
};

export type MaterialAssetPreview = { title: string; kind: string; mime_type: string; content: string; raw_url: string };

export type Task = {
  id: string;
  program_id: string | null;
  title: string;
  category: string;
  status: string;
  due_date: string | null;
  priority: string;
  details: string;
  created_at: string;
};

export type Application = {
  id: string;
  program_id: string;
  status: "planning" | "materials" | "ready" | "submitted" | "interview" | "offer" | "rejected" | "withdrawn";
  round_name: string;
  notes: string;
  created_at: string;
  updated_at: string;
};

export type Skill = {
  name: string;
  version: string;
  description: string;
  tools: string[];
  enabled: boolean;
};

export type Memory = {
  id: string;
  memory_type: string;
  key: string;
  value: Record<string, unknown>;
  source_type: string;
  source_id: string | null;
  confidence: number;
  active: boolean;
  updated_at: string;
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `请求失败：${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; database: string; llm_mode: string; version: string }>("/health"),
  profile: () => request<Profile>("/profile"),
  saveProfile: (profile: Omit<Profile, "id" | "owner_id" | "updated_at">) =>
    request<Profile>("/profile", { method: "PUT", body: JSON.stringify(profile) }),
  profileExportUrl: `${API_URL}/profile/export`,
  deleteProfile: async () => {
    const response = await fetch(`${API_URL}/profile?confirm=DELETE_MY_P0_DATA`, { method: "DELETE" });
    if (!response.ok) throw new Error(await response.text());
  },
  uploadDocument: async (file: File, kind: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("kind", kind);
    const response = await fetch(`${API_URL}/documents`, { method: "POST", body: form });
    if (!response.ok) throw new Error(await response.text());
    return response.json() as Promise<ParsedDocument>;
  },
  documents: () => request<ParsedDocument[]>("/documents"),
  documentDownloadUrl: (id: string) => `${API_URL}/documents/${id}/download`,
  deleteDocument: async (id: string) => {
    const response = await fetch(`${API_URL}/documents/${id}`, { method: "DELETE" });
    if (!response.ok) throw new Error(await response.text());
  },
  confirmDocument: (id: string, acceptedFields: string[]) => request<Profile>(`/documents/${id}/confirm`, {
    method: "POST", body: JSON.stringify({ accepted_fields: acceptedFields }),
  }),
  programs: (query = "", personalized = true) => request<Program[]>(`/programs?q=${encodeURIComponent(query)}&personalized=${personalized}`),
  program: (id: string) => request<Program>(`/programs/${id}`),
  programRecommendations: (query = "", excludeIds: string[] = []) => request<ProgramRecommendation[]>(
    `/programs/recommendations?q=${encodeURIComponent(query)}&limit=5&exclude_ids=${encodeURIComponent(excludeIds.join(","))}`,
    { method: "POST" },
  ),
  verifyProgram: (id: string) => request(`/programs/${id}/verify`, { method: "POST" }),
  verifyMatchedPrograms: (limit = 5) => request<{ matched_count: number; attempted_count: number; verified_count: number; needs_review_count: number; failed_count: number }>(`/programs/verify-matched?limit=${limit}`, { method: "POST" }),
  shortlists: () => request<Shortlist[]>("/shortlists"),
  createShortlist: (programIds: string[], name = "我的 P0 选校方案") =>
    request<Shortlist>("/shortlists", {
      method: "POST",
      body: JSON.stringify({ name, program_ids: programIds }),
    }),
  addShortlistItems: (programIds: string[]) => request<Shortlist>("/shortlists/items", {
    method: "POST", body: JSON.stringify({ program_ids: programIds }),
  }),
  removeShortlistItem: async (shortlistId: string, programId: string) => {
    const response = await fetch(`${API_URL}/shortlists/${shortlistId}/items/${programId}`, { method: "DELETE" });
    if (!response.ok) throw new Error(await response.text());
  },
  materialPlans: () => request<MaterialPlan[]>("/material-plans"),
  createMaterialPlan: (programId: string) =>
    request<MaterialPlan>("/material-plans", {
      method: "POST",
      body: JSON.stringify({ program_id: programId }),
    }),
  materialArtifacts: () => request<MaterialArtifact[]>("/material-artifacts"),
  createMaterialArtifact: (values: {
    document_id: string; program_id: string | null; kind: "cv" | "ps";
    scope: "general" | "program"; version_name: string; status: "draft" | "ready";
  }) => request<MaterialArtifact>("/material-artifacts", { method: "POST", body: JSON.stringify(values) }),
  updateMaterialArtifact: (id: string, values: Partial<MaterialArtifact>) =>
    request<MaterialArtifact>(`/material-artifacts/${id}`, { method: "PATCH", body: JSON.stringify(values) }),
  materialPreflight: (artifactId: string, programId: string) =>
    request<MaterialPreflight>("/material-artifacts/preflight", {
      method: "POST", body: JSON.stringify({ artifact_id: artifactId, program_id: programId }),
    }),
  materialDrafts: (programId = "", slotKey = "") => request<MaterialDraft[]>(`/material-drafts?program_id=${encodeURIComponent(programId)}&slot_key=${encodeURIComponent(slotKey)}`),
  materialDraftExportUrl: (id: string, format: "docx" | "pdf") =>
    `${API_URL}/material-drafts/${id}/export?format=${format}`,
  generateMaterialDraft: (values: { kind: "cv" | "ps" | "recommendation"; program_id: string | null; slot_key?: string; language: "English" | "Chinese"; prompt: string }) =>
    request<MaterialDraft>("/material-drafts/generate", { method: "POST", body: JSON.stringify(values) }),
  updateMaterialDraft: (id: string, values: Partial<Pick<MaterialDraft, "title" | "content" | "status">>) =>
    request<MaterialDraft>(`/material-drafts/${id}`, { method: "PATCH", body: JSON.stringify(values) }),
  restoreMaterialDraft: (id: string) => request<MaterialDraft>(`/material-drafts/${id}/restore`, { method: "POST" }),
  writingConversations: (programId: string, slotKey: string) => request<WritingConversation[]>(`/writing-conversations?program_id=${encodeURIComponent(programId)}&slot_key=${encodeURIComponent(slotKey)}`),
  assistantConversations: () => request<AssistantConversation[]>("/assistant-conversations"),
  createAssistantConversation: (values: { title?: string; resource_ids?: string[] }) =>
    request<AssistantConversation>("/assistant-conversations", { method: "POST", body: JSON.stringify(values) }),
  updateAssistantConversation: (id: string, values: { title?: string; pinned?: boolean; resource_ids?: string[] }) =>
    request<AssistantConversation>(`/assistant-conversations/${id}`, { method: "PATCH", body: JSON.stringify(values) }),
  deleteAssistantConversation: async (id: string) => {
    const response = await fetch(`${API_URL}/assistant-conversations/${id}`, { method: "DELETE" });
    if (!response.ok) throw new Error(await response.text());
  },
  createWritingConversation: (values: { program_id: string; slot_key: string; material_kind: "cv" | "ps" | "recommendation"; title: string; resource_ids: string[] }) => request<WritingConversation>("/writing-conversations", { method: "POST", body: JSON.stringify(values) }),
  updateWritingConversation: (id: string, values: { title?: string; resource_ids?: string[] }) => request<WritingConversation>(`/writing-conversations/${id}`, { method: "PATCH", body: JSON.stringify(values) }),
  sendWritingMessage: (id: string, message: string, signal?: AbortSignal) => request<WritingConversation>(`/writing-conversations/${id}/messages`, { method: "POST", body: JSON.stringify({ message }), signal }),
  cancelWritingGeneration: (id: string) => request<{ cancelled: boolean }>(`/writing-conversations/${id}/cancel`, { method: "POST" }),
  applicationPackages: () => request<ApplicationPackage[]>("/application-packages"),
  refreshApplicationPackage: (programId: string) =>
    request<ApplicationPackage>(`/application-packages/${programId}/refresh`, { method: "POST" }),
  updatePackageMaterial: (packageId: string, values: { material_key: string; status: PackageMaterial["status"]; selected_asset_type: string; selected_asset_id: string; note: string }) =>
    request<ApplicationPackage>(`/application-packages/${packageId}/materials`, { method: "PATCH", body: JSON.stringify(values) }),
  confirmPackagePlan: (packageId: string) => request<ApplicationPackage>(`/application-packages/${packageId}/confirm-plan`, { method: "POST" }),
  materialAssetPreview: (type: string, id: string) => request<MaterialAssetPreview>(`/material-assets/${encodeURIComponent(type)}/${encodeURIComponent(id)}/preview`),
  tasks: () => request<Task[]>("/tasks"),
  applications: () => request<Application[]>("/applications"),
  createApplication: (programId: string) =>
    request<Application>("/applications", { method: "POST", body: JSON.stringify({ program_id: programId }) }),
  updateApplication: (id: string, values: Partial<Application>) =>
    request<Application>(`/applications/${id}`, { method: "PATCH", body: JSON.stringify(values) }),
  createTimeline: (programId: string) =>
    request<Task[]>("/tasks/timeline", {
      method: "POST",
      body: JSON.stringify({ program_id: programId }),
    }),
  updateTask: (id: string, values: Partial<Task>) =>
    request<Task>(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(values) }),
  skills: () => request<Skill[]>("/skills"),
  memories: () => request<Memory[]>("/memories"),
  deleteMemory: async (id: string) => {
    const response = await fetch(`${API_URL}/memories/${id}`, { method: "DELETE" });
    if (!response.ok) throw new Error(await response.text());
  },
};

export type AgentEvent = { event: string; data: Record<string, unknown> };

export async function streamAgent(
  message: string,
  onEvent: (event: AgentEvent) => void,
  conversationId?: string,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_URL}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId || null }),
    signal,
  });
  if (!response.ok || !response.body) throw new Error("Agent 连接失败");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const event = block.match(/^event: (.+)$/m)?.[1];
      const data = block.match(/^data: (.+)$/m)?.[1];
      if (event && data) onEvent({ event, data: JSON.parse(data) });
    }
  }
}
