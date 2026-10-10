# -*- coding: utf-8 -*-
"""Content of the E-Panchayat IEEE manuscript, version 18.

Inline markup understood by build_docx.py:
  [@key]      citation; numbered in order of first appearance
  [@a,@b]     several citations
  *text*      italic
  **text**    bold
  `text`      monospace
Block types: title, authors, affil, emails, abstract, keywords, h1, h2, p,
eq, algo, fig, table, refs, bullets.
"""

TITLE = ("E-Panchayat: A Privacy-Aware, AI-Assisted Decision Support System "
         "for Gram Panchayat Administration in India")
AUTHORS = "Honey Soni, Poornima Rayavarapu, Sujal Jadhavar, and Jyoti Gavhane"
AFFIL = "School of Computing, MIT ADT University, Pune 412201, Maharashtra, India"
EMAILS = ("honeysoni321@gmail.com, rayavarapupoornima4@gmail.com, "
          "sujalj9146@gmail.com, jyoti.gavhane@mituniversity.edu.in")

ABSTRACT = (
    "Gram Panchayats in India decide which residents qualify for central and state welfare "
    "schemes and track the development works residents ask for, yet the national platforms "
    "that serve them mainly record decisions rather than help an office reach them. This "
    "paper describes E-Panchayat, a research prototype that keeps two kinds of reasoning "
    "apart. Welfare eligibility is assessed by a deterministic rule engine over "
    "machine-readable scheme criteria, using three-valued logic so that a missing attribute "
    "leads to officer review instead of refusal; no language model takes part in that "
    "decision. Complaints in English and Marathi are classified and grouped by transparent "
    "keyword rules, and one record links a resident's request to verification, approval, "
    "officer-entered budget figures, implementation and the resulting asset. A "
    "retrieval-augmented assistant answers questions over the Panchayat records the asker "
    "is permitted to see. Three controls limit what reaches the external model provider: "
    "resident records are excluded from the retrieval index, questions containing a recorded "
    "resident name are answered without an external call, and generation is withheld when "
    "retrieved facts are classified as personal. Other question text is still sent to the "
    "provider, so a resident described by attributes rather than named is not protected. The "
    "prototype uses public administrative data for 23 villages of Haveli taluka, Pune "
    "district (coordinates verified for 18), 29 encoded schemes and a synthetic ten-person "
    "register, and has not been deployed in any Panchayat. On author-constructed benchmarks "
    "the classifier reaches 0.732 accuracy on 71 complaints, and embedding retrieval with "
    "link following reaches a mean reciprocal rank of 0.929 on 26 questions. Only 11 of the "
    "29 schemes were checked in detail against published sources, and none has been "
    "confirmed by an administering officer."
)
KEYWORDS = ("E-governance, Gram Panchayat, retrieval-augmented generation, rule-based "
            "decision systems, data privacy, rural digital administration")

# Reference list. Order here is irrelevant: numbers follow first citation.
REFS = {
    "const": 'Government of India, "The Constitution of India, Eleventh Schedule (Article 243G)," Ministry of Law and Justice. [Online]. Available: https://legislative.gov.in/constitution-of-india. Accessed: Oct. 9, 2026.',
    "secc": 'Ministry of Rural Development, "Socio Economic and Caste Census 2011," Government of India. [Online]. Available: https://rural.gov.in. Accessed: Oct. 9, 2026.',
    "niradhar": 'Department of Social Justice and Special Assistance, "Sanjay Gandhi Niradhar Anudan Yojana," Government of Maharashtra. [Online]. Available: https://sjsa.maharashtra.gov.in. Accessed: Oct. 9, 2026.',
    "pmayg": 'Ministry of Rural Development, "Pradhan Mantri Awaas Yojana–Gramin (PMAY-G)," Government of India. [Online]. Available: https://pmayg.nic.in',
    "sbm": 'Department of Drinking Water and Sanitation, "Swachh Bharat Mission (Gramin)," Government of India. [Online]. Available: https://swachhbharatmission.gov.in. Accessed: Oct. 9, 2026.',
    "mjpjay": 'State Health Assurance Society, Public Health Department, "Mahatma Jyotirao Phule Jan Arogya Yojana," Government of Maharashtra. [Online]. Available: https://www.jeevandayee.gov.in',
    "ji": 'Z. Ji et al., "Survey of hallucination in natural language generation," *ACM Comput. Surveys*, vol. 55, no. 12, Art. no. 248, pp. 1–38, 2023, doi: 10.1145/3571730.',
    "carlini": 'N. Carlini et al., "Extracting training data from large language models," in *Proc. 30th USENIX Security Symp.*, 2021, pp. 2633–2650.',
    "rudin": 'C. Rudin, "Stop explaining black box machine learning models for high stakes decisions and use interpretable models instead," *Nature Mach. Intell.*, vol. 1, no. 5, pp. 206–215, 2019, doi: 10.1038/s42256-019-0048-x.',
    "egs": 'Ministry of Panchayati Raj, "e-GramSwaraj: work based accounting application for Panchayati Raj," Government of India. [Online]. Available: https://egramswaraj.gov.in. Accessed: Oct. 9, 2026.',
    "gm": 'Ministry of Panchayati Raj, "Gram Manchitra: spatial planning application for Gram Panchayats," Government of India. [Online]. Available: https://grammanchitra.gov.in. Accessed: Oct. 9, 2026.',
    "sp": 'National Informatics Centre, "ServicePlus: metadata-based e-service delivery framework," Government of India. [Online]. Available: https://serviceonline.gov.in. Accessed: Oct. 9, 2026.',
    "csc": 'Ministry of Electronics and Information Technology, "Common Services Centres scheme," Government of India. [Online]. Available: https://www.csc.gov.in. Accessed: Oct. 9, 2026.',
    "umang": 'Ministry of Electronics and Information Technology, "UMANG: Unified Mobile Application for New-age Governance," Government of India. [Online]. Available: https://web.umang.gov.in. Accessed: Oct. 9, 2026.',
    "digilocker": 'Ministry of Electronics and Information Technology, "DigiLocker," Government of India. [Online]. Available: https://www.digilocker.gov.in. Accessed: Oct. 9, 2026.',
    "heeks02": 'R. Heeks, "Information systems and developing countries: Failure, success, and local improvisations," *The Information Society*, vol. 18, no. 2, pp. 101–112, 2002, doi: 10.1080/01972240290075039.',
    "heeks03": 'R. Heeks, "Most eGovernment-for-development projects fail: How can risks be reduced?" iGovernment Working Paper no. 14, Inst. Develop. Policy Manage., Univ. Manchester, Manchester, U.K., 2003.',
    "lewis": 'P. Lewis et al., "Retrieval-augmented generation for knowledge-intensive NLP tasks," in *Proc. Adv. Neural Inf. Process. Syst. (NeurIPS)*, vol. 33, 2020, pp. 9459–9474.',
    "edge": 'D. Edge et al., "From local to global: A graph RAG approach to query-focused summarization," 2024, *arXiv:2404.16130*.',
    "kisan": 'Ministry of Agriculture and Farmers Welfare, "Kisan e-Mitra: AI chatbot for the PM-KISAN scheme," Press Information Bureau, Government of India, release ID 1959461, Sep. 2023. [Online]. Available: https://pib.gov.in/PressReleasePage.aspx?PRID=1959461. Accessed: Oct. 9, 2026.',
    "kumar": 'R. Kumar and M. L. Best, "Impact and sustainability of e-government services in developing countries: Lessons learned from Tamil Nadu, India," *The Information Society*, vol. 22, no. 1, pp. 1–12, 2006, doi: 10.1080/01972240500388149.',
    "madon": 'S. Madon, "Evaluating the developmental impact of e-governance initiatives: An exploratory framework," *Electron. J. Inf. Syst. Develop. Countries*, vol. 20, no. 5, pp. 1–13, 2004.',
    "tam": 'V. Venkatesh and F. D. Davis, "A theoretical extension of the technology acceptance model: Four longitudinal field studies," *Manage. Sci.*, vol. 46, no. 2, pp. 186–204, 2000, doi: 10.1287/mnsc.46.2.186.11926.',
    "sweeney": 'L. Sweeney, "k-anonymity: A model for protecting privacy," *Int. J. Uncertainty, Fuzziness Knowl.-Based Syst.*, vol. 10, no. 5, pp. 557–570, 2002, doi: 10.1142/S0218488502001648.',
    "narayanan": 'A. Narayanan and V. Shmatikov, "Robust de-anonymization of large sparse datasets," in *Proc. IEEE Symp. Security Privacy*, 2008, pp. 111–125, doi: 10.1109/SP.2008.33.',
    "gemini": 'Google, "Gemini API documentation: Embeddings and text generation." [Online]. Available: https://ai.google.dev/gemini-api/docs',
    "goodman": 'B. Goodman and S. Flaxman, "European Union regulations on algorithmic decision-making and a ‘right to explanation’," *AI Mag.*, vol. 38, no. 3, pp. 50–57, 2017, doi: 10.1609/aimag.v38i3.2741.',
    "dpr": 'V. Karpukhin et al., "Dense passage retrieval for open-domain question answering," in *Proc. Conf. Empirical Methods Natural Lang. Process. (EMNLP)*, 2020, pp. 6769–6781.',
    "gpdp": 'Ministry of Panchayati Raj, "People’s Plan Campaign and Gram Panchayat Development Plan," Government of India. [Online]. Available: https://panchayat.gov.in. Accessed: Oct. 9, 2026.',
    "osm": 'OpenStreetMap contributors, "OpenStreetMap." [Online]. Available: https://www.openstreetmap.org. Accessed: Oct. 9, 2026.',
    "lgd": 'Ministry of Panchayati Raj, "Local Government Directory," Government of India. [Online]. Available: https://lgdirectory.gov.in. Accessed: Oct. 9, 2026.',
    "census": 'Office of the Registrar General and Census Commissioner, "Census of India 2011," Government of India. [Online]. Available: https://censusindia.gov.in. Accessed: Oct. 9, 2026.',
    "nmmss": 'Department of School Education and Literacy, Ministry of Education, "National Means-cum-Merit Scholarship Scheme (NMMSS)," Government of India. [Online]. Available: https://dsel.education.gov.in/scheme/nmmss',
    "nsap": 'Ministry of Rural Development, "National Social Assistance Programme (NSAP)," Government of India. [Online]. Available: https://nsap.nic.in',
    "bhashini": 'Ministry of Electronics and Information Technology, "Bhashini: National Language Translation Mission," Government of India. [Online]. Available: https://bhashini.gov.in. Accessed: Oct. 9, 2026.',
    "uidai": 'Unique Identification Authority of India, "Aadhaar," Government of India. [Online]. Available: https://uidai.gov.in. Accessed: Oct. 9, 2026.',
}

T1 = {
    "caption": "Table 1. Existing systems and research, and what each leaves for this work",
    "wide": True,
    "widths": [1.25, 0.55, 1.75, 1.85, 1.85],
    "header": ["Work", "Year", "What it does well", "What it does not do (as documented)", "What E-Panchayat adds"],
    "rows": [
        ["e-GramSwaraj [@egs]", "2020", "Planning, accounting, work progress, audit and payments for Panchayats nationwide", "Published description does not cover citizen grievances or individual scheme eligibility", "Assesses eligibility from encoded scheme rules and reports the rule that decided"],
        ["Gram Manchitra [@gm]", "2019", "GIS planning; geo-tagged assets with physical and financial progress", "Officer-facing planning; a citizen complaint is not an input", "Lets a resident's complaint become the origin of a work and links it to the asset"],
        ["ServicePlus [@sp]", "2015", "States publish service forms and approval chains online", "Processes an application once filed; does not assess eligibility beforehand", "Classifies a complaint and routes it to a department"],
        ["CSC, UMANG, DigiLocker [@csc], [@umang], [@digilocker]", "2006–2017", "Access to services by kiosk or phone; issuance of verified documents", "Provide access and documents, not eligibility decisions", "Uses officer-verified document status as an input to the eligibility check"],
        ["Heeks [@heeks02], [@heeks03]", "2002, 2003", "Explains e-government failure through design–reality gaps", "Diagnostic; does not build a system", "Assumes counter-based operation, e.g., officer-issued password reset, not reliable email or SMS"],
        ["Rudin [@rudin]", "2019", "Argues for interpretable models in high-stakes decisions", "A general argument, not a system", "Applies encoded welfare rules directly instead of predicting outcomes"],
        ["Lewis et al. [@lewis]", "2020", "Grounds generation in documents retrieved at query time", "Does not address what indexing itself discloses", "Excludes resident records from the index; withholds generation for personal facts"],
        ["Edge et al. [@edge]", "2024", "Uses relations between records for retrieval and summarisation", "Assumes the whole corpus can be sent for indexing", "Follows recorded links only within the asker's permitted scope"],
        ["Kisan e-Mitra [@kisan]", "2023", "Answers PM-KISAN beneficiaries' questions in several Indian languages", "Public descriptions reviewed do not document a comparable resident-level data boundary", "States its boundary, enforces it at three points in code, and reports what can still cross it"],
    ],
}

T2 = {
    "caption": "Table 2. Dataset composition. Village and scheme data are public and cited; all resident-level data are synthetic",
    "wide": False,
    "widths": [1.95, 0.55, 0.95],
    "header": ["Data type", "Count", "Provenance"],
    "rows": [
        ["Villages in Haveli taluka", "23", "LGD, Census 2011 [@lgd], [@census]"],
        [" of which with verified coordinates", "18", "As above; OSM [@osm]"],
        ["Welfare schemes with encoded criteria", "29", "Published central and state sources"],
        ["Resident records", "10", "Synthetic"],
        ["Households (one recorded head each)", "5", "Synthetic"],
        ["Supporting documents held against residents", "30", "Synthetic"],
        ["Grievances in the implementation dataset (5 service, 10 development)", "15", "Synthetic"],
        [" of which linked to a development work", "7", "Synthetic"],
        ["Development works", "6", "Synthetic"],
        ["Budget ledger entries across those works", "20", "Synthetic"],
        ["Public facilities", "5", "Synthetic"],
        ["Gram Sabha meetings", "1", "Synthetic"],
        ["Indexed knowledge records (chunks)", "79", "Derived from rows above"],
        ["Complaint benchmark cases (separate from the 15 grievances)", "71", "Author-constructed"],
        ["Retrieval benchmark questions", "26", "Author-constructed"],
        ["Automated regression tests (evaluated version)", "634", "Project repository"],
    ],
}

T3 = {
    "caption": "Table 3. Distribution of rule-engine verdicts over all 290 resident–scheme pairs of the synthetic register. This is a distribution, not an accuracy measure: no independently established expected verdicts exist",
    "wide": False,
    "widths": [1.05, 0.45, 0.5, 1.45],
    "header": ["Verdict", "Pairs", "Share", "Meaning"],
    "rows": [
        ["Ineligible", "180", "62.1%", "A recorded fact fails a condition"],
        ["Missing Documents", "64", "22.1%", "Conditions pass; a required document is absent or unverified"],
        ["Needs Review", "37", "12.8%", "Outcome Unknown or scheme flagged for officer review"],
        ["Eligible", "9", "3.1%", "Conditions pass; every required document verified"],
        ["Total", "290", "100.0%", ""],
    ],
}

T4 = {
    "caption": "Table 4. Rule-based complaint classification on 71 author-constructed complaints. Category accuracy 0.732 (52/71), macro-F1 0.734. TP, FN and FP are derived from the reported precision, recall and support",
    "wide": False,
    "widths": [0.95, 0.42, 0.5, 0.45, 0.4, 0.27, 0.27, 0.27],
    "header": ["Class", "Supp.", "Prec.", "Rec.", "F1", "TP", "FN", "FP"],
    "rows": [
        ["Water", "17", "0.824", "0.824", "0.824", "14", "3", "3"],
        ["Sanitation", "13", "0.900", "0.692", "0.783", "9", "4", "1"],
        ["Roads", "11", "0.700", "0.636", "0.667", "7", "4", "3"],
        ["Electricity", "13", "1.000", "0.615", "0.762", "8", "5", "0"],
        ["Health", "9", "1.000", "0.667", "0.800", "6", "3", "0"],
        ["Other", "8", "0.400", "1.000", "0.571", "8", "0", "12"],
        ["Macro average", "71", "0.804", "0.739", "0.734", "52", "19", "19"],
    ],
    "note": "Request type (service or development) was correct for 70 of 71 complaints (accuracy 0.986); v17 listed this figure in the F1 column.",
}

T5 = {
    "caption": "Table 5. Retrieval over 79 indexed records for 26 author-constructed questions. Higher is better in every column except the last",
    "wide": True,
    "widths": [2.0, 0.75, 0.75, 0.75, 0.8, 0.95, 1.0],
    "header": ["Retrieval condition", "P@3", "P@5", "R@5", "MRR", "Found overall", "Records sent to model"],
    "rows": [
        ["Keyword search (TF-IDF)", "0.410", "0.308", "0.865", "0.840", "0.865", "4.62"],
        ["Embedding similarity", "0.526", "0.338", "0.904", "0.923", "0.904", "3.62"],
        ["Embedding similarity + link following", "0.526", "0.338", "0.904", "0.929", "0.949", "4.58"],
    ],
}

T6 = {
    "caption": "Table 6. Scope test: the same 26 questions issued under each role, counting retrieved records outside the asker's authority. A bounded result for these queries, not a general security guarantee",
    "wide": False,
    "widths": [1.35, 0.5, 0.6, 0.55, 0.5],
    "header": ["Role", "Queries", "Returned", "In scope", "Out of scope"],
    "rows": [
        ["Citizen", "26", "106", "106", "0"],
        ["Officer, own village", "26", "119", "119", "0"],
        ["Officer, neighbouring village", "26", "47", "47", "0"],
        ["Block administrator", "26", "123", "123", "0"],
    ],
}

T7 = {
    "caption": "Table 7. Synthetic end-to-end case: twenty streetlights, Market Road to Vitthal temple, ward 2. Not a real project, grant or payment",
    "wide": False,
    "widths": [1.45, 2.0],
    "header": ["Stage", "Recorded value"],
    "rows": [
        ["Residents reporting the problem", "5 complaints from 5 distinct residents"],
        ["Classification", "Development request; quantity 20 read from text"],
        ["Priority after grouping", "High, raised on resident count alone"],
        ["Verified, then approved", "Officer decisions, each with a recorded reason"],
        ["Estimate and amount requested", "₹4,00,000"],
        ["Budget approved", "₹3,50,000 (funding-source label: Central Finance Commission grant)"],
        ["Funds received (officer-recorded)", "₹3,50,000"],
        ["Spent to date (officer-recorded)", "₹2,80,000 across two entries"],
        ["Physical progress", "14 of 20 units installed = 70%"],
        ["Financial progress", "₹2,80,000 / ₹3,50,000 approved = 80%"],
        ["On completion", "Streetlight asset added to the register and map"],
    ],
}

T8 = {
    "caption": "Table 8. Physical against financial progress for the six synthetic works. Variance = financial − physical (percentage points); a positive gap is a prompt for review, not a finding of wrongdoing",
    "wide": False,
    "widths": [1.7, 0.6, 0.6, 0.55],
    "header": ["Work (synthetic)", "Physical", "Financial", "Variance"],
    "rows": [
        ["Water tank and pipeline", "45%", "63%", "+18"],
        ["20 streetlights, Market Road", "70%", "80%", "+10"],
        ["School boundary wall and classroom", "90%", "97%", "+7"],
        ["Village concrete road", "68%", "72%", "+4"],
        ["Gram Panchayat digital centre", "100%", "99%", "−1"],
        ["3 public water tap stands", "0%", "0%", "0"],
    ],
}

TA1 = {
    "caption": "Table A1. Encoded criteria and verification status of the 29 schemes. “Checked” = corrected after a source check reported in Section V-C and re-confirmed against a public source in this revision; “Review” = engine never returns Eligible and refers every non-failing case to an officer; “Not re-verified” = encoded from published material, not checked again for this revision. The manuscript does not record which eight further schemes made up the eleven checked in detail; no scheme has been confirmed by an administering officer. Source: GR = Maharashtra Government Resolution consulted but not individually cited; \u2014 = no source cited in the manuscript",
    "wide": True,
    "font": 6.5,
    "widths": [1.55, 1.85, 0.75, 0.75, 2.1],
    "header": ["Scheme (level)", "Encoded criteria (summary)", "Source", "Status", "Outstanding issue"],
    "rows": [
        ["Sanjay Gandhi Niradhar Anudan (state)", "Age 18–65; income ≤ ₹21,000 OR BPL OR (disability route, income ≤ ₹50,000)", "[@niradhar]", "Checked", "Sources disagree on the age ceiling (“below 65” vs. “18–65”); cases at age 65 need officer review, not yet enforced"],
        ["Shravan Bal Seva Nivruttivetan (state)", "Age ≥ 65; income ≤ ₹21,000 OR BPL", "[@niradhar]", "Not re-verified", "Boundary with Niradhar at age 65 depends on the unresolved rule above"],
        ["Ramai Awas (state)", "SC / Neo-Buddhist; income ≤ ₹1,20,000", "GR", "Not re-verified", "Income ceiling and rural/urban variants to be confirmed"],
        ["MJPJAY (state)", "Ration card Yellow, Orange, AAY or Annapurna", "[@mjpjay]", "Not re-verified", "Possible later expansion of coverage to further card types to be checked"],
        ["Shabari Awas (state)", "ST; income ≤ ₹1,20,000", "GR", "Not re-verified", "Domicile and housing conditions not encoded"],
        ["SBM-G toilet incentive (central)", "BPL OR SC/ST OR small farmer (≤ 2 ha) OR disability ≥ 40%", "[@sbm]", "Not re-verified", "Other eligible APL groups (e.g., landless labourers, women-headed households) not encoded"],
        ["Sukanya Samriddhi (central)", "Girl, age ≤ 10", "—", "Not re-verified", "Account opened by guardian; applicant/beneficiary distinction"],
        ["PMJJBY (central)", "Age 18–50", "—", "Not re-verified", "Bank-account requirement treated as document"],
        ["PMFBY (central)", "Occupation farmer/cultivator", "—", "Not re-verified", "Crop and season conditions not encoded"],
        ["PM Ujjwala (central)", "Woman ≥ 18; BPL OR SC/ST", "—", "Not re-verified", "Later eligibility categories broader than encoded subset"],
        ["PMAY-G (central)", "SECC-2011 deprivation listing", "[@pmayg]", "Not re-verified", "Later survey lists not represented"],
        ["PMMVY (central)", "Woman 18–49", "—", "Review", "Child-order condition cannot be read from register"],
        ["AB-PMJAY (central)", "SECC-2011 listing", "—", "Not re-verified", "Later expansions (e.g., age-based coverage) not encoded"],
        ["Saur Krushi Pump (state)", "Occupation farmer", "GR", "Review", "Landholding bands and water source need officer check"],
        ["PM-KISAN (central)", "Farmer with land > 0", "—", "Not re-verified", "Exclusion categories (e.g., income-tax payers) not encoded"],
        ["Lek Ladki (state)", "Girl; income ≤ ₹1,00,000; Yellow/Orange card", "GR", "Review", "Birth-date condition cannot be read from register"],
        ["Namo Shetkari (state)", "Occupation farmer", "GR", "Not re-verified", "Depends on PM-KISAN enrolment, not encoded"],
        ["Majhi Ladki Bahin (state)", "Woman 21–65; income ≤ ₹2,50,000; listed marital statuses", "GR", "Not re-verified", "Per-household limit on unmarried women not encoded"],
        ["IGNOAPS (central)", "Age ≥ 60; BPL", "[@nsap]", "Not re-verified", "—"],
        ["IGNWPS (central)", "Widow, age 40–79; BPL", "[@nsap]", "Not re-verified", "—"],
        ["IGNDPS (central)", "Age 18–79; disability ≥ 80%; BPL", "[@nsap]", "Checked", "Earlier encoding used 40%; corrected"],
        ["NFBS (central)", "BPL", "[@nsap]", "Review", "Age condition concerns the deceased breadwinner"],
        ["MGNREGA / successor (central)", "Age ≥ 18", "—", "Not re-verified", "Programme status to be confirmed"],
        ["NMMSS (central)", "Parental income ≤ ₹3,50,000; age 13–18 (proxy)", "[@nmmss]", "Checked; Review", "Ceiling corrected from ₹1,50,000; class and marks conditions need officer check"],
        ["Disability pension top-up (state)", "Age 18–79", "GR", "Review", "Disability threshold to be aligned with IGNDPS"],
        ["Widow pension top-up (state)", "Widow, age 40–79; BPL", "GR", "Not re-verified", "—"],
        ["EBC fee reimbursement (state)", "Open/SEBC; income ≤ ₹8,00,000", "GR", "Review", "Course and admission conditions"],
        ["Post-Matric Scholarship, SC (state)", "SC; income ≤ ₹2,50,000", "—", "Not re-verified", "Enrolment conditions"],
        ["Birsa Munda Krishi Kranti (state)", "ST farmer; land 0.4–6.0 ha", "GR", "Not re-verified", "Land bounds to be confirmed"],
    ],
}

ALGO = [
    "**Algorithm 1.** EligibilityAssessment(*R*, σ)",
    "1:  **function** Eval(*n*, *R*)",
    "2:    **if** *n* is a leaf κ **then**",
    "3:      **if** *a*(κ) not recorded in *R* **then** *v* ← U",
    "4:      **else if** *R* satisfies κ **then** *v* ← P **else** *v* ← F",
    "5:    **else**  ▷ group node",
    "6:      *V* ← { Eval(*c*, *R*) : *c* ∈ children(*n*) }",
    "7:      **if** *n* is AND **then** *v* ← min *V* **else** *v* ← max *V*",
    "8:    **if** *m*(*n*) **then** *v* ← min(*v*, U)   ▷ F < U < P",
    "9:    **return** *v*",
    "10: *v* ← Eval(*C*σ, *R*);  Δ ← Req(σ) \\ Ver(*R*)",
    "11: **if** *v* = F **then return** Ineligible(failed leaves)",
    "12: **if** *v* = U **then return** NeedsReview(unknown leaves, flags, Δ)",
    "13: **if** Δ ≠ ∅ **then return** MissingDocuments(Δ)",
    "14: **return** Eligible",
]

BODY = [
    ("h1", "Introduction"),
    ("p", "Panchayati Raj has three tiers, and the Gram Panchayat at the bottom carries most of the routine administrative load. It keeps the resident register, determines entitlement under central and state welfare schemes, records grievances, tracks the works sanctioned for the village and keeps the minutes of the Gram Sabha. The Eleventh Schedule of the Constitution lists twenty-nine subjects that states may devolve to Panchayats [@const]; the technical capacity transferred with those subjects has usually been much smaller."),
    ("p", "National platforms, reviewed in Section II, now support planning, accounting, work progress and the mapping of sanctioned assets. Their emphasis is on recording what an office has decided. They are not designed to help the clerk at the counter reach that decision, and the decision is harder than it looks. Whether a woman qualifies for a pension may depend on her age, income, social category, marital status and landholding, on whether she is on the Below Poverty Line (BPL) list, on her household's listing in the Socio Economic and Caste Census 2011 [@secc], and on which documents in her file have been verified. Each scheme reads its own subset of these attributes in its own way. Sanjay Gandhi Niradhar Anudan Yojana accepts an income ceiling or BPL membership as alternatives [@niradhar]; Pradhan Mantri Awaas Yojana–Gramin (PMAY-G) uses SECC deprivation criteria rather than an income test [@pmayg]; the Swachh Bharat Mission (Gramin) toilet incentive admits several alternative routes [@sbm]; and Mahatma Jyotirao Phule Jan Arogya Yojana (MJPJAY) depends largely on ration-card colour [@mjpjay]."),
    ("p", "A second gap lies between complaints and development. A resident reporting that a lane has gone dark is making a service request, which a repair closes. A resident asking for twenty more streetlights is doing something else: stating a need that has to be verified, approved, estimated, funded and built. Systems that treat both as tickets tend to lose the second kind, and with it the connection between what residents asked for and what was eventually sanctioned, paid for and installed."),
    ("p", "Language models are increasingly proposed for this kind of work, often by placing an applicant's record in a prompt and asking whether the person qualifies. We argue against that design for entitlement decisions. Generative models can produce fluent statements that the evidence does not support, especially where evidence is thin [@ji], and an invented entitlement is a serious error when it decides whether a widow's pension starts. Models have also been shown to memorise training data and, under suitable prompting, reproduce it [@carlini]. Where a hosted service's terms permit submitted content to be used for product improvement, sending a resident's record to it creates an exposure that outlasts the request."),
    ("p", "E-Panchayat rests on the position that entitlement adjudication and natural-language assistance can be separated, and that separating them makes each easier to inspect. The paper contributes: (i) a three-valued eligibility model and rule engine over published scheme criteria, following the argument that consequential decisions should use models that are interpretable by construction [@rudin]; (ii) a retrieval-augmented assistant with three code-level controls on what reaches an external provider, together with an explicit account of what those controls leave uncovered; (iii) a work lifecycle linking a resident's request to verification, sanction, officer-recorded funds and the resulting asset; and (iv) an evaluation on synthetic and author-constructed data that separates what was measured from what remains unvalidated. Section II positions the work, Section III presents the design and formal model, Section IV the implementation and Section V the evaluation. Section VI discusses threats to validity, and Sections VII and VIII conclude."),

    ("h1", "Related Work"),
    ("p", "Table 1 places the most relevant systems and studies against three questions: what each contributes, what it leaves open, and where the present system differs. The comparison concerns orientation, not quality. The national platforms carry statutory functions at a scale this prototype does not approach, and the middle column is limited to what their published descriptions document as reviewed for this paper; it is not a claim about every feature those platforms offer."),
    ("table", T1),
    ("p", "Studies of rural e-government in India find that systems survive or fail on local institutional support more than on the technology [@kumar], [@madon]. Technology-acceptance research supplies the other half of the account: sustained use depends on how useful a system is to the person obliged to operate it [@tam]. A separate strand concerns what retrieval discloses. Building a search index means embedding an entire collection, and embedding through a hosted service means sending that collection to the provider whether or not anyone ever asks a question. Removing names is weaker protection than it appears. Work on quasi-identifiers [@sweeney] and the de-anonymisation results that followed [@narayanan] show that ordinary attributes become identifying in combination; in a settlement of a few hundred households, a widowed agricultural labourer of fifty-two in ward three may be exactly one woman. Taken together, the platforms record decisions without helping to reach them, and the retrieval literature grounds answers without asking what the grounding discloses. Section III sets out a design that addresses both."),

    ("h1", "System Design and Formal Model"),
    ("h2", "Architecture and Data Flows"),
    ("p", "Fig. 1 shows the layered architecture. A React client calls a FastAPI service over HTTPS, each request carrying a signed token. Role and village checks are declared as dependencies in each route's signature rather than written inside its body, so a route without one is visibly public during review. Business logic sits in a service layer independent of the routers, and a single module performs every call to the external model provider, the Google Gemini API, which is used for both embedding and generation [@gemini]. Having one exit point is what makes the boundary auditable: there is one place to inspect."),
    ("fig", {"file": "fig1_architecture.png", "width": 3.3,
             "caption": "Fig. 1. Layered architecture and data flows. The dashed line marks the boundary with the external provider. Resident rows, eligibility verdicts and document files are kept inside by design. Indexed non-resident records, question text (unless the name screen fires) and prompts built from non-personal records do cross; Section III-E sets out what this leaves exposed."}),
    ("p", "The privacy argument differs depending on where data sits or travels, so we separate five locations. (1) The *database* holds everything, including resident records, documents and ledger entries; it is a managed PostgreSQL instance, and its protection is a hosting question outside the model-provider boundary. (2) The *retrieval index* holds embedded text for villages, schemes, complaints, works, facilities and Gram Sabha meetings, but no resident records; building it sends the text of each indexed record to the provider. (3) *Question text* is sent to the provider for embedding unless the name screen of Section III-E intercepts it. (4) *Retrieved context* is assembled locally from scoped records. (5) The *generation prompt*, sent only when no retrieved fact is personal, contains the system instructions, the retrieved non-personal records and the question verbatim. The provider therefore receives question text and non-personal record text. It does not receive resident rows, eligibility verdicts or the documents in a resident's file. Complaint records omit the complainant's name, but their titles and descriptions are free text written by residents and are embedded as written."),

    ("h2", "Access Control and Scoping"),
    ("p", "Three roles are supported. A block administrator sees every village in the block; a Gram Panchayat officer sees one village; a citizen sees public village information together with their own record, documents and complaints. Let Scope(*u*) be the set of villages user *u* may see. Before any ranking, a query *Q* over table *X* is restricted to"),
    ("eq", ("Q′ = Q ∩ { x ∈ X : village(x) ∈ Scope(u) }", "1")),
    ("p", "For a citizen, a further filter keeps only public record types (village, scheme, work, facility, meeting) and the citizen's own complaints. Schemes carry no village and are visible to every role. Link following runs after ranking, but only over records already in the scoped candidate set, so a link cannot reach a record the asker may not see. Routes that take an object identifier check that record's village against Scope(*u*) before returning or changing it, and aggregate (analytics) queries apply the same filter."),
    ("p", "Because the restriction is applied before ranking, a record the user may not see is never a candidate, however closely it matches. Filtering after ranking would leave open the possibility of a near match slipping through. We present this as a design property exercised by the tests of Section V-G, not as proof that every endpoint is correct; the cases not yet covered by tests are listed in Section VI."),

    ("h2", "Eligibility Model"),
    ("p", "Let *R* be a resident record, and let scheme σ carry a criteria tree *C*σ. Its leaves are atomic conditions κ (an age bound, an income ceiling, a category list and so on); its internal nodes are conjunctive (AND) or disjunctive (OR) groups; the root is conjunctive. Every node evaluates to Pass (P), Fail (F) or Unknown (U), ordered F < U < P. A leaf is Unknown when the record does not hold the attribute *a*(κ) that the condition reads:"),
    ("eq", ("v(κ, R) = U   if a(κ) is not recorded in R\n                 P   if R satisfies κ\n                 F   otherwise", "2")),
    ("p", "Groups follow strong Kleene logic, so a conjunctive group takes the minimum of its children and a disjunctive group the maximum:"),
    ("eq", ("v(G∧) = F if any child is F;  P if all are P;  else U", "3")),
    ("eq", ("v(G∨) = P if any child is P;  F if all are F;  else U", "4")),
    ("p", "An alternative route thus passes its group as soon as one route passes, fails it only when every route fails, and leaves it Unknown otherwise. A route that fails on a recorded fact counts as failed even if it also mentions an attribute the record lacks."),
    ("p", "Some conditions cannot be assessed from a resident register at all. The National Family Benefit Scheme's age condition, for instance, describes the deceased breadwinner rather than the applicant. Such a scheme or route carries a manual-review flag *m*, and a flagged node is capped at Unknown:"),
    ("eq", ("v′(n) = min(v(n), U) if m(n);  v(n) otherwise", "5")),
    ("p", "The cap keeps decisive failures decisive. A resident who fails a recorded condition is not referred for review over a question whose answer could not change the outcome; a resident who passes everything the register can show is referred, never approved automatically."),
    ("p", "Documents are kept out of the criterion logic. Let Δ(*R*, σ) = Req(σ) \\ Ver(*R*) be the scheme's required document types not yet verified in the resident's file, both sides mapped to one closed vocabulary of document types. The verdict is"),
    ("eq", ("Status(R, σ) = Ineligible   if v′(Cσ) = F\n         Needs Review   if v′(Cσ) = U\n         Missing Documents   if v′(Cσ) = P, Δ ≠ ∅\n         Eligible   if v′(Cσ) = P, Δ = ∅", "6")),
    ("p", "Δ is also reported alongside a Needs Review verdict so that an officer sees what the file lacks, but a missing document never turns a condition into a failure, and a failed condition is never reported as a paperwork gap. Algorithm 1 implements (2)–(6)."),
    ("algo", ALGO),
    ("p", "Equations (2)–(6) restate the rule of the previous version of this paper in explicitly recursive form and add route-level review flags. For the 29 schemes as encoded, review flags are set only at scheme level, and in the synthetic register income, BPL status, SECC listing, occupation and ward are recorded for every resident; under those conditions the restatement and the earlier rule assign the same verdicts, so Table 3 is unaffected. Where an attribute is absent, an implementation must return Unknown for that leaf rather than substitute a default such as zero income or “not BPL”, since either substitution silently decides the case."),
    ("p", "The engine did not start in this form. Eligibility was first written as a chain of conditionals keyed on each scheme's identifier, so a scheme the chain did not recognise fell through to a bare income test and was reported as if it had been assessed. Moving the rules into a per-scheme criteria dictionary made adding a scheme an insert rather than a code change, and made the unrecognised case impossible. Reading the Government Resolutions then widened the vocabulary well beyond age and income, because few of these schemes decide on those two alone: Ramai Awas is restricted by social category, MJPJAY turns on ration-card colour, Saur Krushi Pump on landholding, and PMAY-G applies no income test. The three-valued design matters because the easy mistake is to treat a missing attribute as a failed one, which quietly refuses benefits to people whose paperwork is merely incomplete. And because the rule is itself the decision, a refused applicant can be told exactly which rule refused them, the kind of explanation discussed in work on algorithmic decision-making [@goodman]."),

    ("h2", "Household Headship"),
    ("p", "Several schemes are written for the head of a household rather than an individual, which obliges the register to record who that is. The question looks clerical and is not. An earlier version carried a boolean flag on each resident, set wherever the data suggested a relative, and it ended up true for nine of the ten seeded residents; one household of three had three heads. The relationship labels were also recorded against whoever had last mentioned that person, so they contradicted one another: a widow's own record named two men as heads of her household and described one of them as her father."),
    ("p", "The replacement stores one thing on the resident's row: how that person is related to the household head, with a reserved value marking the head. Three properties follow. First, a household has at most one head, and the database rather than application code enforces it, through a partial unique index over the household identifier restricted to rows carrying the head value. Second, the system never elects or infers a head or a relationship. The first resident recorded in an empty household becomes its head because there is nobody else to be related to; thereafter the head is whoever the officer records. Changing the head requires the officer to re-enter every remaining member's relation to the new head, since each relation was recorded against the outgoing head and may mean something different against the successor. The system derives none of these labels, on the principle that a register should be told family relationships rather than guess them. For the same reason a head cannot leave a household while other members remain."),
    ("p", "Third, relations are stored without gender, and the displayed word is derived from the person's own recorded gender: the row holds the neutral relation, and the interface renders son or daughter according to that resident's recorded gender, or the neutral word where gender is recorded as neither. The vocabulary stops where a word would require knowing which side of the family a relative belongs to. Marathi distinguishes a husband's brother from a wife's brother and a brother's son from a sister's son, distinctions the register does not hold, so such relations are recorded as *other relative* rather than guessed."),
    ("p", "Headship enters eligibility as one more three-valued condition. A resident whose household has no head on record is not thereby treated as a non-head: refusing her because nobody has yet recorded her household's head would turn a gap in the register into a denial of benefit, the same error as treating a missing document as a failed condition. The condition returns Unknown and the case goes to an officer, but only while the rest of the criteria tree still allows a Pass, in accordance with (3)–(5)."),

    ("h2", "Retrieval and the Three Privacy Controls"),
    ("p", "An earlier assistant matched keywords against a short list of conditional branches and returned pre-written paragraphs with figures substituted in. It could answer nothing its author had not anticipated, and the sources it displayed were decorative. The failure that prompted the redesign was a resident writing that a tap had been dry since Diwali, which shares no word with a record titled as a water-supply interruption. Records are therefore compared with a question by meaning. Both are converted to vectors and compared by cosine similarity, the basis of dense retrieval [@dpr]:"),
    ("eq", ("sim(q, k) = E(q)·E(k) / (‖E(q)‖ ‖E(k)‖)", "7")),
    ("p", "A record is accepted when its score reaches τ = 0.55, and at most six direct matches are kept. The threshold was set by inspecting scores on this corpus, where related texts generally scored above 0.6 and unrelated texts near 0.3, leaving 0.55 in the gap; it has not been validated on any other corpus. A weak match is worse than none, because the model treats whatever it is given as relevant. Each accepted record carries links recorded at indexing time to its village and to the works and complaints it relates to, and up to three linked neighbours per match are appended for context, so that one strong match does not crowd out the records that explain it."),
    ("p", "Three controls then limit what leaves the deployment. Each has a distinct purpose and a distinct gap."),
    ("p", "**Control 1: index exclusion.** Resident-level records are excluded from the retrieval index. Indexing runs over every row whether or not anyone asks a question, so indexing residents would export the register to the provider as a standing cost of the feature. The control covers resident rows and the documents in their files. It does not cover complaint text, which is indexed and may contain whatever a resident chose to write, and it does not cover question text."),
    ("p", "**Control 2: name screen.** Questions containing a detected resident name are screened before external embedding. The question is compared with the names on the register, accepting a full recorded name in its Latin or Devanagari spelling or the first and last parts of one occurring together; a lone given name is not treated as evidence, because a common first name would divert ordinary questions for no reason. A question that matches is answered from the keyword path, which makes no external call. The screen catches names only. It misses spelling and transliteration variants not on the register, nicknames and aliases, and any description that identifies a person without naming them; it may also fire falsely when a name coincides with a place or a common word. Neither error rate has been measured."),
    ("p", "**Control 3: personal-fact gate.** Generation is withheld when the retrieved records contain facts classified as personal. Write Personal(*f*) = 1 for any fact drawn from a single identified resident, such as an eligibility explanation, a document status or a summary of their own record. The prompt is built only when"),
    ("eq", ("Prompt(A′) is constructed  iff  ∀ f ∈ A′ : Personal(f) = 0", "8")),
    ("p", "When the condition fails, the system answers from the same facts using a template and makes no generation call. The gate acts after embedding, so the question has already been sent; and because facts are classified by the code path that produces them, a new path that omits the flag would bypass it, which is why the classification is covered by regression tests."),
    ("p", "The three controls are deliberately redundant, so that no single omission defeats them, but they share one gap, and it should be stated plainly. A question that identifies a resident through attributes, for example asking after the widowed labourer of fifty-two in ward three, names nobody, passes Control 2, and is embedded and possibly sent for generation with its wording intact. The quasi-identifier work of Section II is why this cannot be waved away as a corner case; Section VIII returns to the remedy."),
    ("p", "A fourth property is often mistaken for one of these controls and is worth separating. That adjudication was never the model's job guards no path and blocks no call. It is the architectural decision that makes the three controls affordable: because a verdict is computed before any question is asked, withholding a resident's record from the model costs phrasing rather than the answer. Two of the three controls were added after the fact, and the history is instructive. An earlier indexer did embed resident records, and because excluding them only stops new rows being written, the index had to be rebuilt to clear those already stored. The name screen came later still, from tracing the order in which the checks actually ran and finding that the embedding call came first."),

    ("h2", "Complaint Classification and Grouping"),
    ("p", "Complaints are classified by keyword rules, in English and Marathi, into a category, a priority, a department and a request type. The classifier is a rule set and is described as one throughout. The category is the keyword set with most hits in the text; ties go to the first listed set, and a complaint with no hit falls to Other. Department follows from category through a fixed table. The request type matters most: a *service* request concerns something that exists and has failed, and a repair closes it, while a *development* request concerns something that does not yet exist and must become a work. Where the text states a quantity, as in a request for twenty streetlights, the number is extracted and kept; spelled-out numbers and quantities stated without a unit nearby are not reliably found."),
    ("p", "Complaints about the same problem are grouped by a heuristic: same village, ward, category and request type, both still open, and at least one specific term in common. Nothing is merged and no complaint is deleted, so thirty residents reporting one dark lane keep thirty complaints, each with its own timeline, pointing at one shared work. The rule is conservative by design and will miss requests that describe the same need in different words; its precision and recall have not been measured because no labelled complaint pairs exist."),
    ("p", "Each complaint first receives a baseline priority from escalation terms and category defaults. Grouping can then raise it: three distinct residents raise it one level and five raise it two, capped at High. Critical is reserved for complaints containing danger terms (for example, electrocution, collapse or contamination) and cannot be reached by count alone. The count measures how widely a problem is felt, not how severe it is; one resident reporting a live wire matters more than ten reporting a faded sign. What the rule deliberately ignores is who those residents are. Ranking by the caste, income or disability of the people who filed would put the system's most sensitive fields to work where nobody asked for them."),

    ("h2", "Development-Work Lifecycle"),
    ("p", "Fig. 2 traces a work from a resident's request to the asset it leaves. The forward stages are Proposed, Verified, Approved, Budget Requested, Budget Approved, Funds Received, In Progress and Completed, with Rejected and On Hold as side states. No stage may be skipped: a work cannot start before its funds are recorded as received, and spending cannot be entered against a work that has not started. The sequence follows the planning practice that the Gram Panchayat Development Plan already expects of the office [@gpdp]."),
    ("fig", {"file": "fig2_lifecycle.png", "width": 3.3,
             "caption": "Fig. 2. Development-work lifecycle and the kind of actor at each stage. Stage guards are enforced in the service layer and exercised by 126 regression tests in the evaluated version. Funds received and spending are officer-entered values; the system does not verify them against payment systems or the physical site."}),
    ("p", "Two kinds of action move a work. Officer decisions move it where judgement is required (Verified, Approved, Rejected, On Hold), and a decision that closes a door, such as a rejection, requires a recorded reason. Money entries move it where recording the fact is itself the step: entering the estimate and requested amount is what makes a work Budget Requested, so the stage and the ledger cannot disagree. The Approved stage records a Panchayat decision; the officer who enters it may cite a Gram Sabha resolution."),
    ("p", "Five kinds of entry are recorded against a work: estimate, requested, approved, received and spent, each dated and attributed to one of seven funding-source labels. A source label is descriptive; nothing decides which fund a work must be paid from. Totals are not stored: every figure in an overview is the sum of entries against individual works, computed on request, so a summary cannot disagree with what it summarises. At completion, recorded physical and financial progress are compared and a gap is flagged for review. Completion and asset registration are separate events: registering the asset creates its own record, placed on the map, to which later complaints can attach and so build a maintenance history. The complaint, the work, its ledger entries and the asset reference remain linked."),
    ("p", "This is budget tracking, not accounting. There are no vouchers, no vendor ledgers and no reconciliation against payment infrastructure; Funds Received means that an officer recorded money as having arrived. The system supports traceability of a workflow from request to asset. It does not independently verify that money was received or spent, or that anything was built."),

    ("h2", "Answering a Query"),
    ("p", "Fig. 3 gives the activity diagram for the assistant. Two properties are not visible in it. The personal-fact gate precedes the check for model availability, so a personal fact is withheld whether or not a model is configured, and the two outcomes cannot be confused in the logs. Every exit returns the same response shape, carrying the answer, the records it was built from and a flag naming the path taken, so a client can show the difference between a generated answer and a template answer rather than hide it. A failed generation call is retried twice with back-off before the system falls back to a template answer from the retrieved records."),
    ("fig", {"file": "fig3_query_flow.png", "width": 3.2,
             "caption": "Fig. 3. Assistant query flow. Gate 1 (name screen) runs before anything is sent; a question naming a recorded resident is answered by keyword search alone. Other questions are embedded at the provider. Gate 2 (personal-fact gate) runs after ranking and withholds the generation call, not the embedding call."}),

    ("h1", "Implementation"),
    ("p", "The service is written in Python with FastAPI and SQLAlchemy over PostgreSQL, with schema changes tracked through Alembic migrations across about twenty entities. The client is React with TypeScript and has twenty-one screens, bilingual in English and Marathi. Bilingual coverage extends into the data: scheme names, categories and the stated reason for an adverse decision each carry Marathi text, so the explanation a resident reads is composed in Marathi rather than machine-translated. The API exposes seventy-six endpoints in the evaluated version."),
    ("p", "Three implementation choices deserve their reasons. FastAPI was chosen because its dependency injection lets role and village checks be declared in the route signature, so a route lacking one is visibly public in review instead of depending on a condition someone remembered to write in the handler. No dedicated vector store is used: embeddings are kept as 768-dimension vectors in the existing database and compared in process, which avoids a further service and a database extension the managed host does not offer, and is adequate at the scale of one block. Link following likewise walks relations already present in the relational schema instead of a separate graph database. These are deliberate limits rather than claims, and Section VIII says what a district would need instead."),
    ("p", "The generation model is configured by a named version rather than a floating alias. During development a previously working model name was retired and began returning errors while the health endpoint still reported the service as available, because it only checked that a key was configured; a separate check that makes one real call was added in response. Mapping uses Leaflet over OpenStreetMap tiles with no proprietary service [@osm], and the prototype is deployed on Render with PostgreSQL managed by Supabase, both defined declaratively so that the deployed configuration matches version control."),
    ("p", "*Artifact availability.* The source code is maintained in the authors' GitHub repository (Honey-Soni-05/E-Panchayat). The results in Section V were produced with the version described in this paper; the commit identifier of that version, together with the complaint and retrieval benchmarks and the evaluation scripts, must be released with the paper for the results to be reproducible."),

    ("h1", "Evaluation"),
    ("h2", "Setup and Data"),
    ("p", "Table 2 lists what was tested. Village identifiers, census figures and coordinates come from published government sources [@lgd], [@census] and are real, as are the scheme criteria to the extent discussed in Section V-C. Resident records, complaints, works and ledger entries are synthetic, so no real resident's income or documents were processed. Two benchmarks were written for this evaluation by the authors rather than by independent annotators: seventy-one labelled complaints, phrased as residents might speak at a counter rather than built from the classifier's keyword lists, and twenty-six natural-language questions with relevance judgements over the indexed records. The 71 benchmark complaints are distinct from the 15 synthetic grievances in the implementation dataset. Labels in both benchmarks were assigned by the authors; no second annotator was involved and agreement was not measured."),
    ("table", T2),
    ("p", "The protocol was fixed before the figures were taken. Relevance judgements for the retrieval set were recorded against the indexed records before any ranking was run, so the three conditions compared later are scored against prior judgements, not against whatever each happened to return; all three ran over an identical index and identical questions and differ only in the ranking function. The classifier was evaluated on the whole labelled set without a training/test split, because it is a rule system and nothing is fitted to the data; the keyword lists were, however, written by the same authors who wrote the benchmark. Adjudication figures are exhaustive: every one of the ten residents was assessed against every one of the twenty-nine schemes. Latency was measured on the development machine against a file-backed SQLite database and is reported as the mean and population standard deviation of five passes over all pairs for adjudication, two hundred passes over a single complaint for classification and twenty passes for each ranking condition; it excludes the provider's round trip, which dominates the total and is not attributable to the system."),

    ("h2", "Eligibility Verdict Distribution"),
    ("p", "Table 3 reports every verdict the engine produces on this register: ten residents against twenty-nine schemes, all 290 pairs, none sampled. It is a distribution of rule-engine outputs, not a measure of correctness, because no expected verdicts were established independently of the engine. That most pairs are Ineligible is unremarkable, since most residents do not qualify for most schemes. The row of interest is the third."),
    ("table", T3),
    ("p", "The thirty-seven Needs Review cases are the three-valued design at work, and they divide in two. Twenty-five arise because the scheme cannot be decided from a resident record at all; these are the seven schemes whose conditions describe somebody other than the applicant or an event the register does not hold. The remaining twelve arise because the register is silent on an attribute the rule needs, most often a disability assessment or a social category, and in a few cases a landholding or a ration card. A two-valued engine would have returned a refusal in each of those twelve. It would have been a confident refusal with a reason, and in every case the reason would have been a gap in the Panchayat's records rather than anything about the applicant."),
    ("p", "Two verdict changes came late, from a defect of the same family. A scheme states the documents it requires in its own wording, and the engine used to compare that wording with the name under which a resident's document had been filed, so four schemes asking for the same bank passbook in four phrasings in effect required it four times. Requirements and filed documents now map to one closed vocabulary of thirty document types in nine groups, so a passbook already on file satisfies all four. Two resident–scheme pairs that had been short of a paper the resident had in fact filed became Eligible, which moved two pairs from Missing Documents to Eligible in Table 3."),
    ("p", "These corrections were made after the authors had seen the engine's output on this same register, so Table 3 is not an independent test of the corrected engine; it shows what the engine now returns, and the corrections are reported so that the reader can see why."),

    ("h2", "Scheme Criteria Verification"),
    ("p", "Eleven of the twenty-nine encoded schemes were checked against their published descriptions rather than taken on trust, chosen because they carry the largest benefits or the sharpest thresholds. Three of those checks changed the encoding. Sanjay Gandhi Niradhar admits a disabled applicant under a family income ceiling of fifty thousand rupees, more than twice its general ceiling of twenty-one thousand, and the encoding did not express that route. The National Means-cum-Merit Scholarship still carried a parental income ceiling of one hundred and fifty thousand rupees, since revised to three hundred and fifty thousand [@nmmss]. The third error mattered most because it ran in the direction that wastes an applicant's day: the Indira Gandhi National Disability Pension requires an assessed disability of eighty per cent [@nsap], where the encoding required forty, so a resident assessed at forty-five per cent would have been told she qualified for a pension she does not. Correcting it moved one pair from Missing Documents to Ineligible; together with the two document corrections above, these are the only changes that moved Table 3. All three corrections were inserts into a scheme's criteria and touched no code."),
    ("p", "The Niradhar check also exposed a defect in the engine. A disjunctive route that had failed on a recorded fact but also mentioned an unrecorded attribute was being counted as Unknown, so an applicant earning eighty-five thousand rupees was referred to an officer to have a disability certificate looked up that could not have changed the outcome. Under (3)–(4) a route is Unknown only when nothing in it has actually failed. Each correction carries regression tests in both directions."),
    ("p", "Two cautions belong beside these corrections. First, the published sources disagree in places. District portals describe the Niradhar age condition variously as 18 to 65 and as below 65. The encoding was left as it stood (18 to 65 inclusive) and the conflict is recorded rather than resolved by preference. The disagreement matters exactly at age 65, and one synthetic resident is aged 65, so one of the 290 verdicts depends on it; such cases should be referred to an officer, which the engine does not yet do automatically. Second, the remaining eighteen schemes have not been checked in this way, and none of the twenty-nine has been confirmed by an officer who administers it, which is the check that would settle them. Table A1 lists each scheme's encoded criteria, its verification status and the issues that remain open."),

    ("h2", "Complaint Classification"),
    ("p", "Table 4 reports the rule-based classifier on the seventy-one labelled complaints. Category accuracy is 0.732 (52 of 71) and macro-F1 is 0.734. The request type, the field on which the whole lifecycle turns, is correct for seventy of the seventy-one, and quantity extraction succeeds for six of the nine complaints that state a quantity. These figures should not be read as performance on complaints that residents actually write; they measure the rules against their own authors' idea of a complaint, and Section VI returns to what that leaves unestablished."),
    ("table", T4),
    ("p", "The error structure is more informative than the headline. Of the nineteen category errors, twelve are complaints that matched no keyword and defaulted to Other, which is why Other shows perfect recall and a precision of 0.400; the other seven are confusions between named categories, three ending in Water, three in Roads and one in Sanitation. These counts follow arithmetically from Table 4; a full confusion matrix requires the per-complaint predictions, which are not reported here. Two causes account for most of the errors. The first is Marathi inflection. A complaint reading रस्त्यावर मोठे खड्डे (“big potholes on the road”) is plainly about roads, but the keyword list holds रस्ता and खड्डा, and neither inflected form contains its base form as a substring, so the complaint falls to Other. Marathi is agglutinative, and substring matching is the wrong instrument for it. The second is the keyword trap, where a term belonging to one category appears incidentally in a complaint about another, so a road holding water after a shower is read as a water complaint."),

    ("h2", "Routing"),
    ("p", "Routing to the responsible department is derived from the category through a fixed mapping, so it is correct in the same 52 of 71 cases. It is not an independent result and should not be read as one: routing accuracy cannot exceed category accuracy, and the two figures measure the same decision twice. Reporting it separately is useful only in that it names where an error lands, which is at an officer's desk. The system records whether a classification was automatic, so an officer's correction remains visible and an override rate can be reported once the system is in live use."),

    ("h2", "Retrieval"),
    ("p", "Table 5 compares three ways of finding records for the same twenty-six questions over the same scoped pool of 79 indexed records. The relevance unit is one indexed record, and each question's relevant set Rel(*q*) was fixed before any run. Let *L*(*q*) be the ranked list of direct matches for question *q*, and *A*(*q*) the full set returned, that is, *L*(*q*) plus any link-followed records appended after it. Precision at *k* (P@*k*) is the number of relevant records among the first *k* of *L*(*q*) divided by *k*; recall at five (R@5) is the number of relevant records in the first five divided by |Rel(*q*)|; mean reciprocal rank (MRR) averages 1/*r*, where *r* is the position of the first relevant record in the returned sequence (zero if none); and *found overall* is |Rel(*q*) ∩ *A*(*q*)| / |Rel(*q*)|. All are averaged over the 26 questions. Found overall is a recall over a set whose size varies by condition, so it is not a fixed-cutoff recall and must be read together with the final column, the mean number of records passed to the model."),
    ("table", T5),
    ("p", "Embedding similarity beats keyword search on every measure while sending less to the model: MRR rises from 0.840 to 0.923, P@3 from 0.410 to 0.526, and the context shrinks from 4.62 records to 3.62 on average. The reason is visible in the data. A resident writes that a lane is dark after sunset and the matching record is filed as a streetlight fault; the two share no word, and keyword search can reach the record only by loosening its matching until it starts pulling in unrelated records, which is why its precision is lower. The differences are nonetheless small in absolute terms: on 26 questions, one question's worth of recall is 1/26 ≈ 0.038, roughly the gap in R@5 between the first two rows. No significance test was run."),
    ("p", "Link following leaves the first five columns almost unchanged, which is expected rather than disappointing. It never reorders the direct matches; it follows the links recorded at indexing time, such as the village a complaint belongs to or the work that answers it, and appends those records after them. Its effect therefore shows in the last two columns: about 4.5 percentage points more of the relevant material is found, at a cost of roughly one extra record per question. The small MRR change from 0.923 to 0.929 is consistent with this: it can arise only from a question whose first relevant record was reached through a link, and a first hit at position six or seven, averaged over 26 questions, adds 0.005–0.006. Had only the top-five figures been reported, this component would have looked useless and might have been removed."),

    ("h2", "Access-Control and Privacy Tests"),
    ("p", "The index built against the live provider contains seventy-nine records: twenty-nine schemes, twenty-three villages, fifteen complaints, six works, five facilities and one Gram Sabha meeting. The number derived from a resident record is zero. Had the index been built by embedding every table, all ten resident records and their thirty documents would have been sent to the provider before any question was asked. Table 6 reports the same twenty-six questions issued under each role."),
    ("table", T6),
    ("p", "No query returned a record outside the asker's authority. The figures also show scoping doing its job rather than merely not failing: an officer of a village holding no records of its own receives 47 records, being the schemes and public village facts that are legitimately global, while the officer of the village under study receives 119. This is a bounded result for 104 query–role combinations over one synthetic block, not evidence that authorisation is correct for every possible request."),
    ("p", "Five kinds of evidence should be kept apart here. *Functional regression tests* check that features behave as specified. *Authorisation tests* comprise the scope measurement in Table 6 and twenty-four regression tests asserting the village check on every route that accepts an object identifier. *Name-screen tests* comprise eight tests: one substitutes an embedding client that fails if called at all, so a named question reaching the provider breaks the build rather than passing quietly, and another asserts that an ordinary question still reaches it, so a screen that had silently disabled search could not pass for one that works. The number of distinct names, the scripts covered and the false-positive and false-negative rates of the screen have not been measured. *Re-identification evaluation*, testing whether descriptive questions single out residents, and an *end-to-end privacy assessment* of the deployment have not been carried out."),

    ("h2", "Synthetic End-to-End Case"),
    ("p", "The workflow is easiest to judge on one case followed from end to end. In the synthetic data, five residents of ward 2 asked, in English and Marathi, for more streetlights between the market and the temple. The classifier marked these as development requests and read the quantity from one of them; the grouping rule recognised them as one problem and raised their priority on the number of residents, not on anything about those residents. Table 7 records what followed. Financial progress is computed as recorded spending over the approved amount (here equal to the amount received), and physical progress as units installed over units planned."),
    ("table", T7),
    ("fig", {"file": "fig4_streetlight_example.png", "width": 3.3,
             "caption": "Fig. 4. Resident view of the synthetic streetlight case: the complaint, the work it became, its stage, its officer-entered ledger figures and its physical progress. Four other residents are shown as having reported the same problem. All data are synthetic."}),
    ("p", "Fig. 4 shows the same case as a resident sees it. The complaint carries the work it became, the stages that work has passed, the amounts recorded at each step and the count of units installed. The resident who asked can follow the sanction, the recorded funds and the progress without having to trust a summary. This is the feature that most distinguishes the system from a conversational front end, with the caveat already stated: every figure on the screen is an officer's entry, not an independently verified fact."),

    ("h2", "Physical Against Financial Progress"),
    ("p", "Because money and completed units are recorded separately, they can be compared. Table 8 gives both for the six synthetic works. A work whose recorded spending has run ahead of its recorded construction is not thereby evidence of waste or wrongdoing, and the system does not suggest that it is; a gap can have ordinary explanations, such as materials bought in advance, as well as problems that need attention. It is a condition an officer should look at, and in these data the water tank, eighteen points apart, is the clearest instance."),
    ("table", T8),

    ("h2", "Privacy Notice in Use"),
    ("p", "Fig. 5 shows the assistant answering a resident's question about their own entitlement. The answer is assembled from records rather than generated, lists the sources it drew on, and carries a notice that the resident's income, category and documents were not sent outside the system and that the decision was made by a rule engine. The notice is accurate for the facts in this answer, which Control 3 withheld from generation. Its wording (\u201cnever sent\u201d) is broader than the system supports in general: this question named nobody, so its text was embedded at the provider. The interface wording should therefore be narrowed to state what was withheld. The notice is shown at all because a privacy property that users cannot observe is indistinguishable, from their side, from one that was never implemented."),
    ("fig", {"file": "fig5_privacy_notice.png", "width": 3.3,
             "caption": "Fig. 5. The assistant answering a resident's question about their own eligibility (synthetic data). The answer is written from records, not generated, and its sources are listed. The question named nobody and was therefore embedded at the provider; what was withheld from generation is the resident's income, category and documents. The on-screen phrase \u201cnever sent outside this system\u201d is broader than this and is to be narrowed."}),
    ("h2", "Latency"),
    ("p", "The deterministic components are inexpensive. Averaged over repeated runs, classifying one complaint takes 0.016 ms and one eligibility assessment 0.035 ms. Ranking the seventy-nine records took 13.9 ms (standard deviation 3.8 ms) without link following and 11.5 ms (1.5 ms) with it. Link following does strictly more work, so the lower mean does not show that it is faster; the two distributions overlap and no difference should be read into them. All figures come from one workstation without a load profile and exclude the provider's network round trip; they show only that rule-based decisions cost nothing worth optimising at this scale. In production the dominant cost would be the external model call, which the design avoids entirely for a question that names a resident and avoids for generation whenever the retrieved records are personal."),

    ("h2", "Regression Tests"),
    ("p", "The evaluated version has 634 automated regression tests. The 126 lifecycle-guard tests, the 24 route-level authorisation tests and the 8 name-screen tests cited above are subsets of that suite, not additions to it. A language-model baseline for classification was attempted on the same labelled set and abandoned after six complaints when the provider's daily free-tier quota was exhausted, so Table 4 stands without that comparison."),

    ("h1", "Threats to Validity and Limitations"),
    ("p", "*Synthetic resident data.* The register has ten residents in five households, together with fifteen grievances, six works and twenty ledger entries, all synthetic. Results that depend on data distribution, including Table 3 and Tables 7 and 8, describe this register only."),
    ("p", "*Author-constructed benchmarks.* The authors wrote the 71 complaints, the 26 retrieval questions, their labels and the classifier's keyword lists. The benchmarks therefore measure the system against its designers' intent and would not capture, for example, a disagreement between two offices about what a complaint is. The corrections of Sections V-B and V-C were made after seeing the engine's output on the same register."),
    ("p", "*Partial scheme verification.* Eleven of twenty-nine schemes were checked in detail, three of them are identified here, and none has been confirmed by an administering officer. The Niradhar age ceiling remains unresolved between sources. Scheme rules change by Government Resolution, so even checked criteria can become outdated."),
    ("p", "*No deployment.* No Gram Panchayat has used the system, so nothing is claimed about service delivery, usability by officers or residents, or effects on welfare uptake."),
    ("p", "*No generation-level evaluation.* An ablation comparing the correctness and groundedness of answers with and without retrieval needs human judgement of generated text and has not been done. Table 5 concerns what is placed before the model, not what the model then writes."),
    ("p", "*Residual privacy risk.* The three controls are firm for resident rows and for questions that name a recorded resident, and partial elsewhere. A question identifying somebody through a combination of ordinary attributes is embedded and may be sent for generation; complaint text is indexed as written; the name screen's error rates are unmeasured; and the provider's own retention terms govern whatever it receives. No re-identification test or end-to-end privacy assessment has been performed."),
    ("p", "*Authorisation coverage.* The scope results hold for the tested queries and routes. Dedicated tests for pagination, aggregate endpoints, traversal of linked records through every API path and bulk or export operations, should any be added, remain pending."),
    ("p", "*Latency.* Measurements come from one workstation, without a load profile or concurrency, and exclude network calls."),
    ("p", "*Recorded versus verified money.* Financial figures are officer-entered. The system offers traceability of what was recorded, not assurance that funds arrived, were spent as stated, or produced the recorded physical work."),

    ("h1", "Conclusion"),
    ("p", "E-Panchayat demonstrates an architectural approach in which welfare eligibility is decided by deterministic, three-valued rules over encoded scheme criteria, a development request is carried through a traceable lifecycle to an asset, and generative assistance is admitted only around those decisions, never in them. Because a verdict exists before any question is asked, the assistant can be prevented from seeing resident records at little cost: no resident record is indexed, a question naming a recorded resident is answered without an external call, and generation is withheld whenever retrieved facts are personal. Those controls do not stop a question that describes a resident without naming them, or personal details written into a complaint, from reaching the provider, and we report that limit rather than a general guarantee."),
    ("p", "The evaluation shows that, on synthetic data and author-written benchmarks, the rule engine refers incomplete cases for review rather than refusing them, embedding retrieval with link following finds more of the relevant material than keyword search, and the tested queries returned nothing outside the asker's scope. It does not establish that the encoded criteria are authoritative, that the classifier generalises to real complaints, or that the system improves service delivery. Those questions require independent validation of the scheme rules by administering officers and evaluation in a working Gram Panchayat."),

    ("h1", "Future Work"),
    ("p", "The remaining work is listed in order of priority, beginning with what would most change confidence in the present results."),
    ("bullets", [
        "**Validation of all 29 scheme criteria** by the officers who administer them, recording the source, publication date and effective date of each rule, and routing unresolved conflicts such as the Niradhar age ceiling to officer review automatically.",
        "**Privacy testing for descriptive identification and external embedding:** measuring how often attribute-based questions single out a resident in a realistic register, and the name screen's false-positive and false-negative rates across Latin and Devanagari spellings.",
        "**Evaluation on independently collected, officer-labelled complaints,** with agreement between annotators and grouping precision and recall on labelled complaint pairs.",
        "**Human assessment of retrieval-grounded answers,** comparing correctness and groundedness with and without retrieval.",
        "**Usability and field evaluation in a real Gram Panchayat,** with a baseline measured before deployment.",
        "**Performance and scalability testing** under a load profile; at district scale an indexed vector store would replace the in-process linear scan.",
        "**Morphology-aware Marathi classification,** through stemming or a small classifier trained on Panchayat complaints; national language infrastructure [@bhashini] may help here.",
        "**Local embedding models** running inside the deployment, which would mean the question text no longer leaves the deployment for search and would remove the residual risk of descriptive questions on the embedding path. A pre-embedding filter for quasi-identifiers is a weaker alternative.",
        "**Optical character recognition** for Government Resolutions, which often arrive as photographs.",
        "**Authorised document verification and messaging,** for example DigiLocker [@digilocker] and Aadhaar-based verification [@uidai], subject to the authorisation such integrations legally require, and an SMS gateway to replace the counter-issued password reset; none of these integrations exists in the prototype.",
        "**Voice input and predictive maintenance:** voice matters because a resident who cannot type can still speak, and maintenance prediction over the asset register would let a Panchayat plan repairs rather than react to them.",
    ]),

    ("ack", "The authors thank the faculty of the School of Computing, MIT ADT University, for reviewing the design at several stages. Village-level administrative data are drawn from published Government of India sources and from OpenStreetMap, and the scheme criteria from published central and Maharashtra state sources. All resident-level data used in development and evaluation are synthetic."),
]
