/**
 * The works register — every development work in this Gram Panchayat, from a
 * proposal nobody has looked at yet to a finished work a resident has confirmed.
 *
 * This screen used to show a name, a percentage and two totals per project, and
 * an officer changed the totals by typing over them. A work now has a stage, a
 * ledger of dated money entries and a history, and all three are written by the
 * detail panel one step at a time. Nothing on this page edits a figure in
 * place: the "spent" box is gone because spending is a dated entry with a
 * reference, not a number somebody last typed.
 *
 * Two ways in. A new work is opened as a proposal — usually from the complaints
 * screen, out of the complaints that asked for it — so that its approval and
 * its money are on the record from the start. A work that was already under way
 * before this register existed is entered from its two totals, which become
 * opening entries in its ledger.
 *
 * Chart colours #2547a8 / #138808 are this project's validated pair for
 * colour-vision deficiency. Sanctioned and spent share a single ₹ lakh axis:
 * they are the same quantity measured twice, and a second axis would let any
 * pair of bars be scaled to look level regardless of the actual shortfall.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, CalendarDays, Loader2, MapPin, Plus, Users, X } from 'lucide-react';
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

import { api, type Project, type ProjectStage, type Village } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useMutation, useQuery } from '../lib/useApi';
import { EmptyState, ErrorNotice } from './schemes/SchemeBits';
import { ProposalForm } from './works/ProposalForm';
import { WorkDetail } from './works/WorkDetail';
import {
  STATUS_BAR,
  STATUS_CHIP,
  StageBar,
  StageChip,
  formatDate,
  pick,
  rupees,
  warningCount,
} from './works/WorkBits';

// Validated for colour-vision deficiency — see the note at the top of this file.
const SERIES_SANCTIONED = '#2547a8';
const SERIES_SPENT = '#138808';

const INPUT =
  'w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-govnavy/25';

// ─── Grouping the ten stages into what an officer is waiting on ─────────────

type Group = 'all' | 'decision' | 'money' | 'progress' | 'done' | 'aside';

const GROUP_OF: Record<ProjectStage, Exclude<Group, 'all'>> = {
  proposed: 'decision',
  verified: 'decision',
  approved: 'money',
  budget_requested: 'money',
  budget_approved: 'money',
  funds_received: 'money',
  in_progress: 'progress',
  completed: 'done',
  rejected: 'aside',
  on_hold: 'aside',
};

const GROUPS: { key: Group; en: string; mr: string }[] = [
  { key: 'all', en: 'All', mr: 'सर्व' },
  { key: 'decision', en: 'Awaiting a decision', mr: 'निर्णयाच्या प्रतीक्षेत' },
  { key: 'money', en: 'Awaiting money', mr: 'निधीच्या प्रतीक्षेत' },
  { key: 'progress', en: 'In progress', mr: 'काम सुरू' },
  { key: 'done', en: 'Completed', mr: 'पूर्ण' },
  { key: 'aside', en: 'Held or not approved', mr: 'स्थगित / नामंजूर' },
];

const lakhs = (value: number, isEnglish: boolean) =>
  isEnglish ? `₹${(value / 100000).toFixed(2)} L` : `₹${(value / 100000).toFixed(2)} लाख`;

/** One line saying where a work's money stands, at whatever point it has reached. */
const moneyLine = (p: Project, isEnglish: boolean): string => {
  const { finance } = p;
  if (finance.approved !== null) {
    return isEnglish
      ? `${rupees(finance.spent)} spent of ${rupees(finance.approved)} approved`
      : `${rupees(finance.approved)} मंजूर, त्यापैकी ${rupees(finance.spent)} खर्च`;
  }
  if (finance.requested !== null) {
    return isEnglish
      ? `${rupees(finance.requested)} requested, not yet approved`
      : `${rupees(finance.requested)} ची मागणी, अद्याप मंजुरी नाही`;
  }
  if (finance.estimated !== null) {
    return isEnglish
      ? `Estimated at ${rupees(finance.estimated)}`
      : `अंदाजित खर्च ${rupees(finance.estimated)}`;
  }
  return isEnglish ? 'No cost estimate recorded yet' : 'अद्याप खर्चाचा अंदाज नोंदवलेला नाही';
};

// ─── Registering a work that was already under way ──────────────────────────

const RegisterModal: React.FC<{
  isEnglish: boolean;
  village: Village | null;
  onClose: () => void;
  onRegistered: () => void;
}> = ({ isEnglish, village, onClose, onRegistered }) => {
  const [name, setName] = useState('');
  const [nameMr, setNameMr] = useState('');
  const [budget, setBudget] = useState('');
  const [utilized, setUtilized] = useState('');
  const [progress, setProgress] = useState('0');
  const [ward, setWard] = useState('1');
  const [location, setLocation] = useState('');
  const [description, setDescription] = useState('');
  // The village's own recorded centre is a real coordinate, offered as a
  // starting point the officer is expected to move to the actual work site.
  const [latitude, setLatitude] = useState(village?.latitude != null ? String(village.latitude) : '');
  const [longitude, setLongitude] = useState(
    village?.longitude != null ? String(village.longitude) : '',
  );
  const [startDate, setStartDate] = useState('');
  const [expectedCompletion, setExpectedCompletion] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  const register = useMutation(
    (body: Parameters<typeof api.projects.create>[0]) => api.projects.create(body),
    onRegistered,
  );

  const wardOptions = village?.wardCount
    ? Array.from({ length: village.wardCount }, (_, i) => i + 1)
    : null;

  const submit = () => {
    const sanctioned = Number(budget);
    const spent = utilized.trim() === '' ? 0 : Number(utilized);
    const lat = Number(latitude);
    const lng = Number(longitude);

    if (!Number.isFinite(sanctioned) || sanctioned <= 0) {
      setFormError(
        isEnglish ? 'Enter the sanctioned amount in rupees.' : 'मंजूर रक्कम रुपयांमध्ये नोंदवा.',
      );
      return;
    }
    if (!Number.isFinite(spent) || spent < 0 || spent > sanctioned) {
      setFormError(
        isEnglish
          ? 'The amount spent so far cannot be more than the sanctioned amount.'
          : 'आतापर्यंतचा खर्च मंजूर रकमेपेक्षा जास्त असू शकत नाही.',
      );
      return;
    }
    if (latitude.trim() === '' || longitude.trim() === '' || !Number.isFinite(lat) || !Number.isFinite(lng)) {
      setFormError(
        isEnglish
          ? 'Enter the site latitude and longitude — the map plots this work at those coordinates.'
          : 'कामाच्या ठिकाणाचे अक्षांश व रेखांश नोंदवा — नकाशावर काम याच ठिकाणी दाखवले जाईल.',
      );
      return;
    }
    setFormError(null);

    register.run({
      name: name.trim(),
      // Marathi is sent only when actually written; the server falls back to
      // the English rather than this form copying it across and calling it a
      // translation.
      nameMr: nameMr.trim() || undefined,
      description: description.trim(),
      progress: Number(progress) || 0,
      budget: sanctioned,
      utilized: spent,
      status: 'Ongoing',
      ward: Number(ward),
      location: location.trim(),
      latitude: lat,
      longitude: lng,
      startDate: startDate || undefined,
      expectedCompletion: expectedCompletion || undefined,
    });
  };

  return (
    <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-start justify-center p-4 overflow-y-auto">
      <div
        role="dialog"
        aria-modal="true"
        aria-label={isEnglish ? 'Register a work already under way' : 'आधीपासून सुरू असलेले काम नोंदवा'}
        className="w-full max-w-xl my-8 bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-2xl"
      >
        <div className="p-4 border-b border-slate-200 bg-slate-50 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-xs font-bold tracking-widest m-0 uppercase text-slate-500">
              {isEnglish ? 'Register a work already under way' : 'आधीपासून सुरू असलेले काम नोंदवा'}
            </h2>
            <p className="text-[11px] text-slate-500 m-0 mt-1 leading-relaxed normal-case">
              {isEnglish
                ? 'For a work that was sanctioned and started before this register. Its two totals become opening entries in its ledger. A new work should be opened as a proposal instead.'
                : 'या नोंदवहीपूर्वी मंजूर होऊन सुरू झालेल्या कामासाठी. त्याच्या दोन रकमा निधीच्या नोंदवहीत प्रारंभिक नोंदी होतात. नवीन काम प्रस्ताव म्हणून उघडावे.'}
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label={isEnglish ? 'Close' : 'बंद करा'}
            className="p-1 rounded-lg hover:bg-slate-200 text-slate-500 hover:text-slate-800 transition-colors flex-shrink-0"
          >
            <X size={16} />
          </button>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
          className="p-5 space-y-4"
        >
          {register.error && <ErrorNotice message={register.error} />}
          {formError && <ErrorNotice message={formError} />}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label htmlFor="p-name" className="block text-xs font-bold text-slate-600">
                {isEnglish ? 'Name of the work (English)' : 'कामाचे नाव (इंग्रजी)'}
              </label>
              <input id="p-name" required value={name} onChange={(e) => setName(e.target.value)} className={INPUT} />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="p-name-mr" className="block text-xs font-bold text-slate-600">
                {isEnglish ? 'Name of the work (Marathi)' : 'कामाचे नाव (मराठी)'}
              </label>
              <input
                id="p-name-mr"
                value={nameMr}
                onChange={(e) => setNameMr(e.target.value)}
                placeholder={isEnglish ? 'Optional' : 'ऐच्छिक'}
                className={INPUT}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <label htmlFor="p-budget" className="block text-xs font-bold text-slate-600">
                {isEnglish ? 'Sanctioned (₹)' : 'मंजूर रक्कम (₹)'}
              </label>
              <input
                id="p-budget"
                type="number"
                min={1}
                required
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
                className={INPUT}
              />
              {Number(budget) > 0 && (
                <p className="text-[10px] text-slate-400 m-0 tabular-nums">= {rupees(Number(budget))}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <label htmlFor="p-utilized" className="block text-xs font-bold text-slate-600">
                {isEnglish ? 'Spent so far (₹)' : 'आतापर्यंतचा खर्च (₹)'}
              </label>
              <input
                id="p-utilized"
                type="number"
                min={0}
                value={utilized}
                onChange={(e) => setUtilized(e.target.value)}
                placeholder="0"
                className={INPUT}
              />
              {Number(utilized) > 0 && (
                <p className="text-[10px] text-slate-400 m-0 tabular-nums">= {rupees(Number(utilized))}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <label htmlFor="p-progress" className="block text-xs font-bold text-slate-600">
                {isEnglish ? 'Work done (%)' : 'झालेले काम (%)'}
              </label>
              <input
                id="p-progress"
                type="number"
                min={0}
                max={99}
                value={progress}
                onChange={(e) => setProgress(e.target.value)}
                className={INPUT}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <label htmlFor="p-ward" className="block text-xs font-bold text-slate-600">
                {isEnglish ? 'Ward' : 'वॉर्ड'}
              </label>
              {wardOptions ? (
                <select id="p-ward" value={ward} onChange={(e) => setWard(e.target.value)} className={INPUT}>
                  {wardOptions.map((n) => (
                    <option key={n} value={String(n)}>
                      {n}
                    </option>
                  ))}
                </select>
              ) : (
                // No village on this session (an administrator), so the ward
                // count is unknown — take a number rather than show a made-up
                // list of wards.
                <input
                  id="p-ward"
                  type="number"
                  min={1}
                  value={ward}
                  onChange={(e) => setWard(e.target.value)}
                  className={INPUT}
                />
              )}
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <label htmlFor="p-location" className="block text-xs font-bold text-slate-600">
                {isEnglish ? 'Where' : 'ठिकाण'}
              </label>
              <input
                id="p-location"
                required
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                className={INPUT}
              />
            </div>
          </div>

          {/* Coordinates are typed, not generated. An older form produced a
              random point near the village centre, which put works on the map
              at places they are not. */}
          <fieldset className="border border-slate-200 rounded-lg p-3 space-y-2">
            <legend className="px-1 text-[11px] font-bold text-slate-600">
              {isEnglish ? 'Site coordinates' : 'कामाच्या ठिकाणाचे निर्देशांक'}
            </legend>
            <div className="grid grid-cols-2 gap-4">
              <input
                type="number"
                step="any"
                required
                aria-label={isEnglish ? 'Latitude' : 'अक्षांश'}
                placeholder={isEnglish ? 'Latitude' : 'अक्षांश'}
                value={latitude}
                onChange={(e) => setLatitude(e.target.value)}
                className={INPUT}
              />
              <input
                type="number"
                step="any"
                required
                aria-label={isEnglish ? 'Longitude' : 'रेखांश'}
                placeholder={isEnglish ? 'Longitude' : 'रेखांश'}
                value={longitude}
                onChange={(e) => setLongitude(e.target.value)}
                className={INPUT}
              />
            </div>
            <p className="text-[10px] text-slate-500 m-0 leading-relaxed">
              {village?.latitude != null
                ? isEnglish
                  ? `Pre-filled with the recorded centre of ${village.name}. Change it to the actual work site — the map plots this work at exactly these coordinates.`
                  : `${village.nameMr} च्या नोंदवलेल्या मध्यबिंदूने भरलेले. प्रत्यक्ष कामाच्या ठिकाणानुसार बदला — नकाशावर काम याच निर्देशांकांवर दाखवले जाईल.`
                : isEnglish
                  ? 'The map plots this work at exactly these coordinates.'
                  : 'नकाशावर काम याच निर्देशांकांवर दाखवले जाईल.'}
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
                className={INPUT}
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
                className={INPUT}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="p-desc" className="block text-xs font-bold text-slate-600">
              {isEnglish ? 'Description' : 'वर्णन'}
            </label>
            <textarea
              id="p-desc"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className={`${INPUT} resize-y`}
            />
          </div>

          <div className="pt-3 border-t border-slate-100 flex items-center justify-end gap-2.5">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg border border-slate-300 hover:bg-slate-50 text-slate-600 text-xs font-bold transition-colors"
            >
              {isEnglish ? 'Cancel' : 'रद्द करा'}
            </button>
            <button
              type="submit"
              disabled={register.saving}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-govnavy hover:bg-govblue-700 disabled:opacity-60 text-white text-xs font-bold transition-colors shadow-sm"
            >
              {register.saving && <Loader2 size={13} className="animate-spin" />}
              {isEnglish ? 'Register the work' : 'काम नोंदवा'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// ─── The screen ─────────────────────────────────────────────────────────────

export const DevelopmentProjects: React.FC<{
  /** A work to open straight away — set when arriving from a complaint. */
  focusId?: string | null;
  onFocusHandled?: () => void;
}> = ({ focusId, onFocusHandled }) => {
  const { t, i18n } = useTranslation();
  const isEnglish = i18n.language === 'en';
  const { isOfficer } = useAuth();

  const projects = useQuery<Project[]>(() => api.projects.list(), []);
  // Used for the ward list and the starting coordinates on the forms. Null for
  // an administrator, who is not attached to one village.
  const village = useQuery<Village | null>(() => api.villages.current(), []);

  const [group, setGroup] = useState<Group>('all');
  const [openId, setOpenId] = useState<string | null>(focusId ?? null);
  const [proposing, setProposing] = useState(false);
  const [registering, setRegistering] = useState(false);

  useEffect(() => {
    if (focusId) {
      setOpenId(focusId);
      onFocusHandled?.();
    }
  }, [focusId, onFocusHandled]);

  const rows = useMemo(() => projects.data ?? [], [projects.data]);

  const counts = useMemo(() => {
    const out: Record<Group, number> = {
      all: rows.length, decision: 0, money: 0, progress: 0, done: 0, aside: 0,
    };
    for (const p of rows) out[GROUP_OF[p.stage] ?? 'aside'] += 1;
    return out;
  }, [rows]);

  const needLooking = useMemo(
    () => rows.filter((p) => warningCount(p.flags) > 0).length,
    [rows],
  );

  // What needs a person first: works a rule has flagged, then open ones, then
  // the finished and the refused.
  const shown = useMemo(() => {
    const picked = group === 'all' ? rows : rows.filter((p) => GROUP_OF[p.stage] === group);
    const closed = (p: Project) => (p.stage === 'completed' || p.stage === 'rejected' ? 1 : 0);
    return [...picked].sort(
      (a, b) =>
        closed(a) - closed(b) ||
        warningCount(b.flags) - warningCount(a.flags) ||
        a.ward - b.ward,
    );
  }, [rows, group]);

  // Rupees converted to lakh here, in front of the reader, because the record
  // stores rupees and the axis is labelled in lakh. Only works with money
  // sanctioned: a proposal would sit in the chart as an empty pair of bars.
  const chartData = useMemo(
    () =>
      shown
        .filter((p) => p.budget > 0)
        .map((p) => ({
          name: pick(p.name, p.nameMr, isEnglish).slice(0, 18),
          fullName: pick(p.name, p.nameMr, isEnglish),
          sanctioned: Number((p.budget / 100000).toFixed(2)),
          spent: Number((p.utilized / 100000).toFixed(2)),
        })),
    [shown, isEnglish],
  );

  const totals = useMemo(
    () =>
      shown
        .filter((p) => p.stage !== 'rejected')
        .reduce(
          (acc, p) => ({ budget: acc.budget + p.budget, utilized: acc.utilized + p.utilized }),
          { budget: 0, utilized: 0 },
        ),
    [shown],
  );

  const tiles = [
    { label: isEnglish ? 'Awaiting a decision' : 'निर्णयाच्या प्रतीक्षेत', value: counts.decision, border: 'border-slate-400' },
    { label: isEnglish ? 'Awaiting money' : 'निधीच्या प्रतीक्षेत', value: counts.money, border: 'border-govsaffron' },
    { label: isEnglish ? 'In progress' : 'काम सुरू', value: counts.progress, border: 'border-govblue-600' },
    { label: isEnglish ? 'Completed' : 'पूर्ण', value: counts.done, border: 'border-govgreen' },
  ];

  return (
    <div className="space-y-6">
      {/* Title & actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-govblue-900 tracking-tight m-0">
            {t('projects_page.title')}
          </h1>
          <p className="text-xs text-slate-500 mt-1 m-0">
            {isEnglish
              ? 'Every work, from a proposal to a finished asset: what stage it is at, where its money stands, and how much of it exists.'
              : 'प्रत्येक काम, प्रस्तावापासून पूर्ण मालमत्तेपर्यंत: कोणत्या टप्प्यावर आहे, निधी कुठे आहे आणि किती काम झाले आहे.'}
          </p>
        </div>
        {isOfficer && (
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setRegistering(true)}
              className="px-4 py-2.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 font-bold text-xs transition-colors"
            >
              {isEnglish ? 'Register a work already under way' : 'आधीपासून सुरू असलेले काम नोंदवा'}
            </button>
            <button
              onClick={() => setProposing(true)}
              className="px-4 py-2.5 rounded-lg bg-govnavy hover:bg-govblue-700 text-white font-bold text-xs sm:text-sm flex items-center justify-center gap-1.5 shadow-sm transition-colors"
            >
              <Plus size={16} />
              <span>{isEnglish ? 'New proposal' : 'नवीन प्रस्ताव'}</span>
            </button>
          </div>
        )}
      </div>

      {projects.error && <ErrorNotice message={projects.error} onRetry={projects.refetch} />}

      {projects.loading && projects.data === null && (
        <div className="flex items-center justify-center gap-2 py-16 text-slate-400">
          <Loader2 size={18} className="animate-spin" />
          <span className="text-xs font-bold uppercase tracking-wider">
            {isEnglish ? 'Loading works' : 'कामे लोड होत आहेत'}
          </span>
        </div>
      )}

      {projects.data !== null && !projects.error && rows.length === 0 && (
        <EmptyState
          title={
            isEnglish ? 'No development work recorded yet' : 'अद्याप कोणतेही विकासकाम नोंदवलेले नाही'
          }
          hint={
            isEnglish
              ? 'Open a proposal above, or turn a complaint into one from the complaints screen.'
              : 'वरून प्रस्ताव उघडा, किंवा तक्रारी पानावरून तक्रारीचे प्रस्तावात रूपांतर करा.'
          }
        />
      )}

      {rows.length > 0 && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {tiles.map((tile) => (
              <div
                key={tile.label}
                className={`bg-white rounded-xl p-4 border border-slate-200 border-t-4 ${tile.border} shadow-sm`}
              >
                <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">
                  {tile.label}
                </span>
                <span className="text-2xl font-extrabold block mt-1 text-govblue-900 tabular-nums">
                  {tile.value}
                </span>
              </div>
            ))}
          </div>

          {needLooking > 0 && (
            <p className="text-xs text-amber-900 font-semibold bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 m-0 flex items-start gap-1.5">
              <AlertTriangle size={13} className="mt-0.5 flex-shrink-0" />
              {isEnglish
                ? `${needLooking} work(s) have something worth checking. They are listed first.`
                : `${needLooking} कामांमध्ये तपासण्यासारखे काही आहे. ती आधी दाखवली आहेत.`}
            </p>
          )}

          {/* Filters, counted from the loaded records */}
          <div className="flex flex-wrap items-center gap-1.5 bg-white border border-slate-200 p-2 rounded-lg max-w-max shadow-sm">
            {GROUPS.filter((g) => g.key === 'all' || counts[g.key] > 0).map((g) => (
              <button
                key={g.key}
                onClick={() => setGroup(g.key)}
                aria-pressed={group === g.key}
                className={`px-3.5 py-1.5 rounded text-xs font-bold transition-colors ${
                  group === g.key
                    ? 'bg-govnavy text-white'
                    : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800'
                }`}
              >
                {isEnglish ? g.en : g.mr}
                <span className="ml-1.5 tabular-nums opacity-70">{counts[g.key]}</span>
              </button>
            ))}
          </div>

          {/* Sanctioned vs spent. One axis, both series in ₹ lakh. */}
          {chartData.length > 0 && (
            <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm space-y-3">
              <div className="border-b border-slate-100 pb-2">
                <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wider m-0">
                  {isEnglish
                    ? 'Sanctioned vs Spent, by Work (₹ lakh)'
                    : 'कामनिहाय मंजूर निधी व झालेला खर्च (₹ लाख)'}
                </h2>
                <p className="text-[11px] text-slate-400 mt-1 m-0 tabular-nums">
                  {isEnglish
                    ? `${chartData.length} work(s) with money sanctioned · ${lakhs(totals.budget, true)} sanctioned · ${lakhs(totals.utilized, true)} spent`
                    : `निधी मंजूर असलेली ${chartData.length} कामे · ${lakhs(totals.budget, false)} मंजूर · ${lakhs(totals.utilized, false)} खर्च`}
                </p>
              </div>
              <div style={{ height: Math.max(240, Math.min(420, chartData.length * 52)) }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 8, right: 8, left: -18, bottom: 0 }} barGap={2}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
                    <XAxis
                      dataKey="name"
                      stroke="#94a3b8"
                      fontSize={10}
                      tickLine={false}
                      axisLine={{ stroke: '#e2e8f0' }}
                    />
                    <YAxis stroke="#94a3b8" fontSize={10} tickLine={false} axisLine={false} unit="L" />
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
                    <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} iconType="circle" iconSize={8} />
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

          {/* The works */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {shown.length === 0 ? (
              <div className="md:col-span-2">
                <EmptyState
                  title={isEnglish ? 'No works at this point' : 'या टप्प्यावर कोणतेही काम नाही'}
                  hint={isEnglish ? 'Choose “All” to see every work.' : 'सर्व कामे पाहण्यासाठी “सर्व” निवडा.'}
                />
              </div>
            ) : (
              shown.map((p) => {
                const due = p.expectedCompletion ? formatDate(p.expectedCompletion, isEnglish) : null;
                const showsProgress = p.stage === 'in_progress' || p.stage === 'completed';
                const firstWarning = p.flags.find((flag) => flag.severity === 'warning');
                const otherFlags = p.flags.length - (firstWarning ? 1 : 0);

                return (
                  <article
                    key={p.id}
                    className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm hover:shadow-md transition-all flex flex-col justify-between gap-4"
                  >
                    <div className="space-y-1.5">
                      <div className="flex items-start justify-between gap-4">
                        <h3 className="text-sm font-bold text-govblue-900 tracking-tight leading-snug m-0">
                          {pick(p.name, p.nameMr, isEnglish)}
                        </h3>
                        {p.status === 'Delayed' ? (
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide border whitespace-nowrap ${STATUS_CHIP.Delayed}`}
                          >
                            {pick(p.status, p.statusMr, isEnglish)}
                          </span>
                        ) : (
                          <StageChip
                            stage={p.stage}
                            label={p.stageLabel}
                            labelMr={p.stageLabelMr}
                            isEnglish={isEnglish}
                          />
                        )}
                      </div>
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px] text-slate-500">
                        <span className="flex items-center gap-1">
                          <MapPin size={11} className="text-slate-400" />
                          <span>{pick(p.location, p.locationMr, isEnglish)}</span>
                        </span>
                        <span>·</span>
                        <span>{isEnglish ? `Ward ${p.ward}` : `वॉर्ड ${p.ward}`}</span>
                        {due && (
                          <>
                            <span>·</span>
                            <span className="flex items-center gap-1">
                              <CalendarDays size={11} className="text-slate-400" />
                              {isEnglish ? `by ${due}` : `${due} पर्यंत`}
                            </span>
                          </>
                        )}
                      </div>
                    </div>

                    <p className="text-xs text-slate-600 leading-relaxed m-0 line-clamp-2">
                      {pick(p.description, p.descriptionMr, isEnglish)}
                    </p>

                    <StageBar
                      stageIndex={p.stageIndex}
                      stageTotal={p.stageTotal}
                      label={pick(p.stageLabel, p.stageLabelMr, isEnglish)}
                      isEnglish={isEnglish}
                    />

                    {showsProgress && (
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-slate-500 font-bold">
                            {p.unitsPlanned !== null
                              ? isEnglish
                                ? `${p.unitsDone} of ${p.unitsPlanned} ${p.unitLabel ?? 'units'}`
                                : `${p.unitsPlanned} पैकी ${p.unitsDone} ${p.unitLabelMr ?? p.unitLabel ?? 'घटक'}`
                              : t('projects_page.progress')}
                          </span>
                          <strong className="text-govblue-900 tabular-nums">{p.physicalPercent}%</strong>
                        </div>
                        <div
                          className="w-full bg-slate-100 rounded-full h-2 border border-slate-200 overflow-hidden"
                          role="progressbar"
                          aria-valuenow={p.physicalPercent}
                          aria-valuemin={0}
                          aria-valuemax={100}
                        >
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${STATUS_BAR[p.status]}`}
                            style={{ width: `${Math.max(0, Math.min(100, p.physicalPercent))}%` }}
                          />
                        </div>
                      </div>
                    )}

                    <div className="pt-3 border-t border-slate-100 space-y-2">
                      <p className="text-xs text-slate-700 font-semibold m-0 tabular-nums">
                        {moneyLine(p, isEnglish)}
                      </p>

                      {firstWarning && (
                        <p className="text-[11px] text-amber-900 font-semibold m-0 flex items-start gap-1.5 leading-relaxed">
                          <AlertTriangle size={12} className="mt-0.5 flex-shrink-0" />
                          <span>
                            {pick(firstWarning.message, firstWarning.messageMr, isEnglish)}
                            {otherFlags > 0 && (
                              <span className="text-slate-400 font-semibold">
                                {isEnglish ? ` +${otherFlags} more` : ` +${otherFlags} आणखी`}
                              </span>
                            )}
                          </span>
                        </p>
                      )}

                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-[10px] text-slate-400 font-semibold flex items-center gap-1">
                          {p.residentsAffected > 0 && (
                            <>
                              <Users size={11} />
                              {isEnglish
                                ? `${p.residentsAffected} resident(s) asked for this`
                                : `${p.residentsAffected} रहिवाशांची मागणी`}
                            </>
                          )}
                        </span>
                        <button
                          type="button"
                          onClick={() => setOpenId(p.id)}
                          className="text-xs font-bold text-govnavy hover:underline"
                        >
                          {isOfficer
                            ? isEnglish
                              ? 'Open and update'
                              : 'उघडा व अद्ययावत करा'
                            : isEnglish
                              ? 'See details'
                              : 'तपशील पहा'}
                        </button>
                      </div>
                    </div>
                  </article>
                );
              })
            )}
          </div>
        </>
      )}

      {openId && (
        <WorkDetail
          projectId={openId}
          isEnglish={isEnglish}
          canAct={isOfficer}
          onClose={() => setOpenId(null)}
          onChanged={projects.refetch}
        />
      )}

      {proposing && (
        <ProposalForm
          isEnglish={isEnglish}
          village={village.data}
          onClose={() => setProposing(false)}
          onCreated={(project) => {
            setProposing(false);
            projects.refetch();
            // Straight into the new work, where the next step is waiting.
            setOpenId(project.id);
          }}
        />
      )}

      {registering && (
        <RegisterModal
          isEnglish={isEnglish}
          village={village.data}
          onClose={() => setRegistering(false)}
          onRegistered={() => {
            setRegistering(false);
            projects.refetch();
          }}
        />
      )}
    </div>
  );
};
