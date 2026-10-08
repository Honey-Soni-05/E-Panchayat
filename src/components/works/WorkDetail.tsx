/**
 * One development work, from the moment somebody asked for it to the moment
 * the resident who asked says it is done.
 *
 * An officer acts here; a resident reads the same record with the controls
 * left out. What an officer may do next is not decided in this file. Each work
 * arrives with `steps` — the decisions and the kinds of money entry the server
 * will currently accept — and the buttons below are exactly those. A second
 * copy of the stage rules in the browser would be right until the first time
 * one of them changed.
 *
 * Every form says what pressing its button will do before it is pressed: which
 * stage the work moves to, and what the residents who asked for it will see.
 * Nothing recorded here can be edited afterwards — a revision is a new entry
 * and the earlier figure stays in the ledger — so the moment to be clear is
 * before, not after.
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  CalendarDays,
  ChevronRight,
  Landmark,
  Loader2,
  MapPin,
  Trash2,
  Users,
  X,
} from 'lucide-react';

import {
  api,
  type BudgetEntry,
  type BudgetEntryCreate,
  type EntryKind,
  type ProjectDetail,
  type SabhaMeeting,
  type StageAction,
  type WorksVocabulary,
} from '../../lib/api';
import { useMutation, useQuery } from '../../lib/useApi';
import { ErrorNotice } from '../schemes/SchemeBits';
import {
  ENTRY_BUTTON,
  FlagList,
  MoneyStrip,
  ProgressPair,
  STATUS_CHIP,
  StageChip,
  StageTrack,
  WorkHistory,
  formatDate,
  pick,
  rupees,
  todayIso,
  useVocabulary,
} from './WorkBits';

const INPUT =
  'w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-govnavy/25';
const LABEL = 'block text-[11px] font-bold text-slate-600';

/** One thing an officer can do to a work: a decision, a money entry, or a
 *  progress update. Exported so another screen can open the panel on it. */
export type WorkPanel =
  | { type: 'decision'; action: StageAction }
  | { type: 'entry'; kind: EntryKind }
  | { type: 'progress' };
type Panel = WorkPanel;

type Copy = { en: string; mr: string };
const say = (copy: Copy, isEnglish: boolean) => (isEnglish ? copy.en : copy.mr);

// ─── What each step is called, and what it does ─────────────────────────────

const ACTION_COPY: Record<
  StageAction,
  { button: Copy; prompt: Copy; placeholder: Copy; effect: Copy; reasonRequired: boolean }
> = {
  verify: {
    button: { en: 'Record field verification', mr: 'स्थळ पडताळणी नोंदवा' },
    prompt: { en: 'What did the site visit find?', mr: 'स्थळ पाहणीत काय आढळले?' },
    placeholder: {
      en: 'e.g. The stretch is about 600 m and has four working lights; twenty poles are needed.',
      mr: 'उदा. मार्ग सुमारे ६०० मी. आहे, चार दिवे सुरू आहेत; वीस खांब लागतील.',
    },
    effect: {
      en: 'The proposal moves to “Need verified”. This note is the evidence the Panchayat’s decision rests on.',
      mr: 'प्रस्ताव “गरज पडताळली” या टप्प्यावर जाईल. पंचायतीचा निर्णय या नोंदीवर आधारित असेल.',
    },
    reasonRequired: true,
  },
  approve: {
    button: { en: 'Record Panchayat approval', mr: 'पंचायतीची मंजुरी नोंदवा' },
    prompt: { en: 'Decision note', mr: 'निर्णयाची नोंद' },
    placeholder: {
      en: 'e.g. Approved in the Gram Sabha; to be taken up from the Finance Commission grant.',
      mr: 'उदा. ग्रामसभेत मंजूर; वित्त आयोग अनुदानातून काम हाती घेणार.',
    },
    effect: {
      en: 'The proposal moves to “Approved by Panchayat”. The next step is to record the budget request.',
      mr: 'प्रस्ताव “पंचायतीची मंजुरी” या टप्प्यावर जाईल. पुढचा टप्पा: निधीची मागणी नोंदवणे.',
    },
    reasonRequired: false,
  },
  reject: {
    button: { en: 'Not approved', mr: 'नामंजूर' },
    prompt: { en: 'Reason', mr: 'कारण' },
    placeholder: {
      en: 'The residents who asked for this will be shown what you write here.',
      mr: 'ही मागणी करणाऱ्या रहिवाशांना तुम्ही येथे लिहिलेले कारण दाखवले जाईल.',
    },
    effect: {
      en: 'The proposal is closed as not approved, and each resident who asked sees this reason on their own complaint. Their complaints stay open — decide on each from the complaints screen.',
      mr: 'प्रस्ताव नामंजूर म्हणून बंद होईल आणि मागणी करणाऱ्या प्रत्येक रहिवाशाला हे कारण त्यांच्या तक्रारीवर दिसेल. त्यांच्या तक्रारी खुल्या राहतील — प्रत्येकीवर तक्रारी पानावरून निर्णय घ्या.',
    },
    reasonRequired: true,
  },
  start: {
    button: { en: 'Start the work', mr: 'काम सुरू करा' },
    prompt: { en: 'Note (optional)', mr: 'टीप (ऐच्छिक)' },
    placeholder: { en: 'e.g. Work order issued.', mr: 'उदा. कार्यादेश दिला.' },
    effect: {
      en: 'The work moves to “Work in progress”. Spending and progress can be recorded from then on.',
      mr: 'काम “काम सुरू” या टप्प्यावर जाईल. त्यानंतर खर्च व प्रगती नोंदवता येईल.',
    },
    reasonRequired: false,
  },
  complete: {
    button: { en: 'Mark the work complete', mr: 'काम पूर्ण झाल्याची नोंद करा' },
    prompt: { en: 'Note (optional)', mr: 'टीप (ऐच्छिक)' },
    placeholder: { en: 'e.g. Inspected and handed over.', mr: 'उदा. पाहणी करून हस्तांतरित.' },
    effect: {
      en: 'The work is closed. What it built is added to the asset register and the map, and each resident who asked is asked to confirm that it has been done.',
      mr: 'काम बंद होईल. उभारलेली मालमत्ता नोंदवहीत व नकाशावर येईल, आणि मागणी करणाऱ्या प्रत्येक रहिवाशाला काम झाल्याची खात्री करण्यास सांगितले जाईल.',
    },
    reasonRequired: false,
  },
  hold: {
    button: { en: 'Put on hold', mr: 'स्थगित करा' },
    prompt: { en: 'Why is it being held?', mr: 'काम का स्थगित केले जात आहे?' },
    placeholder: {
      en: 'e.g. Supplier has not delivered the poles.',
      mr: 'उदा. पुरवठादाराने खांब दिलेले नाहीत.',
    },
    effect: {
      en: 'Nothing can be recorded against the work until it is resumed. It then returns to the stage it is at now.',
      mr: 'काम पुन्हा सुरू करेपर्यंत त्यावर कोणतीही नोंद करता येणार नाही. नंतर ते सध्याच्या टप्प्यावर परत येईल.',
    },
    reasonRequired: true,
  },
  resume: {
    button: { en: 'Resume', mr: 'पुन्हा सुरू करा' },
    prompt: { en: 'Note (optional)', mr: 'टीप (ऐच्छिक)' },
    placeholder: { en: 'e.g. Poles delivered.', mr: 'उदा. खांब मिळाले.' },
    effect: {
      en: 'The work returns to the stage it was held at.',
      mr: 'काम ज्या टप्प्यावर स्थगित केले होते त्या टप्प्यावर परत येईल.',
    },
    reasonRequired: false,
  },
};

/** What the server will do with an entry of this kind at this stage. */
const entryEffect = (kind: EntryKind, record: ProjectDetail): Copy => {
  switch (kind) {
    case 'estimate':
      return record.finance.estimated !== null
        ? {
            en: 'This becomes the current estimate. The earlier figure stays in the ledger. The figure is yours — nothing in this system estimates a cost.',
            mr: 'हा सध्याचा अंदाज ठरेल. आधीचा आकडा नोंदवहीत राहील. हा आकडा तुमचा आहे — ही प्रणाली खर्चाचा अंदाज लावत नाही.',
          }
        : {
            en: 'The figure is yours — nothing in this system estimates a cost. It can be revised later, and the revision is recorded.',
            mr: 'हा आकडा तुमचा आहे — ही प्रणाली खर्चाचा अंदाज लावत नाही. नंतर सुधारता येईल आणि सुधारणेची नोंद राहील.',
          };
    case 'requested':
      return record.stage === 'approved'
        ? {
            en: 'Recording this moves the work to “Budget requested”.',
            mr: 'ही नोंद केल्यावर काम “निधीची मागणी केली” या टप्प्यावर जाईल.',
          }
        : {
            en: 'This replaces the amount requested. The earlier request stays in the ledger.',
            mr: 'मागणीची रक्कम बदलेल. आधीची मागणी नोंदवहीत राहील.',
          };
    case 'approved':
      return record.stage === 'budget_requested'
        ? {
            en: 'Recording this moves the work to “Budget approved”. If less was sanctioned than requested, enter what was sanctioned — the difference is shown, not hidden.',
            mr: 'ही नोंद केल्यावर काम “निधी मंजूर” या टप्प्यावर जाईल. मागणीपेक्षा कमी मंजूर झाले असल्यास मंजूर रक्कमच नोंदवा — फरक दाखवला जाईल.',
          }
        : {
            en: 'This revises the approved amount. It cannot be less than what has already been received.',
            mr: 'मंजूर रक्कम सुधारली जाईल. ती आधीच प्राप्त झालेल्या रकमेपेक्षा कमी असू शकत नाही.',
          };
    case 'received':
      return record.stage === 'budget_approved'
        ? {
            en: 'Recording this moves the work to “Funds received”. An instalment is fine: enter what has actually arrived.',
            mr: 'ही नोंद केल्यावर काम “निधी प्राप्त” या टप्प्यावर जाईल. हप्ता असल्यास प्रत्यक्ष जमा झालेली रक्कम नोंदवा.',
          }
        : {
            en: 'Added to what has already been received. The total cannot exceed the approved amount.',
            mr: 'आधी प्राप्त झालेल्या रकमेत जमा होईल. एकूण रक्कम मंजूर रकमेपेक्षा जास्त असू शकत नाही.',
          };
    case 'spent':
      return {
        en: 'Added to what has already been spent. The total cannot exceed what has been received.',
        mr: 'आधीच्या खर्चात जमा होईल. एकूण खर्च प्राप्त निधीपेक्षा जास्त असू शकत नाही.',
      };
  }
};

/** The amount most likely meant, offered as a starting point to be changed. */
const suggestedAmount = (kind: EntryKind, record: ProjectDetail): string => {
  const { finance } = record;
  const value =
    kind === 'requested'
      ? finance.requested ?? finance.estimated
      : kind === 'approved'
        ? finance.approved ?? finance.requested
        : kind === 'received'
          ? finance.awaiting || null
          : kind === 'estimate'
            ? finance.estimated
            : null;
  return value ? String(Math.round(value)) : '';
};

/** Where the officer's attention should go at each stage. */
const nextHint = (record: ProjectDetail): Copy => {
  switch (record.stage) {
    case 'proposed':
      return {
        en: 'Check the need on site, then record what you found.',
        mr: 'स्थळावर गरज तपासा आणि आढळलेली माहिती नोंदवा.',
      };
    case 'verified':
      return record.finance.estimated === null
        ? {
            en: 'Record what the work is expected to cost, then put it to the Panchayat.',
            mr: 'कामाचा अंदाजित खर्च नोंदवा आणि प्रस्ताव पंचायतीसमोर ठेवा.',
          }
        : {
            en: 'Put the proposal to the Panchayat and record the decision.',
            mr: 'प्रस्ताव पंचायतीसमोर ठेवा आणि निर्णय नोंदवा.',
          };
    case 'approved':
      return {
        en: 'Record the budget request once it has been sent for sanction.',
        mr: 'मंजुरीसाठी पाठवल्यावर निधीची मागणी नोंदवा.',
      };
    case 'budget_requested':
      return {
        en: 'Waiting for sanction. Record the approval when the order arrives.',
        mr: 'मंजुरीची प्रतीक्षा. आदेश आल्यावर निधी मंजुरी नोंदवा.',
      };
    case 'budget_approved':
      return {
        en: 'Record the funds when they are credited.',
        mr: 'निधी जमा झाल्यावर त्याची नोंद करा.',
      };
    case 'funds_received':
      return { en: 'The money is in hand. Start the work.', mr: 'निधी उपलब्ध आहे. काम सुरू करा.' };
    case 'in_progress':
      return {
        en: 'Record spending and progress as the work goes on.',
        mr: 'काम पुढे जाईल तसा खर्च व प्रगती नोंदवा.',
      };
    case 'completed':
      return {
        en: 'Complete. The residents who asked have been asked to confirm.',
        mr: 'काम पूर्ण. मागणी करणाऱ्या रहिवाशांना खात्री करण्यास सांगितले आहे.',
      };
    case 'rejected':
      return { en: 'This proposal was not approved.', mr: 'हा प्रस्ताव मंजूर झाला नाही.' };
    case 'on_hold':
      return { en: 'On hold. Resume it to continue.', mr: 'स्थगित. पुढे जाण्यासाठी पुन्हा सुरू करा.' };
  }
};

/** The one step that moves a work forward from where it is. */
const isPrimary = (panel: Panel, record: ProjectDetail): boolean => {
  const stage = record.stage;
  if (panel.type === 'decision') {
    if (panel.action === 'verify') return stage === 'proposed';
    if (panel.action === 'approve') return record.finance.estimated !== null;
    // Completing is the next step only once the count has been reached; until
    // then the server would refuse it and say how many are left.
    if (panel.action === 'complete') {
      return record.unitsPlanned === null || record.unitsDone >= record.unitsPlanned;
    }
    return panel.action === 'start' || panel.action === 'resume';
  }
  if (panel.type === 'entry') {
    if (panel.kind === 'estimate') return stage === 'verified' && record.finance.estimated === null;
    if (panel.kind === 'requested') return stage === 'approved';
    if (panel.kind === 'approved') return stage === 'budget_requested';
    if (panel.kind === 'received') return stage === 'budget_approved';
    // A late bill can still be recorded on a finished work, but it is not
    // what anyone is waiting for.
    return panel.kind === 'spent' && stage === 'in_progress';
  }
  return true;
};

// ─── Forms ──────────────────────────────────────────────────────────────────

const FormShell: React.FC<{
  title: string;
  effect: string;
  error: string | null;
  saving: boolean;
  submitLabel: string;
  danger?: boolean;
  isEnglish: boolean;
  onCancel: () => void;
  onSubmit: () => void;
  children: React.ReactNode;
}> = ({ title, effect, error, saving, submitLabel, danger, isEnglish, onCancel, onSubmit, children }) => (
  <form
    onSubmit={(e) => {
      e.preventDefault();
      onSubmit();
    }}
    className="rounded-xl border border-govblue-200 bg-govblue-50/60 p-4 space-y-3"
  >
    <h4 className="text-[11px] font-extrabold uppercase tracking-wider text-govnavy">{title}</h4>
    {children}
    <p className="text-[11px] text-govnavy font-semibold flex items-start gap-1.5 leading-relaxed">
      <ChevronRight size={13} className="mt-0.5 flex-shrink-0" />
      <span>{effect}</span>
    </p>
    {error && <ErrorNotice message={error} />}
    <div className="flex flex-wrap gap-2">
      <button
        type="submit"
        disabled={saving}
        className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-lg disabled:opacity-60 text-white text-xs font-bold transition-colors ${
          danger ? 'bg-rose-700 hover:bg-rose-800' : 'bg-govnavy hover:bg-govblue-700'
        }`}
      >
        {saving && <Loader2 size={13} className="animate-spin" />}
        {submitLabel}
      </button>
      <button
        type="button"
        onClick={onCancel}
        className="px-4 py-2 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-600 text-xs font-bold transition-colors"
      >
        {isEnglish ? 'Cancel' : 'रद्द करा'}
      </button>
    </div>
  </form>
);

const DecisionForm: React.FC<{
  action: StageAction;
  isEnglish: boolean;
  saving: boolean;
  error: string | null;
  onCancel: () => void;
  onSubmit: (body: { note?: string; sabhaMeetingId?: string }) => void;
}> = ({ action, isEnglish, saving, error, onCancel, onSubmit }) => {
  const copy = ACTION_COPY[action];
  const [note, setNote] = useState('');
  const [meetingId, setMeetingId] = useState('');

  // Only an approval can cite a meeting, so only an approval asks for the list.
  const meetings = useQuery<SabhaMeeting[]>(
    () => (action === 'approve' ? api.sabha.meetings() : Promise.resolve([])),
    [action],
  );

  return (
    <FormShell
      title={say(copy.button, isEnglish)}
      effect={say(copy.effect, isEnglish)}
      error={error}
      saving={saving}
      submitLabel={say(copy.button, isEnglish)}
      danger={action === 'reject'}
      isEnglish={isEnglish}
      onCancel={onCancel}
      onSubmit={() => onSubmit({ note: note.trim(), sabhaMeetingId: meetingId })}
    >
      <div className="space-y-1.5">
        <label htmlFor="decision-note" className={LABEL}>
          {say(copy.prompt, isEnglish)}
        </label>
        <textarea
          id="decision-note"
          rows={3}
          required={copy.reasonRequired}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder={say(copy.placeholder, isEnglish)}
          className={`${INPUT} resize-y`}
        />
      </div>

      {action === 'approve' && (meetings.data?.length ?? 0) > 0 && (
        <div className="space-y-1.5">
          <label htmlFor="decision-meeting" className={LABEL}>
            {isEnglish ? 'Decided at (optional)' : 'निर्णय कोणत्या सभेत झाला (ऐच्छिक)'}
          </label>
          <select
            id="decision-meeting"
            value={meetingId}
            onChange={(e) => setMeetingId(e.target.value)}
            className={INPUT}
          >
            <option value="">
              {isEnglish ? 'Not at a recorded Gram Sabha' : 'नोंदवलेल्या ग्रामसभेत नाही'}
            </option>
            {(meetings.data ?? []).map((meeting) => (
              <option key={meeting.id} value={meeting.id}>
                {formatDate(meeting.meetingDate, isEnglish)} ·{' '}
                {pick(meeting.title, meeting.titleMr, isEnglish)}
              </option>
            ))}
          </select>
        </div>
      )}
    </FormShell>
  );
};

const EntryForm: React.FC<{
  kind: EntryKind;
  record: ProjectDetail;
  vocabulary: WorksVocabulary | null;
  isEnglish: boolean;
  saving: boolean;
  error: string | null;
  onCancel: () => void;
  onSubmit: (entry: BudgetEntryCreate) => void;
}> = ({ kind, record, vocabulary, isEnglish, saving, error, onCancel, onSubmit }) => {
  const [amount, setAmount] = useState(() => suggestedAmount(kind, record));
  const [entryDate, setEntryDate] = useState(todayIso());
  const [source, setSource] = useState(record.fundingSource ?? '');
  const [reference, setReference] = useState('');
  const [note, setNote] = useState('');

  const value = Number(amount);
  // An estimate has no source yet; a payment is made from the work's own.
  const asksForSource = kind === 'requested' || kind === 'approved' || kind === 'received';

  return (
    <FormShell
      title={say(ENTRY_BUTTON[kind], isEnglish)}
      effect={say(entryEffect(kind, record), isEnglish)}
      error={error}
      saving={saving}
      submitLabel={say(ENTRY_BUTTON[kind], isEnglish)}
      isEnglish={isEnglish}
      onCancel={onCancel}
      onSubmit={() =>
        onSubmit({
          kind,
          amount: value,
          entryDate,
          fundingSource: asksForSource && source ? source : undefined,
          reference: reference.trim() || undefined,
          note: note.trim() || undefined,
        })
      }
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <label htmlFor="entry-amount" className={LABEL}>
            {isEnglish ? 'Amount (₹)' : 'रक्कम (₹)'}
          </label>
          <input
            id="entry-amount"
            type="number"
            min={1}
            step="any"
            required
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className={INPUT}
          />
          {value > 0 && (
            <p className="text-[10px] text-slate-500 tabular-nums">= {rupees(value)}</p>
          )}
        </div>
        <div className="space-y-1.5">
          <label htmlFor="entry-date" className={LABEL}>
            {isEnglish ? 'Date it happened' : 'घटनेचा दिनांक'}
          </label>
          <input
            id="entry-date"
            type="date"
            required
            max={todayIso()}
            value={entryDate}
            onChange={(e) => setEntryDate(e.target.value)}
            className={INPUT}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {asksForSource && (
          <div className="space-y-1.5">
            <label htmlFor="entry-source" className={LABEL}>
              {isEnglish ? 'Funding source' : 'निधीचा स्रोत'}
            </label>
            <select
              id="entry-source"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className={INPUT}
            >
              <option value="">{isEnglish ? 'Not recorded' : 'नोंद नाही'}</option>
              {(vocabulary?.fundingSources ?? []).map((item) => (
                <option key={item.code} value={item.code}>
                  {pick(item.label, item.labelMr, isEnglish)}
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="space-y-1.5">
          <label htmlFor="entry-reference" className={LABEL}>
            {kind === 'spent'
              ? isEnglish
                ? 'Bill or voucher no. (optional)'
                : 'बिल / व्हाउचर क्र. (ऐच्छिक)'
              : isEnglish
                ? 'Order or letter no. (optional)'
                : 'आदेश / पत्र क्र. (ऐच्छिक)'}
          </label>
          <input
            id="entry-reference"
            value={reference}
            maxLength={120}
            onChange={(e) => setReference(e.target.value)}
            className={INPUT}
          />
        </div>
      </div>

      <div className="space-y-1.5">
        <label htmlFor="entry-note" className={LABEL}>
          {isEnglish ? 'Note (optional)' : 'टीप (ऐच्छिक)'}
        </label>
        <input
          id="entry-note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder={
            kind === 'spent'
              ? isEnglish
                ? 'What was paid for'
                : 'कशासाठी खर्च झाला'
              : undefined
          }
          className={INPUT}
        />
      </div>
    </FormShell>
  );
};

const ProgressForm: React.FC<{
  record: ProjectDetail;
  isEnglish: boolean;
  saving: boolean;
  error: string | null;
  onCancel: () => void;
  onSubmit: (body: { unitsDone?: number; progress?: number; note?: string }) => void;
}> = ({ record, isEnglish, saving, error, onCancel, onSubmit }) => {
  const counted = record.unitsPlanned !== null;
  const unit = pick(record.unitLabel ?? 'units', record.unitLabelMr, isEnglish);
  const [amount, setAmount] = useState(String(counted ? record.unitsDone : record.progress));
  const [note, setNote] = useState('');

  return (
    <FormShell
      title={isEnglish ? 'Record progress' : 'प्रगती नोंदवा'}
      effect={
        counted
          ? isEnglish
            ? `Recorded as a count because that is something anyone can check on site. The work can be marked complete once all ${record.unitsPlanned} are done.`
            : `संख्या म्हणून नोंद, कारण ती स्थळावर कोणीही तपासू शकते. सर्व ${record.unitsPlanned} पूर्ण झाल्यावर काम पूर्ण म्हणून नोंदवता येईल.`
          : isEnglish
            ? 'Recorded as a percentage of the work physically complete.'
            : 'प्रत्यक्ष पूर्ण झालेल्या कामाची टक्केवारी म्हणून नोंद.'
      }
      error={error}
      saving={saving}
      submitLabel={isEnglish ? 'Record progress' : 'प्रगती नोंदवा'}
      isEnglish={isEnglish}
      onCancel={onCancel}
      onSubmit={() =>
        onSubmit(
          counted
            ? { unitsDone: Number(amount), note: note.trim() || undefined }
            : { progress: Number(amount), note: note.trim() || undefined },
        )
      }
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <label htmlFor="progress-amount" className={LABEL}>
            {counted
              ? isEnglish
                ? `Completed so far, of ${record.unitsPlanned} ${unit}`
                : `${record.unitsPlanned} ${unit} पैकी आतापर्यंत पूर्ण`
              : isEnglish
                ? 'Physically complete (%)'
                : 'प्रत्यक्ष पूर्ण (%)'}
          </label>
          <input
            id="progress-amount"
            type="number"
            min={0}
            max={counted ? (record.unitsPlanned ?? undefined) : 100}
            required
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className={INPUT}
          />
        </div>
        <div className="space-y-1.5">
          <label htmlFor="progress-note" className={LABEL}>
            {isEnglish ? 'Note (optional)' : 'टीप (ऐच्छिक)'}
          </label>
          <input
            id="progress-note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className={INPUT}
          />
        </div>
      </div>
    </FormShell>
  );
};

/**
 * Putting a wrong receipt or payment right. Those two add up, so a mistyped
 * one cannot be fixed by recording another; and nothing in the ledger is ever
 * overtyped. The officer says what the entry should have been and why, and a
 * correcting line is added beneath it.
 */
const CorrectionForm: React.FC<{
  entry: BudgetEntry;
  isEnglish: boolean;
  saving: boolean;
  error: string | null;
  onCancel: () => void;
  onSubmit: (body: { amount: number; reason: string }) => void;
}> = ({ entry, isEnglish, saving, error, onCancel, onSubmit }) => {
  const standing = entry.correctedTo ?? entry.amount;
  const [amount, setAmount] = useState(String(Math.round(standing)));
  const [reason, setReason] = useState('');
  const value = Number(amount);

  return (
    <FormShell
      title={isEnglish ? 'Correct this entry' : 'ही नोंद दुरुस्त करा'}
      effect={
        isEnglish
          ? 'A correcting line is added for the difference. The entry as first recorded stays in the ledger, with your name and this reason beside the change. Enter 0 to cancel an entry that should not have been made at all.'
          : 'फरकासाठी दुरुस्तीची ओळ जोडली जाईल. मूळ नोंद नोंदवहीत तशीच राहील आणि बदलासोबत तुमचे नाव व हे कारण दिसेल. जी नोंद व्हायलाच नको होती ती रद्द करण्यासाठी 0 भरा.'
      }
      error={error}
      saving={saving}
      submitLabel={isEnglish ? 'Record the correction' : 'दुरुस्ती नोंदवा'}
      isEnglish={isEnglish}
      onCancel={onCancel}
      onSubmit={() => onSubmit({ amount: value, reason: reason.trim() })}
    >
      <p className="text-[11px] text-slate-600">
        {pick(entry.kindLabel, entry.kindLabelMr, isEnglish)} · {formatDate(entry.entryDate, isEnglish)}{' '}
        · {isEnglish ? 'recorded as' : 'नोंदवलेली रक्कम'}{' '}
        <strong className="tabular-nums">{rupees(standing)}</strong>
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <label htmlFor="correction-amount" className={LABEL}>
            {isEnglish ? 'What it should have been (₹)' : 'योग्य रक्कम (₹)'}
          </label>
          <input
            id="correction-amount"
            type="number"
            min={0}
            step="any"
            required
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className={INPUT}
          />
          {amount.trim() !== '' && value >= 0 && (
            <p className="text-[10px] text-slate-500 tabular-nums">= {rupees(value)}</p>
          )}
        </div>
        <div className="space-y-1.5">
          <label htmlFor="correction-reason" className={LABEL}>
            {isEnglish ? 'What was wrong' : 'काय चुकले होते'}
          </label>
          <input
            id="correction-reason"
            required
            minLength={3}
            maxLength={1000}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder={isEnglish ? 'e.g. One zero too many' : 'उदा. एक शून्य जास्त टाकले'}
            className={INPUT}
          />
        </div>
      </div>
    </FormShell>
  );
};

// ─── The panel ──────────────────────────────────────────────────────────────

export const WorkDetail: React.FC<{
  projectId: string;
  isEnglish: boolean;
  /** Officers and admins act; a resident reads the same record. */
  canAct: boolean;
  /** A form to have open on arrival — set when the officer pressed "Record
   *  spending" on another screen. Ignored if the server will not accept it. */
  initialPanel?: WorkPanel;
  onClose: () => void;
  onChanged?: () => void;
}> = ({ projectId, isEnglish, canAct, initialPanel, onClose, onChanged }) => {
  const vocabulary = useVocabulary();
  const detail = useQuery<ProjectDetail>(() => api.projects.get(projectId), [projectId]);

  // Every write returns the work as the server now holds it, so the panel
  // shows what was stored rather than what was typed.
  const [record, setRecord] = useState<ProjectDetail | null>(null);
  useEffect(() => {
    if (detail.data) setRecord(detail.data);
  }, [detail.data]);

  const [panel, setPanel] = useState<Panel | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  // The entry a correction is being written against, if any.
  const [correctingId, setCorrectingId] = useState<string | null>(null);

  // Open on the form the officer asked for, once, and only if the work is at a
  // point where the server will take it.
  const openedInitial = useRef(false);
  useEffect(() => {
    if (!record || openedInitial.current || !initialPanel || !canAct) return;
    openedInitial.current = true;
    const { steps } = record;
    const allowed =
      initialPanel.type === 'entry'
        ? steps.entryKinds.includes(initialPanel.kind)
        : initialPanel.type === 'progress'
          ? steps.canRecordProgress
          : steps.actions.includes(initialPanel.action);
    if (allowed) setPanel(initialPanel);
  }, [record, initialPanel, canAct]);

  // The ledger as it is read: each entry followed by the corrections made to it.
  const ledger = useMemo(() => {
    const entries = record?.entries ?? [];
    const corrections = new Map<string, BudgetEntry[]>();
    for (const entry of entries) {
      if (entry.correctsId) {
        corrections.set(entry.correctsId, [...(corrections.get(entry.correctsId) ?? []), entry]);
      }
    }
    return entries
      .filter((entry) => !entry.correctsId)
      .flatMap((entry) => [entry, ...(corrections.get(entry.id) ?? [])]);
  }, [record]);

  const applied = (next: ProjectDetail) => {
    setRecord(next);
    setPanel(null);
    onChanged?.();
  };

  const decide = useMutation(
    (action: StageAction, body: { note?: string; sabhaMeetingId?: string }) =>
      api.projects.decide(projectId, action, body),
    applied,
  );
  const addEntry = useMutation(
    (entry: BudgetEntryCreate) => api.projects.addEntry(projectId, entry),
    applied,
  );
  const recordProgress = useMutation(
    (body: { unitsDone?: number; progress?: number; note?: string }) =>
      api.projects.recordProgress(projectId, body),
    applied,
  );
  const setDelayed = useMutation(
    (delayed: boolean) => api.projects.update(projectId, { status: delayed ? 'Delayed' : 'Ongoing' }),
    () => {
      detail.refetch();
      onChanged?.();
    },
  );
  const correct = useMutation(
    (entryId: string, body: { amount: number; reason: string }) =>
      api.projects.correctEntry(projectId, entryId, body),
    (next) => {
      setCorrectingId(null);
      applied(next);
    },
  );
  const unlink = useMutation(
    (grievanceId: string) => api.projects.unlinkGrievance(projectId, grievanceId),
    applied,
  );
  const remove = useMutation(
    () => api.projects.remove(projectId),
    () => {
      onChanged?.();
      onClose();
    },
  );

  const open = (next: Panel) => {
    decide.clearError();
    addEntry.clearError();
    recordProgress.clearError();
    setPanel(next);
  };

  const closed = record ? record.stage === 'completed' || record.stage === 'rejected' : false;

  // Everything the server will currently accept, with the step that moves the
  // work forward put first. Hold and reject take a work off the path, so they
  // are kept apart at the end.
  const operations: Panel[] = record
    ? [
        ...record.steps.entryKinds.map((kind): Panel => ({ type: 'entry', kind })),
        ...(record.steps.canRecordProgress ? [{ type: 'progress' } as Panel] : []),
        ...record.steps.actions
          .filter((action) => action !== 'hold' && action !== 'reject')
          .map((action): Panel => ({ type: 'decision', action })),
      ].sort((a, b) => Number(isPrimary(b, record)) - Number(isPrimary(a, record)))
    : [];
  const sideActions = record
    ? record.steps.actions.filter((action) => action === 'hold' || action === 'reject')
    : [];

  const operationLabel = (operation: Panel): string => {
    if (operation.type === 'decision') return say(ACTION_COPY[operation.action].button, isEnglish);
    if (operation.type === 'progress') return isEnglish ? 'Record progress' : 'प्रगती नोंदवा';
    if (operation.kind === 'estimate' && record?.finance.estimated !== null) {
      return isEnglish ? 'Revise cost estimate' : 'खर्चाचा अंदाज सुधारा';
    }
    if (operation.kind === 'approved' && record?.stage !== 'budget_requested') {
      return isEnglish ? 'Revise approved amount' : 'मंजूर रक्कम सुधारा';
    }
    return say(ENTRY_BUTTON[operation.kind], isEnglish);
  };

  const operationKey = (operation: Panel): string =>
    operation.type === 'decision'
      ? `decision:${operation.action}`
      : operation.type === 'entry'
        ? `entry:${operation.kind}`
        : 'progress';

  const assetLabel = (() => {
    if (!record?.assetType) return null;
    const known = vocabulary?.assetTypes.find((item) => item.code === record.assetType);
    return known ? pick(known.label, known.labelMr, isEnglish) : record.assetType;
  })();

  return (
    <div
      className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-start justify-center p-3 sm:p-6 overflow-y-auto"
      role="dialog"
      aria-modal="true"
      aria-label={isEnglish ? 'Development work' : 'विकास काम'}
    >
      <div className="w-full max-w-3xl bg-white rounded-2xl border border-slate-200 shadow-xl my-auto">
        <header className="p-4 border-b border-slate-100 flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-1.5">
            <h2 className="text-sm font-extrabold text-govblue-900 leading-snug">
              {record
                ? pick(record.name, record.nameMr, isEnglish)
                : isEnglish
                  ? 'Loading the work'
                  : 'काम लोड होत आहे'}
            </h2>
            {record && (
              <div className="flex flex-wrap items-center gap-1.5">
                <StageChip
                  stage={record.stage}
                  label={record.stageLabel}
                  labelMr={record.stageLabelMr}
                  isEnglish={isEnglish}
                />
                {record.status === 'Delayed' && (
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide border ${STATUS_CHIP.Delayed}`}
                  >
                    {pick(record.status, record.statusMr, isEnglish)}
                  </span>
                )}
                <span className="text-[11px] text-slate-400 font-mono">{record.id}</span>
              </div>
            )}
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

        <div className="p-4 space-y-5 max-h-[75vh] overflow-y-auto">
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
              {/* What and where */}
              <section className="space-y-2">
                <p className="text-xs text-slate-600 leading-relaxed">
                  {pick(record.description, record.descriptionMr, isEnglish)}
                </p>
                <p className="text-[11px] text-slate-500 flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="inline-flex items-center gap-1">
                    <MapPin size={11} className="text-slate-400" />
                    {pick(record.location, record.locationMr, isEnglish)} ·{' '}
                    {isEnglish ? `Ward ${record.ward}` : `वॉर्ड ${record.ward}`}
                  </span>
                  {record.expectedCompletion && (
                    <span className="inline-flex items-center gap-1">
                      <CalendarDays size={11} className="text-slate-400" />
                      {isEnglish ? 'Expected by ' : 'अपेक्षित पूर्तता '}
                      {formatDate(record.expectedCompletion, isEnglish)}
                    </span>
                  )}
                  {record.residentsAffected > 0 && (
                    <span className="inline-flex items-center gap-1">
                      <Users size={11} className="text-slate-400" />
                      {isEnglish
                        ? `Asked for by ${record.residentsAffected} resident(s)`
                        : `${record.residentsAffected} रहिवाशांची मागणी`}
                    </span>
                  )}
                  {record.sabhaMeetingId && (
                    <span className="inline-flex items-center gap-1">
                      <Landmark size={11} className="text-slate-400" />
                      {isEnglish ? 'Decided at a Gram Sabha' : 'ग्रामसभेत निर्णय'}
                    </span>
                  )}
                </p>
              </section>

              {/* Where it is */}
              <section className="space-y-3">
                {vocabulary ? (
                  <StageTrack
                    stages={vocabulary.stages}
                    stageIndex={record.stageIndex}
                    isEnglish={isEnglish}
                  />
                ) : null}

                {record.stage === 'rejected' && (
                  <div className="rounded-lg border border-slate-300 bg-slate-50 p-3 text-xs text-slate-700 leading-relaxed">
                    <strong className="block text-slate-800">
                      {isEnglish ? 'Not approved by the Panchayat' : 'पंचायतीने मंजूर केले नाही'}
                    </strong>
                    {record.decisionNote}
                  </div>
                )}
                {record.stage === 'on_hold' && (
                  <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 leading-relaxed">
                    <strong className="block">{isEnglish ? 'On hold' : 'स्थगित'}</strong>
                    {record.events.length
                      ? pick(
                          record.events[record.events.length - 1].note ?? '',
                          record.events[record.events.length - 1].noteMr,
                          isEnglish,
                        )
                      : null}
                  </div>
                )}
                {record.stage !== 'rejected' && record.stage !== 'on_hold' && record.decisionNote && (
                  <p className="text-[11px] text-slate-500 leading-relaxed">
                    <strong className="text-slate-600">
                      {isEnglish ? 'Panchayat’s decision: ' : 'पंचायतीचा निर्णय: '}
                    </strong>
                    {record.decisionNote}
                  </p>
                )}
                {record.daysInStage !== null && !closed && record.stage !== 'in_progress' && (
                  <p className="text-[11px] text-slate-400">
                    {isEnglish
                      ? `At this stage for ${record.daysInStage} day(s).`
                      : `या टप्प्यावर ${record.daysInStage} दिवस.`}
                  </p>
                )}
              </section>

              <FlagList flags={record.flags} isEnglish={isEnglish} />

              {/* What an officer does next */}
              {canAct && (
                <section className="space-y-3">
                  <div>
                    <h3 className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      {isEnglish ? 'Next step' : 'पुढचा टप्पा'}
                    </h3>
                    <p className="text-xs text-slate-700 font-semibold mt-0.5">
                      {say(nextHint(record), isEnglish)}
                    </p>
                  </div>

                  {!panel && (operations.length > 0 || sideActions.length > 0) && (
                    <div className="flex flex-wrap gap-2">
                      {operations.map((operation) => (
                        <button
                          key={operationKey(operation)}
                          type="button"
                          onClick={() => open(operation)}
                          className={
                            isPrimary(operation, record)
                              ? 'px-3.5 py-2 rounded-lg bg-govnavy hover:bg-govblue-700 text-white text-xs font-bold transition-colors'
                              : 'px-3.5 py-2 rounded-lg border border-slate-300 hover:bg-slate-50 text-slate-700 text-xs font-bold transition-colors'
                          }
                        >
                          {operationLabel(operation)}
                        </button>
                      ))}
                      {record.stage === 'in_progress' && (
                        <button
                          type="button"
                          disabled={setDelayed.saving}
                          onClick={() => setDelayed.run(record.status !== 'Delayed')}
                          className="px-3.5 py-2 rounded-lg border border-slate-300 hover:bg-slate-50 disabled:opacity-60 text-slate-700 text-xs font-bold transition-colors"
                        >
                          {record.status === 'Delayed'
                            ? isEnglish
                              ? 'Back on schedule'
                              : 'वेळापत्रकानुसार'
                            : isEnglish
                              ? 'Mark as delayed'
                              : 'विलंब झाल्याची नोंद'}
                        </button>
                      )}
                      {sideActions.map((action) => (
                        <button
                          key={action}
                          type="button"
                          onClick={() => open({ type: 'decision', action })}
                          className={`px-3.5 py-2 rounded-lg border text-xs font-bold transition-colors ${
                            action === 'reject'
                              ? 'border-rose-200 hover:bg-rose-50 text-rose-700'
                              : 'border-amber-200 hover:bg-amber-50 text-amber-800'
                          }`}
                        >
                          {say(ACTION_COPY[action].button, isEnglish)}
                        </button>
                      ))}
                    </div>
                  )}
                  {setDelayed.error && <ErrorNotice message={setDelayed.error} />}

                  {panel?.type === 'decision' && (
                    <DecisionForm
                      key={panel.action}
                      action={panel.action}
                      isEnglish={isEnglish}
                      saving={decide.saving}
                      error={decide.error}
                      onCancel={() => setPanel(null)}
                      onSubmit={(body) => decide.run(panel.action, body)}
                    />
                  )}
                  {panel?.type === 'entry' && (
                    <EntryForm
                      key={panel.kind}
                      kind={panel.kind}
                      record={record}
                      vocabulary={vocabulary}
                      isEnglish={isEnglish}
                      saving={addEntry.saving}
                      error={addEntry.error}
                      onCancel={() => setPanel(null)}
                      onSubmit={(entry) => addEntry.run(entry)}
                    />
                  )}
                  {panel?.type === 'progress' && (
                    <ProgressForm
                      record={record}
                      isEnglish={isEnglish}
                      saving={recordProgress.saving}
                      error={recordProgress.error}
                      onCancel={() => setPanel(null)}
                      onSubmit={(body) => recordProgress.run(body)}
                    />
                  )}
                </section>
              )}

              {/* Money and work, side by side */}
              <section className="rounded-xl border border-slate-200 p-4 space-y-4">
                <MoneyStrip money={record.finance} isEnglish={isEnglish} />
                {record.finance.approved !== null && (
                  <>
                    <ProgressPair
                      physicalPercent={record.physicalPercent}
                      financialPercent={record.finance.financialPercent}
                      physicalDetail={
                        record.unitsPlanned !== null
                          ? isEnglish
                            ? `${record.unitsDone} of ${record.unitsPlanned} ${record.unitLabel ?? 'units'}`
                            : `${record.unitsPlanned} पैकी ${record.unitsDone} ${record.unitLabelMr ?? record.unitLabel ?? 'घटक'}`
                          : null
                      }
                      isEnglish={isEnglish}
                    />
                    <p className="text-xs text-slate-700 tabular-nums">
                      <strong>
                        {isEnglish
                          ? `Remaining ${rupees(record.finance.remaining)}`
                          : `शिल्लक निधी ${rupees(record.finance.remaining)}`}
                      </strong>
                      <span className="text-[11px] text-slate-500">
                        {isEnglish
                          ? ` of ${rupees(record.finance.approved)} approved — ${rupees(record.finance.balance)} in hand, ${rupees(record.finance.awaiting)} still to arrive`
                          : ` (मंजूर ${rupees(record.finance.approved)} पैकी) — ${rupees(record.finance.balance)} हातात, ${rupees(record.finance.awaiting)} येणे बाकी`}
                        {record.fundingSourceLabel &&
                          ` · ${pick(record.fundingSourceLabel, record.fundingSourceLabelMr, isEnglish)}`}
                      </span>
                    </p>
                  </>
                )}
                {record.stage === 'completed' && assetLabel && (
                  <p className="text-[11px] text-govgreen font-semibold">
                    {isEnglish
                      ? `Added to the asset register and the map: ${record.unitsPlanned ? `${record.unitsDone} ` : ''}${assetLabel.toLowerCase()}.`
                      : `मालमत्ता नोंदवहीत व नकाशावर जोडले: ${record.unitsPlanned ? `${record.unitsDone} ` : ''}${assetLabel}.`}
                  </p>
                )}
              </section>

              {/* The ledger */}
              <section className="space-y-2">
                <h3 className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  {isEnglish ? 'Money, entry by entry' : 'निधीच्या नोंदी'}
                </h3>
                {record.entries.length === 0 ? (
                  <p className="text-xs text-slate-400">
                    {isEnglish
                      ? 'No estimate, request or payment has been recorded yet.'
                      : 'अद्याप अंदाज, मागणी किंवा खर्चाची नोंद नाही.'}
                  </p>
                ) : (
                  <div className="overflow-x-auto border border-slate-200 rounded-lg">
                    <table className="w-full text-[11px] text-left">
                      <thead className="bg-slate-50 text-slate-500 uppercase tracking-wide text-[9px]">
                        <tr>
                          <th className="px-3 py-2 font-bold">{isEnglish ? 'Date' : 'दिनांक'}</th>
                          <th className="px-3 py-2 font-bold">{isEnglish ? 'Entry' : 'नोंद'}</th>
                          <th className="px-3 py-2 font-bold text-right">
                            {isEnglish ? 'Amount' : 'रक्कम'}
                          </th>
                          <th className="px-3 py-2 font-bold">
                            {isEnglish ? 'Reference and note' : 'संदर्भ व टीप'}
                          </th>
                          <th className="px-3 py-2 font-bold">{isEnglish ? 'By' : 'नोंदवणारा'}</th>
                          {canAct && <th className="px-3 py-2" aria-label={isEnglish ? 'Correct' : 'दुरुस्ती'} />}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {ledger.map((entry) => {
                          const isCorrection = entry.correctsId !== null;
                          return (
                            <React.Fragment key={entry.id}>
                              <tr className={`align-top ${isCorrection ? 'bg-amber-50/40' : ''}`}>
                                <td className="px-3 py-2 whitespace-nowrap text-slate-600">
                                  {isCorrection
                                    ? // When the correction was made; the entry's own
                                      // date is on the line above.
                                      formatDate(entry.createdAt, isEnglish)
                                    : formatDate(entry.entryDate, isEnglish)}
                                </td>
                                <td className="px-3 py-2 font-bold text-slate-700">
                                  {isCorrection ? (
                                    <span className="text-amber-900">
                                      ↳ {isEnglish ? 'Correction' : 'दुरुस्ती'}
                                    </span>
                                  ) : (
                                    pick(entry.kindLabel, entry.kindLabelMr, isEnglish)
                                  )}
                                </td>
                                <td className="px-3 py-2 text-right font-bold tabular-nums text-slate-800 whitespace-nowrap">
                                  {isCorrection ? (
                                    <span className="text-amber-900">
                                      {entry.amount < 0 ? '−' : '+'}
                                      {rupees(Math.abs(entry.amount))}
                                    </span>
                                  ) : entry.correctedTo !== null ? (
                                    <>
                                      <s className="text-slate-400 font-semibold">{rupees(entry.amount)}</s>
                                      <span className="block">{rupees(entry.correctedTo)}</span>
                                    </>
                                  ) : (
                                    rupees(entry.amount)
                                  )}
                                </td>
                                <td className="px-3 py-2 text-slate-600">
                                  {isCorrection
                                    ? entry.note
                                    : [
                                        entry.reference,
                                        entry.fundingSourceLabel
                                          ? pick(entry.fundingSourceLabel, entry.fundingSourceLabelMr, isEnglish)
                                          : null,
                                        entry.note,
                                      ]
                                        .filter(Boolean)
                                        .join(' · ') || '—'}
                                </td>
                                <td className="px-3 py-2 text-slate-500 whitespace-nowrap">
                                  {entry.createdByName ?? '—'}
                                </td>
                                {canAct && (
                                  <td className="px-3 py-2 text-right whitespace-nowrap">
                                    {entry.canCorrect && correctingId !== entry.id && (
                                      <button
                                        type="button"
                                        onClick={() => {
                                          correct.clearError();
                                          setCorrectingId(entry.id);
                                        }}
                                        className="text-[11px] font-bold text-govnavy hover:underline"
                                      >
                                        {isEnglish ? 'Correct' : 'दुरुस्त करा'}
                                      </button>
                                    )}
                                  </td>
                                )}
                              </tr>
                              {canAct && correctingId === entry.id && (
                                <tr>
                                  <td colSpan={6} className="px-3 py-3">
                                    <CorrectionForm
                                      entry={entry}
                                      isEnglish={isEnglish}
                                      saving={correct.saving}
                                      error={correct.error}
                                      onCancel={() => setCorrectingId(null)}
                                      onSubmit={(body) => correct.run(entry.id, body)}
                                    />
                                  </td>
                                </tr>
                              )}
                            </React.Fragment>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
                <p className="text-[10px] text-slate-400 leading-relaxed">
                  {isEnglish
                    ? 'Entries are never overtyped or deleted. A revised estimate or approval is a new line, and the latest dated one stands. A receipt or payment recorded wrongly is put right with “Correct”, which adds a line saying what it should have been and why. This is budget tracking, not accounts: there are no vouchers behind these figures and nothing here is reconciled with a bank or PFMS.'
                    : 'नोंदी कधीही खोडल्या किंवा हटवल्या जात नाहीत. सुधारित अंदाज किंवा मंजुरी ही नवीन ओळ असते आणि सर्वात अलीकडील दिनांकाची नोंद ग्राह्य धरली जाते. चुकीची नोंदवलेली प्राप्ती किंवा खर्च “दुरुस्त करा” ने सुधारला जातो; त्यात योग्य रक्कम व कारण सांगणारी ओळ जोडली जाते. हे निधीचे निरीक्षण आहे, लेखे नाहीत: या आकड्यांमागे व्हाउचर नाहीत आणि बँक किंवा PFMS शी ताळमेळ घातलेला नाही.'}
                </p>
              </section>

              {/* Who asked — officers only; a resident is given the count above */}
              {canAct && record.grievances.length > 0 && (
                <section className="space-y-2">
                  <h3 className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    {isEnglish
                      ? `Complaints behind this work (${record.grievances.length})`
                      : `या कामामागील तक्रारी (${record.grievances.length})`}
                  </h3>
                  {unlink.error && <ErrorNotice message={unlink.error} />}
                  <ul className="divide-y divide-slate-100 border border-slate-200 rounded-lg p-0 list-none">
                    {record.grievances.map((grievance) => (
                      <li key={grievance.id} className="p-3 flex items-start justify-between gap-3">
                        <div className="min-w-0 space-y-0.5">
                          <p className="text-xs font-bold text-slate-800 leading-snug">
                            {pick(grievance.title, grievance.titleMr, isEnglish)}
                          </p>
                          <p className="text-[11px] text-slate-500">
                            {grievance.citizenName} · {formatDate(grievance.submittedDate, isEnglish)} ·{' '}
                            {grievance.status}
                          </p>
                          {grievance.citizenFeedback === 'confirmed' && (
                            <p className="text-[11px] text-govgreen font-semibold">
                              {isEnglish ? 'Confirmed by the resident' : 'रहिवाशाने खात्री केली'}
                            </p>
                          )}
                          {grievance.citizenFeedback === 'reopened' && (
                            <p className="text-[11px] text-rose-700 font-semibold flex items-start gap-1">
                              <AlertTriangle size={11} className="mt-0.5 flex-shrink-0" />
                              {isEnglish ? 'Resident says it is not done: ' : 'रहिवाशाच्या मते काम झालेले नाही: '}
                              {grievance.feedbackNote}
                            </p>
                          )}
                        </div>
                        {!closed && (
                          <button
                            type="button"
                            disabled={unlink.saving}
                            onClick={() => unlink.run(grievance.id)}
                            className="text-[11px] font-bold text-slate-500 hover:text-rose-700 hover:underline flex-shrink-0 disabled:opacity-60"
                          >
                            {isEnglish ? 'Unlink' : 'वेगळी करा'}
                          </button>
                        )}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {/* History */}
              <section className="space-y-2">
                <h3 className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  {isEnglish ? 'History on record' : 'नोंदवलेला इतिहास'}
                </h3>
                <WorkHistory events={record.events} vocabulary={vocabulary} isEnglish={isEnglish} />
              </section>

              {/* Removing the record */}
              {canAct && (
                <section className="pt-3 border-t border-slate-100">
                  {remove.error && <ErrorNotice message={remove.error} />}
                  {confirmDelete ? (
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[11px] text-rose-700 font-semibold">
                        {isEnglish
                          ? 'This removes the work, its ledger and its history. Linked complaints are kept.'
                          : 'यामुळे काम, त्याच्या निधीच्या नोंदी व इतिहास हटेल. जोडलेल्या तक्रारी राहतील.'}
                      </span>
                      <button
                        type="button"
                        disabled={remove.saving}
                        onClick={() => remove.run()}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-700 hover:bg-rose-800 disabled:opacity-60 text-white text-[11px] font-bold transition-colors"
                      >
                        {remove.saving && <Loader2 size={11} className="animate-spin" />}
                        {isEnglish ? 'Confirm delete' : 'हटवण्याची खात्री'}
                      </button>
                      <button
                        type="button"
                        onClick={() => setConfirmDelete(false)}
                        className="text-[11px] font-bold text-slate-500 hover:underline"
                      >
                        {isEnglish ? 'Cancel' : 'रद्द करा'}
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setConfirmDelete(true)}
                      className="inline-flex items-center gap-1.5 text-[11px] font-bold text-slate-400 hover:text-rose-700 transition-colors"
                    >
                      <Trash2 size={12} />
                      {isEnglish ? 'Delete this record' : 'ही नोंद हटवा'}
                    </button>
                  )}
                </section>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};
