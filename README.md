# Job hunter

A small tool that searches for jobs for you every day, reads each posting with AI, and shows you the ones worth applying to.

You give it two things: your resume and a free Google Gemini key. It does the rest on your own computer.

## What it does

1. **Finds new jobs** on LinkedIn (public job search), Wellfound, and remote job boards (Himalayas, Remotive, RemoteOK, Jobicy, We Work Remotely). It also reads hiring posts on Bluesky and the monthly Hacker News "Who is hiring?" thread.
2. **Scores every job from 0 to 100** against your resume. It checks skills, years of experience asked, whether you can be hired from where you live, and how many people have applied. Each job gets a one-line reason and a warning if something is off, such as "asks for 5+ years".
3. **Drafts your application** for the strong matches (score 70 or more): a cover note, an answer to "why this company", answers to common form questions, a short message for the recruiter, and resume tips for that job. If the company lists the role on its own Greenhouse, Ashby or Lever page, it links you straight to that form and answers the form's real questions.
4. **Opens a report in your browser.** You can filter by region, date posted and competition, search, and mark jobs as applied or hidden.

It never applies for you. You read the drafts, fix them, and send them yourself.

## What you need

- A computer with **Python 3.10 or newer** ([python.org/downloads](https://www.python.org/downloads/)). Nothing else to install.
- A **free Gemini API key** from [aistudio.google.com/apikey](https://aistudio.google.com/apikey). Sign in with a Google account and click "Create API key".
- Your **resume** as a PDF, a Word file (.docx) or plain text.

## Set it up (about 5 minutes)

1. Download this project: click the green **Code** button on GitHub, choose **Download ZIP**, and unzip it. Or run `git clone` if you use git.
2. Open a terminal in the project folder and run:

   ```
   python setup.py
   ```

3. Answer the questions. It asks for your Gemini key, your resume file, your city and country, and which kinds of jobs you want (on-site, remote in your country, remote abroad).
4. Gemini reads your resume and writes your settings: which job titles to search, which titles to skip, your years of experience, and so on. This takes about a minute.
5. Open `answers.json` and fill in the empty lines you can, such as your notice period and work authorization. The AI uses these facts in your application drafts and never makes facts up. Anything you leave empty shows up as **[FILL IN]** in the drafts.

## Run it

```
python job_hunter.py --days 7
```

The first run looks back 7 days and takes 20 to 40 minutes. When it finishes, the report opens in your browser. After that, run it once a day:

```
python job_hunter.py
```

Each run only shows jobs it has not shown you before. The report is saved as `latest.html` in the project folder, and new matches are also added to `tracker.csv`, which you can open in Excel to track your applications.

### Run it automatically every morning

**Windows:** open a terminal in the project folder and run this once. It runs the search every day at 9:00.

```
schtasks /create /tn "Job Hunter" /tr "%cd%\run.bat" /sc daily /st 09:00
```

**Mac or Linux:** run `chmod +x run.sh`, then `crontab -e`, and add this line (change the path to where you put the folder):

```
0 9 * * * /path/to/job-hunter/run.sh
```

## Other commands

| Command | What it does |
|---|---|
| `python job_hunter.py --report-only` | Rebuilds the report from saved results without searching again |
| `python job_hunter.py --kits-only` | Drafts application answers for recent strong matches, then rebuilds the report |
| `python job_hunter.py --rescore` | Scores this week's jobs again, useful after you change your settings |
| `python job_hunter.py --no-open` | Does not open the browser at the end |
| `python job_hunter.py --no-ai` | Skips Gemini and ranks by job title only |

## Change what it looks for

Everything is in `config.json`, which setup wrote for you. The lines you are most likely to change:

- `linkedin_keywords`: the job titles it searches for.
- `title_must_match` and `title_exclude`: which job titles are kept and which are skipped.
- `linkedin_searches`: the places it searches.
- `min_score_to_show`: the lowest score that appears in the report (50 by default).
- `candidate_years`: your years of experience. Jobs asking for much more than this are scored lower.

You can also run `python setup.py` again to start over.

## Good to know

- **Gemini's free plan has daily limits** (about 20 requests per model per day). The tool spreads its work across four models and sends many jobs in one request, so a normal day fits. If the limit runs out, the jobs left over are scored on the next run. You can add a second key to `.env` as `GEMINI_API_KEY_2=...`.
- **Your data stays on your computer.** Your resume and the job texts are sent to Google's Gemini to be read, and nowhere else. Your key, resume, settings and results are never uploaded. They are also listed in `.gitignore`, so they stay out of git if you fork this project.
- **Scores are a guide, not a guarantee.** Always read the posting before you apply.
- **Be gentle with the job sites.** The tool reads public pages slowly and only a few hundred a day. It is meant for one person's own job search. Check that this kind of use is fine under each site's terms before you rely on it.
- **Wellfound can come back empty** for some roles or cities, or when it blocks automated visits. The tool skips it and carries on.

## Files

| File | Purpose |
|---|---|
| `setup.py` | One-time setup from your resume |
| `job_hunter.py` | The search, scoring, drafts and report |
| `report_template.html` | The report page |
| `run.bat`, `run.sh` | Used by the daily schedule |
| `.env`, `resume.txt`, `config.json`, `answers.json` | Created by setup. Yours only. |
