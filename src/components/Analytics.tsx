/**
 * Analytics.
 *
 * Every figure on this screen is served by the API, scoped to the officer's own
 * Gram Panchayat. The previous version computed all four charts from the
 * hardcoded `mockData` arrays — including a "Potential Scheme Eligibility"
 * chart whose bars came from eligibility rules re-implemented in the browser
 * against ten sample residents, and a donut whose centre read "Sample DB".
 *
 * Charts, against the anti-pattern list:
 *  - The donut is gone. It compared three close values and its amber/yellow
 *    pair sat ΔE 2.5 apart for a deuteranopic reader — indistinguishable. Age
 *    bands are an ordered scale, so they are a column chart read off an axis.
 *  - Categorical colours are #2547a8 / #138808, validated for colour-vision
 *    deficiency (ΔE 28.7 deutan) and 3:1 against the white card. Only the
 *    budget chart carries two series, and it has a legend.
 *  - Single-series charts get one hue. Colouring each bar differently would
 *    double-encode bar length as colour and buy nothing.
 *  - No dual axes anywhere: budget and spend share one ₹-lakh scale.
 *  - Gridlines are solid hairlines, not dashes.
 *  - Every chart has a table twin behind the "Show data tables" toggle, so no
 *    value is reachable only by hovering a bar.
 */

import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  AlertTriangle,
  Coins,
  Hammer,
  Loader2,
  Table2,
  Users,
} from 'lucide-react';

import {
  api,
  type DashboardStats,
  type NamedCount,
  type ProjectBudget,
} from '../lib/api';
import { useQuery } from '../lib/useApi';
import { ErrorNotice } from './schemes/SchemeBits';

// Validated pair — see the note at the top of this file.
const SERIES_BUDGET = '#2547a8';
const SERIES_SPENT = '#138808';
const SINGLE_HUE = '#2547a8';

// Chart chrome: hairlines one shade off the card surface.
const GRID = '#eef2f7';
const AXIS_LINE = '#e2e8f0';
const AXIS_TEXT = '#94a3b8';

const TOOLTIP_STYLE = {
  backgroundColor: '#ffffff',
  borderColor: '#e2e8f0',
  borderRadius: 8,
  fontSize: 12,
} as const;

/** `labelMr` is nullable on NamedCount; fall back rather than render "null". */
const nameOf = (row: NamedCount, isEnglish: boolean): string =>
  isEnglish ? row.label : row.labelMr || row.label;

const lakhsFromRupees = (value: number, isEnglish: boolean) =>
  isEnglish
    ? `₹${(value / 100000).toFixed(2)} L`
    : `₹${(value / 100000).toFixed(2)} लाख`;

interface AnalyticsBundle {
  stats: DashboardStats;
  ages: NamedCount[];
  byDepartment: NamedCount[];
  byWard: NamedCount[];
  budgets: ProjectBudget[];
}

// ─── Small building blocks ──────────────────────────────────────────────────

const DataTable: React.FC<{
  caption: string;
  columns: string[];
  rows: (string | number)[][];
}> = ({ caption, columns, rows }) => (
  <div className="overflow-x-auto border-t border-slate-100 pt-3">
    <table className="w-full text-xs">
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr>
          {columns.map((column, i) => (
            <th
              key={column}
              scope="col"
              className={`pb-1.5 font-bold text-[10px] uppercase tracking-wider text-slate-400 ${
                i === 0 ? 'text-left' : 'text-right'
              }`}
            >
              {column}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, rowIndex) => (
          <tr key={rowIndex} className="border-t border-slate-100">
            {row.map((cell, i) => (
              <td
                key={i}
                className={`py-1.5 ${
                  i === 0
                    ? 'text-left text-slate-700 font-semibold'
                    : 'text-right text-slate-600 tabular-nums'
                }`}
              >
                {typeof cell === 'number' ? cell.toLocaleString('en-IN') : cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

const ChartCard: React.FC<{
  title: string;
  hint: string;
  isEmpty: boolean;
  emptyText: string;
  className?: string;
  table: React.ReactNode;
  showTable: boolean;
  children: React.ReactNode;
}> = ({ title, hint, isEmpty, emptyText, className, table, showTable, children }) => (
  <section
    className={`bg-white rounded-xl p-5 border border-slate-200 shadow-sm space-y-3 ${
      className ?? ''
    }`}
  >
    <div className="border-b border-slate-100 pb-2">
      <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wider m-0">
        {title}
      </h2>
      <p className="text-[10px] text-slate-400 mt-0.5 m-0">{hint}</p>
    </div>

    {isEmpty ? (
      <p className="text-xs text-slate-400 py-10 text-center m-0">{emptyText}</p>
    ) : (
      <>
        {children}
        {showTable && table}
      </>
    )}
  </section>
);

// ─── The screen ─────────────────────────────────────────────────────────────

export const Analytics: React.FC = () => {
  const { t, i18n } = useTranslation();
  const isEnglish = i18n.language === 'en';

  const [showTables, setShowTables] = useState(false);

  // One round of parallel requests rather than four chained useQuery calls:
  // the screen is not readable until all of them have landed, so waterfalling
  // them would only push the first paint out by three round trips.
  const query = useQuery<AnalyticsBundle>(async () => {
    const [stats, ages, byDepartment, byWard, budgets] = await Promise.all([
      api.analytics.dashboard(),
      api.analytics.ageDistribution(),
      api.analytics.grievancesByDepartment(),
      api.analytics.grievancesByWard(),
      api.analytics.projectBudgets(),
    ]);
    return { stats, ages, byDepartment, byWard, budgets };
  }, []);

  const bundle = query.data;

  const metrics = useMemo(() => {
    if (!bundle) return [];
    const s = bundle.stats;
    const spentPercent = s.totalBudget
      ? Math.round((s.totalUtilized / s.totalBudget) * 100)
      : 0;

    return [
      {
        label: isEnglish ? 'Residents on record' : 'नोंदणीकृत रहिवासी',
        value: s.totalCitizens.toLocaleString('en-IN'),
        sub: isEnglish
          ? `${s.totalFamilies.toLocaleString('en-IN')} households`
          : `${s.totalFamilies.toLocaleString('en-IN')} कुटुंबे`,
        icon: Users,
        chip: 'bg-govblue-50 text-govblue-700 border-govblue-200',
        border: 'border-govblue-600',
      },
      {
        label: isEnglish ? 'Open grievances' : 'प्रलंबित तक्रारी',
        value: s.openGrievances.toLocaleString('en-IN'),
        sub: isEnglish
          ? `${s.criticalGrievances} critical · ${s.resolvedGrievances} resolved`
          : `${s.criticalGrievances} अत्यावश्यक · ${s.resolvedGrievances} निकाली`,
        icon: AlertTriangle,
        chip: s.criticalGrievances
          ? 'bg-rose-50 text-rose-600 border-rose-200'
          : 'bg-slate-50 text-slate-500 border-slate-200',
        border: s.criticalGrievances ? 'border-rose-600' : 'border-slate-300',
      },
      {
        label: isEnglish ? 'Active projects' : 'सुरू प्रकल्प',
        value: s.activeProjects.toLocaleString('en-IN'),
        sub: s.delayedProjects
          ? isEnglish
            ? `${s.delayedProjects} delayed`
            : `${s.delayedProjects} विलंबित`
          : isEnglish
            ? 'All on track'
            : 'सर्व वेळेत',
        icon: Hammer,
        chip: 'bg-sky-50 text-sky-600 border-sky-200',
        border: s.delayedProjects ? 'border-govsaffron' : 'border-sky-600',
      },
      {
        label: isEnglish ? 'Sanctioned budget' : 'मंजूर निधी',
        value: lakhsFromRupees(s.totalBudget, isEnglish),
        sub: isEnglish
          ? `${lakhsFromRupees(s.totalUtilized, isEnglish)} spent (${spentPercent}%)`
          : `${lakhsFromRupees(s.totalUtilized, isEnglish)} खर्च (${spentPercent}%)`,
        icon: Coins,
        chip: 'bg-purple-50 text-purple-600 border-purple-200',
        border: 'border-purple-600',
      },
    ];
  }, [bundle, isEnglish]);

  // ProjectBudget reports lakhs already; Project.budget is in rupees. Only the
  // lakh fields reach this chart, so the two units never share an axis.
  const budgetChart = useMemo(
    () =>
      (bundle?.budgets ?? []).map((p) => ({
        name: (isEnglish ? p.name : p.nameMr).slice(0, 18),
        fullName: isEnglish ? p.name : p.nameMr,
        budget: p.budgetLakh,
        utilized: p.utilizedLakh,
      })),
    [bundle, isEnglish],
  );

  const ageChart = useMemo(
    () => (bundle?.ages ?? []).map((row) => ({ name: nameOf(row, isEnglish), value: row.value })),
    [bundle, isEnglish],
  );

  const departmentChart = useMemo(
    () =>
      (bundle?.byDepartment ?? []).map((row) => ({
        name: nameOf(row, isEnglish),
        value: row.value,
      })),
    [bundle, isEnglish],
  );

  const wardChart = useMemo(
    () =>
      (bundle?.byWard ?? []).map((row) => ({
        name: nameOf(row, isEnglish),
        value: row.value,
      })),
    [bundle, isEnglish],
  );

  // Refetch keeps the previous render on screen, dimmed, instead of collapsing
  // back to the loading block and jumping the layout.
  const refreshing = query.loading && bundle !== null;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-extrabold text-govblue-900 tracking-tight m-0">
            {t('nav.analytics')}
          </h1>
          <p className="text-xs text-slate-500 m-0">
            {isEnglish
              ? 'Demographics, grievance load and project finance, read from your Panchayat records.'
              : 'लोकसंख्या रचना, तक्रारींचा भार आणि प्रकल्प खर्च — तुमच्या ग्रामपंचायत नोंदींवरून.'}
          </p>
        </div>

        <button
          type="button"
          onClick={() => setShowTables((on) => !on)}
          aria-pressed={showTables}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-bold transition-colors ${
            showTables
              ? 'bg-govnavy text-white border-govnavy'
              : 'bg-white text-slate-600 border-slate-300 hover:bg-slate-50'
          }`}
        >
          <Table2 size={14} />
          {isEnglish ? 'Show data tables' : 'आकडेवारी तक्ता दाखवा'}
        </button>
      </header>

      {query.error && <ErrorNotice message={query.error} onRetry={query.refetch} />}

      {query.loading && !bundle && (
        <div className="flex items-center justify-center gap-2 py-16 text-slate-400">
          <Loader2 size={18} className="animate-spin" />
          <span className="text-xs font-bold uppercase tracking-wider">
            {isEnglish ? 'Loading village figures' : 'गावाची आकडेवारी लोड होत आहे'}
          </span>
        </div>
      )}

      {bundle && (
        <div className={`space-y-6 ${refreshing ? 'opacity-60 transition-opacity' : ''}`}>
          {/* Headline figures */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {metrics.map((card) => {
              const Icon = card.icon;
              return (
                <div
                  key={card.label}
                  className={`bg-white rounded-xl p-5 border border-slate-200 border-t-4 ${card.border} shadow-sm flex items-center justify-between gap-3`}
                >
                  <div className="space-y-1 min-w-0">
                    <span className="text-slate-500 text-[10px] font-bold uppercase tracking-wider block">
                      {card.label}
                    </span>
                    {/* Proportional figures: tabular-nums makes a large
                        standalone number read loose. */}
                    <span className="text-2xl sm:text-3xl font-extrabold text-govblue-900 block">
                      {card.value}
                    </span>
                    <span className="text-[10px] text-slate-400 font-semibold block">
                      {card.sub}
                    </span>
                  </div>
                  <span
                    className={`w-11 h-11 rounded-lg flex items-center justify-center border flex-shrink-0 ${card.chip}`}
                  >
                    <Icon size={20} />
                  </span>
                </div>
              );
            })}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Project finance — the only two-series chart, so the only legend. */}
            <ChartCard
              className="lg:col-span-2"
              title={
                isEnglish
                  ? 'Sanctioned budget vs spent, by project (₹ lakh)'
                  : 'प्रकल्पनिहाय मंजूर निधी व झालेला खर्च (₹ लाख)'
              }
              hint={
                isEnglish
                  ? 'Both bars are on the same ₹-lakh scale.'
                  : 'दोन्ही स्तंभ एकाच ₹-लाख मापावर आहेत.'
              }
              isEmpty={budgetChart.length === 0}
              emptyText={
                isEnglish
                  ? 'No projects recorded for this village yet.'
                  : 'या गावासाठी अद्याप प्रकल्प नोंदवलेले नाहीत.'
              }
              showTable={showTables}
              table={
                <DataTable
                  caption={isEnglish ? 'Project budgets' : 'प्रकल्प निधी'}
                  columns={[
                    isEnglish ? 'Project' : 'प्रकल्प',
                    isEnglish ? 'Sanctioned (₹ lakh)' : 'मंजूर (₹ लाख)',
                    isEnglish ? 'Spent (₹ lakh)' : 'खर्च (₹ लाख)',
                  ]}
                  rows={(bundle.budgets ?? []).map((p) => [
                    isEnglish ? p.name : p.nameMr,
                    p.budgetLakh,
                    p.utilizedLakh,
                  ])}
                />
              }
            >
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={budgetChart}
                    margin={{ top: 8, right: 8, left: -14, bottom: 4 }}
                    barGap={2}
                  >
                    <CartesianGrid stroke={GRID} vertical={false} />
                    <XAxis
                      dataKey="name"
                      stroke={AXIS_TEXT}
                      fontSize={10}
                      tickLine={false}
                      axisLine={{ stroke: AXIS_LINE }}
                    />
                    <YAxis
                      stroke={AXIS_TEXT}
                      fontSize={10}
                      tickLine={false}
                      axisLine={false}
                      unit="L"
                    />
                    <Tooltip
                      cursor={{ fill: 'rgba(37,71,168,0.05)' }}
                      contentStyle={TOOLTIP_STYLE}
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
                      dataKey="budget"
                      fill={SERIES_BUDGET}
                      radius={[4, 4, 0, 0]}
                    />
                    <Bar
                      name={isEnglish ? 'Spent' : 'खर्च'}
                      dataKey="utilized"
                      fill={SERIES_SPENT}
                      radius={[4, 4, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>

            {/* Age bands: an ordered scale read off an axis, not a donut. */}
            <ChartCard
              title={isEnglish ? 'Residents by age band' : 'वयोगटानुसार रहिवासी'}
              hint={
                isEnglish
                  ? 'Age bands as the register groups them.'
                  : 'नोंदवहीतील वयोगटांप्रमाणे.'
              }
              isEmpty={ageChart.length === 0}
              emptyText={
                isEnglish
                  ? 'No residents on the register yet.'
                  : 'नोंदवहीत अद्याप रहिवासी नाहीत.'
              }
              showTable={showTables}
              table={
                <DataTable
                  caption={isEnglish ? 'Residents by age band' : 'वयोगटानुसार रहिवासी'}
                  columns={[
                    isEnglish ? 'Age band' : 'वयोगट',
                    isEnglish ? 'Residents' : 'रहिवासी',
                  ]}
                  rows={ageChart.map((row) => [row.name, row.value])}
                />
              }
            >
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={ageChart}
                    margin={{ top: 16, right: 8, left: -18, bottom: 4 }}
                  >
                    <CartesianGrid stroke={GRID} vertical={false} />
                    <XAxis
                      dataKey="name"
                      stroke={AXIS_TEXT}
                      fontSize={10}
                      tickLine={false}
                      axisLine={{ stroke: AXIS_LINE }}
                      interval={0}
                    />
                    <YAxis
                      stroke={AXIS_TEXT}
                      fontSize={10}
                      tickLine={false}
                      axisLine={false}
                      allowDecimals={false}
                    />
                    <Tooltip
                      cursor={{ fill: 'rgba(37,71,168,0.05)' }}
                      contentStyle={TOOLTIP_STYLE}
                      formatter={(value) =>
                        `${value} ${isEnglish ? 'residents' : 'रहिवासी'}`
                      }
                    />
                    {/* One series, one hue — bar length already carries the value. */}
                    <Bar dataKey="value" fill={SINGLE_HUE} radius={[4, 4, 0, 0]} maxBarSize={56}>
                      <LabelList
                        dataKey="value"
                        position="top"
                        style={{ fill: '#475569', fontSize: 11, fontWeight: 700 }}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>

            {/* Grievances by ward. */}
            <ChartCard
              title={isEnglish ? 'Grievances by ward' : 'वॉर्डनिहाय तक्रारी'}
              hint={
                isEnglish
                  ? 'Where complaints are being raised.'
                  : 'तक्रारी कोठून येत आहेत.'
              }
              isEmpty={wardChart.length === 0}
              emptyText={
                isEnglish
                  ? 'No grievances recorded yet.'
                  : 'अद्याप तक्रारी नोंदवलेल्या नाहीत.'
              }
              showTable={showTables}
              table={
                <DataTable
                  caption={isEnglish ? 'Grievances by ward' : 'वॉर्डनिहाय तक्रारी'}
                  columns={[
                    isEnglish ? 'Ward' : 'वॉर्ड',
                    isEnglish ? 'Grievances' : 'तक्रारी',
                  ]}
                  rows={wardChart.map((row) => [row.name, row.value])}
                />
              }
            >
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={wardChart}
                    margin={{ top: 16, right: 8, left: -18, bottom: 4 }}
                  >
                    <CartesianGrid stroke={GRID} vertical={false} />
                    <XAxis
                      dataKey="name"
                      stroke={AXIS_TEXT}
                      fontSize={10}
                      tickLine={false}
                      axisLine={{ stroke: AXIS_LINE }}
                      interval={0}
                    />
                    <YAxis
                      stroke={AXIS_TEXT}
                      fontSize={10}
                      tickLine={false}
                      axisLine={false}
                      allowDecimals={false}
                    />
                    <Tooltip
                      cursor={{ fill: 'rgba(37,71,168,0.05)' }}
                      contentStyle={TOOLTIP_STYLE}
                      formatter={(value) =>
                        `${value} ${isEnglish ? 'grievances' : 'तक्रारी'}`
                      }
                    />
                    <Bar dataKey="value" fill={SINGLE_HUE} radius={[4, 4, 0, 0]} maxBarSize={56}>
                      <LabelList
                        dataKey="value"
                        position="top"
                        style={{ fill: '#475569', fontSize: 11, fontWeight: 700 }}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>

            {/* Departments carry long names, so the bars go horizontal and the
                values are direct-labelled rather than left to a tooltip. */}
            <ChartCard
              className="lg:col-span-2"
              title={isEnglish ? 'Grievances by department' : 'विभागनिहाय तक्रारी'}
              hint={
                isEnglish
                  ? 'Which department is carrying the load.'
                  : 'कोणत्या विभागावर सर्वाधिक भार आहे.'
              }
              isEmpty={departmentChart.length === 0}
              emptyText={
                isEnglish
                  ? 'No grievances recorded yet.'
                  : 'अद्याप तक्रारी नोंदवलेल्या नाहीत.'
              }
              showTable={showTables}
              table={
                <DataTable
                  caption={isEnglish ? 'Grievances by department' : 'विभागनिहाय तक्रारी'}
                  columns={[
                    isEnglish ? 'Department' : 'विभाग',
                    isEnglish ? 'Grievances' : 'तक्रारी',
                  ]}
                  rows={departmentChart.map((row) => [row.name, row.value])}
                />
              }
            >
              <div style={{ height: Math.max(180, departmentChart.length * 44) }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={departmentChart}
                    layout="vertical"
                    margin={{ top: 4, right: 32, left: 4, bottom: 4 }}
                  >
                    <CartesianGrid stroke={GRID} horizontal={false} />
                    <XAxis type="number" hide />
                    <YAxis
                      type="category"
                      dataKey="name"
                      width={190}
                      stroke="#64748b"
                      fontSize={10}
                      tickLine={false}
                      axisLine={false}
                    />
                    <Tooltip
                      cursor={{ fill: 'rgba(37,71,168,0.05)' }}
                      contentStyle={TOOLTIP_STYLE}
                      formatter={(value) =>
                        `${value} ${isEnglish ? 'grievances' : 'तक्रारी'}`
                      }
                    />
                    <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={16}>
                      {departmentChart.map((entry) => (
                        <Cell key={entry.name} fill={SINGLE_HUE} />
                      ))}
                      <LabelList
                        dataKey="value"
                        position="right"
                        style={{ fill: '#475569', fontSize: 11, fontWeight: 700 }}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>
          </div>
        </div>
      )}
    </div>
  );
};
