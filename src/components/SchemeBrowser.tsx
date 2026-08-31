/**
 * Welfare schemes, seen by a Panchayat officer.
 *
 * Three jobs on one screen: browse and filter the scheme catalogue, act on
 * schemes arriving from the government feed, and for any scheme see exactly
 * which residents qualify and why.
 *
 * Replaces the old BeneficiaryRecommendations screen, which ran its rules in
 * the browser against six invented schemes.
 */

import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Search,
  Landmark,
  Loader2,
  ExternalLink,
  ChevronDown,
  Users,
  Check,
  X,
  Inbox,
  AlertTriangle,
} from 'lucide-react';

import {
  ELIGIBILITY_ORDER,
  api,
  type EligibilityResult,
  type EligibilityStatus,
  type Scheme,
} from '../lib/api';
import { useMutation, useQuery } from '../lib/useApi';
import {
  CriteriaList,
  EmptyState,
  ErrorNotice,
  LevelBadge,
  NewBadge,
  SourceLink,
  StatusChip,
  formatAnnounced,
  isRecent,
} from './schemes/SchemeBits';

type Sort = 'newest' | 'name' | 'level';

export const SchemeBrowser: React.FC = () => {
  const { i18n } = useTranslation();
  const isEnglish = i18n.language === 'en';

  const [search, setSearch] = useState('');
  const [level, setLevel] = useState<'all' | 'central' | 'state'>('all');
  const [category, setCategory] = useState('all');
  const [sort, setSort] = useState<Sort>('newest');
  const [openScheme, setOpenScheme] = useState<string | null>(null);

  // include_feed pulls in schemes still awaiting an adopt / reject decision.
  const schemes = useQuery<Scheme[]>(() => api.schemes.list(true), []);

  const decide = useMutation(
    (id: string, approve: boolean) => api.schemes.decide(id, approve),
    () => schemes.refetch(),
  );

  const all = schemes.data ?? [];
  const feed = all.filter((s) => s.isGovernmentFeed && s.status === 'pending');
  const adopted = all.filter((s) => s.status === 'active');

  const categories = useMemo(
    () => Array.from(new Set(adopted.map((s) => s.category).filter(Boolean))).sort() as string[],
    [adopted],
  );

  const visible = useMemo(() => {
    let list = adopted;
    if (level !== 'all') list = list.filter((s) => s.level === level);
    if (category !== 'all') list = list.filter((s) => s.category === category);

    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter(
        (s) =>
          s.name.toLowerCase().includes(q) ||
          s.nameMr.includes(search.trim()) ||
          (s.category ?? '').toLowerCase().includes(q),
      );
    }

    return [...list].sort((a, b) => {
      if (sort === 'name') return a.name.localeCompare(b.name);
      if (sort === 'level') return a.level.localeCompare(b.level) || a.name.localeCompare(b.name);
      return (b.announcedOn ?? '').localeCompare(a.announcedOn ?? '');
    });
  }, [adopted, level, category, search, sort]);

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Landmark size={20} className="text-govnavy" />
            <h2 className="text-lg font-extrabold text-govblue-900 tracking-tight m-0">
              {isEnglish ? 'Welfare Schemes' : 'कल्याणकारी योजना'}
            </h2>
          </div>
          <p className="text-xs text-slate-500 m-0">
            {isEnglish
              ? 'Central and Maharashtra schemes. Every rule cites the government page it came from.'
              : 'केंद्र व महाराष्ट्र शासनाच्या योजना. प्रत्येक अट अधिकृत स्रोतासह.'}
          </p>
        </div>
        <div className="flex items-baseline gap-1.5">
          <span className="text-2xl font-black text-govnavy tabular-nums">{adopted.length}</span>
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
            {isEnglish ? 'active schemes' : 'सक्रिय योजना'}
          </span>
        </div>
      </header>

      {schemes.error && <ErrorNotice message={schemes.error} onRetry={schemes.refetch} />}
      {decide.error && <ErrorNotice message={decide.error} />}

      {/* Government feed — schemes awaiting a decision */}
      {feed.length > 0 && (
        <section className="rounded-xl border border-govsaffron/40 bg-orange-50/60 p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Inbox size={15} className="text-govsaffron" />
            <h3 className="text-xs font-bold uppercase tracking-widest text-govsaffron m-0">
              {isEnglish ? 'From the government feed' : 'शासन फीडमधून'}
            </h3>
            <span className="text-[11px] text-slate-500">
              {isEnglish
                ? `${feed.length} awaiting your decision`
                : `${feed.length} निर्णयाच्या प्रतीक्षेत`}
            </span>
          </div>

          {feed.map((scheme) => (
            <div
              key={scheme.id}
              className="bg-white rounded-lg border border-slate-200 p-3.5 flex flex-wrap items-start justify-between gap-3"
            >
              <div className="min-w-0 flex-1 space-y-1.5">
                <div className="flex flex-wrap items-center gap-1.5">
                  <NewBadge isEnglish={isEnglish} />
                  <LevelBadge level={scheme.level} />
                </div>
                <h4 className="text-sm font-bold text-govblue-900 m-0">
                  {isEnglish ? scheme.name : scheme.nameMr}
                </h4>
                <p className="text-xs text-slate-600 m-0">
                  {isEnglish ? scheme.benefit : scheme.benefitMr}
                </p>
                <SourceLink scheme={scheme} isEnglish={isEnglish} />
              </div>

              <div className="flex gap-2 flex-shrink-0">
                <button
                  onClick={() => decide.run(scheme.id, true)}
                  disabled={decide.saving}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-govgreen hover:bg-emerald-700 disabled:opacity-60 text-white text-xs font-bold transition-colors"
                >
                  <Check size={13} />
                  {isEnglish ? 'Adopt' : 'स्वीकारा'}
                </button>
                <button
                  onClick={() => decide.run(scheme.id, false)}
                  disabled={decide.saving}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-300 hover:bg-slate-50 disabled:opacity-60 text-slate-600 text-xs font-bold transition-colors"
                >
                  <X size={13} />
                  {isEnglish ? 'Reject' : 'नाकारा'}
                </button>
              </div>
            </div>
          ))}
        </section>
      )}

      {/* Toolbar */}
      <div className="flex flex-wrap gap-2 items-center">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={14} className="absolute left-3 top-2.5 text-slate-400" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={isEnglish ? 'Search by name or category' : 'नाव किंवा प्रकारानुसार शोधा'}
            className="w-full pl-9 pr-3 py-2 text-xs border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-govnavy/25"
          />
        </div>

        <select
          value={level}
          onChange={(e) => setLevel(e.target.value as typeof level)}
          className="px-3 py-2 text-xs font-semibold border border-slate-200 rounded-lg bg-white text-slate-700"
        >
          <option value="all">{isEnglish ? 'All levels' : 'सर्व स्तर'}</option>
          <option value="central">{isEnglish ? 'Central' : 'केंद्र'}</option>
          <option value="state">{isEnglish ? 'Maharashtra' : 'महाराष्ट्र'}</option>
        </select>

        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="px-3 py-2 text-xs font-semibold border border-slate-200 rounded-lg bg-white text-slate-700"
        >
          <option value="all">{isEnglish ? 'All categories' : 'सर्व प्रकार'}</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>

        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as Sort)}
          className="px-3 py-2 text-xs font-semibold border border-slate-200 rounded-lg bg-white text-slate-700"
        >
          <option value="newest">{isEnglish ? 'Newest first' : 'नवीन प्रथम'}</option>
          <option value="name">{isEnglish ? 'Name (A-Z)' : 'नाव (अ-ज्ञ)'}</option>
          <option value="level">{isEnglish ? 'Central / State' : 'केंद्र / राज्य'}</option>
        </select>
      </div>

      {schemes.loading && (
        <div className="flex items-center justify-center gap-2 py-16 text-slate-400">
          <Loader2 size={18} className="animate-spin" />
          <span className="text-xs font-bold uppercase tracking-wider">
            {isEnglish ? 'Loading schemes' : 'योजना लोड होत आहेत'}
          </span>
        </div>
      )}

      {!schemes.loading && !visible.length && (
        <EmptyState
          title={isEnglish ? 'No schemes match these filters' : 'या निवडीशी जुळणारी योजना नाही'}
          hint={isEnglish ? 'Clear the filters to see all schemes.' : 'सर्व योजना पाहण्यासाठी निवड रद्द करा.'}
        />
      )}

      <div className="space-y-2.5">
        {visible.map((scheme) => (
          <SchemeRow
            key={scheme.id}
            scheme={scheme}
            isEnglish={isEnglish}
            open={openScheme === scheme.id}
            onToggle={() => setOpenScheme(openScheme === scheme.id ? null : scheme.id)}
          />
        ))}
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────

const SchemeRow: React.FC<{
  scheme: Scheme;
  isEnglish: boolean;
  open: boolean;
  onToggle: () => void;
}> = ({ scheme, isEnglish, open, onToggle }) => (
  <article className="bg-white rounded-xl border border-slate-200">
    <button
      onClick={onToggle}
      aria-expanded={open}
      className="w-full text-left p-4 flex items-start gap-3"
    >
      <div className="flex-1 min-w-0 space-y-2">
        <div className="flex flex-wrap items-center gap-1.5">
          {isRecent(scheme.announcedOn) && <NewBadge isEnglish={isEnglish} />}
          <LevelBadge level={scheme.level} />
          {scheme.category && (
            <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide bg-slate-100 text-slate-600 border border-slate-200">
              {scheme.category}
            </span>
          )}
          {scheme.confidence !== 'high' && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide bg-amber-50 text-amber-800 border border-amber-200">
              <AlertTriangle size={9} />
              {isEnglish ? 'Verify figures' : 'आकडे तपासा'}
            </span>
          )}
        </div>

        <h3 className="text-sm font-bold text-govblue-900 m-0 leading-snug">
          {isEnglish ? scheme.name : scheme.nameMr}
        </h3>
        <p className="text-xs font-bold text-govgreen m-0">
          {isEnglish ? scheme.benefit : scheme.benefitMr}
        </p>
        <p className="text-[11px] text-slate-400 m-0">
          {isEnglish ? 'Announced ' : 'सुरुवात '}
          {formatAnnounced(scheme.announcedOn, isEnglish)}
        </p>
      </div>

      <ChevronDown
        size={16}
        className={`text-slate-400 flex-shrink-0 mt-1 transition-transform ${open ? 'rotate-180' : ''}`}
      />
    </button>

    {open && (
      <div className="px-4 pb-4 pt-1 border-t border-slate-100 space-y-4">
        <p className="text-xs text-slate-600 leading-relaxed m-0">
          {isEnglish ? scheme.description : scheme.descriptionMr}
        </p>

        <div className="grid gap-4 sm:grid-cols-2">
          <section className="space-y-2">
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-slate-400 m-0">
              {isEnglish ? 'Eligibility rules' : 'पात्रता निकष'}
            </h4>
            <CriteriaList criteria={scheme.criteria} isEnglish={isEnglish} />
          </section>

          <section className="space-y-2">
            <h4 className="text-[10px] font-bold uppercase tracking-widest text-slate-400 m-0">
              {isEnglish ? 'Required documents' : 'आवश्यक कागदपत्रे'}
            </h4>
            {scheme.requiredDocuments.length ? (
              <ul className="space-y-1">
                {scheme.requiredDocuments.map((doc) => (
                  <li key={doc.name} className="text-xs text-slate-700">
                    • {isEnglish ? doc.name : doc.nameMr}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-slate-400 m-0">
                {isEnglish ? 'None listed.' : 'यादी उपलब्ध नाही.'}
              </p>
            )}
          </section>
        </div>

        {scheme.notes && (
          <p className="text-[11px] text-slate-500 bg-slate-50 border border-slate-200 rounded p-2.5 m-0 leading-relaxed">
            <span className="font-bold uppercase tracking-wider text-slate-400">
              {isEnglish ? 'Note · ' : 'टीप · '}
            </span>
            {scheme.notes}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-4">
          <SourceLink scheme={scheme} isEnglish={isEnglish} />
          {scheme.formUrl && (
            <a
              href={scheme.formUrl}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1 text-[11px] font-bold text-govnavy hover:underline"
            >
              {isEnglish ? 'Application portal' : 'अर्ज संकेतस्थळ'}
              <ExternalLink size={11} />
            </a>
          )}
        </div>

        <BeneficiaryPanel schemeId={scheme.id} isEnglish={isEnglish} />
      </div>
    )}
  </article>
);

// ─────────────────────────────────────────────────────────────────────────────

/** Who in the village qualifies for this scheme, worked out server-side. */
const BeneficiaryPanel: React.FC<{ schemeId: string; isEnglish: boolean }> = ({
  schemeId,
  isEnglish,
}) => {
  const [only, setOnly] = useState<EligibilityStatus | 'all'>('all');

  const results = useQuery<EligibilityResult[]>(
    () => api.schemes.eligibility(schemeId, { language: isEnglish ? 'en' : 'mr' }),
    [schemeId, isEnglish],
  );

  const rows = results.data ?? [];
  const counts = useMemo(() => {
    const map = {} as Record<EligibilityStatus, number>;
    ELIGIBILITY_ORDER.forEach((s) => (map[s] = 0));
    rows.forEach((r) => (map[r.status] += 1));
    return map;
  }, [rows]);

  const visible = only === 'all' ? rows : rows.filter((r) => r.status === only);

  return (
    <section className="border-t border-slate-100 pt-4 space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Users size={14} className="text-govnavy" />
        <h4 className="text-[10px] font-bold uppercase tracking-widest text-slate-400 m-0">
          {isEnglish ? 'Residents assessed' : 'तपासलेले रहिवासी'}
        </h4>
        {results.loading && <Loader2 size={12} className="animate-spin text-slate-400" />}
      </div>

      {results.error && <ErrorNotice message={results.error} onRetry={results.refetch} />}

      {!results.loading && !results.error && (
        <>
          <div className="flex flex-wrap gap-1.5">
            <button
              onClick={() => setOnly('all')}
              className={`px-2.5 py-1 rounded-lg text-[11px] font-bold border transition-colors ${
                only === 'all'
                  ? 'bg-govnavy text-white border-govnavy'
                  : 'bg-white text-slate-600 border-slate-200'
              }`}
            >
              {isEnglish ? 'All' : 'सर्व'} <span className="tabular-nums">{rows.length}</span>
            </button>
            {ELIGIBILITY_ORDER.filter((s) => counts[s] > 0).map((s) => (
              <button
                key={s}
                onClick={() => setOnly(s)}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-bold border transition-colors ${
                  only === s
                    ? 'bg-govnavy text-white border-govnavy'
                    : 'bg-white text-slate-600 border-slate-200'
                }`}
              >
                {s} <span className="tabular-nums">{counts[s]}</span>
              </button>
            ))}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-left">
              <thead>
                <tr className="border-b border-slate-200">
                  <th className="py-2 pr-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    {isEnglish ? 'Resident' : 'रहिवासी'}
                  </th>
                  <th className="py-2 pr-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    {isEnglish ? 'Ward' : 'वॉर्ड'}
                  </th>
                  <th className="py-2 pr-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    {isEnglish ? 'Status' : 'स्थिती'}
                  </th>
                  <th className="py-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    {isEnglish ? 'Reason' : 'कारण'}
                  </th>
                </tr>
              </thead>
              <tbody>
                {visible.map((r) => (
                  <tr key={r.citizenId} className="border-b border-slate-50 align-top">
                    <td className="py-2.5 pr-3 text-xs font-bold text-slate-800 whitespace-nowrap">
                      {isEnglish ? r.citizenName : r.citizenNameMr}
                    </td>
                    <td className="py-2.5 pr-3 text-xs text-slate-500 tabular-nums">{r.ward}</td>
                    <td className="py-2.5 pr-3">
                      <StatusChip status={r.status} isEnglish={isEnglish} size="sm" />
                    </td>
                    <td className="py-2.5 text-xs text-slate-600 leading-relaxed">
                      {isEnglish ? r.explanation : r.explanationMr}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {!visible.length && (
            <p className="text-xs text-slate-400 m-0">
              {isEnglish ? 'No residents in this group.' : 'या गटात कोणीही नाही.'}
            </p>
          )}
        </>
      )}
    </section>
  );
};
