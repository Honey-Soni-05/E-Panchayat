/**
 * File a complaint, and track what happens to it.
 *
 * The tracking half is the point. A resident who walks into a Panchayat office
 * to ask "what happened to my complaint?" normally gets a shrug; here they see
 * the actual history — when it was filed, which department it went to, when an
 * officer picked it up, and what they wrote when they closed it.
 *
 * The timeline is read from recorded events, not reconstructed from the current
 * status, so it cannot claim a step that never happened.
 */

import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Megaphone,
  Loader2,
  Plus,
  Check,
  Clock,
  CircleDot,
  ChevronDown,
  Sparkles,
  MapPin,
} from 'lucide-react';

import {
  api,
  type Classification,
  type Grievance,
  type GrievanceDetail,
  type GrievanceStatus,
} from '../lib/api';
import { useMutation, useQuery } from '../lib/useApi';
import { EmptyState, ErrorNotice } from './schemes/SchemeBits';

const STAGES: GrievanceStatus[] = ['Pending', 'In Progress', 'Resolved'];

const STAGE_LABEL: Record<GrievanceStatus, { en: string; mr: string }> = {
  Pending: { en: 'Received', mr: 'प्राप्त' },
  'In Progress': { en: 'Being worked on', mr: 'काम सुरू' },
  Resolved: { en: 'Resolved', mr: 'निराकरण झाले' },
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

// ─── Progress tracker ───────────────────────────────────────────────────────

const StageTracker: React.FC<{ status: GrievanceStatus; isEnglish: boolean }> = ({
  status,
  isEnglish,
}) => {
  const current = STAGES.indexOf(status);

  return (
    <ol className="flex items-center gap-1" aria-label="Complaint progress">
      {STAGES.map((stage, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <li key={stage} className="flex items-center gap-1 flex-1 last:flex-none">
            <div className="flex flex-col items-center gap-1 min-w-0">
              <span
                className={`w-6 h-6 rounded-full flex items-center justify-center border-2 flex-shrink-0 ${
                  done
                    ? 'bg-govgreen border-govgreen text-white'
                    : active
                      ? 'bg-white border-govsaffron text-govsaffron'
                      : 'bg-white border-slate-200 text-slate-300'
                }`}
              >
                {done ? (
                  <Check size={12} strokeWidth={3} />
                ) : active ? (
                  <CircleDot size={12} strokeWidth={3} />
                ) : (
                  <Clock size={11} />
                )}
              </span>
              <span
                className={`text-[10px] font-bold text-center leading-tight ${
                  done ? 'text-govgreen' : active ? 'text-govsaffron' : 'text-slate-400'
                }`}
              >
                {isEnglish ? STAGE_LABEL[stage].en : STAGE_LABEL[stage].mr}
              </span>
            </div>
            {i < STAGES.length - 1 && (
              <span
                aria-hidden
                className={`h-0.5 flex-1 rounded mb-4 ${
                  done ? 'bg-govgreen' : 'bg-slate-200'
                }`}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
};

// ─── One complaint, expandable into its history ─────────────────────────────

const GrievanceCard: React.FC<{ grievance: Grievance; isEnglish: boolean }> = ({
  grievance,
  isEnglish,
}) => {
  const [open, setOpen] = useState(false);

  const detail = useQuery<GrievanceDetail | null>(
    () => (open ? api.grievances.get(grievance.id) : Promise.resolve(null)),
    [open, grievance.id],
  );

  return (
    <article className="bg-white rounded-xl border border-slate-200">
      <div className="p-4 space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0 space-y-1">
            <h3 className="text-sm font-bold text-govblue-900 m-0 leading-snug">
              {isEnglish ? grievance.title : grievance.titleMr}
            </h3>
            <p className="text-[11px] text-slate-400 m-0 flex items-center gap-2 flex-wrap">
              <span className="font-mono">{grievance.id}</span>
              <span>·</span>
              <span>
                {isEnglish ? 'Filed ' : 'दाखल '}
                {formatDate(grievance.submittedDate, isEnglish)}
              </span>
              <span>·</span>
              <span className="inline-flex items-center gap-0.5">
                <MapPin size={10} />
                {isEnglish ? `Ward ${grievance.ward}` : `वॉर्ड ${grievance.ward}`}
              </span>
            </p>
          </div>
          <span
            className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide border whitespace-nowrap ${
              PRIORITY_STYLE[grievance.priority] ?? PRIORITY_STYLE.Low
            }`}
          >
            {isEnglish ? grievance.priority : grievance.priorityMr}
          </span>
        </div>

        <StageTracker status={grievance.status} isEnglish={isEnglish} />

        <p className="text-xs text-slate-600 m-0 leading-relaxed">
          {isEnglish
            ? `Handled by ${grievance.department}`
            : `${grievance.departmentMr} कडे`}
          {grievance.resolvedDate && (
            <>
              {' · '}
              <span className="text-govgreen font-bold">
                {isEnglish ? 'Closed ' : 'बंद '}
                {formatDate(grievance.resolvedDate, isEnglish)}
              </span>
            </>
          )}
        </p>

        <button
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          className="text-xs font-bold text-govnavy hover:underline flex items-center gap-1"
        >
          {open
            ? isEnglish
              ? 'Hide history'
              : 'इतिहास लपवा'
            : isEnglish
              ? 'See what has happened'
              : 'काय झाले ते पहा'}
          <ChevronDown size={13} className={open ? 'rotate-180' : ''} />
        </button>
      </div>

      {open && (
        <div className="px-4 pb-4 border-t border-slate-100 pt-3 space-y-3">
          <p className="text-xs text-slate-600 leading-relaxed m-0">
            {isEnglish ? grievance.description : grievance.descriptionMr}
          </p>

          {detail.loading && (
            <div className="flex items-center gap-2 text-slate-400 py-2">
              <Loader2 size={14} className="animate-spin" />
              <span className="text-xs">{isEnglish ? 'Loading history' : 'इतिहास लोड होत आहे'}</span>
            </div>
          )}

          {detail.error && <ErrorNotice message={detail.error} onRetry={detail.refetch} />}

          {detail.data && (
            <ol className="space-y-0">
              {detail.data.events.map((event, i, all) => (
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
                    {i < all.length - 1 && <span className="w-px flex-1 bg-slate-200 my-1" />}
                  </div>
                  <div className="pb-4 min-w-0">
                    <p className="text-xs font-bold text-slate-800 m-0">
                      {event.toStatus
                        ? isEnglish
                          ? STAGE_LABEL[event.toStatus as GrievanceStatus]?.en ?? event.toStatus
                          : STAGE_LABEL[event.toStatus as GrievanceStatus]?.mr ?? event.toStatus
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
        </div>
      )}
    </article>
  );
};

// ─── The screen ─────────────────────────────────────────────────────────────

export const CitizenGrievances: React.FC = () => {
  const { i18n } = useTranslation();
  const isEnglish = i18n.language === 'en';

  const [filing, setFiling] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [ward, setWard] = useState(1);
  const [preview, setPreview] = useState<Classification | null>(null);

  const grievances = useQuery<Grievance[]>(() => api.grievances.list(), []);

  const file = useMutation(
    () => api.grievances.create({ title, description, ward }),
    () => {
      setTitle('');
      setDescription('');
      setPreview(null);
      setFiling(false);
      grievances.refetch();
    },
  );

  // Show the citizen where their complaint will be routed before they send it,
  // so the classification is something they can correct rather than a surprise.
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

  const rows = grievances.data ?? [];
  const counts = useMemo(
    () => ({
      open: rows.filter((g) => g.status !== 'Resolved').length,
      resolved: rows.filter((g) => g.status === 'Resolved').length,
    }),
    [rows],
  );

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Megaphone size={20} className="text-govnavy" />
            <h2 className="text-lg font-extrabold text-govblue-900 tracking-tight m-0">
              {isEnglish ? 'My Complaints' : 'माझ्या तक्रारी'}
            </h2>
          </div>
          <p className="text-xs text-slate-500 m-0">
            {isEnglish
              ? `${counts.open} open, ${counts.resolved} resolved`
              : `${counts.open} प्रलंबित, ${counts.resolved} निकाली`}
          </p>
        </div>

        {!filing && (
          <button
            onClick={() => setFiling(true)}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-govnavy hover:bg-govblue-700 text-white text-xs font-bold transition-colors shadow-sm"
          >
            <Plus size={14} />
            {isEnglish ? 'File a complaint' : 'तक्रार नोंदवा'}
          </button>
        )}
      </header>

      {/* Filing form */}
      {filing && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            file.run();
          }}
          className="bg-white rounded-xl border border-slate-200 p-4 space-y-4"
        >
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 m-0">
            {isEnglish ? 'New complaint' : 'नवीन तक्रार'}
          </h3>

          {file.error && <ErrorNotice message={file.error} />}

          <div className="space-y-1.5">
            <label htmlFor="g-title" className="block text-xs font-bold text-slate-600">
              {isEnglish ? 'What is the problem?' : 'समस्या काय आहे?'}
            </label>
            <input
              id="g-title"
              required
              value={title}
              onChange={(e) => {
                setTitle(e.target.value);
                classify(e.target.value, description);
              }}
              placeholder={
                isEnglish
                  ? 'e.g. Street light not working near the school'
                  : 'उदा. शाळेजवळील पथदिवा बंद आहे'
              }
              className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-govnavy/25"
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="g-desc" className="block text-xs font-bold text-slate-600">
              {isEnglish ? 'Tell us more' : 'अधिक माहिती'}
            </label>
            <textarea
              id="g-desc"
              required
              rows={3}
              value={description}
              onChange={(e) => {
                setDescription(e.target.value);
                classify(title, e.target.value);
              }}
              placeholder={
                isEnglish
                  ? 'When did it start? Who is affected?'
                  : 'केव्हापासून? कोणाला त्रास होत आहे?'
              }
              className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-govnavy/25 resize-y"
            />
          </div>

          <div className="space-y-1.5 max-w-[140px]">
            <label htmlFor="g-ward" className="block text-xs font-bold text-slate-600">
              {isEnglish ? 'Ward' : 'वॉर्ड'}
            </label>
            <input
              id="g-ward"
              type="number"
              min={1}
              max={20}
              value={ward}
              onChange={(e) => setWard(Number(e.target.value))}
              className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-govnavy/25"
            />
          </div>

          {preview && (
            <div className="rounded-lg border border-govblue-200 bg-govblue-50 p-3 space-y-1.5">
              <p className="text-[11px] font-bold uppercase tracking-wider text-govnavy m-0 flex items-center gap-1.5">
                <Sparkles size={11} />
                {isEnglish ? 'This will be sent to' : 'ही तक्रार येथे पाठवली जाईल'}
              </p>
              <p className="text-xs text-slate-700 m-0">
                <strong>{isEnglish ? preview.department : preview.departmentMr}</strong>
                {' · '}
                {isEnglish ? preview.category : preview.categoryMr}
                {' · '}
                {isEnglish ? `${preview.priority} priority` : `${preview.priorityMr} प्राधान्य`}
              </p>
              <p className="text-[11px] text-slate-500 m-0">
                {isEnglish
                  ? 'An officer can change this after reviewing your complaint.'
                  : 'तक्रार पाहिल्यानंतर अधिकारी यात बदल करू शकतात.'}
              </p>
            </div>
          )}

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={file.saving}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-govnavy hover:bg-govblue-700 disabled:opacity-60 text-white text-xs font-bold transition-colors"
            >
              {file.saving && <Loader2 size={13} className="animate-spin" />}
              {isEnglish ? 'Submit complaint' : 'तक्रार सादर करा'}
            </button>
            <button
              type="button"
              onClick={() => {
                setFiling(false);
                setPreview(null);
                file.clearError();
              }}
              className="px-4 py-2 rounded-lg border border-slate-300 hover:bg-slate-50 text-slate-600 text-xs font-bold transition-colors"
            >
              {isEnglish ? 'Cancel' : 'रद्द करा'}
            </button>
          </div>
        </form>
      )}

      {grievances.error && <ErrorNotice message={grievances.error} onRetry={grievances.refetch} />}

      {grievances.loading && (
        <div className="flex items-center justify-center gap-2 py-16 text-slate-400">
          <Loader2 size={18} className="animate-spin" />
          <span className="text-xs font-bold uppercase tracking-wider">
            {isEnglish ? 'Loading your complaints' : 'तुमच्या तक्रारी लोड होत आहेत'}
          </span>
        </div>
      )}

      {!grievances.loading && !rows.length && !filing && (
        <EmptyState
          title={isEnglish ? 'You have not filed any complaints' : 'तुम्ही अद्याप तक्रार नोंदवलेली नाही'}
          hint={
            isEnglish
              ? 'Use "File a complaint" above to raise one with the Panchayat.'
              : 'वरील "तक्रार नोंदवा" वापरून ग्रामपंचायतीकडे तक्रार करा.'
          }
        />
      )}

      <div className="space-y-2.5">
        {rows.map((g) => (
          <GrievanceCard key={g.id} grievance={g} isEnglish={isEnglish} />
        ))}
      </div>
    </div>
  );
};
