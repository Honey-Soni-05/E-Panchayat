import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  FileUp,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  Info,
  X,
} from 'lucide-react';

import { api } from '../../lib/api';
import type { SchemeReadResult } from '../../lib/api';
import { useMutation } from '../../lib/useApi';

/**
 * Upload a Government Resolution; the assistant proposes a scheme from it.
 *
 * The result is deliberately not presented as a finished scheme. What the
 * officer sees first is what the reader could NOT do: conditions it could not
 * turn into rules, criteria this system does not evaluate, and its own note on
 * what was ambiguous. A proposal that looks clean because its problems were
 * hidden is the failure this panel exists to prevent.
 *
 * The proposal is saved as pending. It reaches no citizen and produces no
 * eligibility result until an officer approves it in the review queue.
 */

export const SchemeReader: React.FC<{ onProposed: () => void }> = ({ onProposed }) => {
  const { i18n } = useTranslation();
  const isEnglish = i18n.language === 'en';

  const [result, setResult] = useState<SchemeReadResult | null>(null);

  const read = useMutation(
    (file: File) => api.schemes.readDocument(file),
    (proposal) => {
      setResult(proposal);
      onProposed();
    },
  );

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setResult(null);
      read.run(file);
    }
    // Reset so re-uploading the same file fires again.
    e.target.value = '';
  };

  const scheme = result?.scheme;
  const hasGaps =
    result && (result.unmappableConditions.length > 0 || result.discardedCriteria.length > 0);

  return (
    <section className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-black text-govblue-900 m-0 flex items-center gap-2">
            <FileUp size={16} className="text-govnavy" />
            {isEnglish ? 'Read a Government Resolution' : 'शासन निर्णय वाचा'}
          </h3>
          <p className="text-xs text-slate-500 font-semibold mt-1 max-w-xl leading-relaxed">
            {isEnglish
              ? 'Upload the GR announcing a scheme. The assistant proposes the scheme and its eligibility rules for your review — nothing is published to residents until you approve it.'
              : 'योजना जाहीर करणारा शासन निर्णय अपलोड करा. सहाय्यक योजना आणि पात्रता नियम सुचवतो — तुम्ही मंजूर करेपर्यंत ते नागरिकांना दिसत नाही.'}
          </p>
        </div>

        <label
          className={`shrink-0 px-4 py-2 rounded-lg text-xs font-bold transition-colors shadow-sm ${
            read.saving
              ? 'bg-slate-300 text-slate-600 cursor-not-allowed'
              : 'bg-govnavy hover:bg-govblue-700 text-white cursor-pointer'
          }`}
        >
          <span>
            {read.saving
              ? isEnglish
                ? 'Reading…'
                : 'वाचत आहे…'
              : isEnglish
                ? 'Upload GR'
                : 'शासन निर्णय अपलोड करा'}
          </span>
          <input
            type="file"
            accept=".pdf,.docx,.txt,.md"
            className="hidden"
            disabled={read.saving}
            onChange={onFile}
          />
        </label>
      </div>

      {read.saving && (
        <p className="flex items-center gap-2 text-xs text-govnavy font-bold">
          <Loader2 size={14} className="animate-spin" />
          {isEnglish
            ? 'Reading the document and drafting eligibility rules…'
            : 'दस्तऐवज वाचून पात्रता नियम तयार केले जात आहेत…'}
        </p>
      )}

      {read.error && (
        <div
          role="alert"
          className="p-3 rounded bg-rose-50 border border-rose-200 text-xs text-rose-700 font-semibold leading-relaxed"
        >
          {read.error}
        </div>
      )}

      {result && scheme && (
        <div className="border border-slate-200 rounded-lg overflow-hidden">
          <header className="p-4 bg-slate-50 border-b border-slate-200 flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[10px] font-black uppercase tracking-wide text-amber-700">
                {isEnglish ? 'Proposed — not yet published' : 'सुचवलेले — अद्याप प्रकाशित नाही'}
              </p>
              <h4 className="text-sm font-black text-govblue-900 mt-1 m-0">
                {isEnglish ? scheme.name : scheme.nameMr}
              </h4>
              <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                {isEnglish ? scheme.benefit : scheme.benefitMr}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setResult(null)}
              aria-label={isEnglish ? 'Dismiss' : 'बंद करा'}
              className="shrink-0 p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-200 transition-colors"
            >
              <X size={16} />
            </button>
          </header>

          <div className="p-4 space-y-3">
            {/* What the reader could not do comes first, deliberately. */}
            {result.unmappableConditions.length > 0 && (
              <div className="p-3 rounded bg-amber-50 border border-amber-200 space-y-1.5">
                <p className="flex items-center gap-1.5 text-[11px] font-black uppercase tracking-wide text-amber-900">
                  <AlertTriangle size={13} />
                  {isEnglish
                    ? 'Conditions that must be checked by hand'
                    : 'हाताने तपासाव्या लागणाऱ्या अटी'}
                </p>
                <ul className="list-disc pl-5 space-y-1 text-[11px] text-amber-900 leading-relaxed">
                  {result.unmappableConditions.map((condition, idx) => (
                    <li key={idx}>{condition}</li>
                  ))}
                </ul>
              </div>
            )}

            {result.discardedCriteria.length > 0 && (
              <div className="p-3 rounded bg-rose-50 border border-rose-200 space-y-1.5">
                <p className="flex items-center gap-1.5 text-[11px] font-black uppercase tracking-wide text-rose-800">
                  <AlertTriangle size={13} />
                  {isEnglish
                    ? 'Proposed rules this system cannot evaluate — not stored'
                    : 'ही प्रणाली तपासू शकत नाही असे नियम — साठवलेले नाहीत'}
                </p>
                <ul className="list-disc pl-5 space-y-1 text-[11px] text-rose-800 font-mono leading-relaxed">
                  {result.discardedCriteria.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              </div>
            )}

            {result.confidenceNote && (
              <p className="flex gap-2 text-[11px] text-slate-600 leading-relaxed">
                <Info size={13} className="shrink-0 mt-0.5 text-slate-400" />
                <span>
                  <span className="font-bold">
                    {isEnglish ? "Reader's note: " : 'वाचकाची टीप: '}
                  </span>
                  {result.confidenceNote}
                </span>
              </p>
            )}

            <div className="space-y-1.5">
              <p className="text-[10px] font-black uppercase tracking-wide text-slate-400">
                {isEnglish ? 'Eligibility rules extracted' : 'काढलेले पात्रता नियम'}
              </p>
              {Object.keys(scheme.criteria || {}).length === 0 ? (
                <p className="text-[11px] text-slate-500 font-medium">
                  {isEnglish
                    ? 'None. Every condition in this GR needs checking by hand.'
                    : 'काहीही नाही. या शासन निर्णयातील प्रत्येक अट हाताने तपासावी लागेल.'}
                </p>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(scheme.criteria || {}).map(([key, value]) => (
                    <span
                      key={key}
                      className="px-2 py-0.5 rounded bg-slate-100 border border-slate-200 text-[10px] font-mono text-slate-700"
                    >
                      {key}: {JSON.stringify(value)}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <p
              className={`flex items-start gap-1.5 text-[11px] leading-relaxed font-semibold ${
                hasGaps ? 'text-amber-800' : 'text-slate-500'
              }`}
            >
              {hasGaps ? (
                <AlertTriangle size={13} className="shrink-0 mt-0.5" />
              ) : (
                <CheckCircle2 size={13} className="shrink-0 mt-0.5 text-govgreen" />
              )}
              <span>
                {isEnglish
                  ? 'Check every figure against the GR before approving. It is waiting in the review queue below.'
                  : 'मंजूर करण्यापूर्वी प्रत्येक आकडा शासन निर्णयाशी ताडून पहा. ते खालील पुनरावलोकन रांगेत आहे.'}
              </span>
            </p>
          </div>
        </div>
      )}
    </section>
  );
};
