import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Bot,
  Award,
  Database,
  ArrowRight,
  Sparkles,
  Layers,
  Globe,
  LayoutDashboard,
  AlertTriangle,
  LineChart,
  FileText,
  Loader2,
} from 'lucide-react';

// Import local components
import { Sidebar } from './components/Sidebar';
import { Dashboard } from './components/Dashboard';
import { CitizenManagement } from './components/CitizenManagement';
import { GrievanceManagement } from './components/GrievanceManagement';
import { DevelopmentProjects } from './components/DevelopmentProjects';
import { GramSabhaAI } from './components/GramSabhaAI';
import { GISMap } from './components/GISMap';
import { AIAssistant } from './components/AIAssistant';
import { Analytics } from './components/Analytics';
import { CitizenPortal } from './components/CitizenPortal';
import { CitizenSchemes } from './components/CitizenSchemes';
import { CitizenGrievances } from './components/CitizenGrievances';
import { DistrictOverview } from './components/DistrictOverview';
import { SchemeBrowser } from './components/SchemeBrowser';
import { RegistrationReview } from './components/RegistrationReview';
import { Login } from './components/Login';

// Import i18n initialization
import './i18n/i18n';
import { useAuth } from './lib/auth';
import { clearPersistentCache } from './lib/persistence';
import { api, type Village } from './lib/api';
import { useQuery } from './lib/useApi';

function App() {
  const { t, i18n } = useTranslation();
  const { user, initialising, signOut, isOfficer } = useAuth();

  const isAdmin = user?.role === 'admin';

  // Which Gram Panchayat this session is working in. Null for an admin, who
  // works across the block — the village name in the header comes from here
  // rather than being hardcoded, because the platform now serves 23 villages.
  const village = useQuery<Village | null>(
    () => (user ? api.villages.current() : Promise.resolve(null)),
    [user?.id],
  );

  const [showLogin, setShowLogin] = useState(false);
  const [currentTab, setCurrentTab] = useState<string>('dashboard');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const toggleLanguage = () => {
    const nextLang = i18n.language === 'en' ? 'mr' : 'en';
    i18n.changeLanguage(nextLang);
  };

  const handleSignOut = () => {
    signOut();
    clearPersistentCache();
    setShowLogin(false);
    setCurrentTab('dashboard');
  };

  // Which screen to show is derived from the session, not from a local
  // variable — you cannot become an officer by setting React state.
  const view = initialising
    ? 'restoring'
    : user
      ? 'dashboard'
      : showLogin
        ? 'login'
        : 'landing';

  const renderTabContent = () => {
    if (!isOfficer) {
      // Schemes are served from the API with this resident's own eligibility;
      // the rest of the portal still runs on the older screens.
      if (currentTab === 'schemes') return <CitizenSchemes />;
      if (currentTab === 'grievances') return <CitizenGrievances />;
      if (currentTab === 'ai_assistant') return <AIAssistant />;
      return (
        <CitizenPortal
          currentTab={currentTab}
          setCurrentTab={setCurrentTab}
          citizenId={user?.citizenId ?? ''}
        />
      );
    }

    switch (currentTab) {
      case 'district':
        return <DistrictOverview />;
      case 'dashboard':
        return <Dashboard setCurrentTab={setCurrentTab} />;
      case 'citizens':
        return <CitizenManagement />;
      case 'registrations':
        return <RegistrationReview />;
      case 'schemes':
        return <SchemeBrowser />;
      case 'grievances':
        return <GrievanceManagement />;
      case 'projects':
        return <DevelopmentProjects />;
      case 'sabha':
        return <GramSabhaAI />;
      case 'gis_map':
        return <GISMap />;
      case 'ai_assistant':
        return <AIAssistant />;
      case 'analytics':
        return <Analytics />;
      default:
        return <Dashboard setCurrentTab={setCurrentTab} />;
    }
  };

  return (
    <div className="min-h-screen text-slate-800 bg-[#f4f6f9] font-sans selection:bg-govsaffron selection:text-white">
      {/* 0. RESTORING AN EXISTING SESSION */}
      {view === 'restoring' && (
        <div className="min-h-screen flex flex-col items-center justify-center gap-3 bg-slate-50">
          <Loader2 size={28} className="animate-spin text-govnavy" />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Restoring your session
          </span>
        </div>
      )}

      {/* 1. LANDING PAGE VIEW */}
      {view === 'landing' && (
        <div className="relative overflow-hidden bg-slate-50 min-h-screen flex flex-col justify-between">
          {/* Top National Tricolor Indicator Strip */}
          <div className="w-full gov-tricolor-strip z-20" />

          {/* Official Indian Gov Header Banner */}
          <div className="bg-white border-b border-slate-200 py-3 shadow-sm z-20">
            <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div className="flex items-center gap-4">
                {/* Ashoka Emblem Vector representation */}
                <div className="w-12 h-14 bg-slate-50 border border-slate-200 rounded flex items-center justify-center p-1.5 shadow-sm">
                  <div className="flex flex-col items-center select-none text-[8px] font-bold text-amber-800">
                    <span className="text-xs">🦁</span>
                    <span className="tracking-tighter">सत्यमेव</span>
                    <span className="tracking-tighter">जयते</span>
                  </div>
                </div>
                <div className="flex flex-col select-none">
                  <span className="text-[10px] font-bold tracking-wider text-slate-500 uppercase">
                    {t('landing.ministry')}
                  </span>
                  <span className="font-extrabold text-govnavy tracking-tight text-lg">
                    {t('landing.portal_name')}
                  </span>
                  <span className="text-[10px] font-bold text-govsaffron uppercase tracking-widest mt-0.5">
                    {t('landing.region')}
                  </span>
                </div>
              </div>

              {/* PM/CM & Flag Section */}
              <div className="flex items-center gap-6 self-end md:self-center">
                <div className="text-right hidden sm:block">
                  <span className="text-[9px] font-bold text-slate-400 uppercase block">
                    {t('landing.governance')}
                  </span>
                  <span className="text-xs font-extrabold text-govgreen uppercase block">
                    {t('landing.mission')}
                  </span>
                </div>
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-200 bg-slate-50">
                  <span className="text-sm">🇮🇳</span>
                  <span className="text-xs font-bold text-slate-700">English | मराठी</span>
                </div>
              </div>
            </div>
          </div>

          {/* Custom Landing Page Navigation */}
          <header className="max-w-7xl mx-auto w-full px-6 py-4 flex items-center justify-between border-b border-slate-100 z-20">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-govsaffron animate-pulse" />
              <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                {t('landing.status')}
              </span>
            </div>

            <div className="flex items-center gap-3">
              {/* Language Switch */}
              <button
                onClick={toggleLanguage}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 hover:text-slate-900 transition-colors text-xs font-bold shadow-sm"
              >
                <Globe size={14} className="text-govnavy" />
                <span>{i18n.language === 'en' ? 'मराठी' : 'English'}</span>
              </button>

              <button
                onClick={() => setShowLogin(true)}
                className="px-4 py-2 rounded-lg bg-govnavy hover:bg-govblue-700 text-white font-bold text-xs sm:text-sm flex items-center gap-1.5 transition-colors shadow-md"
              >
                <span>{t('landing.sign_in')}</span>
                <LayoutDashboard size={14} />
              </button>
            </div>
          </header>

          {/* Hero Section */}
          <main className="max-w-7xl mx-auto w-full px-6 py-12 sm:py-16 flex-1 grid grid-cols-1 lg:grid-cols-12 gap-12 items-center z-10">
            {/* Left Content */}
            <div className="space-y-6 lg:col-span-6 text-left">
              <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-govnavy/10 text-govnavy text-[11px] font-bold uppercase tracking-wider border border-govnavy/15 select-none">
                <Sparkles size={12} className="text-govsaffron animate-pulse" />
                <span>{t('landing.badge')}</span>
              </div>

              <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-govnavy leading-tight tracking-tight m-0 font-sans">
                {t('landing.headline_1')}<br />
                <span className="text-govsaffron">{t('landing.headline_2')}</span>
              </h1>

              <p className="text-slate-600 text-sm sm:text-base leading-relaxed max-w-xl">
                {t('landing.intro')}
              </p>

              {/* CTAs */}
              <div className="flex flex-wrap gap-4 pt-2">
                <button
                  onClick={() => setShowLogin(true)}
                  className="px-6 py-3 rounded-lg bg-govnavy hover:bg-govblue-700 text-white font-bold text-sm flex items-center gap-2 transition-all shadow-lg hover:translate-y-[-1px]"
                >
                  <span>{t('landing.cta_dashboard')}</span>
                  <ArrowRight size={16} />
                </button>
                <button
                  onClick={() => setShowLogin(true)}
                  className="px-6 py-3 rounded-lg bg-white border border-govsaffron text-govsaffron hover:bg-orange-50/50 font-bold text-sm flex items-center gap-2 transition-all"
                >
                  <Bot size={16} />
                  <span>{t('landing.cta_assistant')}</span>
                </button>
              </div>
            </div>

            {/* Right Flow Diagram Card */}
            <div className="lg:col-span-6 flex items-center justify-center">
              <div className="w-full max-w-md bg-white rounded-xl border border-slate-200 p-6 space-y-5 shadow-sm border-t-4 border-govsaffron relative overflow-hidden">
                <h3 className="text-xs text-slate-500 font-bold uppercase tracking-wider border-b border-slate-100 pb-3 flex items-center gap-2">
                  <Database size={14} className="text-govnavy" />
                  <span>{t('landing.architecture')}</span>
                </h3>

                {/* Vertical Step Flow */}
                <div className="space-y-3.5 text-xs font-semibold font-sans">
                  <div className="flex items-center gap-3 bg-slate-50 p-2.5 rounded border border-slate-200">
                    <span className="w-5 h-5 rounded-full bg-white flex items-center justify-center text-[10px] text-slate-500 font-bold border border-slate-200">
                      1
                    </span>
                    <span className="text-slate-700">
                      {t('landing.arch_1')}
                    </span>
                  </div>
                  <div className="h-3 border-l-2 border-dashed border-govsaffron/40 ml-5"></div>
                  <div className="flex items-center gap-3 bg-slate-50 p-2.5 rounded border border-slate-200">
                    <span className="w-5 h-5 rounded-full bg-white flex items-center justify-center text-[10px] text-slate-500 font-bold border border-slate-200">
                      2
                    </span>
                    <span className="text-slate-700">{t('landing.arch_2')}</span>
                  </div>
                  <div className="h-3 border-l-2 border-dashed border-govsaffron/40 ml-5"></div>
                  <div className="flex items-center gap-3 bg-govblue-50 p-2.5 rounded border border-govblue-200">
                    <span className="w-5 h-5 rounded-full bg-white flex items-center justify-center text-[10px] text-govnavy font-bold border border-govblue-200">
                      3
                    </span>
                    <span className="text-govnavy font-bold flex items-center gap-1">
                      <Sparkles size={12} className="text-govsaffron animate-pulse" />
                      <span>{t('landing.arch_3')}</span>
                    </span>
                  </div>
                  <div className="h-3 border-l-2 border-dashed border-govsaffron/40 ml-5"></div>
                  <div className="flex items-center gap-3 bg-emerald-50 p-2.5 rounded border border-emerald-200">
                    <span className="w-5 h-5 rounded-full bg-white flex items-center justify-center text-[10px] text-govgreen font-bold border border-emerald-200">
                      4
                    </span>
                    <span className="text-govgreen font-extrabold">
                      {t('landing.arch_4')}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </main>

          {/* Features Grid Showcase */}
          <section className="bg-slate-100/80 border-t border-slate-200 py-12">
            <div className="max-w-7xl mx-auto px-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              <div className="bg-white rounded-xl p-5 border border-slate-200 text-left space-y-2.5 border-t-3 border-govsaffron">
                <div className="w-9 h-9 rounded-lg bg-orange-50 flex items-center justify-center text-govsaffron border border-orange-100">
                  <Award size={18} />
                </div>
                <h4 className="text-sm font-bold text-govblue-900 tracking-wide uppercase">
                  {t('landing.f1_title')}
                </h4>
                <p className="text-xs text-slate-500 leading-relaxed">
                  {t('landing.f1_body')}
                </p>
              </div>

              <div className="bg-white rounded-xl p-5 border border-slate-200 text-left space-y-2.5 border-t-3 border-govnavy">
                <div className="w-9 h-9 rounded-lg bg-govblue-50 flex items-center justify-center text-govnavy border border-govblue-100">
                  <Layers size={18} />
                </div>
                <h4 className="text-sm font-bold text-govblue-900 tracking-wide uppercase">
                  {t('landing.f2_title')}
                </h4>
                <p className="text-xs text-slate-500 leading-relaxed">
                  {t('landing.f2_body')}
                </p>
              </div>

              <div className="bg-white rounded-xl p-5 border border-slate-200 text-left space-y-2.5 border-t-3 border-govgreen">
                <div className="w-9 h-9 rounded-lg bg-emerald-50 flex items-center justify-center text-govgreen border border-emerald-100">
                  <AlertTriangle size={18} />
                </div>
                <h4 className="text-sm font-bold text-govblue-900 tracking-wide uppercase">
                  {t('landing.f3_title')}
                </h4>
                <p className="text-xs text-slate-500 leading-relaxed">
                  {t('landing.f3_body')}
                </p>
              </div>

              <div className="bg-white rounded-xl p-5 border border-slate-200 text-left space-y-2.5 border-t-3 border-govnavy">
                <div className="w-9 h-9 rounded-lg bg-govblue-50 flex items-center justify-center text-govnavy border border-govblue-100">
                  <LineChart size={18} />
                </div>
                <h4 className="text-sm font-bold text-govblue-900 tracking-wide uppercase">
                  {t('landing.f4_title')}
                </h4>
                <p className="text-xs text-slate-500 leading-relaxed">
                  {t('landing.f4_body')}
                </p>
              </div>

              <div className="bg-white rounded-xl p-5 border border-slate-200 text-left space-y-2.5 border-t-3 border-govsaffron">
                <div className="w-9 h-9 rounded-lg bg-orange-50 flex items-center justify-center text-govsaffron border border-orange-100">
                  <FileText size={18} />
                </div>
                <h4 className="text-sm font-bold text-govblue-900 tracking-wide uppercase">
                  {t('landing.f5_title')}
                </h4>
                <p className="text-xs text-slate-500 leading-relaxed">
                  {t('landing.f5_body')}
                </p>
              </div>

              <div className="bg-white rounded-xl p-5 border border-slate-200 text-left space-y-2.5 border-t-3 border-govgreen">
                <div className="w-9 h-9 rounded-lg bg-emerald-50 flex items-center justify-center text-govgreen border border-emerald-100">
                  <Bot size={18} />
                </div>
                <h4 className="text-sm font-bold text-govblue-900 tracking-wide uppercase">
                  {t('landing.f6_title')}
                </h4>
                <p className="text-xs text-slate-500 leading-relaxed">
                  {t('landing.f6_body')}
                </p>
              </div>
            </div>
          </section>

          {/* National Informatics Centre (NIC) stamp footer */}
          <footer className="bg-white border-t border-slate-200 z-20 text-[11px] text-slate-500">
            <div className="max-w-7xl mx-auto px-6 py-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <span>{t('landing.copyright')}</span>
              <div className="flex gap-4 font-bold text-slate-600">
                <span className="select-none">{t('landing.designed_by')}</span>
                <span>•</span>
                <a href="#" className="hover:underline">
                  {t('landing.terms')}
                </a>
              </div>
            </div>
          </footer>
        </div>
      )}

      {/* 2. SECURE LOGIN VIEW */}
      {view === 'login' && <Login />}

      {/* 3. DASHBOARD VIEW WITH SIDEBAR */}
      {view === 'dashboard' && user && (
        <div className="flex min-h-screen bg-slate-50">
          <Sidebar
            currentTab={currentTab}
            setCurrentTab={setCurrentTab}
            collapsed={sidebarCollapsed}
            setCollapsed={setSidebarCollapsed}
            role={isAdmin ? 'admin' : isOfficer ? 'officer' : 'citizen'}
            onLogout={handleSignOut}
          />

          <div className="flex-1 flex flex-col min-w-0">
            {/* Topbar Header */}
            <header className="sticky top-0 bg-white border-b border-slate-200 p-4 flex items-center justify-between z-20 select-none shadow-sm">
              <div className="flex items-center gap-3">
                <div className="flex flex-col leading-tight">
                  <span className="text-xs font-extrabold text-govblue-900 uppercase">
                    {village.data
                      ? `${i18n.language === 'en' ? village.data.name : village.data.nameMr} Gram Panchayat`
                      : isAdmin
                        ? 'Haveli Block · Pune District'
                        : 'Gram Panchayat Portal'}
                  </span>
                  {village.data && (
                    <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider">
                      {village.data.blockName} · {village.data.districtName} ·{' '}
                      LGD {village.data.lgdCode ?? '—'}
                    </span>
                  )}
                </div>
                <span className="bg-govgreen/10 text-govgreen text-[9px] px-1.5 py-0.5 rounded font-extrabold uppercase border border-govgreen/20">
                  Active Session
                </span>
                <div className="flex items-center gap-2 border-l border-slate-200 pl-3">
                  <span className="text-[10px] font-bold text-slate-500">SIGNED IN AS:</span>
                  <span className="text-xs font-black text-govnavy uppercase bg-slate-100 border border-slate-200 px-2 py-0.5 rounded">
                    {user.fullName} {isOfficer ? '👤' : '👥'}
                  </span>
                  <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider">
                    {user.role}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <button
                  onClick={handleSignOut}
                  className="text-xs font-bold text-govsaffron hover:text-orange-600 transition-colors"
                >
                  ← Sign Out
                </button>
              </div>
            </header>

            {/* Dashboard Content Outlet */}
            <main className="flex-1 p-6 overflow-y-auto max-w-7xl w-full mx-auto">
              {renderTabContent()}
            </main>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
