/**
 * Development projects — what was sanctioned, what has been spent, how far
 * along each work is.
 *
 * The old version held the PROJECTS array from mockData in React state, pushed
 * new rows into that same module-level array, and mirrored it to localStorage
 * through savePersistentData. Nothing ever left the browser, so two officers on
 * two laptops kept two different project registers and neither knew. Reads now
 * come from GET /projects and every write goes through the API, which means a
 * rejected save shows up as an error instead of looking like it worked.
 *
 * The registration form used to invent map coordinates by jittering a hardcoded
 * village centre by a random offset, which dropped works onto the GIS map at
 * places that do not exist. The officer now types the site's coordinates; they
 * are pre-filled with the village's own recorded centre point purely as a
 * starting position, and the form says so.
 *
 * Chart colours #2547a8 / #138808 are this project's validated pair for
 * colour-vision deficiency. Sanctioned and spent share a single ₹ lakh axis:
 * they are the same quantity measured twice, and a second axis would let any
 * pair of bars be scaled to look level regardless of the actual shortfall.
 */

import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  MapPin,
  Percent,
  Plus,
  X,
  Loader2,
  Pencil,
  Trash2,
  CalendarDays,
  AlertTriangle,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { api, type Project, type Village } from '../lib/api';
import { useMutation, useQuery } from '../lib/useApi';
import { EmptyState, ErrorNotice } from './schemes/SchemeBits';

// Validated for colour-vision deficiency — see the note at the top of this file.
const SERIES_SANCTIONED = '#2547a8';
const SERIES_SPENT = '#138808';

type StatusFilter = 'All' | Project['status'];

const STATUS_FILTERS: StatusFilter[] = ['All', 'Ongoing', 'Completed', 'Delayed'];

/** Fixed key per status, rather than building one from the status string —
 *  a lowercased server value that stops matching would silently render a key. */
const STATUS_KEY: Record<Project['status'], string> = {
  Ongoing: 'projects_page.ongoing',
  Completed: 'projects_page.completed',
  Delayed: 'projects_page.delayed',
};

const STATUS_CHIP: Record<Project['status'], string> = {
  Completed: 'bg-emerald-50 text-emerald-800 border-emerald-300',
  Delayed: 'bg-rose-50 text-rose-800 border-rose-300',
  Ongoing: 'bg-govblue-50 text-govnavy border-govnavy/25',
};

const STATUS_BAR: Record<Project['status'], string> = {
  Completed: 'bg-emerald-600',
  Delayed: 'bg-rose-600',
  Ongoing: 'bg-govnavy',
};

const lakhs = (rupees: number, isEnglish: boolean) =>
  isEnglish
    ? `₹${(rupees / 100000).toFixed(2)} L`
    : `₹${(rupees / 100000).toFixed(2)} लाख`;

const formatDate = (value: string | null, isEnglish: boolean) => {
  if (!value) return null;
  return new Date(value).toLocaleDateString(isEnglish ? 'en-IN' : 'mr-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
};

/** Marathi text is optional on a record the office typed in English only. */
const pick = (en: string, mr: string | null | undefined, isEnglish: boolean) =>
  isEnglish ? en : mr || en;

interface ProjectEdit {
  progress: number;
  utilized: number;
  status: Project['status'];
  description: string;
}

export const DevelopmentProjects: React.FC = () => {
  const { t, i18n } = useTranslation();
  const isEnglish = i18n.language === 'en';

  const projects = useQuery<Project[]>(() => api.projects.list(), []);

  // Used for the ward list and the starting coordinates on the new-project
  // form. Null for an administrator, who is not attached to one village.
  const village = useQuery<Village | null>(() => api.villages.current(), []);

  const [statusFilter, setStatusFilter] = useState<StatusFilter>('All');
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<ProjectEdit | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  // New-project form fields
  const [name, setName] = useState<string>('');
  const [nameMr, setNameMr] = useState<string>('');
  const [budget, setBudget] = useState<string>('');
  const [ward, setWard] = useState<string>('1');
  const [location, setLocation] = useState<string>('');
  const [locationMr, setLocationMr] = useState<string>('');
  const [description, setDescription] = useState<string>('');
  const [descriptionMr, setDescriptionMr] = useState<string>('');
  const [latitude, setLatitude] = useState<string>('');
  const [longitude, setLongitude] = useState<string>('');
  const [startDate, setStartDate] = useState<string>('');
  const [expectedCompletion, setExpectedCompletion] = useState<string>('');
  const [formError, setFormError] = useState<string | null>(null);

  const rows = useMemo(() => projects.data ?? [], [projects.data]);

  const counts = useMemo(() => {
    const out: Record<StatusFilter, number> = {
      All: rows.length,
      Ongoing: 0,
      Completed: 0,
      Delayed: 0,
    };
    for (const p of rows) out[p.status] += 1;
    return out;
  }, [rows]);

  const filteredProjects = useMemo(
    () => (statusFilter === 'All' ? rows : rows.filter((p) => p.status === statusFilter)),
    [rows, statusFilter],
  );

  // Rupees converted to lakh here, in front of the reader, because the record
  // stores rupees and the axis is labelled in lakh.
  const chartData = useMemo(
    () =>
      filteredProjects.map((p) => ({
        name: pick(p.name, p.nameMr, isEnglish).slice(0, 18),
        fullName: pick(p.name, p.nameMr, isEnglish),
        sanctioned: Number((p.budget / 100000).toFixed(2)),
        spent: Number((p.utilized / 100000).toFixed(2)),
      })),
    [filteredProjects, isEnglish],
  );

  const totals = useMemo(
    () =>
      filteredProjects.reduce(
        (acc, p) => ({ budget: acc.budget + p.budget, utilized: acc.utilized + p.utilized }),
        { budget: 0, utilized: 0 },
      ),
    [filteredProjects],
  );

  const closeEditor = () => {
    setEditingId(null);
    setDraft(null);
  };

  const save = useMutation(
    (id: string, body: { progress: number; utilized: number; status: string; description: string }) =>
      api.projects.update(id, body),
    () => {
      closeEditor();
      // Re-read rather than patching local state, so the card shows what the
      // server stored (including any status it recomputed).
      projects.refetch();
    },
  );

  const remove = useMutation(
    (id: string) => api.projects.remove(id),
    () => {
      setConfirmDeleteId(null);
      projects.refetch();
    },
  );

  const resetForm = () => {
    setName('');
    setNameMr('');
    setBudget('');
    setWard('1');
    setLocation('');
    setLocationMr('');
    setDescription('');
    setDescriptionMr('');
    setLatitude('');
    setLongitude('');
    setStartDate('');
    setExpectedCompletion('');
    setFormError(null);
  };

  const create = useMutation(
    (body: Partial<Project>) => api.projects.create(body),
    () => {
      resetForm();
      setShowModal(false);
      projects.refetch();
    },
  );

  const openModal = () => {
    resetForm();
    // The village's own recorded centre is a real coordinate, offered as a
    // starting point the officer is expected to move to the actual work site.
    if (village.data?.latitude != null && village.data?.longitude != null) {
      setLatitude(String(village.data.latitude));
      setLongitude(String(village.data.longitude));
    }
    create.clearError();
    setShowModal(true);
  };

  const submitNewProject = (e: React.FormEvent) => {
    e.preventDefault();
    const budgetValue = Number(budget);
    const lat = Number(latitude);
    const lng = Number(longitude);

    if (!name.trim() || !location.trim()) {
      setFormError(
        isEnglish
          ? 'Project name and location are required.'
          : 'प्रकल्पाचे नाव व ठिकाण आवश्यक आहे.',
      );
      return;
    }
    if (!Number.isFinite(budgetValue) || budgetValue <= 0) {
      setFormError(
        isEnglish
          ? 'Enter the sanctioned amount in rupees.'
          : 'मंजूर रक्कम रुपयांमध्ये नोंदवा.',
      );
      return;
    }
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
      setFormError(
        isEnglish
          ? 'Enter the site latitude and longitude — the map plots this work at those coordinates.'
          : 'कामाच्या ठिकाणाचे अक्षांश व रेखांश नोंदवा — नकाशावर काम याच ठिकाणी दाखवले जाईल.',
      );
      return;
    }
    setFormError(null);

    // A newly registered work has spent nothing and completed nothing; those
    // two zeroes are the record's true starting state, not a placeholder.
    const body: Partial<Project> = {
      name: name.trim(),
      description: description.trim(),
      progress: 0,
      budget: budgetValue,
      utilized: 0,
      status: 'Ongoing',
      ward: Number(ward),
      location: location.trim(),
      latitude: lat,
      longitude: lng,
    };
    // Marathi fields are sent only when actually written. The old form copied
    // the English text into them, which produced records that claimed to be
    // translated and were not.
    if (nameMr.trim()) body.nameMr = nameMr.trim();
    if (locationMr.trim()) body.locationMr = locationMr.trim();
    if (descriptionMr.trim()) body.descriptionMr = descriptionMr.trim();
    if (startDate) body.startDate = startDate;
    if (expectedCompletion) body.expectedCompletion = expectedCompletion;

    create.run(body);
  };

  const wardOptions = village.data?.wardCount
    ? Array.from({ length: village.data.wardCount }, (_, i) => i + 1)
    : null;

  return (
    <div className="space-y-6">
      {/* Title & action */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-govblue-900 tracking-tight m-0">
            {t('projects_page.title')}
          </h1>
          <p className="text-xs text-slate-500 mt-1 m-0">
            {isEnglish
              ? 'Sanctioned works in this Gram Panchayat, with expenditure and progress as recorded.'
              : 'या ग्रामपंचायतीतील मंजूर कामे, नोंदीप्रमाणे खर्च व प्रगतीसह.'}
          </p>
        </div>
        <button
          onClick={openModal}
          className="px-4 py-2.5 rounded-lg bg-govnavy hover:bg-govblue-700 text-white font-bold text-xs sm:text-sm flex items-center justify-center gap-1.5 shadow-sm transition-colors"
        >
          <Plus size={16} />
          <span>{t('projects_page.add_project')}</span>
        </button>
      </div>

      {projects.error && (
        <ErrorNotice message={projects.error} onRetry={projects.refetch} />
      )}
      {remove.error && <ErrorNotice message={remove.error} />}

      {projects.loading && (
        <div className="flex items-center justify-center gap-2 py-16 text-slate-400">
          <Loader2 size={18} className="animate-spin" />
          <span className="text-xs font-bold uppercase tracking-wider">
            {isEnglish ? 'Loading projects' : 'प्रकल्प लोड होत आहेत'}
          </span>
        </div>
      )}

      {!projects.loading && !projects.error && rows.length === 0 && (
        <EmptyState
          title={
            isEnglish
              ? 'No development projects recorded yet'
              : 'अद्याप कोणतेही विकासकाम नोंदवलेले नाही'
          }
          hint={
            isEnglish
              ? 'Use "Register New Project" above to add the first sanctioned work.'
              : 'पहिले मंजूर काम नोंदवण्यासाठी वरील "नवीन प्रकल्पाची नोंदणी करा" वापरा.'
          }
        />
      )}

      {!projects.loading && rows.length > 0 && (
        <>
          {/* Status filters, counted from the loaded records */}
          <div className="flex flex-wrap items-center gap-1.5 bg-white border border-slate-200 p-2 rounded-lg max-w-max shadow-sm">
            {STATUS_FILTERS.map((status) => (
              <button
                key={status}
                onClick={() => setStatusFilter(status)}
                aria-pressed={statusFilter === status}
                className={`px-3.5 py-1.5 rounded text-xs font-bold transition-colors ${
                  statusFilter === status
                    ? 'bg-govnavy text-white'
                    : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800'
                }`}
              >
                {status === 'All' ? (isEnglish ? 'All' : 'सर्व') : t(STATUS_KEY[status])}
                <span className="ml-1.5 tabular-nums opacity-70">{counts[status]}</span>
              </button>
            ))}
          </div>

          {/* Sanctioned vs spent. One axis, both series in ₹ lakh. */}
          {chartData.length > 0 && (
            <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm space-y-3">
              <div className="border-b border-slate-100 pb-2">
                <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wider m-0">
                  {isEnglish
                    ? 'Sanctioned vs Spent, by Project (₹ lakh)'
                    : 'प्रकल्पनिहाय मंजूर निधी व झालेला खर्च (₹ लाख)'}
                </h2>
                <p className="text-[11px] text-slate-400 mt-1 m-0 tabular-nums">
                  {isEnglish
                    ? `${filteredProjects.length} project(s) shown · ${lakhs(totals.budget, true)} sanctioned · ${lakhs(totals.utilized, true)} spent`
                    : `${filteredProjects.length} प्रकल्प · ${lakhs(totals.budget, false)} मंजूर · ${lakhs(totals.utilized, false)} खर्च`}
                </p>
              </div>
              <div style={{ height: Math.max(240, Math.min(420, chartData.length * 52)) }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={chartData}
                    margin={{ top: 8, right: 8, left: -18, bottom: 0 }}
                    barGap={2}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
                    <XAxis
                      dataKey="name"
                      stroke="#94a3b8"
                      fontSize={10}
                      tickLine={false}
                      axisLine={{ stroke: '#e2e8f0' }}
                    />
                    <YAxis
                      stroke="#94a3b8"
                      fontSize={10}
                      tickLine={false}
                      axisLine={false}
                      unit="L"
                    />
                    <Tooltip
                      cursor={{ fill: 'rgba(37,71,168,0.05)' }}
                      contentStyle={{
                        backgroundColor: '#ffffff',
                        borderColor: '#e2e8f0',
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                      labelFormatter={(_, payload) => payload?.[0]?.payload?.fullName ?? ''}
                      formatter={(value) => `₹${value} ${isEnglish ? 'lakh' : 'लाख'}`}
                    />
                    <Legend
                      wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
                      iconType="circle"
                      iconSize={8}
                    />
                    <Bar
                      name={isEnglish ? 'Sanctioned' : 'मंजूर'}
                      dataKey="sanctioned"
                      fill={SERIES_SANCTIONED}
                      radius={[4, 4, 0, 0]}
                    />
                    <Bar
                      name={isEnglish ? 'Spent' : 'खर्च'}
                      dataKey="spent"
                      fill={SERIES_SPENT}
                      radius={[4, 4, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Project cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {filteredProjects.length === 0 ? (
              <div className="md:col-span-2">
                <EmptyState
                  title={
                    isEnglish
                      ? 'No projects with this status'
                      : 'या स्थितीतील कोणतेही प्रकल्प नाहीत'
                  }
                  hint={
                    isEnglish
                      ? 'Choose "All" to see every recorded work.'
                      : 'सर्व नोंदवलेली कामे पाहण्यासाठी "सर्व" निवडा.'
                  }
                />
              </div>
            ) : (
              filteredProjects.map((p) => {
                const remaining = p.budget - p.utilized;
                const overspent = remaining < 0;
                const editing = editingId === p.id;
                const started = formatDate(p.startDate, isEnglish);
                const due = formatDate(p.expectedCompletion, isEnglish);

                return (
                  <div
                    key={p.id}
                    className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm hover:shadow-md transition-all flex flex-col justify-between space-y-5"
                  >
                    {/* Header */}
                    <div className="space-y-1.5">
                      <div className="flex items-start justify-between gap-4">
                        <h3 className="text-sm font-bold text-govblue-900 tracking-tight leading-snug m-0">
                          {pick(p.name, p.nameMr, isEnglish)}
                        </h3>
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border whitespace-nowrap ${
                            STATUS_CHIP[p.status]
                          }`}
                        >
                          {isEnglish ? p.status : p.statusMr || p.status}
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-2 text-[10px] text-slate-500">
                        <span className="flex items-center gap-1">
                          <MapPin size={11} className="text-slate-400" />
                          <span>{pick(p.location, p.locationMr, isEnglish)}</span>
                        </span>
                        <span>·</span>
                        <span>
                          {isEnglish ? `Ward ${p.ward}` : `वॉर्ड ${p.ward}`}
                        </span>
                        {(started || due) && (
                          <>
                            <span>·</span>
                            <span className="flex items-center gap-1">
                              <CalendarDays size={11} className="text-slate-400" />
                              <span>
                                {started ?? '—'}
                                {due ? ` → ${due}` : ''}
                              </span>
                            </span>
                          </>
                        )}
                      </div>
                    </div>

                    <p className="text-xs text-slate-600 leading-relaxed m-0">
                      {pick(p.description, p.descriptionMr, isEnglish)}
                    </p>

                    {/* Progress */}
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-500 font-bold flex items-center gap-1">
                          <Percent size={12} className="text-govnavy" />
                          <span>{t('projects_page.progress')}</span>
                        </span>
                        <strong className="text-govblue-900 tabular-nums">{p.progress}%</strong>
                      </div>
                      <div
                        className="w-full bg-slate-100 rounded-full h-2 border border-slate-200 overflow-hidden"
                        role="progressbar"
                        aria-valuenow={p.progress}
                        aria-valuemin={0}
                        aria-valuemax={100}
                      >
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${
                            STATUS_BAR[p.status]
                          }`}
                          style={{ width: `${Math.max(0, Math.min(100, p.progress))}%` }}
                        />
                      </div>
                    </div>

                    {/* Money. Rupee figures divided to lakh here; the unit is on
                        every label so the reader is never guessing. */}
                    <div className="pt-4 border-t border-slate-100 grid grid-cols-3 gap-3 text-center">
                      <div className="space-y-0.5">
                        <span className="text-[9px] text-slate-400 uppercase tracking-wider block font-bold">
                          {t('projects_page.budget')}
                        </span>
                        <strong className="text-xs text-slate-700 block tabular-nums">
                          {lakhs(p.budget, isEnglish)}
                        </strong>
                      </div>
                      <div className="space-y-0.5">
                        <span className="text-[9px] text-slate-400 uppercase tracking-wider block font-bold">
                          {t('projects_page.utilized')}
                        </span>
                        <strong className="text-xs text-govgreen block tabular-nums">
                          {lakhs(p.utilized, isEnglish)}
                        </strong>
                      </div>
                      <div className="space-y-0.5">
                        <span className="text-[9px] text-slate-400 uppercase tracking-wider block font-bold">
                          {isEnglish ? 'Remaining' : 'शिल्लक'}
                        </span>
                        <strong
                          className={`text-xs block tabular-nums ${
                            overspent ? 'text-rose-700' : 'text-slate-500'
                          }`}
                        >
                          {lakhs(remaining, isEnglish)}
                        </strong>
                      </div>
                    </div>

                    {overspent && (
                      <p className="text-[11px] text-rose-700 font-semibold m-0 flex items-start gap-1.5">
                        <AlertTriangle size={12} className="mt-0.5 flex-shrink-0" />
                        {isEnglish
                          ? 'Recorded expenditure exceeds the sanctioned amount.'
                          : 'नोंदवलेला खर्च मंजूर रकमेपेक्षा जास्त आहे.'}
                      </p>
                    )}

                    {/* Actions */}
                    {!editing && (
                      <div className="flex items-center gap-2 pt-1">
                        <button
                          onClick={() => {
                            save.clearError();
                            setConfirmDeleteId(null);
                            setEditingId(p.id);
                            setDraft({
                              progress: p.progress,
                              utilized: p.utilized,
                              status: p.status,
                              description: p.description,
                            });
                          }}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-300 hover:bg-slate-50 text-slate-600 text-[11px] font-bold transition-colors"
                        >
                          <Pencil size={12} />
                          {isEnglish ? 'Update progress' : 'प्रगती अद्ययावत करा'}
                        </button>

                        {confirmDeleteId === p.id ? (
                          <span className="flex items-center gap-2">
                            <button
                              onClick={() => remove.run(p.id)}
                              disabled={remove.saving}
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-700 hover:bg-rose-800 disabled:opacity-60 text-white text-[11px] font-bold transition-colors"
                            >
                              {remove.saving && <Loader2 size={11} className="animate-spin" />}
                              {isEnglish ? 'Confirm delete' : 'हटवण्याची खात्री'}
                            </button>
                            <button
                              onClick={() => setConfirmDeleteId(null)}
                              className="text-[11px] font-bold text-slate-500 hover:underline"
                            >
                              {t('grievances_page.cancel')}
                            </button>
                          </span>
                        ) : (
                          <button
                            onClick={() => setConfirmDeleteId(p.id)}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-rose-200 hover:bg-rose-50 text-rose-700 text-[11px] font-bold transition-colors"
                          >
                            <Trash2 size={12} />
                            {isEnglish ? 'Delete' : 'हटवा'}
                          </button>
                        )}
                      </div>
                    )}

                    {/* Inline editor — PATCH /projects/{id} */}
                    {editing && draft && (
                      <form
                        onSubmit={(e) => {
                          e.preventDefault();
                          save.run(p.id, {
                            progress: draft.progress,
                            utilized: draft.utilized,
                            status: draft.status,
                            description: draft.description,
                          });
                        }}
                        className="pt-4 border-t border-slate-100 space-y-3"
                      >
                        {save.error && <ErrorNotice message={save.error} />}

                        <div className="grid grid-cols-2 gap-3">
                          <div className="space-y-1">
                            <label
                              htmlFor={`progress-${p.id}`}
                              className="block text-[11px] font-bold text-slate-600"
                            >
                              {t('projects_page.progress')} (%)
                            </label>
                            <input
                              id={`progress-${p.id}`}
                              type="number"
                              min={0}
                              max={100}
                              value={draft.progress}
                              onChange={(e) =>
                                setDraft({ ...draft, progress: Number(e.target.value) })
                              }
                              className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-govnavy/25"
                            />
                          </div>
                          <div className="space-y-1">
                            <label
                              htmlFor={`utilized-${p.id}`}
                              className="block text-[11px] font-bold text-slate-600"
                            >
                              {t('projects_page.utilized')} (₹)
                            </label>
                            <input
                              id={`utilized-${p.id}`}
                              type="number"
                              min={0}
                              value={draft.utilized}
                              onChange={(e) =>
                                setDraft({ ...draft, utilized: Number(e.target.value) })
                              }
                              className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-govnavy/25"
                            />
                            <p className="text-[10px] text-slate-400 m-0 tabular-nums">
                              = {lakhs(draft.utilized || 0, isEnglish)}
                            </p>
                          </div>
                        </div>

                        <div className="space-y-1">
                          <label
                            htmlFor={`status-${p.id}`}
                            className="block text-[11px] font-bold text-slate-600"
                          >
                            {t('projects_page.status')}
                          </label>
                          <select
                            id={`status-${p.id}`}
                            value={draft.status}
                            onChange={(e) =>
                              setDraft({ ...draft, status: e.target.value as Project['status'] })
                            }
                            className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-govnavy/25"
                          >
                            <option value="Ongoing">{t('projects_page.ongoing')}</option>
                            <option value="Completed">{t('projects_page.completed')}</option>
                            <option value="Delayed">{t('projects_page.delayed')}</option>
                          </select>
                        </div>

                        <div className="space-y-1">
                          <label
                            htmlFor={`desc-${p.id}`}
                            className="block text-[11px] font-bold text-slate-600"
                          >
                            {t('grievances_page.description')}
                          </label>
                          <textarea
                            id={`desc-${p.id}`}
                            rows={3}
                            value={draft.description}
                            onChange={(e) => setDraft({ ...draft, description: e.target.value })}
                            className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-govnavy/25 resize-y"
                          />
                        </div>

                        <div className="flex items-center gap-2">
                          <button
                            type="submit"
                            disabled={save.saving}
                            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-govnavy hover:bg-govblue-700 disabled:opacity-60 text-white text-xs font-bold transition-colors"
                          >
                            {save.saving && <Loader2 size={13} className="animate-spin" />}
                            {isEnglish ? 'Save changes' : 'बदल जतन करा'}
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              closeEditor();
                              save.clearError();
                            }}
                            className="px-4 py-2 rounded-lg border border-slate-300 hover:bg-slate-50 text-slate-600 text-xs font-bold transition-colors"
                          >
                            {t('grievances_page.cancel')}
                          </button>
                        </div>
                      </form>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </>
      )}

      {/* Register project modal — POST /projects */}
      {showModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-start justify-center p-4 overflow-y-auto">
          <div
            role="dialog"
            aria-modal="true"
            aria-label={t('projects_page.add_project')}
            className="w-full max-w-xl my-8 bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-2xl"
          >
            <div className="p-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
              <h2 className="text-xs font-bold tracking-widest m-0 uppercase text-slate-500">
                {t('projects_page.add_project')}
              </h2>
              <button
                onClick={() => setShowModal(false)}
                aria-label={t('grievances_page.cancel')}
                className="p-1 rounded-lg hover:bg-slate-200 text-slate-500 hover:text-slate-800 transition-colors"
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={submitNewProject} className="p-5 space-y-4">
              {create.error && <ErrorNotice message={create.error} />}
              {formError && (
                <div
                  role="alert"
                  className="border border-rose-200 bg-rose-50 rounded-lg p-3 text-xs text-rose-800 font-semibold"
                >
                  {formError}
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label htmlFor="p-name" className="block text-xs font-bold text-slate-600">
                    {isEnglish ? 'Project name (English)' : 'प्रकल्पाचे नाव (इंग्रजी)'}
                  </label>
                  <input
                    id="p-name"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder={
                      isEnglish ? 'e.g. Primary School Library Block' : 'उदा. शाळा वाचनालय इमारत'
                    }
                    className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-govnavy/25"
                  />
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="p-name-mr" className="block text-xs font-bold text-slate-600">
                    {isEnglish ? 'Project name (Marathi)' : 'प्रकल्पाचे नाव (मराठी)'}
                  </label>
                  <input
                    id="p-name-mr"
                    value={nameMr}
                    onChange={(e) => setNameMr(e.target.value)}
                    placeholder={isEnglish ? 'Optional' : 'ऐच्छिक'}
                    className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-govnavy/25"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label htmlFor="p-budget" className="block text-xs font-bold text-slate-600">
                    {isEnglish ? 'Sanctioned amount (₹)' : 'मंजूर रक्कम (₹)'}
                  </label>
                  <input
                    id="p-budget"
                    type="number"
                    min={1}
                    required
                    value={budget}
                    onChange={(e) => setBudget(e.target.value)}
                    placeholder="500000"
                    className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-govnavy/25"
                  />
                  {Number(budget) > 0 && (
                    <p className="text-[10px] text-slate-400 m-0 tabular-nums">
                      = {lakhs(Number(budget), isEnglish)}
                    </p>
                  )}
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="p-ward" className="block text-xs font-bold text-slate-600">
                    {t('grievances_page.ward')}
                  </label>
                  {wardOptions ? (
                    <select
                      id="p-ward"
                      value={ward}
                      onChange={(e) => setWard(e.target.value)}
                      className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-govnavy/25"
                    >
                      {wardOptions.map((n) => (
                        <option key={n} value={String(n)}>
                          {isEnglish ? `Ward ${n}` : `वॉर्ड ${n}`}
                        </option>
                      ))}
                    </select>
                  ) : (
                    // No village on this session (an administrator), so the
                    // ward count is unknown — take a number rather than show a
                    // made-up list of wards.
                    <input
                      id="p-ward"
                      type="number"
                      min={1}
                      value={ward}
                      onChange={(e) => setWard(e.target.value)}
                      className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-govnavy/25"
                    />
                  )}
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label htmlFor="p-location" className="block text-xs font-bold text-slate-600">
                    {isEnglish ? 'Location / address (English)' : 'ठिकाण / पत्ता (इंग्रजी)'}
                  </label>
                  <input
                    id="p-location"
                    required
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    placeholder={isEnglish ? 'e.g. Near ZP School compound' : 'उदा. जि.प. शाळेजवळ'}
                    className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-govnavy/25"
                  />
                </div>
                <div className="space-y-1.5">
                  <label
                    htmlFor="p-location-mr"
                    className="block text-xs font-bold text-slate-600"
                  >
                    {isEnglish ? 'Location / address (Marathi)' : 'ठिकाण / पत्ता (मराठी)'}
                  </label>
                  <input
                    id="p-location-mr"
                    value={locationMr}
                    onChange={(e) => setLocationMr(e.target.value)}
                    placeholder={isEnglish ? 'Optional' : 'ऐच्छिक'}
                    className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-govnavy/25"
                  />
                </div>
              </div>

              {/* Coordinates are typed, not generated. The old form produced a
                  random point near the village centre, which put works on the
                  GIS map at places they are not. */}
              <fieldset className="border border-slate-200 rounded-lg p-3 space-y-2">
                <legend className="px-1 text-[11px] font-bold text-slate-600">
                  {isEnglish ? 'Site coordinates' : 'कामाच्या ठिकाणाचे निर्देशांक'}
                </legend>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label htmlFor="p-lat" className="block text-[11px] font-bold text-slate-600">
                      {isEnglish ? 'Latitude' : 'अक्षांश'}
                    </label>
                    <input
                      id="p-lat"
                      type="number"
                      step="any"
                      required
                      value={latitude}
                      onChange={(e) => setLatitude(e.target.value)}
                      className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-govnavy/25"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label htmlFor="p-lng" className="block text-[11px] font-bold text-slate-600">
                      {isEnglish ? 'Longitude' : 'रेखांश'}
                    </label>
                    <input
                      id="p-lng"
                      type="number"
                      step="any"
                      required
                      value={longitude}
                      onChange={(e) => setLongitude(e.target.value)}
                      className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-govnavy/25"
                    />
                  </div>
                </div>
                <p className="text-[10px] text-slate-500 m-0 leading-relaxed">
                  {village.data?.latitude != null
                    ? isEnglish
                      ? `Pre-filled with the recorded centre of ${village.data.name}. Change it to the actual work site — the GIS map plots this project at exactly these coordinates.`
                      : `${village.data.nameMr} च्या नोंदवलेल्या मध्यबिंदूने भरलेले. प्रत्यक्ष कामाच्या ठिकाणानुसार बदला — जीआयएस नकाशावर प्रकल्प याच निर्देशांकांवर दाखवला जाईल.`
                    : isEnglish
                      ? 'The GIS map plots this project at exactly these coordinates.'
                      : 'जीआयएस नकाशावर प्रकल्प याच निर्देशांकांवर दाखवला जाईल.'}
                </p>
              </fieldset>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label htmlFor="p-start" className="block text-xs font-bold text-slate-600">
                    {isEnglish ? 'Start date' : 'सुरुवात दिनांक'}
                  </label>
                  <input
                    id="p-start"
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-govnavy/25"
                  />
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="p-due" className="block text-xs font-bold text-slate-600">
                    {isEnglish ? 'Expected completion' : 'अपेक्षित पूर्तता'}
                  </label>
                  <input
                    id="p-due"
                    type="date"
                    value={expectedCompletion}
                    onChange={(e) => setExpectedCompletion(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-govnavy/25"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label htmlFor="p-desc" className="block text-xs font-bold text-slate-600">
                    {isEnglish ? 'Description (English)' : 'वर्णन (इंग्रजी)'}
                  </label>
                  <textarea
                    id="p-desc"
                    rows={3}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-govnavy/25 resize-y"
                  />
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="p-desc-mr" className="block text-xs font-bold text-slate-600">
                    {isEnglish ? 'Description (Marathi)' : 'वर्णन (मराठी)'}
                  </label>
                  <textarea
                    id="p-desc-mr"
                    rows={3}
                    value={descriptionMr}
                    onChange={(e) => setDescriptionMr(e.target.value)}
                    placeholder={isEnglish ? 'Optional' : 'ऐच्छिक'}
                    className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-govnavy/25 resize-y"
                  />
                </div>
              </div>

              <div className="pt-3 border-t border-slate-100 flex items-center justify-end gap-2.5">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 rounded-lg border border-slate-300 hover:bg-slate-50 text-slate-600 text-xs font-bold transition-colors"
                >
                  {t('grievances_page.cancel')}
                </button>
                <button
                  type="submit"
                  disabled={create.saving}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-govnavy hover:bg-govblue-700 disabled:opacity-60 text-white text-xs font-bold transition-colors shadow-sm"
                >
                  {create.saving && <Loader2 size={13} className="animate-spin" />}
                  {isEnglish ? 'Create project' : 'प्रकल्प तयार करा'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
