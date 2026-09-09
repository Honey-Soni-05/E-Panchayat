/**
 * The resident's own portal: their household record, the village's public
 * information, and their Digital Locker.
 *
 * Two tabs live here. App.tsx routes `schemes`, `grievances` and
 * `ai_assistant` to their own components before this one is reached, so this
 * file only renders the citizen dashboard and the locker.
 *
 * The rule that shapes everything below: a resident sees their own record and
 * their own documents, and nothing about any other resident. The server binds
 * a citizen token to one citizen_id and refuses the rest, but nothing here
 * asks for another person's data in the first place. The screen this replaced
 * fell back to `CITIZENS[0]` whenever the signed-in id did not match a mock
 * row, which meant an unlinked account was shown a stranger's age, income and
 * occupation as if they were its own. That fallback is gone: an account with
 * no village record now says so.
 */

import React, { useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Award,
  Bot,
  Building,
  Calendar,
  Check,
  Construction,
  Droplets,
  FileText,
  FolderOpen,
  GraduationCap,
  Landmark,
  Loader2,
  MapPin,
  Plus,
  Stethoscope,
  Upload,
  Users,
} from 'lucide-react';

import {
  api,
  type Citizen,
  type CitizenDocument,
  type Facility,
  type Project,
  type SabhaMeeting,
  type Village,
} from '../lib/api';
import { useMutation, useQuery } from '../lib/useApi';
import { EmptyState, ErrorNotice } from './schemes/SchemeBits';

interface CitizenPortalProps {
  currentTab: string;
  setCurrentTab: (tab: string) => void;
  citizenId: string;
}

/** The Marathi label travels with the upload so the officer's queue and the
 *  resident's locker name the same document identically in both languages. */
const DOC_TYPES: { en: string; mr: string }[] = [
  { en: 'Income Certificate', mr: 'उत्पन्नाचा दाखला' },
  { en: 'Aadhaar Card', mr: 'आधार कार्ड' },
  { en: 'Land ownership 7/12 Extract', mr: '७/१२ उतारा' },
];

const DOC_STATUS_STYLE: Record<CitizenDocument['status'], string> = {
  Verified: 'bg-emerald-50 text-emerald-600 border-emerald-200',
  'Pending Verification': 'bg-amber-50 text-amber-600 border-amber-200',
  Rejected: 'bg-rose-50 text-rose-600 border-rose-200',
};

const DOC_ICON_STYLE: Record<CitizenDocument['status'], string> = {
  Verified: 'bg-emerald-50 text-emerald-600 border-emerald-150',
  'Pending Verification': 'bg-amber-50 text-amber-600 border-amber-150',
  Rejected: 'bg-rose-50 text-rose-600 border-rose-150',
};

const PROJECT_BAR: Record<Project['status'], string> = {
  Completed: 'bg-govgreen',
  Ongoing: 'bg-govnavy',
  Delayed: 'bg-rose-500',
};

/** Facilities carry a bare type string and no Marathi for it, so the label is
 *  supplied here rather than printed raw. */
const FACILITY_LABEL: Record<string, { en: string; mr: string }> = {
  water: { en: 'Water Facility', mr: 'पाणी सुविधा' },
  school: { en: 'School', mr: 'शाळा' },
  health: { en: 'Health Facility', mr: 'आरोग्य सुविधा' },
};

const facilityIcon = (facilityType: string) => {
  const key = (facilityType || '').toLowerCase();
  if (key === 'water') return Droplets;
  if (key === 'school') return GraduationCap;
  if (key === 'health') return Stethoscope;
  return Landmark;
};

const formatDate = (value: string | null, isEnglish: boolean): string => {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString(isEnglish ? 'en-IN' : 'mr-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
};

const formatLakh = (rupees: number): string => `₹${(rupees / 100000).toFixed(1)}`;

const formatSize = (bytes: number | null): string | null => {
  if (bytes === null || bytes <= 0) return null;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const Loading: React.FC<{ label: string }> = ({ label }) => (
  <div className="flex items-center justify-center gap-2 py-8 text-slate-400">
    <Loader2 size={16} className="animate-spin" />
    <span className="text-xs font-bold uppercase tracking-wider">{label}</span>
  </div>
);

const Field: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div className="p-2.5 rounded bg-slate-50 border border-slate-200">
    <span className="text-[9px] text-slate-400 font-bold uppercase tracking-wider block">
      {label}
    </span>
    <span className="text-xs text-slate-800 font-semibold block mt-0.5">{value}</span>
  </div>
);

export const CitizenPortal: React.FC<CitizenPortalProps> = ({
  currentTab,
  setCurrentTab,
  citizenId,
}) => {
  const { i18n } = useTranslation();
  const isEnglish = i18n.language === 'en';

  // An approved account can still have no village record behind it — the
  // officer who approved the sign-up never matched it to the register.
  // Requesting /citizens/ would be a 404 and /documents would be pointless,
  // so nothing personal is fetched until there is an id to fetch it for.
  const linked = citizenId.trim().length > 0;

  // Anything that is not the locker is the home screen; the other citizen
  // tabs never reach this component.
  const onLocker = currentTab === 'documents';
  const onDashboard = !onLocker;

  const me = useQuery<Citizen | null>(
    () => (linked ? api.citizens.get(citizenId) : Promise.resolve(null)),
    [citizenId, linked],
  );

  const village = useQuery<Village | null>(() => api.villages.current(), []);

  const projects = useQuery<Project[]>(
    () => (onDashboard ? api.projects.list() : Promise.resolve([])),
    [onDashboard],
  );

  const facilities = useQuery<Facility[]>(
    () => (onDashboard ? api.facilities.list() : Promise.resolve([])),
    [onDashboard],
  );

  const meetings = useQuery<SabhaMeeting[]>(
    () => (onDashboard ? api.sabha.meetings() : Promise.resolve([])),
    [onDashboard],
  );

  const documents = useQuery<CitizenDocument[]>(
    () => (linked && onLocker ? api.documents.list({ citizenId }) : Promise.resolve([])),
    [citizenId, linked, onLocker],
  );

  // ─── Locker upload ────────────────────────────────────────────────────────

  const [docType, setDocType] = useState<string>('Income Certificate');
  const [file, setFile] = useState<File | null>(null);
  const [uploaded, setUploaded] = useState<CitizenDocument | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const upload = useMutation(
    (chosen: File, type: string) => {
      const match = DOC_TYPES.find((d) => d.en === type);
      return api.documents.upload(citizenId, type, match?.mr ?? type, chosen);
    },
    (created) => {
      // The confirmation quotes what the server stored, so it cannot claim a
      // save that did not happen.
      setUploaded(created);
      setFile(null);
      if (fileRef.current) fileRef.current.value = '';
      documents.refetch();
    },
  );

  // ─── Derived village figures ──────────────────────────────────────────────

  const projectRows = projects.data ?? [];
  const facilityRows = facilities.data ?? [];
  const docRows = documents.data ?? [];

  const projectCounts = useMemo(
    () => ({
      ongoing: projectRows.filter((p) => p.status === 'Ongoing').length,
      delayed: projectRows.filter((p) => p.status === 'Delayed').length,
      completed: projectRows.filter((p) => p.status === 'Completed').length,
    }),
    [projectRows],
  );

  const docCounts = useMemo(
    () => ({
      verified: docRows.filter((d) => d.status === 'Verified').length,
      pending: docRows.filter((d) => d.status === 'Pending Verification').length,
      rejected: docRows.filter((d) => d.status === 'Rejected').length,
    }),
    [docRows],
  );

  // Meetings arrive newest first from the server.
  const latestMeeting = meetings.data?.[0] ?? null;

  const villageName = village.data
    ? isEnglish
      ? village.data.name
      : village.data.nameMr
    : null;

  return (
    <div className="space-y-6">
      {/* Citizen Banner */}
      <div className="relative overflow-hidden rounded-xl bg-white border border-slate-200 shadow-sm p-5 border-t-4 border-govgreen">
        <div className="max-w-3xl space-y-1">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded bg-govgreen/10 text-govgreen text-[10px] font-bold uppercase tracking-wider border border-govgreen/15 select-none">
            <span>
              {isEnglish ? 'Citizen Public Services Access' : 'नागरिक सार्वजनिक सेवा प्रवेश'}
            </span>
          </div>
          <h1 className="text-xl font-bold text-govblue-900 m-0">
            {villageName
              ? `${villageName} ${isEnglish ? 'Citizen Facilitation Portal' : 'नागरिक सुविधा पोर्टल'}`
              : isEnglish
                ? 'Citizen Facilitation Portal'
                : 'नागरिक सुविधा पोर्टल'}
          </h1>
          <p className="text-slate-500 text-xs leading-relaxed">
            {isEnglish
              ? 'Your own household record, the documents you have submitted to the Panchayat, and what the Gram Panchayat is currently building in your village.'
              : 'तुमच्या कुटुंबाची नोंद, तुम्ही ग्रामपंचायतीकडे सादर केलेली कागदपत्रे आणि गावात सुरू असलेली विकासकामे.'}
          </p>
        </div>
      </div>

      {village.error && <ErrorNotice message={village.error} onRetry={village.refetch} />}

      {!linked && (
        <div
          role="status"
          className="rounded-xl border border-amber-200 bg-amber-50 p-4 space-y-1"
        >
          <p className="text-xs font-bold text-amber-900 m-0">
            {isEnglish
              ? 'Your account is not linked to a village record yet.'
              : 'तुमचे खाते अद्याप गावाच्या नोंदीशी जोडलेले नाही.'}
          </p>
          <p className="text-[11px] text-amber-800 m-0 leading-relaxed">
            {isEnglish
              ? 'An officer has to match your registration to the village register before your household details and your Digital Locker can be shown. Village information below is still available to you.'
              : 'तुमची नोंदणी गावाच्या नोंदवहीशी जुळवल्यानंतरच तुमची कौटुंबिक माहिती आणि डिजिटल लॉकर दिसेल. खालील गाव माहिती तुम्हाला आताही पाहता येईल.'}
          </p>
        </div>
      )}

      {/* ─── Home screen ───────────────────────────────────────────────────── */}
      {onDashboard && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
            {/* The resident's own record */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4">
              <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-slate-100 pb-2 flex items-center gap-1.5">
                <Users size={14} className="text-govnavy" />
                <span>{isEnglish ? 'My Household Record' : 'माझ्या कुटुंबाची नोंद'}</span>
              </h2>

              {me.error && <ErrorNotice message={me.error} onRetry={me.refetch} />}

              {linked && me.loading && (
                <Loading label={isEnglish ? 'Loading your record' : 'नोंद लोड होत आहे'} />
              )}

              {!linked && (
                <p className="text-xs text-slate-400 py-6 text-center m-0">
                  {isEnglish
                    ? 'Nothing to show until your account is linked to the village register.'
                    : 'खाते गावाच्या नोंदवहीशी जोडेपर्यंत येथे काहीही दिसणार नाही.'}
                </p>
              )}

              {me.data && (
                <div className="space-y-4">
                  <div>
                    <strong className="text-sm font-bold text-govblue-900 block">
                      {isEnglish ? me.data.name : me.data.nameMr}
                    </strong>
                    <span className="text-[10px] font-mono text-slate-400 block mt-0.5">
                      {me.data.id}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <Field
                      label={isEnglish ? 'Ward' : 'वॉर्ड'}
                      value={isEnglish ? `Ward ${me.data.ward}` : `वॉर्ड ${me.data.ward}`}
                    />
                    <Field
                      label={isEnglish ? 'Age' : 'वय'}
                      value={
                        isEnglish ? `${me.data.age} years` : `${me.data.age} वर्षे`
                      }
                    />
                    <Field
                      label={isEnglish ? 'Occupation' : 'व्यवसाय'}
                      value={isEnglish ? me.data.occupation : me.data.occupationMr}
                    />
                    <Field
                      label={isEnglish ? 'Annual Income' : 'वार्षिक उत्पन्न'}
                      value={`₹${me.data.income.toLocaleString('en-IN')}`}
                    />
                    <Field
                      label={isEnglish ? 'Gender' : 'लिंग'}
                      value={isEnglish ? me.data.gender : me.data.genderMr}
                    />
                    {me.data.phone && (
                      <Field
                        label={isEnglish ? 'Phone on record' : 'नोंदवलेला दूरध्वनी'}
                        value={<span className="font-mono">{me.data.phone}</span>}
                      />
                    )}
                  </div>

                  {/* Family as the register actually holds it */}
                  <div className="space-y-2 pt-1">
                    <h3 className="text-xs font-bold text-slate-700 m-0">
                      {me.data.familyName
                        ? isEnglish
                          ? me.data.familyName
                          : me.data.familyNameMr ?? me.data.familyName
                        : isEnglish
                          ? 'Family members'
                          : 'कुटुंबातील सदस्य'}
                    </h3>

                    {me.data.familyMembers.length === 0 ? (
                      <p className="text-[11px] text-slate-400 m-0">
                        {isEnglish
                          ? 'No other family members are recorded against your household.'
                          : 'तुमच्या कुटुंबात इतर सदस्यांची नोंद नाही.'}
                      </p>
                    ) : (
                      <ul className="space-y-1.5 list-none p-0 m-0">
                        {me.data.familyMembers.map((member) => (
                          <li
                            key={member.id}
                            className="p-2.5 rounded bg-slate-50 border border-slate-200 flex items-center justify-between gap-3"
                          >
                            <span className="text-xs font-semibold text-slate-800 truncate">
                              {isEnglish ? member.name : member.nameMr}
                              {member.isHead && (
                                <span className="ml-1.5 px-1.5 py-0.5 rounded bg-govblue-50 border border-govblue-200 text-govnavy text-[9px] font-bold uppercase tracking-wider">
                                  {isEnglish ? 'Head' : 'प्रमुख'}
                                </span>
                              )}
                            </span>
                            <span className="text-[10px] text-slate-500 font-semibold flex-shrink-0">
                              {(isEnglish ? member.relation : member.relationMr) ?? '—'}
                              {' · '}
                              {isEnglish ? `${member.age} yrs` : `${member.age} वर्षे`}
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Core actions entry card */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4 flex flex-col justify-between">
              <div className="space-y-4">
                <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-slate-100 pb-2">
                  {isEnglish ? 'Available Actions' : 'उपलब्ध सेवा/कृती'}
                </h2>
                <p className="text-xs text-slate-600 leading-relaxed">
                  {isEnglish
                    ? 'Check which welfare schemes you qualify for, file a complaint about local infrastructure and follow what happens to it, keep your certificates in the Digital Locker, or ask the helpdesk a question about Panchayat records.'
                    : 'तुम्ही कोणत्या कल्याणकारी योजनांसाठी पात्र आहात ते पहा, स्थानिक समस्येची तक्रार नोंदवून तिचा मागोवा घ्या, तुमची प्रमाणपत्रे डिजिटल लॉकरमध्ये ठेवा किंवा मदत कक्षाला प्रश्न विचारा.'}
                </p>
              </div>

              <div className="grid grid-cols-4 gap-2 pt-4">
                <button
                  onClick={() => setCurrentTab('schemes')}
                  className="p-2.5 bg-govblue-50 border border-govblue-200 hover:bg-govblue-100 text-govnavy rounded-lg text-center font-bold text-xs space-y-1.5 transition-colors"
                >
                  <Award size={16} className="mx-auto text-govnavy" />
                  <span className="block text-[9px]">
                    {isEnglish ? 'Welfare Schemes' : 'कल्याणकारी योजना'}
                  </span>
                </button>
                <button
                  onClick={() => setCurrentTab('grievances')}
                  className="p-2.5 bg-rose-50 border border-rose-200 hover:bg-rose-100 text-rose-700 rounded-lg text-center font-bold text-xs space-y-1.5 transition-colors"
                >
                  <Plus size={16} className="mx-auto text-rose-600" />
                  <span className="block text-[9px]">
                    {isEnglish ? 'File Grievance' : 'तक्रार नोंदवा'}
                  </span>
                </button>
                <button
                  onClick={() => setCurrentTab('documents')}
                  className="p-2.5 bg-emerald-50 border border-emerald-250 hover:bg-emerald-100 text-govgreen rounded-lg text-center font-bold text-xs space-y-1.5 transition-colors"
                >
                  <FolderOpen size={16} className="mx-auto text-govgreen" />
                  <span className="block text-[9px]">
                    {isEnglish ? 'Digital Locker' : 'डिजिटल लॉकर'}
                  </span>
                </button>
                <button
                  onClick={() => setCurrentTab('ai_assistant')}
                  className="p-2.5 bg-orange-50 border border-orange-200 hover:bg-orange-100 text-govsaffron rounded-lg text-center font-bold text-xs space-y-1.5 transition-colors"
                >
                  <Bot size={16} className="mx-auto text-govsaffron" />
                  <span className="block text-[9px]">
                    {isEnglish ? 'AI Helpdesk' : 'एआय मदतनीस'}
                  </span>
                </button>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
            {/* Village public information */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4">
              <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-slate-100 pb-2 flex items-center gap-1.5">
                <Building size={14} className="text-govnavy" />
                <span>
                  {isEnglish
                    ? 'Village Public Information Board'
                    : 'ग्राम सार्वजनिक माहिती फलक'}
                </span>
              </h2>

              {village.loading && (
                <Loading
                  label={isEnglish ? 'Loading village details' : 'गावाची माहिती लोड होत आहे'}
                />
              )}

              {!village.loading && !village.data && !village.error && (
                <p className="text-xs text-slate-400 py-6 text-center m-0">
                  {isEnglish
                    ? 'No Gram Panchayat is attached to this account.'
                    : 'या खात्याशी कोणतीही ग्रामपंचायत जोडलेली नाही.'}
                </p>
              )}

              {village.data && (
                <div className="p-3 bg-slate-50 rounded border border-slate-200 flex items-start gap-3 text-xs">
                  <MapPin className="text-govnavy flex-shrink-0" size={16} />
                  <div className="min-w-0 space-y-0.5">
                    <strong className="text-slate-800 block">
                      {isEnglish ? village.data.name : village.data.nameMr}
                    </strong>
                    <span className="text-slate-500 block">
                      {isEnglish ? village.data.blockName : village.data.blockNameMr}
                      {' · '}
                      {isEnglish ? village.data.districtName : village.data.districtNameMr}
                      {' · '}
                      {isEnglish ? village.data.stateName : village.data.stateNameMr}
                    </span>
                    <span className="text-slate-500 block">
                      {isEnglish
                        ? `${village.data.wardCount} wards`
                        : `${village.data.wardCount} वॉर्ड`}
                      {village.data.population2011 !== null && (
                        <>
                          {' · '}
                          {isEnglish
                            ? `Population ${village.data.population2011.toLocaleString('en-IN')} (Census 2011)`
                            : `लोकसंख्या ${village.data.population2011.toLocaleString('en-IN')} (जनगणना २०११)`}
                        </>
                      )}
                    </span>
                    {village.data.lgdCode !== null && (
                      <span className="text-[10px] text-slate-400 font-mono block">
                        LGD {village.data.lgdCode}
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Gram Sabha. The API records meetings that have happened; it
                  does not hold a schedule, so this is labelled as the last
                  recorded sitting rather than an upcoming one. */}
              {meetings.error && (
                <ErrorNotice message={meetings.error} onRetry={meetings.refetch} />
              )}

              {meetings.loading && (
                <Loading
                  label={isEnglish ? 'Loading Gram Sabha record' : 'ग्रामसभा नोंद लोड होत आहे'}
                />
              )}

              {!meetings.loading && !meetings.error && !latestMeeting && (
                <p className="text-xs text-slate-400 m-0">
                  {isEnglish
                    ? 'No Gram Sabha proceedings have been published yet.'
                    : 'अद्याप कोणतीही ग्रामसभा कार्यवाही प्रसिद्ध झालेली नाही.'}
                </p>
              )}

              {latestMeeting && (
                <div className="p-3 bg-slate-50 rounded border border-slate-200 flex items-start gap-3 text-xs">
                  <Calendar className="text-govsaffron flex-shrink-0" size={16} />
                  <div className="min-w-0 space-y-1">
                    <strong className="text-slate-800 block">
                      {isEnglish ? latestMeeting.title : latestMeeting.titleMr}
                    </strong>
                    <span className="text-slate-500 block">
                      {isEnglish ? 'Last recorded Gram Sabha' : 'शेवटची नोंदवलेली ग्रामसभा'}
                      {': '}
                      {formatDate(latestMeeting.meetingDate, isEnglish)}
                    </span>
                    {(isEnglish ? latestMeeting.decisions : latestMeeting.decisionsMr).length >
                      0 && (
                      <ul className="list-disc pl-4 m-0 space-y-0.5 text-slate-600">
                        {(isEnglish
                          ? latestMeeting.decisions
                          : latestMeeting.decisionsMr
                        ).map((decision, idx) => (
                          <li key={idx} className="text-[11px] leading-relaxed">
                            {decision}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Public facilities */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4">
              <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-slate-100 pb-2 flex items-center gap-1.5">
                <Landmark size={14} className="text-govnavy" />
                <span>{isEnglish ? 'Public Facilities' : 'सार्वजनिक सुविधा'}</span>
              </h2>

              {facilities.error && (
                <ErrorNotice message={facilities.error} onRetry={facilities.refetch} />
              )}

              {facilities.loading && (
                <Loading label={isEnglish ? 'Loading facilities' : 'सुविधा लोड होत आहेत'} />
              )}

              {!facilities.loading && !facilities.error && facilityRows.length === 0 && (
                <EmptyState
                  title={
                    isEnglish
                      ? 'No public facilities are mapped yet'
                      : 'अद्याप कोणतीही सार्वजनिक सुविधा नोंदवलेली नाही'
                  }
                  hint={
                    isEnglish
                      ? 'The Panchayat office adds schools, health centres and water points as they are surveyed.'
                      : 'शाळा, आरोग्य केंद्रे आणि पाणी स्रोत सर्वेक्षणानंतर ग्रामपंचायत कार्यालय नोंदवते.'
                  }
                />
              )}

              {facilityRows.length > 0 && (
                <ul className="space-y-2 list-none p-0 m-0">
                  {facilityRows.map((facility) => {
                    const Icon = facilityIcon(facility.facilityType);
                    const label = FACILITY_LABEL[facility.facilityType.toLowerCase()];
                    const details = isEnglish
                      ? facility.details
                      : facility.detailsMr ?? facility.details;
                    return (
                      <li
                        key={facility.id}
                        className="p-2.5 rounded bg-slate-50 border border-slate-200 flex items-start gap-2.5"
                      >
                        <Icon size={14} className="text-govgreen flex-shrink-0 mt-0.5" />
                        <div className="min-w-0">
                          <span className="text-xs font-semibold text-slate-800 block">
                            {isEnglish ? facility.name : facility.nameMr}
                          </span>
                          <span className="text-[10px] text-slate-500 block mt-0.5">
                            {label
                              ? isEnglish
                                ? label.en
                                : label.mr
                              : facility.facilityType}
                            {facility.ward !== null && (
                              <>
                                {' · '}
                                {isEnglish
                                  ? `Ward ${facility.ward}`
                                  : `वॉर्ड ${facility.ward}`}
                              </>
                            )}
                          </span>
                          {details && (
                            <span className="text-[10px] text-slate-500 block mt-0.5 leading-relaxed">
                              {details}
                            </span>
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </div>

          {/* Development projects in the village */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4">
            <div className="border-b border-slate-100 pb-2 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5 m-0">
                <Construction size={14} className="text-govnavy" />
                <span>
                  {isEnglish ? 'Development Work in the Village' : 'गावातील विकासकामे'}
                </span>
              </h2>
              {projectRows.length > 0 && (
                <span className="text-[10px] text-slate-500 font-semibold">
                  {isEnglish
                    ? `${projectCounts.ongoing} ongoing · ${projectCounts.delayed} delayed · ${projectCounts.completed} completed`
                    : `${projectCounts.ongoing} सुरू · ${projectCounts.delayed} विलंबित · ${projectCounts.completed} पूर्ण`}
                </span>
              )}
            </div>

            {projects.error && (
              <ErrorNotice message={projects.error} onRetry={projects.refetch} />
            )}

            {projects.loading && (
              <Loading label={isEnglish ? 'Loading projects' : 'प्रकल्प लोड होत आहेत'} />
            )}

            {!projects.loading && !projects.error && projectRows.length === 0 && (
              <EmptyState
                title={
                  isEnglish
                    ? 'No development work is recorded for your village'
                    : 'तुमच्या गावासाठी कोणतेही विकासकाम नोंदवलेले नाही'
                }
              />
            )}

            {projectRows.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {projectRows.map((project) => (
                  <div
                    key={project.id}
                    className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 space-y-2"
                  >
                    <div className="space-y-0.5">
                      <strong className="text-xs font-bold text-slate-800 block leading-snug">
                        {isEnglish ? project.name : project.nameMr}
                      </strong>
                      <span className="text-[10px] text-slate-500 block">
                        {isEnglish ? `Ward ${project.ward}` : `वॉर्ड ${project.ward}`}
                        {' · '}
                        {isEnglish ? project.location : project.locationMr}
                      </span>
                    </div>

                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[9px] font-extrabold uppercase tracking-wider text-slate-500">
                        {isEnglish ? project.status : project.statusMr}
                      </span>
                      <span className="text-[10px] font-bold text-slate-700">
                        {project.progress}%
                      </span>
                    </div>

                    <div
                      className="h-1.5 w-full rounded-full bg-slate-200 overflow-hidden"
                      role="img"
                      aria-label={
                        isEnglish
                          ? `${project.progress} percent complete`
                          : `${project.progress} टक्के पूर्ण`
                      }
                    >
                      <div
                        className={`h-full rounded-full ${PROJECT_BAR[project.status]}`}
                        style={{ width: `${Math.min(100, Math.max(0, project.progress))}%` }}
                      />
                    </div>

                    {/* Project.budget and .utilized are rupees; converted to
                        lakh here so the two figures read at village scale. */}
                    <span className="text-[10px] text-slate-500 block">
                      {isEnglish ? 'Spent' : 'खर्च'} {formatLakh(project.utilized)}{' '}
                      {isEnglish ? 'lakh of' : 'लाख, एकूण'} {formatLakh(project.budget)}{' '}
                      {isEnglish ? 'lakh' : 'लाख'}
                    </span>

                    {project.expectedCompletion && (
                      <span className="text-[10px] text-slate-400 block">
                        {isEnglish ? 'Expected by' : 'अपेक्षित पूर्तता'}{' '}
                        {formatDate(project.expectedCompletion, isEnglish)}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─── Digital Locker ────────────────────────────────────────────────── */}
      {onLocker && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Upload */}
          <div className="lg:col-span-5 bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4">
            <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-slate-100 pb-2">
              {isEnglish
                ? 'Upload Document for Verification'
                : 'पडताळणीसाठी दस्तऐवज अपलोड करा'}
            </h2>

            {uploaded && (
              <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-700 rounded text-xs font-bold flex items-start gap-1.5">
                <Check size={14} className="flex-shrink-0 mt-0.5" />
                <span>
                  {isEnglish
                    ? `${uploaded.fileName} received. Status: ${uploaded.status}.`
                    : `${uploaded.fileName} प्राप्त झाले. स्थिती: ${uploaded.statusMr}.`}
                </span>
              </div>
            )}

            {upload.error && <ErrorNotice message={upload.error} />}

            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (file) upload.run(file, docType);
              }}
              className="space-y-4 text-xs font-semibold"
            >
              <div className="space-y-1.5">
                <label htmlFor="doc-type" className="text-slate-500 block">
                  {isEnglish ? 'Select Document Type' : 'दस्तऐवजाचा प्रकार निवडा'}
                </label>
                <select
                  id="doc-type"
                  value={docType}
                  onChange={(e) => setDocType(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded text-slate-700 bg-white"
                >
                  {DOC_TYPES.map((type) => (
                    <option key={type.en} value={type.en}>
                      {isEnglish ? `${type.en} / ${type.mr}` : type.mr}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="doc-file" className="text-slate-500 block">
                  {isEnglish ? 'Select Document File' : 'फाईल निवडा'}
                </label>
                <input
                  id="doc-file"
                  ref={fileRef}
                  type="file"
                  required
                  accept=".pdf,image/jpeg,image/png,image/webp"
                  onChange={(e) => {
                    setFile(e.target.files?.[0] ?? null);
                    setUploaded(null);
                    upload.clearError();
                  }}
                  className="w-full px-3 py-2 border border-slate-200 rounded text-slate-700 bg-white cursor-pointer focus:outline-none"
                />
              </div>

              <button
                type="submit"
                disabled={!linked || !file || upload.saving}
                className="w-full py-2.5 bg-govnavy hover:bg-govblue-700 disabled:bg-slate-200 disabled:text-slate-400 text-white rounded font-bold transition-all shadow flex items-center justify-center gap-1.5"
              >
                {upload.saving ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Upload size={14} />
                )}
                <span>
                  {isEnglish
                    ? 'Upload to Panchayat Records'
                    : 'ग्रामपंचायत अभिलेखात अपलोड करा'}
                </span>
              </button>

              {!linked && (
                <p className="text-[11px] text-slate-500 m-0 leading-relaxed">
                  {isEnglish
                    ? 'Uploading needs your account to be linked to a village record first.'
                    : 'अपलोड करण्यासाठी आधी तुमचे खाते गावाच्या नोंदीशी जोडलेले असणे आवश्यक आहे.'}
                </p>
              )}
            </form>
          </div>

          {/* The locker itself */}
          <div className="lg:col-span-7 bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4">
            <div className="border-b border-slate-100 pb-2 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wider m-0">
                {isEnglish
                  ? 'Digital Locker & Verification Status'
                  : 'डिजिटल लॉकर आणि पडताळणी स्थिती'}
              </h2>
              {docRows.length > 0 && (
                <span className="text-[10px] text-slate-500 font-semibold">
                  {isEnglish
                    ? `${docCounts.verified} verified · ${docCounts.pending} awaiting check · ${docCounts.rejected} rejected`
                    : `${docCounts.verified} पडताळणी पूर्ण · ${docCounts.pending} प्रतीक्षेत · ${docCounts.rejected} अस्वीकृत`}
                </span>
              )}
            </div>

            {documents.error && (
              <ErrorNotice message={documents.error} onRetry={documents.refetch} />
            )}

            {linked && documents.loading && (
              <Loading
                label={isEnglish ? 'Loading your documents' : 'तुमची कागदपत्रे लोड होत आहेत'}
              />
            )}

            {!linked && (
              <p className="text-xs text-slate-400 py-8 text-center m-0">
                {isEnglish
                  ? 'Your locker opens once an officer links your account to the village register.'
                  : 'अधिकाऱ्याने तुमचे खाते गावाच्या नोंदवहीशी जोडल्यावर तुमचा लॉकर उघडेल.'}
              </p>
            )}

            {linked && !documents.loading && !documents.error && docRows.length === 0 && (
              <EmptyState
                title={
                  isEnglish
                    ? 'Your locker is empty'
                    : 'तुमचा लॉकर रिकामा आहे'
                }
                hint={
                  isEnglish
                    ? 'Upload a certificate on the left and an officer will verify it. Verified documents count towards your scheme eligibility.'
                    : 'डाव्या बाजूने दस्तऐवज अपलोड करा; अधिकारी त्याची पडताळणी करतील. पडताळलेली कागदपत्रे योजना पात्रतेसाठी ग्राह्य धरली जातात.'
                }
              />
            )}

            {docRows.length > 0 && (
              <div className="space-y-3">
                {docRows.map((doc) => {
                  const size = formatSize(doc.sizeBytes);
                  return (
                    <div
                      key={doc.id}
                      className="p-3.5 bg-slate-50 border border-slate-200 rounded-lg space-y-2"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex items-start gap-3 min-w-0">
                          <div
                            className={`w-8 h-8 rounded flex items-center justify-center border flex-shrink-0 ${DOC_ICON_STYLE[doc.status]}`}
                          >
                            <FileText size={16} />
                          </div>
                          <div className="min-w-0">
                            <strong className="text-xs font-bold text-slate-800 block">
                              {isEnglish ? doc.docType : doc.docTypeMr}
                            </strong>
                            <span className="text-[10px] font-mono text-slate-400 block mt-0.5 break-all">
                              {doc.fileName}
                              {size && ` · ${size}`}
                            </span>
                            <span className="text-[10px] text-slate-500 block mt-0.5">
                              {isEnglish ? 'Submitted' : 'सादर'}{' '}
                              {formatDate(doc.submittedDate, isEnglish)}
                              {doc.verifiedAt && (
                                <>
                                  {' · '}
                                  {isEnglish ? 'Checked' : 'तपासले'}{' '}
                                  {formatDate(doc.verifiedAt, isEnglish)}
                                </>
                              )}
                            </span>
                          </div>
                        </div>

                        <span
                          className={`px-2 py-0.5 rounded text-[9px] font-extrabold uppercase tracking-wider border whitespace-nowrap flex-shrink-0 ${DOC_STATUS_STYLE[doc.status]}`}
                        >
                          {isEnglish ? doc.status : doc.statusMr}
                        </span>
                      </div>

                      {/* A rejection the resident cannot read is a rejection
                          they cannot act on. */}
                      {doc.status === 'Rejected' && doc.rejectionReason && (
                        <p className="text-[11px] text-rose-800 bg-rose-50 border border-rose-100 rounded p-2 m-0 leading-relaxed">
                          <strong>{isEnglish ? 'Reason: ' : 'कारण: '}</strong>
                          {doc.rejectionReason}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
