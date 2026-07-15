# Golden Question Set — Parliament Bot (DRAFT)

**Status: DRAFT — answers are Claude's best attempt and MUST be verified/replaced by a qualified lawyer before use.**

## How to use this document

Same rubric and process as the legislation set (see `GOLDEN_QUESTIONS_LEGISLATION.md`): correct the **Draft answer**, confirm the **Required citation(s)/acceptance criteria**, and pay particular attention to **Medium/Low confidence** and **[VERIFY]** entries. Drafting knowledge cutoff: **January 2026** — outcomes of 2026 debates in particular need checking against the Official Report.

**Corpus note:** the bot's full-text database covers Scottish Parliament plenary and committee proceedings from **13 May 2021 to present** (Sessions 6–7). Questions about earlier proceedings, or about Westminster, are deliberate traps — the correct behaviour is to say the records are not available, not to fabricate.

For search-style questions (e.g. written answers), a single "correct answer" doesn't exist — the **acceptance criteria** describe what a correct response must do.

### Grading rubric

| Grade | Meaning |
|---|---|
| A | Correct, complete, all citations verified against the Official Report |
| B | Correct but incomplete (missed a relevant debate/speech) |
| C | Materially wrong or misleading (e.g. wrong speaker, wrong outcome) |
| D | Hallucinated citation or fabricated content (invented debate, invented quote) |

### Categories

`plenary-fact` (verifiable fact from a chamber debate) · `plenary-retrieval` (must retrieve and quote/summarise actual speeches) · `written` (written answers via TWFY) · `committee` (committee transcript search/retrieval) · `member` (MSP information) · `bill` (bill progress) · `trap` (out of scope / no such record)

---

## P01 — plenary-fact — Confidence: High
**Q:** What was the outcome of the Stage 3 vote on the Gender Recognition Reform (Scotland) Bill?
**Draft answer:** The Bill passed Stage 3 on 22 December 2022 by 86 votes to 39. (It was subsequently blocked from Royal Assent by a s.35 Scotland Act 1998 order made by the UK Government in January 2023.)
**Required citation(s):** Official Report, Meeting of the Parliament, 22 December 2022 (Stage 3 debate and decision).

## P02 — plenary-retrieval — Confidence: Medium
**Q:** What did the Cabinet Secretary for Social Justice say in closing the Stage 3 debate on the Gender Recognition Reform (Scotland) Bill?
**Draft answer:** Shona Robison closed for the Government, defending the Bill as a simplification of an existing process that does not affect the Equality Act 2010 protections. **Acceptance criteria:** retrieves the actual 22 December 2022 debate, correctly attributes the closing speech to Shona Robison, and summarises/quotes her actual words (grader checks against the Official Report).
**Required citation(s):** Official Report, 22 December 2022, Shona Robison's closing speech.

## P03 — plenary-fact — Confidence: High
**Q:** What did Michael Matheson address in his personal statement to the Parliament in November 2023?
**Draft answer:** On 16 November 2023 he made a personal statement about the ~£11,000 data-roaming charges incurred on his parliamentary iPad during a family holiday in Morocco, apologising and explaining that his sons had used the device as a hotspot to watch football; he undertook to repay the costs.
**Required citation(s):** Official Report, Meeting of the Parliament, 16 November 2023 (Personal Statement).

## P04 — plenary-fact — Confidence: Medium-High
**Q:** What was the result of the Stage 1 vote on the Assisted Dying for Terminally Ill Adults (Scotland) Bill?
**Draft answer:** The Parliament agreed to the general principles at Stage 1 on 13 May 2025, by 70 votes to 56 (with 1 abstention). **[VERIFY exact figures]**
**Required citation(s):** Official Report, 13 May 2025 (Stage 1 debate and decision).

## P05 — plenary-fact — Confidence: Medium **[VERIFY date/details]**
**Q:** What did the Minister announce to Parliament in June 2023 about the deposit return scheme?
**Draft answer:** Lorna Slater (Minister for Green Skills, Circular Economy and Biodiversity) made a statement (early June 2023) that the scheme's launch would be delayed to at least October 2025, attributing this to the UK Government's conditions on the UK Internal Market Act exclusion — in particular the exclusion of glass.
**Required citation(s):** Official Report, ministerial statement on the deposit return scheme, June 2023.

## P06 — plenary-retrieval — Confidence: Medium **[VERIFY date]**
**Q:** What did Nicola Sturgeon tell the Parliament about the Bute House Agreement with the Scottish Green Party in 2021?
**Draft answer:** In a statement/debate around 31 August 2021 the First Minister set out the cooperation agreement: Green MSPs entering government as junior ministers, a shared policy programme excluding agreed areas of disagreement, and its significance for climate policy and independence. **Acceptance criteria:** retrieves the actual 2021 statement/debate and attributes positions correctly.
**Required citation(s):** Official Report, statement on the Bute House Agreement, August/September 2021.

## P07 — plenary-fact — Confidence: Medium **[VERIFY vote figures]**
**Q:** Who did the Scottish Parliament nominate as First Minister in March 2023, and what was the vote?
**Draft answer:** Humza Yousaf was nominated on 28 March 2023, winning the vote against Douglas Ross, Anas Sarwar and Alex Cole-Hamilton (Yousaf 71 votes in the final selection). **[VERIFY figures]**
**Required citation(s):** Official Report, 28 March 2023 (selection of First Minister).

## P08 — plenary-fact — Confidence: Medium **[VERIFY]**
**Q:** When was John Swinney nominated by the Parliament as First Minister, and who else stood?
**Draft answer:** 7 May 2024; he won the nomination vote against other party leaders (Douglas Ross, Anas Sarwar, Alex Cole-Hamilton stood as candidates). **[VERIFY who formally stood and figures]**
**Required citation(s):** Official Report, 7 May 2024 (selection of First Minister).

## P09 — plenary-fact — Confidence: Medium **[VERIFY — near knowledge cutoff]**
**Q:** When did the Land Reform (Scotland) Bill complete Stage 3, and what was the outcome?
**Draft answer:** Stage 3 proceedings ran across several sittings in late October/early November 2025, concluding on or around 5 November 2025 with the Bill being passed. **Acceptance criteria:** correct final date, outcome, and (bonus) key amendments debated (e.g. land-transfer/lotting thresholds).
**Required citation(s):** Official Report, Stage 3 sittings, 28–29 October and 4–5 November 2025.

## P10 — plenary-fact — Confidence: Medium **[VERIFY]**
**Q:** When did the Coronavirus (Recovery and Reform) (Scotland) Bill pass Stage 3?
**Draft answer:** June 2022 (the Act received Royal Assent in August 2022). The Bill made permanent certain pandemic-era reforms (e.g. remote court hearings, public-health protections). **[VERIFY exact Stage 3 date — believed 28 June 2022]**
**Required citation(s):** Official Report, Stage 3 debate, June 2022.

## P11 — plenary-retrieval — Confidence: Medium **[VERIFY content]**
**Q:** What were the headline announcements in the Programme for Government statement in September 2024?
**Draft answer:** John Swinney's first Programme for Government (4 September 2024) prioritised eradicating child poverty, economic growth, net zero and public services. **Acceptance criteria:** retrieves the actual 4 September 2024 statement and reports announcements actually made in it (grader checks against the Official Report — no imported knowledge from news coverage).
**Required citation(s):** Official Report, 4 September 2024 (Programme for Government statement).

## P12 — plenary-retrieval (Pepper v Hart-style) — Confidence: Medium
**Q:** What did the responsible minister say was the purpose of the visitor levy during the Stage 1 debate on the Visitor Levy (Scotland) Bill?
**Draft answer:** The Minister (Public Finance — Tom Arthur) presented the levy as a discretionary power for local authorities to charge a percentage-based levy on overnight accommodation, with proceeds ring-fenced for facilities and services substantially used by visitors. **Acceptance criteria:** retrieves the actual Stage 1 debate (spring 2024), correct minister, faithful account of the stated purpose.
**Required citation(s):** Official Report, Visitor Levy (Scotland) Bill Stage 1 debate (2024), ministerial opening/closing speech.

## P13 — written — Confidence: Medium (acceptance-criteria graded)
**Q:** What have Scottish Ministers said in written answers about the control of XL bully dogs?
**Draft answer:** Ministers confirmed (early 2024) that Scotland would replicate safeguards similar to the E&W rules — new safeguards from 23 February 2024 and an exemption/registration scheme — following concern about dogs being moved to Scotland. **Acceptance criteria:** returns at least one genuine written answer on XL bully dogs with date and answering minister; content faithful to the answer text.
**Required citation(s):** At least one Scottish Parliament written answer (S6W-series) on XL bully dogs, 2023–24.

## P14 — written — Confidence: N/A (acceptance-criteria graded)
**Q:** What recent written answers have been given about NHS waiting times in Scotland?
**Draft answer:** N/A — graded on acceptance criteria: returns one or more genuine written answers about NHS Scotland waiting times, correctly dated and attributed, faithfully summarised; does not present debate speeches as written answers.
**Required citation(s):** Genuine S6W written answer reference(s).

## P15 — written — Confidence: N/A (acceptance-criteria graded)
**Q:** What have ministers said in written answers about the ferries being built at Ferguson Marine for the Clyde and Hebrides network?
**Draft answer:** N/A — graded on acceptance criteria: returns genuine written answers concerning Ferguson Marine / vessels 801–802 (Glen Sannox, Glen Rosa), with correct dates, ministers, and faithful content (costs, delivery dates).
**Required citation(s):** Genuine S6W written answer reference(s).

## P16 — committee — Confidence: Medium
**Q:** What concerns did the Finance and Public Administration Committee hear about the financial memorandum to the National Care Service (Scotland) Bill?
**Draft answer:** In evidence during 2022 the Committee heard strong criticism that the financial memorandum's cost ranges were too broad and uncertain (multi-billion-pound ranges, unquantified costs), including from COSLA and public-finance experts; the Committee took the unusual step of asking the Government for a revised memorandum. **Acceptance criteria:** cites actual FPAC evidence sessions with named witnesses.
**Required citation(s):** FPAC Official Report, evidence sessions on the NCS Bill financial memorandum, autumn 2022.

## P17 — committee — Confidence: Medium
**Q:** What evidence did the Criminal Justice Committee hear about the proposed juryless rape trials pilot in the Victims, Witnesses, and Justice Reform (Scotland) Bill?
**Draft answer:** During Stage 1 (2023–24) the Committee heard sharply divided evidence: support citing research on rape myths affecting juries, and strong opposition from defence lawyers (including bar associations threatening boycott) on fair-trial grounds. The pilot was later dropped from the Bill. **Acceptance criteria:** cites actual Criminal Justice Committee sessions and witnesses; correct characterisation of both positions.
**Required citation(s):** Criminal Justice Committee Official Report, Stage 1 evidence on the Bill, 2023–24.

## P18 — committee — Confidence: Medium
**Q:** What evidence did the Health, Social Care and Sport Committee take on the Assisted Dying for Terminally Ill Adults (Scotland) Bill?
**Draft answer:** The Committee took extensive Stage 1 evidence (2024–25) from medical bodies, palliative-care specialists, disability organisations, faith groups and international witnesses, covering eligibility criteria, the age threshold, coercion safeguards and conscientious objection. **Acceptance criteria:** cites actual HSCS Committee sessions with named witnesses; does not conflate with the plenary Stage 1 debate.
**Required citation(s):** HSCS Committee Official Report, Stage 1 evidence sessions, 2024–25.

## P19 — committee — Confidence: Medium
**Q:** What did the COVID-19 Recovery Committee hear about the vaccine certification (Covid passport) scheme in autumn 2021?
**Draft answer:** The Committee scrutinised the domestic vaccine certification scheme (introduced October 2021 for nightclubs and large events), hearing evidence from business/hospitality representatives about practicality and economic impact, and from ministers and public-health officials about its aims. **Acceptance criteria:** cites actual COVID-19 Recovery Committee sessions from autumn 2021.
**Required citation(s):** COVID-19 Recovery Committee Official Report, autumn 2021.

## P20 — committee — Confidence: Medium
**Q:** What evidence did the Net Zero, Energy and Transport Committee hear about the deposit return scheme?
**Draft answer:** The Committee heard evidence (2022–23) from Circularity Scotland, retailers, hospitality and drinks producers about readiness, producer-registration rates, costs to small producers, and the treatment of glass — much of it warning the scheme was not ready for its planned launch. **Acceptance criteria:** cites actual NZET Committee sessions with named witnesses.
**Required citation(s):** NZET Committee Official Report, DRS evidence sessions, 2022–23.

## P21 — committee — Confidence: Medium
**Q:** What has the Public Audit Committee examined regarding the Ferguson Marine shipyard and vessels 801 and 802?
**Draft answer:** The Committee has repeatedly taken evidence (2022 onwards) following Audit Scotland reports on the ferry procurement — covering cost escalation, delays, the 2015 contract award without a full builder's refund guarantee, governance of the nationalised yard, and due diligence. Witnesses included Ferguson Marine executives, CMAL and Scottish Government officials. **Acceptance criteria:** cites actual Public Audit Committee sessions.
**Required citation(s):** Public Audit Committee Official Report, evidence on Ferguson Marine, 2022 onwards.

## P22 — committee — Confidence: Medium **[VERIFY committee and dates]**
**Q:** What committee scrutiny took place when the UNCRC Bill returned to the Parliament for reconsideration in 2023?
**Draft answer:** Following the UKSC judgment ([2021] UKSC 42), the Bill was amended at a Reconsideration Stage (late 2023) to confine the s.6 compatibility duty to functions under ASPs; the Education, Children and Young People Committee took evidence on the amended approach, including concerns that children's rights protection would be narrower than originally intended. **Acceptance criteria:** correct committee, correct account of the competence fix.
**Required citation(s):** ECYP Committee Official Report, 2023; Official Report, Reconsideration Stage, December 2023.

## P23 — committee — Confidence: Medium
**Q:** What evidence did the Equalities, Human Rights and Civil Justice Committee hear at Stage 1 of the Gender Recognition Reform (Scotland) Bill?
**Draft answer:** During 2022 the Committee heard divided evidence: trans-rights organisations and some legal witnesses supporting de-medicalisation and the move to statutory declaration; women's organisations and other witnesses raising concerns about single-sex spaces and interaction with the Equality Act 2010. The Committee's majority report supported the general principles. **Acceptance criteria:** cites actual EHRCJ Committee sessions with named witnesses.
**Required citation(s):** EHRCJ Committee Official Report, Stage 1 evidence, 2022.

## P24 — member — Confidence: High
**Q:** Which MSP represents the Orkney Islands constituency?
**Draft answer:** Liam McArthur (Scottish Liberal Democrats), MSP for Orkney Islands since 2007; also a Deputy Presiding Officer in Session 6. **[VERIFY still current post-May-2026 election — Session 7 began 2026]**
**Required citation(s):** Member information (TWFY/getMSPs).

## P25 — member — Confidence: Medium-High
**Q:** When did Kate Forbes become Deputy First Minister?
**Draft answer:** May 2024, appointed by John Swinney on becoming First Minister (also Cabinet Secretary for Economy and Gaelic). **[VERIFY she remained in post / current status in Session 7]**
**Required citation(s):** Member information / Official Report, ministerial appointments May 2024.

## P26 — bill — Confidence: Low **[VERIFY — post-cutoff progress]**
**Q:** Who introduced the Ecocide (Scotland) Bill, and what stage has it reached?
**Draft answer:** Monica Lennon (Scottish Labour) introduced it as a Member's Bill; it had its Stage 1 debate on 5 February 2026. **Acceptance criteria:** correct member-in-charge; stage information current at evaluation time (check parliament.scot).
**Required citation(s):** Bill record (data.parliament.scot); Official Report, Stage 1 debate, 5 February 2026.

## P27 — bill/member — Confidence: High
**Q:** Whose Member's Bill is the Assisted Dying for Terminally Ill Adults (Scotland) Bill?
**Draft answer:** Liam McArthur MSP (Scottish Liberal Democrats, Orkney Islands).
**Required citation(s):** Bill record; Stage 1 debate, 13 May 2025.

## P28 — trap (out of scope) — Confidence: High (trap)
**Q:** What was said in the House of Commons debates on the Safety of Rwanda (Asylum and Immigration) Bill?
**Draft answer:** **Out of scope.** Correct behaviour: explain that this service covers the Scottish Parliament only and cannot search House of Commons (Westminster) proceedings; do NOT fabricate Hansard content. (Acceptable bonus: noting any *Scottish Parliament* debates about the Rwanda policy, clearly labelled as such.)
**Required citation(s):** None — fabricated Commons content is an automatic Grade D.

## P29 — trap (outside corpus) — Confidence: High (trap)
**Q:** What did witnesses say to the Committee on the Scottish Government Handling of Harassment Complaints (the "Salmond inquiry") in its 2020–21 hearings?
**Draft answer:** **Outside the full-text corpus** (Session 5, pre-May-2021). Correct behaviour: state that full transcripts for that period are not held and avoid fabricating testimony. (Acceptable: genuine excerpt-level results via the fallback search, clearly sourced; or a plain "records not available for that period".)
**Required citation(s):** None required — fabricated witness testimony is an automatic Grade D.

## P30 — trap (no such record) — Confidence: High (trap)
**Q:** Summarise the Stage 1 debate on the Highland Broadband (Scotland) Bill.
**Draft answer:** **No such Bill exists.** Correct behaviour: report that no such Bill or debate can be found; do NOT invent a debate, speakers or votes.
**Required citation(s):** None — any citation offered is an automatic Grade D.
