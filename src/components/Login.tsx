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
  KeyRound,
  Fingerprint,
  ShieldAlert,
  Smartphone,
} from 'lucide-react';

import { useAuth } from '../lib/auth';
import { api, ApiError, isAadhaar } from '../lib/api';
import type { LoginChallenge, OtpSent, PublicVillage } from '../lib/api';

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
/**
 * 'recover' is reached by a link under the sign-in form rather than a third
 * tab. A resident needs it perhaps once, and only after a trip to the Panchayat
 * office to be identified — giving it equal billing with signing in would
 * suggest it is something you can start from here, which it is not.
 */
type Mode = 'signin' | 'register' | 'recover';

const field =
  'w-full pl-9 pr-3 py-2 border border-slate-200 rounded text-slate-800 font-medium ' +
  'focus:outline-none focus:ring-2 focus:ring-govnavy/30';

export const Login: React.FC = () => {
  const { t, i18n } = useTranslation();
  const { signIn, completeSignIn, loading, error, clearError } = useAuth();

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

  // Redeeming a code issued at the Panchayat counter. The code permits setting
  // a password; the password itself is chosen here and never reaches the
  // officer who handed the code over.
  const [recover, setRecover] = useState({
    email: '',
    code: '',
    password: '',
    confirm: '',
  });
  const [recovered, setRecovered] = useState(false);
  // Residents recover by an OTP to their registered phone and email. After
  // repeated failed sign-ins the server refuses that (423) and only a code
  // from the Panchayat office will do — the 'office' path.
  const [recoverBy, setRecoverBy] = useState<'otp' | 'office'>('otp');
  const [otpInfo, setOtpInfo] = useState<OtpSent | null>(null);

  // A sign-in from a device this account has not used before waits here
  // until the owner approves or denies it from the SMS / email alert.
  const [challenge, setChallenge] = useState<LoginChallenge | null>(null);
  const [challengeState, setChallengeState] = useState<'pending' | 'denied' | 'expired'>('pending');

  useEffect(() => {
    if (!challenge || challengeState !== 'pending') return;
    const timer = window.setInterval(async () => {
      try {
        const res = await api.auth.pollChallenge(challenge.challengeId, challenge.pollToken);
        if (res.status === 'approved' && res.tokens) {
          window.clearInterval(timer);
          await completeSignIn(res.tokens);
        } else if (res.status !== 'pending') {
          window.clearInterval(timer);
          setChallengeState(res.status === 'expired' ? 'expired' : 'denied');
        }
      } catch {
        /* transient; try again on the next tick */
      }
    }, 2500);
    return () => window.clearInterval(timer);
  }, [challenge, challengeState, completeSignIn]);

  const isEnglish = i18n.language === 'en';
  const toggleLanguage = () => i18n.changeLanguage(isEnglish ? 'mr' : 'en');

  const selectedVillage = villages.find((v) => v.id === form.villageId) ?? null;

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
    setRecovered(false);
    setRecoverBy('otp');
    setOtpInfo(null);
  };

  const handleRecover = async (event: React.FormEvent) => {
    event.preventDefault();
    setFormError(null);

    // Step one of the OTP path: send the code, then reveal the rest of the form.
    if (recoverBy === 'otp' && !otpInfo) {
      setSubmitting(true);
      try {
        setOtpInfo(await api.auth.requestOtp(recover.email));
      } catch (err) {
        if (err instanceof ApiError && err.status === 423) setRecoverBy('office');
        setFormError(err instanceof Error ? err.message : String(err));
      } finally {
        setSubmitting(false);
      }
      return;
    }

    if (recover.password !== recover.confirm) {
      setFormError(
        isEnglish ? 'The two passwords do not match.' : 'दोन्ही संकेतशब्द जुळत नाहीत.',
      );
      return;
    }

    setSubmitting(true);
    try {
      if (recoverBy === 'otp') {
        await api.auth.verifyOtp(recover.email, recover.code, recover.password);
      } else {
        await api.auth.resetPassword(recover.email, recover.code, recover.password);
      }
      setRecovered(true);
      // Carry the address over so signing in is one field, not two.
      setEmail(recover.email);
      setPassword('');
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const pending = await signIn(email, password);
      if (pending) {
        setChallengeState('pending');
        setChallenge(pending);
      }
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
    <div className="login-hero min-h-screen flex flex-col justify-between bg-slate-50 relative selection:bg-govsaffron selection:text-white">
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
        <div className="login-card w-full max-w-md bg-white rounded-2xl border border-slate-200 p-6 sm:p-8 shadow-md border-t-4 border-govsaffron space-y-6">
          <div className="text-center space-y-1.5">
            <h1 className="text-lg sm:text-xl font-black text-govblue-900 tracking-tight uppercase m-0">
              {t('auth.portal_title')}
            </h1>
            <p className="text-xs text-slate-500 font-medium">
              {mode === 'signin'
                ? t('auth.subtitle')
                : mode === 'recover'
                  ? isEnglish
                    ? 'Recover your account with an OTP, or a code from the Panchayat office'
                    : 'ओटीपी किंवा ग्रामपंचायत कार्यालयातील कोड वापरून खाते पुनर्प्राप्त करा'
                  : t('auth.register_subtitle')}
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

          {mode === 'signin' && challenge ? (
            <div className="space-y-4 text-center">
              {challengeState === 'pending' ? (
                <>
                  <div className="mx-auto w-14 h-14 rounded-full bg-govsaffron/10 flex items-center justify-center">
                    <Smartphone size={26} className="text-govsaffron animate-pulse" />
                  </div>
                  <p className="text-sm font-bold text-govblue-900 m-0">
                    {isEnglish ? 'New device detected' : 'नवीन उपकरण आढळले'}
                  </p>
                  <p className="text-xs text-slate-600 leading-relaxed m-0">
                    {isEnglish
                      ? 'This account is usually used from another device. We sent an "Is this you?" alert to the registered mobile and email. Approve it there to continue.'
                      : 'हे खाते सहसा दुसऱ्या उपकरणावरून वापरले जाते. नोंदणीकृत मोबाइल व ईमेलवर "हे तुम्हीच आहात का?" सूचना पाठवली आहे. पुढे जाण्यासाठी तेथे मंजुरी द्या.'}
                  </p>
                  <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-[11px] text-slate-600 text-left">
                    <p className="m-0 font-bold">{challenge.sentTo.join(' · ')}</p>
                    <p className="m-0 flex items-center gap-1.5 mt-1">
                      <Loader2 size={12} className="animate-spin" />
                      {isEnglish
                        ? `Waiting for approval · expires in ${challenge.expiresInMinutes} minutes`
                        : `मंजुरीची प्रतीक्षा · ${challenge.expiresInMinutes} मिनिटांत कालबाह्य`}
                    </p>
                  </div>
                  {challenge.demoDecisionUrl && (
                    <a
                      href={challenge.demoDecisionUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="block p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-[11px] text-emerald-800 font-bold hover:bg-emerald-100"
                    >
                      {isEnglish
                        ? 'Demo mode (no SMS gateway yet): open the link from the SMS / email →'
                        : 'डेमो मोड: एसएमएस / ईमेलमधील लिंक उघडा →'}
                    </a>
                  )}
                </>
              ) : (
                <>
                  <ShieldAlert size={40} className="mx-auto text-rose-600" />
                  <p className="text-sm font-bold text-rose-700 m-0">
                    {challengeState === 'denied'
                      ? isEnglish ? 'Sign-in was denied' : 'साइन इन नाकारले'
                      : isEnglish ? 'Approval request expired' : 'मंजुरीची विनंती कालबाह्य'}
                  </p>
                  <p className="text-xs text-slate-600 leading-relaxed m-0">
                    {challengeState === 'denied'
                      ? isEnglish
                        ? 'The account owner denied this device. If that was you by mistake, sign in again.'
                        : 'खातेधारकाने हे उपकरण नाकारले.'
                      : isEnglish ? 'Sign in again to send a new alert.' : 'नवीन सूचनेसाठी पुन्हा साइन इन करा.'}
                  </p>
                </>
              )}
              <button
                type="button"
                onClick={() => setChallenge(null)}
                className="text-xs font-bold text-govnavy hover:underline"
              >
                {isEnglish ? '← Back to sign in' : '← साइन इनकडे परत'}
              </button>
            </div>
          ) : mode === 'signin' ? (
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
                    {isEnglish ? 'Email or Aadhaar number' : 'ईमेल किंवा आधार क्रमांक'}
                  </label>
                  <div className="relative">
                    {isAadhaar(email) ? (
                      <Fingerprint size={14} className="absolute left-3 top-3 text-govsaffron" />
                    ) : (
                      <Mail size={14} className="absolute left-3 top-3 text-slate-400" />
                    )}
                    <input
                      id="email"
                      type="text"
                      inputMode={/^[\d\s-]+$/.test(email) ? 'numeric' : 'email'}
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
                {/* Deliberately understated: this is not a self-service reset,
                    and offering it as one would send residents looking for an
                    email that is never sent. */}
                <p className="text-[11px] text-slate-500 text-center leading-relaxed m-0">
                  <button
                    type="button"
                    onClick={() => switchMode('recover')}
                    className="font-bold text-govnavy hover:underline"
                  >
                    {isEnglish ? 'Forgot password?' : 'संकेतशब्द विसरलात?'}
                  </button>
                </p>
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
                  <br />
                  {isEnglish ? 'Or sign in with demo Aadhaar ' : 'किंवा डेमो आधार '}
                  <button
                    type="button"
                    onClick={() => setEmail('9999 0000 0102')}
                    className="font-mono text-govnavy hover:underline"
                  >
                    9999 0000 0102
                  </button>{' '}
                  {isEnglish ? '(Savita Patil)' : '(सविता पाटील)'}
                </p>
              </div>
            </>
          ) : mode === 'recover' ? (
            recovered ? (
              <div className="space-y-4 text-center">
                <CheckCircle2 size={40} className="mx-auto text-govgreen" />
                <p className="text-sm font-bold text-govblue-900 m-0">
                  {isEnglish ? 'Your password is set' : 'तुमचा संकेतशब्द तयार झाला'}
                </p>
                <p className="text-xs text-slate-600 leading-relaxed m-0">
                  {isEnglish
                    ? 'Sign in with it now. Any other device that was signed in to this account has been signed out.'
                    : 'आता त्याने साइन इन करा. या खात्यावर साइन इन असलेली इतर कोणतीही उपकरणे साइन आउट झाली आहेत.'}
                </p>
                <button
                  type="button"
                  onClick={() => switchMode('signin')}
                  className="w-full py-2.5 bg-govnavy hover:bg-govblue-700 text-white rounded font-bold text-xs sm:text-sm transition-all shadow-md"
                >
                  {isEnglish ? 'Go to sign in' : 'साइन इनकडे जा'}
                </button>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  {(['otp', 'office'] as const).map((key) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => {
                        setRecoverBy(key);
                        setOtpInfo(null);
                        setFormError(null);
                      }}
                      className={`py-1.5 rounded-lg border font-bold transition-all ${
                        recoverBy === key
                          ? 'border-govnavy/40 bg-govnavy/5 text-govnavy'
                          : 'border-slate-200 text-slate-500 hover:text-slate-900'
                      }`}
                    >
                      {key === 'otp'
                        ? isEnglish ? 'OTP on SMS / email' : 'एसएमएस / ईमेल ओटीपी'
                        : isEnglish ? 'Code from office' : 'कार्यालयातील कोड'}
                    </button>
                  ))}
                </div>
                <div className="p-3 rounded-lg bg-govblue-50 border border-govnavy/15 text-[11px] text-slate-600 leading-relaxed text-left">
                  {recoverBy === 'otp'
                    ? isEnglish
                      ? 'Enter your email or Aadhaar number. We will send a 6-digit OTP to the mobile number and email registered with the Panchayat. After 5 failed sign-in attempts the account is locked, and you will need a reset code from the Panchayat office instead.'
                      : 'तुमचा ईमेल किंवा आधार क्रमांक टाका. पंचायतीकडे नोंदवलेल्या मोबाइल व ईमेलवर ६ अंकी ओटीपी पाठवला जाईल. ५ वेळा चुकीचा प्रयत्न झाल्यास खाते लॉक होते; तेव्हा पंचायत कार्यालयातील रीसेट कोड लागेल.'
                    : isEnglish
                      ? 'Locked accounts are recovered at the Gram Panchayat office: an officer verifies you against the village register and gives you a one-time reset code.'
                      : 'लॉक झालेली खाती ग्रामपंचायत कार्यालयात पुनर्प्राप्त होतात: अधिकारी ओळख पटवून एकवेळचा रीसेट कोड देतात.'}
                </div>

                {otpInfo && (
                  <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-[11px] text-emerald-800 leading-relaxed text-left">
                    <p className="m-0 font-bold">
                      {isEnglish ? 'OTP sent' : 'ओटीपी पाठवला'}: {otpInfo.sentTo.join(' · ')}
                    </p>
                    <p className="m-0">
                      {isEnglish
                        ? `Valid for ${otpInfo.expiresInMinutes} minutes.`
                        : `${otpInfo.expiresInMinutes} मिनिटे वैध.`}
                    </p>
                    {otpInfo.demoOtp && (
                      <p className="m-0 mt-1.5 pt-1.5 border-t border-emerald-200">
                        {isEnglish ? 'Demo mode (no SMS gateway yet): your OTP is ' : 'डेमो मोड: तुमचा ओटीपी '}
                        <span className="font-mono font-black tracking-widest text-sm">{otpInfo.demoOtp}</span>
                      </p>
                    )}
                  </div>
                )}

                {formError && (
                  <div
                    role="alert"
                    className="p-3 rounded bg-rose-50 border border-rose-200 text-xs text-rose-700 font-semibold leading-relaxed"
                  >
                    {formError}
                  </div>
                )}

                <form
                  onSubmit={handleRecover}
                  className="space-y-4 text-xs font-bold text-slate-500 text-left"
                >
                  <div className="space-y-1.5">
                    <label htmlFor="rec-email" className="block">
                      {recoverBy === 'otp'
                        ? isEnglish ? 'Email or Aadhaar number' : 'ईमेल किंवा आधार क्रमांक'
                        : t('auth.email')}
                    </label>
                    <div className="relative">
                      <Mail size={14} className="absolute left-3 top-3 text-slate-400" />
                      <input
                        id="rec-email"
                        type={recoverBy === 'otp' ? 'text' : 'email'}
                        required
                        readOnly={Boolean(otpInfo)}
                        value={recover.email}
                        onChange={(e) => setRecover({ ...recover, email: e.target.value })}
                        placeholder="savita@citizen.panchayat.gov.in"
                        className={field}
                      />
                    </div>
                  </div>

                  {(recoverBy === 'office' || otpInfo) && (
                  <>
                  <div className="space-y-1.5">
                    <label htmlFor="rec-code" className="block">
                      {recoverBy === 'otp'
                        ? isEnglish ? '6-digit OTP' : '६ अंकी ओटीपी'
                        : isEnglish ? 'Reset code' : 'रीसेट कोड'}
                    </label>
                    <div className="relative">
                      <KeyRound size={14} className="absolute left-3 top-3 text-slate-400" />
                      <input
                        id="rec-code"
                        required
                        value={recover.code}
                        onChange={(e) => setRecover({ ...recover, code: e.target.value })}
                        placeholder={recoverBy === 'otp' ? '••••••' : 'XXXXX-XXXXX'}
                        inputMode={recoverBy === 'otp' ? 'numeric' : 'text'}
                        autoCapitalize="characters"
                        spellCheck={false}
                        className={`${field} font-mono tracking-widest uppercase`}
                      />
                    </div>
                    {recoverBy === 'office' && (
                    <p className="text-[10px] text-slate-400 font-medium m-0">
                      {isEnglish
                        ? 'Capitals and the dash do not matter.'
                        : 'लहान-मोठी अक्षरे किंवा डॅश यांनी फरक पडत नाही.'}
                    </p>
                    )}
                  </div>

                  <div className="space-y-1.5">
                    <label htmlFor="rec-password" className="block">
                      {isEnglish ? 'New password' : 'नवीन संकेतशब्द'}
                    </label>
                    <div className="relative">
                      <Lock size={14} className="absolute left-3 top-3 text-slate-400" />
                      <input
                        id="rec-password"
                        type="password"
                        required
                        minLength={8}
                        autoComplete="new-password"
                        value={recover.password}
                        onChange={(e) =>
                          setRecover({ ...recover, password: e.target.value })
                        }
                        placeholder="••••••••"
                        className={field}
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label htmlFor="rec-confirm" className="block">
                      {isEnglish ? 'Confirm new password' : 'संकेतशब्दाची खात्री करा'}
                    </label>
                    <div className="relative">
                      <Lock size={14} className="absolute left-3 top-3 text-slate-400" />
                      <input
                        id="rec-confirm"
                        type="password"
                        required
                        minLength={8}
                        autoComplete="new-password"
                        value={recover.confirm}
                        onChange={(e) =>
                          setRecover({ ...recover, confirm: e.target.value })
                        }
                        placeholder="••••••••"
                        className={field}
                      />
                    </div>
                  </div>

                  </>
                  )}

                  <button
                    type="submit"
                    disabled={submitting}
                    className="w-full py-2.5 bg-govnavy hover:bg-govblue-700 disabled:opacity-60 disabled:cursor-not-allowed text-white rounded font-bold text-xs sm:text-sm flex items-center justify-center gap-1.5 transition-all shadow-md mt-4"
                  >
                    {submitting ? (
                      <>
                        <Loader2 size={14} className="animate-spin" />
                        <span>{isEnglish ? 'Setting password' : 'संकेतशब्द तयार होत आहे'}</span>
                      </>
                    ) : (
                      <>
                        <span>
                          {recoverBy === 'otp' && !otpInfo
                            ? isEnglish ? 'Send OTP' : 'ओटीपी पाठवा'
                            : isEnglish ? 'Set my password' : 'माझा संकेतशब्द ठरवा'}
                        </span>
                        <ArrowRight size={14} />
                      </>
                    )}
                  </button>
                </form>

                <button
                  type="button"
                  onClick={() => switchMode('signin')}
                  className="w-full text-[11px] font-bold text-slate-500 hover:text-govnavy transition-colors"
                >
                  {isEnglish ? '← Back to sign in' : '← साइन इनकडे परत'}
                </button>
              </>
            )
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

                {/* The block, district and state are shown rather than asked
                    for. This platform serves one block, so three dropdowns
                    with one option each would be pure friction — but an
                    applicant still needs to see where the village they picked
                    actually sits, because village names repeat across a
                    district. When this covers more than one block, these
                    become real cascading selects. */}
                {selectedVillage && (
                  <p className="text-[10px] text-slate-500 font-semibold leading-relaxed">
                    {isEnglish
                      ? `${selectedVillage.blockName} block · ${selectedVillage.districtName} district · ${selectedVillage.stateName}`
                      : `${selectedVillage.blockNameMr} तालुका · ${selectedVillage.districtNameMr} जिल्हा · ${selectedVillage.stateNameMr}`}
                    {selectedVillage.lgdCode
                      ? ` · LGD ${selectedVillage.lgdCode}`
                      : ''}
                  </p>
                )}
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
