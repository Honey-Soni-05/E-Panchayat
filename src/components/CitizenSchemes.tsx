/**
 * Welfare schemes, seen by a resident.
 *
 * Every active scheme, newest first, each carrying that person's own
 * eligibility worked out server-side against real government criteria — with
 * the reason spelled out in their language.
 *
 * A resident walking into a Panchayat office asks one question: "is there
 * anything for me?" This screen answers it.
 */

import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Search,
  Landmark,
  Loader2,
  ExternalLink,
  ChevronDown,
  FileText,
  Info,
} from 'lucide-react';

import { api, type EligibilityResult, type Scheme } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useQuery } from '../lib/useApi';
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

type Filter = 'all' | 'eligible' | 'almost' | 'new';

export const CitizenSchemes: React.FC = () => {
  const { i18n } = useTranslation();
  const { user } = useAuth();
  const isEnglish = i18n.language === 'en';
  const citizenId = user?.citizenId ?? '';

  const [filter, setFilter] = useState<Filter>('all');
  const [search, setSearch] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);

  const schemes = useQuery<Scheme[]>(() => api.schemes.list(), []);
  const eligibility = useQuery<EligibilityResult[]>(
    () => (citizenId ? api.citizens.eligibility(citizenId, isEnglish ? 'en' : 'mr') : Promise.resolve([])),
    [citizenId, i18n.language],
  );

  const loading = schemes.loading || eligibility.loading;
  const error = schemes.error || eligibility.error;

  const byId = useMemo(() => {
    const map = new Map<string, Scheme>();
    (schemes.data ?? []).forEach((s) => map.set(s.id, s));
    return map;
  }, [schemes.data]);

  const rows = useMemo(() => {
    const results = eligibility.data ?? [];
    const merged = results
      .map((result) => ({ result, scheme: byId.get(result.schemeId) }))
      .filter((row): row is { result: EligibilityResult; scheme: Scheme } => !!row.scheme);

    // Newest first within each group; the backend already ranks by status.
    return merged.sort((a, b) => {
      const dateA = a.scheme.announcedOn ?? '';
      const dateB = b.scheme.announcedOn ?? '';
      return dateB.localeCompare(dateA);
    });
  }, [eligibility.data, byId]);

  const counts = useMemo(
    () => ({
      all: rows.length,
      eligible: rows.filter((r) => r.result.status === 'Eligible').length,
      almost: rows.filter((r) => r.result.status === 'Missing Documents').length,
      new: rows.filter((r) => isRecent(r.scheme.announcedOn)).length,
    }),
    [rows],
  );

  const visible = useMemo(() => {
    let list = rows;
    if (filter === 'eligible') list = list.filter((r) => r.result.status === 'Eligible');
    if (filter === 'almost') list = list.filter((r) => r.result.status === 'Missing Documents');
    if (filter === 'new') list = list.filter((r) => isRecent(r.scheme.announcedOn));

    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter(
        (r) =>
          r.scheme.name.toLowerCase().includes(q) ||
          r.scheme.nameMr.includes(search.trim()) ||
          (r.scheme.category ?? '').toLowerCase().includes(q),
      );
    }
    return list;
  }, [rows, filter, search]);

  const FILTERS: { id: Filter; en: string; mr: string; count: number }[] = [
    { id: 'all', en: 'All schemes', mr: 'सर्व योजना', count: counts.all },
    { id: 'eligible', en: 'You qualify', mr: 'तुम्ही पात्र', count: counts.eligible },
    { id: 'almost', en: 'Almost there', mr: 'जवळपास पात्र', count: counts.almost },
    { id: 'new', en: 'Recently launched', mr: 'नवीन योजना', count: counts.new },
  ];

  if (!citizenId) {
    return (
      <EmptyState
        title={isEnglish ? 'No resident record linked to this account' : 'या खात्याशी रहिवासी नोंद जोडलेली नाही'}
        hint={isEnglish ? 'Ask the Panchayat office to link your record.' : 'कृपया ग्रामपंचायत कार्यालयाशी संपर्क साधा.'}
      />
    );
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <header className="space-y-1">
        <div className="flex items-center gap-2">
          <Landmark size={20} className="text-govnavy" />
          <h2 className="text-lg font-extrabold text-govblue-900 tracking-tight m-0">
            {isEnglish ? 'Welfare Schemes' : 'कल्याणकारी योजना'}
          </h2>
        </div>
        <p className="text-xs text-slate-500 m-0">
          {isEnglish
            ? 'Central and Maharashtra schemes, checked against your own record.'
            : 'केंद्र व महाराष्ट्र शासनाच्या योजना, तुमच्या नोंदीनुसार तपासलेल्या.'}
        </p>
      </header>

      {/* Headline answer */}
      {!loading && !error && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 flex items-start gap-3">
          <div className="w-9 h-9 rounded-lg bg-white border border-emerald-200 flex items-center justify-center flex-shrink-0">
            <span className="text-lg font-black text-emerald-700 tabular-nums">
              {counts.eligible}
            </span>
          </div>
          <div className="min-w-0">
            <p className="text-sm font-bold text-emerald-900 m-0">
              {isEnglish
                ? counts.eligible === 1
                  ? 'You qualify for 1 scheme right now'
                  : `You qualify for ${counts.eligible} schemes right now`
                : `तुम्ही सध्या ${counts.eligible} योजनांसाठी पात्र आहात`}
            </p>
            {counts.almost > 0 && (
              <p className="text-xs text-emerald-800 mt-0.5 m-0">
                {isEnglish
                  ? `And ${counts.almost} more once your documents are uploaded and verified.`
                  : `तसेच कागदपत्रे अपलोड व पडताळणी झाल्यावर आणखी ${counts.almost} योजनांसाठी पात्र व्हाल.`}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-1.5">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition-colors ${
                filter === f.id
                  ? 'bg-govnavy text-white border-govnavy'
                  : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
              }`}
            >
              {isEnglish ? f.en : f.mr}
              <span
                className={`ml-1.5 tabular-nums ${
                  filter === f.id ? 'text-white/70' : 'text-slate-400'
                }`}
              >
                {f.count}
              </span>
            </button>
          ))}
        </div>

        <div className="relative sm:w-64">
          <Search size={14} className="absolute left-3 top-2.5 text-slate-400" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={isEnglish ? 'Search schemes' : 'योजना शोधा'}
            className="w-full pl-9 pr-3 py-2 text-xs border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-govnavy/25"
          />
        </div>
      </div>

      {error && <ErrorNotice message={error} onRetry={eligibility.refetch} />}

      {loading && (
        <div className="flex items-center justify-center gap-2 py-16 text-slate-400">
          <Loader2 size={18} className="animate-spin" />
          <span className="text-xs font-bold uppercase tracking-wider">
            {isEnglish ? 'Checking your eligibility' : 'तुमची पात्रता तपासत आहे'}
          </span>
        </div>
      )}

      {!loading && !error && !visible.length && (
        <EmptyState
          title={isEnglish ? 'No schemes match this filter' : 'या निवडीशी जुळणारी योजना नाही'}
          hint={isEnglish ? 'Try "All schemes".' : '"सर्व योजना" पहा.'}
        />
      )}

      {/* Scheme list */}
      <div className="space-y-2.5">
        {visible.map(({ scheme, result }) => {
          const open = expanded === scheme.id;
          return (
            <article
              key={scheme.id}
              className={`bg-white rounded-xl border transition-colors ${
                result.status === 'Eligible'
                  ? 'border-emerald-300 shadow-sm'
                  : 'border-slate-200'
              }`}
            >
              <button
                onClick={() => setExpanded(open ? null : scheme.id)}
                aria-expanded={open}
                className="w-full text-left p-4 flex items-start gap-3"
              >
                <div className="flex-1 min-w-0 space-y-2">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <StatusChip status={result.status} isEnglish={isEnglish} friendly size="sm" />
                    {isRecent(scheme.announcedOn) && <NewBadge isEnglish={isEnglish} />}
                    <LevelBadge level={scheme.level} />
                    {scheme.category && (
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide bg-slate-100 text-slate-600 border border-slate-200">
                        {scheme.category}
                      </span>
                    )}
                  </div>

                  <h3 className="text-sm font-bold text-govblue-900 m-0 leading-snug">
                    {isEnglish ? scheme.name : scheme.nameMr}
                  </h3>

                  <p className="text-xs font-bold text-govgreen m-0">
                    {isEnglish ? scheme.benefit : scheme.benefitMr}
                  </p>

                  <p className="text-xs text-slate-600 m-0 leading-relaxed">
                    {isEnglish ? result.explanation : result.explanationMr}
                  </p>
                </div>

                <ChevronDown
                  size={16}
                  className={`text-slate-400 flex-shrink-0 mt-1 transition-transform ${
                    open ? 'rotate-180' : ''
                  }`}
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
                        {isEnglish ? 'Who can apply' : 'कोण अर्ज करू शकते'}
                      </h4>
                      <CriteriaList criteria={scheme.criteria} isEnglish={isEnglish} />
                    </section>

                    <section className="space-y-2">
                      <h4 className="text-[10px] font-bold uppercase tracking-widest text-slate-400 m-0">
                        {isEnglish ? 'Documents needed' : 'आवश्यक कागदपत्रे'}
                      </h4>
                      {scheme.requiredDocuments.length ? (
                        <ul className="space-y-1.5">
                          {scheme.requiredDocuments.map((doc) => {
                            const missing = result.missingDocuments.some((d) => d.name === doc.name);
                            const pending = result.unverifiedDocuments.find(
                              (d) => d.name === doc.name,
                            );
                            return (
                              <li
                                key={doc.name}
                                className="flex items-start gap-2 text-xs leading-relaxed"
                              >
                                <FileText
                                  size={12}
                                  className={`mt-0.5 flex-shrink-0 ${
                                    missing
                                      ? 'text-rose-500'
                                      : pending
                                        ? 'text-amber-500'
                                        : 'text-emerald-600'
                                  }`}
                                />
                                <span className={missing ? 'text-rose-700' : 'text-slate-700'}>
                                  {isEnglish ? doc.name : doc.nameMr}
                                  {missing && (
                                    <span className="text-rose-600 font-bold">
                                      {isEnglish ? ' — not uploaded' : ' — अपलोड बाकी'}
                                    </span>
                                  )}
                                  {pending && (
                                    <span className="text-amber-700 font-bold">
                                      {isEnglish
                                        ? ` — ${pending.fileStatus}`
                                        : ' — पडताळणी बाकी'}
                                    </span>
                                  )}
                                </span>
                              </li>
                            );
                          })}
                        </ul>
                      ) : (
                        <p className="text-xs text-slate-400 m-0">
                          {isEnglish ? 'None listed.' : 'यादी उपलब्ध नाही.'}
                        </p>
                      )}
                    </section>
                  </div>

                  {scheme.confidence !== 'high' && (
                    <p className="flex items-start gap-2 text-[11px] text-slate-500 bg-slate-50 border border-slate-200 rounded p-2 m-0 leading-relaxed">
                      <Info size={12} className="mt-0.5 flex-shrink-0" />
                      {isEnglish
                        ? 'Some figures for this scheme could not be fully verified against an official page. Confirm at the Panchayat office before applying.'
                        : 'या योजनेतील काही आकडे अधिकृत पानावरून पूर्णपणे पडताळता आले नाहीत. अर्जापूर्वी ग्रामपंचायत कार्यालयात खात्री करा.'}
                    </p>
                  )}

                  <div className="flex flex-wrap items-center gap-4 pt-1">
                    {scheme.formUrl && (
                      <a
                        href={scheme.formUrl}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-govnavy hover:bg-govblue-700 text-white text-xs font-bold transition-colors"
                      >
                        {isEnglish ? 'Apply on the official portal' : 'अधिकृत संकेतस्थळावर अर्ज करा'}
                        <ExternalLink size={12} />
                      </a>
                    )}
                    <SourceLink scheme={scheme} isEnglish={isEnglish} />
                    <span className="text-[11px] text-slate-400">
                      {isEnglish ? 'Announced ' : 'सुरुवात '}
                      {formatAnnounced(scheme.announcedOn, isEnglish)}
                    </span>
                  </div>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
};
