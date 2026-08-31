import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  UserPlus,
  Phone,
  MapPin,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  AlertTriangle,
  Inbox,
} from 'lucide-react';

import { api } from '../lib/api';
import type { RegistrationRequest, RegistrationStatus, SuggestedMatch } from '../lib/api';
import { useQuery, useMutation } from '../lib/useApi';

/**
 * The officer's queue of account applications.
 *
 * The whole screen exists to make one decision safe: which resident record
 * this applicant actually is. A citizen account can read that person's income,
 * documents, family and grievances, so approving the wrong match hands one
 * villager another villager's file.
 *
 * The server ranks candidates and says why; it does not choose. Nothing here
 * approves automatically, however confident a suggestion looks, and an
 * application with no plausible match is meant to be sent back to the office
 * counter rather than approved on a name that is merely close.
 */

const STATUS_STYLES: Record<RegistrationStatus, string> = {
  pending: 'bg-amber-50 text-amber-800 border-amber-200',
  approved: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  rejected: 'bg-rose-50 text-rose-700 border-rose-200',
};

const formatDate = (iso: string, language: string) =>
  new Date(iso).toLocaleDateString(language === 'mr' ? 'mr-IN' : 'en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });

const MatchRow: React.FC<{
  match: SuggestedMatch;
  selected: boolean;
  onSelect: () => void;
}> = ({ match, selected, onSelect }) => {
  const { t, i18n } = useTranslation();
  const blocked = match.alreadyHasAccount;

  return (
    <button
      type="button"
      disabled={blocked}
      onClick={onSelect}
      className={`w-full text-left p-3 rounded-lg border transition-all ${
        blocked
          ? 'border-slate-200 bg-slate-50 opacity-70 cursor-not-allowed'
          : selected
            ? 'border-govnavy bg-govnavy/5 ring-2 ring-govnavy/20'
            : 'border-slate-200 bg-white hover:border-govnavy/40'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-bold text-govblue-900 truncate">
            {i18n.language === 'mr' ? match.nameMr : match.name}
          </p>
          <p className="text-[11px] text-slate-500 font-semibold mt-0.5">
            {match.citizenId} · {match.age} · {t('auth.ward')} {match.ward}
            {match.phone ? ` · ${match.phone}` : ''}
          </p>
          <p className="text-[11px] text-slate-500 mt-1.5 leading-relaxed">
            <span className="font-bold text-slate-400 uppercase text-[9px] tracking-wide">
              {t('registrations.why')}:{' '}
            </span>
            {match.reasons.join(' · ')}
          </p>
        </div>

        <div className="shrink-0 text-right">
          {blocked ? (
            <span className="inline-block px-2 py-0.5 rounded text-[10px] font-bold bg-slate-200 text-slate-600">
              {t('registrations.already_has_account')}
            </span>
          ) : (
            <span
              className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                selected ? 'bg-govnavy text-white' : 'bg-slate-100 text-slate-600'
              }`}
            >
              {selected ? t('registrations.selected') : t('registrations.select_resident')}
            </span>
          )}
          <p className="text-[10px] text-slate-400 font-mono mt-1">
            {Math.round(match.confidence * 100)}%
          </p>
        </div>
      </div>
    </button>
  );
};

const ApplicationCard: React.FC<{
  request: RegistrationRequest;
  onDecided: () => void;
}> = ({ request, onDecided }) => {
  const { t, i18n } = useTranslation();
  const [chosen, setChosen] = useState<string | null>(null);
  const [note, setNote] = useState('');

  const decide = useMutation(
    (approve: boolean) =>
      api.auth.decideRegistration(request.id, {
        approve,
        citizenId: approve ? chosen ?? undefined : undefined,
        reviewNote: note.trim() || undefined,
      }),
    onDecided,
  );

  const settled = request.status !== 'pending';

  return (
    <article className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <header className="p-4 border-b border-slate-100 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-base font-black text-govblue-900 truncate m-0">
            {request.fullName}
          </h3>
          <p className="text-xs text-slate-500 font-semibold truncate">{request.email}</p>
          <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-[11px] text-slate-500 font-semibold">
            <span className="inline-flex items-center gap-1">
              <Clock size={12} />
              {t('registrations.applied')} {formatDate(request.createdAt, i18n.language)}
            </span>
            {request.phone && (
              <span className="inline-flex items-center gap-1">
                <Phone size={12} />
                {request.phone}
              </span>
            )}
            {!request.villageId && (
              <span className="inline-flex items-center gap-1 text-amber-700">
                <MapPin size={12} />
                {t('registrations.no_village')}
              </span>
            )}
            {request.claimedWard !== null && (
              <span>
                {t('registrations.claims_ward')} {request.claimedWard}
              </span>
            )}
          </div>
        </div>

        <span
          className={`shrink-0 px-2.5 py-1 rounded border text-[10px] font-black uppercase ${
            STATUS_STYLES[request.status]
          }`}
        >
          {t(`registrations.${request.status}`)}
        </span>
      </header>

      {request.note && (
        <p className="px-4 pt-3 text-xs text-slate-600 leading-relaxed italic">
          “{request.note}”
        </p>
      )}

      {!settled && (
        <div className="p-4 space-y-3">
          <p className="text-[10px] font-black uppercase tracking-wide text-slate-400">
            {t('registrations.candidates')}
          </p>

          {request.suggestedMatches.length === 0 ? (
            <div className="flex gap-2 p-3 rounded bg-amber-50 border border-amber-200 text-[11px] text-amber-900 font-semibold leading-relaxed">
              <AlertTriangle size={16} className="shrink-0 mt-0.5" />
              <span>{t('registrations.no_candidates')}</span>
            </div>
          ) : (
            <>
              <div className="space-y-2">
                {request.suggestedMatches.map((match) => (
                  <MatchRow
                    key={match.citizenId}
                    match={match}
                    selected={chosen === match.citizenId}
                    onSelect={() => setChosen(match.citizenId)}
                  />
                ))}
              </div>
              <p className="text-[10px] text-slate-400 leading-relaxed">
                {t('registrations.approve_hint')}
              </p>
            </>
          )}

          <div className="space-y-1.5">
            <label
              htmlFor={`note-${request.id}`}
              className="block text-[10px] font-black uppercase tracking-wide text-slate-400"
            >
              {t('registrations.review_note')}
            </label>
            <textarea
              id={`note-${request.id}`}
              rows={2}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded text-xs text-slate-800 font-medium focus:outline-none focus:ring-2 focus:ring-govnavy/30"
            />
          </div>

          {decide.error && (
            <p role="alert" className="text-xs text-rose-700 font-semibold">
              {decide.error}
            </p>
          )}

          <div className="flex gap-2 pt-1">
            <button
              type="button"
              disabled={!chosen || decide.saving}
              onClick={() => decide.run(true)}
              className="flex-1 py-2.5 bg-govgreen hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded font-bold text-xs flex items-center justify-center gap-1.5 transition-all"
            >
              {decide.saving ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <CheckCircle2 size={14} />
              )}
              <span>{t('registrations.approve')}</span>
            </button>
            <button
              type="button"
              disabled={decide.saving}
              onClick={() => decide.run(false)}
              className="px-4 py-2.5 border border-rose-200 text-rose-700 hover:bg-rose-50 disabled:opacity-50 rounded font-bold text-xs flex items-center justify-center gap-1.5 transition-all"
            >
              <XCircle size={14} />
              <span>{t('registrations.reject')}</span>
            </button>
          </div>
        </div>
      )}

      {settled && request.reviewNote && (
        <p className="px-4 pb-4 pt-2 text-xs text-slate-600 leading-relaxed">
          {request.reviewNote}
        </p>
      )}
    </article>
  );
};

export const RegistrationReview: React.FC = () => {
  const { t } = useTranslation();
  const [filter, setFilter] = useState<'pending' | 'all'>('pending');

  const { data, loading, error, refetch } = useQuery(
    () => api.auth.registrations(filter),
    [filter],
  );

  const requests = data ?? [];

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-black text-govblue-900 tracking-tight m-0 flex items-center gap-2">
            <UserPlus size={20} className="text-govnavy" />
            {t('registrations.title')}
          </h2>
          <p className="text-xs text-slate-500 font-semibold mt-1">
            {t('registrations.subtitle')}
          </p>
        </div>

        <div className="flex gap-1 bg-slate-100 p-1 rounded-lg border border-slate-200">
          {(['pending', 'all'] as const).map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => setFilter(key)}
              className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all ${
                filter === key
                  ? 'bg-white text-govnavy shadow-sm border border-slate-200'
                  : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              {t(`registrations.filter_${key}`)}
            </button>
          ))}
        </div>
      </header>

      {error && (
        <p role="alert" className="p-3 rounded bg-rose-50 border border-rose-200 text-xs text-rose-700 font-semibold">
          {error}
        </p>
      )}

      {loading ? (
        <p className="flex items-center gap-2 text-xs text-slate-500 font-semibold">
          <Loader2 size={14} className="animate-spin" />
          {t('registrations.loading')}
        </p>
      ) : requests.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-xl border border-dashed border-slate-300">
          <Inbox size={32} className="mx-auto text-slate-300" />
          <p className="text-sm font-bold text-slate-600 mt-3">{t('registrations.empty')}</p>
          <p className="text-xs text-slate-400 mt-1">{t('registrations.empty_hint')}</p>
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {requests.map((request) => (
            <ApplicationCard key={request.id} request={request} onDecided={refetch} />
          ))}
        </div>
      )}
    </div>
  );
};
