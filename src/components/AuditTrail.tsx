/**
 * The audit trail: who did what, to whose record.
 *
 * Admin only, and that is a privacy decision rather than a hierarchy one. This
 * table records which residents an officer has opened, so it is more revealing
 * than most of what it describes — an officer who could read it would learn
 * what their colleagues have been looking at.
 *
 * There is nothing here that writes. Events are recorded by middleware on the
 * server, and no route exists to amend or delete one, because a trail its
 * subjects can edit is not a trail. The two filters are the two questions it
 * exists to answer: everything that touched one record, and everything one
 * person did.
 *
 * What the trail deliberately does not hold is worth stating on the screen
 * rather than only in the code: no request bodies, and no rows for list
 * endpoints or the assistant. Otherwise a reader assumes the absence of an
 * event means the access did not happen.
 */

import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ScrollText, Filter, Loader2, Info, RotateCw } from 'lucide-react';

import { api, type AuditEvent } from '../lib/api';
import { useQuery } from '../lib/useApi';
import { EmptyState, ErrorNotice } from './schemes/SchemeBits';

/** Colour carries meaning here, so it is never the only signal — the verb is
 *  spelled out beside it. */
const ACTION_STYLES: Record<string, string> = {
  read: 'bg-slate-100 text-slate-600 border-slate-300',
  post: 'bg-govblue-50 text-govnavy border-govnavy/25',
  patch: 'bg-amber-50 text-amber-800 border-amber-300',
  put: 'bg-amber-50 text-amber-800 border-amber-300',
  delete: 'bg-rose-50 text-rose-700 border-rose-300',
};

const ENTITY_TYPES = [
  'citizen',
  'document',
  'grievance',
  'scheme',
  'project',
  'sabha_meeting',
  'user',
  'registration',
];

const timestamp = (iso: string, isEnglish: boolean) =>
  new Date(iso).toLocaleString(isEnglish ? 'en-IN' : 'mr-IN', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

export const AuditTrail: React.FC = () => {
  const { i18n } = useTranslation();
  const isEnglish = i18n.language === 'en';

  const [entityType, setEntityType] = useState('');
  const [entityId, setEntityId] = useState('');
  const [action, setAction] = useState('');
  // Applied filters are separate from the typed ones, so the list does not
  // refetch on every keystroke of an entity id.
  const [applied, setApplied] = useState({ entityType: '', entityId: '', action: '' });

  const events = useQuery<AuditEvent[]>(
    () =>
      api.audit.events({
        entityType: applied.entityType || undefined,
        entityId: applied.entityId || undefined,
        action: applied.action || undefined,
        limit: 200,
      }),
    [applied],
  );

  const rows = events.data ?? [];

  const refusedCount = useMemo(
    () => rows.filter((e) => e.statusCode >= 400).length,
    [rows],
  );

  const apply = () => setApplied({ entityType, entityId: entityId.trim(), action });
  const clear = () => {
    setEntityType('');
    setEntityId('');
    setAction('');
    setApplied({ entityType: '', entityId: '', action: '' });
  };

  const filtered = applied.entityType || applied.entityId || applied.action;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-govblue-900 tracking-tight m-0">
          {isEnglish ? 'Audit Trail' : 'लेखापरीक्षण नोंद'}
        </h1>
        <p className="text-xs text-slate-500 mt-1 m-0 max-w-3xl">
          {isEnglish
            ? 'Who did what, to whose record, and when. Recorded automatically for every change and every read that names one record. Nothing here can be edited or deleted.'
            : 'कोणी, कोणाच्या नोंदीवर, काय आणि केव्हा केले. प्रत्येक बदलाची आणि एका नोंदीचा उल्लेख करणाऱ्या प्रत्येक वाचनाची नोंद आपोआप होते. येथील काहीही बदलता किंवा हटवता येत नाही.'}
        </p>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter size={14} className="text-govnavy" />
          <h2 className="text-[11px] font-bold tracking-widest m-0 uppercase text-slate-500">
            {isEnglish ? 'Filter' : 'गाळणी'}
          </h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              {isEnglish ? 'Record type' : 'नोंद प्रकार'}
            </span>
            <select
              value={entityType}
              onChange={(e) => setEntityType(e.target.value)}
              className="text-xs border border-slate-200 rounded-lg px-2.5 py-2 bg-white outline-none focus:border-govnavy"
            >
              <option value="">{isEnglish ? 'Any' : 'कोणतीही'}</option>
              {ENTITY_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              {isEnglish ? 'Record ID' : 'नोंद क्रमांक'}
            </span>
            <input
              value={entityId}
              onChange={(e) => setEntityId(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && apply()}
              placeholder="cit_102"
              className="text-xs border border-slate-200 rounded-lg px-2.5 py-2 outline-none focus:border-govnavy placeholder:text-slate-300"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              {isEnglish ? 'Action' : 'क्रिया'}
            </span>
            <select
              value={action}
              onChange={(e) => setAction(e.target.value)}
              className="text-xs border border-slate-200 rounded-lg px-2.5 py-2 bg-white outline-none focus:border-govnavy"
            >
              <option value="">{isEnglish ? 'Any' : 'कोणतीही'}</option>
              {['read', 'post', 'patch', 'put', 'delete'].map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </label>

          <div className="flex items-end gap-2">
            <button
              onClick={apply}
              className="flex-1 px-3 py-2 rounded-lg bg-govnavy text-white text-xs font-bold hover:bg-govblue-700 transition-colors"
            >
              {isEnglish ? 'Apply' : 'लागू करा'}
            </button>
            {filtered && (
              <button
                onClick={clear}
                className="px-3 py-2 rounded-lg border border-slate-200 text-xs font-bold text-slate-600 hover:bg-slate-50 transition-colors"
              >
                {isEnglish ? 'Clear' : 'रिकामे'}
              </button>
            )}
            <button
              onClick={events.refetch}
              className="p-2 rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50 transition-colors"
              aria-label={isEnglish ? 'Refresh' : 'रिफ्रेश'}
            >
              <RotateCw size={14} />
            </button>
          </div>
        </div>
      </div>

      {events.error && <ErrorNotice message={events.error} onRetry={events.refetch} />}

      {events.loading && (
        <div className="flex items-center justify-center gap-2 py-16 text-slate-400">
          <Loader2 size={18} className="animate-spin" />
          <span className="text-xs font-bold uppercase tracking-wider">
            {isEnglish ? 'Loading events' : 'नोंदी लोड होत आहेत'}
          </span>
        </div>
      )}

      {!events.loading && !events.error && rows.length === 0 && (
        <EmptyState
          title={isEnglish ? 'No events match' : 'जुळणाऱ्या नोंदी नाहीत'}
          hint={
            isEnglish
              ? 'Nothing has been recorded for that filter. Remember the trail holds changes and reads that name one record — not directory listings, and not assistant questions.'
              : 'या गाळणीसाठी काहीही नोंदलेले नाही. लक्षात ठेवा की नोंदीत बदल आणि एका नोंदीचा उल्लेख करणारी वाचने असतात — यादी पाहणे किंवा सहाय्यकाचे प्रश्न नाहीत.'
          }
        />
      )}

      {rows.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <ScrollText size={15} className="text-govnavy" />
              <span className="text-[11px] font-bold uppercase tracking-widest text-slate-500">
                {isEnglish ? `${rows.length} events` : `${rows.length} नोंदी`}
              </span>
            </div>
            {refusedCount > 0 && (
              <span className="text-[10px] font-bold uppercase tracking-wider text-rose-700 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded">
                {isEnglish
                  ? `${refusedCount} refused`
                  : `${refusedCount} नाकारलेल्या`}
              </span>
            )}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="bg-slate-50 text-left">
                  {[
                    isEnglish ? 'When' : 'केव्हा',
                    isEnglish ? 'Who' : 'कोण',
                    isEnglish ? 'Did' : 'क्रिया',
                    isEnglish ? 'To' : 'कशावर',
                    isEnglish ? 'Result' : 'निकाल',
                  ].map((head) => (
                    <th
                      key={head}
                      className="px-4 py-2.5 font-bold uppercase tracking-wider text-[10px] text-slate-500 whitespace-nowrap"
                    >
                      {head}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((event) => (
                  <tr key={event.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="px-4 py-2.5 text-slate-500 whitespace-nowrap tabular-nums">
                      {timestamp(event.createdAt, isEnglish)}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="block font-semibold text-slate-800 truncate max-w-[220px]">
                        {event.actorEmail ?? (isEnglish ? 'deleted account' : 'हटवलेले खाते')}
                      </span>
                      {event.actorRole && (
                        <span className="block text-[10px] text-slate-400 uppercase tracking-wider">
                          {event.actorRole}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 whitespace-nowrap">
                      <span
                        className={`inline-block px-1.5 py-0.5 rounded border text-[10px] font-bold uppercase tracking-wider ${
                          ACTION_STYLES[event.action] ?? ACTION_STYLES.read
                        }`}
                      >
                        {event.action}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      {event.entityId ? (
                        <button
                          onClick={() => {
                            setEntityType(event.entityType ?? '');
                            setEntityId(event.entityId ?? '');
                            setApplied({
                              entityType: event.entityType ?? '',
                              entityId: event.entityId ?? '',
                              action: '',
                            });
                          }}
                          className="text-left group"
                          title={
                            isEnglish
                              ? 'Show everything that touched this record'
                              : 'या नोंदीला स्पर्श करणारे सर्व दाखवा'
                          }
                        >
                          <span className="block font-mono text-slate-800 group-hover:underline">
                            {event.entityId}
                          </span>
                          <span className="block text-[10px] text-slate-400">
                            {event.entityType}
                          </span>
                        </button>
                      ) : (
                        <span className="text-slate-300">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 whitespace-nowrap">
                      <span
                        className={`font-bold tabular-nums ${
                          event.statusCode >= 400 ? 'text-rose-600' : 'text-slate-400'
                        }`}
                      >
                        {event.statusCode}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* What is absent, said plainly — otherwise a missing event reads as
          proof that the access never happened. */}
      <div className="p-3 bg-govblue-50 rounded-lg border border-govnavy/15 flex items-start gap-2">
        <Info size={14} className="text-govnavy mt-0.5 flex-shrink-0" />
        <div className="text-[10px] text-slate-600 leading-normal space-y-1">
          <p className="m-0 font-semibold text-slate-700">
            {isEnglish ? 'What this trail does not hold' : 'या नोंदीत काय नाही'}
          </p>
          <p className="m-0">
            {isEnglish
              ? 'No request bodies — this table is kept and read later, which is the last place a resident’s income or a password being set should end up.'
              : 'कोणतीही विनंती-सामग्री नाही — ही नोंद दीर्घकाळ ठेवली जाते, त्यामुळे रहिवाशाचे उत्पन्न किंवा संकेतशब्द येथे असू नयेत.'}
          </p>
          <p className="m-0">
            {isEnglish
              ? 'No rows for directory listings or assistant questions. It answers “who opened this resident’s file”, not “who could have”.'
              : 'यादी पाहणे किंवा सहाय्यकाचे प्रश्न नोंदवले जात नाहीत. “ही नोंद कोणी उघडली” याचे उत्तर मिळते, “कोण उघडू शकत होते” याचे नाही.'}
          </p>
        </div>
      </div>
    </div>
  );
};
