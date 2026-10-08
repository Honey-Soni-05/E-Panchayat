/**
 * Shared pieces for every screen that shows a development work: the works
 * register, the budget, a complaint that became a work, and the resident's own
 * tracking page.
 *
 * One rule runs through all of them. The stage a work is at, what may be done
 * to it next, where its money stands and what looks wrong with it are all
 * computed on the server and sent with the work. Nothing here re-derives any of
 * that — these components draw what they are given — so the officer's screen
 * and the resident's screen cannot disagree about the same work.
 */

import React, { useEffect, useState } from 'react';
import { AlertTriangle, Check, Info } from 'lucide-react';

import {
  api,
  type CodedLabel,
  type EntryKind,
  type ProjectEvent,
  type ProjectFlag,
  type ProjectStage,
  type ProjectStatus,
  type WorksVocabulary,
} from '../../lib/api';

// ─── Formatting ─────────────────────────────────────────────────────────────

/** ₹3,50,000 — grouped the way the amount is written in the office. */
export const rupees = (value: number | null | undefined): string =>
  value === null || value === undefined
    ? '—'
    : `₹${Math.round(value).toLocaleString('en-IN')}`;

/** Marathi text is optional on a record the office typed in English only. */
export const pick = (en: string, mr: string | null | undefined, isEnglish: boolean) =>
  isEnglish ? en : mr || en;

export const formatDate = (value: string | null | undefined, isEnglish: boolean): string => {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString(isEnglish ? 'en-IN' : 'mr-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
};

/** Today in the browser's own calendar, as the `YYYY-MM-DD` a date input takes. */
export const todayIso = (): string => {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${now.getFullYear()}-${month}-${day}`;
};

// ─── Vocabulary ─────────────────────────────────────────────────────────────

// Fetched once per page load and shared. The stage names, funding sources and
// asset types are the same for everyone and change only when the server does.
let vocabularyRequest: Promise<WorksVocabulary> | null = null;

export function useVocabulary(): WorksVocabulary | null {
  const [data, setData] = useState<WorksVocabulary | null>(null);

  useEffect(() => {
    let cancelled = false;
    vocabularyRequest ??= api.projects.vocabulary();
    vocabularyRequest
      .then((vocabulary) => {
        if (!cancelled) setData(vocabulary);
      })
      .catch(() => {
        // Let the next screen that needs it ask again. Everything that reads
        // this copes with null — a work carries its own current stage label.
        vocabularyRequest = null;
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return data;
}

// ─── Status and stage ───────────────────────────────────────────────────────

export const STATUS_CHIP: Record<ProjectStatus, string> = {
  Planned: 'bg-slate-100 text-slate-700 border-slate-300',
  Ongoing: 'bg-govblue-50 text-govnavy border-govnavy/25',
  Delayed: 'bg-rose-50 text-rose-800 border-rose-300',
  Completed: 'bg-emerald-50 text-emerald-800 border-emerald-300',
  'On Hold': 'bg-amber-50 text-amber-900 border-amber-300',
  Rejected: 'bg-slate-100 text-slate-500 border-slate-300',
};

export const STATUS_BAR: Record<ProjectStatus, string> = {
  Planned: 'bg-slate-400',
  Ongoing: 'bg-govnavy',
  Delayed: 'bg-rose-600',
  Completed: 'bg-emerald-600',
  'On Hold': 'bg-amber-500',
  Rejected: 'bg-slate-300',
};

const STAGE_CHIP: Record<ProjectStage, string> = {
  proposed: 'bg-slate-100 text-slate-700 border-slate-300',
  verified: 'bg-slate-100 text-slate-700 border-slate-300',
  approved: 'bg-sky-50 text-sky-900 border-sky-300',
  budget_requested: 'bg-amber-50 text-amber-900 border-amber-300',
  budget_approved: 'bg-sky-50 text-sky-900 border-sky-300',
  funds_received: 'bg-sky-50 text-sky-900 border-sky-300',
  in_progress: 'bg-govblue-50 text-govnavy border-govnavy/25',
  completed: 'bg-emerald-50 text-emerald-800 border-emerald-300',
  rejected: 'bg-slate-100 text-slate-500 border-slate-300',
  on_hold: 'bg-amber-50 text-amber-900 border-amber-300',
};

export const StageChip: React.FC<{
  stage: ProjectStage;
  label: string;
  labelMr: string;
  isEnglish: boolean;
}> = ({ stage, label, labelMr, isEnglish }) => (
  <span
    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide border whitespace-nowrap ${
      STAGE_CHIP[stage] ?? STAGE_CHIP.proposed
    }`}
  >
    {pick(label, labelMr, isEnglish)}
  </span>
);

/**
 * The eight steps, as a strip. `stageIndex` is 1-based and null for a work
 * that was rejected or put on hold, which is drawn with nothing filled: the
 * banner beside it says what happened, and a half-filled track would suggest
 * the work is still moving.
 */
export const StageBar: React.FC<{
  stageIndex: number | null;
  stageTotal: number;
  label: string;
  isEnglish: boolean;
}> = ({ stageIndex, stageTotal, label, isEnglish }) => (
  <div className="space-y-1">
    <div
      className="flex gap-0.5"
      role="img"
      aria-label={
        stageIndex
          ? isEnglish
            ? `Stage ${stageIndex} of ${stageTotal}: ${label}`
            : `टप्पा ${stageIndex} / ${stageTotal}: ${label}`
          : label
      }
    >
      {Array.from({ length: stageTotal }, (_, i) => {
        const position = i + 1;
        const done = stageIndex !== null && position < stageIndex;
        const current = stageIndex !== null && position === stageIndex;
        return (
          <span
            key={position}
            className={`h-1.5 flex-1 rounded-full ${
              current
                ? stageIndex === stageTotal
                  ? 'bg-govgreen'
                  : 'bg-govsaffron'
                : done
                  ? 'bg-govgreen'
                  : 'bg-slate-200'
            }`}
          />
        );
      })}
    </div>
    <p className="text-[10px] text-slate-500 font-semibold">
      {stageIndex
        ? isEnglish
          ? `Step ${stageIndex} of ${stageTotal} · ${label}`
          : `टप्पा ${stageIndex} / ${stageTotal} · ${label}`
        : label}
    </p>
  </div>
);

/** The same eight steps written out, for the detail view. */
export const StageTrack: React.FC<{
  stages: CodedLabel[];
  stageIndex: number | null;
  isEnglish: boolean;
}> = ({ stages, stageIndex, isEnglish }) => (
  <ol className="grid grid-cols-4 lg:grid-cols-8 gap-x-1 gap-y-3 p-0 list-none">
    {stages.map((stage, i) => {
      const position = i + 1;
      const done = stageIndex !== null && (position < stageIndex || stageIndex === stages.length);
      const current = stageIndex !== null && position === stageIndex && !done;
      return (
        <li key={stage.code} className="flex flex-col items-center gap-1 text-center min-w-0">
          <span
            className={`w-6 h-6 rounded-full flex items-center justify-center border-2 text-[10px] font-extrabold ${
              done
                ? 'bg-govgreen border-govgreen text-white'
                : current
                  ? 'bg-white border-govsaffron text-govsaffron'
                  : 'bg-white border-slate-200 text-slate-300'
            }`}
            aria-current={current ? 'step' : undefined}
          >
            {done ? <Check size={12} strokeWidth={3} /> : position}
          </span>
          <span
            className={`text-[10px] font-bold leading-tight ${
              done ? 'text-govgreen' : current ? 'text-govsaffron' : 'text-slate-400'
            }`}
          >
            {pick(stage.label, stage.labelMr, isEnglish)}
          </span>
        </li>
      );
    })}
  </ol>
);

// ─── Recording money ────────────────────────────────────────────────────────

export const ENTRY_BUTTON: Record<EntryKind, { en: string; mr: string }> = {
  estimate: { en: 'Record cost estimate', mr: 'खर्चाचा अंदाज नोंदवा' },
  requested: { en: 'Record budget request', mr: 'निधीची मागणी नोंदवा' },
  approved: { en: 'Record budget approval', mr: 'निधी मंजुरी नोंदवा' },
  received: { en: 'Record funds received', mr: 'प्राप्त निधी नोंदवा' },
  spent: { en: 'Record spending', mr: 'खर्च नोंदवा' },
};

/**
 * The money entry a work is waiting for at the stage it has reached — or null
 * when the next step is a decision rather than a figure. Only ever one of the
 * kinds the server says it will accept, so this chooses which button to put
 * first; it does not decide what is allowed.
 */
export const nextEntryKind = (
  stage: ProjectStage,
  offered: EntryKind[],
  hasEstimate: boolean,
): EntryKind | null => {
  const wanted: Partial<Record<ProjectStage, EntryKind>> = {
    proposed: 'estimate',
    verified: 'estimate',
    approved: 'requested',
    budget_requested: 'approved',
    budget_approved: 'received',
    in_progress: 'spent',
  };
  const kind = wanted[stage];
  if (!kind || !offered.includes(kind)) return null;
  // Once there is an estimate, a proposal is waiting on people, not on a figure.
  if (kind === 'estimate' && hasEstimate) return null;
  return kind;
};

// ─── Money ──────────────────────────────────────────────────────────────────

interface MoneyFigures {
  estimated: number | null;
  requested: number | null;
  approved: number | null;
  received: number;
  spent: number;
}

/**
 * The five figures in the order the money actually moves. A figure that has
 * not been recorded is shown as a dash, never as ₹0: "nobody has estimated
 * this yet" and "it will cost nothing" are different statements.
 */
export const MoneyStrip: React.FC<{ money: MoneyFigures; isEnglish: boolean }> = ({
  money,
  isEnglish,
}) => {
  const cells: { label: string; value: number | null; tone: string }[] = [
    { label: isEnglish ? 'Estimated' : 'अंदाजित', value: money.estimated, tone: 'text-slate-700' },
    { label: isEnglish ? 'Requested' : 'मागणी', value: money.requested, tone: 'text-slate-700' },
    { label: isEnglish ? 'Approved' : 'मंजूर', value: money.approved, tone: 'text-govnavy' },
    {
      label: isEnglish ? 'Received' : 'प्राप्त',
      value: money.approved === null && !money.received ? null : money.received,
      tone: 'text-govnavy',
    },
    {
      label: isEnglish ? 'Spent' : 'खर्च',
      value: money.approved === null && !money.spent ? null : money.spent,
      tone: 'text-govgreen',
    },
  ];
  return (
    <dl className="grid grid-cols-5 gap-2 text-center">
      {cells.map((cell) => (
        <div key={cell.label} className="min-w-0">
          <dt className="text-[9px] text-slate-400 uppercase tracking-wider font-bold">
            {cell.label}
          </dt>
          <dd className={`text-xs font-bold tabular-nums truncate ${cell.tone}`}>
            {rupees(cell.value)}
          </dd>
        </div>
      ))}
    </dl>
  );
};

/**
 * Work done against money spent, on one scale. They are drawn together because
 * the gap between them is the thing worth seeing: eighty per cent of the money
 * gone with a third of the work visible is a question somebody should ask.
 */
export const ProgressPair: React.FC<{
  physicalPercent: number;
  financialPercent: number;
  physicalDetail?: string | null;
  isEnglish: boolean;
}> = ({ physicalPercent, financialPercent, physicalDetail, isEnglish }) => {
  const rows = [
    {
      label: isEnglish ? 'Work done' : 'झालेले काम',
      detail: physicalDetail,
      value: physicalPercent,
      bar: 'bg-govnavy',
    },
    {
      label: isEnglish ? 'Budget spent' : 'खर्च झालेला निधी',
      detail: null,
      value: financialPercent,
      bar: 'bg-govgreen',
    },
  ];
  return (
    <div className="space-y-2">
      {rows.map((row) => (
        <div key={row.label} className="space-y-1">
          <div className="flex items-center justify-between gap-2 text-[11px]">
            <span className="text-slate-500 font-bold">
              {row.label}
              {row.detail ? <span className="font-semibold text-slate-400"> · {row.detail}</span> : null}
            </span>
            <strong className="text-slate-800 tabular-nums">{row.value}%</strong>
          </div>
          <div
            className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden"
            role="progressbar"
            aria-label={row.label}
            aria-valuenow={row.value}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className={`h-full rounded-full ${row.bar}`}
              style={{ width: `${Math.max(0, Math.min(100, row.value))}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
};

// ─── Flags ──────────────────────────────────────────────────────────────────

/**
 * What a rule noticed about a work. Worded on the server as something to check,
 * and shown here without a verdict colour stronger than amber: a flag compares
 * two recorded figures, and spending can run ahead of visible work for good
 * reasons.
 */
export const FlagList: React.FC<{ flags: ProjectFlag[]; isEnglish: boolean }> = ({
  flags,
  isEnglish,
}) => {
  if (!flags.length) return null;
  return (
    <ul className="space-y-1.5 p-0 list-none">
      {flags.map((flag) => {
        const warning = flag.severity === 'warning';
        const Icon = warning ? AlertTriangle : Info;
        return (
          <li
            key={flag.code}
            className={`flex items-start gap-1.5 text-[11px] leading-relaxed font-semibold rounded-lg border px-2.5 py-1.5 ${
              warning
                ? 'bg-amber-50 border-amber-200 text-amber-900'
                : 'bg-sky-50 border-sky-200 text-sky-900'
            }`}
          >
            <Icon size={12} className="mt-0.5 flex-shrink-0" />
            <span>{pick(flag.message, flag.messageMr, isEnglish)}</span>
          </li>
        );
      })}
    </ul>
  );
};

export const warningCount = (flags: ProjectFlag[]): number =>
  flags.filter((flag) => flag.severity === 'warning').length;

// ─── History ────────────────────────────────────────────────────────────────

export const WorkHistory: React.FC<{
  events: ProjectEvent[];
  vocabulary: WorksVocabulary | null;
  isEnglish: boolean;
}> = ({ events, vocabulary, isEnglish }) => {
  const stageName = (code: string): string => {
    const known = [...(vocabulary?.stages ?? []), ...(vocabulary?.sideStages ?? [])].find(
      (stage) => stage.code === code,
    );
    return known ? pick(known.label, known.labelMr, isEnglish) : code;
  };

  if (!events.length) {
    return (
      <p className="text-xs text-slate-400">
        {isEnglish
          ? 'Nothing was recorded for this work before stages were tracked.'
          : 'टप्प्यांची नोंद सुरू होण्यापूर्वी या कामाची कोणतीही नोंद नाही.'}
      </p>
    );
  }
  return (
    <ol className="space-y-0 p-0 list-none">
      {events.map((event, i, all) => (
        <li key={event.id} className="flex gap-3">
          <div className="flex flex-col items-center flex-shrink-0">
            <span
              className={`w-2.5 h-2.5 rounded-full mt-1.5 ${
                event.toStage === 'completed'
                  ? 'bg-govgreen'
                  : event.toStage === 'rejected'
                    ? 'bg-rose-500'
                    : event.toStage
                      ? 'bg-govnavy'
                      : 'bg-govsaffron'
              }`}
            />
            {i < all.length - 1 && <span className="w-px flex-1 bg-slate-200 my-1" />}
          </div>
          <div className="pb-3.5 min-w-0">
            {/* A move between stages is headed by the stage it reached; the
                note under it is the reason the officer gave. */}
            {event.toStage && (
              <p className="text-xs font-bold text-slate-800">{stageName(event.toStage)}</p>
            )}
            {(event.note || !event.toStage) && (
              <p className="text-xs text-slate-600 leading-relaxed">
                {pick(event.note ?? '', event.noteMr, isEnglish) ||
                  (isEnglish ? 'Updated' : 'अद्ययावत')}
              </p>
            )}
            <p className="text-[11px] text-slate-400">
              {formatDate(event.createdAt, isEnglish)}
              {event.actorName && ` · ${event.actorName}`}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
};
