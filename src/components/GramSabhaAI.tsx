import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Upload,
  Sparkles,
  CheckCircle,
  User,
  Calendar,
  Loader2,
  Plus,
  FileText,
  Info,
} from 'lucide-react';

import { api } from '../lib/api';
import type { ActionItem, SabhaMeeting } from '../lib/api';
import { useQuery, useMutation } from '../lib/useApi';
import { EmptyState, ErrorNotice } from './schemes/SchemeBits';

/**
 * Gram Sabha meetings, their decisions and the follow-up tasks they created.
 *
 * The version this replaces was theatre. Uploading a file ran a 2.5-second
 * setTimeout and then displayed a fixed summary — the same three "decisions",
 * the same ₹50,000, the same two action items — regardless of which file you
 * chose or whether it contained anything at all. It labelled that output
 * "Parsed via GraphRAG" and wrote it to localStorage, where nobody else could
 * ever see it.
 *
 * The real endpoint reads the uploaded file's actual text and asks the model to
 * extract what is in it. That means it can fail: no API key configured, an
 * unreadable file, a transcript the model cannot make sense of. Those failures
 * are shown rather than papered over, because a summary of a meeting that did
 * not happen is worse than no summary.
 */

const STATUS_STYLES: Record<ActionItem['status'], string> = {
  Pending: 'bg-slate-100 text-slate-600 border-slate-200',
  'In Progress': 'bg-govnavy/10 text-govnavy border-govnavy/25',
  Completed: 'bg-emerald-50 text-emerald-700 border-emerald-200',
};

// The officer clicks one button to advance a task, so the order matters.
const NEXT_STATUS: Record<ActionItem['status'], ActionItem['status']> = {
  Pending: 'In Progress',
  'In Progress': 'Completed',
  Completed: 'Pending',
};

const formatDate = (iso: string | null, language: string) =>
  iso
    ? new Date(iso).toLocaleDateString(language === 'mr' ? 'mr-IN' : 'en-IN', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      })
    : '—';

const ActionCard: React.FC<{ item: ActionItem; onChanged: () => void }> = ({
  item,
  onChanged,
}) => {
  const { i18n } = useTranslation();
  const isEnglish = i18n.language === 'en';

  const advance = useMutation(
    (next: ActionItem['status']) => api.sabha.updateActionItem(item.id, { status: next }),
    onChanged,
  );

  return (
    <div className="p-3 rounded-lg bg-white border border-slate-200 space-y-2">
      <strong className="text-xs text-govblue-900 block leading-snug">
        {isEnglish ? item.action : item.actionMr}
      </strong>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-slate-500 font-semibold">
        <span className="inline-flex items-center gap-1">
          <User size={10} />
          {isEnglish ? item.responsible : item.responsibleMr}
        </span>
        <span className="inline-flex items-center gap-1">
          <Calendar size={10} />
          {formatDate(item.deadline, i18n.language)}
        </span>
      </div>

      {advance.error && (
        <p role="alert" className="text-[10px] text-rose-700 font-semibold">
          {advance.error}
        </p>
      )}

      <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
        <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wide">
          {isEnglish ? 'Status' : 'स्थिती'}
        </span>
        <button
          type="button"
          disabled={advance.saving}
          onClick={() => advance.run(NEXT_STATUS[item.status])}
          className={`px-2 py-0.5 rounded border text-[10px] font-bold uppercase tracking-wider transition-all disabled:opacity-50 ${
            STATUS_STYLES[item.status]
          }`}
        >
          {advance.saving ? '…' : isEnglish ? item.status : item.statusMr}
        </button>
      </div>
    </div>
  );
};

const AssignForm: React.FC<{ meetingId: string; onAdded: () => void }> = ({
  meetingId,
  onAdded,
}) => {
  const { i18n } = useTranslation();
  const isEnglish = i18n.language === 'en';

  const [action, setAction] = useState('');
  const [responsible, setResponsible] = useState('');
  const [deadline, setDeadline] = useState('');

  const assign = useMutation(
    () =>
      api.sabha.createActionItem(meetingId, {
        action: action.trim(),
        responsible: responsible.trim(),
        deadline: deadline || null,
      }),
    () => {
      setAction('');
      setResponsible('');
      setDeadline('');
      onAdded();
    },
  );

  const ready = action.trim().length > 1 && responsible.trim().length > 1;
  const field =
    'w-full px-3 py-1.5 rounded border border-slate-200 text-xs text-slate-800 ' +
    'font-medium focus:outline-none focus:ring-2 focus:ring-govnavy/30';

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (ready) assign.run();
      }}
      className="pt-4 border-t border-slate-100 space-y-2.5"
    >
      <h4 className="text-[10px] text-slate-400 font-black uppercase tracking-wide">
        {isEnglish ? 'Assign a follow-up task' : 'पाठपुरावा काम नेमून द्या'}
      </h4>

      <input
        value={action}
        onChange={(e) => setAction(e.target.value)}
        placeholder={isEnglish ? 'What needs doing…' : 'काय करायचे आहे…'}
        className={field}
      />
      <input
        value={responsible}
        onChange={(e) => setResponsible(e.target.value)}
        placeholder={isEnglish ? 'Who is responsible…' : 'जबाबदार व्यक्ती…'}
        className={field}
      />

      {assign.error && (
        <p role="alert" className="text-[10px] text-rose-700 font-semibold">
          {assign.error}
        </p>
      )}

      <div className="grid grid-cols-2 gap-2">
        <input
          type="date"
          value={deadline}
          onChange={(e) => setDeadline(e.target.value)}
          className={field}
        />
        <button
          type="submit"
          disabled={!ready || assign.saving}
          className="bg-govnavy hover:bg-govblue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded text-xs font-bold flex items-center justify-center gap-1 transition-colors"
        >
          {assign.saving ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
          <span>{isEnglish ? 'Assign' : 'नेमा'}</span>
        </button>
      </div>
    </form>
  );
};

const MeetingPanel: React.FC<{ meeting: SabhaMeeting; onChanged: () => void }> = ({
  meeting,
  onChanged,
}) => {
  const { t, i18n } = useTranslation();
  const isEnglish = i18n.language === 'en';
  const decisions = isEnglish ? meeting.decisions : meeting.decisionsMr;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 items-start">
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-5 lg:col-span-2">
        <div className="border-b border-slate-100 pb-4 flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2.5">
          <div className="min-w-0">
            <h3 className="text-sm font-black text-govblue-900 m-0">
              {isEnglish ? meeting.title : meeting.titleMr}
            </h3>
            <span className="text-[10px] text-slate-500 font-semibold">
              {formatDate(meeting.meetingDate, i18n.language)}
              {meeting.sourceFileName ? ` · ${meeting.sourceFileName}` : ''}
            </span>
          </div>

          {/* Says how this record was made. A meeting an officer typed in by
              hand should not wear a badge implying a model extracted it. */}
          {meeting.extractedBy === 'llm' ? (
            <span className="shrink-0 inline-flex items-center gap-1 text-[10px] text-govnavy bg-govnavy/10 border border-govnavy/20 px-2 py-0.5 rounded-full font-bold uppercase tracking-wider">
              <Sparkles size={10} />
              {isEnglish ? 'Extracted from transcript' : 'उतार्‍यातून काढलेले'}
            </span>
          ) : (
            <span className="shrink-0 inline-flex items-center gap-1 text-[10px] text-slate-500 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded-full font-bold uppercase tracking-wider">
              <FileText size={10} />
              {isEnglish ? 'Entered manually' : 'हाताने नोंदवलेले'}
            </span>
          )}
        </div>

        <div className="space-y-2">
          <h4 className="text-[10px] text-slate-400 font-black uppercase tracking-wide">
            {t('sabha_page.summary_title')}
          </h4>
          <p className="text-xs sm:text-sm text-slate-700 leading-relaxed bg-slate-50 p-4 rounded-lg border border-slate-100">
            {(isEnglish ? meeting.summary : meeting.summaryMr) ||
              (isEnglish ? 'No summary recorded.' : 'सारांश नोंदवलेला नाही.')}
          </p>
        </div>

        <div className="space-y-2.5">
          <h4 className="text-[10px] text-slate-400 font-black uppercase tracking-wide">
            {t('sabha_page.decisions_title')}
          </h4>
          {decisions.length === 0 ? (
            <p className="text-xs text-slate-400 font-medium">
              {isEnglish
                ? 'No decisions were recorded for this meeting.'
                : 'या बैठकीचे कोणतेही निर्णय नोंदवलेले नाहीत.'}
            </p>
          ) : (
            <div className="space-y-2">
              {decisions.map((decision, idx) => (
                <div
                  key={idx}
                  className="flex items-start gap-2.5 text-xs text-slate-700 p-3 rounded-lg bg-white border border-slate-200"
                >
                  <CheckCircle size={14} className="text-govgreen mt-0.5 shrink-0" />
                  <span className="leading-relaxed">{decision}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4">
        <h3 className="text-[10px] text-slate-400 font-black uppercase tracking-wide border-b border-slate-100 pb-3">
          {t('sabha_page.actions_title')}
        </h3>

        {meeting.actionItems.length === 0 ? (
          <p className="text-xs text-slate-400 font-medium">
            {isEnglish
              ? 'No follow-up tasks yet.'
              : 'अद्याप कोणतेही पाठपुरावा काम नाही.'}
          </p>
        ) : (
          <div className="space-y-3">
            {meeting.actionItems.map((item) => (
              <ActionCard key={item.id} item={item} onChanged={onChanged} />
            ))}
          </div>
        )}

        <AssignForm meetingId={meeting.id} onAdded={onChanged} />
      </div>
    </div>
  );
};

export const GramSabhaAI: React.FC = () => {
  const { t, i18n } = useTranslation();
  const isEnglish = i18n.language === 'en';

  const { data, loading, error, refetch } = useQuery(() => api.sabha.meetings(), []);
  const meetings = data ?? [];

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [meetingDate, setMeetingDate] = useState(() => new Date().toISOString().slice(0, 10));

  // The server returns newest first, so with nothing chosen the officer lands
  // on the most recent sitting rather than an empty panel.
  const selected = meetings.find((m) => m.id === selectedId) ?? meetings[0] ?? null;

  const upload = useMutation(
    (file: File) => api.sabha.processTranscript(file, meetingDate),
    (created) => {
      setSelectedId(created.id);
      refetch();
    },
  );

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) upload.run(file);
    // Clear the input so choosing the same file twice fires a second time.
    e.target.value = '';
  };

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-black text-govblue-900 tracking-tight m-0">
          {t('sabha_page.title')}
        </h1>
        <p className="text-xs text-slate-500 font-semibold mt-1">
          {isEnglish
            ? 'Upload the minutes of a meeting and the assistant extracts its decisions and follow-up tasks from the file itself.'
            : 'बैठकीचे इतिवृत्त अपलोड करा; सहाय्यक त्या फाइलमधूनच निर्णय आणि पाठपुरावा कामे काढतो.'}
        </p>
      </header>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 flex flex-col items-center text-center space-y-4">
        <div className="w-14 h-14 rounded-full bg-govnavy/10 border border-govnavy/20 flex items-center justify-center text-govnavy">
          <Upload size={24} />
        </div>

        <div className="space-y-1">
          <h2 className="text-sm font-black text-govblue-900">{t('sabha_page.upload_title')}</h2>
          <p className="text-xs text-slate-500 max-w-md leading-relaxed">
            {t('sabha_page.upload_desc')}
          </p>
        </div>

        <div className="flex flex-wrap items-end justify-center gap-3">
          <div className="text-left">
            <label
              htmlFor="sabha-date"
              className="block text-[10px] font-black uppercase tracking-wide text-slate-400 mb-1"
            >
              {isEnglish ? 'Meeting date' : 'बैठकीची तारीख'}
            </label>
            <input
              id="sabha-date"
              type="date"
              value={meetingDate}
              onChange={(e) => setMeetingDate(e.target.value)}
              className="px-3 py-2 rounded border border-slate-200 text-xs text-slate-800 font-medium focus:outline-none focus:ring-2 focus:ring-govnavy/30"
            />
          </div>

          <label
            className={`px-4 py-2 rounded-lg text-xs font-bold transition-colors shadow-sm ${
              upload.saving
                ? 'bg-slate-300 text-slate-600 cursor-not-allowed'
                : 'bg-govnavy hover:bg-govblue-700 text-white cursor-pointer'
            }`}
          >
            <span>{upload.saving ? t('sabha_page.processing') : t('sabha_page.upload_btn')}</span>
            <input
              type="file"
              accept=".txt,.md,.pdf,.docx"
              className="hidden"
              disabled={upload.saving}
              onChange={onFile}
            />
          </label>
        </div>

        {upload.saving && (
          <p className="flex items-center gap-2 text-xs text-govnavy font-bold">
            <Loader2 size={14} className="animate-spin" />
            {isEnglish
              ? 'Reading the file and extracting decisions…'
              : 'फाइल वाचून निर्णय काढले जात आहेत…'}
          </p>
        )}

        {upload.error && (
          <div
            role="alert"
            className="w-full max-w-lg p-3 rounded bg-rose-50 border border-rose-200 text-xs text-rose-700 font-semibold leading-relaxed text-left"
          >
            {upload.error}
          </div>
        )}

        <p className="flex items-start gap-1.5 text-[10px] text-slate-400 max-w-lg leading-relaxed">
          <Info size={12} className="shrink-0 mt-0.5" />
          <span>
            {isEnglish
              ? 'The summary is drawn from the uploaded file only. Read it against the minutes before acting on it.'
              : 'सारांश फक्त अपलोड केलेल्या फाइलमधून तयार होतो. कार्यवाहीपूर्वी तो मूळ इतिवृत्ताशी ताडून पहा.'}
          </span>
        </p>
      </div>

      {error && <ErrorNotice message={error} onRetry={refetch} />}

      {loading ? (
        <p className="flex items-center gap-2 text-xs text-slate-500 font-semibold">
          <Loader2 size={14} className="animate-spin" />
          {isEnglish ? 'Loading meetings…' : 'बैठका उघडत आहेत…'}
        </p>
      ) : meetings.length === 0 ? (
        !error && (
          <EmptyState
            title={
              isEnglish
                ? 'No Gram Sabha meetings recorded yet'
                : 'अद्याप कोणतीही ग्रामसभा नोंदवलेली नाही'
            }
            hint={
              isEnglish
                ? 'Upload a set of minutes above to add the first one.'
                : 'पहिली नोंद करण्यासाठी वरील इतिवृत्त अपलोड करा.'
            }
          />
        )
      ) : (
        <>
          {meetings.length > 1 && (
            <div className="flex flex-wrap gap-2">
              {meetings.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => setSelectedId(m.id)}
                  className={`px-3 py-1.5 rounded-lg border text-xs font-bold transition-all ${
                    selected?.id === m.id
                      ? 'border-govnavy bg-govnavy/5 text-govnavy'
                      : 'border-slate-200 bg-white text-slate-500 hover:text-slate-900'
                  }`}
                >
                  {formatDate(m.meetingDate, i18n.language)}
                </button>
              ))}
            </div>
          )}

          {selected && <MeetingPanel meeting={selected} onChanged={refetch} />}
        </>
      )}
    </div>
  );
};
