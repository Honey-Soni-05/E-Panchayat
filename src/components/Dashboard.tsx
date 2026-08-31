/**
 * Officer dashboard.
 *
 * Every figure here comes from `/analytics/dashboard`, scoped to the officer's
 * own Gram Panchayat. The previous version displayed invented headline numbers
 * — 12,450 citizens, 3,210 families, ₹2.4 Cr — with the real database counts
 * demoted to subtitles reading "10 DB records" and "5 active mock cases", and a
 * chart label that read "Total Mock".
 *
 * The insights below are computed from the same live figures rather than being
 * four fixed sentences, so they change when the village does and say nothing
 * when there is nothing to say.
 *
 * Chart colours: #2547a8 / #138808 — validated for colour-vision deficiency
 * (ΔE 28.7 deutan, 32.0 normal) and 3:1 contrast against the surface. The old
 * donut used amber #f59e0b beside yellow #eab308, which are ΔE 2.5 apart for a
 * red-green colourblind reader and 5.3 for everyone else: indistinguishable.
 */

import React, { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Users,
  Home,
  AlertTriangle,
  Hammer,
  Coins,
  FileWarning,
  ChevronRight,
  Bot,
  Loader2,
  CheckCircle2,
} from 'lucide-react';
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
  api,
  type DashboardStats,
  type NamedCount,
  type ProjectBudget,
  type Village,
} from '../lib/api';
import { useQuery } from '../lib/useApi';
import { ErrorNotice } from './schemes/SchemeBits';

interface DashboardProps {
  setCurrentTab: (tab: string) => void;
}

// Validated pair — see the note at the top of this file.
const SERIES_BUDGET = '#2547a8';
const SERIES_SPENT = '#138808';
const SINGLE_HUE = '#2547a8';

const lakhs = (value: number, isEnglish: boolean) =>
  isEnglish
    ? `₹${(value / 100000).toFixed(2)} L`
    : `₹${(value / 100000).toFixed(2)} लाख`;

export const Dashboard: React.FC<DashboardProps> = ({ setCurrentTab }) => {
  const { t, i18n } = useTranslation();
  const isEnglish = i18n.language === 'en';

  const stats = useQuery<DashboardStats>(() => api.analytics.dashboard(), []);
  const budgets = useQuery<ProjectBudget[]>(() => api.analytics.projectBudgets(), []);
  const byDepartment = useQuery<NamedCount[]>(
    () => api.analytics.grievancesByDepartment(),
    [],
  );
  const village = useQuery<Village | null>(() => api.villages.current(), []);

  const s = stats.data;

  const metrics = useMemo(() => {
    if (!s) return [];
    return [
      {
        label: t('dashboard.total_citizens'),
        value: s.totalCitizens.toLocaleString('en-IN'),
        sub: t('dashboard.sub_registered'),
        icon: Users,
        border: 'border-govblue-600',
        chip: 'bg-govblue-50 text-govblue-700 border-govblue-200',
        tab: 'citizens',
      },
      {
        label: t('dashboard.families'),
        value: s.totalFamilies.toLocaleString('en-IN'),
        sub: t('dashboard.sub_households'),
        icon: Home,
        border: 'border-govgreen',
        chip: 'bg-emerald-50 text-govgreen border-emerald-200',
        tab: 'citizens',
      },
      {
        label: t('dashboard.pending_grievances'),
        value: s.openGrievances.toLocaleString('en-IN'),
        sub: s.criticalGrievances
          ? t('dashboard.sub_critical', { count: s.criticalGrievances })
          : t('dashboard.sub_none_critical'),
        icon: AlertTriangle,
        border: s.criticalGrievances ? 'border-rose-600' : 'border-slate-300',
        chip: s.criticalGrievances
          ? 'bg-rose-50 text-rose-600 border-rose-200'
          : 'bg-slate-50 text-slate-500 border-slate-200',
        tab: 'grievances',
      },
      {
        label: t('dashboard.ongoing_projects'),
        value: s.activeProjects.toLocaleString('en-IN'),
        sub: s.delayedProjects
          ? t('dashboard.sub_delayed', { count: s.delayedProjects })
          : t('dashboard.sub_on_track'),
        icon: Hammer,
        border: s.delayedProjects ? 'border-govsaffron' : 'border-sky-600',
        chip: 'bg-sky-50 text-sky-600 border-sky-200',
        tab: 'projects',
      },
      {
        label: t('dashboard.project_budget'),
        value: lakhs(s.totalBudget, isEnglish),
        sub: t('dashboard.sub_spent', {
          amount: lakhs(s.totalUtilized, isEnglish),
          percent: s.totalBudget
            ? Math.round((s.totalUtilized / s.totalBudget) * 100)
            : 0,
        }),
        icon: Coins,
        border: 'border-purple-600',
        chip: 'bg-purple-50 text-purple-600 border-purple-200',
        tab: 'projects',
      },
      {
        label: t('dashboard.pending_documents'),
        value: s.pendingDocuments.toLocaleString('en-IN'),
        sub: t('dashboard.sub_awaiting'),
        icon: FileWarning,
        border: 'border-amber-500',
        chip: 'bg-amber-50 text-amber-700 border-amber-200',
        tab: 'citizens',
      },
    ];
  }, [s, t, isEnglish]);

  /** Alerts derived from the live figures — not a fixed list of sentences. */
  const insights = useMemo(() => {
    if (!s) return [];
    const out: { text: string; tab: string }[] = [];

    if (s.criticalGrievances > 0) {
      out.push({
        text: t('dashboard.alert_critical', { count: s.criticalGrievances }),
        tab: 'grievances',
      });
    }
    if (s.delayedProjects > 0) {
      out.push({
        text: t('dashboard.alert_delayed', { count: s.delayedProjects }),
        tab: 'projects',
      });
    }
    if (s.pendingDocuments > 0) {
      out.push({
        text: t('dashboard.alert_documents', { count: s.pendingDocuments }),
        tab: 'citizens',
      });
    }
    const unspent = s.totalBudget - s.totalUtilized;
    if (unspent > 0) {
      out.push({
        text: t('dashboard.alert_budget', { amount: lakhs(unspent, isEnglish) }),
        tab: 'projects',
      });
    }
    return out;
  }, [s, t, isEnglish]);

  const budgetChart = useMemo(
    () =>
      (budgets.data ?? []).map((p) => ({
        name: (isEnglish ? p.name : p.nameMr).slice(0, 18),
        fullName: isEnglish ? p.name : p.nameMr,
        budget: p.budgetLakh,
        utilized: p.utilizedLakh,
      })),
    [budgets.data, isEnglish],
  );

  const departmentChart = useMemo(
    () =>
      (byDepartment.data ?? []).map((d) => ({
        name: (isEnglish ? d.label : d.labelMr || d.label).replace(
          / (Department|Cell|Board Liaison|Administration)$/,
          '',
        ),
        value: d.value,
      })),
    [byDepartment.data, isEnglish],
  );

  const loading = stats.loading || budgets.loading || byDepartment.loading;
  const error = stats.error || budgets.error || byDepartment.error;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="relative overflow-hidden rounded-xl bg-white border border-slate-200 shadow-sm p-6">
        <div className="absolute top-0 left-0 right-0 h-1.5 gov-tricolor-strip" />
        <div className="max-w-3xl space-y-2 mt-1">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-govnavy/10 text-govnavy text-[10px] font-bold uppercase tracking-wider border border-govnavy/15 select-none">
            <span>{t('dashboard.overview')}</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-govblue-900 tracking-tight leading-tight m-0 font-sans">
            {village.data
              ? isEnglish
                ? `${village.data.name} Gram Panchayat`
                : `${village.data.nameMr} ग्रामपंचायत`
              : t('app_title')}
          </h1>
          <p className="text-slate-600 text-xs sm:text-sm leading-relaxed">
            {village.data
              ? isEnglish
                ? `${village.data.blockName} block, ${village.data.districtName} district, ${village.data.stateName}. LGD code ${village.data.lgdCode ?? '—'}${
                    village.data.population2011
                      ? ` · Census 2011 population ${village.data.population2011.toLocaleString('en-IN')}`
                      : ''
                  }.`
                : `${village.data.blockNameMr} तालुका, ${village.data.districtNameMr} जिल्हा. एलजीडी क्रमांक ${village.data.lgdCode ?? '—'}.`
              : t('dashboard.subtitle')}
          </p>
        </div>
      </div>

      {error && <ErrorNotice message={error} onRetry={stats.refetch} />}

      {loading && (
        <div className="flex items-center justify-center gap-2 py-16 text-slate-400">
          <Loader2 size={18} className="animate-spin" />
          <span className="text-xs font-bold uppercase tracking-wider">
            {t('dashboard.loading')}
          </span>
        </div>
      )}

      {!loading && s && (
        <>
          {/* Metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {metrics.map((card) => {
              const Icon = card.icon;
              return (
                <button
                  key={card.label}
                  onClick={() => setCurrentTab(card.tab)}
                  className={`text-left bg-white rounded-xl p-5 border border-slate-200 border-t-4 ${card.border} shadow-sm hover:shadow-md transition-all flex items-center justify-between gap-3`}
                >
                  <div className="space-y-1 min-w-0">
                    <span className="text-slate-500 text-[10px] font-bold uppercase tracking-wider block">
                      {card.label}
                    </span>
                    <span className="text-2xl sm:text-3xl font-extrabold text-govblue-900 block tabular-nums">
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
                </button>
              );
            })}
          </div>

          {/* Attention needed */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 border-t-4 border-govsaffron">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4 border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2.5">
                <span className="w-8 h-8 rounded-lg bg-orange-50 flex items-center justify-center border border-orange-200">
                  <Bot size={18} className="text-govsaffron" />
                </span>
                <div>
                  <h2 className="text-sm font-bold text-govblue-900 m-0 tracking-wide uppercase">
                    {t('dashboard.needs_attention')}
                  </h2>
                  <p className="text-[10px] text-slate-500 font-medium m-0">
                    {t('dashboard.needs_attention_sub')}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setCurrentTab('ai_assistant')}
                className="text-xs font-bold text-govnavy hover:text-govblue-500 flex items-center gap-1 transition-colors"
              >
                <span>{t('dashboard.ask_assistant')}</span>
                <ChevronRight size={14} />
              </button>
            </div>

            {insights.length === 0 ? (
              <p className="flex items-center gap-2 text-xs text-govgreen font-semibold m-0 py-2">
                <CheckCircle2 size={15} />
                {t('dashboard.all_clear')}
              </p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {insights.map((insight, i) => (
                  <div
                    key={i}
                    className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 flex items-start justify-between gap-3"
                  >
                    <p className="text-xs text-slate-700 leading-relaxed font-semibold m-0">
                      {insight.text}
                    </p>
                    <button
                      onClick={() => setCurrentTab(insight.tab)}
                      className="text-[10px] font-bold text-govnavy hover:text-govblue-600 whitespace-nowrap flex-shrink-0 mt-0.5"
                    >
                      {t('dashboard.view_details')}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm lg:col-span-2 space-y-3">
              <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-slate-100 pb-2 m-0">
                {t('dashboard.chart_budget')}
              </h2>
              {budgetChart.length ? (
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={budgetChart}
                      margin={{ top: 8, right: 8, left: -18, bottom: 0 }}
                      barGap={2}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
                      <XAxis
                        dataKey="name"
                        stroke="#94a3b8"
                        fontSize={10}
                        tickLine={false}
                        axisLine={{ stroke: '#e2e8f0' }}
                      />
                      <YAxis
                        stroke="#94a3b8"
                        fontSize={10}
                        tickLine={false}
                        axisLine={false}
                        unit="L"
                      />
                      <Tooltip
                        cursor={{ fill: 'rgba(37,71,168,0.05)' }}
                        contentStyle={{
                          backgroundColor: '#ffffff',
                          borderColor: '#e2e8f0',
                          borderRadius: 8,
                          fontSize: 12,
                        }}
                        labelFormatter={(_, payload) =>
                          payload?.[0]?.payload?.fullName ?? ''
                        }
                        formatter={(value) => `₹${value} ${isEnglish ? 'lakh' : 'लाख'}`}
                      />
                      <Legend
                        wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
                        iconType="circle"
                        iconSize={8}
                      />
                      <Bar
                        name={t('dashboard.legend_sanctioned')}
                        dataKey="budget"
                        fill={SERIES_BUDGET}
                        radius={[4, 4, 0, 0]}
                      />
                      <Bar
                        name={t('dashboard.legend_spent')}
                        dataKey="utilized"
                        fill={SERIES_SPENT}
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="text-xs text-slate-400 py-8 text-center m-0">
                  {t('dashboard.no_projects')}
                </p>
              )}
            </div>

            {/* Grievances by department.
                A horizontal bar, not the old donut: the question is "which
                department is carrying the most", which is a magnitude
                comparison. One series, so no legend and no categorical palette
                — the values are labelled directly. */}
            <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm space-y-3">
              <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-slate-100 pb-2 m-0">
                {t('dashboard.chart_departments')}
              </h2>
              {departmentChart.length ? (
                <div style={{ height: Math.max(180, departmentChart.length * 44) }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={departmentChart}
                      layout="vertical"
                      margin={{ top: 4, right: 28, left: 4, bottom: 4 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" horizontal={false} />
                      <XAxis type="number" hide />
                      <YAxis
                        type="category"
                        dataKey="name"
                        width={104}
                        stroke="#64748b"
                        fontSize={10}
                        tickLine={false}
                        axisLine={false}
                      />
                      <Tooltip
                        cursor={{ fill: 'rgba(37,71,168,0.05)' }}
                        contentStyle={{
                          backgroundColor: '#ffffff',
                          borderColor: '#e2e8f0',
                          borderRadius: 8,
                          fontSize: 12,
                        }}
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
              ) : (
                <p className="text-xs text-slate-400 py-8 text-center m-0">
                  {t('dashboard.no_grievances')}
                </p>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};
