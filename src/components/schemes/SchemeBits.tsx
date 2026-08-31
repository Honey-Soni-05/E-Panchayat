/**
 * Shared pieces for the two scheme screens.
 *
 * The important one is `describeCriteria`, which turns the backend's rule
 * dictionary into sentences a Panchayat officer or a resident can read. A
 * scheme whose rules are visible is a scheme people can argue with — which for
 * welfare eligibility is the point.
 */

import React from 'react';
import {
  CheckCircle2,
  FileWarning,
  HelpCircle,
  XCircle,
  Sparkles,
  ExternalLink,
  ShieldQuestion,
} from 'lucide-react';

import type { EligibilityStatus, Scheme, SchemeCriteria } from '../../lib/api';

// ─── Status chip ────────────────────────────────────────────────────────────

const STATUS_STYLES: Record<
  EligibilityStatus,
  { icon: typeof CheckCircle2; classes: string; labelEn: string; labelMr: string }
> = {
  Eligible: {
    icon: CheckCircle2,
    classes: 'bg-emerald-50 text-emerald-800 border-emerald-300',
    labelEn: 'You qualify',
    labelMr: 'तुम्ही पात्र आहात',
  },
  'Missing Documents': {
    icon: FileWarning,
    classes: 'bg-amber-50 text-amber-900 border-amber-300',
    labelEn: 'Almost — documents needed',
    labelMr: 'जवळपास — कागदपत्रे हवीत',
  },
  'Needs Review': {
    icon: ShieldQuestion,
    classes: 'bg-sky-50 text-sky-900 border-sky-300',
    labelEn: 'Needs officer check',
    labelMr: 'अधिकारी तपासणी आवश्यक',
  },
  Ineligible: {
    icon: XCircle,
    classes: 'bg-slate-100 text-slate-600 border-slate-300',
    labelEn: 'Not eligible',
    labelMr: 'पात्र नाही',
  },
};

export const StatusChip: React.FC<{
  status: EligibilityStatus;
  isEnglish: boolean;
  /** Officer lists want the bare status; the citizen view wants the friendly wording. */
  friendly?: boolean;
  size?: 'sm' | 'md';
}> = ({ status, isEnglish, friendly = false, size = 'md' }) => {
  const style = STATUS_STYLES[status];
  const Icon = style.icon;
  const label = friendly
    ? isEnglish
      ? style.labelEn
      : style.labelMr
    : status;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-bold whitespace-nowrap ${style.classes} ${
        size === 'sm' ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-1 text-[11px]'
      }`}
    >
      <Icon size={size === 'sm' ? 11 : 13} />
      {label}
    </span>
  );
};

// ─── Level and confidence badges ────────────────────────────────────────────

export const LevelBadge: React.FC<{ level: Scheme['level'] }> = ({ level }) => (
  <span
    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide border ${
      level === 'central'
        ? 'bg-govblue-50 text-govnavy border-govnavy/25'
        : 'bg-orange-50 text-govsaffron border-govsaffron/30'
    }`}
  >
    {level === 'central' ? 'Central' : 'Maharashtra'}
  </span>
);

export const NewBadge: React.FC<{ isEnglish: boolean }> = ({ isEnglish }) => (
  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide bg-govsaffron text-white">
    <Sparkles size={10} />
    {isEnglish ? 'New' : 'नवीन'}
  </span>
);

/** A scheme announced within the last three years counts as new. */
export const isRecent = (announcedOn: string | null): boolean => {
  if (!announcedOn) return false;
  const announced = new Date(announcedOn);
  const cutoff = new Date();
  cutoff.setFullYear(cutoff.getFullYear() - 3);
  return announced >= cutoff;
};

export const formatAnnounced = (value: string | null, isEnglish: boolean): string => {
  if (!value) return isEnglish ? 'Date not recorded' : 'तारीख नोंद नाही';
  return new Date(value).toLocaleDateString(isEnglish ? 'en-IN' : 'mr-IN', {
    year: 'numeric',
    month: 'short',
  });
};

export const SourceLink: React.FC<{ scheme: Scheme; isEnglish: boolean }> = ({
  scheme,
  isEnglish,
}) => {
  if (!scheme.sourceUrl) return null;
  return (
    <a
      href={scheme.sourceUrl}
      target="_blank"
      rel="noreferrer noopener"
      className="inline-flex items-center gap-1 text-[11px] font-bold text-govnavy hover:underline"
    >
      {isEnglish ? 'Official source' : 'अधिकृत स्रोत'}
      <ExternalLink size={11} />
    </a>
  );
};

// ─── Criteria in plain language ─────────────────────────────────────────────

const CATEGORY_LABEL: Record<string, string> = {
  SC: 'Scheduled Caste',
  ST: 'Scheduled Tribe',
  OBC: 'Other Backward Class',
  SEBC: 'Socially and Educationally Backward Class',
  VJNT: 'Vimukta Jati / Nomadic Tribe',
  SBC: 'Special Backward Class',
  Open: 'Open category',
};

const rupees = (n: number) => `₹${n.toLocaleString('en-IN')}`;

/**
 * Render one criteria dictionary as readable conditions.
 * Returns English and Marathi in parallel so the caller picks by language.
 */
export function describeCriteria(
  criteria: SchemeCriteria,
  isEnglish: boolean,
): string[] {
  const out: string[] = [];
  const push = (en: string, mr: string) => out.push(isEnglish ? en : mr);

  if (criteria.min_age !== undefined && criteria.max_age !== undefined) {
    push(`Aged between ${criteria.min_age} and ${criteria.max_age}`,
         `वय ${criteria.min_age} ते ${criteria.max_age} दरम्यान`);
  } else if (criteria.min_age !== undefined) {
    push(`Aged ${criteria.min_age} or above`, `वय ${criteria.min_age} किंवा अधिक`);
  } else if (criteria.max_age !== undefined) {
    push(`Aged ${criteria.max_age} or below`, `वय ${criteria.max_age} किंवा कमी`);
  }

  if (criteria.max_income !== undefined) {
    push(`Annual household income up to ${rupees(criteria.max_income)}`,
         `वार्षिक कौटुंबिक उत्पन्न ${rupees(criteria.max_income)} पर्यंत`);
  }
  if (criteria.min_income !== undefined) {
    push(`Annual household income at least ${rupees(criteria.min_income)}`,
         `वार्षिक उत्पन्न किमान ${rupees(criteria.min_income)}`);
  }

  if (criteria.gender) {
    push(criteria.gender === 'Female' ? 'Women only' : 'Men only',
         criteria.gender === 'Female' ? 'फक्त महिलांसाठी' : 'फक्त पुरुषांसाठी');
  }

  if (criteria.marital_status_any?.length) {
    push(`Marital status: ${criteria.marital_status_any.join(', ').toLowerCase()}`,
         `वैवाहिक स्थिती: ${criteria.marital_status_any.join(', ')}`);
  }

  if (criteria.category_any?.length) {
    const named = criteria.category_any.map((c) => CATEGORY_LABEL[c] ?? c).join(' or ');
    push(`Open to ${named} applicants`, `${criteria.category_any.join(' / ')} प्रवर्गासाठी`);
  }

  if (criteria.requires_bpl) {
    push('Household must be on the Below Poverty Line list',
         'कुटुंब दारिद्र्यरेषेखालील यादीत असणे आवश्यक');
  }

  if (criteria.requires_secc_listed) {
    push('Household must appear in the SECC-2011 deprivation data',
         'कुटुंब एसईसीसी-२०११ वंचितता यादीत असणे आवश्यक');
  }

  if (criteria.ration_card_any?.length) {
    push(`Ration card: ${criteria.ration_card_any.join(', ')}`,
         `शिधापत्रिका: ${criteria.ration_card_any.join(', ')}`);
  }

  if (criteria.min_land_hectares !== undefined && criteria.max_land_hectares !== undefined) {
    push(`Land holding between ${criteria.min_land_hectares} and ${criteria.max_land_hectares} hectares`,
         `जमीनधारणा ${criteria.min_land_hectares} ते ${criteria.max_land_hectares} हेक्टर दरम्यान`);
  } else if (criteria.max_land_hectares !== undefined) {
    push(`Land holding up to ${criteria.max_land_hectares} hectares`,
         `जमीनधारणा ${criteria.max_land_hectares} हेक्टरपर्यंत`);
  } else if (criteria.min_land_hectares !== undefined) {
    push('Must own cultivable land', 'लागवडीयोग्य जमीन असणे आवश्यक');
  }

  if (criteria.min_disability_percent !== undefined) {
    push(`Disability assessed at ${criteria.min_disability_percent}% or more`,
         `${criteria.min_disability_percent}% किंवा अधिक दिव्यांगत्व`);
  }

  if (criteria.occupation_any?.length) {
    // The keyword list carries both languages; show only the English words.
    const words = criteria.occupation_any.filter((w) => /^[\x20-\x7E]+$/.test(w));
    push(`Occupation: ${(words.length ? words : criteria.occupation_any).join(', ')}`,
         `व्यवसाय: ${criteria.occupation_any.join(', ')}`);
  }

  if (criteria.is_head) {
    push('Household head only', 'फक्त कुटुंब प्रमुखांसाठी');
  }

  if (criteria.ward_in?.length) {
    push(`Wards ${criteria.ward_in.join(', ')}`, `वॉर्ड ${criteria.ward_in.join(', ')}`);
  }

  if (criteria.any_of?.length) {
    const branches = criteria.any_of.map((branch) =>
      describeCriteria(branch, isEnglish).join(' and '),
    );
    push(`Any one of: ${branches.join('  —OR—  ')}`,
         `यापैकी कोणतीही एक: ${branches.join('  —किंवा—  ')}`);
  }

  if (!out.length) {
    push('No stated restrictions — open to all residents',
         'कोणतीही अट नाही — सर्व रहिवाशांसाठी खुली');
  }

  return out;
}

export const CriteriaList: React.FC<{
  criteria: SchemeCriteria;
  isEnglish: boolean;
}> = ({ criteria, isEnglish }) => (
  <ul className="space-y-1.5">
    {describeCriteria(criteria, isEnglish).map((line, i) => (
      <li key={i} className="flex gap-2 text-xs text-slate-700 leading-relaxed">
        <span className="text-govsaffron mt-0.5 flex-shrink-0">•</span>
        <span>{line}</span>
      </li>
    ))}
    {criteria.manual_review && (
      <li className="flex gap-2 text-xs text-sky-800 leading-relaxed bg-sky-50 border border-sky-200 rounded p-2 mt-2">
        <HelpCircle size={13} className="mt-0.5 flex-shrink-0" />
        <span>
          {isEnglish
            ? 'This scheme has conditions that cannot be judged from a resident record, so an officer must confirm eligibility.'
            : 'या योजनेच्या काही अटी नोंदीवरून तपासता येत नाहीत; अधिकाऱ्याने पात्रता निश्चित करावी.'}
        </span>
      </li>
    )}
  </ul>
);

// ─── Small layout helpers ───────────────────────────────────────────────────

export const EmptyState: React.FC<{ title: string; hint?: string }> = ({ title, hint }) => (
  <div className="border border-dashed border-slate-300 rounded-xl p-10 text-center bg-white">
    <p className="text-sm font-bold text-slate-600 m-0">{title}</p>
    {hint && <p className="text-xs text-slate-400 mt-1.5 m-0">{hint}</p>}
  </div>
);

export const ErrorNotice: React.FC<{ message: string; onRetry?: () => void }> = ({
  message,
  onRetry,
}) => (
  <div
    role="alert"
    className="border border-rose-200 bg-rose-50 rounded-xl p-4 flex items-start justify-between gap-4"
  >
    <p className="text-xs text-rose-800 font-semibold m-0 leading-relaxed">{message}</p>
    {onRetry && (
      <button
        onClick={onRetry}
        className="text-xs font-bold text-rose-800 underline hover:no-underline flex-shrink-0"
      >
        Try again
      </button>
    )}
  </div>
);
