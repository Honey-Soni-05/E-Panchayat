/**
 * The officer's grievance queue.
 *
 * This is the counterpart to CitizenGrievances.tsx: what an officer does here
 * is what a resident reads there. Every status or priority change is recorded
 * server-side as a GrievanceEvent and appears on the resident's own tracking
 * timeline, so the controls say so in as many words rather than looking like a
 * private admin field.
 *
 * What changed from the previous version:
 *  - The list came from the hardcoded GRIEVANCES array and was filtered in the
 *    browser. Status, priority, category and ward are now query parameters on
 *    /grievances, so the officer filters the register rather than a page of it.
 *  - A status change wrote to localStorage through savePersistentData(), which
 *    reported success whether or not anything synced. It is now a PATCH whose
 *    failure is rendered, and whose success is re-read from the server.
 *  - The "AI classification" preview was a keyword ladder written in this file.
 *    It now calls /grievances/classify — the same classifier that will actually
 *    route the complaint, so the preview cannot disagree with the outcome.
 *  - The old form generated coordinates by jittering MAP_CENTER. Made-up
 *    positions put pins on the GIS map that no one had ever surveyed, so the
 *    form no longer sends any.
 *
 * A complaint is now one of two kinds, and the screen treats them differently.
 * A repair is closed from here. A request for something new — twenty
 * streetlights, a drain that does not exist yet — cannot be: it has to become a
 * work, with a decision and a budget behind it. So a complaint shows how many
 * other residents have reported the same problem, and offers to open a work
 * proposal out of all of them at once. Which kind a complaint is, and which
 * complaints are "the same problem", are keyword rules on the server; both are
 * shown as suggestions the officer can overrule.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  Clock,
  Construction,
  Filter,
  Loader2,
  Megaphone,
  Plus,
  Sparkles,
  UserCheck,
  Users,
  X,
} from 'lucide-react';

import {
  api,
  type Classification,
  type DashboardStats,
  type Grievance,
  type GrievanceDetail,
  type GrievanceStatus,
  type Priority,
  type ProjectDetail,
  type RequestType,
  type Village,
} from '../lib/api';
import { useMutation, useQuery } from '../lib/useApi';
import { EmptyState, ErrorNotice } from './schemes/SchemeBits';
import { ProposalForm } from './works/ProposalForm';
import { StageBar, pick, rupees } from './works/WorkBits';

const STATUSES: GrievanceStatus[] = ['Pending', 'In Progress', 'Resolved'];
const PRIORITIES: Priority[] = ['Low', 'Medium', 'High', 'Critical'];

/**
 * What the resident sees for each status. Mirrors the wording in
 * CitizenGrievances.tsx on purpose — an officer setting "In Progress" should be
 * able to read what that will say on the complainant's screen.
 */
const CITIZEN_LABEL: Record<GrievanceStatus, { en: string; mr: string }> = {
  Pending: { en: 'Received', mr: 'प्राप्त' },
  'In Progress': { en: 'Being worked on', mr: 'काम सुरू' },
  Resolved: { en: 'Resolved', mr: 'निराकरण झाले' },
};

const STATUS_STYLE: Record<GrievanceStatus, string> = {
  Pending: 'bg-slate-100 text-slate-600 border-slate-300',
  'In Progress': 'bg-sky-50 text-sky-900 border-sky-300',
  Resolved: 'bg-emerald-50 text-emerald-800 border-emerald-300',
};

const PRIORITY_STYLE: Record<string, string> = {
  Critical: 'bg-rose-50 text-rose-800 border-rose-300',
  High: 'bg-amber-50 text-amber-900 border-amber-300',
  Medium: 'bg-sky-50 text-sky-900 border-sky-300',
  Low: 'bg-slate-100 text-slate-600 border-slate-300',
};

const formatDate = (value: string, isEnglish: boolean) =>
  new Date(value).toLocaleDateString(isEnglish ? 'en-IN' : 'mr-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });

const SELECT_CLASS =
  'w-full px-3 py-2 text-xs font-semibold border border-slate-200 rounded-lg bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-govnavy/25';

const REQUEST_TYPE_LABEL: Record<RequestType, { en: string; mr: string }> = {
  service: { en: 'Repair or service', mr: 'दुरुस्ती / सेवा' },
  development: { en: 'New work', mr: 'नवीन काम' },
};

const CHIP = 'px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide border';

/** "New work · 20" — the kind of request and, where the text gave one, the
 *  number asked for. Shown only for new work: a repair is the ordinary case. */
const RequestChip: React.FC<{ grievance: Grievance; isEnglish: boolean }> = ({
  grievance,
  isEnglish,
}) =>
  grievance.requestType === 'development' ? (
    <span className={`inline-flex items-center gap-1 ${CHIP} border-violet-200 bg-violet-50 text-violet-800`}>
      <Construction size={10} />
      {isEnglish ? 'New work' : 'नवीन काम'}
      {grievance.requestedQuantity ? ` · ${grievance.requestedQuantity}` : ''}
    </span>
  ) : null;

/** People, not complaints: one resident filing twice asked once. */
const residentsBehind = (complaints: Grievance[]): number =>
  new Set(complaints.map((g) => g.citizenId ?? g.id)).size;

// ─── Detail panel: history plus the controls that write to it ───────────────

type GrievanceChanges = {
  status?: GrievanceStatus;
  priority?: Priority;
  officerNotes?: string;
  requestType?: RequestType;
  requestedQuantity?: number | null;
};

const DetailPanel: React.FC<{
  grievanceId: string;
  isEnglish: boolean;
  /** Null for an administrator, who has no village of their own. */
  village: Village | null;
  onClose: () => void;
  onSaved: () => void;
  /** Go to the works register with this work open. */
  onOpenWork?: (projectId: string) => void;
}> = ({ grievanceId, isEnglish, village, onClose, onSaved, onOpenWork }) => {
  const detail = useQuery<GrievanceDetail>(
    () => api.grievances.get(grievanceId),
    [grievanceId],
  );

  const [status, setStatus] = useState<GrievanceStatus | ''>('');
  const [priority, setPriority] = useState<Priority | ''>('');
  const [notes, setNotes] = useState('');
  const [requestType, setRequestType] = useState<RequestType>('service');
  const [quantity, setQuantity] = useState('');

  // Seed the controls from whatever the server last confirmed. This also runs
  // after a successful save, so the form shows what was stored rather than
  // what was typed.
  useEffect(() => {
    if (!detail.data) return;
    setStatus(detail.data.status);
    setPriority(detail.data.priority);
    setNotes(detail.data.officerNotes ?? '');
    setRequestType(detail.data.requestType);
    setQuantity(detail.data.requestedQuantity ? String(detail.data.requestedQuantity) : '');
  }, [detail.data]);

  const record = detail.data;

  // Send only what the officer actually changed — an unchanged field would
  // otherwise be logged as an event on the resident's timeline for nothing.
  const changes = useMemo(() => {
    const next: GrievanceChanges = {};
    if (!record) return next;
    if (status && status !== record.status) next.status = status;
    if (priority && priority !== record.priority) next.priority = priority;
    if (notes !== (record.officerNotes ?? '')) next.officerNotes = notes;
    if (requestType !== record.requestType) next.requestType = requestType;
    const wanted = quantity.trim() === '' ? null : Number(quantity);
    if (wanted !== (record.requestedQuantity ?? null) && (wanted === null || wanted >= 1)) {
      next.requestedQuantity = wanted;
    }
    return next;
  }, [record, status, priority, notes, requestType, quantity]);

  const dirty = Object.keys(changes).length > 0;

  const save = useMutation(
    () => api.grievances.update(grievanceId, changes),
    () => {
      detail.refetch();
      onSaved();
    },
  );

  // ── The same problem, reported by other residents ─────────────────────────
  const open = record ? record.status !== 'Resolved' : false;
  const similar = useQuery<Grievance[]>(
    () => (open ? api.grievances.similar(grievanceId) : Promise.resolve([])),
    [grievanceId, open, record?.projectId, record?.requestType],
  );
  const others = useMemo(() => similar.data ?? [], [similar.data]);

  // Which of the others go into a proposal with this one. All of them that are
  // not already answered by a work, until the officer says otherwise.
  const [excluded, setExcluded] = useState<Set<string>>(new Set());
  const unlinked = useMemo(() => others.filter((g) => !g.projectId), [others]);
  const chosen = useMemo(
    () => unlinked.filter((g) => !excluded.has(g.id)),
    [unlinked, excluded],
  );

  // If a neighbour's complaint about the same thing is already part of a work,
  // the right move is to join it, not to open a second proposal.
  const existingWorkId = record?.projectId ? null : (others.find((g) => g.projectId)?.projectId ?? null);
  const existingWork = useQuery<ProjectDetail | null>(
    () => (existingWorkId ? api.projects.get(existingWorkId) : Promise.resolve(null)),
    [existingWorkId],
  );

  const [proposing, setProposing] = useState(false);

  const join = useMutation(
    (projectId: string) =>
      api.projects.linkGrievances(projectId, [grievanceId, ...chosen.map((g) => g.id)]),
    () => {
      detail.refetch();
      onSaved();
    },
  );

  return (
    <div
      className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-start sm:items-center justify-center p-3 sm:p-6 overflow-y-auto"
      role="dialog"
      aria-modal="true"
      aria-label={isEnglish ? 'Grievance detail' : 'तक्रार तपशील'}
    >
      <div className="w-full max-w-2xl bg-white rounded-2xl border border-slate-200 shadow-xl my-auto">
        <header className="p-4 border-b border-slate-100 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-sm font-extrabold text-govblue-900 m-0 leading-snug">
              {record
                ? isEnglish
                  ? record.title
                  : record.titleMr
                : isEnglish
                  ? 'Loading complaint'
                  : 'तक्रार लोड होत आहे'}
            </h2>
            <p className="text-[11px] text-slate-400 m-0 font-mono mt-0.5">{grievanceId}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={isEnglish ? 'Close' : 'बंद करा'}
            className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors flex-shrink-0"
          >
            <X size={16} />
          </button>
        </header>

        <div className="p-4 space-y-5 max-h-[70vh] overflow-y-auto">
          {detail.loading && !record && (
            <div className="flex items-center gap-2 text-slate-400 py-6">
              <Loader2 size={15} className="animate-spin" />
              <span className="text-xs font-bold uppercase tracking-wider">
                {isEnglish ? 'Loading' : 'लोड होत आहे'}
              </span>
            </div>
          )}

          {detail.error && <ErrorNotice message={detail.error} onRetry={detail.refetch} />}

          {record && (
            <>
              {/* Facts as filed */}
              <div className="space-y-2">
                <div className="flex flex-wrap gap-1.5">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide border ${
                      STATUS_STYLE[record.status]
                    }`}
                  >
                    {isEnglish ? record.status : record.statusMr}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide border ${
                      PRIORITY_STYLE[record.priority] ?? PRIORITY_STYLE.Low
                    }`}
                  >
                    {isEnglish ? record.priority : record.priorityMr}
                  </span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide border border-slate-200 bg-slate-50 text-slate-600">
                    {isEnglish ? record.category : record.categoryMr}
                  </span>
                  <RequestChip grievance={record} isEnglish={isEnglish} />
                  {record.autoClassified && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide border border-govblue-200 bg-govblue-50 text-govnavy">
                      <Sparkles size={10} />
                      {isEnglish ? 'Auto-classified' : 'स्वयं-वर्गीकृत'}
                    </span>
                  )}
                </div>

                <p className="text-xs text-slate-600 leading-relaxed m-0">
                  {isEnglish ? record.description : record.descriptionMr}
                </p>

                <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[11px] m-0">
                  <div>
                    <dt className="text-slate-400 font-bold uppercase tracking-wide text-[9px] m-0">
                      {isEnglish ? 'Complainant' : 'तक्रारदार'}
                    </dt>
                    <dd className="text-slate-700 font-semibold m-0">
                      {record.citizenName}
                      {record.phone ? ` · ${record.phone}` : ''}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-400 font-bold uppercase tracking-wide text-[9px] m-0">
                      {isEnglish ? 'Ward' : 'वॉर्ड'}
                    </dt>
                    <dd className="text-slate-700 font-semibold m-0">{record.ward}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-400 font-bold uppercase tracking-wide text-[9px] m-0">
                      {isEnglish ? 'Routed to' : 'विभाग'}
                    </dt>
                    <dd className="text-slate-700 font-semibold m-0">
                      {isEnglish ? record.department : record.departmentMr}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-400 font-bold uppercase tracking-wide text-[9px] m-0">
                      {isEnglish ? 'Filed' : 'दाखल'}
                    </dt>
                    <dd className="text-slate-700 font-semibold m-0">
                      {formatDate(record.submittedDate, isEnglish)}
                      {record.resolvedDate
                        ? ` · ${isEnglish ? 'closed' : 'बंद'} ${formatDate(record.resolvedDate, isEnglish)}`
                        : ''}
                    </dd>
                  </div>
                </dl>

                {/* What the resident said once it was marked resolved. */}
                {record.citizenFeedback === 'confirmed' && (
                  <p className="text-[11px] text-govgreen font-semibold m-0 flex items-start gap-1.5">
                    <CheckCircle2 size={13} className="mt-0.5 flex-shrink-0" />
                    {isEnglish
                      ? 'The resident has confirmed that this is resolved.'
                      : 'समस्या सुटल्याची रहिवाशाने खात्री केली आहे.'}
                    {record.feedbackNote ? ` “${record.feedbackNote}”` : ''}
                  </p>
                )}
                {record.citizenFeedback === 'reopened' && (
                  <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800 leading-relaxed">
                    <strong className="flex items-center gap-1.5">
                      <AlertTriangle size={13} />
                      {isEnglish
                        ? 'The resident says this is not resolved'
                        : 'रहिवाशाच्या मते समस्या सुटलेली नाही'}
                    </strong>
                    {record.feedbackNote}
                  </div>
                )}
              </div>

              {/* The work this complaint became */}
              {record.project && (
                <section className="rounded-xl border border-violet-200 bg-violet-50/50 p-4 space-y-2.5">
                  <h3 className="text-[11px] font-extrabold uppercase tracking-wider text-violet-900 m-0 flex items-center gap-1.5">
                    <Construction size={13} />
                    {isEnglish ? 'Being answered by a development work' : 'विकास कामाद्वारे उत्तर दिले जात आहे'}
                  </h3>
                  <p className="text-xs font-bold text-slate-800 m-0">
                    {pick(record.project.name, record.project.nameMr, isEnglish)}
                  </p>
                  <StageBar
                    stageIndex={record.project.stageIndex}
                    stageTotal={record.project.stageTotal}
                    label={pick(record.project.stageLabel, record.project.stageLabelMr, isEnglish)}
                    isEnglish={isEnglish}
                  />
                  <p className="text-[11px] text-slate-600 m-0 tabular-nums">
                    {record.project.approved !== null
                      ? isEnglish
                        ? `${rupees(record.project.spent)} spent of ${rupees(record.project.approved)} approved`
                        : `${rupees(record.project.approved)} मंजूर, त्यापैकी ${rupees(record.project.spent)} खर्च`
                      : record.project.estimated !== null
                        ? isEnglish
                          ? `Estimated at ${rupees(record.project.estimated)}`
                          : `अंदाजित खर्च ${rupees(record.project.estimated)}`
                        : isEnglish
                          ? 'No cost estimate recorded yet'
                          : 'अद्याप खर्चाचा अंदाज नोंदवलेला नाही'}
                    {record.project.linkedGrievances > 1 &&
                      (isEnglish
                        ? ` · asked for by ${record.project.linkedGrievances} residents`
                        : ` · ${record.project.linkedGrievances} रहिवाशांची मागणी`)}
                  </p>
                  {onOpenWork && (
                    <button
                      type="button"
                      onClick={() => onOpenWork(record.project!.id)}
                      className="text-xs font-bold text-govnavy hover:underline"
                    >
                      {isEnglish ? 'Open the work →' : 'काम उघडा →'}
                    </button>
                  )}
                </section>
              )}

              {/* Other residents with the same problem, and what to do about it */}
              {open && !record.project && (
                <section className="rounded-xl border border-slate-200 p-4 space-y-3">
                  <div>
                    <h3 className="text-[11px] font-extrabold uppercase tracking-wider text-slate-600 m-0 flex items-center gap-1.5">
                      <Users size={13} />
                      {others.length > 0
                        ? isEnglish
                          ? `${residentsBehind(others)} other resident(s) report the same problem`
                          : `${residentsBehind(others)} इतर रहिवाशांनी हीच समस्या नोंदवली आहे`
                        : isEnglish
                          ? 'No other resident has reported this'
                          : 'इतर कोणत्याही रहिवाशाने ही समस्या नोंदवलेली नाही'}
                    </h3>
                    <p className="text-[11px] text-slate-500 leading-relaxed mt-1 m-0">
                      {isEnglish
                        ? 'Matched by rule: same ward, same category, same kind of request, and a keyword in common. Untick any that are not the same thing.'
                        : 'नियमानुसार जुळवलेले: तोच वॉर्ड, तोच वर्ग, तोच मागणी प्रकार आणि एक समान शब्द. वेगळ्या असलेल्या तक्रारींची खूण काढा.'}
                    </p>
                  </div>

                  {similar.error && <ErrorNotice message={similar.error} onRetry={similar.refetch} />}

                  {others.length > 0 && (
                    <ul className="divide-y divide-slate-100 border border-slate-200 rounded-lg m-0 p-0 list-none">
                      {others.map((g) => (
                        <li key={g.id} className="p-2.5 flex items-start gap-2.5">
                          <input
                            type="checkbox"
                            className="mt-0.5 accent-govnavy"
                            aria-label={isEnglish ? `Include ${g.title}` : `${g.titleMr} समाविष्ट करा`}
                            checked={!g.projectId && !excluded.has(g.id)}
                            disabled={Boolean(g.projectId)}
                            onChange={(e) => {
                              const next = new Set(excluded);
                              if (e.target.checked) next.delete(g.id);
                              else next.add(g.id);
                              setExcluded(next);
                            }}
                          />
                          <div className="min-w-0">
                            <p className="text-xs font-semibold text-slate-800 m-0 leading-snug">
                              {pick(g.title, g.titleMr, isEnglish)}
                            </p>
                            <p className="text-[11px] text-slate-500 m-0">
                              {g.citizenName} · {formatDate(g.submittedDate, isEnglish)}
                              {g.projectId
                                ? isEnglish
                                  ? ' · already part of a work'
                                  : ' · आधीच एका कामाचा भाग'
                                : ''}
                            </p>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}

                  {join.error && <ErrorNotice message={join.error} />}

                  {existingWork.data ? (
                    <div className="space-y-2">
                      <p className="text-xs text-slate-700 m-0 leading-relaxed">
                        {isEnglish ? 'A work already exists for this problem: ' : 'या समस्येसाठी आधीच एक काम आहे: '}
                        <strong>{pick(existingWork.data.name, existingWork.data.nameMr, isEnglish)}</strong>
                        {' — '}
                        {pick(existingWork.data.stageLabel, existingWork.data.stageLabelMr, isEnglish)}
                      </p>
                      <button
                        type="button"
                        disabled={join.saving}
                        onClick={() => join.run(existingWork.data!.id)}
                        className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-govnavy hover:bg-govblue-700 disabled:opacity-60 text-white text-xs font-bold transition-colors"
                      >
                        {join.saving && <Loader2 size={13} className="animate-spin" />}
                        {chosen.length > 0
                          ? isEnglish
                            ? `Add this and ${chosen.length} other(s) to that work`
                            : `ही व इतर ${chosen.length} तक्रारी त्या कामाशी जोडा`
                          : isEnglish
                            ? 'Add this complaint to that work'
                            : 'ही तक्रार त्या कामाशी जोडा'}
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-1.5">
                      <button
                        type="button"
                        onClick={() => setProposing(true)}
                        className={
                          record.requestType === 'development'
                            ? 'inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-govnavy hover:bg-govblue-700 text-white text-xs font-bold transition-colors'
                            : 'inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border border-slate-300 hover:bg-slate-50 text-slate-700 text-xs font-bold transition-colors'
                        }
                      >
                        <Construction size={13} />
                        {chosen.length > 0
                          ? isEnglish
                            ? `Open a work proposal from these ${chosen.length + 1} complaints`
                            : `या ${chosen.length + 1} तक्रारींमधून काम प्रस्ताव उघडा`
                          : isEnglish
                            ? 'Open a work proposal from this complaint'
                            : 'या तक्रारीमधून काम प्रस्ताव उघडा'}
                      </button>
                      <p className="text-[11px] text-slate-500 m-0 leading-relaxed">
                        {record.requestType === 'development'
                          ? isEnglish
                            ? 'This asks for something that does not exist yet, so it cannot be closed from here. A proposal is where it gets checked, decided and funded.'
                            : 'ही मागणी अद्याप अस्तित्वात नसलेल्या गोष्टीची आहे, त्यामुळे ती येथून बंद करता येणार नाही. प्रस्तावात तिची पडताळणी, निर्णय व निधी होतो.'
                          : isEnglish
                            ? 'Recorded as a repair. If it needs a sanctioned work rather than a repair, open a proposal.'
                            : 'दुरुस्ती म्हणून नोंद. दुरुस्तीऐवजी मंजूर काम आवश्यक असल्यास प्रस्ताव उघडा.'}
                      </p>
                    </div>
                  )}
                </section>
              )}

              {/* Officer controls */}
              <section className="rounded-xl border border-govblue-200 bg-govblue-50/60 p-4 space-y-3">
                <div>
                  <h3 className="text-[11px] font-extrabold uppercase tracking-wider text-govnavy m-0 flex items-center gap-1.5">
                    <UserCheck size={13} />
                    {isEnglish ? 'Update this complaint' : 'ही तक्रार अद्ययावत करा'}
                  </h3>
                  <p className="text-[11px] text-slate-600 leading-relaxed mt-1 m-0">
                    {isEnglish
                      ? 'Saving records an entry in this complaint’s history. The complainant sees it on their own tracking page.'
                      : 'जतन केल्यास या तक्रारीच्या इतिहासात नोंद होते आणि ती तक्रारदाराला त्यांच्या पृष्ठावर दिसते.'}
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <label
                      htmlFor="detail-status"
                      className="block text-[10px] font-bold uppercase tracking-wide text-slate-500"
                    >
                      {isEnglish ? 'Status' : 'स्थिती'}
                    </label>
                    <select
                      id="detail-status"
                      value={status}
                      onChange={(e) => setStatus(e.target.value as GrievanceStatus)}
                      className={SELECT_CLASS}
                    >
                      {STATUSES.map((value) => (
                        <option key={value} value={value}>
                          {isEnglish
                            ? `${value} — resident sees “${CITIZEN_LABEL[value].en}”`
                            : `${value} — नागरिकाला “${CITIZEN_LABEL[value].mr}” दिसेल`}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="space-y-1.5">
                    <label
                      htmlFor="detail-priority"
                      className="block text-[10px] font-bold uppercase tracking-wide text-slate-500"
                    >
                      {isEnglish ? 'Priority' : 'प्राधान्य'}
                    </label>
                    <select
                      id="detail-priority"
                      value={priority}
                      onChange={(e) => setPriority(e.target.value as Priority)}
                      className={SELECT_CLASS}
                    >
                      {PRIORITIES.map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* The rules suggested one; the officer decides. */}
                  <div className="space-y-1.5">
                    <label
                      htmlFor="detail-kind"
                      className="block text-[10px] font-bold uppercase tracking-wide text-slate-500"
                    >
                      {isEnglish ? 'Kind of request' : 'मागणीचा प्रकार'}
                    </label>
                    <select
                      id="detail-kind"
                      value={requestType}
                      onChange={(e) => setRequestType(e.target.value as RequestType)}
                      className={SELECT_CLASS}
                    >
                      {(Object.keys(REQUEST_TYPE_LABEL) as RequestType[]).map((value) => (
                        <option key={value} value={value}>
                          {isEnglish ? REQUEST_TYPE_LABEL[value].en : REQUEST_TYPE_LABEL[value].mr}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="space-y-1.5">
                    <label
                      htmlFor="detail-quantity"
                      className="block text-[10px] font-bold uppercase tracking-wide text-slate-500"
                    >
                      {isEnglish ? 'Number asked for' : 'मागितलेली संख्या'}
                    </label>
                    <input
                      id="detail-quantity"
                      type="number"
                      min={1}
                      value={quantity}
                      onChange={(e) => setQuantity(e.target.value)}
                      placeholder={isEnglish ? 'None given' : 'दिलेली नाही'}
                      className={SELECT_CLASS}
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label
                    htmlFor="detail-notes"
                    className="block text-[10px] font-bold uppercase tracking-wide text-slate-500"
                  >
                    {isEnglish ? 'Officer notes' : 'अधिकारी टिप्पणी'}
                  </label>
                  <textarea
                    id="detail-notes"
                    rows={3}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder={
                      isEnglish
                        ? 'What was done, or what the complainant should expect next.'
                        : 'काय कार्यवाही झाली, किंवा पुढे काय होणार.'
                    }
                    className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-govnavy/25 resize-y"
                  />
                </div>

                {/* Say what this save will do before it happens. */}
                {dirty && (
                  <p className="text-[11px] text-govnavy font-semibold m-0 flex items-start gap-1.5 leading-relaxed">
                    <ChevronRight size={13} className="mt-0.5 flex-shrink-0" />
                    <span>
                      {changes.status
                        ? isEnglish
                          ? `Status will change from “${record.status}” to “${changes.status}”, and the resident's page will show “${CITIZEN_LABEL[changes.status].en}”.`
                          : `स्थिती “${record.status}” वरून “${changes.status}” होईल; नागरिकाला “${CITIZEN_LABEL[changes.status].mr}” दिसेल.`
                        : isEnglish
                          ? 'This will be added to the complaint history.'
                          : 'ही नोंद तक्रारीच्या इतिहासात जोडली जाईल.'}
                    </span>
                  </p>
                )}

                {save.error && <ErrorNotice message={save.error} />}

                <div className="flex flex-wrap gap-2 pt-1">
                  <button
                    type="button"
                    disabled={!dirty || save.saving}
                    onClick={() => save.run()}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-govnavy hover:bg-govblue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-bold transition-colors"
                  >
                    {save.saving ? (
                      <Loader2 size={13} className="animate-spin" />
                    ) : (
                      <Check size={13} />
                    )}
                    {isEnglish ? 'Save and record it' : 'जतन करा व नोंद घ्या'}
                  </button>
                  <button
                    type="button"
                    onClick={onClose}
                    className="px-4 py-2 rounded-lg border border-slate-300 hover:bg-slate-50 text-slate-600 text-xs font-bold transition-colors"
                  >
                    {isEnglish ? 'Close' : 'बंद करा'}
                  </button>
                </div>
              </section>

              {/* Recorded history — the same events the resident reads. */}
              <section className="space-y-2">
                <h3 className="text-[10px] font-bold uppercase tracking-wider text-slate-400 m-0">
                  {isEnglish ? 'History on record' : 'नोंदवलेला इतिहास'}
                </h3>
                {record.events.length === 0 ? (
                  <p className="text-xs text-slate-400 m-0">
                    {isEnglish
                      ? 'Nothing recorded yet beyond the filing.'
                      : 'दाखल केल्यानंतर अद्याप कोणतीही नोंद नाही.'}
                  </p>
                ) : (
                  <ol className="space-y-0 m-0 p-0 list-none">
                    {record.events.map((event, i, all) => (
                      <li key={event.id} className="flex gap-3">
                        <div className="flex flex-col items-center flex-shrink-0">
                          <span
                            className={`w-2.5 h-2.5 rounded-full mt-1.5 ${
                              event.toStatus === 'Resolved'
                                ? 'bg-govgreen'
                                : event.eventType === 'filed'
                                  ? 'bg-govnavy'
                                  : 'bg-govsaffron'
                            }`}
                          />
                          {i < all.length - 1 && (
                            <span className="w-px flex-1 bg-slate-200 my-1" />
                          )}
                        </div>
                        <div className="pb-4 min-w-0">
                          <p className="text-xs font-bold text-slate-800 m-0">
                            {event.toStatus
                              ? isEnglish
                                ? (CITIZEN_LABEL[event.toStatus as GrievanceStatus]?.en ??
                                  event.toStatus)
                                : (CITIZEN_LABEL[event.toStatus as GrievanceStatus]?.mr ??
                                  event.toStatus)
                              : isEnglish
                                ? 'Update'
                                : 'अद्ययावत'}
                          </p>
                          <p className="text-[11px] text-slate-400 m-0">
                            {formatDate(event.createdAt, isEnglish)}
                            {event.actorName && ` · ${event.actorName}`}
                          </p>
                          {(isEnglish ? event.note : event.noteMr || event.note) && (
                            <p className="text-xs text-slate-600 mt-1 m-0 leading-relaxed">
                              {isEnglish ? event.note : event.noteMr || event.note}
                            </p>
                          )}
                        </div>
                      </li>
                    ))}
                  </ol>
                )}
              </section>
            </>
          )}
        </div>
      </div>

      {proposing && record && (
        <ProposalForm
          isEnglish={isEnglish}
          village={village}
          seed={{
            name: record.title,
            description: record.description,
            ward: record.ward,
            category: record.category,
            unitsPlanned: record.requestedQuantity,
            grievances: [record, ...chosen],
          }}
          onClose={() => setProposing(false)}
          onCreated={() => {
            setProposing(false);
            detail.refetch();
            onSaved();
          }}
        />
      )}
    </div>
  );
};

// ─── Walk-in filing form ────────────────────────────────────────────────────

const FilingModal: React.FC<{
  isEnglish: boolean;
  wardOptions: number[];
  onClose: () => void;
  onFiled: () => void;
}> = ({ isEnglish, wardOptions, onClose, onFiled }) => {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [ward, setWard] = useState<number>(wardOptions[0] ?? 1);
  const [citizenName, setCitizenName] = useState('');
  const [phone, setPhone] = useState('');
  const [preview, setPreview] = useState<Classification | null>(null);

  const file = useMutation(
    () =>
      api.grievances.create({
        title,
        description,
        ward,
        citizenName: citizenName.trim() || undefined,
        phone: phone.trim() || undefined,
      }),
    () => {
      onFiled();
      onClose();
    },
  );

  // The server's own classifier, so this preview is the routing that will
  // actually be applied rather than a second guess written in the browser.
  const classify = async (nextTitle: string, nextDescription: string) => {
    if (nextTitle.trim().length < 6) {
      setPreview(null);
      return;
    }
    try {
      setPreview(await api.grievances.classify(nextTitle, nextDescription, ward));
    } catch {
      setPreview(null);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-start sm:items-center justify-center p-3 sm:p-6 overflow-y-auto"
      role="dialog"
      aria-modal="true"
      aria-label={isEnglish ? 'Log a complaint' : 'तक्रार नोंदवा'}
    >
      <div className="w-full max-w-lg bg-white rounded-2xl border border-slate-200 shadow-xl my-auto">
        <header className="p-4 border-b border-slate-100 flex items-center justify-between gap-3">
          <h2 className="text-sm font-extrabold text-govblue-900 m-0">
            {isEnglish ? 'Log a walk-in complaint' : 'कार्यालयात आलेली तक्रार नोंदवा'}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={isEnglish ? 'Close' : 'बंद करा'}
            className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors"
          >
            <X size={16} />
          </button>
        </header>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            file.run();
          }}
          className="p-4 space-y-4 max-h-[70vh] overflow-y-auto"
        >
          {file.error && <ErrorNotice message={file.error} />}

          <div className="space-y-1.5">
            <label htmlFor="new-title" className="block text-xs font-bold text-slate-600">
              {isEnglish ? 'What is the problem?' : 'समस्या काय आहे?'}
            </label>
            <input
              id="new-title"
              required
              value={title}
              onChange={(e) => {
                setTitle(e.target.value);
                classify(e.target.value, description);
              }}
              placeholder={
                isEnglish
                  ? 'e.g. Broken water pipe near the ZP school'
                  : 'उदा. जिल्हा परिषद शाळेजवळ पाण्याची पाईप फुटली आहे'
              }
              className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-govnavy/25"
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="new-desc" className="block text-xs font-bold text-slate-600">
              {isEnglish ? 'Details' : 'तपशील'}
            </label>
            <textarea
              id="new-desc"
              required
              rows={3}
              value={description}
              onChange={(e) => {
                setDescription(e.target.value);
                classify(title, e.target.value);
              }}
              className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-govnavy/25 resize-y"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="space-y-1.5">
              <label htmlFor="new-ward" className="block text-xs font-bold text-slate-600">
                {isEnglish ? 'Ward' : 'वॉर्ड'}
              </label>
              <select
                id="new-ward"
                value={ward}
                onChange={(e) => setWard(Number(e.target.value))}
                className={SELECT_CLASS}
              >
                {wardOptions.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="new-name" className="block text-xs font-bold text-slate-600">
                {isEnglish ? 'Complainant' : 'तक्रारदार'}
              </label>
              <input
                id="new-name"
                value={citizenName}
                onChange={(e) => setCitizenName(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-govnavy/25"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="new-phone" className="block text-xs font-bold text-slate-600">
                {isEnglish ? 'Phone' : 'दूरध्वनी'}
              </label>
              <input
                id="new-phone"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-govnavy/25"
              />
            </div>
          </div>

          {preview && (
            <div className="rounded-lg border border-govblue-200 bg-govblue-50 p-3 space-y-1.5">
              <p className="text-[11px] font-bold uppercase tracking-wider text-govnavy m-0 flex items-center gap-1.5">
                <Sparkles size={11} />
                {isEnglish ? 'This will be routed to' : 'ही तक्रार येथे पाठवली जाईल'}
              </p>
              <p className="text-xs text-slate-700 m-0">
                <strong>{isEnglish ? preview.department : preview.departmentMr}</strong>
                {' · '}
                {isEnglish ? preview.category : preview.categoryMr}
                {' · '}
                {isEnglish ? `${preview.priority} priority` : `${preview.priorityMr} प्राधान्य`}
              </p>
              {preview.requestType === 'development' && (
                <p className="text-xs text-violet-900 font-semibold m-0">
                  {isEnglish
                    ? `Reads as a request for new work${preview.requestedQuantity ? ` (${preview.requestedQuantity} asked for)` : ''}, not a repair.`
                    : `ही दुरुस्ती नसून नवीन कामाची मागणी दिसते${preview.requestedQuantity ? ` (${preview.requestedQuantity} मागितले)` : ''}.`}
                </p>
              )}
              {preview.similarCount > 0 && (
                <p className="text-xs text-slate-700 font-semibold m-0">
                  {isEnglish
                    ? `${preview.similarCount} other resident(s) in ward ${ward} have already reported this.`
                    : `वॉर्ड ${ward} मधील ${preview.similarCount} इतर रहिवाशांनी हीच समस्या आधीच नोंदवली आहे.`}
                </p>
              )}
              <p className="text-[11px] text-slate-500 m-0">
                {isEnglish
                  ? 'You can change the category, priority and kind of request after it is filed.'
                  : 'नोंदणीनंतर वर्ग, प्राधान्य व मागणीचा प्रकार बदलता येईल.'}
              </p>
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <button
              type="submit"
              disabled={file.saving}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-govnavy hover:bg-govblue-700 disabled:opacity-60 text-white text-xs font-bold transition-colors"
            >
              {file.saving && <Loader2 size={13} className="animate-spin" />}
              {isEnglish ? 'File complaint' : 'तक्रार नोंदवा'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg border border-slate-300 hover:bg-slate-50 text-slate-600 text-xs font-bold transition-colors"
            >
              {isEnglish ? 'Cancel' : 'रद्द करा'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// ─── The screen ─────────────────────────────────────────────────────────────

interface SummaryBundle {
  stats: DashboardStats;
  village: Village | null;
}

export const GrievanceManagement: React.FC<{
  /** Go to the works register with this work open. */
  onOpenWork?: (projectId: string) => void;
}> = ({ onOpenWork }) => {
  const { t, i18n } = useTranslation();
  const isEnglish = i18n.language === 'en';

  const [status, setStatus] = useState<string>('');
  const [priority, setPriority] = useState<string>('');
  const [category, setCategory] = useState<string>('');
  const [ward, setWard] = useState<string>('');
  const [kind, setKind] = useState<RequestType | ''>('');

  const [openId, setOpenId] = useState<string | null>(null);
  const [filing, setFiling] = useState(false);

  // Headline counts and the ward list are independent of the filters, so they
  // are fetched once rather than re-read every time a filter moves.
  const summary = useQuery<SummaryBundle>(async () => {
    const [stats, village] = await Promise.all([
      api.analytics.dashboard(),
      api.villages.current(),
    ]);
    return { stats, village };
  }, []);

  // Filters are query parameters, not a client-side pass over a full list —
  // the officer is filtering the register, not one page of it.
  const queue = useQuery<Grievance[]>(
    () =>
      api.grievances.list({
        status: status || undefined,
        priority: priority || undefined,
        category: category || undefined,
        ward: ward ? Number(ward) : undefined,
        requestType: kind || undefined,
      }),
    [status, priority, category, ward, kind],
  );

  const rows = useMemo(() => queue.data ?? [], [queue.data]);

  /**
   * There is no endpoint that lists the classifier's category vocabulary, so
   * the options are the categories seen in responses so far. They accumulate:
   * once a category filter narrows the response to one category, the rest must
   * still be selectable.
   */
  const [categoryOptions, setCategoryOptions] = useState<
    { value: string; label: string; labelMr: string }[]
  >([]);

  useEffect(() => {
    if (!rows.length) return;
    setCategoryOptions((previous) => {
      const merged = new Map(previous.map((option) => [option.value, option]));
      let added = false;
      for (const row of rows) {
        if (!merged.has(row.category)) {
          merged.set(row.category, {
            value: row.category,
            label: row.category,
            labelMr: row.categoryMr,
          });
          added = true;
        }
      }
      // Returning `previous` unchanged is what stops this from looping.
      return added
        ? [...merged.values()].sort((a, b) => a.label.localeCompare(b.label))
        : previous;
    });
  }, [rows]);

  // Ward numbers come from the village record. Falling back to the wards
  // present in the queue keeps the filter usable for an admin, whose
  // /villages/current is null.
  const wardOptions = useMemo(() => {
    const count = summary.data?.village?.wardCount ?? 0;
    if (count > 0) return Array.from({ length: count }, (_, i) => i + 1);
    return [...new Set(rows.map((row) => row.ward))].sort((a, b) => a - b);
  }, [summary.data, rows]);

  const stats = summary.data?.stats;

  const tiles = stats
    ? [
        {
          label: isEnglish ? 'Open' : 'प्रलंबित',
          value: stats.openGrievances,
          tone: 'text-govblue-900',
          border: 'border-govblue-600',
        },
        {
          label: isEnglish ? 'Critical' : 'अत्यावश्यक',
          value: stats.criticalGrievances,
          tone: stats.criticalGrievances ? 'text-rose-600' : 'text-slate-400',
          border: stats.criticalGrievances ? 'border-rose-600' : 'border-slate-300',
        },
        {
          label: isEnglish ? 'Resolved' : 'निकाली',
          value: stats.resolvedGrievances,
          tone: 'text-govgreen',
          border: 'border-govgreen',
        },
      ]
    : [];

  const refreshAll = () => {
    queue.refetch();
    summary.refetch();
  };

  // Refetch dims the queue instead of dropping back to the loading block.
  const refreshing = queue.loading && queue.data !== null;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Megaphone size={20} className="text-govnavy" />
            <h1 className="text-xl font-extrabold text-govblue-900 tracking-tight m-0">
              {t('grievances_page.title')}
            </h1>
          </div>
          <p className="text-xs text-slate-500 m-0">
            {isEnglish
              ? 'Every status change you make here is recorded and shown to the complainant on their own tracking page.'
              : 'येथे केलेला प्रत्येक स्थिती बदल नोंदवला जातो आणि तक्रारदाराला त्यांच्या पृष्ठावर दिसतो.'}
          </p>
        </div>

        <button
          type="button"
          onClick={() => setFiling(true)}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-govnavy hover:bg-govblue-700 text-white text-xs font-bold transition-colors shadow-sm"
        >
          <Plus size={14} />
          {t('grievances_page.submit_new')}
        </button>
      </header>

      {summary.error && <ErrorNotice message={summary.error} onRetry={summary.refetch} />}

      {tiles.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          {tiles.map((tile) => (
            <div
              key={tile.label}
              className={`bg-white rounded-xl p-4 border border-slate-200 border-t-4 ${tile.border} shadow-sm`}
            >
              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">
                {tile.label}
              </span>
              <span className={`text-2xl font-extrabold block mt-1 ${tile.tone}`}>
                {tile.value.toLocaleString('en-IN')}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* One filter row, scoping everything below it. */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-3">
        <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2">
          <Filter size={12} />
          {isEnglish ? 'Filter the register' : 'नोंदवही गाळा'}
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <div className="space-y-1">
            <label
              htmlFor="filter-status"
              className="block text-[10px] font-bold uppercase tracking-wide text-slate-500"
            >
              {t('grievances_page.status')}
            </label>
            <select
              id="filter-status"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className={SELECT_CLASS}
            >
              <option value="">{isEnglish ? 'All' : 'सर्व'}</option>
              {STATUSES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <label
              htmlFor="filter-priority"
              className="block text-[10px] font-bold uppercase tracking-wide text-slate-500"
            >
              {t('grievances_page.priority')}
            </label>
            <select
              id="filter-priority"
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              className={SELECT_CLASS}
            >
              <option value="">{isEnglish ? 'All' : 'सर्व'}</option>
              {PRIORITIES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <label
              htmlFor="filter-category"
              className="block text-[10px] font-bold uppercase tracking-wide text-slate-500"
            >
              {t('grievances_page.category')}
            </label>
            <select
              id="filter-category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className={SELECT_CLASS}
            >
              <option value="">{isEnglish ? 'All' : 'सर्व'}</option>
              {categoryOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {isEnglish ? option.label : option.labelMr || option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <label
              htmlFor="filter-ward"
              className="block text-[10px] font-bold uppercase tracking-wide text-slate-500"
            >
              {t('grievances_page.ward')}
            </label>
            <select
              id="filter-ward"
              value={ward}
              onChange={(e) => setWard(e.target.value)}
              className={SELECT_CLASS}
            >
              <option value="">{isEnglish ? 'All' : 'सर्व'}</option>
              {wardOptions.map((value) => (
                <option key={value} value={String(value)}>
                  {value}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <label
              htmlFor="filter-kind"
              className="block text-[10px] font-bold uppercase tracking-wide text-slate-500"
            >
              {isEnglish ? 'Kind' : 'प्रकार'}
            </label>
            <select
              id="filter-kind"
              value={kind}
              onChange={(e) => setKind(e.target.value as RequestType | '')}
              className={SELECT_CLASS}
            >
              <option value="">{isEnglish ? 'All' : 'सर्व'}</option>
              {(Object.keys(REQUEST_TYPE_LABEL) as RequestType[]).map((value) => (
                <option key={value} value={value}>
                  {isEnglish ? REQUEST_TYPE_LABEL[value].en : REQUEST_TYPE_LABEL[value].mr}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {queue.error && <ErrorNotice message={queue.error} onRetry={queue.refetch} />}

      {queue.loading && queue.data === null && (
        <div className="flex items-center justify-center gap-2 py-16 text-slate-400">
          <Loader2 size={18} className="animate-spin" />
          <span className="text-xs font-bold uppercase tracking-wider">
            {isEnglish ? 'Loading the register' : 'नोंदवही लोड होत आहे'}
          </span>
        </div>
      )}

      {queue.data !== null && rows.length === 0 && (
        <EmptyState
          title={
            status || priority || category || ward || kind
              ? isEnglish
                ? 'No complaints match these filters'
                : 'या निकषांशी जुळणारी तक्रार नाही'
              : isEnglish
                ? 'No complaints on the register'
                : 'नोंदवहीत एकही तक्रार नाही'
          }
          hint={
            status || priority || category || ward || kind
              ? isEnglish
                ? 'Widen or clear a filter above.'
                : 'वरील निकष बदला किंवा काढून टाका.'
              : undefined
          }
        />
      )}

      {rows.length > 0 && (
        <div
          className={`grid grid-cols-1 lg:grid-cols-2 gap-4 ${
            refreshing ? 'opacity-60 transition-opacity' : ''
          }`}
        >
          {rows.map((row) => (
            <article
              key={row.id}
              className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 flex flex-col justify-between gap-3"
            >
              <div className="space-y-2">
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-sm font-bold text-govblue-900 m-0 leading-snug">
                    {isEnglish ? row.title : row.titleMr}
                  </h3>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide border whitespace-nowrap flex-shrink-0 ${
                      STATUS_STYLE[row.status]
                    }`}
                  >
                    {isEnglish ? row.status : row.statusMr}
                  </span>
                </div>

                <p className="text-[11px] text-slate-400 m-0 flex flex-wrap items-center gap-x-2">
                  <span className="font-mono">{row.id}</span>
                  <span>·</span>
                  <span>{isEnglish ? `Ward ${row.ward}` : `वॉर्ड ${row.ward}`}</span>
                  <span>·</span>
                  <span>{formatDate(row.submittedDate, isEnglish)}</span>
                  {row.citizenName && (
                    <>
                      <span>·</span>
                      <span>{row.citizenName}</span>
                    </>
                  )}
                </p>

                <p className="text-xs text-slate-600 leading-relaxed m-0 line-clamp-3">
                  {isEnglish ? row.description : row.descriptionMr}
                </p>
              </div>

              <div className="pt-3 border-t border-slate-100 space-y-2.5">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide border border-slate-200 bg-slate-50 text-slate-600">
                    {isEnglish ? row.category : row.categoryMr}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide border ${
                      PRIORITY_STYLE[row.priority] ?? PRIORITY_STYLE.Low
                    }`}
                  >
                    {isEnglish ? row.priority : row.priorityMr}
                  </span>
                  <RequestChip grievance={row} isEnglish={isEnglish} />
                  {row.similarCount > 0 && (
                    <span className={`inline-flex items-center gap-1 ${CHIP} border-slate-200 bg-white text-slate-600`}>
                      <Users size={10} />
                      {isEnglish
                        ? `+${row.similarCount} resident(s)`
                        : `+${row.similarCount} रहिवासी`}
                    </span>
                  )}
                  {row.projectId && (
                    <span className={`${CHIP} border-violet-200 bg-white text-violet-800`}>
                      {isEnglish ? 'Part of a work' : 'कामाचा भाग'}
                    </span>
                  )}
                  {row.citizenFeedback === 'reopened' && (
                    <span className="inline-flex items-center gap-1 text-[10px] font-bold text-rose-600">
                      <AlertTriangle size={11} />
                      {isEnglish ? 'Reopened by the resident' : 'रहिवाशाने पुन्हा उघडली'}
                    </span>
                  )}
                  {row.priority === 'Critical' && row.status !== 'Resolved' && (
                    <span className="inline-flex items-center gap-1 text-[10px] font-bold text-rose-600">
                      <AlertTriangle size={11} />
                      {isEnglish ? 'Needs action' : 'कार्यवाही आवश्यक'}
                    </span>
                  )}
                </div>

                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-[10px] text-slate-400 font-semibold">
                    {isEnglish ? row.department : row.departmentMr}
                  </span>
                  <button
                    type="button"
                    onClick={() => setOpenId(row.id)}
                    className="inline-flex items-center gap-1 text-xs font-bold text-govnavy hover:underline"
                  >
                    {row.status === 'Resolved' ? (
                      <>
                        <CheckCircle2 size={13} />
                        {isEnglish ? 'View history' : 'इतिहास पहा'}
                      </>
                    ) : row.status === 'In Progress' ? (
                      <>
                        <CircleDot size={13} />
                        {isEnglish ? 'Update status' : 'स्थिती बदला'}
                      </>
                    ) : (
                      <>
                        <Clock size={13} />
                        {isEnglish ? 'Review and update' : 'पाहून अद्ययावत करा'}
                      </>
                    )}
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      {openId && (
        <DetailPanel
          grievanceId={openId}
          isEnglish={isEnglish}
          village={summary.data?.village ?? null}
          onClose={() => setOpenId(null)}
          onSaved={refreshAll}
          onOpenWork={onOpenWork}
        />
      )}

      {filing && (
        <FilingModal
          isEnglish={isEnglish}
          wardOptions={wardOptions.length ? wardOptions : [1]}
          onClose={() => setFiling(false)}
          onFiled={refreshAll}
        />
      )}
    </div>
  );
};
