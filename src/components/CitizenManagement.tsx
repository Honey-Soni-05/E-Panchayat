/**
 * The officer's resident directory, and the document verification queue.
 *
 * Both halves used to run on the hardcoded CITIZENS / SCHEMES /
 * CITIZEN_DOCUMENTS arrays, and a verification decision was written with
 * savePersistentData — localStorage only, so an approval an officer made on one
 * machine did not exist on any other. Every read here is now an API call scoped
 * to the officer's own Gram Panchayat, and every write goes to the server with
 * its error shown on screen.
 *
 * Three things changed beyond swapping the data source:
 *
 * 1. Search and ward filtering are done by the server (`/citizens?search=&ward=`)
 *    rather than by filtering a full in-memory list, so the client never has to
 *    hold the whole register to answer "who is Savita Patil".
 * 2. Scheme eligibility comes from `/citizens/{id}/eligibility`, which returns a
 *    status and a written reason per scheme. The old screen printed a row of
 *    purple chips from a static `eligibleSchemes` array with no reasoning at
 *    all — it could say a person qualified without anything having been checked.
 * 3. Rejecting a document now requires a written reason. An officer who rejects
 *    an income certificate silently forces that resident to travel back to the
 *    office to find out what was wrong with it.
 *
 * Removed: the document "preview" modal, which drew a fake Income Certificate,
 * a fake Aadhaar card (a hardcoded 12-digit number and an invented date of
 * birth) and a fake 7/12 land extract with an invented survey number, area and
 * tax figure. The API stores document metadata, not the document, so there is
 * nothing real to render. The review dialog now shows the actual stored record.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Search,
  User,
  MapPin,
  Briefcase,
  Award,
  GitMerge,
  ArrowRight,
  X,
  Check,
  Loader2,
  Plus,
  Pencil,
  Trash2,
  FileText,
  Phone,
  Inbox,
  AlertTriangle,
} from 'lucide-react';

import {
  api,
  ELIGIBILITY_ORDER,
  type Citizen,
  type CitizenDocument,
  type EligibilityResult,
  type EligibilityStatus,
  type Language,
  type Scheme,
  type Village,
} from '../lib/api';
import { useMutation, useQuery } from '../lib/useApi';
import { CriteriaList, EmptyState, ErrorNotice, StatusChip } from './schemes/SchemeBits';

// ─── Small formatters ───────────────────────────────────────────────────────

const rupees = (value: number) => `₹${value.toLocaleString('en-IN')}`;

const formatDate = (value: string | null, isEnglish: boolean): string => {
  if (!value) return '—';
  const parsed = new Date(value);
  // A date the server sends in a shape Date cannot parse is shown as-is rather
  // than as "Invalid Date".
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString(isEnglish ? 'en-IN' : 'mr-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
};

const formatSize = (bytes: number | null): string => {
  if (bytes === null || bytes <= 0) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

/** Label translation for a closed set of three values — not derived data. */
const GENDER_MR: Record<Citizen['gender'], string> = {
  Male: 'पुरुष',
  Female: 'महिला',
  Other: 'इतर',
};

interface DocsQuery {
  data: CitizenDocument[] | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

// ─── Resident create / edit form ────────────────────────────────────────────

/**
 * Family linkage (familyId, relation, isHead) is deliberately not editable
 * here: reassigning a person to another household changes whose income a
 * scheme is assessed against, and that belongs in a dedicated flow rather than
 * a free-text field on this form.
 */
const CitizenEditor: React.FC<{
  citizen: Citizen | null;
  onClose: () => void;
  onSaved: (saved: Citizen) => void;
}> = ({ citizen, onClose, onSaved }) => {
  const { i18n } = useTranslation();
  const isEnglish = i18n.language === 'en';

  const [form, setForm] = useState({
    name: citizen?.name ?? '',
    nameMr: citizen?.nameMr ?? '',
    age: citizen ? String(citizen.age) : '',
    gender: (citizen?.gender ?? 'Male') as Citizen['gender'],
    occupation: citizen?.occupation ?? '',
    occupationMr: citizen?.occupationMr ?? '',
    income: citizen ? String(citizen.income) : '',
    ward: citizen ? String(citizen.ward) : '',
    phone: citizen?.phone ?? '',
  });
  const [validation, setValidation] = useState<string | null>(null);

  const save = useMutation(
    (body: Partial<Citizen>) =>
      citizen ? api.citizens.update(citizen.id, body) : api.citizens.create(body),
    onSaved,
  );

  const set = (patch: Partial<typeof form>) => setForm((prev) => ({ ...prev, ...patch }));

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();

    const age = Number.parseInt(form.age, 10);
    const income = Number.parseInt(form.income, 10);
    const ward = Number.parseInt(form.ward, 10);

    if (!form.name.trim()) {
      setValidation(isEnglish ? 'Enter the resident’s name.' : 'रहिवाशाचे नाव भरा.');
      return;
    }
    if (!Number.isFinite(age) || age < 0 || age > 120) {
      setValidation(isEnglish ? 'Enter an age between 0 and 120.' : '० ते १२० दरम्यान वय भरा.');
      return;
    }
    if (!Number.isFinite(income) || income < 0) {
      setValidation(
        isEnglish
          ? 'Enter the annual income in rupees (0 if none).'
          : 'वार्षिक उत्पन्न रुपयांत भरा (नसल्यास ०).',
      );
      return;
    }
    if (!Number.isInteger(ward) || ward < 1) {
      setValidation(isEnglish ? 'Enter a ward number.' : 'वॉर्ड क्रमांक भरा.');
      return;
    }
    setValidation(null);

    // Built key by key so an untouched optional field is left out of the
    // request entirely rather than being sent as an empty string.
    const body: Partial<Citizen> = {
      name: form.name.trim(),
      age,
      gender: form.gender,
      genderMr: GENDER_MR[form.gender],
      income,
      ward,
      phone: form.phone.trim() || null,
    };
    if (form.nameMr.trim()) body.nameMr = form.nameMr.trim();
    if (form.occupation.trim()) body.occupation = form.occupation.trim();
    if (form.occupationMr.trim()) body.occupationMr = form.occupationMr.trim();

    await save.run(body);
  };

  const field =
    'w-full px-3 py-2 border border-slate-200 rounded text-xs text-slate-800 font-medium focus:outline-none focus:ring-2 focus:ring-govnavy/30';
  const label = 'block text-[10px] font-black uppercase tracking-wide text-slate-400 mb-1';

  return (
    <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-[2px] flex items-center justify-center p-4 z-50">
      <form
        onSubmit={submit}
        className="bg-white rounded-xl border border-slate-200 shadow-2xl w-full max-w-lg overflow-hidden border-t-4 border-govnavy max-h-[90vh] flex flex-col"
      >
        <header className="p-4 border-b border-slate-100 bg-slate-50 flex items-start justify-between">
          <div>
            <strong className="text-xs font-black text-govblue-900 uppercase block">
              {citizen
                ? isEnglish
                  ? 'Edit resident record'
                  : 'रहिवासी नोंद संपादित करा'
                : isEnglish
                  ? 'Add a resident'
                  : 'नवीन रहिवासी नोंदवा'}
            </strong>
            <span className="text-[10px] text-slate-500 font-semibold block mt-0.5">
              {citizen
                ? citizen.id
                : isEnglish
                  ? 'Added to your Gram Panchayat register'
                  : 'तुमच्या ग्रामपंचायत नोंदवहीत जोडले जाईल'}
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded hover:bg-slate-200 text-slate-400 hover:text-slate-700"
            aria-label={isEnglish ? 'Close' : 'बंद करा'}
          >
            <X size={16} />
          </button>
        </header>

        <div className="p-4 space-y-3 overflow-y-auto">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className={label} htmlFor="cit-name">
                {isEnglish ? 'Name (English)' : 'नाव (इंग्रजी)'}
              </label>
              <input
                id="cit-name"
                className={field}
                value={form.name}
                onChange={(e) => set({ name: e.target.value })}
              />
            </div>
            <div>
              <label className={label} htmlFor="cit-name-mr">
                {isEnglish ? 'Name (Marathi)' : 'नाव (मराठी)'}
              </label>
              <input
                id="cit-name-mr"
                className={field}
                value={form.nameMr}
                onChange={(e) => set({ nameMr: e.target.value })}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <label className={label} htmlFor="cit-age">
                {isEnglish ? 'Age' : 'वय'}
              </label>
              <input
                id="cit-age"
                type="number"
                min={0}
                max={120}
                className={field}
                value={form.age}
                onChange={(e) => set({ age: e.target.value })}
              />
            </div>
            <div>
              <label className={label} htmlFor="cit-gender">
                {isEnglish ? 'Gender' : 'लिंग'}
              </label>
              <select
                id="cit-gender"
                className={field}
                value={form.gender}
                onChange={(e) =>
                  // Safe: the three options below are the only values this
                  // select can produce, and they are exactly the three the
                  // API accepts.
                  set({ gender: e.target.value as Citizen['gender'] })
                }
              >
                <option value="Male">{isEnglish ? 'Male' : 'पुरुष'}</option>
                <option value="Female">{isEnglish ? 'Female' : 'महिला'}</option>
                <option value="Other">{isEnglish ? 'Other' : 'इतर'}</option>
              </select>
            </div>
            <div>
              <label className={label} htmlFor="cit-ward">
                {isEnglish ? 'Ward' : 'वॉर्ड'}
              </label>
              <input
                id="cit-ward"
                type="number"
                min={1}
                className={field}
                value={form.ward}
                onChange={(e) => set({ ward: e.target.value })}
              />
            </div>
            <div>
              <label className={label} htmlFor="cit-phone">
                {isEnglish ? 'Phone' : 'दूरध्वनी'}
              </label>
              <input
                id="cit-phone"
                className={field}
                value={form.phone}
                onChange={(e) => set({ phone: e.target.value })}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className={label} htmlFor="cit-occ">
                {isEnglish ? 'Occupation (English)' : 'व्यवसाय (इंग्रजी)'}
              </label>
              <input
                id="cit-occ"
                className={field}
                value={form.occupation}
                onChange={(e) => set({ occupation: e.target.value })}
              />
            </div>
            <div>
              <label className={label} htmlFor="cit-occ-mr">
                {isEnglish ? 'Occupation (Marathi)' : 'व्यवसाय (मराठी)'}
              </label>
              <input
                id="cit-occ-mr"
                className={field}
                value={form.occupationMr}
                onChange={(e) => set({ occupationMr: e.target.value })}
              />
            </div>
          </div>

          <div>
            <label className={label} htmlFor="cit-income">
              {isEnglish ? 'Annual household income (₹)' : 'वार्षिक कौटुंबिक उत्पन्न (₹)'}
            </label>
            <input
              id="cit-income"
              type="number"
              min={0}
              className={field}
              value={form.income}
              onChange={(e) => set({ income: e.target.value })}
            />
            <p className="text-[10px] text-slate-400 mt-1 leading-relaxed">
              {isEnglish
                ? 'Scheme eligibility is assessed against this figure, so an estimate entered here becomes a decision about someone’s benefits.'
                : 'योजनांची पात्रता याच आकड्यावरून ठरते, त्यामुळे अंदाजे नोंद केल्यास त्याचा थेट परिणाम लाभावर होतो.'}
            </p>
          </div>

          {validation && (
            <p role="alert" className="text-xs font-bold text-rose-700 m-0">
              {validation}
            </p>
          )}
          {save.error && (
            <p
              role="alert"
              className="text-xs text-rose-800 font-semibold bg-rose-50 border border-rose-200 rounded p-2.5 m-0"
            >
              {save.error}
            </p>
          )}
        </div>

        <footer className="p-4 border-t border-slate-100 bg-slate-50 flex items-center justify-end gap-2.5">
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-1.5 border border-slate-200 rounded text-xs font-bold text-slate-600 hover:bg-slate-100 transition-colors"
          >
            {isEnglish ? 'Cancel' : 'रद्द करा'}
          </button>
          <button
            type="submit"
            disabled={save.saving}
            className="px-4 py-1.5 bg-govnavy hover:bg-govblue-700 disabled:opacity-50 text-white rounded text-xs font-bold flex items-center gap-1.5 transition-colors shadow"
          >
            {save.saving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
            <span>{isEnglish ? 'Save to register' : 'नोंदवहीत जतन करा'}</span>
          </button>
        </footer>
      </form>
    </div>
  );
};

// ─── Scheme eligibility for one resident ────────────────────────────────────

/**
 * The engine runs server-side against the real scheme criteria and this
 * person's record, and returns a reason for every verdict. Nothing here decides
 * anything — it reports what was decided and why, which is what an officer
 * needs when a villager standing at the counter asks "why not me?".
 */
const EligibilityPanel: React.FC<{ citizenId: string }> = ({ citizenId }) => {
  const { t, i18n } = useTranslation();
  const isEnglish = i18n.language === 'en';
  const language: Language = isEnglish ? 'en' : 'mr';

  const [only, setOnly] = useState<EligibilityStatus | 'all'>('all');
  const [expanded, setExpanded] = useState<string | null>(null);

  const results = useQuery<EligibilityResult[]>(
    () => api.citizens.eligibility(citizenId, language),
    [citizenId, language],
  );

  // Fetched only so an expanded row can show the scheme's stated conditions in
  // plain language; the verdict itself never depends on this call.
  const schemes = useQuery<Scheme[]>(() => api.schemes.list(), []);

  const rows = useMemo(() => results.data ?? [], [results.data]);

  const counts = useMemo(() => {
    const map = {} as Record<EligibilityStatus, number>;
    ELIGIBILITY_ORDER.forEach((status) => {
      map[status] = 0;
    });
    rows.forEach((row) => {
      map[row.status] += 1;
    });
    return map;
  }, [rows]);

  const schemeById = useMemo(() => {
    const map = new Map<string, Scheme>();
    (schemes.data ?? []).forEach((scheme) => map.set(scheme.id, scheme));
    return map;
  }, [schemes.data]);

  const visible = only === 'all' ? rows : rows.filter((row) => row.status === only);

  return (
    <section className="space-y-3 pt-4 border-t border-slate-100">
      <div className="flex items-center gap-1.5 text-xs text-slate-400 font-bold uppercase tracking-wider">
        <Award size={14} className="text-govsaffron" />
        <span>{t('citizens_page.potential_schemes')}</span>
        {results.loading && <Loader2 size={12} className="animate-spin text-slate-400" />}
      </div>

      {results.error && <ErrorNotice message={results.error} onRetry={results.refetch} />}

      {!results.loading && !results.error && rows.length === 0 && (
        <p className="text-xs text-slate-500 m-0">
          {isEnglish
            ? 'No schemes have been assessed for this resident yet.'
            : 'या रहिवाशासाठी अद्याप कोणतीही योजना तपासलेली नाही.'}
        </p>
      )}

      {!results.loading && !results.error && rows.length > 0 && (
        <>
          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => setOnly('all')}
              className={`px-2.5 py-1 rounded-lg text-[11px] font-bold border transition-colors ${
                only === 'all'
                  ? 'bg-govnavy text-white border-govnavy'
                  : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
              }`}
            >
              {isEnglish ? 'All' : 'सर्व'} <span className="tabular-nums">{rows.length}</span>
            </button>
            {ELIGIBILITY_ORDER.filter((status) => counts[status] > 0).map((status) => (
              <button
                key={status}
                type="button"
                onClick={() => setOnly(status)}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-bold border transition-colors ${
                  only === status
                    ? 'bg-govnavy text-white border-govnavy'
                    : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
                }`}
              >
                {status} <span className="tabular-nums">{counts[status]}</span>
              </button>
            ))}
          </div>

          <div className="space-y-2">
            {visible.map((row) => {
              const open = expanded === row.schemeId;
              const scheme = schemeById.get(row.schemeId);
              return (
                <div
                  key={row.schemeId}
                  className="border border-slate-200 rounded-lg bg-white overflow-hidden"
                >
                  <button
                    type="button"
                    onClick={() => setExpanded(open ? null : row.schemeId)}
                    aria-expanded={open}
                    className="w-full text-left p-3 space-y-1.5"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-xs font-bold text-govblue-900 leading-snug">
                        {isEnglish ? row.schemeName : row.schemeNameMr}
                      </span>
                      <StatusChip status={row.status} isEnglish={isEnglish} size="sm" />
                    </div>
                    <p className="text-[11px] text-slate-600 leading-relaxed m-0">
                      {isEnglish ? row.explanation : row.explanationMr}
                    </p>
                  </button>

                  {open && (
                    <div className="px-3 pb-3 pt-1 border-t border-slate-100 space-y-3">
                      {row.failedCriteria.length > 0 && (
                        <div className="space-y-1">
                          <h5 className="text-[10px] font-black uppercase tracking-widest text-slate-400 m-0">
                            {isEnglish ? 'Conditions not met' : 'पूर्ण न झालेल्या अटी'}
                          </h5>
                          <ul className="space-y-1 m-0 pl-0 list-none">
                            {row.failedCriteria.map((line, index) => (
                              <li
                                key={index}
                                className="flex gap-2 text-[11px] text-rose-700 leading-relaxed"
                              >
                                <span className="mt-0.5">•</span>
                                <span>{line}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {(row.missingDocuments.length > 0 || row.unverifiedDocuments.length > 0) && (
                        <div className="space-y-1">
                          <h5 className="text-[10px] font-black uppercase tracking-widest text-slate-400 m-0">
                            {isEnglish ? 'Documents' : 'कागदपत्रे'}
                          </h5>
                          <ul className="space-y-1 m-0 pl-0 list-none">
                            {row.missingDocuments.map((doc) => (
                              <li
                                key={`missing-${doc.name}`}
                                className="flex items-start gap-2 text-[11px] leading-relaxed text-rose-700"
                              >
                                <FileText size={12} className="mt-0.5 flex-shrink-0" />
                                <span>
                                  {isEnglish ? doc.name : doc.nameMr}
                                  <span className="font-bold">
                                    {isEnglish ? ' — not uploaded' : ' — अपलोड बाकी'}
                                  </span>
                                </span>
                              </li>
                            ))}
                            {row.unverifiedDocuments.map((doc) => (
                              <li
                                key={`unverified-${doc.name}`}
                                className="flex items-start gap-2 text-[11px] leading-relaxed text-amber-800"
                              >
                                <FileText size={12} className="mt-0.5 flex-shrink-0" />
                                <span>
                                  {isEnglish ? doc.name : doc.nameMr}
                                  <span className="font-bold">
                                    {isEnglish
                                      ? ` — ${doc.fileStatus ?? 'awaiting verification'}`
                                      : ' — पडताळणी बाकी'}
                                  </span>
                                </span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {row.unknownAttributes.length > 0 && (
                        <p className="flex items-start gap-2 text-[11px] text-sky-900 bg-sky-50 border border-sky-200 rounded p-2 m-0 leading-relaxed">
                          <AlertTriangle size={12} className="mt-0.5 flex-shrink-0" />
                          <span>
                            {isEnglish
                              ? `The record does not hold ${row.unknownAttributes.join(', ')}, so those rules could not be checked.`
                              : `नोंदीत ${row.unknownAttributes.join(', ')} उपलब्ध नसल्याने त्या अटी तपासता आल्या नाहीत.`}
                          </span>
                        </p>
                      )}

                      {scheme ? (
                        <div className="space-y-1.5">
                          <h5 className="text-[10px] font-black uppercase tracking-widest text-slate-400 m-0">
                            {isEnglish ? 'Who can apply' : 'कोण अर्ज करू शकते'}
                          </h5>
                          <CriteriaList criteria={scheme.criteria} isEnglish={isEnglish} />
                        </div>
                      ) : (
                        schemes.error && (
                          <p role="alert" className="text-[11px] text-rose-700 font-semibold m-0">
                            {isEnglish
                              ? `Scheme conditions could not be loaded: ${schemes.error}`
                              : `योजनेच्या अटी उपलब्ध झाल्या नाहीत: ${schemes.error}`}
                          </p>
                        )
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {visible.length === 0 && (
            <p className="text-xs text-slate-400 m-0">
              {isEnglish ? 'No schemes in this group.' : 'या गटात कोणतीही योजना नाही.'}
            </p>
          )}
        </>
      )}
    </section>
  );
};

// ─── Resident profile drawer ────────────────────────────────────────────────

/**
 * Read with `/citizens/{id}` rather than reused from the table row: a family
 * member the officer clicks through to may sit outside the current ward or
 * search filter, and would otherwise not be in the loaded list at all.
 */
const CitizenProfile: React.FC<{
  citizenId: string;
  onClose: () => void;
  onSelect: (id: string) => void;
  onRegisterChanged: () => void;
}> = ({ citizenId, onClose, onSelect, onRegisterChanged }) => {
  const { t, i18n } = useTranslation();
  const isEnglish = i18n.language === 'en';

  const [editing, setEditing] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const profile = useQuery<Citizen>(() => api.citizens.get(citizenId), [citizenId]);
  const citizen = profile.data;

  const remove = useMutation(
    (id: string) => api.citizens.remove(id),
    () => {
      onRegisterChanged();
      onClose();
    },
  );

  // A different resident was selected — drop any half-finished delete.
  useEffect(() => {
    setConfirmingDelete(false);
    setEditing(false);
  }, [citizenId]);

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-5 relative">
      <button
        type="button"
        onClick={onClose}
        className="absolute top-4 right-4 p-1.5 rounded-lg bg-white border border-slate-200 text-slate-400 hover:text-slate-700 hover:bg-slate-50 transition-colors"
        aria-label={isEnglish ? 'Close profile' : 'प्रोफाइल बंद करा'}
      >
        <X size={14} />
      </button>

      {profile.loading && (
        <div className="flex items-center gap-2 py-8 text-slate-400">
          <Loader2 size={16} className="animate-spin" />
          <span className="text-xs font-bold uppercase tracking-wider">
            {isEnglish ? 'Loading record' : 'नोंद उघडत आहे'}
          </span>
        </div>
      )}

      {profile.error && <ErrorNotice message={profile.error} onRetry={profile.refetch} />}

      {citizen && (
        <>
          {/* Heading */}
          <div className="space-y-2 pb-4 border-b border-slate-100">
            <div className="w-12 h-12 rounded-xl bg-govblue-50 border border-govnavy/20 flex items-center justify-center text-govnavy font-black text-lg">
              {citizen.name.slice(0, 1)}
            </div>
            <div>
              <h2 className="text-base font-black text-govblue-900 m-0">
                {isEnglish ? citizen.name : citizen.nameMr}
              </h2>
              <span className="text-[10px] font-mono font-bold text-govnavy">{citizen.id}</span>
            </div>
          </div>

          {/* Specs */}
          <div className="grid grid-cols-2 gap-4 text-xs">
            <div className="space-y-1">
              <span className="text-slate-400 block font-bold uppercase text-[10px] tracking-wide">
                {t('beneficiary.age')}
              </span>
              <span className="text-slate-800 font-bold block">{citizen.age}</span>
            </div>
            <div className="space-y-1">
              <span className="text-slate-400 block font-bold uppercase text-[10px] tracking-wide">
                {t('citizens_page.gender')}
              </span>
              <span className="text-slate-800 font-bold block">
                {isEnglish ? citizen.gender : citizen.genderMr}
              </span>
            </div>
            <div className="space-y-1">
              <span className="text-slate-400 block font-bold uppercase text-[10px] tracking-wide">
                {t('beneficiary.ward')}
              </span>
              <span className="text-slate-800 font-bold block">{citizen.ward}</span>
            </div>
            <div className="space-y-1">
              <span className="text-slate-400 block font-bold uppercase text-[10px] tracking-wide">
                {t('beneficiary.income')}
              </span>
              <span className="text-govgreen font-black block">{rupees(citizen.income)}</span>
            </div>
            <div className="col-span-2 space-y-1 border-t border-slate-100 pt-2.5">
              <span className="text-slate-400 block font-bold uppercase text-[10px] tracking-wide">
                {t('citizens_page.occupation')}
              </span>
              <span className="text-slate-800 font-bold block">
                {isEnglish ? citizen.occupation : citizen.occupationMr}
              </span>
            </div>
            {citizen.phone && (
              <div className="col-span-2 space-y-1">
                <span className="text-slate-400 block font-bold uppercase text-[10px] tracking-wide">
                  {isEnglish ? 'Phone' : 'दूरध्वनी'}
                </span>
                <span className="text-slate-800 font-bold flex items-center gap-1.5">
                  <Phone size={12} className="text-govnavy" />
                  {citizen.phone}
                </span>
              </div>
            )}
          </div>

          {/* Family */}
          <div className="space-y-3 pt-4 border-t border-slate-100">
            <div className="flex items-center gap-1.5 text-xs text-slate-400 font-bold uppercase tracking-wider">
              <GitMerge size={14} className="text-govnavy" />
              <span>{t('citizens_page.family_tree')}</span>
            </div>

            {(citizen.familyName || citizen.familyId) && (
              <span className="text-[10px] text-slate-500 block font-semibold">
                {isEnglish ? citizen.familyName : citizen.familyNameMr ?? citizen.familyName}
                {citizen.familyId ? ` · ${citizen.familyId}` : ''}
                {citizen.isHead ? (isEnglish ? ' · household head' : ' · कुटुंबप्रमुख') : ''}
              </span>
            )}

            {citizen.familyMembers.length === 0 ? (
              <p className="text-xs text-slate-500 m-0">
                {isEnglish
                  ? 'No other household members are on the register.'
                  : 'नोंदवहीत इतर कुटुंब सदस्य नाहीत.'}
              </p>
            ) : (
              <div className="space-y-2">
                {citizen.familyMembers.map((member) => (
                  <button
                    key={member.id}
                    type="button"
                    onClick={() => onSelect(member.id)}
                    className="w-full flex items-center justify-between gap-2 p-2.5 rounded-lg bg-slate-50 border border-slate-200 hover:border-govnavy/40 hover:bg-white text-left transition-colors"
                  >
                    <div className="min-w-0">
                      <span className="text-xs font-bold text-slate-800 block truncate">
                        {isEnglish ? member.name : member.nameMr}
                      </span>
                      <span className="text-[10px] text-slate-500 font-semibold">
                        {member.age}
                        {member.isHead ? (isEnglish ? ' · head' : ' · प्रमुख') : ''}
                      </span>
                    </div>
                    <div className="flex items-center gap-1 text-[10px] text-govnavy font-bold flex-shrink-0">
                      <span>
                        {(isEnglish ? member.relation : member.relationMr) ??
                          (isEnglish ? 'Household member' : 'कुटुंब सदस्य')}
                      </span>
                      <ArrowRight size={10} />
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Scheme eligibility */}
          <EligibilityPanel citizenId={citizen.id} />

          {/* Record actions */}
          <div className="pt-4 border-t border-slate-100 space-y-2">
            {remove.error && (
              <p
                role="alert"
                className="text-xs text-rose-800 font-semibold bg-rose-50 border border-rose-200 rounded p-2.5 m-0"
              >
                {remove.error}
              </p>
            )}

            {confirmingDelete ? (
              <div className="space-y-2 bg-rose-50 border border-rose-200 rounded-lg p-3">
                <p className="text-xs text-rose-900 font-semibold m-0 leading-relaxed">
                  {isEnglish
                    ? `Remove ${citizen.name} from the village register? Their documents and scheme history go with the record.`
                    : `${citizen.nameMr} यांची नोंद नोंदवहीतून काढायची? त्यांची कागदपत्रे व योजनांचा इतिहासही जाईल.`}
                </p>
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={remove.saving}
                    onClick={() => remove.run(citizen.id)}
                    className="px-3 py-1.5 rounded bg-rose-600 hover:bg-rose-700 disabled:opacity-50 text-white text-xs font-bold flex items-center gap-1.5"
                  >
                    {remove.saving ? (
                      <Loader2 size={13} className="animate-spin" />
                    ) : (
                      <Trash2 size={13} />
                    )}
                    <span>{isEnglish ? 'Yes, remove' : 'होय, काढा'}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmingDelete(false)}
                    className="px-3 py-1.5 rounded border border-slate-200 bg-white text-slate-600 text-xs font-bold"
                  >
                    {isEnglish ? 'Keep record' : 'नोंद ठेवा'}
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setEditing(true)}
                  className="flex-1 px-3 py-2 rounded border border-slate-200 bg-white text-slate-700 hover:border-govnavy/40 text-xs font-bold flex items-center justify-center gap-1.5 transition-colors"
                >
                  <Pencil size={13} />
                  <span>{isEnglish ? 'Edit record' : 'नोंद संपादित करा'}</span>
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmingDelete(true)}
                  className="px-3 py-2 rounded border border-rose-200 text-rose-700 hover:bg-rose-50 text-xs font-bold flex items-center gap-1.5 transition-colors"
                >
                  <Trash2 size={13} />
                  <span>{isEnglish ? 'Remove' : 'काढा'}</span>
                </button>
              </div>
            )}
          </div>

          {editing && (
            <CitizenEditor
              citizen={citizen}
              onClose={() => setEditing(false)}
              onSaved={() => {
                setEditing(false);
                profile.refetch();
                onRegisterChanged();
              }}
            />
          )}
        </>
      )}
    </div>
  );
};

// ─── Document verification queue (the Digital Locker review desk) ───────────

const VerificationQueue: React.FC<{
  query: DocsQuery;
  statusFilter: string;
  setStatusFilter: (value: string) => void;
}> = ({ query, statusFilter, setStatusFilter }) => {
  const { i18n } = useTranslation();
  const isEnglish = i18n.language === 'en';

  const [reviewing, setReviewing] = useState<CitizenDocument | null>(null);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState('');

  const close = () => {
    setReviewing(null);
    setRejecting(false);
    setReason('');
  };

  const review = useMutation(
    (id: string, status: 'Verified' | 'Rejected', rejectionReason?: string) =>
      api.documents.review(id, status, rejectionReason),
    () => {
      query.refetch();
      close();
    },
  );

  const documents = query.data ?? [];
  const pendingCount = documents.filter((d) => d.status === 'Pending Verification').length;

  // A rejection with no reason sends the resident back to the counter to find
  // out what was wrong, so the button stays disabled until one is written.
  const reasonGiven = reason.trim().length > 0;

  const openReview = (doc: CitizenDocument, startRejecting: boolean) => {
    setReviewing(doc);
    setRejecting(startRejecting);
    setReason('');
    review.clearError();
  };

  const statusChip = (doc: CitizenDocument) =>
    doc.status === 'Verified'
      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
      : doc.status === 'Rejected'
        ? 'bg-rose-50 text-rose-700 border-rose-200'
        : 'bg-amber-50 text-amber-800 border-amber-200';

  return (
    <>
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden border-t-4 border-govnavy">
        <div className="p-4 border-b border-slate-100 bg-slate-50/60 flex flex-wrap items-center justify-between gap-3">
          <span className="text-xs text-slate-500 font-bold uppercase tracking-wider flex items-center gap-2">
            {query.loading && <Loader2 size={13} className="animate-spin" />}
            {statusFilter === 'Pending Verification'
              ? isEnglish
                ? `${pendingCount} pending document${pendingCount === 1 ? '' : 's'} to verify`
                : `${pendingCount} कागदपत्रे पडताळणीसाठी प्रलंबित`
              : isEnglish
                ? `${documents.length} document${documents.length === 1 ? '' : 's'} on file`
                : `${documents.length} कागदपत्रे नोंदीत`}
          </span>

          <div className="flex gap-1 bg-slate-100 p-1 rounded-lg border border-slate-200">
            {[
              { id: 'Pending Verification', en: 'Pending', mr: 'प्रलंबित' },
              { id: 'all', en: 'All', mr: 'सर्व' },
            ].map((option) => (
              <button
                key={option.id}
                type="button"
                onClick={() => setStatusFilter(option.id)}
                className={`px-3 py-1 rounded-md text-xs font-bold transition-all ${
                  statusFilter === option.id
                    ? 'bg-white text-govnavy shadow-sm border border-slate-200'
                    : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                {isEnglish ? option.en : option.mr}
              </button>
            ))}
          </div>
        </div>

        {query.error && (
          <div className="p-4">
            <ErrorNotice message={query.error} onRetry={query.refetch} />
          </div>
        )}

        {!query.loading && !query.error && documents.length === 0 && (
          <div className="p-10 text-center">
            <Inbox size={30} className="mx-auto text-slate-300" />
            <p className="text-sm font-bold text-slate-600 mt-3 m-0">
              {statusFilter === 'Pending Verification'
                ? isEnglish
                  ? 'Nothing waiting for verification.'
                  : 'पडताळणीसाठी काहीही प्रलंबित नाही.'
                : isEnglish
                  ? 'No documents have been uploaded yet.'
                  : 'अद्याप कोणतेही कागदपत्र अपलोड झालेले नाही.'}
            </p>
            <p className="text-xs text-slate-400 mt-1 m-0">
              {isEnglish
                ? 'Documents appear here when a resident uploads one from the portal.'
                : 'रहिवाशाने पोर्टलवरून कागदपत्र अपलोड केल्यावर ते येथे दिसेल.'}
            </p>
          </div>
        )}

        {documents.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-xs sm:text-sm border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-slate-500 font-bold select-none">
                  <th className="p-4">{isEnglish ? 'Resident' : 'रहिवासी'}</th>
                  <th className="p-4">{isEnglish ? 'Document type' : 'दस्तऐवज प्रकार'}</th>
                  <th className="p-4">{isEnglish ? 'File' : 'फाईल'}</th>
                  <th className="p-4">{isEnglish ? 'Submitted' : 'सादर दिनांक'}</th>
                  <th className="p-4">{isEnglish ? 'Status' : 'स्थिती'}</th>
                  <th className="p-4 text-right">{isEnglish ? 'Actions' : 'कृती'}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {documents.map((doc) => {
                  const isPending = doc.status === 'Pending Verification';
                  return (
                    <tr key={doc.id} className="hover:bg-slate-50 transition-colors align-top">
                      <td className="p-4 font-bold text-slate-800">
                        {doc.citizenName ?? doc.citizenId}
                      </td>
                      <td className="p-4 text-slate-600 font-semibold">
                        {isEnglish ? doc.docType : doc.docTypeMr}
                      </td>
                      <td className="p-4">
                        <button
                          type="button"
                          onClick={() => openReview(doc, false)}
                          className="font-mono text-[11px] text-govnavy font-bold hover:underline text-left focus:outline-none focus:ring-2 focus:ring-govnavy/30 rounded"
                        >
                          {doc.fileName}
                        </button>
                        <span className="block text-[10px] text-slate-400 font-semibold mt-0.5">
                          {formatSize(doc.sizeBytes)}
                        </span>
                      </td>
                      <td className="p-4 text-slate-500">
                        {formatDate(doc.submittedDate, isEnglish)}
                      </td>
                      <td className="p-4">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${statusChip(doc)}`}
                        >
                          {isEnglish ? doc.status : doc.statusMr}
                        </span>
                        {doc.status === 'Rejected' && doc.rejectionReason && (
                          <span className="block text-[10px] text-rose-700 mt-1 max-w-[220px] leading-relaxed">
                            {doc.rejectionReason}
                          </span>
                        )}
                      </td>
                      <td className="p-4 text-right">
                        <div className="flex items-center gap-1.5 justify-end">
                          {doc.status !== 'Verified' && (
                            <button
                              type="button"
                              disabled={review.saving}
                              onClick={() => review.run(doc.id, 'Verified')}
                              className="p-1.5 rounded text-emerald-700 hover:bg-emerald-50 border border-transparent hover:border-emerald-200 disabled:opacity-40 transition-colors"
                              title={isEnglish ? 'Mark verified' : 'पडताळणी पूर्ण करा'}
                            >
                              <Check size={14} />
                            </button>
                          )}
                          {doc.status !== 'Rejected' && (
                            <button
                              type="button"
                              onClick={() => openReview(doc, true)}
                              className="p-1.5 rounded text-rose-700 hover:bg-rose-50 border border-transparent hover:border-rose-200 transition-colors"
                              title={
                                isEnglish
                                  ? 'Reject — a reason is required'
                                  : 'नाकारा — कारण आवश्यक'
                              }
                            >
                              <X size={14} />
                            </button>
                          )}
                          {!isPending && (
                            <span className="text-[10px] text-slate-400 font-semibold">
                              {formatDate(doc.verifiedAt, isEnglish)}
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {review.error && !reviewing && (
          <div className="p-4 border-t border-slate-100">
            <p
              role="alert"
              className="text-xs text-rose-800 font-semibold bg-rose-50 border border-rose-200 rounded p-2.5 m-0"
            >
              {review.error}
            </p>
          </div>
        )}
      </div>

      {/* Review dialog: the stored record, plus the decision. */}
      {reviewing && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-[2px] flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl border border-slate-200 shadow-2xl max-w-md w-full overflow-hidden border-t-4 border-govsaffron flex flex-col max-h-[90vh]">
            <header className="p-4 border-b border-slate-100 bg-slate-50 flex items-start justify-between">
              <div>
                <strong className="text-xs font-black text-govblue-900 uppercase block">
                  {isEnglish ? 'Verify document' : 'दस्तऐवज पडताळणी'}
                </strong>
                <span className="text-[10px] text-slate-500 font-semibold block mt-0.5 font-mono">
                  {reviewing.fileName}
                </span>
              </div>
              <button
                type="button"
                onClick={close}
                className="p-1 rounded hover:bg-slate-200 text-slate-400 hover:text-slate-700"
                aria-label={isEnglish ? 'Close' : 'बंद करा'}
              >
                <X size={16} />
              </button>
            </header>

            <div className="p-5 space-y-3 overflow-y-auto">
              <dl className="grid grid-cols-2 gap-3 text-xs m-0">
                <div>
                  <dt className="text-[10px] font-black uppercase tracking-wide text-slate-400">
                    {isEnglish ? 'Resident' : 'रहिवासी'}
                  </dt>
                  <dd className="text-slate-800 font-bold m-0">
                    {reviewing.citizenName ?? reviewing.citizenId}
                  </dd>
                </div>
                <div>
                  <dt className="text-[10px] font-black uppercase tracking-wide text-slate-400">
                    {isEnglish ? 'Document type' : 'दस्तऐवज प्रकार'}
                  </dt>
                  <dd className="text-slate-800 font-bold m-0">
                    {isEnglish ? reviewing.docType : reviewing.docTypeMr}
                  </dd>
                </div>
                <div>
                  <dt className="text-[10px] font-black uppercase tracking-wide text-slate-400">
                    {isEnglish ? 'Submitted' : 'सादर दिनांक'}
                  </dt>
                  <dd className="text-slate-800 font-bold m-0">
                    {formatDate(reviewing.submittedDate, isEnglish)}
                  </dd>
                </div>
                <div>
                  <dt className="text-[10px] font-black uppercase tracking-wide text-slate-400">
                    {isEnglish ? 'File size' : 'फाईल आकार'}
                  </dt>
                  <dd className="text-slate-800 font-bold m-0">{formatSize(reviewing.sizeBytes)}</dd>
                </div>
                <div className="col-span-2">
                  <dt className="text-[10px] font-black uppercase tracking-wide text-slate-400">
                    {isEnglish ? 'Current status' : 'सध्याची स्थिती'}
                  </dt>
                  <dd className="m-0">
                    <span
                      className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${statusChip(reviewing)}`}
                    >
                      {isEnglish ? reviewing.status : reviewing.statusMr}
                    </span>
                  </dd>
                </div>
                {reviewing.rejectionReason && (
                  <div className="col-span-2">
                    <dt className="text-[10px] font-black uppercase tracking-wide text-slate-400">
                      {isEnglish ? 'Reason given' : 'दिलेले कारण'}
                    </dt>
                    <dd className="text-rose-700 font-semibold m-0 leading-relaxed">
                      {reviewing.rejectionReason}
                    </dd>
                  </div>
                )}
              </dl>

              <p className="text-[11px] text-slate-500 bg-slate-50 border border-slate-200 rounded p-2.5 m-0 leading-relaxed">
                {isEnglish
                  ? 'The uploaded file is held on the server; this screen shows the record of it. Open the file itself before deciding.'
                  : 'अपलोड केलेली फाईल सर्व्हरवर आहे; येथे तिची नोंद दिसते. निर्णयापूर्वी मूळ फाईल तपासा.'}
              </p>

              {rejecting && (
                <div className="space-y-1.5">
                  <label
                    htmlFor="reject-reason"
                    className="block text-[10px] font-black uppercase tracking-wide text-slate-400"
                  >
                    {isEnglish ? 'Why is it being rejected?' : 'नाकारण्याचे कारण काय?'}
                  </label>
                  <textarea
                    id="reject-reason"
                    autoFocus
                    rows={3}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder={
                      isEnglish
                        ? 'e.g. The income figure is not legible — please upload a clearer scan.'
                        : 'उदा. उत्पन्नाचा आकडा वाचता येत नाही — स्पष्ट प्रत अपलोड करा.'
                    }
                    className="w-full px-3 py-2 border border-slate-200 rounded text-xs text-slate-800 font-medium focus:outline-none focus:ring-2 focus:ring-rose-300"
                  />
                  <p className="text-[10px] text-slate-500 m-0 leading-relaxed">
                    {isEnglish
                      ? 'Required. The resident sees this, and it is the only way they know what to fix without coming back to the office.'
                      : 'आवश्यक. हे कारण रहिवाशाला दिसते; कार्यालयात न येता काय दुरुस्त करायचे हे त्यावरूनच कळते.'}
                  </p>
                </div>
              )}

              {review.error && (
                <p
                  role="alert"
                  className="text-xs text-rose-800 font-semibold bg-rose-50 border border-rose-200 rounded p-2.5 m-0"
                >
                  {review.error}
                </p>
              )}
            </div>

            <footer className="p-4 border-t border-slate-100 bg-slate-50 flex items-center justify-end gap-2.5">
              {rejecting ? (
                <>
                  <button
                    type="button"
                    onClick={() => {
                      setRejecting(false);
                      setReason('');
                    }}
                    className="px-3.5 py-1.5 border border-slate-200 rounded text-xs font-bold text-slate-600 hover:bg-slate-100 transition-colors"
                  >
                    {isEnglish ? 'Back' : 'मागे'}
                  </button>
                  <button
                    type="button"
                    disabled={!reasonGiven || review.saving}
                    onClick={() => review.run(reviewing.id, 'Rejected', reason.trim())}
                    className="px-4 py-1.5 bg-rose-600 hover:bg-rose-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded text-xs font-bold flex items-center gap-1.5 transition-colors shadow"
                  >
                    {review.saving ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : (
                      <X size={14} />
                    )}
                    <span>{isEnglish ? 'Reject with this reason' : 'या कारणासह नाकारा'}</span>
                  </button>
                </>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={close}
                    className="px-3.5 py-1.5 border border-slate-200 rounded text-xs font-bold text-slate-600 hover:bg-slate-100 transition-colors"
                  >
                    {isEnglish ? 'Close' : 'बंद करा'}
                  </button>
                  {reviewing.status !== 'Rejected' && (
                    <button
                      type="button"
                      onClick={() => setRejecting(true)}
                      className="px-3.5 py-1.5 border border-rose-200 rounded text-xs font-bold text-rose-700 hover:bg-rose-50 transition-colors"
                    >
                      {isEnglish ? 'Reject…' : 'नाकारा…'}
                    </button>
                  )}
                  {reviewing.status !== 'Verified' && (
                    <button
                      type="button"
                      disabled={review.saving}
                      onClick={() => review.run(reviewing.id, 'Verified')}
                      className="px-4 py-1.5 bg-govnavy hover:bg-govblue-700 disabled:opacity-50 text-white rounded text-xs font-bold flex items-center gap-1.5 transition-colors shadow"
                    >
                      {review.saving ? (
                        <Loader2 size={14} className="animate-spin" />
                      ) : (
                        <Check size={14} />
                      )}
                      <span>{isEnglish ? 'Mark verified' : 'पडताळणी पूर्ण करा'}</span>
                    </button>
                  )}
                </>
              )}
            </footer>
          </div>
        </div>
      )}
    </>
  );
};

// ─── Screen ─────────────────────────────────────────────────────────────────

export const CitizenManagement: React.FC = () => {
  const { t, i18n } = useTranslation();
  const isEnglish = i18n.language === 'en';

  const [activeSubTab, setActiveSubTab] = useState<'directory' | 'verification'>('directory');

  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [wardFilter, setWardFilter] = useState<string>('all');
  const [ageFilter, setAgeFilter] = useState<string>('all');
  const [occupationFilter, setOccupationFilter] = useState<string>('all');
  const [selectedCitizenId, setSelectedCitizenId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [docStatusFilter, setDocStatusFilter] = useState<string>('Pending Verification');

  // Search is a server query, so it is debounced — otherwise every keystroke
  // in the box would be a request against the register.
  useEffect(() => {
    const timer = setTimeout(() => setSearch(searchInput.trim()), 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const citizens = useQuery<Citizen[]>(() => {
    const params: { search?: string; ward?: number } = {};
    if (search) params.search = search;
    if (wardFilter !== 'all') params.ward = Number(wardFilter);
    return api.citizens.list(params);
  }, [search, wardFilter]);

  const documents = useQuery<CitizenDocument[]>(() => {
    const params: { status?: string } = {};
    if (docStatusFilter !== 'all') params.status = docStatusFilter;
    return api.documents.list(params);
  }, [docStatusFilter]);

  // Ward numbers come from the Panchayat's own record rather than the old
  // hardcoded "Ward 1–4" list, since the platform now serves many villages.
  const village = useQuery<Village | null>(() => api.villages.current(), []);

  // An admin session has no current village, so the dropdown falls back to the
  // wards seen in the data. They accumulate: selecting one ward would otherwise
  // shrink the list to that single option and strand the officer there.
  const [knownWards, setKnownWards] = useState<number[]>([]);
  useEffect(() => {
    const rows = citizens.data;
    if (!rows) return;
    setKnownWards((prev) => {
      const next = new Set(prev);
      rows.forEach((row) => next.add(row.ward));
      return next.size === prev.length ? prev : Array.from(next).sort((a, b) => a - b);
    });
  }, [citizens.data]);

  const wardOptions = useMemo(() => {
    const count = village.data?.wardCount ?? 0;
    if (count > 0) return Array.from({ length: count }, (_, index) => index + 1);
    return knownWards;
  }, [village.data, knownWards]);

  const rows = useMemo(() => citizens.data ?? [], [citizens.data]);

  const occupations = useMemo(() => {
    const jobs = new Set<string>();
    rows.forEach((row) => {
      const job = isEnglish ? row.occupation : row.occupationMr;
      if (job) jobs.add(job);
    });
    return Array.from(jobs).sort((a, b) => a.localeCompare(b));
  }, [rows, isEnglish]);

  // Age band and occupation are not server filters, so they narrow what the
  // server already returned rather than pretending to be a query.
  const visible = useMemo(
    () =>
      rows.filter((row) => {
        if (ageFilter === 'young' && row.age >= 30) return false;
        if (ageFilter === 'middle' && (row.age < 30 || row.age >= 60)) return false;
        if (ageFilter === 'senior' && row.age < 60) return false;
        if (occupationFilter !== 'all') {
          const job = isEnglish ? row.occupation : row.occupationMr;
          if (job !== occupationFilter) return false;
        }
        return true;
      }),
    [rows, ageFilter, occupationFilter, isEnglish],
  );

  const filtersActive =
    Boolean(search) || wardFilter !== 'all' || ageFilter !== 'all' || occupationFilter !== 'all';

  const hasPendingDocs = (documents.data ?? []).some(
    (doc) => doc.status === 'Pending Verification',
  );

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-black text-govblue-900 tracking-tight m-0">
            {t('citizens_page.title')}
          </h1>
          <p className="text-xs text-slate-500 font-semibold mt-1 m-0">
            {isEnglish
              ? 'Search the village register, follow household links, and review uploaded documents.'
              : 'गावाची नोंदवही शोधा, कौटुंबिक संबंध पहा आणि अपलोड केलेली कागदपत्रे तपासा.'}
          </p>
        </div>
        {activeSubTab === 'directory' && (
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="px-3.5 py-2 rounded-lg bg-govnavy hover:bg-govblue-700 text-white text-xs font-bold flex items-center gap-1.5 transition-colors shadow-sm"
          >
            <Plus size={14} />
            <span>{isEnglish ? 'Add resident' : 'रहिवासी जोडा'}</span>
          </button>
        )}
      </div>

      {/* Sub-tabs */}
      <div className="flex border-b border-slate-200 gap-6 select-none">
        <button
          type="button"
          onClick={() => setActiveSubTab('directory')}
          className={`pb-2.5 text-xs font-bold uppercase tracking-wider transition-all focus:outline-none ${
            activeSubTab === 'directory'
              ? 'border-b-2 border-govnavy text-govnavy font-black'
              : 'text-slate-400 hover:text-slate-700'
          }`}
        >
          👥 {isEnglish ? 'Citizen Directory' : 'नागरिक मार्गदर्शिका'}
        </button>
        <button
          type="button"
          onClick={() => setActiveSubTab('verification')}
          className={`pb-2.5 text-xs font-bold uppercase tracking-wider transition-all focus:outline-none relative flex items-center gap-1.5 ${
            activeSubTab === 'verification'
              ? 'border-b-2 border-govnavy text-govnavy font-black'
              : 'text-slate-400 hover:text-slate-700'
          }`}
        >
          <span>📂 {isEnglish ? 'Document Verification Queue' : 'दस्तऐवज पडताळणी रांग'}</span>
          {hasPendingDocs && <span className="w-2 h-2 rounded-full bg-govsaffron" />}
        </button>
      </div>

      {activeSubTab === 'directory' ? (
        <>
          {/* Search and filters */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4">
            <div className="relative">
              <Search size={16} className="absolute left-3.5 top-3 text-slate-400" />
              <input
                type="search"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder={t('citizens_page.search_placeholder')}
                aria-label={t('citizens_page.search_placeholder')}
                className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-white border border-slate-200 text-xs sm:text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-govnavy/25"
              />
              {citizens.loading && (
                <Loader2
                  size={14}
                  className="absolute right-3.5 top-3.5 animate-spin text-slate-400"
                />
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">
                <MapPin size={14} className="text-govnavy flex-shrink-0" />
                <select
                  value={wardFilter}
                  onChange={(e) => setWardFilter(e.target.value)}
                  aria-label={t('beneficiary.ward')}
                  className="flex-1 bg-transparent border-none text-xs text-slate-700 font-semibold focus:outline-none"
                >
                  <option value="all">
                    {t('beneficiary.ward')}: {isEnglish ? 'All' : 'सर्व'}
                  </option>
                  {wardOptions.map((ward) => (
                    <option key={ward} value={String(ward)}>
                      {t('beneficiary.ward')} {ward}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">
                <User size={14} className="text-govnavy flex-shrink-0" />
                <select
                  value={ageFilter}
                  onChange={(e) => setAgeFilter(e.target.value)}
                  aria-label={t('beneficiary.age')}
                  className="flex-1 bg-transparent border-none text-xs text-slate-700 font-semibold focus:outline-none"
                >
                  <option value="all">
                    {t('beneficiary.age')}: {isEnglish ? 'All' : 'सर्व'}
                  </option>
                  <option value="young">{isEnglish ? 'Under 30' : '३० पेक्षा कमी'}</option>
                  <option value="middle">{isEnglish ? '30 to 59' : '३० ते ५९'}</option>
                  <option value="senior">{isEnglish ? '60 and over' : '६० व अधिक'}</option>
                </select>
              </div>

              <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">
                <Briefcase size={14} className="text-govnavy flex-shrink-0" />
                <select
                  value={occupationFilter}
                  onChange={(e) => setOccupationFilter(e.target.value)}
                  aria-label={t('citizens_page.occupation')}
                  className="flex-1 bg-transparent border-none text-xs text-slate-700 font-semibold focus:outline-none"
                >
                  <option value="all">
                    {t('citizens_page.occupation')}: {isEnglish ? 'All' : 'सर्व'}
                  </option>
                  {occupations.map((job) => (
                    <option key={job} value={job}>
                      {job}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <p className="text-[10px] text-slate-400 font-semibold m-0">
              {isEnglish
                ? 'Name, ID and ward are matched by the server; age band and occupation narrow the results already returned.'
                : 'नाव, आयडी व वॉर्ड सर्व्हरवर शोधले जातात; वयोगट व व्यवसाय मिळालेल्या यादीतून निवडतात.'}
            </p>
          </div>

          {citizens.error && <ErrorNotice message={citizens.error} onRetry={citizens.refetch} />}

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
            {/* Register */}
            <div
              className={`bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden transition-all duration-300 ${
                selectedCitizenId ? 'lg:col-span-2' : 'lg:col-span-3'
              }`}
            >
              {citizens.loading && !citizens.data ? (
                <div className="p-10 flex items-center justify-center gap-2 text-slate-400">
                  <Loader2 size={18} className="animate-spin" />
                  <span className="text-xs font-bold uppercase tracking-wider">
                    {isEnglish ? 'Loading the register' : 'नोंदवही उघडत आहे'}
                  </span>
                </div>
              ) : !citizens.error && visible.length === 0 ? (
                <div className="p-4">
                  <EmptyState
                    title={
                      filtersActive
                        ? isEnglish
                          ? 'No resident matches these filters.'
                          : 'या निकषांशी जुळणारा रहिवासी नाही.'
                        : isEnglish
                          ? 'No residents on the register yet.'
                          : 'नोंदवहीत अद्याप कोणताही रहिवासी नाही.'
                    }
                    hint={
                      filtersActive
                        ? isEnglish
                          ? 'Clear the search or widen the ward filter.'
                          : 'शोध रिकामा करा किंवा वॉर्ड निवड बदला.'
                        : isEnglish
                          ? 'Use “Add resident” to record the first household.'
                          : '“रहिवासी जोडा” वापरून पहिली नोंद करा.'
                    }
                  />
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[720px] text-left text-xs sm:text-sm border-collapse">
                    <thead>
                      <tr className="border-b border-slate-200 bg-slate-50 text-slate-500 font-bold">
                        <th className="p-4">{isEnglish ? 'Citizen ID' : 'नागरिक आयडी'}</th>
                        <th className="p-4">{t('beneficiary.citizen')}</th>
                        <th className="p-4 text-center">{t('beneficiary.age')}</th>
                        <th className="p-4">{t('citizens_page.gender')}</th>
                        <th className="p-4 text-center">{t('beneficiary.ward')}</th>
                        <th className="p-4">{t('citizens_page.occupation')}</th>
                        <th className="p-4 text-right">{t('beneficiary.income')}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {visible.map((row) => {
                        const isSelected = selectedCitizenId === row.id;
                        return (
                          <tr
                            key={row.id}
                            tabIndex={0}
                            onClick={() => setSelectedCitizenId(row.id)}
                            onKeyDown={(event) => {
                              if (event.key === 'Enter' || event.key === ' ') {
                                event.preventDefault();
                                setSelectedCitizenId(row.id);
                              }
                            }}
                            className={`cursor-pointer transition-colors focus:outline-none focus:bg-govblue-50 ${
                              isSelected
                                ? 'bg-govblue-50 border-l-2 border-govnavy'
                                : 'hover:bg-slate-50'
                            }`}
                          >
                            <td className="p-4 font-mono text-[11px] font-bold text-govnavy">
                              {row.id}
                            </td>
                            <td className="p-4 font-bold text-slate-800">
                              {isEnglish ? row.name : row.nameMr}
                            </td>
                            <td className="p-4 text-center text-slate-600 tabular-nums">
                              {row.age}
                            </td>
                            <td className="p-4 text-slate-600">
                              {isEnglish ? row.gender : row.genderMr}
                            </td>
                            <td className="p-4 text-center text-slate-600 tabular-nums">
                              {row.ward}
                            </td>
                            <td className="p-4 text-slate-600">
                              {isEnglish ? row.occupation : row.occupationMr}
                            </td>
                            <td className="p-4 text-right text-slate-700 font-semibold tabular-nums">
                              {rupees(row.income)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Profile */}
            {selectedCitizenId && (
              <CitizenProfile
                citizenId={selectedCitizenId}
                onClose={() => setSelectedCitizenId(null)}
                onSelect={setSelectedCitizenId}
                onRegisterChanged={citizens.refetch}
              />
            )}
          </div>
        </>
      ) : (
        <VerificationQueue
          query={documents}
          statusFilter={docStatusFilter}
          setStatusFilter={setDocStatusFilter}
        />
      )}

      {creating && (
        <CitizenEditor
          citizen={null}
          onClose={() => setCreating(false)}
          onSaved={(saved) => {
            setCreating(false);
            citizens.refetch();
            // Open the record that was actually stored, so the officer sees the
            // server's version of what they just entered.
            setSelectedCitizenId(saved.id);
          }}
        />
      )}
    </div>
  );
};
