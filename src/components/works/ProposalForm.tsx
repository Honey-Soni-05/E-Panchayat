/**
 * Opening a proposed work — usually out of one or more complaints.
 *
 * This is the step that turns "we need twenty streetlights" from a complaint
 * nobody can close into a work somebody can decide on. It asks for what is
 * known at that moment: what is wanted, where, how many — and, if the officer
 * can already say, roughly what it will cost. That figure is optional and it is
 * the officer's own: it goes into the ledger as the first estimate, with their
 * name and the date, and can be revised once the need has been checked on site.
 * Nothing in this system produces a rupee figure by itself.
 *
 * The complaints are linked, not merged. Each resident keeps their own, with
 * their own words and their own timeline, pointing at the shared work.
 */

import React, { useState } from 'react';
import { ChevronRight, Loader2, Users, X } from 'lucide-react';

import {
  api,
  type Grievance,
  type ProjectDetail,
  type ProposalCreate,
  type Village,
} from '../../lib/api';
import { useMutation, useQuery } from '../../lib/useApi';
import { ErrorNotice } from '../schemes/SchemeBits';
import { pick, rupees, useVocabulary } from './WorkBits';

const INPUT =
  'w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-govnavy/25';
const LABEL = 'block text-xs font-bold text-slate-600';

export interface ProposalSeed {
  name?: string;
  description?: string;
  ward?: number;
  category?: string;
  unitsPlanned?: number | null;
  /** The complaints this proposal answers. */
  grievances?: Grievance[];
}

/** A starting guess at what is being counted, from the wording of the request.
 *  Only ever a prefill in an editable field. */
const guessUnits = (text: string): { unit: string; unitMr: string; asset: string } | null => {
  const lowered = text.toLowerCase();
  if (/street\s?light|पथदिव/.test(lowered)) {
    return { unit: 'streetlights', unitMr: 'पथदिवे', asset: 'streetlight' };
  }
  if (/\btaps?\b|stand ?post|नळ/.test(lowered)) {
    return { unit: 'tap stands', unitMr: 'नळ कोंडाळी', asset: 'water' };
  }
  if (/toilet|शौचालय/.test(lowered)) {
    return { unit: 'toilet blocks', unitMr: 'शौचालये', asset: 'toilet' };
  }
  return null;
};

export const ProposalForm: React.FC<{
  isEnglish: boolean;
  /** Null for an administrator, who has to say which village the work is for. */
  village: Village | null;
  seed?: ProposalSeed;
  onClose: () => void;
  onCreated: (project: ProjectDetail) => void;
}> = ({ isEnglish, village, seed, onClose, onCreated }) => {
  const vocabulary = useVocabulary();
  const linked = seed?.grievances ?? [];
  const guess = guessUnits(`${seed?.name ?? ''} ${seed?.description ?? ''}`);

  const [name, setName] = useState(seed?.name ?? '');
  const [nameMr, setNameMr] = useState('');
  const [description, setDescription] = useState(seed?.description ?? '');
  const [ward, setWard] = useState(String(seed?.ward ?? 1));
  const [location, setLocation] = useState(seed?.ward ? `Ward ${seed.ward}` : '');
  const [locationMr, setLocationMr] = useState('');
  const [unitsPlanned, setUnitsPlanned] = useState(
    seed?.unitsPlanned ? String(seed.unitsPlanned) : '',
  );
  const [unitLabel, setUnitLabel] = useState(guess?.unit ?? '');
  const [unitLabelMr, setUnitLabelMr] = useState(guess?.unitMr ?? '');
  const [assetType, setAssetType] = useState(guess?.asset ?? '');
  const [expectedCompletion, setExpectedCompletion] = useState('');
  const [estimate, setEstimate] = useState('');
  const [estimateNote, setEstimateNote] = useState('');
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [villageId, setVillageId] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  // An administrator works across the block, so the form has to ask. An
  // officer's proposal always belongs to the Gram Panchayat they serve.
  const needsVillage = village === null && linked.length === 0;
  const villages = useQuery<Village[]>(
    () => (needsVillage ? api.villages.list(true) : Promise.resolve([])),
    [needsVillage],
  );

  const wardOptions = village?.wardCount
    ? Array.from({ length: village.wardCount }, (_, i) => i + 1)
    : null;

  const residents = new Set(linked.map((g) => g.citizenId ?? g.id)).size;
  const located = linked.some((g) => g.latitude !== null && g.longitude !== null);

  const create = useMutation((body: ProposalCreate) => api.projects.propose(body), onCreated);

  const submit = () => {
    const lat = latitude.trim() === '' ? undefined : Number(latitude);
    const lng = longitude.trim() === '' ? undefined : Number(longitude);
    if ((lat === undefined) !== (lng === undefined) || Number.isNaN(lat) || Number.isNaN(lng)) {
      setFormError(
        isEnglish
          ? 'Give both the latitude and the longitude, or leave both empty.'
          : 'अक्षांश व रेखांश दोन्ही भरा, किंवा दोन्ही रिकामे ठेवा.',
      );
      return;
    }
    if (needsVillage && !villageId) {
      setFormError(
        isEnglish ? 'Say which Gram Panchayat this work is for.' : 'हे काम कोणत्या ग्रामपंचायतीसाठी आहे ते निवडा.',
      );
      return;
    }
    const cost = estimate.trim() === '' ? undefined : Number(estimate);
    if (cost !== undefined && !(cost > 0)) {
      setFormError(
        isEnglish
          ? 'Give the approximate cost in rupees, or leave it empty for now.'
          : 'अंदाजित खर्च रुपयांमध्ये द्या, किंवा आत्ता रिकामा ठेवा.',
      );
      return;
    }
    setFormError(null);

    const units = unitsPlanned.trim() === '' ? undefined : Number(unitsPlanned);
    create.run({
      estimate: cost,
      estimateNote: cost !== undefined ? estimateNote.trim() || undefined : undefined,
      name: name.trim(),
      nameMr: nameMr.trim() || undefined,
      description: description.trim(),
      ward: Number(ward),
      location: location.trim(),
      locationMr: locationMr.trim() || undefined,
      latitude: lat,
      longitude: lng,
      category: seed?.category,
      unitsPlanned: units,
      unitLabel: units ? unitLabel.trim() || undefined : undefined,
      unitLabelMr: units ? unitLabelMr.trim() || undefined : undefined,
      assetType: assetType || undefined,
      expectedCompletion: expectedCompletion || undefined,
      grievanceIds: linked.map((g) => g.id),
      villageId: needsVillage ? villageId : undefined,
    });
  };

  return (
    <div
      className="fixed inset-0 z-[60] bg-slate-900/40 backdrop-blur-sm flex items-start justify-center p-3 sm:p-6 overflow-y-auto"
      role="dialog"
      aria-modal="true"
      aria-label={isEnglish ? 'New work proposal' : 'नवीन काम प्रस्ताव'}
    >
      <div className="w-full max-w-2xl bg-white rounded-2xl border border-slate-200 shadow-xl my-auto">
        <header className="p-4 border-b border-slate-100 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-extrabold text-govblue-900">
              {isEnglish ? 'New work proposal' : 'नवीन काम प्रस्ताव'}
            </h2>
            <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
              {isEnglish
                ? 'What is wanted, where, how many, and roughly what it will cost if you can say. Approval and money are recorded afterwards, step by step.'
                : 'काय हवे आहे, कुठे, किती, आणि सांगता येत असल्यास अंदाजे खर्च. मंजुरी व निधी नंतर टप्प्याटप्प्याने नोंदवले जातात.'}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={isEnglish ? 'Close' : 'बंद करा'}
            className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors flex-shrink-0"
          >
            <X size={16} />
          </button>
        </header>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
          className="p-4 space-y-4 max-h-[75vh] overflow-y-auto"
        >
          {linked.length > 0 && (
            <div className="rounded-lg border border-govblue-200 bg-govblue-50 p-3 space-y-2">
              <p className="text-[11px] font-bold uppercase tracking-wider text-govnavy flex items-center gap-1.5">
                <Users size={12} />
                {isEnglish
                  ? `Answering ${linked.length} complaint(s) from ${residents} resident(s)`
                  : `${residents} रहिवाशांच्या ${linked.length} तक्रारींना उत्तर`}
              </p>
              <ul className="p-0 list-none space-y-0.5">
                {linked.map((g) => (
                  <li key={g.id} className="text-[11px] text-slate-600 truncate">
                    {pick(g.title, g.titleMr, isEnglish)}
                    <span className="text-slate-400"> · {g.citizenName}</span>
                  </li>
                ))}
              </ul>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                {isEnglish
                  ? 'Each stays its own complaint. Once linked, its owner can follow this work from their tracking page.'
                  : 'प्रत्येक तक्रार स्वतंत्र राहते. जोडल्यानंतर तक्रारदार त्यांच्या पृष्ठावरून या कामाचा मागोवा घेऊ शकतो.'}
              </p>
            </div>
          )}

          {needsVillage && (
            <div className="space-y-1.5">
              <label htmlFor="proposal-village" className={LABEL}>
                {isEnglish ? 'Gram Panchayat' : 'ग्रामपंचायत'}
              </label>
              <select
                id="proposal-village"
                required
                value={villageId}
                onChange={(e) => setVillageId(e.target.value)}
                className={INPUT}
              >
                <option value="">{isEnglish ? 'Choose a village' : 'गाव निवडा'}</option>
                {(villages.data ?? []).map((v) => (
                  <option key={v.id} value={v.id}>
                    {pick(v.name, v.nameMr, isEnglish)}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label htmlFor="proposal-name" className={LABEL}>
                {isEnglish ? 'Name of the work (English)' : 'कामाचे नाव (इंग्रजी)'}
              </label>
              <input
                id="proposal-name"
                required
                minLength={3}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={isEnglish ? 'e.g. 20 streetlights, Market Road' : 'उदा. 20 streetlights, Market Road'}
                className={INPUT}
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="proposal-name-mr" className={LABEL}>
                {isEnglish ? 'Name of the work (Marathi)' : 'कामाचे नाव (मराठी)'}
              </label>
              <input
                id="proposal-name-mr"
                value={nameMr}
                onChange={(e) => setNameMr(e.target.value)}
                placeholder={isEnglish ? 'Optional' : 'ऐच्छिक'}
                className={INPUT}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="proposal-description" className={LABEL}>
              {isEnglish ? 'What is to be done' : 'काय करायचे आहे'}
            </label>
            <textarea
              id="proposal-description"
              required
              minLength={3}
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className={`${INPUT} resize-y`}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="space-y-1.5">
              <label htmlFor="proposal-ward" className={LABEL}>
                {isEnglish ? 'Ward' : 'वॉर्ड'}
              </label>
              {wardOptions ? (
                <select
                  id="proposal-ward"
                  value={ward}
                  onChange={(e) => setWard(e.target.value)}
                  className={INPUT}
                >
                  {wardOptions.map((n) => (
                    <option key={n} value={String(n)}>
                      {n}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  id="proposal-ward"
                  type="number"
                  min={1}
                  required
                  value={ward}
                  onChange={(e) => setWard(e.target.value)}
                  className={INPUT}
                />
              )}
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <label htmlFor="proposal-location" className={LABEL}>
                {isEnglish ? 'Where' : 'ठिकाण'}
              </label>
              <input
                id="proposal-location"
                required
                minLength={2}
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder={isEnglish ? 'e.g. Ward 2, Market Road to the temple' : 'उदा. Ward 2, Market Road to the temple'}
                className={INPUT}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="proposal-location-mr" className={LABEL}>
              {isEnglish ? 'Where (Marathi)' : 'ठिकाण (मराठी)'}
            </label>
            <input
              id="proposal-location-mr"
              value={locationMr}
              onChange={(e) => setLocationMr(e.target.value)}
              placeholder={isEnglish ? 'Optional' : 'ऐच्छिक'}
              className={INPUT}
            />
          </div>

          {/* A count, where the work has one */}
          <fieldset className="border border-slate-200 rounded-lg p-3 space-y-2.5">
            <legend className="px-1 text-[11px] font-bold text-slate-600">
              {isEnglish ? 'How many, if it can be counted' : 'किती, मोजता येत असल्यास'}
            </legend>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="space-y-1.5">
                <label htmlFor="proposal-units" className="block text-[11px] font-bold text-slate-600">
                  {isEnglish ? 'Number planned' : 'नियोजित संख्या'}
                </label>
                <input
                  id="proposal-units"
                  type="number"
                  min={1}
                  value={unitsPlanned}
                  onChange={(e) => setUnitsPlanned(e.target.value)}
                  placeholder={isEnglish ? 'Leave empty if not counted' : 'मोजता येत नसल्यास रिकामे'}
                  className={INPUT}
                />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="proposal-unit" className="block text-[11px] font-bold text-slate-600">
                  {isEnglish ? 'Of what (English)' : 'कशाची (इंग्रजी)'}
                </label>
                <input
                  id="proposal-unit"
                  value={unitLabel}
                  maxLength={60}
                  onChange={(e) => setUnitLabel(e.target.value)}
                  placeholder="streetlights"
                  className={INPUT}
                />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="proposal-unit-mr" className="block text-[11px] font-bold text-slate-600">
                  {isEnglish ? 'Of what (Marathi)' : 'कशाची (मराठी)'}
                </label>
                <input
                  id="proposal-unit-mr"
                  value={unitLabelMr}
                  maxLength={60}
                  onChange={(e) => setUnitLabelMr(e.target.value)}
                  placeholder="पथदिवे"
                  className={INPUT}
                />
              </div>
            </div>
            <p className="text-[10px] text-slate-500 leading-relaxed">
              {isEnglish
                ? 'With a number, progress is recorded as “14 of 20” — something anyone can check on site — instead of a percentage.'
                : 'संख्या दिल्यास प्रगती “२० पैकी १४” अशी नोंदवली जाते — जी स्थळावर कोणीही तपासू शकते — टक्केवारीऐवजी.'}
            </p>
          </fieldset>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label htmlFor="proposal-asset" className={LABEL}>
                {isEnglish ? 'What it adds to the village' : 'गावात काय भर पडेल'}
              </label>
              <select
                id="proposal-asset"
                value={assetType}
                onChange={(e) => setAssetType(e.target.value)}
                className={INPUT}
              >
                <option value="">
                  {isEnglish ? 'Nothing new (a repair or a service)' : 'नवीन काही नाही (दुरुस्ती / सेवा)'}
                </option>
                {(vocabulary?.assetTypes ?? []).map((item) => (
                  <option key={item.code} value={item.code}>
                    {pick(item.label, item.labelMr, isEnglish)}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <label htmlFor="proposal-due" className={LABEL}>
                {isEnglish ? 'Expected completion (optional)' : 'अपेक्षित पूर्तता (ऐच्छिक)'}
              </label>
              <input
                id="proposal-due"
                type="date"
                value={expectedCompletion}
                onChange={(e) => setExpectedCompletion(e.target.value)}
                className={INPUT}
              />
            </div>
          </div>
          <p className="text-[10px] text-slate-500 leading-relaxed -mt-2">
            {isEnglish
              ? 'When the work is completed, what it built is added to the asset register and shown on the map.'
              : 'काम पूर्ण झाल्यावर उभारलेली मालमत्ता नोंदवहीत जोडली जाते आणि नकाशावर दिसते.'}
          </p>

          {/* What it is expected to cost — the officer's own figure, optional */}
          <fieldset className="border border-slate-200 rounded-lg p-3 space-y-2.5">
            <legend className="px-1 text-[11px] font-bold text-slate-600">
              {isEnglish ? 'Approximate cost, if you can say' : 'अंदाजे खर्च, सांगता येत असल्यास'}
            </legend>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="space-y-1.5">
                <label htmlFor="proposal-estimate" className="block text-[11px] font-bold text-slate-600">
                  {isEnglish ? 'Amount (₹)' : 'रक्कम (₹)'}
                </label>
                <input
                  id="proposal-estimate"
                  type="number"
                  min={1}
                  step="any"
                  value={estimate}
                  onChange={(e) => setEstimate(e.target.value)}
                  placeholder={isEnglish ? 'Leave empty if not known' : 'माहीत नसल्यास रिकामे'}
                  className={INPUT}
                />
                {Number(estimate) > 0 && (
                  <p className="text-[10px] text-slate-500 tabular-nums">= {rupees(Number(estimate))}</p>
                )}
              </div>
              <div className="space-y-1.5 sm:col-span-2">
                <label htmlFor="proposal-estimate-note" className="block text-[11px] font-bold text-slate-600">
                  {isEnglish ? 'What it covers' : 'यात काय समाविष्ट आहे'}
                </label>
                <input
                  id="proposal-estimate-note"
                  value={estimateNote}
                  maxLength={1000}
                  onChange={(e) => setEstimateNote(e.target.value)}
                  placeholder={
                    isEnglish
                      ? 'e.g. 20 poles, fittings, cabling and labour'
                      : 'उदा. २० खांब, दिवे, केबल व मजुरी'
                  }
                  className={INPUT}
                />
              </div>
            </div>
            <p className="text-[10px] text-slate-500 leading-relaxed">
              {isEnglish
                ? 'Recorded as the first estimate, under your name. It decides nothing by itself and can be revised later; the earlier figure stays on the record.'
                : 'तुमच्या नावाने पहिला अंदाज म्हणून नोंदवला जातो. त्याने काहीही ठरत नाही आणि नंतर सुधारता येतो; आधीचा आकडा नोंदीत राहतो.'}
            </p>
          </fieldset>

          {/* Coordinates are optional, and never invented */}
          <fieldset className="border border-slate-200 rounded-lg p-3 space-y-2">
            <legend className="px-1 text-[11px] font-bold text-slate-600">
              {isEnglish ? 'Site coordinates (optional)' : 'ठिकाणाचे निर्देशांक (ऐच्छिक)'}
            </legend>
            <div className="grid grid-cols-2 gap-3">
              <input
                type="number"
                step="any"
                aria-label={isEnglish ? 'Latitude' : 'अक्षांश'}
                placeholder={isEnglish ? 'Latitude' : 'अक्षांश'}
                value={latitude}
                onChange={(e) => setLatitude(e.target.value)}
                className={INPUT}
              />
              <input
                type="number"
                step="any"
                aria-label={isEnglish ? 'Longitude' : 'रेखांश'}
                placeholder={isEnglish ? 'Longitude' : 'रेखांश'}
                value={longitude}
                onChange={(e) => setLongitude(e.target.value)}
                className={INPUT}
              />
            </div>
            <p className="text-[10px] text-slate-500 leading-relaxed">
              {located
                ? isEnglish
                  ? 'Left empty, the work is placed where the first located complaint was reported.'
                  : 'रिकामे ठेवल्यास, ठिकाण नोंद असलेल्या पहिल्या तक्रारीच्या जागी काम दाखवले जाईल.'
                : isEnglish
                  ? 'Left empty, the work is placed at the village’s recorded centre point until someone gives its real position.'
                  : 'रिकामे ठेवल्यास, प्रत्यक्ष ठिकाण नोंदवेपर्यंत काम गावाच्या नोंदवलेल्या मध्यबिंदूवर दाखवले जाईल.'}
            </p>
          </fieldset>

          <p className="text-[11px] text-govnavy font-semibold flex items-start gap-1.5 leading-relaxed">
            <ChevronRight size={13} className="mt-0.5 flex-shrink-0" />
            <span>
              {linked.length > 0
                ? isEnglish
                  ? `This opens the work at “Proposed” and moves ${linked.length} complaint(s) to “In Progress”. Each complainant will see that their complaint has been taken up as a development work.`
                  : `काम “प्रस्तावित” टप्प्यावर उघडेल आणि ${linked.length} तक्रारी “प्रगतीपथावर” जातील. प्रत्येक तक्रारदाराला त्यांची तक्रार विकास काम म्हणून हाती घेतल्याचे दिसेल.`
                : isEnglish
                  ? 'This opens the work at “Proposed”. It has no approval and no money until those are recorded.'
                  : 'काम “प्रस्तावित” टप्प्यावर उघडेल. मंजुरी व निधी नोंदवेपर्यंत त्याला काहीही नाही.'}
            </span>
          </p>

          {formError && <ErrorNotice message={formError} />}
          {create.error && <ErrorNotice message={create.error} />}

          <div className="flex flex-wrap gap-2 pt-1">
            <button
              type="submit"
              disabled={create.saving}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-govnavy hover:bg-govblue-700 disabled:opacity-60 text-white text-xs font-bold transition-colors"
            >
              {create.saving && <Loader2 size={13} className="animate-spin" />}
              {isEnglish ? 'Open the proposal' : 'प्रस्ताव उघडा'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg border border-slate-300 hover:bg-slate-50 text-slate-600 text-xs font-bold transition-colors"
            >
              {isEnglish ? 'Cancel' : 'रद्द करा'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
