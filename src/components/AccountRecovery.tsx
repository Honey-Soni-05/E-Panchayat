/**
 * Password recovery, run from the Panchayat counter.
 *
 * There is no email or SMS gateway in this deployment, so a reset link cannot
 * be sent anywhere. The channel a Gram Panchayat actually has is the office
 * itself: a resident who cannot sign in comes in, an officer identifies them
 * against the village register, and issues a code that the resident redeems
 * for a password of their own choosing.
 *
 * Two things this screen has to get right, because the API cannot enforce
 * either on its own:
 *
 *  - **The code is shown exactly once.** Only a bcrypt hash is stored, so there
 *    is no endpoint that can show it again. If the officer closes the panel
 *    before writing it down, the only remedy is issuing another — which voids
 *    the first. The UI says so before revealing it, and does not tuck it into
 *    a toast that disappears on its own.
 *  - **The officer must not learn the password.** They hand over a code that
 *    permits setting one; what gets set happens between the resident and the
 *    server, on the sign-in screen. This panel never asks for a password and
 *    has no field to type one into.
 *
 * The account list is scoped server-side: an officer sees the resident accounts
 * of their own village and nothing else. That is the same rule the reset
 * enforces, so nothing here can be offered and then refused.
 */

import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  KeyRound,
  Search,
  Copy,
  Check,
  AlertTriangle,
  ShieldCheck,
  Loader2,
  X,
} from 'lucide-react';

import { api, type PasswordResetIssued, type User } from '../lib/api';
import { useQuery } from '../lib/useApi';
import { EmptyState, ErrorNotice } from './schemes/SchemeBits';

const formatExpiry = (iso: string, isEnglish: boolean) =>
  new Date(iso).toLocaleString(isEnglish ? 'en-IN' : 'mr-IN', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });

export const AccountRecovery: React.FC = () => {
  const { i18n } = useTranslation();
  const isEnglish = i18n.language === 'en';

  const accounts = useQuery<User[]>(() => api.auth.users(), []);
  const [search, setSearch] = useState('');
  const [issuing, setIssuing] = useState<string | null>(null);
  const [issued, setIssued] = useState<PasswordResetIssued | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const rows = useMemo(() => {
    const all = accounts.data ?? [];
    const needle = search.trim().toLowerCase();
    if (!needle) return all;
    return all.filter(
      (a) =>
        a.fullName.toLowerCase().includes(needle) ||
        a.email.toLowerCase().includes(needle),
    );
  }, [accounts.data, search]);

  const issue = async (account: User) => {
    setFailure(null);
    setIssuing(account.id);
    setCopied(false);
    try {
      setIssued(await api.auth.issuePasswordReset(account.id));
    } catch (err) {
      setFailure(err instanceof Error ? err.message : String(err));
    } finally {
      setIssuing(null);
    }
  };

  const copyCode = async () => {
    if (!issued) return;
    try {
      await navigator.clipboard.writeText(issued.code);
      setCopied(true);
    } catch {
      // Clipboard access can be refused; the code is on screen to be read.
      setCopied(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-govblue-900 tracking-tight m-0">
          {isEnglish ? 'Account Recovery' : 'खाते पुनर्प्राप्ती'}
        </h1>
        <p className="text-xs text-slate-500 mt-1 m-0 max-w-3xl">
          {isEnglish
            ? 'For a resident who cannot sign in. Identify them against the village register first, then issue a one-time code and hand it over. They choose their own new password — you never see it.'
            : 'जो रहिवासी साइन इन करू शकत नाही त्यांच्यासाठी. आधी गावाच्या नोंदवहीत त्यांची ओळख पटवा, मग एक-वेळ कोड तयार करून द्या. नवीन संकेतशब्द ते स्वतः ठरवतात — तो तुम्हाला दिसत नाही.'}
        </p>
      </div>

      {/* The code, shown once. Deliberately a panel that has to be dismissed by
          hand rather than a toast that vanishes on a timer. */}
      {issued && (
        <div className="rounded-2xl border-2 border-govgreen/40 bg-emerald-50/60 p-5 space-y-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <ShieldCheck size={20} className="text-govgreen mt-0.5 flex-shrink-0" />
              <div>
                <h2 className="text-sm font-extrabold text-govblue-900 m-0">
                  {isEnglish
                    ? `Reset code for ${issued.userName}`
                    : `${issued.userName} यांच्यासाठी कोड`}
                </h2>
                <p className="text-[11px] text-slate-600 m-0 mt-0.5">
                  {issued.userEmail} ·{' '}
                  {isEnglish ? 'valid until' : 'वैध'}{' '}
                  {formatExpiry(issued.expiresAt, isEnglish)}
                </p>
              </div>
            </div>
            <button
              onClick={() => setIssued(null)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-white/70 transition-colors flex-shrink-0"
              aria-label={isEnglish ? 'Dismiss' : 'बंद करा'}
            >
              <X size={16} />
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <code className="text-2xl font-black tracking-[0.2em] text-govblue-900 bg-white border-2 border-govgreen/30 rounded-xl px-5 py-3 select-all">
              {issued.code}
            </code>
            <button
              onClick={copyCode}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white border border-slate-300 text-xs font-bold text-slate-700 hover:bg-slate-50 transition-colors"
            >
              {copied ? <Check size={14} className="text-govgreen" /> : <Copy size={14} />}
              {copied
                ? isEnglish
                  ? 'Copied'
                  : 'कॉपी झाले'
                : isEnglish
                  ? 'Copy'
                  : 'कॉपी करा'}
            </button>
          </div>

          <div className="flex items-start gap-2 text-[11px] text-amber-900 bg-amber-50 border border-amber-300 rounded-lg px-3 py-2">
            <AlertTriangle size={14} className="mt-0.5 flex-shrink-0" />
            <p className="m-0 leading-normal">
              {isEnglish
                ? 'Write this down before closing. It is stored only as a hash, so it cannot be shown again — issuing another code is the only remedy, and it voids this one. Tell the resident to enter it on the sign-in screen under “I have a reset code”.'
                : 'बंद करण्यापूर्वी हा कोड लिहून घ्या. तो फक्त हॅश स्वरूपात साठवला जातो, त्यामुळे पुन्हा दाखवता येणार नाही — नवीन कोड तयार करणे हाच पर्याय, आणि त्याने हा कोड रद्द होतो. रहिवाशाला साइन-इन स्क्रीनवर “माझ्याकडे रीसेट कोड आहे” मधून तो टाकायला सांगा.'}
            </p>
          </div>
        </div>
      )}

      {failure && <ErrorNotice message={failure} onRetry={() => setFailure(null)} />}
      {accounts.error && <ErrorNotice message={accounts.error} onRetry={accounts.refetch} />}

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
        <div className="p-4 border-b border-slate-100 flex items-center gap-2">
          <Search size={15} className="text-slate-400 flex-shrink-0" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={
              isEnglish ? 'Search by name or email' : 'नाव किंवा ईमेलने शोधा'
            }
            className="flex-1 text-sm outline-none placeholder:text-slate-400"
          />
          {accounts.data && (
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 tabular-nums">
              {rows.length}/{accounts.data.length}
            </span>
          )}
        </div>

        {accounts.loading && (
          <div className="flex items-center justify-center gap-2 py-12 text-slate-400">
            <Loader2 size={16} className="animate-spin" />
            <span className="text-xs font-bold uppercase tracking-wider">
              {isEnglish ? 'Loading accounts' : 'खाती लोड होत आहेत'}
            </span>
          </div>
        )}

        {!accounts.loading && !accounts.error && rows.length === 0 && (
          <EmptyState
            title={isEnglish ? 'No matching account' : 'जुळणारे खाते नाही'}
            hint={
              isEnglish
                ? 'Only residents of your own Gram Panchayat who already hold a portal account appear here. A resident with no account applies from the sign-in screen instead.'
                : 'फक्त तुमच्या ग्रामपंचायतीतील, ज्यांचे पोर्टल खाते आधीच आहे असे रहिवासी येथे दिसतात. खाते नसलेल्या रहिवाशाने साइन-इन स्क्रीनवरून अर्ज करावा.'
            }
          />
        )}

        {rows.length > 0 && (
          <ul className="divide-y divide-slate-100 m-0 p-0 list-none">
            {rows.map((account) => (
              <li
                key={account.id}
                className="p-4 flex items-center justify-between gap-4 hover:bg-slate-50/70 transition-colors"
              >
                <div className="min-w-0">
                  <p className="text-sm font-bold text-slate-800 m-0 truncate">
                    {account.fullName}
                  </p>
                  <p className="text-[11px] text-slate-500 m-0 truncate">
                    {account.email}
                    {account.citizenId ? ` · ${account.citizenId}` : ''}
                    {account.isActive
                      ? ''
                      : isEnglish
                        ? ' · deactivated'
                        : ' · निष्क्रिय'}
                  </p>
                </div>
                <button
                  onClick={() => issue(account)}
                  disabled={issuing !== null}
                  className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-govnavy text-white text-xs font-bold hover:bg-govblue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-shrink-0"
                >
                  {issuing === account.id ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <KeyRound size={14} />
                  )}
                  {isEnglish ? 'Issue reset code' : 'रीसेट कोड द्या'}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};
