/**
 * Typed client for the E-Panchayat API.
 *
 * Replaces `persistence.ts`, which wrote to localStorage and then attempted a
 * best-effort Supabase sync that failed silently on four of five tables. Here,
 * a failed request throws an ApiError with the server's own message, so a
 * broken save looks broken instead of looking saved.
 *
 * Tokens are held in memory and mirrored to localStorage so a refresh does not
 * sign you out. An expired access token is refreshed once, transparently, and
 * the original request retried.
 */

const BASE_URL =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ||
  'http://localhost:8000/api/v1';

// Deliberately not prefixed `panchayat_` — that prefix is what
// clearPersistentCache() wipes, and tokens are managed separately.
const ACCESS_KEY = 'epanchayat_access_token';
const REFRESH_KEY = 'epanchayat_refresh_token';

// ─── Token store ────────────────────────────────────────────────────────────

let accessToken: string | null = null;
let refreshToken: string | null = null;

const readStorage = (key: string): string | null => {
  try {
    return localStorage.getItem(key);
  } catch {
    return null; // private mode, storage disabled
  }
};

const writeStorage = (key: string, value: string | null) => {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* non-fatal: tokens simply won't survive a reload */
  }
};

accessToken = readStorage(ACCESS_KEY);
refreshToken = readStorage(REFRESH_KEY);

export const setTokens = (access: string | null, refresh: string | null) => {
  accessToken = access;
  refreshToken = refresh;
  writeStorage(ACCESS_KEY, access);
  writeStorage(REFRESH_KEY, refresh);
};

export const clearTokens = () => setTokens(null, null);
export const hasSession = () => Boolean(accessToken);

// Lets the auth provider react to a refresh failure without importing React here.
let onSessionExpired: (() => void) | null = null;
export const setSessionExpiredHandler = (fn: (() => void) | null) => {
  onSessionExpired = fn;
};

// ─── Errors ─────────────────────────────────────────────────────────────────

export class ApiError extends Error {
  // Declared and assigned explicitly rather than as constructor parameter
  // properties, which this project's tsconfig forbids (erasableSyntaxOnly).
  status: number;
  detail?: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }

  /** True when the server could not be reached at all. */
  get isOffline() {
    return this.status === 0;
  }
}

const messageFrom = async (response: Response): Promise<string> => {
  try {
    const body = await response.json();
    const detail = body?.detail;
    if (typeof detail === 'string') return detail;
    // FastAPI validation errors arrive as an array of field objects.
    if (Array.isArray(detail) && detail.length) {
      return detail
        .map((d: any) => `${(d.loc || []).slice(1).join('.')}: ${d.msg}`)
        .join('; ');
    }
    return response.statusText || `Request failed (${response.status})`;
  } catch {
    return response.statusText || `Request failed (${response.status})`;
  }
};

// ─── Core request ───────────────────────────────────────────────────────────

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  body?: unknown;
  params?: Record<string, string | number | boolean | undefined | null>;
  formData?: FormData;
  /** Skip the Authorization header — used by login and refresh. */
  anonymous?: boolean;
}

const buildUrl = (path: string, params?: RequestOptions['params']): string => {
  const url = new URL(`${BASE_URL}${path}`);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
};

const attemptRefresh = async (): Promise<boolean> => {
  if (!refreshToken) return false;
  try {
    const response = await fetch(buildUrl('/auth/refresh'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refreshToken }),
    });
    if (!response.ok) return false;
    const data = await response.json();
    setTokens(data.accessToken, data.refreshToken);
    return true;
  } catch {
    return false;
  }
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, params, formData, anonymous } = options;

  const send = async (): Promise<Response> => {
    const headers: Record<string, string> = {};
    if (!anonymous && accessToken) headers.Authorization = `Bearer ${accessToken}`;
    if (body !== undefined) headers['Content-Type'] = 'application/json';

    return fetch(buildUrl(path, params), {
      method,
      headers,
      body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
    });
  };

  let response: Response;
  try {
    response = await send();
  } catch {
    throw new ApiError(
      0,
      'Cannot reach the server. Is the backend running on port 8000?',
    );
  }

  // One transparent retry after refreshing an expired access token.
  if (response.status === 401 && !anonymous && refreshToken) {
    if (await attemptRefresh()) {
      try {
        response = await send();
      } catch {
        throw new ApiError(0, 'Cannot reach the server.');
      }
    } else {
      clearTokens();
      onSessionExpired?.();
      throw new ApiError(401, 'Your session has expired. Please sign in again.');
    }
  }

  if (!response.ok) {
    throw new ApiError(response.status, await messageFrom(response));
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/**
 * Like `request`, but hands back the raw Response instead of parsed JSON —
 * for binary bodies such as an uploaded document. Shares the same token
 * handling and the same one-shot refresh, so a stale token behaves identically
 * whether you are fetching a grievance or a PDF.
 */
async function authorizedFetch(path: string): Promise<Response> {
  const send = () =>
    fetch(buildUrl(path), {
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    });

  let response: Response;
  try {
    response = await send();
  } catch {
    throw new ApiError(0, 'Cannot reach the server.');
  }

  if (response.status === 401 && refreshToken) {
    if (await attemptRefresh()) {
      response = await send();
    } else {
      clearTokens();
      onSessionExpired?.();
      throw new ApiError(401, 'Your session has expired. Please sign in again.');
    }
  }

  if (!response.ok) {
    throw new ApiError(response.status, await messageFrom(response));
  }
  return response;
}

// ─── Types ──────────────────────────────────────────────────────────────────

export type Role = 'admin' | 'officer' | 'citizen';
export type Language = 'en' | 'mr';

export interface TokenPair {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  expiresIn: number;
}

/** One entry in the audit trail. Carries no request body, because none is
 *  stored — the table is kept and read later, which is the last place a
 *  resident's income or a password being set should end up. */
export interface AuditEvent {
  id: string;
  actorId: string | null;
  actorEmail: string | null;
  actorRole: Role | null;
  /** 'read' for a request that named one record, otherwise the HTTP verb. */
  action: string;
  method: string;
  path: string;
  statusCode: number;
  entityType: string | null;
  entityId: string | null;
  villageId: string | null;
  ip: string | null;
  createdAt: string;
}

/** The one and only time a reset code is readable. Only its hash is stored, so
 *  there is no endpoint that can show it again — losing it means issuing
 *  another, which voids this one. */
export interface PasswordResetIssued {
  code: string;
  expiresAt: string;
  userEmail: string;
  userName: string;
}

export interface User {
  id: string;
  email: string;
  fullName: string;
  role: Role;
  citizenId: string | null;
  villageId: string | null;
  isActive: boolean;
  lastLoginAt: string | null;
}

export type RegistrationStatus = 'pending' | 'approved' | 'rejected';

export interface RegistrationCreate {
  fullName: string;
  email: string;
  password: string;
  phone?: string | null;
  claimedWard?: number | null;
  claimedCitizenId?: string | null;
  villageId?: string | null;
  note?: string | null;
}

export interface RegistrationAck {
  status: 'pending';
  message: string;
}

/** A resident the officer could plausibly be looking at, with the reasons why. */
export interface SuggestedMatch {
  citizenId: string;
  name: string;
  nameMr: string;
  age: number;
  ward: number;
  phone: string | null;
  villageId: string | null;
  alreadyHasAccount: boolean;
  reasons: string[];
  confidence: number;
}

export interface RegistrationRequest {
  id: string;
  fullName: string;
  email: string;
  phone: string | null;
  claimedWard: number | null;
  claimedCitizenId: string | null;
  note: string | null;
  villageId: string | null;
  status: RegistrationStatus;
  matchedCitizenId: string | null;
  reviewNote: string | null;
  createdAt: string;
  reviewedAt: string | null;
  suggestedMatches: SuggestedMatch[];
}

export interface PublicVillage {
  id: string;
  name: string;
  nameMr: string;
  lgdCode: number | null;
  blockName: string;
  blockNameMr: string;
  districtName: string;
  districtNameMr: string;
  stateName: string;
  stateNameMr: string;
}

export interface Village {
  id: string;
  name: string;
  nameMr: string;
  lgdCode: number | null;
  censusCode2011: number | null;
  blockId: string;
  blockName: string;
  blockNameMr: string;
  districtName: string;
  districtNameMr: string;
  stateName: string;
  stateNameMr: string;
  latitude: number | null;
  longitude: number | null;
  population2011: number | null;
  households2011: number | null;
  wardCount: number;
  /** 'active' | 'merged_into_municipal_corporation' | 'uncertain' */
  gramPanchayatStatus: string;
  notes: string | null;
}

export interface VillageDetail extends Village {
  registeredCitizens: number;
  openGrievances: number;
  activeProjects: number;
}

export interface VillageSummary {
  id: string;
  name: string;
  nameMr: string;
  lgdCode: number | null;
  population2011: number | null;
  gramPanchayatStatus: string;
  registeredCitizens: number;
  openGrievances: number;
  activeProjects: number;
}

export interface FamilyMember {
  id: string;
  name: string;
  nameMr: string;
  relation: string | null;
  relationMr: string | null;
  age: number;
  isHead: boolean;
}

export interface Citizen {
  id: string;
  name: string;
  nameMr: string;
  age: number;
  gender: 'Male' | 'Female' | 'Other';
  genderMr: string;
  occupation: string;
  occupationMr: string;
  income: number;
  ward: number;
  phone: string | null;
  familyId: string | null;
  relation: string | null;
  relationMr: string | null;
  isHead: boolean;
  familyName: string | null;
  familyNameMr: string | null;
  familyMembers: FamilyMember[];
}

export interface RequiredDocument {
  name: string;
  nameMr: string;
}

export interface Scheme {
  id: string;
  name: string;
  nameMr: string;
  description: string;
  descriptionMr: string;
  benefit: string;
  benefitMr: string;
  criteria: SchemeCriteria;
  requiredDocuments: RequiredDocument[];
  status: 'active' | 'pending' | 'rejected';
  isGovernmentFeed: boolean;
  sourceGov: string | null;
  formUrl: string | null;
  level: 'central' | 'state' | 'district' | 'panchayat';
  category: string | null;
  announcedOn: string | null;
  /** The official page this scheme's rules were taken from. */
  sourceUrl: string | null;
  confidence: 'high' | 'medium' | 'low';
  notes: string | null;
}

/** The rule vocabulary the backend engine understands. Keys are absent when
 *  the scheme does not state that condition — an absent key is not a zero. */
export interface SchemeCriteria {
  min_age?: number;
  max_age?: number;
  min_income?: number;
  max_income?: number;
  gender?: 'Male' | 'Female';
  marital_status_any?: string[];
  ward_in?: number[];
  occupation_any?: string[];
  occupation_none?: string[];
  is_head?: boolean;
  category_any?: string[];
  requires_bpl?: boolean;
  requires_secc_listed?: boolean;
  ration_card_any?: string[];
  min_land_hectares?: number;
  max_land_hectares?: number;
  min_disability_percent?: number;
  any_of?: SchemeCriteria[];
  manual_review?: boolean;
}

export interface DocumentGap {
  name: string;
  nameMr: string;
  fileStatus: string | null;
}

export type EligibilityStatus =
  | 'Eligible'
  | 'Missing Documents'
  | 'Needs Review'
  | 'Ineligible';

/** The order the backend sorts by, and the order the UI groups by. */
export const ELIGIBILITY_ORDER: EligibilityStatus[] = [
  'Eligible',
  'Missing Documents',
  'Needs Review',
  'Ineligible',
];

/** What came back from reading a Government Resolution. */
export interface SchemeReadResult {
  scheme: Scheme;
  /** Conditions in the GR that no automatic rule can express. */
  unmappableConditions: string[];
  /** Criteria the reader proposed that this system does not evaluate. */
  discardedCriteria: string[];
  confidenceNote: string | null;
  needsManualReview: boolean;
}

export interface EligibilityResult {
  citizenId: string;
  citizenName: string;
  citizenNameMr: string;
  ward: number;
  schemeId: string;
  schemeName: string;
  schemeNameMr: string;
  status: EligibilityStatus;
  statusMr: string;
  criteriaPassed: boolean;
  failedCriteria: string[];
  missingDocuments: DocumentGap[];
  unverifiedDocuments: DocumentGap[];
  /** Attributes the resident record does not hold, so a rule could not run. */
  unknownAttributes: string[];
  explanation: string;
  explanationMr: string;
}

export type Priority = 'Low' | 'Medium' | 'High' | 'Critical';
export type GrievanceStatus = 'Pending' | 'In Progress' | 'Resolved';

export interface Grievance {
  id: string;
  title: string;
  titleMr: string;
  description: string;
  descriptionMr: string;
  category: string;
  categoryMr: string;
  priority: Priority;
  priorityMr: string;
  status: GrievanceStatus;
  statusMr: string;
  department: string;
  departmentMr: string;
  ward: number;
  latitude: number | null;
  longitude: number | null;
  citizenId: string | null;
  citizenName: string;
  phone: string | null;
  submittedDate: string;
  resolvedDate: string | null;
  officerNotes: string | null;
  autoClassified: boolean;
}

export interface GrievanceEvent {
  id: string;
  eventType: 'filed' | 'status_changed' | 'priority_changed' | 'note_added';
  fromStatus: string | null;
  toStatus: string | null;
  note: string | null;
  noteMr: string | null;
  actorName: string | null;
  createdAt: string;
}

/** One complaint with its recorded history — what the tracking view reads. */
export interface GrievanceDetail extends Grievance {
  events: GrievanceEvent[];
}

export interface Classification {
  category: string;
  categoryMr: string;
  priority: Priority;
  priorityMr: string;
  department: string;
  departmentMr: string;
  matchedTerms: string[];
}

export interface Project {
  id: string;
  name: string;
  nameMr: string;
  description: string;
  descriptionMr: string;
  progress: number;
  budget: number;
  utilized: number;
  status: 'Ongoing' | 'Completed' | 'Delayed';
  statusMr: string;
  ward: number;
  location: string;
  locationMr: string;
  latitude: number;
  longitude: number;
  startDate: string | null;
  expectedCompletion: string | null;
}

export interface CitizenDocument {
  id: string;
  citizenId: string;
  citizenName: string | null;
  docType: string;
  docTypeMr: string;
  fileName: string;
  status: 'Pending Verification' | 'Verified' | 'Rejected';
  statusMr: string;
  submittedDate: string;
  verifiedAt: string | null;
  rejectionReason: string | null;
  sizeBytes: number | null;
}

export interface ActionItem {
  id: string;
  meetingId: string;
  action: string;
  actionMr: string;
  responsible: string;
  responsibleMr: string;
  deadline: string | null;
  status: 'Pending' | 'In Progress' | 'Completed';
  statusMr: string;
}

export interface SabhaMeeting {
  id: string;
  meetingDate: string;
  title: string;
  titleMr: string;
  summary: string;
  summaryMr: string;
  decisions: string[];
  decisionsMr: string[];
  sourceFileName: string | null;
  extractedBy: string | null;
  actionItems: ActionItem[];
}

export interface Facility {
  id: string;
  name: string;
  nameMr: string;
  facilityType: string;
  latitude: number;
  longitude: number;
  ward: number | null;
  details: string | null;
  detailsMr: string | null;
}

export interface DashboardStats {
  totalCitizens: number;
  totalFamilies: number;
  openGrievances: number;
  criticalGrievances: number;
  resolvedGrievances: number;
  activeProjects: number;
  delayedProjects: number;
  totalBudget: number;
  totalUtilized: number;
  pendingDocuments: number;
  nextMeetingDate: string | null;
}

export interface NamedCount {
  label: string;
  labelMr: string | null;
  value: number;
}

export interface ProjectBudget {
  id: string;
  name: string;
  nameMr: string;
  ward: number;
  status: string;
  progress: number;
  budgetLakh: number;
  utilizedLakh: number;
}

export interface RetrievedSource {
  entityType: string;
  entityId: string;
  title: string;
  score: number | null;
}

export interface AssistantAnswer {
  answer: string;
  sources: RetrievedSource[];
  /** How the answer was produced.
   *  - 'llm'                     a model wrote it from the retrieved records
   *  - 'retrieval_only'          read straight from the records, because no
   *                              model key is configured or the call failed
   *  - 'retrieval_only_personal' read straight from the records on purpose:
   *                              the answer concerns one resident's own file,
   *                              which is never sent to an outside AI service */
  mode: 'llm' | 'retrieval_only' | 'retrieval_only_personal' | 'unavailable';
}

/** What the assistant retrieved, without calling the model. Makes the
 *  retrieval step visible instead of leaving the answer looking like magic. */
export interface AssistantContext {
  topics: string[];
  factCount: number;
  facts: string[];
  sources: { entityType: string; entityId: string; title: string }[];
  aiEnabled: boolean;
}

export interface HealthStatus {
  status: string;
  database: string;
  aiEnabled: boolean;
  version: string;
}

// ─── Endpoints ──────────────────────────────────────────────────────────────

export const api = {
  /** Health lives outside the versioned prefix. */
  health: (): Promise<HealthStatus> =>
    fetch(`${BASE_URL.replace(/\/api\/v1$/, '')}/health`).then((r) => r.json()),

  auth: {
    login: (email: string, password: string): Promise<TokenPair> =>
      request('/auth/login', {
        method: 'POST',
        body: { email, password },
        anonymous: true,
      }),
    me: (): Promise<User> => request('/auth/me'),
    /** Changing a password revokes every token issued before it — including the
     *  one that made this call — so the server hands back a fresh pair. Store
     *  them, or the caller is signed out by their own success. */
    changePassword: (currentPassword: string, newPassword: string): Promise<TokenPair> =>
      request('/auth/change-password', {
        method: 'POST',
        body: { currentPassword, newPassword },
      }),

    /** Officer or admin: issue a one-time reset code for someone who cannot
     *  sign in. The code is in this response and nowhere else readable, so it
     *  has to be written down before the screen is closed. Issuing another
     *  voids this one. */
    issuePasswordReset: (userId: string): Promise<PasswordResetIssued> =>
      request(`/auth/users/${userId}/password-reset`, { method: 'POST' }),

    /** Public: set a new password with a code from the Panchayat office. */
    resetPassword: (email: string, code: string, newPassword: string): Promise<void> =>
      request('/auth/reset-password', {
        method: 'POST',
        body: { email, code, newPassword },
        anonymous: true,
      }),

    /**
     * Apply for a resident account. This never returns a token — an officer
     * has to match the applicant to a record on the village register first.
     */
    register: (body: RegistrationCreate): Promise<RegistrationAck> =>
      request('/auth/register', { method: 'POST', body, anonymous: true }),

    /** Officer only. The pending queue for their own Gram Panchayat. */
    registrations: (statusFilter: RegistrationStatus | 'all' = 'pending'):
      Promise<RegistrationRequest[]> =>
      request('/auth/registrations', { params: { status_filter: statusFilter } }),

    decideRegistration: (
      id: string,
      body: { approve: boolean; citizenId?: string; reviewNote?: string },
    ): Promise<RegistrationRequest> =>
      request(`/auth/registrations/${id}/decision`, { method: 'POST', body }),
  },

  /** The audit trail. Admin only — it records who opened whose file, which is
   *  more revealing than most of what it describes. Written by middleware on
   *  the server; there is no way to add to or delete from it here. */
  audit: {
    events: (filters: {
      entityType?: string;
      entityId?: string;
      actorId?: string;
      action?: string;
      limit?: number;
    } = {}): Promise<AuditEvent[]> => {
      const query = new URLSearchParams(
        Object.entries(filters)
          .filter(([, v]) => v !== undefined && v !== '')
          .map(([k, v]) => [k, String(v)]),
      ).toString();
      return request(`/audit/events${query ? `?${query}` : ''}`);
    },
  },

  villages: {
    list: (onlyActive = false): Promise<Village[]> =>
      request('/villages', { params: { only_active: onlyActive } }),
    /**
     * Names only, no token needed — the sign-up form has to populate its
     * village picker before anyone has a session.
     */
    publicList: (): Promise<PublicVillage[]> =>
      request('/villages/public', { anonymous: true }),
    /** The signed-in user's own Gram Panchayat; null for an admin. */
    current: (): Promise<Village | null> => request('/villages/current'),
    get: (id: string): Promise<VillageDetail> => request(`/villages/${id}`),
  },

  districts: {
    /** Admin only — every village in the block with its headline numbers. */
    summary: (): Promise<VillageSummary[]> => request('/districts/summary'),
  },

  citizens: {
    list: (params?: { search?: string; ward?: number }): Promise<Citizen[]> =>
      request('/citizens', { params }),
    get: (id: string): Promise<Citizen> => request(`/citizens/${id}`),
    create: (data: Partial<Citizen>): Promise<Citizen> =>
      request('/citizens', { method: 'POST', body: data }),
    update: (id: string, data: Partial<Citizen>): Promise<Citizen> =>
      request(`/citizens/${id}`, { method: 'PATCH', body: data }),
    remove: (id: string): Promise<void> =>
      request(`/citizens/${id}`, { method: 'DELETE' }),
    eligibility: (id: string, language: Language = 'en'): Promise<EligibilityResult[]> =>
      request(`/citizens/${id}/eligibility`, { params: { language } }),
  },

  schemes: {
    list: (includeFeed = false): Promise<Scheme[]> =>
      request('/schemes', { params: { include_feed: includeFeed } }),
    feed: (): Promise<Scheme[]> => request('/schemes/feed'),
    create: (data: Partial<Scheme>): Promise<Scheme> =>
      request('/schemes', { method: 'POST', body: data }),
    update: (id: string, data: Partial<Scheme>): Promise<Scheme> =>
      request(`/schemes/${id}`, { method: 'PATCH', body: data }),
    decide: (id: string, approve: boolean): Promise<Scheme> =>
      request(`/schemes/${id}/decision`, { method: 'POST', params: { approve } }),

    /**
     * Read a Government Resolution and propose a scheme from it. Officer only.
     * The proposal is saved as pending — it reaches no citizen and no
     * eligibility result until an officer approves it with decide().
     */
    readDocument: (file: File): Promise<SchemeReadResult> => {
      const form = new FormData();
      form.append('file', file);
      return request('/schemes/read', { method: 'POST', formData: form });
    },
    eligibility: (
      schemeId: string,
      params?: { ward?: number; only?: string; language?: Language },
    ): Promise<EligibilityResult[]> =>
      request(`/schemes/${schemeId}/eligibility`, { params }),
  },

  grievances: {
    list: (params?: {
      status?: string;
      category?: string;
      priority?: string;
      ward?: number;
    }): Promise<Grievance[]> => request('/grievances', { params }),
    get: (id: string): Promise<GrievanceDetail> => request(`/grievances/${id}`),
    create: (data: {
      title: string;
      description: string;
      ward: number;
      titleMr?: string;
      descriptionMr?: string;
      citizenName?: string;
      phone?: string;
      latitude?: number;
      longitude?: number;
      category?: string;
      priority?: Priority;
    }): Promise<Grievance> => request('/grievances', { method: 'POST', body: data }),
    update: (
      id: string,
      data: { status?: GrievanceStatus; priority?: Priority; category?: string; officerNotes?: string },
    ): Promise<Grievance> => request(`/grievances/${id}`, { method: 'PATCH', body: data }),
    classify: (title: string, description: string, ward = 1): Promise<Classification> =>
      request('/grievances/classify', {
        method: 'POST',
        body: { title, description, ward },
      }),
  },

  projects: {
    list: (params?: { ward?: number }): Promise<Project[]> =>
      request('/projects', { params }),
    get: (id: string): Promise<Project> => request(`/projects/${id}`),
    create: (data: Partial<Project>): Promise<Project> =>
      request('/projects', { method: 'POST', body: data }),
    update: (
      id: string,
      data: { progress?: number; utilized?: number; status?: string; description?: string },
    ): Promise<Project> => request(`/projects/${id}`, { method: 'PATCH', body: data }),
    remove: (id: string): Promise<void> =>
      request(`/projects/${id}`, { method: 'DELETE' }),
  },

  documents: {
    list: (params?: { citizenId?: string; status?: string }): Promise<CitizenDocument[]> =>
      request('/documents', {
        params: { citizen_id: params?.citizenId, status_filter: params?.status },
      }),
    upload: (
      citizenId: string,
      docType: string,
      docTypeMr: string,
      file: File,
    ): Promise<CitizenDocument> => {
      const form = new FormData();
      form.append('citizenId', citizenId);
      form.append('docType', docType);
      form.append('docTypeMr', docTypeMr);
      form.append('file', file);
      return request('/documents', { method: 'POST', formData: form });
    },
    /**
     * Fetch the stored file as a blob URL for viewing.
     *
     * A plain <a href> cannot be used: the endpoint needs the Authorization
     * header, and a link carries no headers. The caller must revoke the URL
     * when finished, or the blob is held in memory for the life of the tab.
     */
    fileUrl: async (id: string): Promise<string> => {
      const response = await authorizedFetch(`/documents/${id}/file`);
      return URL.createObjectURL(await response.blob());
    },

    review: (
      id: string,
      status: 'Verified' | 'Rejected',
      rejectionReason?: string,
    ): Promise<CitizenDocument> =>
      request(`/documents/${id}/review`, {
        method: 'POST',
        body: { status, rejectionReason },
      }),
  },

  sabha: {
    meetings: (): Promise<SabhaMeeting[]> => request('/sabha/meetings'),
    meeting: (id: string): Promise<SabhaMeeting> => request(`/sabha/meetings/${id}`),
    processTranscript: (file: File, meetingDate: string): Promise<SabhaMeeting> => {
      const form = new FormData();
      form.append('file', file);
      form.append('meetingDate', meetingDate);
      return request('/sabha/meetings/process', { method: 'POST', formData: form });
    },
    updateActionItem: (
      id: string,
      data: { status?: 'Pending' | 'In Progress' | 'Completed'; responsible?: string },
    ): Promise<ActionItem> =>
      request(`/sabha/action-items/${id}`, { method: 'PATCH', body: data }),

    /** Assign a follow-up task by hand — for commitments the transcript reader
     *  did not pick up. Officer only. */
    createActionItem: (
      meetingId: string,
      data: {
        action: string;
        actionMr?: string;
        responsible: string;
        responsibleMr?: string;
        deadline?: string | null;
      },
    ): Promise<ActionItem> =>
      request(`/sabha/meetings/${meetingId}/action-items`, {
        method: 'POST',
        body: data,
      }),
  },

  analytics: {
    dashboard: (): Promise<DashboardStats> => request('/analytics/dashboard'),
    ageDistribution: (): Promise<NamedCount[]> => request('/analytics/age-distribution'),
    grievancesByDepartment: (): Promise<NamedCount[]> =>
      request('/analytics/grievances-by-department'),
    grievancesByWard: (): Promise<NamedCount[]> => request('/analytics/grievances-by-ward'),
    projectBudgets: (): Promise<ProjectBudget[]> => request('/analytics/project-budgets'),
  },

  assistant: {
    ask: (query: string, language: Language = 'en'): Promise<AssistantAnswer> =>
      request('/assistant/ask', { method: 'POST', body: { query, language } }),
    context: (query: string, language: Language = 'en'): Promise<AssistantContext> =>
      request('/assistant/context', { method: 'POST', body: { query, language } }),
  },

  facilities: {
    list: (facilityType?: string): Promise<Facility[]> =>
      request('/facilities', { params: { facility_type: facilityType } }),
  },
};
