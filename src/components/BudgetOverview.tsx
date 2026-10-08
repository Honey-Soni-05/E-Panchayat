/**
 * The Panchayat's budget across all its works.
 *
 * Open to everyone in the village, residents included, and an officer and a
 * resident of the same village see the same figures. What a Gram Panchayat has
 * sanctioned, received and spent on public works is public information, and
 * there is nothing about any individual in it: the table lists works, not
 * people.
 *
 * Nothing on this page is stored anywhere as a total. Every figure is the sum
 * of the dated entries officers recorded against individual works, added up by
 * the server when the page is opened, so this screen cannot disagree with the
 * works it summarises.
 *
 * That is also its limit, and the page says so at the bottom. It answers "how
 * much was sanctioned, how much has arrived, how much has been paid, and
 * against which works". It is not a set of accounts: there are no vouchers
 * behind the payments, no balances carried between years, and nothing is
 * reconciled against a bank statement or PFMS.
 *
 * An officer also records the money from here. Each work's row carries a
 * button for the entry that work is waiting for — its estimate, the budget
 * request, the sanction, funds arriving, a payment — which opens the work on
 * that form. The first version of this page was read-only, with the entry
 * forms a screen away inside each work, and it read as though the officer had
 * no way to touch the budget at all. Which entry is offered comes from the
 * server with the row; this page still holds no rules of its own.
 */

import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, Info, Loader2, PencilLine, Wallet } from 'lucide-react';

import { api, type BudgetOverview as Overview, type Village } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useQuery } from '../lib/useApi';
import { EmptyState, ErrorNotice } from './schemes/SchemeBits';
import { WorkDetail, type WorkPanel } from './works/WorkDetail';
import {
  ENTRY_BUTTON,
  StageChip,
  nextEntryKind,
  pick,
  rupees,
  useVocabulary,
} from './works/WorkBits';

export const BudgetOverview: React.FC = () => {
  const { i18n } = useTranslation();
  const isEnglish = i18n.language === 'en';
  const { isOfficer, role } = useAuth();
  const isAdmin = role === 'admin';
  const vocabulary = useVocabulary();

  // Empty string means every year on record.
  const [fy, setFy] = useState('');
  const [villageId, setVillageId] = useState('');
  // The work that is open, and the form it should open on if the officer
  // pressed a "record" button rather than the work's name.
  const [openWork, setOpenWork] = useState<{ id: string; panel?: WorkPanel } | null>(null);

  const overview = useQuery<Overview>(
    () => api.budget.overview({ fy: fy || undefined, villageId: villageId || undefined }),
    [fy, villageId],
  );

  // Only an administrator works across villages, so only they are offered one.
  const villages = useQuery<Village[]>(
    () => (isAdmin ? api.villages.list(true) : Promise.resolve([])),
    [isAdmin],
  );

  const data = overview.data;
  const totals = data?.totals;

  // One scale for the three figures that follow each other: what was
  // sanctioned, how much of it arrived, how much of that was paid out.
  const funnel = useMemo(() => {
    if (!totals) return [];
    const scale = Math.max(totals.approved, totals.received, totals.spent, 1);
    return [
      { label: isEnglish ? 'Approved' : 'मंजूर', value: totals.approved, bar: 'bg-govblue-600' },
      { label: isEnglish ? 'Received' : 'प्राप्त', value: totals.received, bar: 'bg-govnavy' },
      { label: isEnglish ? 'Spent' : 'खर्च', value: totals.spent, bar: 'bg-govgreen' },
    ].map((row) => ({ ...row, width: (row.value / scale) * 100 }));
  }, [totals, isEnglish]);

  const stageLine = useMemo(() => {
    if (!data || !vocabulary) return '';
    const counts = data.stageCounts as Record<string, number | undefined>;
    return [...vocabulary.stages, ...vocabulary.sideStages]
      .filter((stage) => (counts[stage.code] ?? 0) > 0)
      .map(
        (stage) =>
          `${counts[stage.code]} ${pick(stage.label, stage.labelMr, isEnglish).toLowerCase()}`,
      )
      .join(' · ');
  }, [data, vocabulary, isEnglish]);

  const refreshing = overview.loading && overview.data !== null;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Wallet size={20} className="text-govnavy" />
            <h1 className="text-xl font-extrabold text-govblue-900 tracking-tight">
              {isEnglish ? 'Panchayat Budget' : 'पंचायतीचा निधी'}
            </h1>
          </div>
          <p className="text-xs text-slate-500 max-w-2xl leading-relaxed">
            {isEnglish
              ? 'What has been sanctioned, what has arrived and what has been paid out, across every development work. Each figure is the sum of the dated entries recorded against the works below.'
              : 'प्रत्येक विकास कामासाठी किती निधी मंजूर झाला, किती प्राप्त झाला आणि किती खर्च झाला. प्रत्येक आकडा खालील कामांवर नोंदवलेल्या दिनांकित नोंदींची बेरीज आहे.'}
          </p>
        </div>

        {isAdmin && (villages.data?.length ?? 0) > 0 && (
          <div className="space-y-1">
            <label
              htmlFor="budget-village"
              className="block text-[10px] font-bold uppercase tracking-wide text-slate-500"
            >
              {isEnglish ? 'Gram Panchayat' : 'ग्रामपंचायत'}
            </label>
            <select
              id="budget-village"
              value={villageId}
              onChange={(e) => setVillageId(e.target.value)}
              className="px-3 py-2 text-xs font-semibold border border-slate-200 rounded-lg bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-govnavy/25"
            >
              <option value="">{isEnglish ? 'Whole block' : 'संपूर्ण तालुका'}</option>
              {(villages.data ?? []).map((v) => (
                <option key={v.id} value={v.id}>
                  {pick(v.name, v.nameMr, isEnglish)}
                </option>
              ))}
            </select>
          </div>
        )}
      </header>

      {/* Where the figures come from, said to the person who can change them. */}
      {isOfficer && (
        <div className="p-3.5 bg-white rounded-lg border border-govnavy/20 flex items-start gap-2.5">
          <PencilLine size={15} className="text-govnavy mt-0.5 flex-shrink-0" />
          <p className="text-xs text-slate-700 leading-relaxed">
            {isEnglish ? (
              <>
                <strong>You record the budget here, work by work.</strong> Use the button on a
                work’s row to enter what it is waiting for: the cost estimate, the budget
                request, the sanction, money received, or a payment. Each payment comes off
                that work’s remaining budget, and every total on this page is those entries
                added up. A figure entered wrongly is put right from inside the work, with
                “Correct”.
              </>
            ) : (
              <>
                <strong>निधीची नोंद तुम्ही येथूनच, कामनिहाय करता.</strong> कामाच्या ओळीतील बटण
                वापरून त्या कामाची पुढची नोंद करा: खर्चाचा अंदाज, निधीची मागणी, मंजुरी, प्राप्त निधी
                किंवा खर्च. प्रत्येक खर्च त्या कामाच्या शिल्लक निधीतून वजा होतो, आणि या पानावरील
                प्रत्येक एकूण रक्कम त्या नोंदींची बेरीज आहे. चुकीची नोंद कामाच्या आत “दुरुस्त करा”
                वापरून सुधारता येते.
              </>
            )}
          </p>
        </div>
      )}

      {overview.error && <ErrorNotice message={overview.error} onRetry={overview.refetch} />}

      {overview.loading && overview.data === null && (
        <div className="flex items-center justify-center gap-2 py-16 text-slate-400">
          <Loader2 size={18} className="animate-spin" />
          <span className="text-xs font-bold uppercase tracking-wider">
            {isEnglish ? 'Adding up the ledgers' : 'नोंदींची बेरीज सुरू आहे'}
          </span>
        </div>
      )}

      {data && totals && (
        <div className={`space-y-5 ${refreshing ? 'opacity-60 transition-opacity' : ''}`}>
          {/* Financial year. A year counts the entries dated in it. */}
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-1.5 bg-white border border-slate-200 p-2 rounded-lg max-w-max shadow-sm">
              {['', ...data.financialYears].map((year) => (
                <button
                  key={year || 'all'}
                  onClick={() => setFy(year)}
                  aria-pressed={fy === year}
                  className={`px-3.5 py-1.5 rounded text-xs font-bold tabular-nums transition-colors ${
                    fy === year
                      ? 'bg-govnavy text-white'
                      : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800'
                  }`}
                >
                  {year ? (isEnglish ? `FY ${year}` : `आ.व. ${year}`) : isEnglish ? 'All years' : 'सर्व वर्षे'}
                </button>
              ))}
            </div>
            {fy && (
              <p className="text-[11px] text-slate-500 leading-relaxed">
                {isEnglish
                  ? `Only entries dated between 1 April and 31 March of ${fy} are counted. A work sanctioned in one year and built in the next shows its approval in the first and its spending in the second — which is why the remaining budget is shown under “All years” and not for a single year.`
                  : `फक्त ${fy} च्या १ एप्रिल ते ३१ मार्च दरम्यानच्या नोंदी मोजल्या आहेत. एका वर्षात मंजूर होऊन पुढील वर्षात झालेल्या कामाची मंजुरी पहिल्या वर्षात व खर्च दुसऱ्या वर्षात दिसतो — म्हणूनच शिल्लक निधी एका वर्षासाठी नाही, तर “सर्व वर्षे” मध्ये दाखवला आहे.`}
              </p>
            )}
          </div>

          {/* Headline figures. "Remaining" is a balance, and a single year has
              none of its own — money received in one year is often spent in
              the next — so it is shown only across all years. */}
          <div className={`grid grid-cols-2 gap-4 ${fy ? 'lg:grid-cols-3' : 'lg:grid-cols-4'}`}>
            {[
              {
                label: isEnglish ? 'Approved' : 'मंजूर',
                value: totals.approved,
                sub: isEnglish ? 'sanctioned for works' : 'कामांसाठी मंजूर',
                border: 'border-govblue-600',
                tone: 'text-govblue-900',
              },
              {
                label: isEnglish ? 'Received' : 'प्राप्त',
                value: totals.received,
                sub:
                  totals.awaiting > 0
                    ? isEnglish
                      ? `${rupees(totals.awaiting)} still to arrive`
                      : `${rupees(totals.awaiting)} येणे बाकी`
                    : isEnglish
                      ? 'all of it has arrived'
                      : 'संपूर्ण निधी प्राप्त',
                border: 'border-govnavy',
                tone: 'text-govblue-900',
              },
              {
                label: isEnglish ? 'Spent' : 'खर्च',
                value: totals.spent,
                sub: isEnglish
                  ? `${totals.utilisationPercent}% of what was approved`
                  : `मंजूर निधीच्या ${totals.utilisationPercent}%`,
                border: 'border-govgreen',
                tone: 'text-govgreen',
              },
              ...(fy
                ? []
                : [
                    {
                      label: isEnglish ? 'Remaining' : 'शिल्लक निधी',
                      value: totals.remaining,
                      sub: isEnglish
                        ? `${rupees(totals.balance)} in hand · ${rupees(totals.awaiting)} still to arrive`
                        : `${rupees(totals.balance)} हातात · ${rupees(totals.awaiting)} येणे बाकी`,
                      border: 'border-govsaffron',
                      tone: 'text-govblue-900',
                    },
                  ]),
            ].map((tile) => (
              <div
                key={tile.label}
                className={`bg-white rounded-xl p-4 border border-slate-200 border-t-4 ${tile.border} shadow-sm`}
              >
                <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">
                  {tile.label}
                </span>
                <span className={`text-xl font-extrabold block mt-1 tabular-nums ${tile.tone}`}>
                  {rupees(tile.value)}
                </span>
                <span className="text-[10px] text-slate-400 font-semibold block mt-0.5">{tile.sub}</span>
              </div>
            ))}
          </div>

          {/* The same three figures on one scale, and what is still upstream */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 grid grid-cols-1 lg:grid-cols-3 gap-5">
            <div className="lg:col-span-2 space-y-2.5">
              {funnel.map((row) => (
                <div key={row.label} className="space-y-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="font-bold text-slate-600">{row.label}</span>
                    <span className="font-bold text-slate-800 tabular-nums">{rupees(row.value)}</span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                    <div className={`h-full rounded-full ${row.bar}`} style={{ width: `${row.width}%` }} />
                  </div>
                </div>
              ))}
            </div>
            <dl className="space-y-2 text-[11px] lg:border-l lg:border-slate-100 lg:pl-5">
              <div className="flex items-center justify-between gap-3">
                <dt className="text-slate-500 font-semibold">
                  {isEnglish ? 'Estimated cost of all works' : 'सर्व कामांचा अंदाजित खर्च'}
                </dt>
                <dd className="font-bold text-slate-800 tabular-nums">{rupees(totals.estimated)}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-slate-500 font-semibold">
                  {isEnglish ? 'Requested, awaiting a decision' : 'मागणी केलेला, निर्णय प्रलंबित'}
                </dt>
                <dd
                  className={`font-bold tabular-nums ${
                    totals.requestedPending > 0 ? 'text-amber-800' : 'text-slate-800'
                  }`}
                >
                  {rupees(totals.requestedPending)}
                </dd>
              </div>
              {stageLine && <p className="text-slate-400 pt-1 leading-relaxed">{stageLine}</p>}
            </dl>
          </div>

          {/* Work by work */}
          {data.projects.length === 0 ? (
            <EmptyState
              title={
                fy
                  ? isEnglish
                    ? `Nothing was recorded in FY ${fy}`
                    : `आ.व. ${fy} मध्ये कोणतीही नोंद नाही`
                  : isEnglish
                    ? 'No development work recorded yet'
                    : 'अद्याप कोणतेही विकासकाम नोंदवलेले नाही'
              }
              hint={fy ? (isEnglish ? 'Choose another year, or “All years”.' : 'दुसरे वर्ष किंवा “सर्व वर्षे” निवडा.') : undefined}
            />
          ) : (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wider px-4 pt-4 pb-2">
                {isEnglish ? 'Work by work' : 'कामनिहाय'}
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-[11px] text-left">
                  <thead className="bg-slate-50 text-slate-500 uppercase tracking-wide text-[9px]">
                    <tr>
                      <th className="px-4 py-2 font-bold">{isEnglish ? 'Work' : 'काम'}</th>
                      <th className="px-3 py-2 font-bold">{isEnglish ? 'Stage' : 'टप्पा'}</th>
                      <th className="px-3 py-2 font-bold text-right">{isEnglish ? 'Estimated' : 'अंदाजित'}</th>
                      <th className="px-3 py-2 font-bold text-right">{isEnglish ? 'Approved' : 'मंजूर'}</th>
                      <th className="px-3 py-2 font-bold text-right">{isEnglish ? 'Received' : 'प्राप्त'}</th>
                      <th className="px-3 py-2 font-bold text-right">{isEnglish ? 'Spent' : 'खर्च'}</th>
                      {!fy && (
                        <th className="px-3 py-2 font-bold text-right">
                          {isEnglish ? 'Remaining' : 'शिल्लक'}
                        </th>
                      )}
                      <th className="px-3 py-2 font-bold">{isEnglish ? 'Work / money' : 'काम / निधी'}</th>
                      {isOfficer && (
                        <th className="px-3 py-2 font-bold">{isEnglish ? 'Record' : 'नोंद'}</th>
                      )}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.projects.map((row) => {
                      const firstWarning = row.flags.find((flag) => flag.severity === 'warning');
                      const rejected = row.stage === 'rejected';
                      // The entry this work is waiting for, if its next step is
                      // a figure rather than a decision.
                      const waitingFor = nextEntryKind(
                        row.stage,
                        row.steps.entryKinds,
                        row.estimated !== null,
                      );
                      return (
                        <tr
                          key={row.id}
                          className={`align-top hover:bg-slate-50 ${rejected ? 'text-slate-400' : ''}`}
                        >
                          <td className="px-4 py-2.5 min-w-[200px]">
                            <button
                              type="button"
                              onClick={() => setOpenWork({ id: row.id })}
                              className="text-left font-bold text-govnavy hover:underline leading-snug"
                            >
                              {pick(row.name, row.nameMr, isEnglish)}
                            </button>
                            <span className="block text-[10px] text-slate-400 font-semibold">
                              {isEnglish ? `Ward ${row.ward}` : `वॉर्ड ${row.ward}`}
                              {row.fundingSourceLabel &&
                                ` · ${pick(row.fundingSourceLabel, row.fundingSourceLabelMr, isEnglish)}`}
                            </span>
                            {firstWarning && (
                              <span className="flex items-start gap-1 text-[10px] text-amber-800 font-semibold mt-0.5 leading-snug">
                                <AlertTriangle size={10} className="mt-0.5 flex-shrink-0" />
                                {pick(firstWarning.message, firstWarning.messageMr, isEnglish)}
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-2.5">
                            <StageChip
                              stage={row.stage}
                              label={row.stageLabel}
                              labelMr={row.stageLabelMr}
                              isEnglish={isEnglish}
                            />
                          </td>
                          <td className="px-3 py-2.5 text-right tabular-nums">{rupees(row.estimated)}</td>
                          <td className="px-3 py-2.5 text-right tabular-nums font-bold">
                            {rupees(row.approved)}
                          </td>
                          <td className="px-3 py-2.5 text-right tabular-nums">
                            {row.approved === null ? '—' : rupees(row.received)}
                          </td>
                          <td className="px-3 py-2.5 text-right tabular-nums">
                            {row.approved === null ? '—' : rupees(row.spent)}
                          </td>
                          {!fy && (
                            <td className="px-3 py-2.5 text-right tabular-nums font-bold">
                              {row.approved === null ? '—' : rupees(row.remaining)}
                            </td>
                          )}
                          <td className="px-3 py-2.5 min-w-[110px]">
                            {row.approved === null ? (
                              <span className="text-slate-300">—</span>
                            ) : (
                              // Two bars on one scale: the gap between them is
                              // the thing worth seeing.
                              <div
                                className="space-y-1"
                                title={
                                  isEnglish
                                    ? `${row.physicalPercent}% of the work done, ${row.financialPercent}% of the budget spent`
                                    : `${row.physicalPercent}% काम पूर्ण, ${row.financialPercent}% निधी खर्च`
                                }
                              >
                                {[
                                  { value: row.physicalPercent, bar: 'bg-govnavy' },
                                  { value: row.financialPercent, bar: 'bg-govgreen' },
                                ].map((bar, i) => (
                                  <div key={i} className="flex items-center gap-1.5">
                                    <div className="h-1.5 flex-1 rounded-full bg-slate-100 overflow-hidden">
                                      <div
                                        className={`h-full rounded-full ${bar.bar}`}
                                        style={{ width: `${Math.max(0, Math.min(100, bar.value))}%` }}
                                      />
                                    </div>
                                    <span className="w-8 text-right tabular-nums text-[10px] text-slate-500">
                                      {bar.value}%
                                    </span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </td>
                          {isOfficer && (
                            <td className="px-3 py-2.5 whitespace-nowrap">
                              {waitingFor ? (
                                <button
                                  type="button"
                                  onClick={() =>
                                    setOpenWork({
                                      id: row.id,
                                      panel: { type: 'entry', kind: waitingFor },
                                    })
                                  }
                                  className="px-2.5 py-1.5 rounded-lg bg-govnavy hover:bg-govblue-700 text-white text-[11px] font-bold transition-colors"
                                >
                                  {isEnglish
                                    ? ENTRY_BUTTON[waitingFor].en
                                    : ENTRY_BUTTON[waitingFor].mr}
                                </button>
                              ) : (
                                <button
                                  type="button"
                                  onClick={() => setOpenWork({ id: row.id })}
                                  className="px-2.5 py-1.5 rounded-lg border border-slate-300 hover:bg-slate-50 text-slate-600 text-[11px] font-bold transition-colors"
                                >
                                  {isEnglish ? 'Open the work' : 'काम उघडा'}
                                </button>
                              )}
                            </td>
                          )}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <p className="text-[10px] text-slate-400 px-4 py-2.5 border-t border-slate-100 leading-relaxed">
                {isEnglish
                  ? 'Remaining is approved less spent. Under “Work / money” the upper bar is work physically done and the lower is budget spent. A proposal that was not approved is listed with its estimate and left out of the totals above.'
                  : 'शिल्लक म्हणजे मंजूर रकमेतून खर्च वजा. “काम / निधी” मध्ये वरची पट्टी प्रत्यक्ष झालेले काम व खालची पट्टी खर्च झालेला निधी दर्शवते. नामंजूर प्रस्ताव अंदाजासह यादीत आहे, पण वरील एकूण रकमांमध्ये धरलेला नाही.'}
              </p>
            </div>
          )}

          {/* By source */}
          {data.sources.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wider px-4 pt-4 pb-2">
                {isEnglish ? 'Where the money came from' : 'निधी कुठून आला'}
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-[11px] text-left">
                  <thead className="bg-slate-50 text-slate-500 uppercase tracking-wide text-[9px]">
                    <tr>
                      <th className="px-4 py-2 font-bold">{isEnglish ? 'Source' : 'स्रोत'}</th>
                      <th className="px-3 py-2 font-bold text-right">{isEnglish ? 'Works' : 'कामे'}</th>
                      <th className="px-3 py-2 font-bold text-right">{isEnglish ? 'Approved' : 'मंजूर'}</th>
                      <th className="px-3 py-2 font-bold text-right">{isEnglish ? 'Received' : 'प्राप्त'}</th>
                      <th className="px-3 py-2 font-bold text-right">{isEnglish ? 'Spent' : 'खर्च'}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.sources.map((source) => (
                      <tr key={source.code ?? 'none'}>
                        <td className="px-4 py-2.5 font-bold text-slate-700">
                          {pick(source.label, source.labelMr, isEnglish)}
                        </td>
                        <td className="px-3 py-2.5 text-right tabular-nums">{source.projects}</td>
                        <td className="px-3 py-2.5 text-right tabular-nums">{rupees(source.approved)}</td>
                        <td className="px-3 py-2.5 text-right tabular-nums">{rupees(source.received)}</td>
                        <td className="px-3 py-2.5 text-right tabular-nums">{rupees(source.spent)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-[10px] text-slate-400 px-4 py-2.5 border-t border-slate-100 leading-relaxed">
                {isEnglish
                  ? 'The source is what the officer recorded on each entry. This system does not decide which fund a work may be paid from.'
                  : 'स्रोत म्हणजे अधिकाऱ्याने प्रत्येक नोंदीवर नोंदवलेली माहिती. कोणते काम कोणत्या निधीतून करता येईल हे ही प्रणाली ठरवत नाही.'}
              </p>
            </div>
          )}

          {/* What this page is not */}
          <div className="p-3.5 bg-govblue-50 rounded-lg border border-govnavy/15 flex items-start gap-2">
            <Info size={14} className="text-govnavy mt-0.5 flex-shrink-0" />
            <p className="text-[11px] text-slate-600 leading-relaxed">
              {isEnglish
                ? 'This is budget tracking, not the Panchayat’s accounts. “Received” and “spent” are an officer recording that money arrived or was paid — this system does not move money. There are no vouchers or vendor ledgers behind these figures, no balances are carried from one year to the next, and nothing here is reconciled against a bank statement or PFMS.'
                : 'हे निधीचे निरीक्षण आहे, पंचायतीचे लेखे नाहीत. “प्राप्त” व “खर्च” म्हणजे निधी आला किंवा दिला गेला याची अधिकाऱ्याने केलेली नोंद — ही प्रणाली पैसे हलवत नाही. या आकड्यांमागे व्हाउचर किंवा पुरवठादार खाती नाहीत, एका वर्षातील शिल्लक पुढील वर्षात नेली जात नाही, आणि बँक विवरण किंवा PFMS शी ताळमेळ घातलेला नाही.'}
            </p>
          </div>
        </div>
      )}

      {openWork && (
        <WorkDetail
          projectId={openWork.id}
          isEnglish={isEnglish}
          canAct={isOfficer}
          initialPanel={openWork.panel}
          onClose={() => setOpenWork(null)}
          onChanged={overview.refetch}
        />
      )}
    </div>
  );
};
