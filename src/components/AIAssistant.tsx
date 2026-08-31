/**
 * The Panchayat assistant.
 *
 * Every answer comes from `/assistant/ask`, which fetches the relevant database
 * records and hands them to the language model as its only permitted source.
 * The previous version of this file matched keywords against six `if` branches
 * and returned paragraphs its author had written in advance; the "sources" it
 * displayed were decoration and the knowledge graph beneath them was a
 * hand-written array of four nodes.
 *
 * Two deliberate honesty choices here:
 *
 *   * A badge says whether a model wrote the answer or whether it was read
 *     straight from the records because no key is configured. The user is never
 *     left guessing which they got.
 *   * "What I looked at" shows the exact facts retrieved for the question. It
 *     makes the retrieval step visible rather than leaving the answer looking
 *     like magic, and when an answer is wrong it separates "fetched the wrong
 *     records" from "worded it badly".
 */

import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Bot,
  Send,
  Loader2,
  User as UserIcon,
  Database,
  ChevronDown,
  Sparkles,
  FileSearch,
} from 'lucide-react';

import {
  ApiError,
  api,
  type AssistantAnswer,
  type AssistantContext,
} from '../lib/api';
import { useAuth } from '../lib/auth';
import { ErrorNotice } from './schemes/SchemeBits';

interface Turn {
  id: number;
  question: string;
  answer: AssistantAnswer | null;
  context: AssistantContext | null;
  error: string | null;
}

const OFFICER_PRESETS = [
  { en: 'Which projects are delayed and how much is unspent?', mr: 'कोणते प्रकल्प विलंबित आहेत आणि किती निधी शिल्लक आहे?' },
  { en: 'What grievances are still open, and in which wards?', mr: 'कोणत्या तक्रारी प्रलंबित आहेत आणि कोणत्या वॉर्डमध्ये?' },
  { en: 'Who in this village qualifies for a pension scheme?', mr: 'या गावात कोण पेन्शन योजनेसाठी पात्र आहे?' },
  { en: 'What action items from the last Gram Sabha are still open?', mr: 'मागील ग्रामसभेतील कोणती कार्यवाही अद्याप बाकी आहे?' },
];

const CITIZEN_PRESETS = [
  { en: 'Which schemes am I eligible for?', mr: 'मी कोणत्या योजनांसाठी पात्र आहे?' },
  { en: 'What documents am I missing?', mr: 'माझी कोणती कागदपत्रे बाकी आहेत?' },
  { en: 'What happened to my complaint?', mr: 'माझ्या तक्रारीचे काय झाले?' },
  { en: 'What development work is happening in my village?', mr: 'माझ्या गावात कोणती विकासकामे सुरू आहेत?' },
];

/** Render the model's light markdown — bold and bullets — without a library. */
const renderAnswer = (text: string) =>
  text.split('\n').map((line, i) => {
    const trimmed = line.trim();
    const isBullet = trimmed.startsWith('-') || trimmed.startsWith('•') || trimmed.startsWith('*');
    const content = isBullet ? trimmed.replace(/^[-•*]\s*/, '') : line;

    const parts = content.split('**').map((part, j) =>
      j % 2 === 1 ? <strong key={j}>{part}</strong> : part,
    );

    if (isBullet) {
      return (
        <li key={i} className="ml-4 list-disc my-0.5">
          {parts}
        </li>
      );
    }
    return (
      <p key={i} className="my-1 min-h-[0.5em]">
        {parts}
      </p>
    );
  });

export const AIAssistant: React.FC = () => {
  const { i18n } = useTranslation();
  const { user, isOfficer } = useAuth();
  const isEnglish = i18n.language === 'en';

  const [input, setInput] = useState('');
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [openContext, setOpenContext] = useState<number | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const presets = isOfficer ? OFFICER_PRESETS : CITIZEN_PRESETS;

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns, busy]);

  const ask = async (question: string) => {
    const text = question.trim();
    if (!text || busy) return;

    const id = Date.now();
    setTurns((prev) => [...prev, { id, question: text, answer: null, context: null, error: null }]);
    setInput('');
    setBusy(true);

    try {
      // Both calls run against the same retrieval, so the panel always shows
      // what the answer was actually built from.
      const [answer, context] = await Promise.all([
        api.assistant.ask(text, isEnglish ? 'en' : 'mr'),
        api.assistant.context(text, isEnglish ? 'en' : 'mr').catch(() => null),
      ]);
      setTurns((prev) =>
        prev.map((t) => (t.id === id ? { ...t, answer, context } : t)),
      );
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : isEnglish
            ? 'Something went wrong.'
            : 'काहीतरी चूक झाली.';
      setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, error: message } : t)));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <header className="space-y-1">
        <div className="flex items-center gap-2">
          <Bot size={20} className="text-govnavy" />
          <h2 className="text-lg font-extrabold text-govblue-900 tracking-tight m-0">
            {isEnglish ? 'Panchayat Assistant' : 'पंचायत सहाय्यक'}
          </h2>
        </div>
        <p className="text-xs text-slate-500 m-0">
          {isEnglish
            ? 'Answers come from your Panchayat records, in English or Marathi.'
            : 'उत्तरे तुमच्या पंचायत नोंदींमधून, इंग्रजी किंवा मराठीत.'}
        </p>
      </header>

      {/* Conversation */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-4 min-h-[280px]">
        {!turns.length && (
          <div className="text-center py-8 space-y-2">
            <div className="w-11 h-11 rounded-xl bg-govblue-50 border border-govblue-200 flex items-center justify-center mx-auto">
              <Bot size={20} className="text-govnavy" />
            </div>
            <p className="text-sm font-bold text-slate-700 m-0">
              {isEnglish
                ? `Namaskar${user ? `, ${user.fullName.split(' ')[0]}` : ''}`
                : `नमस्कार${user ? `, ${user.fullName.split(' ')[0]}` : ''}`}
            </p>
            <p className="text-xs text-slate-500 max-w-md mx-auto m-0 leading-relaxed">
              {isEnglish
                ? isOfficer
                  ? 'Ask about residents, grievances, projects, budgets, schemes or Gram Sabha decisions.'
                  : 'Ask about the schemes you qualify for, your documents, or your complaints.'
                : isOfficer
                  ? 'रहिवासी, तक्रारी, प्रकल्प, निधी, योजना किंवा ग्रामसभेच्या निर्णयांबद्दल विचारा.'
                  : 'तुम्ही पात्र असलेल्या योजना, तुमची कागदपत्रे किंवा तक्रारींबद्दल विचारा.'}
            </p>
          </div>
        )}

        {turns.map((turn) => (
          <div key={turn.id} className="space-y-3">
            {/* Question */}
            <div className="flex gap-2.5 justify-end">
              <div className="bg-govnavy text-white rounded-xl rounded-tr-sm px-3.5 py-2 max-w-[80%]">
                <p className="text-xs leading-relaxed m-0">{turn.question}</p>
              </div>
              <span className="w-7 h-7 rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-center flex-shrink-0">
                <UserIcon size={14} className="text-slate-500" />
              </span>
            </div>

            {/* Answer */}
            <div className="flex gap-2.5">
              <span className="w-7 h-7 rounded-lg bg-govblue-50 border border-govblue-200 flex items-center justify-center flex-shrink-0">
                <Bot size={14} className="text-govnavy" />
              </span>
              <div className="min-w-0 flex-1 space-y-2">
                {turn.error && <ErrorNotice message={turn.error} />}

                {!turn.answer && !turn.error && (
                  <div className="flex items-center gap-2 text-slate-400 py-1">
                    <Loader2 size={14} className="animate-spin" />
                    <span className="text-xs">
                      {isEnglish ? 'Reading the records' : 'नोंदी तपासत आहे'}
                    </span>
                  </div>
                )}

                {turn.answer && (
                  <>
                    <div className="bg-slate-50 border border-slate-200 rounded-xl rounded-tl-sm px-3.5 py-2.5 text-xs text-slate-800 leading-relaxed">
                      {renderAnswer(turn.answer.answer)}
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      {/* Honest about how the answer was produced. */}
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide border ${
                          turn.answer.mode === 'llm'
                            ? 'bg-govblue-50 text-govnavy border-govnavy/25'
                            : 'bg-amber-50 text-amber-800 border-amber-300'
                        }`}
                      >
                        {turn.answer.mode === 'llm' ? (
                          <>
                            <Sparkles size={9} />
                            {isEnglish ? 'Written from records' : 'नोंदींवरून लिहिलेले'}
                          </>
                        ) : (
                          <>
                            <Database size={9} />
                            {isEnglish ? 'Records only — no model key' : 'फक्त नोंदी — मॉडेल की नाही'}
                          </>
                        )}
                      </span>

                      {turn.context && turn.context.factCount > 0 && (
                        <button
                          onClick={() =>
                            setOpenContext(openContext === turn.id ? null : turn.id)
                          }
                          className="inline-flex items-center gap-1 text-[11px] font-bold text-govnavy hover:underline"
                        >
                          <FileSearch size={11} />
                          {isEnglish
                            ? `What I looked at (${turn.context.factCount})`
                            : `काय तपासले (${turn.context.factCount})`}
                          <ChevronDown
                            size={11}
                            className={openContext === turn.id ? 'rotate-180' : ''}
                          />
                        </button>
                      )}
                    </div>

                    {/* Sources */}
                    {turn.answer.sources.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {turn.answer.sources.slice(0, 6).map((source, i) => (
                          <span
                            key={`${source.entityId}-${i}`}
                            className="px-2 py-0.5 rounded bg-white border border-slate-200 text-[10px] text-slate-600"
                            title={source.entityId}
                          >
                            <span className="text-slate-400 uppercase font-bold mr-1">
                              {source.entityType}
                            </span>
                            {source.title.length > 46
                              ? `${source.title.slice(0, 46)}…`
                              : source.title}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* The retrieved facts themselves */}
                    {openContext === turn.id && turn.context && (
                      <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-2">
                        <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 m-0">
                          {isEnglish
                            ? `Retrieved from: ${turn.context.topics.join(', ')}`
                            : `यामधून घेतले: ${turn.context.topics.join(', ')}`}
                        </p>
                        <ul className="space-y-1">
                          {turn.context.facts.map((fact, i) => (
                            <li
                              key={i}
                              className="text-[11px] text-slate-600 leading-relaxed flex gap-1.5"
                            >
                              <span className="text-govsaffron flex-shrink-0">•</span>
                              <span>{fact}</span>
                            </li>
                          ))}
                        </ul>
                        <p className="text-[10px] text-slate-400 m-0 pt-1 border-t border-slate-100">
                          {isEnglish
                            ? 'The assistant may use only these records. It is instructed not to add anything else.'
                            : 'सहाय्यक फक्त याच नोंदी वापरू शकतो; इतर काहीही जोडण्यास मनाई आहे.'}
                        </p>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>

      {/* Presets */}
      {!turns.length && (
        <div className="flex flex-wrap gap-2">
          {presets.map((preset) => (
            <button
              key={preset.en}
              onClick={() => ask(isEnglish ? preset.en : preset.mr)}
              className="px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:border-govnavy/40 hover:bg-slate-50 text-[11px] font-semibold text-slate-600 text-left transition-colors"
            >
              {isEnglish ? preset.en : preset.mr}
            </button>
          ))}
        </div>
      )}

      {/* Composer */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(input);
        }}
        className="flex gap-2"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={busy}
          placeholder={
            isEnglish ? 'Ask about your Panchayat records' : 'पंचायत नोंदींबद्दल विचारा'
          }
          className="flex-1 px-3.5 py-2.5 text-sm border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-govnavy/25 disabled:bg-slate-50"
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="px-4 py-2.5 rounded-lg bg-govnavy hover:bg-govblue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white transition-colors"
          aria-label={isEnglish ? 'Send' : 'पाठवा'}
        >
          {busy ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
        </button>
      </form>
    </div>
  );
};
