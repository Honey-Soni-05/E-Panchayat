import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Lock,
  Mail,
  ShieldCheck,
  Globe,
  ArrowRight,
  Loader2,
  User as UserIcon,
  Phone,
  MapPin,
  CheckCircle2,
  Info,
} from 'lucide-react';

import { useAuth } from '../lib/auth';
import { api, ApiError } from '../lib/api';
import type { PublicVillage } from '../lib/api';

/**
 * Sign-in and sign-up.
 *
 * Credentials go to the server, which returns a signed token carrying the
 * role. The previous version compared `admin`/`admin` in this file and let
 * anyone open any resident's record by typing their citizen ID.
 *
 * Registration is deliberately only for residents, and it does not produce a
 * working account by itself: it produces an application that a Panchayat
 * officer must match against the village register. There is no "register as
 * officer" tab and there should never be one — an officer can read every
 * resident's income, documents and family details, so that account is created
 * by an administrator or it is not created.
 */

const DEMO_ACCOUNTS = {
  officer: { email: 'officer@panchayat.gov.in', label: 'Panchayat Officer' },
  citizen: { email: 'savita@citizen.panchayat.gov.in', label: 'Village Citizen' },
} as const;

type DemoRole = keyof typeof DEMO_ACCOUNTS;
type Mode = 'signin' | 'register';

const field =
  'w-full pl-9 pr-3 py-2 border border-slate-200 rounded text-slate-800 font-medium ' +
  'focus:outline-none focus:ring-2 focus:ring-govnavy/30';

export const Login: React.FC = () => {
  const { t, i18n } = useTranslation();
  const { signIn, loading, error, clearError } = useAuth();

  const [mode, setMode] = useState<Mode>('signin');
  const [tab, setTab] = useState<DemoRole>('officer');
  const [email, setEmail] = useState<string>(DEMO_ACCOUNTS.officer.email);
  const [password, setPassword] = useState('');

  // Registration form
  const [villages, setVillages] = useState<PublicVillage[]>([]);
  const [form, setForm] = useState({
    fullName: '',
    email: '',
    password: '',
    confirm: '',
    phone: '',
    villageId: '',
    claimedWard: '',
    note: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState<string | null>(null);

  const isEnglish = i18n.language === 'en';
  const toggleLanguage = () => i18n.changeLanguage(isEnglish ? 'mr' : 'en');

  // Loaded only when the form is open, and from the unauthenticated endpoint
  // that returns names alone.
  useEffect(() => {
    if (mode !== 'register' || villages.length) return;
    api.villages
      .publicList()
      .then(setVillages)
      .catch(() => setVillages([]));
  }, [mode, villages.length]);

  const selectTab = (next: DemoRole) => {
    setTab(next);
    setEmail(DEMO_ACCOUNTS[next].email);
    clearError();
  };

  const switchMode = (next: Mode) => {
    setMode(next);
    clearError();
    setFormError(null);
    setSubmitted(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await signIn(email, password);
    } catch {
      // The message is already in `error` and rendered below.
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (form.password !== form.confirm) {
      setFormError(t('auth.password_mismatch'));
      return;
    }
    if (form.password.length < 8) {
      setFormError(t('auth.password_too_short'));
      return;
    }

    setSubmitting(true);
    try {
      const ack = await api.auth.register({
        fullName: form.fullName.trim(),
        email: form.email.trim(),
        password: form.password,
        phone: form.phone.trim() || null,
        villageId: form.villageId || null,
        claimedWard: form.claimedWard ? Number(form.claimedWard) : null,
        note: form.note.trim() || null,
      });
      setSubmitted(ack.message);
    } catch (err) {
      setFormError(
        err instanceof ApiError ? err.message : t('auth.register_failed'),
      );
    } finally {
      setSubmitting(false);
    }
  };

  const set = (key: keyof typeof form) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>,
  ) => setForm((prev) => ({ ...prev, [key]: e.target.value }));

  return (
    <div className="min-h-screen flex flex-col justify-between bg-slate-50 relative selection:bg-govsaffron selection:text-white">
      <div className="w-full gov-tricolor-strip absolute top-0 left-0 z-20" />

      <header className="bg-white border-b border-slate-200 py-3.5 shadow-sm z-10">
        <div className="max-w-7xl mx-auto px-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-12 bg-slate-50 border border-slate-200 rounded flex items-center justify-center p-1 shadow-sm">
              <span className="text-lg">🦁</span>
            </div>
            <div className="flex flex-col text-left select-none">
              <span className="text-[9px] font-bold text-slate-400 uppercase">
                {t('landing.ministry')}
              </span>
              <span className="font-extrabold text-govnavy text-sm sm:text-base tracking-tight">
                {t('auth.sso_service')}
              </span>
            </div>
          </div>

          <button
            onClick={toggleLanguage}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 transition-colors text-xs font-bold shadow-sm"
          >
            <Globe size={14} className="text-govnavy" />
            <span>{isEnglish ? 'मराठी' : 'English'}</span>
          </button>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center py-12 px-6 z-10">
        <div className="w-full max-w-md bg-white rounded-xl border border-slate-200 p-6 sm:p-8 shadow-md border-t-4 border-govsaffron space-y-6">
          <div className="text-center space-y-1.5">
            <h1 className="text-lg sm:text-xl font-black text-govblue-900 tracking-tight uppercase m-0">
              {t('auth.portal_title')}
            </h1>
            <p className="text-xs text-slate-500 font-medium">
              {mode === 'signin' ? t('auth.subtitle') : t('auth.register_subtitle')}
            </p>
          </div>

          {/* Sign in vs apply. Not a role picker — see the note at the top. */}
          <div className="grid grid-cols-2 gap-2 bg-slate-100 p-1 rounded-lg border border-slate-200">
            {(['signin', 'register'] as Mode[]).map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => switchMode(key)}
                className={`py-2 rounded-md text-xs font-bold transition-all ${
                  mode === key
                    ? 'bg-white text-govnavy shadow-sm border border-slate-200'
                    : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                {key === 'signin' ? t('auth.tab_signin') : t('auth.tab_register')}
              </button>
            ))}
          </div>

          {mode === 'signin' ? (
            <>
              {/* Prefills a demo account. The account decides the role, not this tab. */}
              <div className="grid grid-cols-2 gap-2 text-[11px]">
                {(Object.keys(DEMO_ACCOUNTS) as DemoRole[]).map((key) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => selectTab(key)}
                    className={`py-1.5 rounded border font-bold transition-all ${
                      tab === key
                        ? 'border-govnavy/40 bg-govnavy/5 text-govnavy'
                        : 'border-slate-200 text-slate-500 hover:text-slate-900'
                    }`}
                  >
                    {t(`auth.demo_${key}`)}
                  </button>
                ))}
              </div>

              {error && (
                <div
                  role="alert"
                  className="p-3 rounded bg-rose-50 border border-rose-200 text-xs text-rose-700 font-semibold leading-relaxed"
                >
                  {error}
                </div>
              )}

              <form
                onSubmit={handleSubmit}
                className="space-y-4 text-xs font-bold text-slate-500 text-left"
              >
                <div className="space-y-1.5">
                  <label htmlFor="email" className="block">
                    {t('auth.email')}
                  </label>
                  <div className="relative">
                    <Mail size={14} className="absolute left-3 top-3 text-slate-400" />
                    <input
                      id="email"
                      type="email"
                      required
                      autoComplete="username"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="officer@panchayat.gov.in"
                      className={field}
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="password" className="block">
                    {t('auth.password')}
                  </label>
                  <div className="relative">
                    <Lock size={14} className="absolute left-3 top-3 text-slate-400" />
                    <input
                      id="password"
                      type="password"
                      required
                      autoComplete="current-password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      className={field}
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-2.5 bg-govnavy hover:bg-govblue-700 disabled:opacity-60 disabled:cursor-not-allowed text-white rounded font-bold text-xs sm:text-sm flex items-center justify-center gap-1.5 transition-all shadow-md mt-4"
                >
                  {loading ? (
                    <>
                      <Loader2 size={14} className="animate-spin" />
                      <span>{t('auth.signing_in')}</span>
                    </>
                  ) : (
                    <>
                      <span>{t('auth.sign_in')}</span>
                      <ArrowRight size={14} />
                    </>
                  )}
                </button>
              </form>

              <div className="pt-4 border-t border-slate-100 space-y-3">
                <div className="flex items-center justify-center gap-2 text-[10px] text-slate-400 font-medium">
                  <ShieldCheck size={14} className="text-govgreen" />
                  <span>{t('auth.jwt_note')}</span>
                </div>
                <p className="text-[10px] text-slate-400 text-center leading-relaxed">
                  {t('auth.demo_password')}{' '}
                  <span className="font-mono text-slate-500">Panchayat@2026</span>
                  <br />
                  {t('auth.demo_citizen_hint')}{' '}
                  <span className="font-mono text-slate-500">
                    firstname@citizen.panchayat.gov.in
                  </span>
                </p>
              </div>
            </>
          ) : submitted ? (
            <div className="space-y-4 text-center">
              <CheckCircle2 size={40} className="mx-auto text-govgreen" />
              <p className="text-sm font-bold text-govblue-900">
                {t('auth.application_sent')}
              </p>
              <p className="text-xs text-slate-600 leading-relaxed">{submitted}</p>
              <button
                type="button"
                onClick={() => switchMode('signin')}
                className="w-full py-2.5 bg-govnavy hover:bg-govblue-700 text-white rounded font-bold text-xs transition-all shadow-md"
              >
                {t('auth.back_to_sign_in')}
              </button>
            </div>
          ) : (
            <form
              onSubmit={handleRegister}
              className="space-y-4 text-xs font-bold text-slate-500 text-left"
            >
              {/* Said plainly, because an applicant who expects an instant login
                  will otherwise think the form is broken. */}
              <div className="flex gap-2 p-3 rounded bg-govnavy/5 border border-govnavy/15 text-[11px] text-govblue-900 font-semibold leading-relaxed">
                <Info size={16} className="shrink-0 mt-0.5 text-govnavy" />
                <span>{t('auth.register_explainer')}</span>
              </div>

              {formError && (
                <div
                  role="alert"
                  className="p-3 rounded bg-rose-50 border border-rose-200 text-xs text-rose-700 font-semibold leading-relaxed"
                >
                  {formError}
                </div>
              )}

              <div className="space-y-1.5">
                <label htmlFor="reg-name" className="block">
                  {t('auth.full_name')} *
                </label>
                <div className="relative">
                  <UserIcon size={14} className="absolute left-3 top-3 text-slate-400" />
                  <input
                    id="reg-name"
                    required
                    minLength={2}
                    value={form.fullName}
                    onChange={set('fullName')}
                    placeholder={t('auth.full_name_hint')}
                    className={field}
                  />
                </div>
                <p className="text-[10px] text-slate-400 font-medium">
                  {t('auth.full_name_note')}
                </p>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="reg-village" className="block">
                  {t('auth.village')} *
                </label>
                <div className="relative">
                  <MapPin size={14} className="absolute left-3 top-3 text-slate-400" />
                  <select
                    id="reg-village"
                    required
                    value={form.villageId}
                    onChange={set('villageId')}
                    className={field}
                  >
                    <option value="">{t('auth.select_village')}</option>
                    {villages.map((v) => (
                      <option key={v.id} value={v.id}>
                        {isEnglish ? v.name : v.nameMr}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label htmlFor="reg-phone" className="block">
                    {t('auth.phone')}
                  </label>
                  <div className="relative">
                    <Phone size={14} className="absolute left-3 top-3 text-slate-400" />
                    <input
                      id="reg-phone"
                      value={form.phone}
                      onChange={set('phone')}
                      placeholder="98XXXXXXXX"
                      className={field}
                    />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="reg-ward" className="block">
                    {t('auth.ward')}
                  </label>
                  <input
                    id="reg-ward"
                    type="number"
                    min={1}
                    max={50}
                    value={form.claimedWard}
                    onChange={set('claimedWard')}
                    placeholder="3"
                    className="w-full px-3 py-2 border border-slate-200 rounded text-slate-800 font-medium focus:outline-none focus:ring-2 focus:ring-govnavy/30"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="reg-email" className="block">
                  {t('auth.email')} *
                </label>
                <div className="relative">
                  <Mail size={14} className="absolute left-3 top-3 text-slate-400" />
                  <input
                    id="reg-email"
                    type="email"
                    required
                    value={form.email}
                    onChange={set('email')}
                    placeholder="name@example.com"
                    className={field}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label htmlFor="reg-password" className="block">
                    {t('auth.password')} *
                  </label>
                  <div className="relative">
                    <Lock size={14} className="absolute left-3 top-3 text-slate-400" />
                    <input
                      id="reg-password"
                      type="password"
                      required
                      minLength={8}
                      autoComplete="new-password"
                      value={form.password}
                      onChange={set('password')}
                      placeholder="••••••••"
                      className={field}
                    />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="reg-confirm" className="block">
                    {t('auth.confirm_password')} *
                  </label>
                  <div className="relative">
                    <Lock size={14} className="absolute left-3 top-3 text-slate-400" />
                    <input
                      id="reg-confirm"
                      type="password"
                      required
                      autoComplete="new-password"
                      value={form.confirm}
                      onChange={set('confirm')}
                      placeholder="••••••••"
                      className={field}
                    />
                  </div>
                </div>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="reg-note" className="block">
                  {t('auth.note')}
                </label>
                <textarea
                  id="reg-note"
                  rows={2}
                  value={form.note}
                  onChange={set('note')}
                  placeholder={t('auth.note_hint')}
                  className="w-full px-3 py-2 border border-slate-200 rounded text-slate-800 font-medium focus:outline-none focus:ring-2 focus:ring-govnavy/30"
                />
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="w-full py-2.5 bg-govgreen hover:bg-emerald-700 disabled:opacity-60 disabled:cursor-not-allowed text-white rounded font-bold text-xs sm:text-sm flex items-center justify-center gap-1.5 transition-all shadow-md mt-4"
              >
                {submitting ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    <span>{t('auth.sending')}</span>
                  </>
                ) : (
                  <>
                    <span>{t('auth.submit_application')}</span>
                    <ArrowRight size={14} />
                  </>
                )}
              </button>

              <p className="text-[10px] text-slate-400 text-center leading-relaxed pt-1">
                {t('auth.staff_account_note')}
              </p>
            </form>
          )}
        </div>
      </main>

      <footer className="bg-white border-t border-slate-200 py-4 text-[10px] text-slate-500 z-10">
        <div className="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <span>{t('auth.footer_left')}</span>
          <span>{t('auth.footer_right')}</span>
        </div>
      </footer>
    </div>
  );
};
