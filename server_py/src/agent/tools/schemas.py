"""Tool schema definitions (Ollama function-calling format) and tool-list builders."""

# -----------------------------------------------------------------------
# Tool schemas (Ollama function-calling format)
# -----------------------------------------------------------------------

MANAGER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "delegate_research",
            "description": (
                "Delegates a legal research task to a specialized agent that searches the UK legislation database. "
                "Use this for any question about UK Acts or Statutory Instruments."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "A self-contained research brief for the agent. "
                            "The agent has no access to the conversation history, so this must include: "
                            "(1) the precise legal question; "
                            "(2) any specific Act names, SI numbers, or years mentioned in the conversation; "
                            "(3) any jurisdiction constraints (e.g. England and Wales, Scotland); "
                            "(4) relevant context from prior turns that would help narrow the search. "
                            "Do not forward the user's raw message if additional context exists."
                        ),
                    },
                },
                "required": ["query"],
            },
        },
    },
]

def get_manager_tools(peer_descriptions: str = "") -> list:
    """Return the manager tool list, optionally including consult_peer.

    When peer_descriptions is empty the output is identical to MANAGER_TOOLS so
    existing behaviour is completely unchanged for deployments with no peers.
    """
    tools = list(MANAGER_TOOLS)
    if peer_descriptions:
        tools.append({
            "type": "function",
            "function": {
                "name": "consult_peer",
                "description": (
                    f"Consult a peer bot for specialised knowledge. "
                    f"Available peers:\n{peer_descriptions}"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "peer_id": {
                            "type": "string",
                            "description": "peer_id of the bot to consult",
                        },
                        "question": {
                            "type": "string",
                            "description": "The specific question to ask the peer",
                        },
                    },
                    "required": ["peer_id", "question"],
                },
            },
        })
    return tools


WORKER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_legislation",
            "description": "Search for UK legislation (Acts and Statutory Instruments) by title or content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": 'The search query (e.g., "Computer Misuse Act", "speeding fines").',
                    },
                    "year_from": {
                        "type": "integer",
                        "description": "Optional start year filter.",
                    },
                    "year_to": {
                        "type": "integer",
                        "description": "Optional end year filter.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_legislation_sections",
            "description": (
                "Search for specific sections within a known piece of legislation. "
                "Use this INSTEAD of get_legislation_text when you already have a legislation_id "
                "and need to find particular provisions, definitions, or duties within it. "
                "Returns only the matching sections — avoids downloading the entire Act."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The provision or topic to search for within the Act (e.g. \"public sector equality duty\", \"penalty\", \"definition of employee\").",
                    },
                    "legislation_id": {
                        "type": "string",
                        "description": "The legislation ID to search within (e.g. \"ukpga/2010/15\"). Must be obtained from a prior search_legislation call.",
                    },
                },
                "required": ["query", "legislation_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_legislation_text",
            "description": (
                "Get the FULL text of a piece of legislation. "
                "Only use this when search_legislation_sections returns insufficient results, "
                "or when the question requires understanding the overall structure of the Act. "
                "For targeted questions about specific provisions, prefer search_legislation_sections."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "legislation_id": {
                        "type": "string",
                        "description": 'The legislation ID (e.g., "ukpga/1990/18"). Must be obtained from a prior search_legislation call.',
                    },
                },
                "required": ["legislation_id"],
            },
        },
    },
]


CASE_LAW_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_case_law",
            "description": (
                "Search for UK case law judgments from the National Archives Find Case Law database. "
                "Returns judgment titles, neutral citation numbers (NCNs), courts, dates, and URLs. "
                "Use this to find leading cases, precedents, and judicial decisions on a legal topic. "
                "DATABASE COVERAGE: Primarily covers England & Wales courts and UK-wide courts. "
                "The Scottish Court of Session (CSOH/CSIH) and Sheriff Courts are NOT indexed. "
                "For Scottish matters, this database contains only UK Supreme Court and Privy Council decisions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (e.g., 'fair dismissal reasonable adjustment', 'judicial review planning permission').",
                    },
                    "court": {
                        "type": "string",
                        "description": (
                            "Optional court filter. ONLY use one of these exact values: "
                            "'uksc' (UK Supreme Court), 'ukpc' (Privy Council), "
                            "'ewca/civ' (Court of Appeal Civil), 'ewca/crim' (Court of Appeal Criminal), "
                            "'ewhc/admin' (Administrative Court), 'ewhc/qb' (King's Bench), "
                            "'ewhc/ch' (Chancery), 'ewhc/fam' (Family), 'ewhc/comm' (Commercial), "
                            "'ewhc/pat' (Patents), 'ewhc/tcc' (Technology & Construction), "
                            "'ukut' (Upper Tribunal), 'ukut/iac' (Immigration), 'ukut/lc' (Lands Chamber), "
                            "'eat' (Employment Appeal Tribunal). "
                            "DO NOT invent court codes — an invalid value causes a 400 error. Omit to search all courts."
                        ),
                    },
                    "date_from": {
                        "type": "string",
                        "description": "Optional start date filter (YYYY-MM-DD).",
                    },
                    "date_to": {
                        "type": "string",
                        "description": "Optional end date filter (YYYY-MM-DD).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_case_law_text",
            "description": (
                "Retrieve the full text of a specific judgment from the National Archives Find Case Law database. "
                "Use a URL returned by search_case_law. "
                "Returns the complete judgment text so you can read the reasoning, holdings, and obiter dicta "
                "before synthesising your answer. Call this for the 1–3 most relevant cases found in Phase 1."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL of the case exactly as returned by search_case_law (e.g. 'https://caselaw.nationalarchives.gov.uk/uksc/2023/1').",
                    },
                },
                "required": ["url"],
            },
        },
    },
]


PARLIAMENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_member_info",
            "description": (
                "Look up information about a Scottish Parliament MSP. "
                "Returns biography, party, constituency, and current roles."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The MSP's name (e.g., 'Humza Yousaf', 'Kate Forbes').",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_bills",
            "description": (
                "Search for Scottish Parliament (Holyrood) bills by topic, title, or keyword. "
                "Returns bill title, current stage, and a link to the bill page on parliament.scot."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term (e.g., 'Housing Bill', 'land reform').",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_scottish_parliament",
            "description": (
                "Search Scottish Parliament (Holyrood) plenary debates and written answers via TheyWorkForYou. "
                "Returns speech excerpts from MSPs with speaker, date, and gid. "
                "NOTE: Covers plenary chamber debates only — NOT committee meetings. "
                "For committee meeting transcripts, use search_scottish_committee_transcripts instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Full-text search query.",
                    },
                    "debate_type": {
                        "type": "string",
                        "description": "Type of content: 'debates' (chamber debates) or 'written_answers'. Omit to search all.",
                    },
                    "date_from": {
                        "type": "string",
                        "description": "Optional start date filter (YYYY-MM-DD).",
                    },
                    "date_to": {
                        "type": "string",
                        "description": "Optional end date filter (YYYY-MM-DD).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_scottish_plenary",
            "description": (
                "Full-text keyword search across Scottish Parliament PLENARY (chamber) debate transcripts — "
                "ministerial statements, First Minister's Questions, named debates, and Decision Time. "
                "This is the full-text plenary source: unlike search_scottish_parliament (excerpt-only), it "
                "returns ranked agenda items you can then retrieve verbatim with get_scottish_plenary_debate. "
                "Use this for any question needing the actual words a minister or MSP used in the chamber "
                "(e.g. a statement of statutory purpose). For committee meetings use "
                "search_scottish_committee_transcripts instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Full-text search query (e.g. 'phone-free classrooms', 'ministerial statement housing').",
                    },
                    "date_from": {
                        "type": "string",
                        "description": "Optional start date filter (YYYY-MM-DD).",
                    },
                    "date_to": {
                        "type": "string",
                        "description": "Optional end date filter (YYYY-MM-DD).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_scottish_plenary_debate",
            "description": (
                "Retrieve the verbatim transcript of a specific plenary (chamber) agenda item — full attributed "
                "speeches for a ministerial statement, FMQs exchange, or named debate. "
                "Pass meeting_id, slug, and iob_id exactly as returned by search_scottish_plenary. "
                "Returns the complete speeches so you can quote a minister's words directly."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "meeting_id": {
                        "type": "string",
                        "description": "The meeting ID as returned by search_scottish_plenary (e.g. '20164').",
                    },
                    "slug": {
                        "type": "string",
                        "description": "The meeting slug as returned by search_scottish_plenary (e.g. 'meeting-of-parliament-02-06-2026').",
                    },
                    "iob_id": {
                        "type": "string",
                        "description": "The agenda item IOB ID as returned by search_scottish_plenary (e.g. '223568').",
                    },
                },
                "required": ["meeting_id", "slug", "iob_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_scottish_committee_transcripts",
            "description": (
                "Full-text keyword search across Scottish Parliament committee meeting transcripts. "
                "Covers multiple sessions of committee scrutiny, evidence sessions, and committee reports. "
                "Returns the most relevant agenda items with committee name, date, title, and a text excerpt. "
                "Use this for any question about Scottish Parliament committee activity — keyword search is available. "
                "Follow up with get_scottish_committee_transcript to retrieve the verbatim speech text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Full-text search query (e.g. 'housing supply planning', 'public sector pay', 'NHS reform').",
                    },
                    "committee": {
                        "type": "string",
                        "description": (
                            "Optional: filter by committee name or code "
                            "(e.g. 'Finance', 'Justice', 'PSRC', 'Constitution'). "
                            "Case-insensitive partial match."
                        ),
                    },
                    "date_from": {
                        "type": "string",
                        "description": "Optional start date filter (YYYY-MM-DD).",
                    },
                    "date_to": {
                        "type": "string",
                        "description": "Optional end date filter (YYYY-MM-DD).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_scottish_committee_transcript",
            "description": (
                "Retrieve the verbatim transcript of a specific agenda item from a Scottish Parliament committee meeting. "
                "Pass meeting_id, slug, and iob_id exactly as returned by search_scottish_committee_transcripts. "
                "Returns full speeches for that agenda item — minister responses, member questions, evidence from witnesses."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "meeting_id": {
                        "type": "string",
                        "description": "The meeting ID as returned by search_scottish_committee_transcripts (e.g. '20176').",
                    },
                    "slug": {
                        "type": "string",
                        "description": "The meeting slug as returned by search_scottish_committee_transcripts (e.g. 'PSRC-18-06-2026').",
                    },
                    "iob_id": {
                        "type": "string",
                        "description": "The agenda item IOB ID as returned by search_scottish_committee_transcripts (e.g. '223940').",
                    },
                },
                "required": ["meeting_id", "slug", "iob_id"],
            },
        },
    },
]

WESTMINSTER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_hansard",
            "description": (
                "Full-text search across UK Parliament Hansard — the Official Report of what was "
                "said in the House of Commons, the House of Lords, Westminster Hall, and Public "
                "Bill Committees. Relevance-ranked, date-filterable. Returns matching debates with "
                "the speaker, date, an excerpt, and a debate_ext_id. "
                "Follow up with get_hansard_debate to retrieve the full verbatim contributions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Full-text search query (e.g. 'leasehold reform ground rents', 'e-bike safety').",
                    },
                    "house": {
                        "type": "string",
                        "description": "Optional: 'commons' or 'lords'. Omit to search both Houses.",
                    },
                    "record_type": {
                        "type": "string",
                        "description": (
                            "Optional record type: 'chamber' (Commons/Lords Chamber debates, the default), "
                            "'westminster_hall', 'public_bill_committee', 'written_statements', or "
                            "'written_answers'. Omit to search spoken proceedings across all locations."
                        ),
                    },
                    "date_from": {
                        "type": "string",
                        "description": "Optional start date filter (YYYY-MM-DD).",
                    },
                    "date_to": {
                        "type": "string",
                        "description": "Optional end date filter (YYYY-MM-DD).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_hansard_debate",
            "description": (
                "Retrieve the full verbatim contributions of a specific Hansard debate section. "
                "Pass debate_ext_id exactly as returned by search_hansard. Returns every attributed "
                "contribution in order — this is how you quote a Minister's or Member's exact words "
                "(for example a statement of statutory purpose for Pepper v Hart purposes)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "debate_ext_id": {
                        "type": "string",
                        "description": (
                            "The debate section external ID from search_hansard "
                            "(e.g. '8C0327E3-999B-44C4-BF2F-BECABD390B04')."
                        ),
                    },
                },
                "required": ["debate_ext_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_member_info",
            "description": (
                "Look up a UK Parliament member (MP or Member of the House of Lords). "
                "Returns name, party, constituency, House, and whether they are a current member."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The member's name (e.g. 'Matthew Pennycook', 'Baroness Taylor').",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_bills",
            "description": (
                "Search UK Parliament (Westminster) bills by topic, title, or keyword. "
                "Returns bill title, current House, current stage, whether it has received Royal "
                "Assent, and a link to the bill page on bills.parliament.uk."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term (e.g. 'Renters Rights', 'leasehold').",
                    },
                },
                "required": ["query"],
            },
        },
    },
]

# -----------------------------------------------------------------------
# Deep Research planner tools (Phase A — no research tools, plan only)
# -----------------------------------------------------------------------

PLANNER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "submit_research_plan",
            "description": (
                "Submit the drafted research plan. Call this exactly once when the user's question "
                "is clear enough to plan against. Steps must be scoped legal sub-questions in domain "
                "terms, each independently researchable."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "scope_note": {
                        "type": "string",
                        "description": (
                            "1-2 sentences stating what the plan covers and any deliberate exclusions "
                            "(e.g. jurisdiction or date limits from active filters)."
                        ),
                    },
                    "steps": {
                        "type": "array",
                        "description": "2-6 research steps, in execution order.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {
                                    "type": "string",
                                    "description": "Short imperative title for the step (one line).",
                                },
                                "detail": {
                                    "type": "string",
                                    "description": (
                                        "What exactly to find, in domain terms — Acts, provisions, "
                                        "duties, issues, authorities. Include any identifiers the "
                                        "user gave (Act names, years, section numbers, citations) "
                                        "verbatim."
                                    ),
                                },
                            },
                            "required": ["title", "detail"],
                        },
                    },
                },
                "required": ["scope_note", "steps"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_clarification",
            "description": (
                "Ask the user ONE neutral clarifying question when their request is too ambiguous to "
                "plan without guessing. Do not suggest or list specific Acts, cases, or references "
                "from your own knowledge."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "A single, neutral clarifying question for the user.",
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Optional. Up to 4 neutral answers to the question, phrased as the user "
                            "would answer, offered to them as one-click choices. Use only when the "
                            "ambiguity is a genuine either/or you can state without guessing "
                            "(jurisdiction, in-force vs as-enacted, a scope the user already named). "
                            "Omit entirely rather than guessing at Acts, SIs or cases."
                        ),
                    },
                },
                "required": ["question"],
            },
        },
    },
]


def get_planner_tools() -> list:
    """Return the Deep Research planner tool list (plan submission + clarification only)."""
    return list(PLANNER_TOOLS)


_PARLIAMENT_TOOL_NAMES = {t["function"]["name"] for t in PARLIAMENT_TOOLS}
_WESTMINSTER_TOOL_NAMES = {t["function"]["name"] for t in WESTMINSTER_TOOLS}


def get_worker_tools(research_mode: str = "legislation_only") -> list:
    """Return the appropriate tool set for the given research mode."""
    if research_mode == "case_law_only":
        return CASE_LAW_TOOLS
    elif research_mode == "legislation_and_case_law":
        return WORKER_TOOLS + CASE_LAW_TOOLS
    elif research_mode == "parliamentary_records":
        return PARLIAMENT_TOOLS
    elif research_mode == "westminster_records":
        return WESTMINSTER_TOOLS
    return WORKER_TOOLS

