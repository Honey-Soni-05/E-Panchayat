import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2 } from 'lucide-react';

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
import { AccountRecovery } from './components/AccountRecovery';
import { AuditTrail } from './components/AuditTrail';
import { Login } from './components/Login';
import { Landing } from './components/Landing';

// Import i18n initialization
import './i18n/i18n';
import { useAuth } from './lib/auth';
import { clearPersistentCache } from './lib/persistence';
import { api, type Village } from './lib/api';
import { useQuery } from './lib/useApi';

function App() {
  const { i18n } = useTranslation();
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
      case 'recovery':
        return <AccountRecovery />;
      case 'audit':
        // Admin only. The server refuses anyone else, so this is the tab
        // matching the rule rather than the rule itself.
        return isAdmin ? <AuditTrail /> : <Dashboard setCurrentTab={setCurrentTab} />;
      default:
        return <Dashboard setCurrentTab={setCurrentTab} />;
    }
  };

  return (
    <div className="app-shell min-h-screen text-slate-800 bg-[#f4f6f9] font-sans selection:bg-govsaffron selection:text-white">
      {/* 0. RESTORING AN EXISTING SESSION */}
      {view === 'restoring' && (
        <div className="min-h-screen flex flex-col items-center justify-center gap-3 bg-slate-50">
          <Loader2 size={28} className="animate-spin text-govnavy" />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Restoring your session
          </span>
        </div>
      )}

      {/* 1. PUBLIC HOME PAGE */}
      {view === 'landing' && <Landing onSignIn={() => setShowLogin(true)} />}

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
            <header className="app-topbar sticky top-0 bg-white border-b border-slate-200 p-4 flex items-center justify-between z-20 select-none shadow-sm">
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
            <main key={currentTab} className="app-main flex-1 p-6 overflow-y-auto max-w-7xl w-full mx-auto">
              {renderTabContent()}
            </main>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
