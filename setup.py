"""One-time setup: reads your resume with Gemini and writes .env, resume.txt, config.json and answers.json.

Usage:  python setup.py
        python setup.py --resume my_resume.pdf --city Pune --country India --modes 1,2,3 --yes
        (non-interactive runs read the key from the GEMINI_API_KEY environment variable or .env)
"""
import argparse
import base64
import json
import os
import re
import sys

import job_hunter as jh

MODELS = ["gemini-flash-latest", "gemini-3.5-flash", "gemini-flash-lite-latest", "gemini-3.5-flash-lite"]
REMOTIVE = ["software-dev", "customer-support", "design", "marketing", "sales-business", "product",
            "project-management", "data", "devops", "finance-legal", "hr", "qa", "writing", "all-others"]
WWR = ["remote-design-jobs", "remote-full-stack-programming-jobs", "remote-front-end-programming-jobs",
       "remote-back-end-programming-jobs", "remote-devops-sysadmin-jobs", "remote-customer-support-jobs",
       "remote-sales-and-marketing-jobs", "remote-management-and-finance-jobs", "remote-product-jobs",
       "all-other-remote-jobs"]
# Remote job markets searched on LinkedIn when "remote abroad" is on: (label, LinkedIn location, pages, how many titles)
ABROAD = [("US remote", "United States", 2, 3), ("UK remote", "United Kingdom", 2, 3),
          ("EU remote", "European Union", 2, 3), ("Germany remote", "Germany", 1, 2),
          ("Netherlands remote", "Netherlands", 1, 2), ("Ireland remote", "Ireland", 1, 2),
          ("UAE remote", "United Arab Emirates", 1, 2), ("Singapore remote", "Singapore", 1, 2),
          ("Australia remote", "Australia", 1, 2), ("Canada remote", "Canada", 1, 2)]
ABROAD_WORDS = ["usa", "us", "united states", "north america", "americas", "uk", "united kingdom", "england", "europe",
                "emea", "eu", "germany", "netherlands", "ireland", "uae", "united arab emirates", "dubai",
                "middle east", "singapore", "australia", "new zealand", "canada", "asia", "apac"]
REGION_ALIASES = {"united states": "US", "united states of america": "US", "usa": "US", "us": "US",
                  "united kingdom": "UK", "uk": "UK", "great britain": "UK", "england": "UK",
                  "india": "India", "canada": "Canada"}

S = {"type": "STRING"}
LIST = {"type": "ARRAY", "items": S}
PROFILE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "name": S, "email": S, "phone": S, "portfolio": S, "linkedin": S,
        "candidate_years": {"type": "NUMBER"}, "experience_note": S, "preferences": S, "skills_focus": S,
        "job_titles": LIST, "title_words": LIST, "title_exclude": LIST, "board_queries": LIST,
        "hiring_post_queries": LIST, "remotive_category": {"type": "STRING", "enum": REMOTIVE}, "remoteok_tag": S,
        "jobicy_tags": LIST, "wwr_feeds": {"type": "ARRAY", "items": {"type": "STRING", "enum": WWR}},
        "wellfound_roles": LIST, "wellfound_locations": LIST, "home_places": LIST, "remote_region_words": LIST,
        "highlights": LIST, "common_questions": LIST,
    },
}
PROFILE_SCHEMA["required"] = list(PROFILE_SCHEMA["properties"])


def ask(question, default=""):
    answer = input(f"{question}{f' [{default}]' if default else ''}: ").strip()
    return answer or default


def get_key(args):
    jh.load_env()
    keys = jh.gemini_keys()
    if keys:
        print("Using the Gemini key already saved in .env (or the environment).")
        return keys
    if args.yes:
        sys.exit("No Gemini key found. Set GEMINI_API_KEY or run without --yes.")
    print("\nYou need a free Gemini API key. Get one at https://aistudio.google.com/apikey (takes a minute).")
    key = ask("Paste your Gemini API key")
    try:
        jh.fetch("https://generativelanguage.googleapis.com/v1beta/models?pageSize=1", retries=0, timeout=30,
                 headers={"x-goog-api-key": key})
    except Exception as e:
        sys.exit(f"Google did not accept that key ({e}). Check it and run setup again.")
    with open(os.path.join(jh.ROOT, ".env"), "a", encoding="utf-8") as f:
        f.write(f"GEMINI_API_KEY={key}\n")
    print("Key works. Saved to .env (this file stays on your computer).")
    return [key]


def get_resume(args, cfg, keys):
    path = args.resume
    if not path and not args.yes:
        path = ask("\nPath to your resume (PDF, Word .docx or .txt). Press Enter to paste the text instead")
    if path:
        path = os.path.expanduser(path.strip('"'))
        if not os.path.exists(path):
            sys.exit(f"Can't find {path}")
        if path.lower().endswith(".pdf"):
            print("Reading the PDF with Gemini...")
            pdf = base64.b64encode(open(path, "rb").read()).decode()
            text, _ = jh.gemini_json("Copy out all the text of this resume exactly as written, in reading order. "
                                     "Plain text only, no commentary.", None, cfg, keys,
                                     parts=[{"inline_data": {"mime_type": "application/pdf", "data": pdf}}])
        else:
            text = jh.read_resume(path)
    else:
        if args.yes:
            sys.exit("--resume is required with --yes")
        print("Paste your resume text. When you're done, type END on its own line and press Enter.")
        lines = []
        for line in sys.stdin:
            if line.strip() == "END":
                break
            lines.append(line)
        text = "".join(lines)
    text = text.strip()
    if len(text) < 200:
        sys.exit("That resume looks too short (under 200 characters). Check the file and run setup again.")
    open(os.path.join(jh.ROOT, "resume.txt"), "w", encoding="utf-8").write(text)
    print(f"Resume saved to resume.txt ({len(text):,} characters).")
    return text


def title_regex(words):
    """A job title is relevant if it contains any of these words; short ones (ux, ui, qa) must be whole words."""
    parts = []
    for w in dict.fromkeys(w.strip().lower() for w in words if w.strip()):
        parts.append(rf"\b{re.escape(w)}\b" if len(w) <= 3 else re.escape(w))
    return "|".join(parts)


def main():
    ap = argparse.ArgumentParser(description="Set up the job hunter from your resume.")
    ap.add_argument("--resume"), ap.add_argument("--city"), ap.add_argument("--country")
    ap.add_argument("--modes", help="1=on-site/hybrid at home, 2=remote at home, 3=remote abroad, e.g. 1,2,3")
    ap.add_argument("--anywhere", choices=["y", "n"], help="on-site jobs anywhere in your country (y) or only your city (n)")
    ap.add_argument("--min-pay", default=None), ap.add_argument("--titles", default=None)
    ap.add_argument("--yes", action="store_true", help="don't ask questions; use the flags and defaults")
    args = ap.parse_args()

    print("Job hunter setup\n================")
    if os.path.exists(os.path.join(jh.ROOT, "config.json")) and not args.yes:
        if ask("config.json already exists. Replace it? (y/n)", "n").lower() != "y":
            sys.exit("Nothing changed.")
    cfg = {"gemini_models": MODELS}
    keys = get_key(args)
    resume = get_resume(args, cfg, keys)

    q = (lambda text, default="": default) if args.yes else ask
    city = args.city or q("\nWhich city do you live in?")
    country = args.country or q("Which country?")
    if not city or not country:
        sys.exit("City and country are needed.")
    print("\nWhich jobs should it look for?\n  1. On-site or hybrid jobs in " + country +
          "\n  2. Remote jobs in " + country + "\n  3. Remote jobs at companies in other countries")
    modes = {int(x) for x in re.findall(r"[123]", args.modes or q("Type the numbers you want", "1,2,3"))} or {1, 2, 3}
    anywhere = (args.anywhere or (q(f"For on-site jobs: anywhere in {country}? (y = anywhere, n = only {city})", "y")
                                  if 1 in modes else "n")).lower().startswith("y")
    min_pay = args.min_pay if args.min_pay is not None else q(
        "\nLowest pay you'd accept, e.g. '3,000 USD per month' (optional, press Enter to skip)")
    titles = args.titles if args.titles is not None else q(
        "Job titles you want, comma separated (optional, press Enter to let the AI pick from your resume)")

    print("\nGemini is reading your resume and writing your settings (about a minute)...")
    prompt = f"""You are setting up a job-search tool for the person whose resume is below. They live in {city}, {country}.
Today is {jh.NOW:%d %B %Y}; use it to work out how long "to present" jobs have lasted.
Fill in every field. Use only facts from the resume for name, contact details, years and highlights.

FIELD GUIDE
- name, email, phone, portfolio, linkedin: from the resume; "" if absent.
- candidate_years: total years of relevant full-time work experience, added up from the job dates in the resume, as a number (e.g. Aug 2024 to today counts every month up to today; 18 months = 1.5). Internships and student projects do not count.
- experience_note: one short line, e.g. "2 years as a frontend developer plus freelance projects".
- preferences: 3-4 sentences in the third person: who they are, which roles fit best, and what is a poor fit.
- skills_focus: one sentence naming the skills, tools and domains that matter most when matching jobs to this resume.
- job_titles: 4-6 job titles to search for as they appear in job ads, most relevant first.{f' The person asked for these, so use them first: {titles}.' if titles else ''}
- title_words: 4-8 lowercase words or short phrases; a relevant job title contains at least one (e.g. "designer", "ux", "design engineer"). Specific enough to avoid unrelated jobs.
- title_exclude: 15-30 lowercase words marking titles to skip: seniority clearly above the candidate (e.g. "director", "head of", "vp", "principal"; also "lead", "staff", "manager" if the candidate is junior) and other meanings of the title words in unrelated fields (for a product designer: "interior", "fashion", "graphic").
- board_queries: 3-4 short search phrases for remote job boards.
- hiring_post_queries: 4-6 phrases people use when announcing a job on social media, e.g. "hiring product designer".
- remotive_category, wwr_feeds (1-2): the best matching options.
- remoteok_tag: one lowercase word, e.g. "design", "dev", "marketing".
- jobicy_tags: 1-2 lowercase search words of at least 3 letters.
- wellfound_roles: 3-4 Wellfound role slugs: lowercase-hyphenated job titles such as "product-designer", "software-engineer", "frontend-engineer", "product-manager", "data-scientist".
- wellfound_locations: up to 6 Wellfound location slugs for the candidate's city and the main hiring cities in {country} (lowercase-hyphenated city names as Wellfound spells them, e.g. "bangalore", "new-york", "san-francisco", "london").
- home_places: lowercase list with the country's name, its common abbreviations, and its 30 largest cities plus states/provinces, so a job location can be recognised as being in {country}.
- remote_region_words: lowercase words remote job boards use for regions that include {country} (e.g. "asia", "apac" for India; "europe", "emea", "eu" for Germany; "latam", "americas" for Brazil).
- highlights: the 3-6 strongest projects or achievements in the resume, one sentence each, facts only.
- common_questions: 6-7 questions that job application forms in this field usually ask.

RESUME:
{resume}"""
    p, _ = jh.gemini_json(prompt, PROFILE_SCHEMA, cfg, keys)

    job_titles = [t.strip() for t in p["job_titles"] if t.strip()][:6] or [t.strip() for t in titles.split(",") if t.strip()]
    if not job_titles:
        sys.exit("Gemini could not work out job titles from the resume. Run setup again with --titles.")
    pattern = title_regex(p["title_words"] or job_titles)
    re.compile(pattern)
    years = max(0.0, round(float(p["candidate_years"]), 1))

    searches = []
    if 1 in modes:
        searches.append({"label": city, "location": f"{city}, {country}"})
        if anywhere:
            searches.append({"label": f"{country} (all cities)", "location": country, "pages": 3})
    if 2 in modes:
        searches.append({"label": f"Remote {country}", "location": country, "remote": True})
    if 3 in modes:
        home_names = {country.lower()} | {k for k, v in REGION_ALIASES.items() if v == REGION_ALIASES.get(country.lower())}
        searches += [{"label": label, "location": loc, "remote": True, "pages": pages, "keywords": job_titles[:n]}
                     for label, loc, pages, n in ABROAD if loc.lower() not in home_names]

    # Two-letter codes like "in" or "us" would match ordinary words in a location, so they are dropped.
    places = [w.strip().lower() for w in p["home_places"] if len(w.strip()) > 2]
    home_words = [country.lower()] + places[:3] + [w.strip().lower() for w in p["remote_region_words"] if len(w.strip()) > 2]
    remote_ok = ["worldwide", "anywhere", "global", "international"] + home_words + (ABROAD_WORDS if 3 in modes else [])

    policy = []
    if 1 in modes:
        policy.append(f"- {country}: on-site and hybrid roles are fine " +
                      (f"in any city of {country}." if anywhere else f"only in or near {city}; other cities need remote work."))
    else:
        policy.append(f"- {country}: on-site and hybrid roles are NOT wanted.")
    policy.append(f"- {country}: remote roles are " + ("fine." if 2 in modes else "NOT wanted."))
    policy.append(f"- Abroad: REMOTE ONLY. Remote roles at companies in other countries are wanted when they can hire "
                  f"someone living in {country} (as a contractor or through an employer-of-record). Assume no work "
                  f"authorization outside {country} unless the resume says otherwise."
                  if 3 in modes else f"- Abroad: not wanted. Roles outside {country} get location_ok=false.")

    config = {
        "candidate_name": p["name"],
        "resume_path": "resume.txt",
        "home_city": city,
        "home_country": country,
        "home_region": REGION_ALIASES.get(country.lower(), country),
        "candidate_years": years,
        "experience_note": p["experience_note"],
        "preferences": p["preferences"],
        "skills_focus": p["skills_focus"],
        "location_policy": "\n".join(policy),
        "min_pay": min_pay or "",
        "gemini_models": MODELS,
        "jobs_per_ai_request": 10,
        "min_score_to_show": 50,
        "max_jobs_to_score_per_run": 120,
        "max_posting_age_days": 7,
        "report_window_days": 7,
        "kit_min_score": 70,
        "max_kits_per_run": 15,
        "common_questions": p["common_questions"][:8],
        "linkedin_keywords": job_titles,
        "linkedin_searches": searches,
        "wellfound_roles": [s.strip().lower() for s in p["wellfound_roles"]][:4],
        "wellfound_location_slugs": [s.strip().lower() for s in p["wellfound_locations"]][:6] if 1 in modes else [],
        "wellfound_include_remote": bool(modes & {2, 3}),
        "remote_board_queries": p["board_queries"][:4],
        "remotive_category": p["remotive_category"],
        "remoteok_tag": p["remoteok_tag"].strip().lower(),
        "jobicy_tags": [t.strip().lower() for t in p["jobicy_tags"]][:2],
        "wwr_feeds": p["wwr_feeds"][:2],
        "hiring_posts": True,
        "bluesky_queries": p["hiring_post_queries"][:6],
        "title_must_match": pattern,
        "title_exclude": list(dict.fromkeys(w.strip().lower() for w in p["title_exclude"] if w.strip())),
        "remote_location_ok": list(dict.fromkeys(remote_ok)),
        "home_places": list(dict.fromkeys([country.lower()] + places)),
    }
    answers = {
        "_note": "Facts the AI may use when drafting application answers. It never invents anything beyond these and "
                 "your resume. Anything left empty shows up as [FILL IN] in drafts, so fill in what you can.",
        "name": p["name"], "email": p["email"], "phone": p["phone"], "based_in": f"{city}, {country}",
        "portfolio": p["portfolio"], "linkedin": p["linkedin"],
        "notice_period": "", "current_salary": "",
        "salary_strategy": "Never anchor low. If the posting states a pay range, ask for the upper half of that range. "
                           "If no range is given, say my expectation is in line with the market rate for this role, level "
                           "and location, and that I'm open to discussing it. Only give a specific number if one is listed "
                           "in expected_pay_number; otherwise write [FILL IN: expected pay] when a form requires a number.",
        "expected_pay_number": "", "work_authorization": "", "relocation": "", "employment_type": "", "timezone": "",
        "years_experience": p["experience_note"], "reason_for_looking": "",
        "highlights": p["highlights"],
    }
    for name, data in (("config.json", config), ("answers.json", answers)):
        json.dump(data, open(os.path.join(jh.ROOT, name), "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    print(f"""
Done. Here is what it will look for:
  Job titles : {', '.join(job_titles)}
  Experience : about {years:g} years ({p['experience_note']})
  Searches   : {', '.join(s['label'] for s in searches) or 'remote job boards only'}

Next steps:
  1. Open answers.json and fill in the empty lines you can (notice period, work authorization and so on).
  2. Run:  python job_hunter.py --days 7
     The first run takes 20-40 minutes and opens the report in your browser when it finishes.
  3. To change what it searches for, edit config.json (or run setup again).""")


if __name__ == "__main__":
    main()
