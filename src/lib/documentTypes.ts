/**
 * Document types a resident can keep in their Digital Locker, grouped the way
 * DigiLocker groups them. The server matches uploads to scheme requirements by
 * document family, so naming a file here is enough for it to count towards
 * every scheme that accepts it. "Other" lets a resident name anything else.
 */

export interface DocType {
  en: string;
  mr: string;
}

export const DOC_GROUPS: { en: string; mr: string; types: DocType[] }[] = [
  {
    en: 'Identity',
    mr: 'ओळख',
    types: [
      { en: 'Aadhaar Card', mr: 'आधार कार्ड' },
      { en: 'PAN Card', mr: 'पॅन कार्ड' },
      { en: 'Voter ID', mr: 'मतदार ओळखपत्र' },
      { en: 'Passport', mr: 'पासपोर्ट' },
      { en: 'Driving Licence', mr: 'वाहन चालक परवाना' },
      { en: 'Passport-size Photograph', mr: 'पासपोर्ट आकाराचे छायाचित्र' },
    ],
  },
  {
    en: 'Family & household',
    mr: 'कुटुंब',
    types: [
      { en: 'Ration Card', mr: 'रेशन कार्ड' },
      { en: 'BPL Certificate', mr: 'दारिद्र्यरेषेखालील दाखला' },
      { en: 'Birth Certificate', mr: 'जन्म दाखला' },
      { en: 'Marriage Certificate', mr: 'विवाह प्रमाणपत्र' },
      { en: 'Death Certificate', mr: 'मृत्यू दाखला' },
      { en: 'SECC-2011 List Entry', mr: 'एसईसीसी-२०११ यादीतील नोंद' },
    ],
  },
  {
    en: 'Certificates',
    mr: 'दाखले',
    types: [
      { en: 'Income Certificate', mr: 'उत्पन्नाचा दाखला' },
      { en: 'Caste Certificate', mr: 'जातीचा दाखला' },
      { en: 'Domicile Certificate', mr: 'अधिवास प्रमाणपत्र' },
      { en: 'Residence Certificate', mr: 'रहिवासी दाखला' },
      { en: 'Disability Certificate (UDID)', mr: 'अपंगत्व प्रमाणपत्र (UDID)' },
      { en: 'Non-Creamy Layer Certificate', mr: 'नॉन-क्रिमीलेयर प्रमाणपत्र' },
    ],
  },
  {
    en: 'Education',
    mr: 'शिक्षण',
    types: [
      { en: '10th (SSC) Marksheet', mr: '१०वी (SSC) गुणपत्रिका' },
      { en: '12th (HSC) Marksheet', mr: '१२वी (HSC) गुणपत्रिका' },
      { en: 'Diploma Certificate', mr: 'पदविका प्रमाणपत्र' },
      { en: 'Degree Certificate', mr: 'पदवी प्रमाणपत्र' },
      { en: 'School Leaving Certificate', mr: 'शाळा सोडल्याचा दाखला' },
      { en: 'Bonafide Certificate', mr: 'बोनाफाईड प्रमाणपत्र' },
    ],
  },
  {
    en: 'Land & property',
    mr: 'जमीन व मालमत्ता',
    types: [
      { en: '7/12 Land Extract', mr: '७/१२ उतारा' },
      { en: '8-A Land Extract', mr: '८-अ उतारा' },
      { en: 'Property Tax Receipt', mr: 'मालमत्ता कर पावती' },
      { en: 'Electricity Bill', mr: 'वीज बिल' },
    ],
  },
  {
    en: 'Bank & health',
    mr: 'बँक व आरोग्य',
    types: [
      { en: 'Bank Passbook', mr: 'बँक पासबुक' },
      { en: 'Cancelled Cheque', mr: 'रद्द धनादेश' },
      { en: 'Ayushman Bharat / MJPJAY Card', mr: 'आयुष्मान भारत / MJPJAY कार्ड' },
      { en: 'MGNREGA Job Card', mr: 'मनरेगा जॉब कार्ड' },
    ],
  },
];

export const ALL_DOC_TYPES: DocType[] = DOC_GROUPS.flatMap((g) => g.types);

/** The Marathi name for a known type, or the English name for a custom one. */
export const marathiFor = (en: string): string =>
  ALL_DOC_TYPES.find((d) => d.en === en)?.mr ?? en;
