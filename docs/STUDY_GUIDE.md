# Deploying an AI App: Claude, MCP, and GitHub — An Introduction
## A Study Guide & Guided Deployment Workshop

**Source repository:** https://github.com/gwest-enterprisemaps/GWest-Porsche-911-Valuator
**Level:** Introductory (AI/API/GitHub 101 — no prior experience with any of them assumed)
**Time budget:** 4–6 hours across six modules
**You will need:** a computer with a terminal, a web browser, and about $5 for AI usage credits
**The goal:** by the end, a Porsche 911 valuation app that *you* deployed is running at a public **onrender.com** web address, and you can explain what every part of it does.

---

## How to use this guide

Each module has two halves. The **Background** half explains a piece of the system in plain language — what it is, why it exists, and why it was built this way. The **Activity** half is one step of a single continuous project: getting this app from someone else's repository onto the public internet under your own accounts.

The activities only ever ask you to *deploy and observe* — you will not write or modify code. Understanding comes from reading the code with a map in hand and then watching it run. Do the modules in order; each activity depends on the one before it.

Here is the whole journey in one line:

> get the code → put it in *your* GitHub repository from your desktop → connect an AI key → deploy on Render → open your onrender.com URL and value a Porsche.

### What you are deploying, in one paragraph

The app values Porsche 911 sports cars. A user enters their car's year, trim, and mileage, optionally drops in photos, and receives a market valuation report. Behind the scenes, an AI model (Anthropic's Claude) inspects the photos, looks up Porsche facts from a small built-in knowledge service, searches the live web for comparable sales, and returns a structured report. It sounds complex; by Module 2 you will see it is a small number of understandable pieces.

---

# Module 1 — The big picture: what all the parts are

### Background: four words you need first

**API (Application Programming Interface).** A way for programs to talk to each other over the internet by sending structured requests and getting structured replies. When this app "calls the Claude API," it sends a package of text and images to Anthropic's servers and gets the model's response back. No magic — just a well-defined request/reply format.

**Model.** The AI itself — Claude, in this case. It lives on Anthropic's computers, not yours. Your app rents its intelligence per request, which is why you will need an API key (Module 4) and a few dollars of credit.

**Tool use.** Modern AI models can do more than chat. You can hand the model a list of *tools* — functions it is allowed to ask for, like "look up the baseline price of a 2011 Carrera S" — and it decides when to use them. The model never runs the tool itself; it *asks*, your app runs the function, and the answer is fed back. This request-run-reply cycle is called an **agentic loop**, and it is the heart of this app.

**MCP (Model Context Protocol).** An open standard for packaging tools so *any* AI application can use them. Think of it as USB for AI: build a tool server once, plug it into this web app, or Claude Desktop, or anything else that speaks MCP. This project includes its own small MCP server full of Porsche knowledge — that is one of the main things the repository showcases.

### The four runtime pieces

```
Browser ──form + photos──▶ FastAPI app ──request──▶ Claude (Anthropic's API)
                              │   ▲                    │        ▲
                              │   └── "run this tool" ◀┘        │
                              ▼                                 ▼
                       MCP server                          web search
                       (Porsche facts)                  (live sale prices)
```

1. **The browser page** — a simple form (year, trim, mileage, photos) and a report display. Plain HTML and JavaScript; view-source friendly on purpose.
2. **The FastAPI app** — a small Python web server. It receives the form, checks the input is sane, and manages the conversation with Claude.
3. **The MCP server** — a Porsche encyclopedia exposed as five tools (generation facts, baseline prices, a mileage calculator, value drivers, valid trims). It runs quietly alongside the app.
4. **Claude + web search** — the reasoning happens on Anthropic's side. Claude also has a search tool that Anthropic runs on its own servers, which is how the app finds what similar cars sold for *this month* even though the model's built-in knowledge has a cutoff date.

### Why the app remembers nothing (and why that helps you)

The app is **stateless**: no database, no saved files. Photos are held in memory just long enough to show Claude, then discarded. This was a deliberate design choice with three payoffs. Privacy: user photos never persist anywhere. Simplicity: nothing to install, back up, or corrupt. And — most relevant to you — **deployability**: a stateless app can be stopped and restarted by its host at any moment without losing anything, which is exactly how free cloud hosting behaves (you will see this firsthand in Module 6 as "cold starts").

### Activity 1 — set up your two free accounts

Everything downstream needs these, so do them now:

1. Create a **GitHub** account at github.com (free). GitHub is where code lives and where Render will fetch your app from. Pick a professional username — it appears in your public URLs.
2. Create a **Render** account at render.com (free, no credit card). Choose "Sign up with GitHub" — this links the two accounts, which Module 5 relies on.
3. Open the source repository (link at top) in your browser. Read the README from top to bottom, including the architecture diagram. Don't worry about understanding every term — Modules 2–5 will fill them in.
4. On paper, sketch the four-piece diagram above from memory and label what each piece does.

**Checkpoint:** you can name the four pieces and state, in one sentence each, why the app is stateless and what MCP is for.

---

# Module 2 — A guided tour of the codebase

### Background: reading a repository like a map

Before deploying code you should be able to walk through it and say what each file is *for* — not necessarily how every line works. Here is the full layout; nothing is hidden:

```
porsche-911-valuator/
├── README.md            ← the front door: what/why/how, architecture diagram
├── requirements.txt     ← the Python libraries the app needs, one per line
├── .env.example         ← template showing which secrets/settings the app expects
├── .gitignore           ← files git must NEVER upload (secrets, caches)
├── Dockerfile           ← recipe for packaging the app into a container (Module 5)
├── render.yaml          ← instructions Render reads to deploy it (Module 5)
├── app/
│   ├── main.py          ← the web server: receives the form, checks input
│   └── agent.py         ← the AI brain: talks to Claude, runs the tool loop
├── mcp_server/
│   ├── server.py        ← the five Porsche tools, exposed via MCP
│   └── data.py          ← the Porsche facts themselves (plain Python data)
├── static/
│   ├── index.html       ← the page the user sees
│   ├── app.js           ← browser logic: photo previews, submit, render report
│   └── style.css        ← appearance
└── docs/                ← architecture notes and this guide
```

### The five files worth actually reading

**`mcp_server/data.py` — knowledge as data.** Scroll it. Every 911 generation from 1989 onward, its known mechanical issues, baseline price ranges per trim, and lists of things that raise or lower value. Notice there is no clever code here — it is a reviewable, editable encyclopedia. Putting facts in a data file (instead of burying them in AI prompt text) means a human can audit and correct them. Note the honest comment at the top: these numbers are *illustrative anchors*, and the AI is told to trust live market data over them.

**`mcp_server/server.py` — knowledge as tools.** Each function has a `@mcp.tool()` decorator. That one line turns an ordinary Python function into an MCP tool that any AI host can discover and call. Read the docstrings — those descriptions are literally what Claude reads when deciding which tool to use. One function deserves special attention: `adjust_for_mileage` does percentage arithmetic in Python rather than letting the AI do math. Language models are unreliable calculators; the design principle is **code does arithmetic, the model does judgment**.

**`app/agent.py` — the agentic loop.** The most important file. Find three things: the `SYSTEM_PROMPT` (a numbered six-step method the AI must follow — ground yourself in Porsche facts, adjust for mileage, study the photos, search the web for comparable sales, reconcile, report); the `REPORT_TOOL` (a rigid template — called a schema — that forces the AI's final answer into exact named fields like `estimated_value_low_usd` and `confidence`, instead of a free-form essay the app would have to guess its way through); and the `while` loop in `valuate()` that carries messages back and forth until the report arrives.

**`app/main.py` — the bouncer.** Before anything reaches the AI, this file checks: is the year plausible? mileage under 500,000? photos under 5 MB and actually images? has this visitor already made 5 requests this minute? That last one — **rate limiting** — exists because every valuation costs real money in AI usage; without it, one prankster with a loop could drain the owner's credit. Also find the startup check that refuses to boot if the API key is missing: better to fail loudly at deploy time than mysteriously at 2 a.m.

**`static/app.js` — the browser side.** Find `renderReport()`. Notice it reads exactly the fields defined in `REPORT_TOOL` — the AI's answer template and the web page's display logic are two ends of one contract.

### Activity 2 — the code scavenger hunt (read-only)

Using only GitHub's web interface (click into files; press `t` to search filenames), find and write down:

1. The five tool names the MCP server offers, and which file defines their *data* versus their *functions*.
2. The six steps of the system prompt, paraphrased in your own words.
3. The line in `app/main.py` that sets the maximum number of photos, and the line in `agent.py` that caps how many web searches Claude may run. (Both are cost/abuse controls — connect each to *why*.)
4. The three files that mention `ANTHROPIC_API_KEY`, and what role each plays (template, startup check, deploy config).
5. In `.gitignore`: what is being excluded, and what could go wrong if `.env` were *not* listed there?

**Checkpoint:** given any file name in the repo, you can say in one sentence what it is for — that is the level of understanding deployment requires.

---

# Module 3 — Git and GitHub: putting the code in *your* repository, from your desktop

### Background: what version control actually is

**Git** is a program on your computer that tracks versions of a folder. Each saved snapshot is a **commit** — a permanent record of "the files looked exactly like this, at this time, saved by this person, for this reason." A folder tracked by git is a **repository** ("repo"). **GitHub** is a website that hosts copies of repositories so they can be shared, showcased, and — critically for us — fetched by deployment services like Render.

Four commands cover 90% of daily git use:

| Command | Plain meaning |
|---|---|
| `git init` | "Start tracking this folder." |
| `git add .` | "Stage everything — include these files in the next snapshot." |
| `git commit -m "message"` | "Take the snapshot, labeled with this message." |
| `git push` | "Upload my snapshots to GitHub." |

One security concept before you push: GitHub no longer accepts your account password from the command line. Instead you create a **Personal Access Token (PAT)** — a long generated string that acts as a scoped, expiring, revocable password. Treat any token like cash: short expiry, revoke it when done, and never save it into a file that git tracks.

### Activity 3 — your repo, committed and pushed from your desktop

**Step 1 — install git** (skip if `git --version` in your terminal prints a version). macOS: run `xcode-select --install`. Windows: install "Git for Windows" from git-scm.com and use the "Git Bash" terminal it provides.

**Step 2 — get the code.** On the source repository page: green **Code** button → **Download ZIP**. Unzip it somewhere sensible, e.g. `~/projects/porsche-911-valuator`. (Downloading the ZIP rather than cloning is deliberate — you get clean files with no history, so the repo you build next is 100% yours.)

**Step 3 — create your empty repository on GitHub.** github.com → **+** (top right) → **New repository**. Name: `porsche-911-valuator`. Visibility: **Public** (it is a showcase). Leave every initialization checkbox **unchecked** — no README, no .gitignore, no license. You want it truly empty; your desktop files are about to fill it.

**Step 4 — create your token.** GitHub → Settings → Developer settings → **Personal access tokens → Tokens (classic)** → Generate new token (classic). Check exactly one scope box: **`repo`**. Expiry: 7 days. Copy the `ghp_...` string somewhere temporary. (Why classic instead of the newer "fine-grained" type? Fine-grained tokens default to read-only access and fail pushes with a confusing error — see the troubleshooting box below. Classic + `repo` scope is the beginner-proof path.)

**Step 5 — commit and push.** In your terminal (replace `YOUR-USERNAME`):

```bash
cd ~/projects/porsche-911-valuator

git init -b main                                   # start tracking, name the branch "main"
git add .                                          # stage every file
git status                                         # LOOK: verify no .env or secret is listed
git commit -m "Initial commit: Porsche 911 Valuator (Claude + MCP)"

git remote add origin https://github.com/YOUR-USERNAME/porsche-911-valuator.git
git push -u origin main                            # username: YOUR-USERNAME, password: the ghp_ token
```

**Step 6 — verify and tidy.** Refresh your repository page: all files should be there and the README should render with its architecture diagram. Then revoke the token (Settings → Developer settings → tokens → Delete) — its job is done, and Render will not need it.

> **Troubleshooting box: the 403 "Permission denied" saga.** When this very app was first pushed, three tokens in a row failed with `403: Permission to ... denied` before one worked. The lessons, in the order you should check them: (1) a fine-grained token's default access is *"Public repositories — read-only"* — it can authenticate but never push; (2) a classic token with **no scope boxes checked** also authenticates but can do nothing — the `repo` box must actually be ticked; (3) the diagnostic that cuts through guesswork is the difference between **401** ("I don't know who you are" — bad token) and **403** ("I know exactly who you are, and the answer is no" — bad *permissions*). If you hit 403, the token is fine; its scopes are not.

**Checkpoint:** your public GitHub URL shows the full codebase under your name, with one commit authored by you, and the token is revoked.

---

# Module 4 — The AI key: how apps pay for intelligence

### Background: API keys, and why this one costs money

An **API key** is a secret string that tells a service who is calling so it can meter and bill the usage. Your app's key is the single secret it needs.

Two facts that trip up almost every newcomer:

1. **The Claude Console is not the Claude app.** A claude.ai or Claude Desktop subscription is a *chat product* for humans. Programs use the **Claude Platform**, managed at **console.anthropic.com**, with separate signup and separate billing. Your subscription, if you have one, contributes nothing here.
2. **API usage is metered per token** (roughly, per word-piece processed), prepaid from credits. For this app, each valuation sends photos (images are token-expensive), runs a few conversation turns, and performs up to 4 web searches — a few cents total. The repo defends the wallet in layers you saw in Module 2: rate limits per visitor, a cap on loop turns, a cap on searches, and photo size/count limits.

**Where secrets live** is the other half of this module. The repo shows the pattern: `.env.example` documents *which* settings exist (committed, harmless), the real `.env` holds actual values locally (gitignored, never uploaded), and in production the key lives in the host's **environment variables** — typed once into Render's dashboard, injected into the running app, never written into code or git history. If you remember one security rule from this course: *secrets go in the environment, never in the repository.*

### Activity 4 — get your key

1. Go to **console.anthropic.com** → sign up (any email; it is separate from claude.ai).
2. **Settings → Billing** → add $5 of credits. (Optionally set a monthly spend limit of $5 too — a nice safety net.)
3. **API Keys → Create Key** → name it `porsche-valuator` → copy the `sk-ant-...` string immediately (it is shown exactly once).
4. Park it somewhere temporary and private — a password manager note is ideal. It gets typed into Render in the next module, then you can delete your temporary copy.
5. Open `.env.example` in your repo and confirm you can now explain each line in it.

**Checkpoint:** you hold an `sk-ant-...` key, can state the Console-vs-claude.ai distinction, and can recite where secrets do and do not belong.

---

# Module 5 — Deployment: from your repository to a public URL

### Background: what "deploying" means

So far the app exists as files. **Deploying** means getting it running on a server that is always on and reachable by anyone. You will use **Render**, a hosting service whose free tier is ideal for showcase projects. Two files in your repo do the heavy lifting:

**`Dockerfile` — the packing recipe.** A **container** is a self-contained box holding the app plus everything it needs (Python, the libraries in `requirements.txt`) so it runs identically anywhere. Read the Dockerfile — it is seven meaningful lines: start from a slim Python image, install the requirements, copy in `app/`, `mcp_server/`, and `static/`, and state the command that starts the server. Render follows this recipe to build your app. Notice the MCP server needs no separate arrangement: it is started *by* the app as a child process, so it ships inside the same box.

**`render.yaml` — the deployment instructions.** Read it; it is ten lines. It tells Render: this is a web service, build it with Docker, use the free plan, check `/api/health` to confirm each deploy is alive (that's the health endpoint from `app/main.py` — now you know who it's for), set the rate limit, and — the line worth studying — `ANTHROPIC_API_KEY: sync: false`, which means *"prompt the human for this secret at deploy time; never store it in the repository."* Infrastructure described in a committed file like this is called **Infrastructure as Code**: your deployment setup is versioned, reviewable, and reproducible, just like the app.

### Activity 5 — deploy

1. Go to **dashboard.render.com** → **New +** → **Blueprint**.
2. Connect your GitHub account if prompted, and select **your** `porsche-911-valuator` repository. Render finds `render.yaml` automatically and shows what it plans to create.
3. When prompted for `ANTHROPIC_API_KEY`, paste your `sk-ant-...` key from Module 4.
4. Click **Apply / Deploy** and *watch the build logs stream* — do not skip this. You will see the Dockerfile executing line by line: the Python image downloading, `pip install` working through `requirements.txt`, the container starting, then Render probing `/api/health` until it answers. This log is the Dockerfile made visible.
5. When the service shows **Live**, note your URL: `https://porsche-911-valuator-XXXX.onrender.com`.
6. **Use your app.** Open the URL, enter a car — say, a 2011 Carrera S, 42,000 miles, manual — add a photo or two if you have them, and submit. While it thinks (10–30 seconds; it is orchestrating Claude, five MCP tools, and live web searches), open the **Logs** tab in Render and watch your request being processed. Then read your valuation report and connect each section on screen — the range, confidence, value drivers, comparable sales — back to the `REPORT_TOOL` fields you found in Module 2.

**Checkpoint:** a valuation report, produced by infrastructure you deployed, visible at a public onrender.com URL you can send to anyone.

---

# Module 6 — Living with your deployment

### Background: what the free tier teaches you

Your app is now a real, operating web service, and the free tier's quirks are a compact operations education:

**Cold starts.** After ~15 minutes without visitors, Render spins your container down. The next visitor waits roughly 30 seconds while it boots. This is not a defect — it is the economics of free hosting, and it is *possible* only because the app is stateless: nothing was lost when the container stopped. You designed for this in Module 1 without knowing it.

**Auto-deploy.** Render watches your GitHub repository. Any `git push` to `main` triggers an automatic rebuild and release. Your commit history *is* your release history — which is why commit messages like "Initial commit: Porsche 911 Valuator" beat "stuff".

**Logs are your eyes.** The app prints what it is doing (which MCP tools loaded at startup, each valuation request, any errors) to standard output, and Render captures it. When something misbehaves in production, logs are where every investigation starts.

**Your spend is bounded.** Trace the full chain of cost protection you now operate: Render hosting is free → each valuation costs cents → visitors are limited to 5/minute and 30/day each → the agent stops after at most 12 turns and 4 searches → your Console credits are prepaid, so the absolute worst case is a drained $5, never a surprise bill.

### Activity 6 — operate it

1. **Measure a cold start.** Leave the app untouched for 20+ minutes, then time how long the page takes to load. Then reload immediately — note the difference. Explain both numbers using the Background above.
2. **Read your startup logs.** In Render's Logs tab, find the line listing the five MCP tools discovered at boot. That line is `app/main.py`'s lifespan code executing — the moment the app and the MCP server shook hands.
3. **Check the health endpoint** a deployment platform relies on: open `https://YOUR-URL.onrender.com/api/health` in your browser and interpret each field it returns.
4. **Trigger the rate limiter** honestly: submit six valuations inside a minute and observe the polite refusal on the sixth. Find the matching 429 events in the logs. You are watching `app/main.py`'s wallet-defense working in production.
5. **Verify your usage bill.** In console.anthropic.com, look at usage: confirm your test valuations cost roughly what Appendix B predicts.
6. **Share it.** Put the onrender.com link and the GitHub link side by side at the top of your repo's README (edit it directly on GitHub — pencil icon — and commit; then watch Render auto-deploy your first change).

**Checkpoint:** you have observed a cold start, read production logs, seen the rate limiter fire, reconciled your AI bill, and triggered an auto-deploy — the full basic operations loop.

---

## Where to go next

This guide deliberately stopped at deployment. When you are ready for the 201 material, the codebase is your syllabus: run the app locally with `uvicorn` and a `.env` file; plug `mcp_server` into Claude Desktop and call the Porsche tools from a chat; read `docs/architecture.md` for the deeper design discussion; then try changing something small (a value in `data.py`, a sentence in the system prompt) and watch a `git push` carry it live.

---

# Appendix A — Glossary (101 edition)

- **API:** a structured way for programs to request services from each other over the internet.
- **API key:** a secret string identifying who is calling an API, used for access and billing.
- **Repository (repo):** a folder whose history is tracked by git; hosted publicly on GitHub.
- **Commit:** one saved snapshot of the repository, with author, time, and message.
- **Push:** uploading your local commits to GitHub.
- **PAT (Personal Access Token):** a generated, revocable, expiring password for command-line GitHub access.
- **Model:** the AI itself (Claude), running on Anthropic's servers, rented per request.
- **Tool use / agentic loop:** the cycle where the model asks for a function to be run, the app runs it, and the result is fed back until a final answer emerges.
- **MCP (Model Context Protocol):** an open standard for packaging tools so any AI app can discover and call them.
- **Schema / structured output:** a rigid template the model's final answer must fit, so software can read it without guessing.
- **Stateless:** the app keeps nothing between requests — no database, no stored photos.
- **Environment variable:** a named setting given to a program by its host at startup; where secrets belong.
- **Container / Dockerfile:** a self-contained runnable box holding the app and all its dependencies / the recipe that builds it.
- **Infrastructure as Code:** describing deployment setup in a committed file (`render.yaml`) instead of clicking it together by hand.
- **Cold start:** the boot delay when a free-tier host restarts your idled container for a new visitor.
- **Rate limiting:** capping requests per visitor to protect cost and stability.

# Appendix B — What a valuation costs (order of magnitude)

Each valuation = one conversation with Claude involving: your photos (images are the expensive part), several loop turns (a feature called prompt caching makes the repeated instructions cheap), up to 4 web searches, and a handful of MCP tool calls (free — they run in your own container). Total: **a few cents**. Your $5 of credits comfortably covers a semester of demos. Every cap that keeps it bounded is one you located in Activity 2.

# Appendix C — Security habits you practiced

- Secrets live in environment variables (Render dashboard) or a gitignored `.env` — never in committed files. `git status` before every commit is the habit that enforces it.
- Tokens and keys are scoped (one `repo` box, one named API key), short-lived, and revoked the moment their job is done.
- Anything ever pasted into a chat, email, or ticket is considered exposed — revoke and regenerate.
- Endpoints that cost money are rate-limited; user input is validated at the boundary; errors shown to visitors are generic while details go to the logs.
