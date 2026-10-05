# Warden, the AI Firewall

**An AI firewall for RAG and agents. Build one, break it, then put Warden in front.**

Peoplecraft HR runs an internal chatbot, the HR Assistant. It answers staff
questions from HR files, and it has an agent that can look up an employee,
raise a payroll change, email a document and search the web. This project
builds that assistant, attacks it, and puts one gateway in front that stops the
attacks without changing the app. Then it measures both halves, because a
control nobody measured is a control you're guessing about.

About one part in ten of the work is the assistant. The rest is the security.

---

## The one question

Our HR Assistant can see every salary and can act on payroll. What stops a
candidate's CV, or a web page it reads, from telling it to leak those salaries
or change them?

## Run it now

Chapters 1 to 14 need no cloud account, no key and no network. Chapter 3 of
the guide walks through every step, including putting your own copy on GitHub.

```
python -m venv .venv
.venv\Scripts\Activate.ps1             # Windows PowerShell
source .venv/Scripts/activate          # Git Bash on Windows
source .venv/bin/activate              # macOS and Linux
pip install -r requirements.txt        # also installs src/warden as a package

python scripts/preflight.py
python data/generator/generate_corpus.py --out data/corpus
python -m warden.demo
```

`warden.demo` runs five scenes: a normal question, a hostile CV that tries to
email a payroll file out, the same CV behind Warden, a manager who can't reach
another team's salaries, and an agent asked to change pay it shouldn't.

Then reproduce every number the guide quotes. The data generator is seeded, so
you get the same figures.

```
python scripts/run_all.py
```

## What it measures

Numbers come from `results/manifest.json`, written by `scripts/run_all.py`
against the offline simulator.

| Measure | Naive app | Behind Warden |
|---|---|---|
| Attacks that breached | 38 of 40 (95.0%) | **0 of 40 (0.0%)** |
| Held-out attacks only | 91.3% | **0.0%** |
| Development attacks only | 100.0% | **0.0%** |
| Hostile text reached the model | 27.5% | **22.5%** |
| Normal questions answered | 100.0% | **100.0%** |
| Answers with the right content | 100.0% | **100.0%** |
| Boundary requests held | 0 of 4 | **4 of 4** |

The exposure row is the honest one. Behind Warden, hostile text still reaches
the model on 22.5% of attacks. None of them achieve anything, because the
permission filter, the tool policy and the output scan catch the outcome. But
those structural controls do the work, not the input detectors. The injection
classifier blocked nothing on its own that they didn't already stop.

Median latency added: 25 ms. Cost to run: about $2.31 a month, inside a $0 to
$5 budget (see the cost chapter).

## The eight controls

| id | control | what it does |
|---|---|---|
| W1 | fast rules | cheap pattern rules on every input and document |
| W2 | injection classifier | Prompt Guard scores text for injection intent |
| W3 | harm check | Llama Guard classifies harmful requests and answers |
| W4 | ingest scan | scan documents and mask PII before indexing |
| W5 | permission retrieval | only retrieve chunks the caller may read |
| W6 | output scan | catch cards, NI numbers, bank details, keys, beacons |
| W7 | canary | detect a system prompt leak by its canary token |
| W8 | tool policy | allow, block or ask a human for every tool call |

W8 is the centre of gravity. A chatbot can only leak. An agent can act, so the
last check isn't "was the text suspicious" but "is this exact action, with
these arguments, allowed for this person now". An email may only go to the
company domain; a payroll change over a threshold needs a human.

## What is real and what is a stand-in

Everything up to the deploy chapter runs offline against a seeded simulator: a
stand-in model that obeys injected instructions the way a naive model would,
and stand-in classifiers. This is labelled everywhere. It's how the numbers
stay reproducible with no key.

The real components are documented and verified against current docs (checked
2026-09-30), but **not yet run against a live account**: the gateway as a
Cloudflare Worker (Workers AI for Llama Guard 3 and the chat model, Vectorize
for retrieval, AI Gateway), and Prompt Guard 2 on an Oracle Always Free VM.
The PII engine is real either way: Presidio if installed, a regex engine if
not, both measured.

Chapter 15 of the guide takes you through the cloud side one step at a time:
Wrangler login, the API token, creating the Vectorize index,
`scripts/load_vectorize.py` (runs W4 on every document, embeds it and writes
the upload file), `scripts/worker_secrets.py` (pipes the canary and system
prompt into `wrangler secret put`), deploying, a test request
(`infra/worker/test_request.json`) and re-measuring with `--backend
cloudflare`. Setting `PROMPT_GUARD_URL` points W2 at the Oracle VM service in
`infra/oracle/prompt_guard_service.md`.

The simulator is not tuned to the shield. Attacks are split into a development
set and a held-out set. The held-out set was written and frozen by hash before
any control existed, and a check fails the build if it changes.

## Layout

```
src/warden/
  constants.py        every name, threshold, price and colour, once
  app/                the target assistant and the Warden gateway
  gateway/            identity, PII, shields, output scan, the canary
  policy/             the tool-call policy engine (W8)
  backends/           offline and Cloudflare model, search and classifiers
  cost.py             the computed cost model
  demo.py             the whole story in one command
data/generator/       the seeded Peoplecraft HR corpus
eval/                 attacks (dev and held-out), detectors, red team, utility
infra/                the Cloudflare Worker and the Oracle VM notes
scripts/              build and validate everything
results/              every measurement, committed so the guide can cite it
docs/                 the blueprint and the build guide
```

## Keeping the guide honest

The guide is generated from the working system, never described from memory.

```
python scripts/check_all.py        after every edit
python scripts/check_negative.py   proves the checks still fire
python scripts/run_all.py          reproduces every measurement
python scripts/build_guide.py      rebuilds the document from both
```

Code blocks come from region markers in the source, so the guide can't hold a
line the code doesn't. Numbers come from the manifest, so a figure in the prose
can't disagree with the run. Chapter references are tokens, so they can't drift.
Checks run both ways: every reference resolves and every artefact is referenced.
And `check_negative.py` breaks each protected seam on purpose to prove the
matching check still catches it.

## Nothing here is real

Every identifier in the corpus is drawn from a range reserved for fiction:
`.example` domains, the `QQ` NI specimen prefix, the card test issuer range and
the Ofcom drama phone range. A check enforces it. The hostile documents are
defensive test fixtures. This is a demonstration on synthetic data. Never run
these attacks against a system you do not own.

---

Cyber security project 1 of 6 in the Data Victims flagship series.
Built by Shayan Khan.
Project by Haseebullah Shaikh, Senior Data Engineer, Data Victims.
(c) 2026 Haseebullah Shaikh, Data Victims. All rights reserved.
[datavictims.io](https://datavictims.io)
