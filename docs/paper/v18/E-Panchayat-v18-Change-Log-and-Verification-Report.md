# E-Panchayat IEEE paper: v18 change log, verification report and unresolved issues

Prepared alongside `E-Panchayat-Research-Paper-IEEE-v18.docx` / `.pdf`. Each item is tagged with the classification the revision brief asked for:

- **VC**: verified correction (backed by the manuscript, the source code, executed tests or an authoritative source)
- **ED**: evidence-dependent (needs repository access to the evaluated version, an external check or an experiment)
- **EI**: editorial improvement
- **FW**: proposed future work, not described as done

---

## 0. The most important finding: the public repository does not match the paper

The paper was audited against `Honey-Soni-05/E-Panchayat` at commit `f6d9d2b` (branches `main`, `claude/wizardly-cray-hntwci` and `claude/dreamy-edison-wzabm3`, which all point to the same code). That snapshot is **older than the system v17 describes**. Several components and figures the paper reports cannot be found in it:

| v17 claim | What commit f6d9d2b contains |
|---|---|
| 634 automated regression tests | **295 tests collected, 295 passed** (run in this session, Python 3.13, SQLite) |
| 76 API endpoints | 66 router endpoints + `/health` = 67 |
| 8-stage work lifecycle, ledger with 5 entry kinds, 7 funding sources, asset registration | `Project` has `status ∈ {Ongoing, Completed, Delayed}`, a `budget` and a `utilized` field. No stages, ledger or asset link |
| 15 grievances, 6 works, 20 ledger entries, 7 linked grievances | 5 grievances, 4 projects, no ledger |
| 79 indexed chunks | 67 (29 schemes, 23 villages, 5 grievances, 4 projects, 5 facilities, 1 meeting) |
| Name screen before embedding (Control 2), 8 tests | Absent. `gather_semantic()` embeds the question unconditionally |
| Request type (service/development), quantity extraction, grouping, count-based priority | Absent from `services/classifier.py` |
| Closed vocabulary of 30 document types in 9 groups | Absent. Documents are matched by normalised substring |
| Household head as a relation, enforced by a partial unique index | Boolean `is_head` flag. **9 of 10 residents are flagged as head**, exactly the defect v17 says was fixed |
| Disjunctive branch that fails on a recorded fact is not Unknown | Defect still present in `evaluate()` (`any(r.unknown ...)` checked before failures) |
| IGNDPS 80%, NMMSS ₹3.5 lakh, Niradhar disability route | Encoded as 40%, ₹1.5 lakh, and no disability route |
| 71-case complaint benchmark, 26-question retrieval set, evaluation and latency scripts | None in the repository |

**Reconciliation that supports the paper:** running the engine at `f6d9d2b` over all 290 pairs gives **179 Ineligible / 67 Missing Documents / 37 Needs Review / 7 Eligible**. Apply the corrections v17 describes (document vocabulary: 2 pairs Missing Documents → Eligible; IGNDPS 80%: 1 pair Missing Documents → Ineligible) and you get **180 / 64 / 37 / 9**, exactly v17's Table 3. So the reported numbers look consistent with a later version of the code that was never pushed. The internal split of Needs Review (v17: 25 review-flag + 12 unknown; `f6d9d2b`: 24 + 13) could not be reproduced.

**Required action before submission:** push the version used for the evaluation, together with the benchmarks and evaluation scripts, and put its commit hash in the *Artifact availability* paragraph (Section IV). Until then every v18 statement that depends on that version is marked ED below. I kept the reported results rather than replacing them with the older snapshot's figures, because they describe the system the paper is about.

---

## Deliverable B: change log

| # | Page / section (v17) | Original issue | Exact correction in v18 | Reason | Evidence | Status |
|---|---|---|---|---|---|---|
| 1 | p.1 Abstract | "keeps every resident record out of the search index and out of the prompt, so that the model may be shown the village and never a villager's file" overstates the protection: question text is still embedded and sent | Rewritten. Names the three controls, then says plainly: "Other question text is still sent to the provider, so a resident described by attributes rather than named is not protected." | Privacy accuracy (Parts 2, 3) | v17 §III-E itself; `assistant.py` builds the prompt with `QUESTION: {body.query}`; `llm.embed()` sends the question | VC |
| 2 | p.1 Abstract | Scope, evaluation and limitations missing; "intended to serve first" could be read as deployment | Adds 23 villages / 18 verified coordinates, 29 schemes, synthetic 10-person register, "has not been deployed in any Panchayat", key metrics, 11/29 checked, no officer confirmation | Part 2 | Counts verified in `villages_data.json` (23 villages, 18 with coordinates) and seed data | VC |
| 3 | p.1 Index terms | Mixed separators | Normalised to an IEEE comma list | Formatting | n/a | EI |
| 4 | p.1 §I | Contributions implicit | Explicit contributions (i)–(iv) and a roadmap that matches the new section order | Clarity | n/a | EI |
| 5 | p.1 §I | "E-Panchayat decides entitlement… safer and more accountable" | "makes each easier to inspect". The unproven "safer" claim is removed | Unsupported superlative | n/a | EI |
| 6 | p.2 Table 1 | Kisan e-Mitra "in eleven languages" cited to a Sept 2023 PIB release; at launch the chatbot reportedly supported 5 languages and 11 only after a 2024 upgrade | Changed to "several Indian languages" | Citation does not support the specific count | Web search: Vikaspedia (5 at launch), Wadhwani AI (11 after Feb 2024). PIB 1959461 itself not retrieved | ED (reference) |
| 7 | p.2 Table 1 | Year "2006, 2015" for CSC/UMANG/DigiLocker; UMANG launched in 2017 | "2006–2017" | Factual | Widely documented launch (Nov 2017). Not re-fetched in this session | ED |
| 8 | p.2 Table 1 | Absence claims ("does not handle citizen grievances…") stated as fact | Column renamed "What it does not do (as documented)"; intro says the column reflects published descriptions as reviewed | Part 13: keep comparison tied to documented capabilities | n/a | EI |
| 9 | p.2 Table 1 | Heeks row: "Password reset works over the office counter…" read as a fact about Heeks | Reworded as E-Panchayat's design response | Clarity | n/a | EI |
| 10 | p.2–3 §III-A, Fig. 1 | Provider unnamed; data locations conflated; complaint free text sent to the provider not mentioned | Names the provider (Google Gemini API, embedding and generation). Separates five locations: database, index, question text, retrieved context, generation prompt. States that complaint titles and descriptions are embedded as written | Part 3 | `indexer._grievance_drafts()` embeds `g.title` and `g.description`; `config.py` `GEMINI_MODEL`, `GEMINI_EMBED_MODEL`; `EMBED_DIMENSIONS = 768` | VC (at f6d9d2b) |
| 11 | p.3 Fig. 1 | Bottom box "Never transmitted: resident names…" was too broad; "22 screens" in the figure vs "twenty-one" in the text | Fig. 1 redrawn: what crosses (a, b, c), what stays inside, and a separate "Not prevented" box. Screen count removed from the figure | Parts 3, 14 | `tools/figures.py` | VC |
| 12 | p.3 §III-B | "The order of those two steps is the whole guarantee" | Recast as a design property exercised by tests, not a proof. Spells out citizen scope, link following limited to the scoped set, object-ID checks and aggregate scoping. Points to pending tests | Part 6 | `graph._visible_chunks()`, `_expand()`; `deps.assert_can_access_village`; `analytics._in_village()`; `test_village_isolation.py` (24 tests) | VC (at f6d9d2b) |
| 13 | p.3 §III-C eq. + Algorithm 1 | Algorithm 1 not recursive; line 3 ("combine members by OR") was undefined for nested groups; lines 4–5 then applied to the group itself; manual review mixed with unknowns; prose, equation and algorithm described different procedures | New formal model: eq. (2) leaf semantics, (3)–(4) strong Kleene AND/OR, (5) manual-review cap min(v, U), (6) verdict with Δ kept separate. Algorithm 1 rewritten as a recursive Eval matching (2)–(6). Prose rewritten to match | Part 4 | Logic verified by hand. Equivalent to v17's rule for the 29 schemes as encoded (review flags only at scheme level; verified in seed data) | VC |
| 14 | p.3 §III-C | Missing attributes: rule not stated for income/BPL/SECC | Adds: an implementation must return Unknown rather than substitute defaults. States that income, BPL, SECC, occupation and ward are recorded for all 10 synthetic residents, so Table 3 is unaffected | Part 4 | Seed-data null counts computed. **Code at f6d9d2b violates this** (`income or 0`; `not citizen.is_bpl` fails on null). See C-7 | VC (paper) / ED (evaluated code) |
| 15 | p.3–4 §III-D | Could be read as the system determining relationships; "exactly one head" conflicts with "household with no head on record" | "At most one head"; "the system never elects or infers a head or a relationship"; relations entered by the officer | Part 4 | v17 text; 9-of-10 heads defect confirmed at f6d9d2b | VC (defect) / ED (fix) |
| 16 | p.4 §III-E | "Three mechanisms… enforce the boundary independently" with uneven naming | Consistent names (Control 1 index exclusion, Control 2 name screen, Control 3 personal-fact gate); purpose and gaps of each; shared gap (descriptive identification) stated in its own paragraph | Part 3 | v17 text; f6d9d2b code for Controls 1 and 3 | VC (1, 3) / ED (2) |
| 17 | p.4 §III-E | Name-screen limitations incomplete | Adds transliteration variants, nicknames/aliases, false positives on place names; "neither error rate has been measured" | Part 3 | n/a | EI |
| 18 | p.4 §III-E | Top-k and link limits not stated | Adds "at most six direct matches", "up to three linked neighbours per match", and that τ was not validated on any other corpus | Reproducibility | `semantic_search(limit=6)`, `EXPAND_PER_HIT = 3`, `MIN_SIMILARITY = 0.55` | VC |
| 19 | p.4–5 §III-F | Baseline priority, ties, Other default, quantity limits and grouping heuristic under-specified; "the count suffices" implied that frequency equals urgency | Specifies max-hit category, tie rule, Other default, baseline priority from escalation terms and category defaults, +1 at 3 / +2 at 5 capped at High, Critical only by danger terms. Adds "count measures how widely a problem is felt, not how severe". Grouping called a heuristic with unmeasured precision and recall | Part 7 | `classifier.py` (category, priority, Critical/High/Low terms) at f6d9d2b. Grouping and quantity rules from v17 | VC / ED |
| 20 | p.5 §III-G, Fig. 2 | Fig. 2 omitted Rejected and On Hold; legend text truncated ("officer decisi"); asset/completion distinction blurred; "the two can never disagree" | Fig. 2 redrawn with side states, a full legend and a reason requirement. Text separates officer decisions from money entries and completion from asset registration, and states that no money or construction is independently verified | Part 8 | v17 text. Lifecycle code not in public repo | ED |
| 21 | p.5 Fig. 3 | Caption fine; embedding failure path and gap note missing | Fig. 3 redrawn: embedding marked as "question leaves the deployment", embedding-failure fallback, τ and link limit, Gate 1 limitation box | Parts 3, 14 | Fallback in `gather_semantic()`; retries `RETRY_DELAYS=(0.6,1.8)` | VC |
| 22 | p.5–6 §IV | "twenty-one screens" vs Fig. 1 "22 screens"; 76 endpoints unverified | Text keeps 21 (figure no longer states a count); endpoints "in the evaluated version". *Artifact availability* paragraph added | Consistency, reproducibility | Public repo: 67 endpoints, 21 component files | ED |
| 23 | p.6 §V-A, Table 2 | 15 grievances and the 71-case benchmark could be confused; label provenance not stated | Table 2 adds "(separate from the 15 grievances)", sub-rows, "one recorded head each". Text adds who assigned labels and that no agreement was measured | Part 9A | v17 text | EI |
| 24 | p.6 Table 3 | Could be read as accuracy | Caption: "distribution, not an accuracy measure"; Total row added; corrections made post hoc on the same register now stated | Part 9B | Arithmetic: 180+64+37+9=290; 62.07/22.07/12.76/3.10% | VC |
| 25 | p.7 §V-B | Niradhar age conflict: affected cases not identified | States that one synthetic resident is exactly 65, so one of 290 verdicts depends on the unresolved rule; such cases should go to an officer (not yet automatic) | Part 5 | Seed: Lata Shinde, age 65, BPL. District portals: "below 65" vs "18–65" | VC |
| 26 | p.7 §V-B | Scheme corrections lacked sources | NMMSS ₹3.5 lakh cited to the MoE scheme page [33]; IGNDPS 80% cited to NSAP [34] | Part 13 | Web: MoE NMMSS page confirms ₹3,50,000; Bihar govt portal + others confirm 80%, 18–79, BPL; district portals confirm ₹21,000 / ₹50,000 (disabled) | VC (facts) / ED (URL access) |
| 27 | (new) Appendix Table A1 | No per-scheme validation table | 29-row table: encoded criteria, source, status (Checked / Review / Not re-verified), outstanding issue | Part 5 | Criteria from `seed_data.json`, adjusted for the 3 reported corrections | VC (encodings) / ED (status of the other 8 of the 11) |
| 28 | p.7 Table 4 | Request-type figure 0.986 shown in the F1 column; it is accuracy (70/71) | Moved to a table note as accuracy. TP/FN/FP columns derived; macro-average row added | Part 9C | Recomputed: TP=14,9,7,8,6,8 (Σ52); predictions Σ71; macro-F1 = 0.7344; macro-P 0.804; macro-R 0.739 | VC |
| 29 | p.7 §V-C | "Three causes account for nearly all" without counts | Derived: 19 errors = 12 defaults to Other + 7 cross-category (3→Water, 3→Roads, 1→Sanitation). States that a full confusion matrix needs per-item predictions | Part 7 | Arithmetic from Table 4 | VC |
| 30 | p.7 §V-C | Marathi example: only रस्ता noted | Adds that खड्डे does not contain खड्डा either | Accuracy | String check | VC |
| 31 | p.7–8 §V-D | Routing: correct framing retained | Kept. Wording tightened | n/a | n/a | EI |
| 32 | p.8 §V-E, Table 5 | Metrics loosely defined; "Found overall" read as recall; MRR change from link following unexplained although "it never reorders" | Formal definitions of P@k, R@5, MRR and found overall with L(q), A(q); found overall named as variable-size recall; explains the +0.006 MRR (first hit at rank 6–7 for about one question); notes 1/26 ≈ 0.038 granularity and that no significance test was run | Part 9D | Arithmetic: 0.904−0.865 ≈ 1/26; 1/6/26 = 0.0064, 1/7/26 = 0.0055; 0.949−0.904 = 0.045; 4.58−3.62 = 0.96 | VC (arithmetic) / ED (definitions must match the script) |
| 33 | p.8 §V-F, Table 6 | "unauthorised retrieval rate of zero" read as general | "bounded result for 104 query–role combinations over one synthetic block" | Parts 6, 10 | n/a | EI |
| 34 | p.8 §V-F | Regression, authorisation, name-screen, re-identification and privacy assessment used loosely | Five kinds of evidence defined and kept apart; re-identification and end-to-end privacy assessment marked as not done | Part 10 | n/a | EI |
| 35 | p.9 Table 7, Fig. 4 | Synthetic status implicit; financial-progress denominator not stated | Caption "Not a real project, grant or payment"; financial progress defined as spent/approved; officer-recorded labels | Part 9E | 14/20 = 70%; 2,80,000/3,50,000 = 80%; screenshot shows the same figures | VC |
| 36 | p.9 Table 8 | Wrongdoing risk in interpretation | Caption and text: gap is a prompt for review; ordinary explanations possible | Part 9E | Variances recomputed: +18, +10, +7, +4, −1, 0 | VC |
| 37 | p.10 Fig. 5 | Caption said "what did not leave is the resident's income, category and documents". On-screen notice says "never sent outside this system" | Caption and new §V-J say the notice is right for this answer but broader than the system supports, and that the wording should be narrowed | Parts 3, 14 | `retrieval.plain_answer()` footer text | VC |
| 38 | p.10 §V-I latency | "link following… 11.5 ms" might be read as faster | Adds "link following does strictly more work, so the lower mean does not show that it is faster" | Part 9F | v17 text | EI |
| 39 | p.10 tests | Overlap of 634/126/24/8 unclear | States 126, 24 and 8 are subsets of the 634 | Part 9G | 24 confirmed as a subset at f6d9d2b; others ED | ED |
| 40 | p.10 §V-J Threats | Missing several required threats | Rewritten as labelled paragraphs covering all 9 items from Part 11 plus post-hoc corrections and pending authorisation tests | Part 11 | n/a | EI |
| 41 | p.10–11 §VI Conclusion | "The pattern generalises. Wherever a consequential outcome…" and "the model is never asked to reason about a person's circumstances" read as general claims | Conclusion limited to what was shown; lists what was not established; generalisation claim removed | Part 11 | n/a | EI |
| 42 | p.11 §VII Future scope | Unordered; Aadhaar/DigiLocker/SMS could read as near-ready | 11 priorities in the order given in Part 12; integrations explicitly "none of these… exists", subject to legal authorisation | Part 12 | Repo has only a hashed Aadhaar number used as a login identifier, no UIDAI authentication and no SMS gateway (`notify.py`) | VC / FW |
| 43 | p.11 Acknowledgement | Thanks Prof. Jyoti Gavhane, who is a co-author | Removed (IEEE practice: co-authors are not acknowledged). **Authors to confirm** | Formatting | Author list | EI |
| 44 | Refs [4] | `https://pmayg.gov.in` | `https://pmayg.nic.in`; access date removed until re-checked by the authors | URL accuracy | Multiple secondary sources name pmayg.nic.in | ED |
| 45 | Refs [6] | MJPJAY attributed to "Public Health Department", URL `phd.maharashtra.gov.in` | "State Health Assurance Society, Public Health Department"; `https://www.jeevandayee.gov.in` | URL accuracy | Secondary sources | ED |
| 46 | Refs [7],[9],[16],[21],[23]–[25],[27] | No DOIs; some abbreviations inconsistent | DOIs added; IEEE abbreviations (ACM Comput. Surveys, Nature Mach. Intell., Manage. Sci., etc.); Rudin issue no. 5; Ji Art. no. 248 | Part 13 | Standard bibliographic records known to the editor; **not resolved online in this session** | ED |
| 47 | Refs [17] | Institution incomplete | "Inst. Develop. Policy Manage., Univ. Manchester" | Formatting | n/a | EI |
| 48 | Refs (new) [26], [33], [34] | Provider, NMMSS and NSAP uncited | Added Gemini API docs, MoE NMMSS page, NSAP. No access date, because they were not opened directly in this session | Part 13 | See items 10, 26 | ED |
| 49 | All refs | Order | Renumbered by first citation (generator enforces it) | IEEE style | `build_docx.py` | VC |
| 50 | Tables | Arabic numbering | IEEE Roman numerals (TABLE I–VIII), appendix TABLE A1 | IEEE style | n/a | EI |
| 51 | Throughout | Long, sometimes rhetorical sentences ("Into this gap the language model arrives…", "It should be resisted.") | Rewritten in a plainer academic register, keeping the authors' concrete examples (Diwali tap, widowed labourer, 30 complaints on one lane) | Part 15A | n/a | EI |

**Claims removed, narrowed or qualified:** model "never a villager's file" (narrowed); "the whole guarantee" (narrowed); "safer and more accountable" (removed); "eleven languages" (removed); "The pattern generalises…" (removed); "the two can never disagree" (narrowed to stage and ledger); "badge is load-bearing" (kept as reasoning, with the wording problem stated); "zero unauthorised retrieval rate" (bounded); request-type "F1 0.986" (relabelled as accuracy).

---

## Deliverable C: unresolved issues and the evidence each needs

| # | Issue | Evidence required |
|---|---|---|
| C-1 | Evaluated code version is not in the public repository (Section 0) | Push the code; tag the commit; insert the hash in §IV *Artifact availability*; release the 71-complaint and 26-question benchmarks, labels, predictions and the evaluation and latency scripts |
| C-2 | 634 / 126 / 8 test counts and pass status | Run `pytest --collect-only -q` and `pytest` on the evaluated commit; report collected/passed; confirm 126 and 8 are subsets |
| C-3 | 76 endpoints, 21 screens, ~20 entities | Count from the evaluated commit (e.g., `app.routes`) |
| C-4 | Classifier metrics, full confusion matrix | Per-complaint gold labels and predictions; recompute with a script; add a 6×6 confusion matrix |
| C-5 | Retrieval metric definitions | Confirm the script uses a fixed-k denominator for P@k, the denominator for R@5, the role under which the 26 questions were run, and \|Rel(q)\| per question. If any differ, change the definitions, not the numbers |
| C-6 | Needs Review split 25/12 | Recompute on the evaluated commit (f6d9d2b gives 24/13) |
| C-7 | Missing-value handling in the eligibility code (f6d9d2b: missing income → 0, i.e. passes ceilings; missing BPL/SECC → fail; missing occupation/ward → fail; failed-branch-with-unknown → Unknown; route-level `manual_review` dropped) | Confirm the evaluated code returns Unknown for every missing attribute, as eq. (2) states; add regression tests. The same defects should be fixed in the public code |
| C-8 | Which 8 further schemes made up the "eleven checked in detail" | Authors' records of the 11; update Table A1 status |
| C-9 | Officer confirmation of all 29 schemes; Niradhar age ceiling | Written confirmation from the administering office or the current GR text with date; then encode the boundary rule or route age-65 cases to review |
| C-10 | Scheme criteria that may be outdated (MJPJAY coverage, AB-PMJAY expansions, PMUY categories, PM-KISAN exclusions, Ladki Bahin household limit, SBM-G APL groups) | Current GRs and guidelines with publication and effective dates |
| C-11 | Name-screen evaluation | Test set of named and unnamed questions in Latin and Devanagari, with variants; report false positives and false negatives |
| C-12 | Re-identification / descriptive-query risk | Experiment on a realistic synthetic register: what fraction of attribute combinations single out one person |
| C-13 | Authorisation coverage | Pending tests: pagination beyond the first page (`/citizens?limit`, `/audit?limit`); every analytics endpoint per role; direct-object GET/PATCH/DELETE across villages for works, ledger entries, assets and meetings; link traversal through every API that returns related records; any export or bulk route |
| C-14 | Lifecycle details | Exact set of states from which Rejected and On Hold can be entered, which transitions require a reason, which role can enter which money entry. Then update Fig. 2 if needed |
| C-15 | Grouping precision and recall | Labelled complaint pairs |
| C-16 | Generation-level ablation | Human judgements of correctness and groundedness |
| C-17 | Reference checks not done online | Resolve all DOIs; open each government URL and record the access date; retrieve PIB 1959461 and confirm what it states; confirm pmayg.nic.in and jeevandayee.gov.in; confirm UMANG launch year; add access dates for [4], [6], [26], [33], [34] |
| C-18 | Provider data-use terms | Cite the provider's current terms for the tier actually used (the intro says "where a hosted service's terms permit…") |
| C-19 | UI notice wording ("never sent outside this system") | Change the interface text; replace the Fig. 5 screenshot afterwards |
| C-20 | Acknowledgement change | Authors to confirm that removing the thanks to a co-author is acceptable |
| C-21 | Page count | v18 runs to 14 pages including the appendix. If the venue limits length, move Table A1 to supplementary material |

---

## Deliverable D: verification report

### D.1 Claims verified from the manuscript (internal consistency)
- Table 2 sums: 29 + 23 + 15 + 6 + 5 + 1 = 79 chunks ✓. 5 service + 10 development = 15 ✓.
- Table 3: totals and percentages ✓.
- Table 4: support Σ = 71; predicted Σ = 71; TP Σ = 52 → 0.7324 ✓; per-class F1 ✓; macro-F1 = 0.7344 ✓.
- Table 5: values consistent with 26 questions (MRR × 26 = 24.0 for embeddings; R@5 differences = 1/26).
- Table 6: within + outside = returned ✓.
- Table 7 vs Fig. 4 (screenshot): ₹4,00,000 / ₹4,00,000 / ₹3,50,000 / ₹3,50,000 / ₹2,80,000; 14 of 20; 70%; "4 other residents" ✓.
- Table 8 variances ✓.
- Inconsistency found: Fig. 1 "22 screens" vs text "twenty-one" (resolved by removing the count from the figure).

### D.2 Claims verified from source code (commit f6d9d2b)
- Three roles; `require_officer`, `require_admin`; village scope applied before ranking (`_visible_chunks`); link expansion restricted to the visible set; object-ID routes check village; analytics scoped.
- Resident records not indexed (indexer builds no citizen drafts; test `test_no_chunk_from_any_table_quotes_a_resident_by_name`).
- Complaint title and description embedded; complainant name not included.
- Personal-fact gate checked before the key check; template answer; `mode` flag on every exit.
- Question text included verbatim in the generation prompt and sent for embedding.
- Provider: Google Gemini API; embeddings 768-d (`EMBED_DIMENSIONS`); τ = 0.55; top 6; 3 links per hit; 2 retries with back-off.
- 23 villages, 18 with coordinates; 29 schemes; 10 residents; 5 households; 30 documents; 1 meeting; 5 facilities; 7 schemes with `manual_review`.
- Classifier: max-hit category, Other default, Critical/High/Low terms, Water/Health default High.
- Aadhaar: hashed Aadhaar number used as a sign-in identifier only; no UIDAI authentication; no SMS gateway.

### D.3 Tests actually executed
- `pytest` at f6d9d2b: **295 collected, 295 passed** (203.96 s, Python 3.13.16, SQLite). This is **not** the 634-test suite the paper reports.
- Seeding plus a full eligibility sweep: 179 / 67 / 37 / 7 (see Section 0).
- No benchmark, retrieval or latency script was available to run.

### D.4 External references checked (web search in this session)
- Niradhar: ₹21,000 general and ₹50,000 for disabled applicants confirmed by district government portals; age condition conflicts ("below 65" on the Pune/Nashik pages vs "18–65" on Ahmednagar).
- NMMSS: ₹3,50,000 parental income ceiling confirmed by the Ministry of Education scheme page.
- IGNDPS: 18–79, ≥80% disability, BPL confirmed (Bihar government portal and other listings).
- Kisan e-Mitra: launched Sept 2023; 5 languages at launch, 11 after the 2024 upgrade (secondary sources).
- PMAY-G URL pmayg.nic.in and MJPJAY URL jeevandayee.gov.in: secondary sources only.
- Direct fetches of nsap.nic.in and ai.google.dev failed (DNS unavailable in the sandbox), so access dates were not added.
- Academic references ([7]–[9], [16]–[19], [21]–[25], [27], [28]) were checked against known bibliographic records, not resolved online.

### D.5 Arithmetic independently recalculated
Every number in Tables 3, 4, 7 and 8; the derived TP/FN/FP; macro averages; the MRR increment; the recall granularity (1/26); the extra records from link following (+0.96); percentage-point differences.

### D.6 Items requiring additional experiments
C-4, C-5, C-11, C-12, C-13, C-15, C-16, plus latency under load.

### D.7 Proposed features that remain future work
Officer validation workflow; automatic age-boundary referral; local embeddings; a pre-embedding quasi-identifier filter; morphology-aware Marathi; OCR for GRs; DigiLocker, Aadhaar authentication and SMS gateway; voice input; predictive maintenance; an indexed vector store at district scale.

---

## Passages where the authors should add their own input (Part 15A item 9)
1. **§V-A label assignment:** when and how the complaint and retrieval labels were assigned (before or after the rules were written; one author or several).
2. **§V-C:** the identity of the other eight schemes among the eleven checked, and the documents consulted.
3. **§III-G / Fig. 2:** exact transition rules for Rejected and On Hold and the permissions for each money entry.
4. **§IV:** the commit hash and benchmark release location.
5. **§I and §VI:** if the team has spoken with any Panchayat staff, describe it accurately. Otherwise leave the text as is: v18 claims no fieldwork.
6. **Acknowledgement:** supervisor/funding wording, and any AI-assistance disclosure your university or the venue requires. Many IEEE venues ask authors to disclose AI use in the acknowledgements.

## Note on writing style and AI detection
The prose was revised for clarity, specificity and a consistent voice, as Part 15A asks. It was not tuned for, and no claim is made about, any AI-detection score. Disclosure of AI assistance is governed by your university's and the venue's policy.

## Rebuilding the files
```
pip install python-docx matplotlib
python docs/paper/v18/tools/figures.py docs/paper/v18/figures
python docs/paper/v18/tools/build_docx.py docs/paper/v18/figures docs/paper/v18/E-Panchayat-Research-Paper-IEEE-v18.docx
soffice --headless --convert-to pdf --outdir docs/paper/v18 docs/paper/v18/E-Panchayat-Research-Paper-IEEE-v18.docx
```
Figures 4 and 5 are the v17 screenshots, extracted unchanged. Devanagari text needs a Devanagari font (Noto Serif Devanagari was used).
