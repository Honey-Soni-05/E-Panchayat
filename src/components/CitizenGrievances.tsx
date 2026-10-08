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
 *
 * Two things were added to that. A complaint asking for something new — twenty
 * streetlights, not a broken one — cannot be closed from a desk, and used to
 * sit at "Being worked on" with nothing behind the words. It now points at the
 * work it became, and the resident can follow that work from here: whether the
 * Panchayat approved it, whether the money has been sanctioned and has arrived,
 * and how much of it has been built. And "Resolved" is no longer the last word.
 * It is the office's claim; the person who raised the complaint is asked
 * whether it is true, and a "no" puts it back in front of the office.
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
  Construction,
  Sparkles,
  MapPin,
  Users,
} from 'lucide-react';

import {
  api,
  type Classification,
  type Grievance,
  type GrievanceDetail,
  type GrievanceEvent,
  type GrievanceStatus,
  type ProjectBrief,
} from '../lib/api';
import { useMutation, useQuery } from '../lib/useApi';
import { EmptyState, ErrorNotice } from './schemes/SchemeBits';
import {
  MoneyStrip,
  StageTrack,
  WorkHistory,
  formatDate as formatWorkDate,
  pick,
  useVocabulary,
} from './works/WorkBits';

const STAGES: GrievanceStatus[] = ['Pending', 'In Progress', 'Resolved'];

const STAGE_LABEL: Record<GrievanceStatus, { en: string; mr: string }> = {
  Pending: { en: 'Received', mr: 'प्राप्त' },
  'In Progress': { en: 'Being worked on', mr: 'काम सुरू' },
  Resolved: { en: 'Resolved', mr: 'निराकरण झाले' },
};

/** Entries that are not a plain change of status say what they are. */
const EVENT_TITLE: Partial<Record<GrievanceEvent['eventType'], { en: string; mr: string }>> = {
  priority_changed: { en: 'Priority raised', mr: 'प्राधान्य वाढवले' },
  linked_to_project: { en: 'Taken up as a development work', mr: 'विकास काम म्हणून हाती घेतले' },
  confirmed: { en: 'Confirmed by you', mr: 'तुम्ही खात्री केली' },
  reopened: { en: 'Reopened by you', mr: 'तुम्ही पुन्हा उघडली' },
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

// ─── The work a complaint became ────────────────────────────────────────────

/**
 * Plain enough to read without knowing how a Panchayat budgets: what stage the
 * work is at, whether the money has been approved and has arrived, how much of
 * it exists, and when it is expected. All of it is public within the village;
 * none of it is about any other resident — they appear only as a number.
 */
const WorkCard: React.FC<{ work: ProjectBrief; isEnglish: boolean }> = ({ work, isEnglish }) => {
  const vocabulary = useVocabulary();
  const others = work.linkedGrievances - 1;

  return (
    <section className="rounded-xl border border-violet-200 bg-violet-50/40 p-4 space-y-3.5">
      <div>
        <h4 className="text-[11px] font-extrabold uppercase tracking-wider text-violet-900 m-0 flex items-center gap-1.5">
          <Construction size={13} />
          {isEnglish ? 'The work your complaint became' : 'तुमच्या तक्रारीतून हाती घेतलेले काम'}
        </h4>
        <p className="text-sm font-bold text-slate-800 m-0 mt-1 leading-snug">
          {pick(work.name, work.nameMr, isEnglish)}
        </p>
        {others > 0 && (
          <p className="text-[11px] text-slate-500 m-0 mt-0.5 flex items-center gap-1">
            <Users size={11} />
            {isEnglish
              ? `${others} other resident(s) asked for the same thing.`
              : `${others} इतर रहिवाशांनीही हीच मागणी केली आहे.`}
          </p>
        )}
      </div>

      {work.stage === 'rejected' ? (
        <div className="rounded-lg border border-slate-300 bg-white p-3 text-xs text-slate-700 leading-relaxed">
          <strong className="block text-slate-800">
            {isEnglish ? 'Not approved by the Panchayat' : 'पंचायतीने मंजूर केले नाही'}
          </strong>
          {work.decisionNote}
          <span className="block text-slate-500 mt-1.5">
            {isEnglish
              ? 'Your complaint itself is still open. The office will say what happens to it next.'
              : 'तुमची तक्रार अद्याप खुली आहे. पुढे काय होईल ते कार्यालय कळवेल.'}
          </span>
        </div>
      ) : work.stage === 'on_hold' ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 font-semibold leading-relaxed">
          {isEnglish
            ? 'The Panchayat has put this work on hold. The reason is in the history below.'
            : 'पंचायतीने हे काम स्थगित केले आहे. कारण खालील इतिहासात आहे.'}
        </div>
      ) : vocabulary ? (
        <StageTrack stages={vocabulary.stages} stageIndex={work.stageIndex} isEnglish={isEnglish} />
      ) : (
        <p className="text-xs font-bold text-slate-700 m-0">
          {pick(work.stageLabel, work.stageLabelMr, isEnglish)}
        </p>
      )}

      {work.stage !== 'rejected' && (
        <div className="rounded-lg bg-white border border-slate-200 p-3 space-y-3">
          <MoneyStrip money={work} isEnglish={isEnglish} />

          {(work.stage === 'in_progress' || work.stage === 'completed') && (
            <div className="space-y-1">
              <div className="flex items-center justify-between text-[11px]">
                <span className="font-bold text-slate-500">
                  {work.unitsPlanned !== null
                    ? isEnglish
                      ? `${work.unitsDone} of ${work.unitsPlanned} ${work.unitLabel ?? 'units'} done`
                      : `${work.unitsPlanned} पैकी ${work.unitsDone} ${work.unitLabelMr ?? work.unitLabel ?? 'घटक'} पूर्ण`
                    : isEnglish
                      ? 'Work done'
                      : 'झालेले काम'}
                </span>
                <strong className="text-slate-800 tabular-nums">{work.physicalPercent}%</strong>
              </div>
              <div
                className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden"
                role="progressbar"
                aria-valuenow={work.physicalPercent}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <div
                  className={`h-full rounded-full ${
                    work.stage === 'completed' ? 'bg-govgreen' : 'bg-govnavy'
                  }`}
                  style={{ width: `${Math.max(0, Math.min(100, work.physicalPercent))}%` }}
                />
              </div>
            </div>
          )}

          {work.expectedCompletion && work.stage !== 'completed' && (
            <p className="text-[11px] text-slate-500 m-0">
              {isEnglish ? 'Expected to be complete by ' : 'अपेक्षित पूर्तता '}
              <strong className="text-slate-700">
                {formatWorkDate(work.expectedCompletion, isEnglish)}
              </strong>
            </p>
          )}
        </div>
      )}

      <div className="space-y-1.5">
        <h5 className="text-[10px] font-bold uppercase tracking-wider text-slate-400 m-0">
          {isEnglish ? 'What has happened to the work' : 'कामाचा आतापर्यंतचा प्रवास'}
        </h5>
        <WorkHistory events={work.history} vocabulary={vocabulary} isEnglish={isEnglish} />
      </div>
    </section>
  );
};

// ─── The resident's answer ──────────────────────────────────────────────────

const FeedbackBox: React.FC<{
  grievance: Grievance;
  isEnglish: boolean;
  onAnswered: () => void;
}> = ({ grievance, isEnglish, onAnswered }) => {
  const [disputing, setDisputing] = useState(false);
  const [note, setNote] = useState('');

  const answer = useMutation(
    (resolved: boolean, text?: string) => api.grievances.feedback(grievance.id, resolved, text),
    onAnswered,
  );

  if (grievance.citizenFeedback === 'confirmed') {
    return (
      <p className="text-xs text-govgreen font-semibold m-0 flex items-center gap-1.5">
        <Check size={13} strokeWidth={3} />
        {isEnglish ? 'You confirmed that this was resolved.' : 'समस्या सुटल्याची तुम्ही खात्री केली.'}
      </p>
    );
  }

  if (grievance.status !== 'Resolved') {
    // Reopened and now back with the office.
    return grievance.citizenFeedback === 'reopened' ? (
      <p className="text-xs text-amber-900 font-semibold bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 m-0 leading-relaxed">
        {isEnglish
          ? 'You told the office this was not resolved. It is back with them.'
          : 'समस्या सुटलेली नाही असे तुम्ही कार्यालयाला कळवले. तक्रार पुन्हा त्यांच्याकडे आहे.'}
        {grievance.feedbackNote ? ` “${grievance.feedbackNote}”` : ''}
      </p>
    ) : null;
  }

  return (
    <div className="rounded-lg border border-govsaffron/40 bg-orange-50/60 p-3 space-y-2.5">
      <div>
        <p className="text-xs font-extrabold text-govblue-900 m-0">
          {isEnglish ? 'The office says this is resolved. Is it?' : 'कार्यालयाच्या मते समस्या सुटली आहे. खरंच सुटली का?'}
        </p>
        <p className="text-[11px] text-slate-600 m-0 mt-0.5 leading-relaxed">
          {isEnglish
            ? 'Only you can answer this. If it is not done, the complaint goes back to the office with your reason.'
            : 'याचे उत्तर फक्त तुम्हीच देऊ शकता. काम झाले नसल्यास, तुमच्या कारणासह तक्रार पुन्हा कार्यालयाकडे जाईल.'}
        </p>
      </div>

      {answer.error && <ErrorNotice message={answer.error} />}

      {!disputing ? (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={answer.saving}
            onClick={() => answer.run(true)}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-govgreen hover:bg-emerald-700 disabled:opacity-60 text-white text-xs font-bold transition-colors"
          >
            {answer.saving ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
            {isEnglish ? 'Yes, it is resolved' : 'होय, समस्या सुटली'}
          </button>
          <button
            type="button"
            disabled={answer.saving}
            onClick={() => setDisputing(true)}
            className="px-4 py-2 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 text-xs font-bold transition-colors"
          >
            {isEnglish ? 'No, it is not' : 'नाही, सुटलेली नाही'}
          </button>
        </div>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            answer.run(false, note.trim());
          }}
          className="space-y-2"
        >
          <label htmlFor={`dispute-${grievance.id}`} className="block text-xs font-bold text-slate-600">
            {isEnglish ? 'What is still wrong?' : 'अजून काय बाकी आहे?'}
          </label>
          <textarea
            id={`dispute-${grievance.id}`}
            required
            rows={2}
            maxLength={1000}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder={
              isEnglish
                ? 'e.g. Only 18 of the 20 lights were installed.'
                : 'उदा. २० पैकी फक्त १८ दिवे बसवले आहेत.'
            }
            className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-govnavy/25 resize-y"
          />
          <div className="flex flex-wrap gap-2">
            <button
              type="submit"
              disabled={answer.saving}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-govnavy hover:bg-govblue-700 disabled:opacity-60 text-white text-xs font-bold transition-colors"
            >
              {answer.saving && <Loader2 size={13} className="animate-spin" />}
              {isEnglish ? 'Send it back to the office' : 'कार्यालयाकडे परत पाठवा'}
            </button>
            <button
              type="button"
              onClick={() => setDisputing(false)}
              className="px-4 py-2 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-600 text-xs font-bold transition-colors"
            >
              {isEnglish ? 'Cancel' : 'रद्द करा'}
            </button>
          </div>
        </form>
      )}
    </div>
  );
};

// ─── One complaint, expandable into its history ─────────────────────────────

const GrievanceCard: React.FC<{
  grievance: Grievance;
  isEnglish: boolean;
  onChanged: () => void;
}> = ({ grievance, isEnglish, onChanged }) => {
  // A complaint that became a work opens by itself: the work is the answer to
  // "what is happening", and it should not be one more click away.
  const [open, setOpen] = useState(Boolean(grievance.projectId));

  const detail = useQuery<GrievanceDetail | null>(
    () => (open ? api.grievances.get(grievance.id) : Promise.resolve(null)),
    [open, grievance.id, grievance.status, grievance.citizenFeedback],
  );

  const eventTitle = (event: GrievanceEvent): string => {
    const named = EVENT_TITLE[event.eventType];
    if (named) return isEnglish ? named.en : named.mr;
    if (event.toStatus) {
      const label = STAGE_LABEL[event.toStatus as GrievanceStatus];
      return label ? (isEnglish ? label.en : label.mr) : event.toStatus;
    }
    return isEnglish ? 'Update' : 'अद्ययावत';
  };

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

        {/* How many neighbours have the same problem — a number, never who. */}
        {(grievance.requestType === 'development' || grievance.similarCount > 0) && (
          <div className="flex flex-wrap items-center gap-1.5">
            {grievance.requestType === 'development' && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide border border-violet-200 bg-violet-50 text-violet-800">
                <Construction size={10} />
                {isEnglish ? 'Request for new work' : 'नवीन कामाची मागणी'}
                {grievance.requestedQuantity ? ` · ${grievance.requestedQuantity}` : ''}
              </span>
            )}
            {grievance.similarCount > 0 && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold border border-slate-200 bg-slate-50 text-slate-600">
                <Users size={10} />
                {isEnglish
                  ? `${grievance.similarCount} other resident(s) have reported this too`
                  : `${grievance.similarCount} इतर रहिवाशांनीही हीच समस्या नोंदवली आहे`}
              </span>
            )}
          </div>
        )}

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

        <FeedbackBox grievance={grievance} isEnglish={isEnglish} onAnswered={onChanged} />

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
        <div className="px-4 pb-4 border-t border-slate-100 pt-3 space-y-4">
          <p className="text-xs text-slate-600 leading-relaxed m-0">
            {isEnglish ? grievance.description : grievance.descriptionMr}
          </p>

          {detail.loading && detail.data === null && (
            <div className="flex items-center gap-2 text-slate-400 py-2">
              <Loader2 size={14} className="animate-spin" />
              <span className="text-xs">{isEnglish ? 'Loading history' : 'इतिहास लोड होत आहे'}</span>
            </div>
          )}

          {detail.error && <ErrorNotice message={detail.error} onRetry={detail.refetch} />}

          {detail.data?.project && <WorkCard work={detail.data.project} isEnglish={isEnglish} />}

          {detail.data && (
            <div className="space-y-1.5">
              {detail.data.project && (
                <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-400 m-0">
                  {isEnglish ? 'What has happened to your complaint' : 'तुमच्या तक्रारीचा प्रवास'}
                </h4>
              )}
              <ol className="space-y-0 m-0 p-0 list-none">
                {detail.data.events.map((event, i, all) => (
                  <li key={event.id} className="flex gap-3">
                    <div className="flex flex-col items-center flex-shrink-0">
                      <span
                        className={`w-2.5 h-2.5 rounded-full mt-1.5 ${
                          event.toStatus === 'Resolved' || event.eventType === 'confirmed'
                            ? 'bg-govgreen'
                            : event.eventType === 'filed'
                              ? 'bg-govnavy'
                              : 'bg-govsaffron'
                        }`}
                      />
                      {i < all.length - 1 && <span className="w-px flex-1 bg-slate-200 my-1" />}
                    </div>
                    <div className="pb-4 min-w-0">
                      <p className="text-xs font-bold text-slate-800 m-0">{eventTitle(event)}</p>
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
            </div>
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
  const classify = async (nextTitle: string, nextDescription: string, nextWard = ward) => {
    if (nextTitle.trim().length < 6) {
      setPreview(null);
      return;
    }
    try {
      setPreview(await api.grievances.classify(nextTitle, nextDescription, nextWard));
    } catch {
      setPreview(null);
    }
  };

  const rows = useMemo(() => grievances.data ?? [], [grievances.data]);
  const counts = useMemo(
    () => ({
      open: rows.filter((g) => g.status !== 'Resolved').length,
      resolved: rows.filter((g) => g.status === 'Resolved').length,
      // Marked resolved by the office and not yet answered by the resident.
      toConfirm: rows.filter((g) => g.status === 'Resolved' && !g.citizenFeedback).length,
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
            {counts.toConfirm > 0 && (
              <strong className="text-govsaffron">
                {isEnglish
                  ? ` · ${counts.toConfirm} waiting for your answer`
                  : ` · ${counts.toConfirm} तुमच्या उत्तराच्या प्रतीक्षेत`}
              </strong>
            )}
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
                  ? 'When did it start? Who is affected? If you are asking for something new, how many?'
                  : 'केव्हापासून? कोणाला त्रास होत आहे? नवीन काही हवे असल्यास, किती?'
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
              onChange={(e) => {
                const next = Number(e.target.value);
                setWard(next);
                // Who else has reported it depends on the ward.
                classify(title, description, next);
              }}
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
              {preview.requestType === 'development' && (
                <p className="text-xs text-violet-900 font-semibold m-0 leading-relaxed">
                  {isEnglish
                    ? `This reads as a request for something new${preview.requestedQuantity ? ` (${preview.requestedQuantity} asked for)` : ''}. That cannot be fixed like a repair: the Panchayat has to approve it and find the money, and you will be able to follow each step here.`
                    : `ही नवीन गोष्टीची मागणी दिसते${preview.requestedQuantity ? ` (${preview.requestedQuantity} मागितले)` : ''}. ती दुरुस्तीसारखी लगेच होत नाही: पंचायतीची मंजुरी व निधी लागतो, आणि प्रत्येक टप्पा तुम्हाला येथे पाहता येईल.`}
                </p>
              )}
              {preview.similarCount > 0 && (
                <p className="text-xs text-slate-700 font-semibold m-0 leading-relaxed">
                  {isEnglish
                    ? `${preview.similarCount} other resident(s) in ward ${ward} have already reported this. File yours too — the more residents report a problem, the higher its priority.`
                    : `वॉर्ड ${ward} मधील ${preview.similarCount} इतर रहिवाशांनी हीच समस्या आधीच नोंदवली आहे. तुम्हीही नोंदवा — जितके जास्त रहिवासी नोंदवतील, तितके प्राधान्य वाढते.`}
                </p>
              )}
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

      {grievances.loading && grievances.data === null && (
        <div className="flex items-center justify-center gap-2 py-16 text-slate-400">
          <Loader2 size={18} className="animate-spin" />
          <span className="text-xs font-bold uppercase tracking-wider">
            {isEnglish ? 'Loading your complaints' : 'तुमच्या तक्रारी लोड होत आहेत'}
          </span>
        </div>
      )}

      {grievances.data !== null && !rows.length && !filing && (
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
          <GrievanceCard
            key={g.id}
            grievance={g}
            isEnglish={isEnglish}
            onChanged={grievances.refetch}
          />
        ))}
      </div>
    </div>
  );
};
