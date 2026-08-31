/**
 * Every Gram Panchayat in the block, with its headline numbers.
 *
 * Admin only. This screen exists because the administrative hierarchy is
 * modelled properly — state, district, block, village, each with its official
 * Local Government Directory code — so a district rollup is one query rather
 * than a separate system.
 */

import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Building2, Loader2, Search, AlertTriangle } from 'lucide-react';

import { api, type VillageSummary } from '../lib/api';
import { useQuery } from '../lib/useApi';
import { EmptyState, ErrorNotice } from './schemes/SchemeBits';

const STATUS_LABEL: Record<string, { en: string; mr: string; classes: string }> = {
  active: {
    en: 'Gram Panchayat',
    mr: 'ग्रामपंचायत',
    classes: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  },
  merged_into_municipal_corporation: {
    en: 'Merged into PMC',
    mr: 'महानगरपालिकेत विलीन',
    classes: 'bg-slate-100 text-slate-600 border-slate-300',
  },
  uncertain: {
    en: 'Status unconfirmed',
    mr: 'स्थिती अनिश्चित',
    classes: 'bg-amber-50 text-amber-800 border-amber-200',
  },
};

export const DistrictOverview: React.FC = () => {
  const { i18n } = useTranslation();
  const isEnglish = i18n.language === 'en';
  const [search, setSearch] = useState('');
  const [activeOnly, setActiveOnly] = useState(false);

  const villages = useQuery<VillageSummary[]>(() => api.districts.summary(), []);
  const rows = villages.data ?? [];

  const visible = useMemo(() => {
    let list = rows;
    if (activeOnly) list = list.filter((v) => v.gramPanchayatStatus === 'active');
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter(
        (v) => v.name.toLowerCase().includes(q) || v.nameMr.includes(search.trim()),
      );
    }
    return list;
  }, [rows, activeOnly, search]);

  const totals = useMemo(
    () => ({
      villages: rows.length,
      active: rows.filter((v) => v.gramPanchayatStatus === 'active').length,
      citizens: rows.reduce((n, v) => n + v.registeredCitizens, 0),
      grievances: rows.reduce((n, v) => n + v.openGrievances, 0),
      population: rows.reduce((n, v) => n + (v.population2011 ?? 0), 0),
    }),
    [rows],
  );

  return (
    <div className="space-y-5">
      <header className="space-y-1">
        <div className="flex items-center gap-2">
          <Building2 size={20} className="text-govnavy" />
          <h2 className="text-lg font-extrabold text-govblue-900 tracking-tight m-0">
            {isEnglish ? 'Haveli Block Overview' : 'हवेली तालुका आढावा'}
          </h2>
        </div>
        <p className="text-xs text-slate-500 m-0">
          {isEnglish
            ? 'Pune district, Maharashtra. Village codes are from the Local Government Directory.'
            : 'पुणे जिल्हा, महाराष्ट्र. गाव संकेतांक स्थानिक शासन निर्देशिकेतील.'}
        </p>
      </header>

      {villages.error && <ErrorNotice message={villages.error} onRetry={villages.refetch} />}

      {villages.loading ? (
        <div className="flex items-center justify-center gap-2 py-16 text-slate-400">
          <Loader2 size={18} className="animate-spin" />
          <span className="text-xs font-bold uppercase tracking-wider">
            {isEnglish ? 'Loading the block' : 'तालुका माहिती लोड होत आहे'}
          </span>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {[
              {
                label: isEnglish ? 'Villages' : 'गावे',
                value: totals.villages,
                sub: isEnglish
                  ? `${totals.active} with a Gram Panchayat`
                  : `${totals.active} ग्रामपंचायतीसह`,
              },
              {
                label: isEnglish ? 'Population (2011)' : 'लोकसंख्या (२०११)',
                value: totals.population.toLocaleString('en-IN'),
                sub: isEnglish ? 'Census figures' : 'जनगणना आकडेवारी',
              },
              {
                label: isEnglish ? 'Registered residents' : 'नोंदणीकृत रहिवासी',
                value: totals.citizens,
                sub: isEnglish ? 'On this platform' : 'या प्रणालीवर',
              },
              {
                label: isEnglish ? 'Open grievances' : 'प्रलंबित तक्रारी',
                value: totals.grievances,
                sub: isEnglish ? 'Across the block' : 'संपूर्ण तालुक्यात',
              },
            ].map((stat) => (
              <div
                key={stat.label}
                className="bg-white rounded-xl border border-slate-200 p-4 space-y-1"
              >
                <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 m-0">
                  {stat.label}
                </p>
                <p className="text-2xl font-black text-govnavy tabular-nums m-0">{stat.value}</p>
                <p className="text-[11px] text-slate-400 m-0">{stat.sub}</p>
              </div>
            ))}
          </div>

          <div className="flex flex-wrap gap-2 items-center">
            <div className="relative flex-1 min-w-[200px]">
              <Search size={14} className="absolute left-3 top-2.5 text-slate-400" />
              <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={isEnglish ? 'Search villages' : 'गावे शोधा'}
                className="w-full pl-9 pr-3 py-2 text-xs border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-govnavy/25"
              />
            </div>
            <label className="flex items-center gap-2 text-xs font-bold text-slate-600 px-3 py-2 border border-slate-200 rounded-lg bg-white cursor-pointer">
              <input
                type="checkbox"
                checked={activeOnly}
                onChange={(e) => setActiveOnly(e.target.checked)}
                className="accent-govnavy"
              />
              {isEnglish ? 'Only active Panchayats' : 'फक्त कार्यरत ग्रामपंचायती'}
            </label>
          </div>

          {!visible.length ? (
            <EmptyState title={isEnglish ? 'No villages match' : 'जुळणारे गाव नाही'} />
          ) : (
            <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
              <table className="w-full min-w-[720px] text-left">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50">
                    {[
                      isEnglish ? 'Village' : 'गाव',
                      isEnglish ? 'LGD code' : 'एलजीडी क्रमांक',
                      isEnglish ? 'Population' : 'लोकसंख्या',
                      isEnglish ? 'Residents' : 'रहिवासी',
                      isEnglish ? 'Open grievances' : 'तक्रारी',
                      isEnglish ? 'Active projects' : 'प्रकल्प',
                      isEnglish ? 'Status' : 'स्थिती',
                    ].map((h) => (
                      <th
                        key={h}
                        className="py-2.5 px-4 text-[10px] font-bold uppercase tracking-wider text-slate-400 whitespace-nowrap"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {visible.map((v) => {
                    const status = STATUS_LABEL[v.gramPanchayatStatus] ?? STATUS_LABEL.uncertain;
                    return (
                      <tr key={v.id} className="border-b border-slate-50 last:border-0">
                        <td className="py-3 px-4 text-xs font-bold text-slate-800 whitespace-nowrap">
                          {isEnglish ? v.name : v.nameMr}
                        </td>
                        <td className="py-3 px-4 text-xs text-slate-500 tabular-nums">
                          {v.lgdCode ?? '—'}
                        </td>
                        <td className="py-3 px-4 text-xs text-slate-600 tabular-nums">
                          {v.population2011?.toLocaleString('en-IN') ?? '—'}
                        </td>
                        <td className="py-3 px-4 text-xs tabular-nums">
                          <span
                            className={
                              v.registeredCitizens
                                ? 'font-bold text-govnavy'
                                : 'text-slate-300'
                            }
                          >
                            {v.registeredCitizens || '—'}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-xs tabular-nums">
                          <span
                            className={
                              v.openGrievances ? 'font-bold text-govsaffron' : 'text-slate-300'
                            }
                          >
                            {v.openGrievances || '—'}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-xs text-slate-600 tabular-nums">
                          {v.activeProjects || '—'}
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold border whitespace-nowrap ${status.classes}`}
                          >
                            {isEnglish ? status.en : status.mr}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          <p className="flex items-start gap-2 text-[11px] text-slate-500 bg-slate-50 border border-slate-200 rounded-lg p-3 m-0 leading-relaxed">
            <AlertTriangle size={12} className="mt-0.5 flex-shrink-0 text-amber-500" />
            {isEnglish
              ? 'Villages marked "Merged into PMC" were absorbed into Pune Municipal Corporation in 2017 and 2021 and no longer have a Gram Panchayat. Those marked unconfirmed appear in the 2021 merger list but still held a local body code in the Local Government Directory snapshot used here — verify against a live LGD lookup before acting on them.'
              : '"महानगरपालिकेत विलीन" अशी नोंद असलेली गावे २०१७ व २०२१ मध्ये पुणे महानगरपालिकेत समाविष्ट झाली आहेत आणि तेथे ग्रामपंचायत नाही. "अनिश्चित" गावांची स्थिती अधिकृत नोंदीवरून तपासावी.'}
          </p>
        </>
      )}
    </div>
  );
};
