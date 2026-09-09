import React from 'react';
import { useTranslation } from 'react-i18next';
import { 
  LayoutDashboard, 
  Users, 
  Landmark, 
  Megaphone, 
  Construction, 
  Notebook, 
  Map, 
  Bot, 
  BarChart3, 
  ChevronLeft,
  ChevronRight,
  Globe,
  LogOut,
  FolderOpen,
  UserPlus,
  KeyRound,
  ScrollText
} from 'lucide-react';

interface SidebarProps {
  currentTab: string;
  setCurrentTab: (tab: string) => void;
  collapsed: boolean;
  setCollapsed: (collapsed: boolean) => void;
  role?: 'officer' | 'citizen' | 'admin';
  onLogout?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ 
  currentTab, 
  setCurrentTab, 
  collapsed, 
  setCollapsed,
  role = 'officer',
  onLogout
}) => {
  const { t, i18n } = useTranslation();

  const toggleLanguage = () => {
    const nextLang = i18n.language === 'en' ? 'mr' : 'en';
    i18n.changeLanguage(nextLang);
  };

  const navItems = role === 'citizen' ? [
    { id: 'dashboard', label: i18n.language === 'en' ? 'Public Info' : 'सार्वजनिक माहिती', icon: LayoutDashboard },
    { id: 'schemes', label: i18n.language === 'en' ? 'Welfare Schemes' : 'कल्याणकारी योजना', icon: Landmark },
    { id: 'grievances', label: i18n.language === 'en' ? 'Track Grievances' : 'तक्रारींचा मागोवा', icon: Megaphone },
    { id: 'documents', label: i18n.language === 'en' ? 'Digital Locker' : 'डिजिटल लॉकर', icon: FolderOpen },
    { id: 'ai_assistant', label: i18n.language === 'en' ? 'AI Helpdesk' : 'AI मदत कक्ष', icon: Bot, isAI: true }
  ] : [
    ...(role === 'admin'
      ? [{
          id: 'district',
          label: i18n.language === 'en' ? 'Block Overview' : 'तालुका आढावा',
          icon: Landmark,
        }]
      : []),
    { id: 'dashboard', label: t('nav.dashboard'), icon: LayoutDashboard },
    { id: 'citizens', label: t('nav.citizens'), icon: Users },
    { id: 'registrations', label: t('registrations.title'), icon: UserPlus },
    { id: 'schemes', label: t('nav.schemes'), icon: Landmark },
    { id: 'grievances', label: t('nav.grievances'), icon: Megaphone },
    { id: 'projects', label: t('nav.projects'), icon: Construction },
    { id: 'sabha', label: t('nav.sabha'), icon: Notebook },
    { id: 'gis_map', label: t('nav.gis_map'), icon: Map },
    { id: 'ai_assistant', label: t('nav.ai_assistant'), icon: Bot, isAI: true },
    { id: 'analytics', label: t('nav.analytics'), icon: BarChart3 },
    {
      id: 'recovery',
      label: i18n.language === 'en' ? 'Account Recovery' : 'खाते पुनर्प्राप्ती',
      icon: KeyRound,
    },
    // The audit trail says which residents an officer's colleagues have been
    // looking at, so it is admin-only — a privacy boundary rather than a
    // seniority one. The server refuses an officer regardless; hiding the tab
    // just stops it being a dead end.
    ...(role === 'admin'
      ? [{
          id: 'audit',
          label: i18n.language === 'en' ? 'Audit Trail' : 'लेखापरीक्षण नोंद',
          icon: ScrollText,
        }]
      : []),
  ];

  return (
    <aside 
      className={`h-screen sticky top-0 flex flex-col justify-between bg-white border-r border-slate-200 transition-all duration-300 z-30 shadow-sm ${
        collapsed ? 'w-20' : 'w-64'
      }`}
    >
      {/* Brand Header */}
      <div>
        <div className="p-4 flex items-center justify-between border-b border-slate-100 bg-slate-50/80">
          <div className="flex items-center gap-3 overflow-hidden">
            {/* Tricolor Emblem Circle */}
            <div className="flex-shrink-0 w-10 h-10 rounded-full bg-gradient-to-tr from-govgreen via-white to-govsaffron p-[2px] flex items-center justify-center shadow-sm border border-slate-200">
              <div className="w-full h-full bg-white rounded-full flex items-center justify-center">
                <span className="text-govnavy font-black text-xs select-none">GP</span>
              </div>
            </div>
            {!collapsed && (
              <div className="flex flex-col select-none">
                <span className="font-extrabold text-govblue-900 tracking-tight text-sm uppercase whitespace-nowrap">{t('app_title')}</span>
                <span className="text-[10px] text-govsaffron font-bold uppercase tracking-wider whitespace-nowrap">{t('app_subtitle')}</span>
              </div>
            )}
          </div>
          <button 
            onClick={() => setCollapsed(!collapsed)}
            className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
          </button>
        </div>

        {/* Navigation List */}
        <nav className="p-3 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            
            return (
              <button
                key={item.id}
                onClick={() => setCurrentTab(item.id)}
                className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs sm:text-sm font-semibold transition-all group relative ${
                  isActive 
                    ? item.isAI
                      ? 'bg-gradient-to-r from-govsaffron to-amber-500 text-white shadow shadow-orange-500/10'
                      : 'bg-govblue-50 border-l-4 border-govnavy text-govnavy'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                }`}
              >
                <Icon 
                  size={18} 
                  className={`flex-shrink-0 transition-transform group-hover:scale-105 ${
                    isActive 
                      ? item.isAI ? 'text-white' : 'text-govnavy' 
                      : item.isAI ? 'text-govsaffron' : 'text-slate-500'
                  }`} 
                />
                {!collapsed && <span className="truncate">{item.label}</span>}
                {item.isAI && !collapsed && (
                  <span className="ml-auto bg-govsaffron/10 text-govsaffron text-[9px] px-1.5 py-0.5 rounded font-bold uppercase tracking-wider border border-govsaffron/20 animate-pulse">
                    AI
                  </span>
                )}
                {collapsed && (
                  <div className="absolute left-full ml-2 px-2 py-1 bg-slate-900 text-slate-100 text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap shadow-md z-50">
                    {item.label}
                  </div>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Language Toggle & User Section */}
      <div className="p-3 border-t border-slate-100 bg-slate-50/50 space-y-3">
        {/* Language Button */}
        <button
          onClick={toggleLanguage}
          className="w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 hover:text-slate-900 transition-colors text-xs font-bold shadow-sm"
          aria-label="Toggle Language / भाषा बदला"
        >
          <Globe size={16} className="text-govnavy" />
          {!collapsed && (
            <div className="flex items-center justify-between w-full">
               <span>भाषा / Language</span>
               <span className="bg-govnavy/10 text-govnavy px-1.5 py-0.5 rounded text-[10px] font-extrabold uppercase border border-govnavy/20">
                {i18n.language === 'en' ? 'मराठी' : 'English'}
              </span>
            </div>
          )}
        </button>

        {/* User Card & Logout Button */}
        <div className="flex items-center justify-between p-1.5 overflow-hidden gap-2">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="w-8 h-8 rounded-full bg-govblue-100 text-govnavy flex items-center justify-center font-extrabold border border-govblue-250 flex-shrink-0 text-xs">
              {role === 'officer' ? 'PO' : 'CT'}
            </div>
            {!collapsed && (
              <div className="flex flex-col select-none text-left truncate">
                <span className="text-xs font-bold text-slate-800 leading-tight block truncate">
                  {role === 'officer' ? 'Panchayat Officer' : 'Village Citizen'}
                </span>
                <span className="text-[10px] text-slate-500 font-medium block truncate">
                  {role === 'officer' ? 'Loni Kalbhor GP' : 'Visitor Mode'}
                </span>
              </div>
            )}
          </div>
          {onLogout && (
            <button 
              onClick={onLogout}
              className="p-1.5 rounded-lg hover:bg-rose-50 text-slate-400 hover:text-rose-600 border border-transparent hover:border-rose-100 transition-all flex-shrink-0"
              title="Sign Out / लॉग आउट"
              aria-label="Sign Out / लॉग आउट"
            >
              <LogOut size={16} />
            </button>
          )}
        </div>
      </div>
    </aside>
  );
};
