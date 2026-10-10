import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  ArrowRight,
  Building2,
  ClipboardList,
  FileCheck2,
  Globe,
  HandCoins,
  Landmark,
  MapPinned,
  MessageSquareWarning,
  Phone,
  Mail,
  UserPlus,
  ShieldCheck,
  Users,
} from 'lucide-react';

/**
 * The public home page, shown before sign-in.
 *
 * Written for residents, not for reviewers of the software: what the portal
 * lets you do, how to get an account, and where to get help.
 */

const VillageScene: React.FC = () => (
  <svg
    className="absolute inset-0 w-full h-full"
    viewBox="0 0 1440 720"
    preserveAspectRatio="xMidYMax slice"
    aria-hidden="true"
  >
    <defs>
      <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#f6c48b" />
        <stop offset="0.45" stopColor="#fbe3c0" />
        <stop offset="1" stopColor="#fdf3e3" />
      </linearGradient>
      <linearGradient id="field1" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#8fb36a" />
        <stop offset="1" stopColor="#6e9a4c" />
      </linearGradient>
      <linearGradient id="field2" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#5f8c3f" />
        <stop offset="1" stopColor="#3f6b2a" />
      </linearGradient>
    </defs>

    <rect width="1440" height="720" fill="url(#sky)" />
    {/* Morning sun */}
    <circle cx="1120" cy="210" r="70" fill="#ffd79a" opacity="0.9" />
    <circle cx="1120" cy="210" r="110" fill="#ffd79a" opacity="0.25" />

    {/* Distant Sahyadri hills */}
    <path d="M0 380 L120 330 L230 360 L360 300 L470 345 L600 290 L720 340 L860 285 L990 335 L1120 295 L1260 345 L1440 310 L1440 720 L0 720 Z"
      fill="#c9b79a" opacity="0.55" />
    <path d="M0 420 C180 380 300 410 460 385 C640 355 760 405 930 380 C1100 355 1240 400 1440 375 L1440 720 L0 720 Z"
      fill="#a9a37a" opacity="0.6" />

    {/* Fields */}
    <path d="M0 470 C240 440 480 460 720 450 C960 440 1200 455 1440 440 L1440 720 L0 720 Z" fill="url(#field1)" />
    <path d="M0 470 C240 440 480 460 720 450 C960 440 1200 455 1440 440" stroke="#a7c47f" strokeWidth="2" fill="none" />
    {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
      <path key={i} d={`M${i * 200 - 40} 720 L${i * 180 + 120} 470`} stroke="#7fa65a" strokeWidth="1.5" opacity="0.5" />
    ))}
    <path d="M0 560 C300 530 600 555 900 540 C1150 528 1300 545 1440 535 L1440 720 L0 720 Z" fill="url(#field2)" />

    {/* Village path */}
    <path d="M760 720 C800 640 860 580 930 520 L960 520 C910 585 870 650 860 720 Z" fill="#d9bf8f" opacity="0.85" />

    {/* Banyan tree */}
    <g transform="translate(560 330)">
      <rect x="44" y="90" width="18" height="80" fill="#6b4a2f" />
      <path d="M40 170 L46 120 M66 170 L60 125" stroke="#6b4a2f" strokeWidth="3" />
      <ellipse cx="53" cy="70" rx="80" ry="48" fill="#3f6b2a" />
      <ellipse cx="15" cy="88" rx="44" ry="30" fill="#4c7a33" />
      <ellipse cx="95" cy="86" rx="46" ry="30" fill="#4c7a33" />
      <ellipse cx="55" cy="45" rx="50" ry="30" fill="#5a8a3c" />
    </g>

    {/* Gram Panchayat Bhavan */}
    <g transform="translate(940 340)">
      <rect x="0" y="80" width="300" height="120" fill="#f3e6cf" stroke="#c9ad85" strokeWidth="2" />
      <path d="M-15 82 L150 20 L315 82 Z" fill="#b5523b" />
      <rect x="0" y="80" width="300" height="10" fill="#8f3f2d" opacity="0.5" />
      {[30, 90, 190, 250].map((x) => (
        <rect key={x} x={x} y="110" width="26" height="34" fill="#7a9cc2" stroke="#c9ad85" strokeWidth="2" />
      ))}
      <rect x="128" y="120" width="44" height="80" fill="#8b5a3c" />
      <rect x="110" y="96" width="80" height="16" rx="2" fill="#0f1f4b" />
      <text x="150" y="108" textAnchor="middle" fontSize="9" fontWeight="700" fill="#fff" fontFamily="sans-serif">
        ग्रामपंचायत
      </text>
      {[20, 60, 240, 280].map((x) => (
        <rect key={x} x={x} y="150" width="6" height="50" fill="#e6d3b3" />
      ))}
      {/* Flagpole with tricolour */}
      <rect x="148" y="-40" width="3" height="64" fill="#6b6b6b" />
      <rect x="151" y="-38" width="42" height="9" fill="#ff9933" />
      <rect x="151" y="-29" width="42" height="9" fill="#ffffff" />
      <rect x="151" y="-20" width="42" height="9" fill="#138808" />
      <circle cx="172" cy="-24.5" r="3" fill="none" stroke="#000080" strokeWidth="1" />
    </g>

    {/* Houses */}
    {[
      [300, 430, '#e9d2ad', '#a1462f'],
      [390, 445, '#efdcbc', '#b5523b'],
      [1320, 420, '#e9d2ad', '#a1462f'],
    ].map(([x, y, wall, roof], i) => (
      <g key={i} transform={`translate(${x} ${y})`}>
        <rect x="0" y="28" width="70" height="44" fill={wall as string} />
        <path d="M-6 30 L35 0 L76 30 Z" fill={roof as string} />
        <rect x="28" y="44" width="14" height="28" fill="#7a5034" />
      </g>
    ))}

    {/* Coconut palms */}
    {[[150, 400], [1260, 380], [250, 420]].map(([x, y], i) => (
      <g key={i} transform={`translate(${x} ${y})`}>
        <path d="M10 120 C14 80 6 40 14 0" stroke="#7a5a3a" strokeWidth="6" fill="none" />
        {[-60, -20, 20, 60, 100, 140].map((a) => (
          <path key={a} d="M14 0 q30 -10 55 12" stroke="#4c7a33" strokeWidth="6" fill="none"
            transform={`rotate(${a} 14 0)`} strokeLinecap="round" />
        ))}
      </g>
    ))}
  </svg>
);

export const Landing: React.FC<{ onSignIn: () => void }> = ({ onSignIn }) => {
  const { i18n } = useTranslation();
  const en = i18n.language === 'en';
  const L = (english: string, marathi: string) => (en ? english : marathi);

  const services = [
    { icon: Users, t: L('Family & resident records', 'कुटुंब व रहिवासी नोंदी'),
      d: L('View your household record and keep your details up to date with the Gram Panchayat.', 'तुमच्या कुटुंबाची नोंद पहा आणि ग्रामपंचायतीकडील माहिती अद्ययावत ठेवा.') },
    { icon: HandCoins, t: L('Welfare schemes', 'कल्याणकारी योजना'),
      d: L('Find out which central and state schemes you qualify for, and which documents you still need.', 'तुम्ही कोणत्या केंद्र व राज्य योजनांसाठी पात्र आहात आणि कोणती कागदपत्रे लागतील ते जाणून घ्या.') },
    { icon: MessageSquareWarning, t: L('Grievance redressal', 'तक्रार निवारण'),
      d: L('Report a problem with water, roads, drainage or streetlights and follow it until it is resolved.', 'पाणी, रस्ते, गटार किंवा पथदिव्यांबाबत तक्रार नोंदवा आणि निवारण होईपर्यंत पाठपुरावा करा.') },
    { icon: FileCheck2, t: L('Digital document locker', 'डिजिटल दस्तऐवज कोठी'),
      d: L('Upload certificates once and have them verified by the Panchayat office.', 'प्रमाणपत्रे एकदाच अपलोड करा आणि पंचायत कार्यालयाकडून पडताळणी करून घ्या.') },
    { icon: ClipboardList, t: L('Gram Sabha proceedings', 'ग्रामसभा कामकाज'),
      d: L('Read the decisions taken in your Gram Sabha and track the follow-up work.', 'ग्रामसभेत घेतलेले निर्णय वाचा आणि पुढील कामांचा पाठपुरावा करा.') },
    { icon: MapPinned, t: L('Development works', 'विकासकामे'),
      d: L('See ongoing works in your village, their budget and progress, on a map.', 'गावातील चालू कामे, त्यांचे अंदाजपत्रक व प्रगती नकाशावर पहा.') },
  ];

  const stats = [
    ['23', L('Gram Panchayats', 'ग्रामपंचायती')],
    ['29', L('Welfare schemes', 'कल्याणकारी योजना')],
    ['2', L('Languages', 'भाषा')],
    ['24×7', L('Online access', 'ऑनलाइन सेवा')],
  ];

  const steps = [
    [UserPlus, L('Apply for an account', 'खात्यासाठी अर्ज करा'), L('Fill in your name, phone and village.', 'नाव, फोन व गाव भरा.')],
    [ShieldCheck, L('Get verified', 'पडताळणी'), L('An officer matches you to the village register.', 'अधिकारी गावाच्या नोंदवहीशी तुमची ओळख जुळवतात.')],
    [Landmark, L('Use Panchayat services', 'पंचायत सेवा वापरा'), L('Sign in with your email or Aadhaar number.', 'ईमेल किंवा आधार क्रमांकाने साइन इन करा.')],
  ] as const;

  return (
    <div className="min-h-screen flex flex-col bg-[#fbf7f0] text-slate-800">
      {/* Government identity bar */}
      <div className="gov-tricolor-strip" />
      <div className="bg-[#0f1f4b] text-[11px] text-[#dbe3f2]">
        <div className="max-w-7xl mx-auto px-6 py-1.5 flex items-center justify-between gap-4">
          <span className="truncate">{L('Government of Maharashtra', 'महाराष्ट्र शासन')} · {L('Rural Development & Panchayat Raj Department', 'ग्रामविकास व पंचायत राज विभाग')}</span>
          <button onClick={() => i18n.changeLanguage(en ? 'mr' : 'en')} className="flex items-center gap-1.5 hover:text-white">
            <Globe size={12} /> {en ? 'मराठी' : 'English'}
          </button>
        </div>
      </div>

      <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-full border-2 border-[#c9a34a] bg-[#fff8e8] flex items-center justify-center">
              <Landmark size={20} className="text-[#0f1f4b]" />
            </div>
            <div className="leading-tight">
              <div className="font-extrabold text-[#0f1f4b] text-lg tracking-tight">
                e-Panchayat <span className="text-[#c86a12]">{L('Maharashtra', 'महाराष्ट्र')}</span>
              </div>
              <div className="text-[11px] text-slate-500">{L('Haveli Block · Pune District', 'हवेली तालुका · पुणे जिल्हा')}</div>
            </div>
          </div>
          <nav className="hidden md:flex items-center gap-7 text-sm font-semibold text-slate-600">
            <a href="#services" className="hover:text-[#0f1f4b]">{L('Services', 'सेवा')}</a>
            <a href="#how" className="hover:text-[#0f1f4b]">{L('How to register', 'नोंदणी कशी करावी')}</a>
            <a href="#help" className="hover:text-[#0f1f4b]">{L('Helpdesk', 'मदत केंद्र')}</a>
          </nav>
          <button onClick={onSignIn}
            className="px-4 py-2 rounded-lg bg-govnavy text-white font-semibold text-sm flex items-center gap-1.5 whitespace-nowrap">
            {L('Sign in', 'साइन इन')} <ArrowRight size={14} />
          </button>
        </div>
      </header>

      {/* Hero with village illustration */}
      <section className="relative overflow-hidden min-h-[560px] flex items-center">
        <VillageScene />
        <div className="absolute inset-0 bg-gradient-to-r from-[#0f1f4b]/90 via-[#0f1f4b]/60 to-transparent" />
        <div className="relative max-w-7xl mx-auto px-6 py-20 w-full">
          <div className="max-w-xl text-white space-y-5">
            <p className="text-[#ffc98a] font-semibold tracking-wide text-sm">
              {L('आपली ग्रामपंचायत, आपल्या दारी', 'आपली ग्रामपंचायत, आपल्या दारी')}
            </p>
            <h1 className="text-4xl sm:text-5xl font-extrabold leading-tight m-0">
              {L('Your Gram Panchayat, now online', 'तुमची ग्रामपंचायत, आता ऑनलाइन')}
            </h1>
            <p className="text-[#dbe3f2] text-base leading-relaxed m-0">
              {L(
                'Apply for welfare schemes, raise and track complaints, keep your documents in one place and follow the work being done in your village, without a trip to the office.',
                'कल्याणकारी योजनांसाठी अर्ज करा, तक्रारी नोंदवा व पाठपुरावा करा, कागदपत्रे एकाच ठिकाणी ठेवा आणि गावातील कामांची माहिती घ्या — कार्यालयात न जाता.',
              )}
            </p>
            <div className="flex flex-wrap gap-3 pt-2">
              <button onClick={onSignIn}
                className="px-6 py-3 rounded-lg bg-[#ff8a1f] hover:bg-[#f07a10] text-white font-bold text-sm flex items-center gap-2 shadow-lg">
                {L('Sign in to the portal', 'पोर्टलवर साइन इन करा')} <ArrowRight size={16} />
              </button>
              <button onClick={onSignIn}
                className="px-6 py-3 rounded-lg bg-white/10 border border-white/40 hover:bg-white/20 text-white font-bold text-sm">
                {L('New resident? Register', 'नवीन रहिवासी? नोंदणी करा')}
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Key figures */}
      <section className="relative z-10 -mt-10">
        <div className="max-w-5xl mx-auto px-6">
          <div className="grid grid-cols-2 md:grid-cols-4 bg-white rounded-xl shadow-lg border border-slate-200 divide-x divide-slate-100">
            {stats.map(([n, label]) => (
              <div key={label} className="py-5 text-center">
                <div className="text-2xl font-extrabold text-[#0f1f4b]">{n}</div>
                <div className="text-xs text-slate-500 font-medium mt-1">{label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Services */}
      <section id="services" className="max-w-7xl mx-auto px-6 py-16 w-full">
        <h2 className="text-2xl font-extrabold text-[#0f1f4b] m-0">{L('Citizen services', 'नागरिक सेवा')}</h2>
        <div className="h-1 w-14 bg-[#ff8a1f] rounded mt-2 mb-8" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {services.map(({ icon: Icon, t, d }) => (
            <div key={t} className="bg-white rounded-xl p-6 border border-slate-200 hover:border-[#ff8a1f]/50 hover:shadow-md transition-all">
              <div className="w-11 h-11 rounded-lg bg-[#fff1e2] text-[#c86a12] flex items-center justify-center mb-4">
                <Icon size={20} />
              </div>
              <h3 className="text-base font-bold text-[#0f1f4b] m-0">{t}</h3>
              <p className="text-sm text-slate-600 leading-relaxed mt-2 mb-0">{d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How to register */}
      <section id="how" className="bg-white border-y border-slate-200">
        <div className="max-w-7xl mx-auto px-6 py-16">
          <h2 className="text-2xl font-extrabold text-[#0f1f4b] m-0">{L('How to get an account', 'खाते कसे मिळवावे')}</h2>
          <div className="h-1 w-14 bg-[#138808] rounded mt-2 mb-8" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {steps.map(([Icon, t, d], i) => (
              <div key={t} className="flex gap-4">
                <div className="flex-shrink-0 w-12 h-12 rounded-full bg-[#0f1f4b] text-white flex items-center justify-center font-bold relative">
                  <Icon size={20} />
                  <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-[#ff8a1f] text-[10px] flex items-center justify-center">{i + 1}</span>
                </div>
                <div>
                  <h3 className="text-base font-bold text-[#0f1f4b] m-0">{t}</h3>
                  <p className="text-sm text-slate-600 mt-1 mb-0">{d}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Helpdesk + footer */}
      <footer id="help" className="bg-[#0f1f4b] text-[#c3cde0] mt-auto">
        <div className="max-w-7xl mx-auto px-6 py-12 grid grid-cols-1 md:grid-cols-3 gap-8 text-sm">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-white font-bold text-base">
              <Building2 size={18} /> {L('Panchayat Helpdesk', 'पंचायत मदत केंद्र')}
            </div>
            <p className="m-0">{L('Visit your Gram Panchayat office, Monday to Saturday, 10:00 to 17:30.', 'तुमच्या ग्रामपंचायत कार्यालयात भेट द्या, सोमवार ते शनिवार, १०:०० ते १७:३०.')}</p>
            <p className="m-0 flex items-center gap-2"><Phone size={14} /> {L('Contact your village office', 'गावाच्या कार्यालयाशी संपर्क साधा')}</p>
            <p className="m-0 flex items-center gap-2"><Mail size={14} /> {L('Raise a request after signing in', 'साइन इन करून विनंती नोंदवा')}</p>
          </div>
          <div className="space-y-2">
            <div className="text-white font-bold text-base">{L('Related government portals', 'संबंधित शासकीय संकेतस्थळे')}</div>
            <a className="block hover:text-white" href="https://egramswaraj.gov.in" target="_blank" rel="noreferrer">eGramSwaraj</a>
            <a className="block hover:text-white" href="https://panchayat.gov.in" target="_blank" rel="noreferrer">{L('Ministry of Panchayati Raj', 'पंचायती राज मंत्रालय')}</a>
            <a className="block hover:text-white" href="https://rdd.maharashtra.gov.in" target="_blank" rel="noreferrer">{L('Rural Development Dept., Maharashtra', 'ग्रामविकास विभाग, महाराष्ट्र')}</a>
          </div>
          <div className="space-y-2">
            <div className="text-white font-bold text-base">{L('Already registered?', 'आधीच नोंदणी केली आहे?')}</div>
            <p className="m-0">{L('Residents can sign in with their email or Aadhaar number.', 'रहिवासी ईमेल किंवा आधार क्रमांकाने साइन इन करू शकतात.')}</p>
            <button onClick={onSignIn} className="mt-2 px-4 py-2 rounded-lg bg-[#ff8a1f] text-white font-semibold text-sm">
              {L('Sign in', 'साइन इन')}
            </button>
          </div>
        </div>
        <div className="border-t border-white/10">
          <div className="max-w-7xl mx-auto px-6 py-4 text-[11px] text-[#93a0bb] flex flex-col sm:flex-row justify-between gap-2">
            <span>© 2026 e-Panchayat · Haveli, Pune</span>
            <span>{L('Demonstration portal. Resident records shown are sample data.', 'प्रात्यक्षिक पोर्टल. दाखवलेल्या रहिवासी नोंदी नमुना माहिती आहेत.')}</span>
          </div>
        </div>
      </footer>
    </div>
  );
};
