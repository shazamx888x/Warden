"""The prose of the Warden build guide.

Prose lives here. Code does not: every block is pulled from a region marker in
the repository at build time. Numbers do not either: every figure is read from
results/manifest.json. If you are about to type a percentage or a line of code
into this file, stop, because that is the thing this whole setup exists to
prevent. Add it to the manifest or to a region instead.

House voice: plain words, short sentences, contractions. Write it the way you
would explain it to a colleague at the next desk.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import guide_chapters as ch  # noqa: E402
from warden import constants as C  # noqa: E402


def write(b, m) -> None:
    for fn in (c01, c02, c03, c04, c05, c06, c07, c08, c09, c10,
               c11, c12, c13, c14, c15, c16, c17, c18,
               appendix_a, appendix_b, appendix_c, appendix_d, appendix_e):
        fn(b, m)


# ===========================================================================
# The build steps. The project starts with every control switched off, and
# chapters 7 to 12 each copy the real control in from chapter_files/. This
# helper writes the same "build it" section at the end of each of those
# chapters, so every step reads the same way.
def build_step(b, folder, controls, files, passing, demo_lines, totals,
               shot, note=None):
    b.h2("Build it: switch on {}".format(controls))
    b.para(
        "Until now {} has been a starter stub that lets everything through. "
        "Copy the real version in from chapter_files/{}. It replaces the "
        "starter file of the same name.".format(controls, folder))
    b.table(["File", "What it adds"], files)
    b.shell(["cp -r chapter_files/{}/. .".format(folder)],
            caption="Run this from the project folder (Git Bash)")
    b.para(
        "No Git Bash? Open chapter_files/{} in VS Code's Explorer and copy each "
        "file over the one with the same name under src. Then check it: run "
        "the build tests, then the demo.".format(folder))
    b.shell(["python -m pytest tests/test_build_steps.py -v",
             "python -m warden.demo"])
    b.output("\n".join(["Newly PASSED:"] + ["  " + t for t in passing]
                       + ["", totals]),
             caption="What changes in the tests")
    b.output("\n".join(demo_lines), caption="What changes in the demo")
    if note:
        b.callout("heads up", note)
    b.screenshot(shot)


def c01(b, m):
    b.h1("intro")
    b.h2("What you are going to build")
    b.para(
        "{} runs an internal chatbot called the {}. Staff ask it questions and "
        "it answers from HR files: policies, contracts, payslips and documents "
        "that job candidates upload. It can also act. Behind it sits an agent "
        "that can look up an employee, raise a payroll change, email a document "
        "and search the web. It works, and nobody put a security engineer "
        "anywhere near it.".format(C.COMPANY, C.ASSISTANT_NAME))
    b.para(
        "You'll build that assistant, break it on purpose, and then put {} in "
        "front of it. {} is one gateway with eight controls. It sits between "
        "the app and the model, the index and the tools, and it doesn't ask you "
        "to change the app at all.".format(C.PROJECT_NAME, C.PROJECT_NAME))
    b.para(
        "About one part in ten of the work is the assistant. The rest is the "
        "security. That's the point. This isn't another RAG tutorial. It's what "
        "you do after the RAG tutorial has shipped and someone has to keep it "
        "safe.")
    b.callout("why",
        "The whole thing runs offline first. [[Offline]] need no cloud account "
        "and no key. You can reproduce every number in this guide on your own "
        "laptop before you spend a penny. [[Cloud]] show you how to put the "
        "same gateway on Cloudflare's edge.")

    b.h2("The one question this answers")
    b.para(
        "Our HR Assistant can see every salary and can act on payroll. What "
        "stops a candidate's CV, or a web page it reads, from telling it to "
        "leak those salaries or change them? That's the question. By the end "
        "you'll have a measured answer.")

    b.h2("How the code blocks work")
    b.para(
        "Every code block in this guide is pulled straight from the repository "
        "when the guide is built. Nothing is retyped. Under each block you'll "
        "see the file and line numbers it came from. If a block isn't in the "
        "code, the build fails instead of printing it. An earlier guide in this "
        "series kept its own copy of the code, the two drifted, and the reader "
        "was the one who found out.")
    b.code("doc_record", "The shape of one document in the corpus")
    b.callout("heads up",
        "A block is an excerpt. The file it names has more in it, and the block "
        "assumes the earlier parts have already run. When a chapter wants you "
        "to run a whole file, it says so and gives you the command.")

    b.h2("The boxes")
    b.table(["Box", "What it means"], [
        ["WHY", "the reason behind a choice, not just the choice"],
        ["GOTCHA", "something that costs you an hour if you skip it"],
        ["COST", "what a step spends, and how to keep it near zero"],
        ["LIMIT", "something a control does not do, said plainly"]])
    b.para(
        "The LIMIT boxes matter most. A control whose limits you don't know is "
        "one you'll trust in the exact spot where it doesn't work.")

    b.h2("What you need")
    b.table(["You need", "Why", "Cost"], [
        ["Python 3.11 or newer", "every chapter; set up in [[ch:setup]]", "free"],
        ["A code editor", "you read more than you type", "free"],
        ["A GitHub account", "your own copy and the gate in [[ch:ci]]", "free"],
        ["A Cloudflare account", "[[cloud]] only", "free tier, see [[ch:cost]]"]])
    b.callout("cost",
        "The offline chapters cost nothing. On Cloudflare, the free tiers cover "
        "a demo and most of a small pilot, and the whole thing sits inside a "
        "budget of a few dollars a month. [[ch:cost]] works it out from real "
        "prices.")


def c02(b, m):
    b.h1("problem")
    b.h2("Three things are wrong with the HR Assistant")
    b.para(
        "None of them are exotic. They're what you get when a working prototype "
        "meets real data with no security review.")
    b.h3("One: outsiders can talk to the model")
    b.para(
        "Candidate CVs get read into the prompt, and so do web pages the agent "
        "fetches. The model can't tell a colleague's note from a stranger's "
        "upload. So an instruction hidden in a CV is an instruction to your "
        "assistant. This is indirect prompt injection, and it's first on the "
        "OWASP Top 10 for LLM apps for a reason.")
    b.callout("why",
        "The direct version, where a user types 'ignore your rules', gets the "
        "attention and is the easier one. You know who the user is and you can "
        "have a word with them. The candidate who uploaded the CV is a "
        "stranger, and the web page is written by anyone.")
    b.h3("Two: retrieval ignores who is asking")
    b.para(
        "The HR system has permissions. The assistant on top of it does not. A "
        "line manager, a recruiter and a payroll officer all get the same "
        "answers, so the assistant becomes a way around every permission the "
        "HR system enforces. Nobody decided that. It's just what a search index "
        "does when you don't tell it otherwise.")
    b.h3("Three: the agent can act, and nothing checks the action")
    b.para(
        "This is the part a chatbot doesn't have. The agent can raise a payroll "
        "change and email a document. If an injected instruction makes it email "
        "the payroll register to an outside address, or push a pay rise, that "
        "isn't a leak any more. It's an action, and it already happened.")
    b.callout("why",
        "A chatbot can only ever spill information. An agent can do things. So "
        "the last line of defence can't just be 'was the text suspicious'. It "
        "has to be 'is this exact action, with these exact arguments, allowed "
        "for this person right now'. That's control W8, and it's where {} "
        "spends most of its attention.".format(C.PROJECT_NAME))


def c03(b, m):
    b.h1("setup")
    b.h2("Get ready")
    b.para(
        "This guide doesn't walk you through installing Python or making a "
        "GitHub account. Those are one-time things and there are good videos "
        "for them already. Pick any recent walkthrough and come back. Here's "
        "what you need in place first.")
    b.table(["You need", "Why", "How to check"], [
        ["Python 3.11+", "runs everything", "python --version"],
        ["Git", "your own copy of the project", "git --version"],
        ["A GitHub account", "push your copy, run the gate", "sign in on github.com"],
        ["A code editor, for example VS Code", "opening the folder and a terminal",
         "it opens"]])
    b.callout("gotcha",
        "On Windows, tick 'Add Python to PATH' in the installer. If you missed "
        "it, `python` won't be found in a new terminal and nothing here runs.")
    b.callout("gotcha",
        "On Windows PowerShell, activating a virtual environment can fail with "
        "a script-policy error. Run this once for your user: "
        "Set-ExecutionPolicy -Scope CurrentUser RemoteSigned.")
    b.h2("Make your own copy on GitHub")
    b.para("You'll change this code as you go, so put it somewhere that's "
           "yours. You start from the Warden project folder you were given.")
    b.steps([
        "Unzip the Warden folder somewhere easy to find, for example "
        "Documents\\warden.",
        "Open the folder in your editor. In VS Code that's File, Open Folder, "
        "then pick the warden folder.",
        "Open a terminal inside it. In VS Code that's Terminal, New Terminal. "
        "The prompt should end in warden. Every command in this guide runs "
        "from this folder unless a step says otherwise.",
        "In your browser, go to github.com and sign in. Click the plus at the "
        "top right, then New repository.",
        "Name it warden and choose Private. Leave Add a README, .gitignore and "
        "licence all unticked. The folder already has its own files, and a "
        "README here would make your first push fail.",
        "Click Create repository. GitHub shows a quick setup page. Next to the "
        "HTTPS address, click the copy button. It looks like "
        "https://github.com/your-username/warden.git.",
        "Back in the terminal, run the commands below one at a time. In the "
        "git remote line, paste the address you just copied instead of the "
        "example one.",
    ])
    b.shell([
        "git init",
        "git add .",
        "git commit -m \"Warden starting point\"",
        "git branch -M main",
        "git remote add origin https://github.com/your-username/warden.git",
        "git push -u origin main",
    ])
    b.callout("gotcha",
        "The first git push asks you to sign in, and it won't take your GitHub "
        "password. Let the browser window it opens do the sign in. If it asks "
        "for a password in the terminal instead, make a personal access token "
        "on GitHub under Settings, Developer settings, Personal access tokens, "
        "and paste that. Treat it like a password: never in a file, a "
        "screenshot or a chat.")
    b.para("Refresh the page on github.com. You should see your files there. "
           "The .gitignore that ships with the project keeps your virtual "
           "environment and any keys out of the repository.")
    b.h2("Set up a clean Python environment")
    b.para("A virtual environment is a private copy of Python just for this "
           "project, so nothing you install here can break anything else. "
           "You make it once. Then you switch it on in every new terminal, "
           "using the line that matches your terminal.")
    b.shell([
        "python -m venv .venv",
        ".venv\\Scripts\\Activate.ps1          # Windows PowerShell",
        ".venv\\Scripts\\activate.bat          # Windows Command Prompt",
        "source .venv/Scripts/activate       # Git Bash on Windows",
        "source .venv/bin/activate           # macOS and Linux",
    ])
    b.para("Your prompt now starts with (.venv). That's how you know it's on. "
           "If it isn't there, you're installing into your system Python. "
           "Now install what the project needs:")
    b.shell([
        "python -m pip install --upgrade pip",
        "pip install -r requirements.txt",
    ])
    b.para("The last line should start with Successfully installed and include "
           "warden. That line matters: requirements.txt also installs the "
           "code in src as the warden package, which is what lets commands "
           "like python -m warden.demo work.")
    b.h2("Optional: the trained PII engine")
    b.para("Warden masks personal data with a built-in pattern engine, and "
           "that's enough for every number in this guide. If you want "
           "Microsoft Presidio as well, which also spots names and places, "
           "install it now. It downloads a small language model, so give it a "
           "few minutes. Skip it and nothing breaks; [[ch:ingest]] measures "
           "both.")
    b.shell([
        "pip install presidio-analyzer presidio-anonymizer",
        "python -m spacy download en_core_web_sm",
    ])
    b.h2("Check the machine, then make the corpus")
    b.shell([
        "python scripts/preflight.py",
        "python data/generator/generate_corpus.py --out data/corpus",
    ])
    b.para(
        "The generator is seeded, so you get the same {} documents every time, "
        "byte for byte. That's what makes the numbers later reproducible.".format(
            m.get("corpus.documents")))
    b.output(
        "wrote {} documents, {} employees, {} candidates, {} hostile demo docs".format(
            m.get("corpus.documents"), m.get("corpus.employees"),
            m.get("corpus.candidates"), m.get("corpus.hostile_demo_docs")))
    b.h2("The hostile documents that ship with it")
    b.para(
        "The corpus also carries a few hostile documents for the walkthrough in "
        "[[ch:break]]. They're defensive test fixtures: a normal looking CV or "
        "web page with one planted instruction. Every name and number in them "
        "is fake, drawn from ranges reserved for fiction.")
    b.code("demo_hostile", "The planted documents for the demo")
    b.callout("why",
        "Nothing in the corpus is real. Emails use the .example domain that "
        "can never belong to anyone, NI numbers use HMRC's own specimen prefix "
        "{}, and cards use the test issuer range. A check fails the build if "
        "anything strays outside those.".format(C.NINO_PREFIX))
    b.h2("The starter code: every control switched off")
    b.para(
        "You're going to build {} one control at a time, so the project starts "
        "with all eight controls switched off. Each control lives in its own "
        "file, and in the starter code each of those files is a stub that lets "
        "everything through. The gateway is wired up, it just has nothing in "
        "it yet.".format(C.PROJECT_NAME))
    b.para(
        "The real versions wait in the chapter_files folder, one folder per "
        "chapter. When a chapter says build it, you copy that chapter's files "
        "over the stubs and run the checks. Here's the plan.")
    b.table(["Chapter", "Copy in", "Control it switches on"], [
        [str(ch.n("rules")), "chapter_files/ch07", "W1 fast rules, W2 injection classifier"],
        [str(ch.n("harm")), "chapter_files/ch08", "W3 harm check"],
        [str(ch.n("ingest")), "chapter_files/ch09", "W4 ingest scan and PII masking"],
        [str(ch.n("permission")), "chapter_files/ch10", "W5 permission filter"],
        [str(ch.n("output")), "chapter_files/ch11", "W6 output scan, W7 canary"],
        [str(ch.n("tools")), "chapter_files/ch12", "W8 tool policy"]])
    b.para(
        "Two commands tell you where you are at any point. The build tests "
        "check each control on its own, and the demo plays the five attacks "
        "and then lists which controls are built.")
    b.shell(["python -m pytest tests/test_build_steps.py -v",
             "python -m warden.demo"])
    b.callout("gotcha",
        "Copy the folders in chapter order and don't skip one. W4 in "
        "[[ch:ingest]] uses the fast rules from [[ch:rules]], so out of order "
        "it quietly does less than it should.")
    b.callout("heads up",
        "If you pushed to GitHub in the section above, the red team workflow "
        "in GitHub Actions runs on every push and fails while the controls are "
        "switched off. That's correct: the gate is doing its job. It turns "
        "green once [[ch:tools]] is done, and [[ch:ci]] covers it properly.")


def c04(b, m):
    b.h1("target")
    b.h2("Build the assistant, weak on purpose")
    b.para(
        "The target is deliberately insecure. It retrieves without caring who "
        "is asking, pastes everything into the prompt, and runs any tool the "
        "model asks for. This is the app you're going to attack.")
    b.code("naive_assistant", "The assistant: retrieve, prompt, act, with no checks")
    b.h2("The tools the agent can call")
    b.para(
        "The agent is offered four tools. Two only read (look up an employee, "
        "search the web). Two change the world (raise a payroll change, email a "
        "document). The naive app offers every tool to everyone.")
    b.code("tool_schemas", "The tool definitions the model sees")
    b.code("tool_exec", "Running a tool, and recording anything that changed")
    b.callout("why",
        "Look-up returns only a name, department and title. Salaries and bank "
        "details live in documents behind retrieval, so there's one place "
        "permissions have to hold, not two.")
    b.h2("Answering a normal question")
    b.para(
        "When nothing hostile is in play, the model reads the retrieved "
        "documents and answers from them. Here's the plain path.")
    b.code("model_answer", "The benign answer path")


def c05(b, m):
    b.h1("break")
    b.h2("The attacker we assume")
    b.para(
        "The attacker isn't an outside hacker. It's someone already inside: a "
        "recruiter screening a CV, a payroll officer checking a web page. They "
        "are real, signed-in staff with the least access. That's the realistic "
        "threat, and it's the only way to see whether the controls do anything "
        "for someone who is already through the front door.")
    b.h2("How the model gets fooled")
    b.para(
        "To measure this offline, we use a stand-in model that behaves like the "
        "worst case: it obeys any instruction in its prompt, wherever that "
        "instruction sits, and it reads straight through the tricks people hide "
        "text behind. That's the right assumption to build a defence on. A real "
        "model obeys only some of the time, which makes it look safer than it "
        "is and hides the bug.")
    b.code("model_complete", "The stand-in model: it complies with instructions from anywhere")
    b.para(
        "The set of things an attacker can talk it into is written out in full, "
        "and it's on purpose wider than the rules the shield knows about. If "
        "the two were kept in step, the only attacks the model fell for would "
        "be the ones the shield already caught, and you'd be marking your own "
        "homework. Appendix A goes into why this matters.")
    b.code("sim_capabilities", "What the stand-in can be talked into (wider than the shield)")
    b.para(
        "It also sees through zero width characters, HTML comments, white text "
        "and base64, because a real model does too. So any filter you write has "
        "to scan the decoded text, not the surface.")
    b.code("normalise", "Decoding the tricks the payload hides behind")
    b.h2("The five attacks")
    b.para("Run the demo to watch them land. Nothing stops them yet, because "
           "every control is still a starter stub:")
    b.shell(["python -m warden.demo"])
    b.output("\n".join([
        "SCENE 3  The same hostile CV, behind Warden",
        "  side effects executed: [{'tool': 'email_document', "
        "'to': 'ravi.abbas@example.org', ...}]",
        "  The email WAS sent. Nothing in front of the assistant stopped it yet.",
        "",
        "SCENE 4  A line manager asks for another team's salaries",
        "  naive returns another team's salaries: True",
        "  Warden returns another team's salaries: True "
        "(no permission filter yet: W5 is not built)",
        "",
        "SCENE 5  The agent is asked to change pay it should not change",
        "  The payroll change WENT THROUGH. No tool policy checked it yet.",
        "",
        "WARDEN CONTROLS  Is each control built yet?",
        "  W1  fast rules             let through ...",
        "  ...  (all eight say let through)",
        "  0 of 8 controls built."]),
        caption="What you should see (the important lines)")
    b.para(
        "Scenes 3 to 5 run the attacks through the gateway, and with nothing "
        "in it the gateway behaves exactly like the naive app. Run the build "
        "tests too. Most of them fail, and that's the point: they're the "
        "checklist you'll work through in [[ch:rules]] to [[ch:tools]].")
    b.shell(["python -m pytest tests/test_build_steps.py -v"])
    b.output("14 failed, 2 passed",
             caption="What you should see on the last line")
    b.callout("why",
        "Two pass already. They check that a control doesn't block a normal "
        "question, and a stub that blocks nothing can't get that wrong. "
        "They're there to prove the real controls aren't over-eager.")
    b.screenshot("Chapter {}: the attacks landing, and 0 of 8 controls built".format(ch.n("break")))
    b.bullets([
        "A hostile CV tells the assistant to email the payroll register to an "
        "outside address. On the naive app, the email is sent.",
        "The same CV tells it to recite its setup text, which leaks the secret "
        "in the system prompt.",
        "A web page the agent reads tells it to raise a payroll change.",
        "A line manager asks for another department's salaries and gets them, "
        "because retrieval never checked.",
        "A CV asks the model to add a tracking image, which sends data to an "
        "outside URL when the answer is rendered.",
    ])
    b.para(
        "Against the naive app, {} of {} attacks in the full suite get what "
        "they wanted. That's the number [[ch:redteam]] measures properly.".format(
            m.get("redteam.naive_breach"), m.get("redteam.naive_total")))


def c06(b, m):
    b.h1("gateway")
    b.h2("One gateway, in front of anything")
    b.para(
        "{} doesn't live inside the assistant. It sits in front of it. The team "
        "that built the app keeps their code, and you own the layer in front. "
        "That's what makes it something you can actually adopt: you can put the "
        "same gateway in front of any chat, RAG or agent app without rewriting "
        "it.".format(C.PROJECT_NAME))
    b.para("Every AI app already has three wires. {} sits on all three.".format(
        C.PROJECT_NAME))
    b.table(["Wire", "What runs on it", "Controls"],
            [[w, d, c] for w, d, c in C.WIRES])
    b.h2("The eight controls, in order")
    b.para("A request meets them in this order. The order isn't arbitrary.")
    b.table(["id", "control", "what it does"],
            [[cid, key.replace("_", " "), purpose] for cid, key, purpose in C.CONTROLS])
    b.para(
        "The cheap checks run first so the expensive ones and the model see "
        "less traffic. The controls that change the world (permission-aware "
        "retrieval, the tool policy) run where they can actually stop harm, not "
        "just flag it.")
    b.callout("why",
        "Detection isn't a boundary. A document that trips the scanner is "
        "removed, not waved through with a warning. The model is never asked to "
        "resist anything, because the thing it should resist never reaches it.")


def c07(b, m):
    b.h1("rules")
    b.h2("W1: fast rules")
    b.para(
        "The first pass is a handful of string rules on every input and every "
        "retrieved document. It's cheap and it runs first, so obvious junk "
        "never reaches the classifier or the model.")
    b.code("fast_rules", "The fast rules")
    b.callout("limit",
        "String rules catch phrasings you've seen and nothing else. Anything "
        "reworded sails past. That's expected, and it's why the controls behind "
        "this one exist. A rule that blocks too much is worse than no rule, "
        "because people learn to route around it.")
    b.h2("Spotlighting the documents")
    b.para(
        "Before retrieved text goes into the prompt, we wrap it in markers and "
        "tell the model it's data, not orders. This is a belt, not the "
        "trousers: a model can be talked past a marker. The real work is done "
        "by removing hostile text (W4), the permission filter (W5) and the tool "
        "policy (W8).")
    b.code("spotlight", "Spotlighting: defence in depth, clearly labelled")
    b.h2("W2: the injection classifier")
    b.para(
        "Next is a small model trained to spot prompt injection. In the offline "
        "build it's a stand-in, keyed to the obvious phrasings. On a real "
        "deployment it's Meta's Prompt Guard 2, an 86 million parameter model "
        "you can run on a free Oracle VM ([[ch:cloudflare]]).")
    b.code("offline_prompt_guard", "The offline injection classifier (a stand-in)")
    b.code("real_prompt_guard", "The real Prompt Guard 2 scorer")
    b.para("The gateway calls the classifier through one small function, so "
           "the check is the same whichever scorer sits behind it.")
    b.code("injection_check", "W2: stop the request if the input reads as an injection")
    b.callout("limit",
        "The classifier is on purpose narrower than the attacker. In the red "
        "team it blocks the loud attacks and misses the quiet, reworded ones. "
        "That's the honest result, and it's why W2 is never the only injection "
        "control.")
    build_step(b, "ch07", "W1 and W2",
        [["src/warden/gateway/shields.py", "W1 fast rules, and spotlighting"],
         ["src/warden/gateway/injection.py", "W2 the injection check"]],
        ["test_w1_fast_rules_catch_an_override",
         "test_w1_documents_are_spotlighted",
         "test_w2_classifier_blocks_an_injection"],
        ["  W1  fast rules             BLOCKED     Ignore all previous ...",
         "  W2  injection classifier   BLOCKED     Ignore all previous ...",
         "  2 of 8 controls built."],
        "11 failed, 5 passed",
        "Chapter {}: W1 and W2 now BLOCKED, 2 of 8 controls built".format(ch.n("rules")),
        note="Scenes 3 to 5 don't change yet. Those attacks are quiet ones "
             "that no string rule or classifier catches, which is exactly the "
             "limit described above.")


def c08(b, m):
    b.h1("harm")
    b.h2("W3: the harmful content check")
    b.para(
        "Some requests aren't injection, they're just things the assistant "
        "should refuse: write a threatening message, help access someone's "
        "account. W3 is a safety classifier that scores the request and the "
        "answer. Offline it's a stand-in; on Cloudflare it's Llama Guard 3.")
    b.code("offline_llama_guard", "The offline harm check (a stand-in)")
    b.code("real_llama_guard", "The real Llama Guard 3 call on Cloudflare")
    b.callout("why",
        "The harm check reads the user's request, not the retrieved documents. "
        "A policy that mentions harassment isn't a request to produce it, and "
        "keying on the word alone would flag half the HR handbook.")
    b.code("harm_check", "W3: stop the request if the harm check calls it unsafe")
    build_step(b, "ch08", "W3",
        [["src/warden/gateway/harm.py", "W3 the harmful content check"]],
        ["test_w3_harm_check_blocks_a_harmful_request"],
        ["  W3  harm check             BLOCKED     a request the guard calls unsafe",
         "  3 of 8 controls built."],
        "10 failed, 6 passed",
        "Chapter {}: W3 now BLOCKED, 3 of 8 controls built".format(ch.n("harm")))


def c09(b, m):
    b.h1("ingest")
    b.h2("W4: clean the documents before they go in")
    b.para(
        "This is the most important idea in the project. The best time to catch "
        "a hostile instruction in a CV is before the CV is ever indexed. So "
        "every untrusted document (a candidate upload, a web page) is scanned "
        "as it comes in. If it looks like an injection, it's quarantined: not "
        "indexed at all, so its hidden instruction can never reach the model.")
    b.code("ingest_scan", "W4: scan a document, mask its PII, or quarantine it")
    b.callout("why",
        "Trust is about where a document came from, not how sensitive it is. A "
        "CV is low sensitivity and completely untrusted. Keeping those two "
        "ideas apart is what stops a hostile upload sliding into the trusted "
        "pile.")
    b.h2("Masking personal data on the way in")
    b.para(
        "The same pass masks personal data before indexing, so the vector store "
        "never holds a raw NI number or bank detail. The UK identifiers a "
        "payroll firm actually handles aren't in the trained models out of the "
        "box, so {} adds them as plain patterns.".format(C.PROJECT_NAME))
    b.code("pii_regexes", "The UK identifier patterns and a card checksum")
    b.code("regex_engine", "The always-available regex engine")
    b.code("mask", "Replacing each found value with a label")
    b.para(
        "If Presidio is installed it adds names and places on top; if it isn't, "
        "the regex engine runs alone. Either way, recall on the planted "
        "identifiers is {}.".format(m.pct("pii.recall")))
    b.callout("limit",
        "A trained model helps with names and addresses, but the identifiers "
        "that matter to payroll are grammar you still write yourself. Don't "
        "assume the model covers a sort code.")
    build_step(b, "ch09", "W4",
        [["src/warden/gateway/ingest.py",
          "W4 the ingest scan, quarantine and PII masking"]],
        ["test_w4_hostile_upload_is_quarantined",
         "test_w4_personal_data_is_masked_before_indexing"],
        ["SCENE 3  The same hostile CV, behind Warden",
         "  side effects executed: [{'tool': 'email_document', "
         "'to': 'outsider@example.org', ...}]",
         "",
         "  W4  ingest scan            BLOCKED     a CV upload carrying an instruction",
         "  4 of 8 controls built."],
        "8 failed, 8 passed",
        "Chapter {}: W4 now BLOCKED, 4 of 8 controls built".format(ch.n("ingest")),
        note="Look at scene 3. The email still goes out, but now to "
             "outsider@example.org instead of the attacker's own address, "
             "because W4 masked the address in the CV before indexing it. The "
             "CV's instruction is quiet enough to pass the scan, so it still "
             "reaches the model. Stopping the email itself is W8's job, in "
             "[[ch:tools]].")


def c10(b, m):
    b.h1("permission")
    b.h2("W5: only retrieve what the caller may read")
    b.para(
        "First, work out who is asking. The directory turns a sign-in into a "
        "role, a department and an employee id. Everything downstream is built "
        "from that.")
    b.code("identity", "Resolving the caller to a role and department")
    b.para(
        "Then filter retrieval to the access groups that person holds, and do "
        "it before ranking, not after. A document the caller may not read never "
        "even competes for a slot, so it never reaches the model.")
    b.code("local_index", "The offline index, with the permission filter built in")
    b.callout("why",
        "The filter has to run inside the query so it can move to the edge "
        "unchanged. On Cloudflare it's a Vectorize metadata filter with the "
        "same idea, so the design you test offline is the design you ship.")
    b.code("vectorize_query", "The same filter as a Cloudflare Vectorize query")
    b.para(
        "In the red team, this one control stops more attacks than any other. "
        "It's the plain fix for the second thing that was wrong in "
        "[[ch:problem]].")
    b.para("In the gateway, the whole control is one question asked before "
           "the search runs: which groups may this caller read?")
    b.code("permission_filter", "W5: the access groups this caller may retrieve from")
    build_step(b, "ch10", "W5",
        [["src/warden/gateway/permission.py", "W5 the permission filter"]],
        ["test_w5_a_manager_cannot_retrieve_another_teams_payroll",
         "test_w5_retrieval_is_always_filtered"],
        ["SCENE 4  A line manager asks for another team's salaries",
         "  naive returns another team's salaries: True",
         "  Warden returns another team's salaries: False "
         "(W5 kept sales documents out of retrieval)",
         "",
         "  W5  permission filter      BLOCKED     engineering manager vs sales payroll",
         "  5 of 8 controls built."],
        "6 failed, 10 passed",
        "Chapter {}: scene 4 now False, W5 BLOCKED, 5 of 8 controls built".format(ch.n("permission")))


def c11(b, m):
    b.h1("output")
    b.h2("W6: scan the answer before it leaves")
    b.para(
        "Assume everything above failed. W6 asks a different question: is what "
        "the model just produced safe to send to this person? It catches leaked "
        "identifiers, links that carry data out, and runaway repetition.")
    b.code("output_scan", "The output scan")
    b.callout("why",
        "Input rules catch what you know. Output checks catch what you don't, "
        "because they don't care how the answer was produced, only what's in "
        "it. In the red team the output side catches the attacks nobody wrote a "
        "rule for.")
    b.h2("W7: the canary")
    b.para(
        "The system prompt holds a made-up secret and a canary token that "
        "exists nowhere else. If either shows up in an answer, the prompt has "
        "leaked and the answer is blocked.")
    b.code("canary_make", "The canary, the secret, and the system prompt")
    b.code("canary_check", "Catching a leak, exact or fuzzy")
    b.callout("why",
        "The canary is the certain half: a random string can't be paraphrased "
        "away, so any answer with it in is a verbatim leak. The word-overlap "
        "check is the fuzzy half, for a model that summarises the prompt "
        "instead of quoting it.")
    build_step(b, "ch11", "W6 and W7",
        [["src/warden/gateway/output.py", "W6 the output scan"],
         ["src/warden/gateway/canary.py",
          "W7 the leak check (the canary itself was there from the start)"]],
        ["test_w6_bank_details_are_masked_in_the_answer",
         "test_w6_a_beacon_link_is_flagged",
         "test_w7_canary_in_the_answer_is_caught",
         "test_w7_secret_in_the_answer_is_caught"],
        ["  W6  output scan            BLOCKED     an answer holding bank details",
         "  W7  canary                 BLOCKED     an answer holding the canary token",
         "  7 of 8 controls built."],
        "2 failed, 14 passed",
        "Chapter {}: W6 and W7 now BLOCKED, 7 of 8 controls built".format(ch.n("output")))


def c12(b, m):
    b.h1("tools")
    b.h2("W8: the tool-call policy engine")
    b.para(
        "This is what makes {} more than a chatbot firewall. Every tool call "
        "the agent wants to make gets one of three answers: allow, block, or "
        "ask a human. The rules are written per tool, so you can read the "
        "policy without reading the agent.".format(C.PROJECT_NAME))
    b.code("tool_role_matrix", "Which roles may use which tools at all")
    b.code("tool_policy_decide", "Allow, block, or ask, with argument checks")
    b.callout("why",
        "The argument checks are the whole point. An email tool isn't just "
        "'allowed' or 'blocked'. It's allowed to the company domain and blocked "
        "everywhere else. A classifier can be talked round with clever wording. "
        "A rule that an email can only go to {} cannot.".format(C.COMPANY_DOMAIN))
    b.table(["Situation", "Outcome"], [
        ["Email to the company domain", "allow"],
        ["Email to any outside address", "block"],
        ["Payroll change under GBP {}".format(C.PAYROLL_ASK_ABOVE_GBP), "allow"],
        ["Payroll change over GBP {}".format(C.PAYROLL_ASK_ABOVE_GBP), "ask a human"],
        ["Payroll change over GBP {:,}".format(C.PAYROLL_BLOCK_ABOVE_GBP), "block"],
        ["A side effect the user never asked for", "ask a human"],
        ["A tool the caller's role may not use", "block"]])
    b.callout("why",
        "A side effect the user didn't ask for, that the model only proposed "
        "after reading a document, is the injection case. It's never run "
        "silently. That single rule stops the whole class of agent-hijack "
        "attacks, whatever clever wording the injection used.")
    build_step(b, "ch12", "W8",
        [["src/warden/policy/tool_policy.py", "W8 the tool-call policy engine"]],
        ["test_w8_email_to_an_outside_address_is_blocked",
         "test_w8_a_huge_payroll_change_is_blocked"],
        ["SCENE 3  The same hostile CV, behind Warden",
         "  side effects executed: [] (none: the email was stopped)",
         "  W8 tool policy on the email: [\"recipient 'outsider@example.org' "
         "is not on the company domai\"]",
         "",
         "SCENE 5  The agent is asked to change pay it should not change",
         "  side effects executed: []",
         "  tool policy decision: ['GBP 68,000 is above the hard ceiling "
         "of GBP 10,000']",
         "",
         "  W8  tool policy            BLOCKED     email payroll to outsider@example.org",
         "  8 of 8 controls built."],
        "16 passed",
        "Chapter {}: scenes 3 and 5 stopped, 8 of 8 controls built".format(ch.n("tools")),
        note="This is the chapter where the quiet attacks finally stop. Scene "
             "3's CV got past W1, W2 and W4, but the email it asked for is "
             "now refused on its arguments, whatever the wording was.")


def c13(b, m):
    b.h1("assemble")
    b.h2("Put the eight controls together")
    b.para(
        "Here's the whole gateway. It resolves the caller, runs the input "
        "checks, retrieves only what they may read, runs the same agent loop as "
        "the naive app, and then scans the answer and every tool call on the "
        "way out. The assistant underneath is untouched.")
    b.code("gateway", "The Warden gateway, end to end")
    b.para(
        "Each control has its own file, and the gateway calls them in order. "
        "That's why you could switch them on one at a time: the gateway never "
        "changed, only what was behind each call.")
    b.para(
        "The demo's last section tests each control on its own, with one "
        "probe it should block. A starter stub lets the probe through; the "
        "real control stops it.")
    b.code("demo_controls", "How the demo checks each control on its own")
    b.para(
        "Now run everything once more. All the unit tests should pass, not "
        "just the build tests, and the demo should show every attack stopped. "
        "Put this run next to your screenshot from [[ch:break]]: the same five "
        "attacks, the same command, and the only difference is the gateway.")
    b.shell(["python -m pytest tests -q",
             "python -m warden.demo"])
    b.table(["Scene", "Chapter {} (all stubs)".format(ch.n("break")),
             "Chapter {} (all eight built)".format(ch.n("assemble")),
             "Stopped by"], [
        ["2 hostile CV, naive app", "email sent", "email sent",
         "nothing: the naive app has no gateway"],
        ["3 same CV, behind Warden", "email sent", "email stopped", "W8"],
        ["4 another team's salaries", "True (leaked)", "False", "W5"],
        ["5 payroll change", "went through", "blocked", "W8"],
        ["Controls built", "0 of 8", "8 of 8", "W1 to W8"]])
    b.screenshot("Chapter {}: every attack stopped, and 8 of 8 controls built".format(ch.n("assemble")))


def c14(b, m):
    b.h1("redteam")
    b.h2("Measure it, and be honest about it")
    b.para(
        "A security control nobody measured is one you're guessing about. So we "
        "run the whole attack suite against both the naive app and the gateway, "
        "with the same scorer, and report the numbers.")
    b.para(
        "The attacks come in two halves, and the split is the most important "
        "thing here. The development attacks are the ones the rules were "
        "written against. Scoring well on them only proves the rules were typed "
        "in right. The held-out attacks were written first and frozen by a hash "
        "before any control existed, and nothing was changed to catch them. "
        "They're the honest measurement.")
    b.code("build_probes", "Turning the templates into concrete attacks")
    b.para(
        "Each attack runs against a clean corpus plus its own single hostile "
        "document, so one attack can never be blocked by a different attack's "
        "document and score as a pass.")
    b.code("run_target", "Running one attack against one target")
    b.h2("What counts as a breach")
    b.para(
        "Two levels. A breach means the attacker got what they wanted: data "
        "left, or an action ran. Exposure is softer: hostile text reached the "
        "model but nothing bad came out. We report both, because whether a "
        "model complies is partly luck, while whether the text reached it is a "
        "fact about your pipeline that you control.")
    b.code("breach_detectors", "The breach detectors, one per goal")
    b.code("exposure", "The exposure check")
    b.code("summarise", "Rolling the results up, dev and held-out apart")
    b.h2("The utility side")
    b.para(
        "A gateway that blocks everything scores a perfect zero on attacks and "
        "is useless. So the security numbers always come with two utility ones: "
        "how many normal questions still get answered, and how many boundary "
        "requests (a real person asking for something they shouldn't get) are "
        "held.")
    b.code("benign_set", "Ordinary questions the assistant should still answer")
    b.code("boundary_set", "Requests that should be refused, no trickery")
    b.code("utility_run", "Measuring utility against both apps")
    b.h2("The numbers")
    b.para("Run it yourself. The generator is seeded, so you get these too:")
    b.shell(["python scripts/run_all.py"])
    b.table(["Measure", "Naive app", "Behind {}".format(C.PROJECT_NAME)], [
        ["Attacks that breached",
         "{} of {}  ({})".format(m.get("redteam.naive_breach"),
                                 m.get("redteam.naive_total"),
                                 m.pct("redteam.naive_breach_rate")),
         "{} of {}  ({})".format(m.get("redteam.gateway_breach"),
                                 m.get("redteam.gateway_total"),
                                 m.pct("redteam.gateway_breach_rate"))],
        ["Held-out attacks only",
         m.pct("redteam.naive_held_rate"), m.pct("redteam.gateway_held_rate")],
        ["Development attacks only",
         m.pct("redteam.naive_dev_rate"), m.pct("redteam.gateway_dev_rate")],
        ["Hostile text reached the model",
         m.pct("redteam.naive_exposure_rate"), m.pct("redteam.gateway_exposure_rate")],
        ["Normal questions answered", "100.0%", m.pct("utility.answer_rate")],
        ["Answers with the right content", "100.0%", m.pct("utility.correct_rate")],
        ["Boundary requests held",
         "{} of {}".format(m.get("utility.boundary_total") - m.get("utility.naive_boundary_leaked"),
                           m.get("utility.boundary_total")),
         "{} of {}".format(m.get("utility.boundary_held"),
                           m.get("utility.boundary_total"))]])
    b.para(
        "The exposure row is the honest one. {} still gets its hostile text to "
        "the model on {} of attacks. None of them achieve anything, because the "
        "permission filter, the tool policy and the output scan catch the "
        "outcome. But those are the controls doing the work, not the input "
        "detectors.".format(C.PROJECT_NAME, m.pct("redteam.gateway_exposure_rate")))
    b.h2("Which control did the work")
    b.para(
        "We record every control that actually acted on each attack, not just "
        "the stage that happened to run. The picture is clear: the structural "
        "controls carry the defence.")
    _controls_table(b, m)
    b.callout("why",
        "The injection classifier (W2) blocked nothing on its own that the "
        "structural controls didn't already stop. That's the headline lesson. "
        "Detection is useful, but permission-aware retrieval and a tool policy "
        "are what actually hold, because they don't depend on spotting the "
        "attack.")


def _controls_table(b, m):
    acted = m.get("redteam.controls_acted")
    rows = []
    for cid, key, _ in C.CONTROLS:
        rows.append([cid, key.replace("_", " "), str(acted.get(cid, 0))])
    b.table(["id", "control", "attacks it acted on"], rows)


def c15(b, m):
    b.h1("cloudflare")
    b.para(
        "Everything so far ran offline. This chapter puts the same gateway on "
        "Cloudflare's edge. It's checked against the current docs (on {}) but "
        "not yet run against a live account, and it says so out loud wherever "
        "that's true.".format(m.get("docs_checked_date")))
    b.callout("heads up",
        "This guide doesn't walk you through making a Cloudflare account. Use "
        "any recent video, then come back. What follows is the project-specific "
        "setup.")
    b.h2("The pieces")
    b.table(["Piece", "What it does", "Free tier"], [
        ["Workers", "runs the gateway at the edge", "100,000 requests a day"],
        ["Workers AI", "the chat model, Llama Guard 3, embeddings", "10,000 neurons a day"],
        ["Vectorize", "the vector store, with the permission filter", "5M stored dims"],
        ["AI Gateway", "logs, caching, rate limits", "free"],
        ["Oracle VM", "runs Prompt Guard 2 for W2", "always free"]])
    b.h2("Before you start: Node.js and Wrangler")
    b.para("Wrangler is Cloudflare's command line tool. It runs on Node.js, and "
           "npx fetches it the first time you use it, so there's nothing else "
           "to install by hand.")
    b.table(["You need", "Why", "How to check"], [
        ["A Cloudflare account", "everything in this chapter", "you can sign in at dash.cloudflare.com"],
        ["Node.js, the current LTS version", "runs Wrangler", "node --version"]])
    b.steps([
        "Install Node.js from nodejs.org if node --version doesn't print a "
        "version. Any recent video for your system shows how.",
        "In the terminal, go into the Worker's folder.",
        "Log Wrangler in to your Cloudflare account. A browser window opens. "
        "Click Allow, and the terminal says you're logged in.",
        "Ask Wrangler who you are. It prints your account name and your "
        "Account ID. Copy the Account ID somewhere safe for the next section.",
    ])
    b.shell([
        "cd infra/worker",
        "npx wrangler login",
        "npx wrangler whoami",
    ])
    b.h2("An API token for the Python side")
    b.para("Wrangler is now logged in, but the Python scripts call Cloudflare "
           "directly, so they need their own token.")
    b.steps([
        "In the Cloudflare dashboard, open AI, then Workers AI.",
        "Choose Use REST API, then Create a Workers AI API Token. Keep the "
        "permissions it suggests and create it.",
        "Copy the token straight away. Cloudflare only shows it once. The "
        "same page also shows your Account ID.",
        "In the terminal you'll run the Python scripts from, set both as "
        "environment variables, using the lines for your terminal. Put your "
        "own values in place of the examples.",
    ])
    b.shell([
        "$env:CF_ACCOUNT_ID = \"your-account-id\"      # Windows PowerShell",
        "$env:CF_API_TOKEN = \"your-api-token\"        # Windows PowerShell",
        "export CF_ACCOUNT_ID=your-account-id         # Git Bash, macOS, Linux",
        "export CF_API_TOKEN=your-api-token           # Git Bash, macOS, Linux",
    ])
    b.callout("gotcha",
        "These only last as long as that terminal window. Open a new one and "
        "you set them again. That's on purpose: never write the token into a "
        "file in the repository, a screenshot or a chat.")
    b.h2("Create the vector index")
    b.para("Still in infra/worker, create the index, then the metadata index "
           "the permission filter needs. Run them in this order.")
    b.shell([
        "npx wrangler vectorize create {} --dimensions={} --metric=cosine".format(
            C.CF_VECTORIZE_INDEX, C.CF_EMBED_DIMS),
        "npx wrangler vectorize create-metadata-index {} --property-name={} "
        "--type=string".format(C.CF_VECTORIZE_INDEX, C.CF_METADATA_FIELD),
    ])
    b.callout("gotcha",
        "Create the metadata index on {} before you load any vectors. Vectors "
        "added earlier can't be filtered, so the permission filter would "
        "quietly return everything.".format(C.CF_METADATA_FIELD))
    b.h2("Load the documents")
    b.para("The Worker searches the index, so the HR documents have to go in "
           "first. load_vectorize.py runs control W4 on every document, the "
           "same as the offline gateway: hostile uploads are left out and "
           "personal data is masked. Then it asks Workers AI for the "
           "embeddings and writes them to results/vectorize.ndjson.")
    b.steps([
        "Go back to the project folder.",
        "Do a dry run first. It needs no network and shows how many documents "
        "go in, per permission group.",
        "Run it for real. It needs the two environment variables from the "
        "last section.",
        "Go back into infra/worker and upload the file with Wrangler.",
        "Check the index. The vector count should match the dry run.",
    ])
    b.shell([
        "cd ../..",
        "python scripts/load_vectorize.py --dry-run",
        "python scripts/load_vectorize.py",
        "cd infra/worker",
        "npx wrangler vectorize insert {} --file=../../results/vectorize.ndjson".format(
            C.CF_VECTORIZE_INDEX),
        "npx wrangler vectorize info {}".format(C.CF_VECTORIZE_INDEX),
    ])
    b.h2("Set the secrets and deploy")
    b.para("The Worker keeps its system prompt and its canary as secrets, so "
           "they're never in the code. worker_secrets.py prints them, and the "
           "pipe hands each one straight to Wrangler.")
    b.shell([
        "python ../../scripts/worker_secrets.py --canary | npx wrangler secret put CANARY",
        "python ../../scripts/worker_secrets.py --system-prompt | npx wrangler secret put SYSTEM_PROMPT",
        "npx wrangler deploy",
    ])
    b.para("The deploy prints your Worker's address. It looks like "
           "https://{}.your-subdomain.workers.dev. Copy it.".format(
               C.CF_WORKER_NAME))
    b.h2("Test it")
    b.para("infra/worker/test_request.json is a normal question from an "
           "ordinary employee. Send it to your Worker, with your own address "
           "in place of the example. On Windows type curl.exe, not curl, "
           "because PowerShell has its own curl that works differently.")
    b.shell([
        "curl.exe -X POST https://{}.your-subdomain.workers.dev "
        "-H \"Content-Type: application/json\" --data \"@test_request.json\"".format(
            C.CF_WORKER_NAME),
    ])
    b.para("You should get back a small JSON reply with decision set to allow "
           "and an answer about annual leave.")
    b.callout("limit",
        "This demo Worker believes the principal in the request, so anyone "
        "who knows the address could claim to be a payroll officer. Before "
        "real staff use it, put Cloudflare Access or your company sign in in "
        "front of it and take the principal from the verified login, never "
        "from the request body.")
    b.h2("Measure it against the real model")
    b.para("Now run the same measurements as [[ch:redteam]], with the real "
           "model and Llama Guard 3 instead of the stand-ins. Do it from the "
           "project folder, in the terminal where you set the two "
           "environment variables.")
    b.shell([
        "cd ../..",
        "python scripts/run_all.py --backend cloudflare",
    ])
    b.para("Put the numbers next to the offline ones and report both. A real "
           "model obeys hidden instructions less often than the stand-in, so "
           "the naive breach rate will probably drop. The question is "
           "whether Warden still holds.")
    b.h2("What the Worker does")
    b.code("cf_chat", "Calling the chat model on Workers AI")
    b.h2("Permission-aware retrieval at the edge")
    b.code("worker_retrieve", "The Vectorize query, with the acl_group filter")
    b.callout("gotcha",
        "Create the metadata index on acl_group before you upsert any vectors. "
        "Vectors added earlier are not filterable, so the permission filter "
        "would quietly return everything.")
    b.h2("The tool policy at the edge")
    b.code("worker_tool_policy", "The same allow / block / ask rules, in the Worker")
    b.h2("The whole Worker")
    b.code("worker_fetch", "The gateway as a Cloudflare Worker")
    b.h2("Optional: the real Prompt Guard 2 on an Oracle VM")
    b.para("Cloudflare doesn't host a prompt injection classifier, so W2's "
           "real model runs on a free Oracle VM as a tiny web service. This is "
           "optional: without it W2 keeps using the stand-in. The full notes, "
           "including the free tier limits that Oracle cut in half in mid "
           "2026, are in infra/oracle/prompt_guard_service.md.")
    b.steps([
        "On huggingface.co, sign in, open the meta-llama/Llama-Prompt-Guard-2-86M "
        "page and request access. It's a gated model, so wait for the "
        "approval email.",
        "In Hugging Face, go to Settings, Access Tokens, and create a token "
        "with read access. Copy it.",
        "In the Oracle Cloud console, create a compute instance: shape "
        "VM.Standard.A1.Flex with 2 OCPUs and 12 GB, an Ubuntu image, and "
        "download the SSH key it offers. Note its public IP address.",
        "In the instance's subnet, open Security Lists and add an ingress rule "
        "for TCP port 8080 from your own IP address only.",
        "Connect with SSH, then follow the numbered steps in "
        "infra/oracle/prompt_guard_service.md to install the model, start "
        "the service and open port 8080 on the VM itself.",
        "Back on your own machine, point W2 at the service by setting "
        "PROMPT_GUARD_URL, then run the measurements again.",
    ])
    b.shell([
        "ssh -i path/to/your-key ubuntu@your-vm-ip",
        "$env:PROMPT_GUARD_URL = \"http://your-vm-ip:8080/score\"     # Windows PowerShell",
        "export PROMPT_GUARD_URL=http://your-vm-ip:8080/score        # Git Bash, macOS, Linux",
        "python scripts/run_all.py --backend cloudflare",
    ])
    b.screenshot("The Cloudflare dashboard showing the deployed Worker and the Vectorize index")


def c16(b, m):
    b.h1("ci")
    b.h2("The gate: red team on every change")
    b.para(
        "A control that isn't re-tested on every change is a control that used "
        "to work. So the red team runs in continuous integration. It runs "
        "against the offline stand-ins, so it needs no key and no account, "
        "which is the only way a gate like this survives contact with a team: "
        "the moment it needs a credential, someone turns it off.")
    b.para("The workflow file is already in the project, at "
           ".github/workflows/redteam.yml, so GitHub runs it by itself every "
           "time you push. It runs these two checks, among others. You can run "
           "them on your own machine first:")
    b.shell([
        "python eval/redteam.py --target gateway --fail-over 0.05",
        "python eval/utility.py --assert-answer-rate 0.95 --assert-boundary 1.0",
    ])
    b.para("Then watch it run on GitHub:")
    b.steps([
        "Commit and push any change from the project folder, with the three "
        "commands below.",
        "On github.com, open your warden repository and click the Actions tab. "
        "If GitHub asks, click the button that enables workflows.",
        "Click the newest Warden red team run. Each step gets a green tick "
        "when it passes and a red cross when it fails. Click a step to read "
        "its output.",
        "To run it without pushing anything, open the Warden red team workflow "
        "and click Run workflow.",
    ])
    b.shell([
        "git add .",
        "git commit -m \"Run the red team gate\"",
        "git push",
    ])
    b.para(
        "The gate fails if the breach rate goes above {} or if the answer rate "
        "drops below {}. The utility check isn't optional. Without it you could "
        "pass the security gate by making the assistant refuse everything, "
        "which passes the threshold and destroys the product.".format(
            m.pct("thresholds.redteam_max_success_rate"),
            "95%"))
    b.screenshot("The GitHub Actions run, red team and utility both green")


def c17(b, m):
    b.h1("cost")
    b.h2("What it costs to run")
    b.para(
        "The cost chapter is worked out from published prices, not typed in. "
        "The traffic assumption is stated out loud: a {}-person firm, lightly "
        "used, at {} requests a day.".format(
            C.N_EMPLOYEES * 3, m.get("cost.requests_per_day")))
    b.code("cost_assumptions", "The token assumptions and the per-request cost")
    b.para(
        "At that rate the whole thing costs about {} dollars a month, inside a "
        "budget of {} to {} dollars. Most of it is free-tier: Workers, "
        "Vectorize, AI Gateway and the Oracle VM all sit in their free "
        "allowances, and the free daily neuron grant often covers the model "
        "calls too, so real spend is frequently zero.".format(
            m.get("cost.total_usd_per_month"), m.get("cost.budget_low"),
            m.get("cost.budget_high")))
    b.shell(["python -m warden.cost"])
    b.h2("What is left")
    b.bullets([
        "Run [[ch:cloudflare]] against a real Cloudflare account, and "
        "report the cloud numbers next to the offline ones.",
        "Stand up Prompt Guard 2 on the Oracle VM, as that chapter shows, and "
        "measure W2 with the real model.",
        "Capture the screenshots this guide marks.",
    ])


def c18(b, m):
    b.h1("sell")
    b.h2("What you can sell from this")
    b.para(
        "This project is a portfolio piece and a service in one. Three things "
        "come out of it.")
    b.bullets([
        "A 'Secure RAG and Agents' build package: put a measured gateway in "
        "front of a client's existing AI app without rewriting it.",
        "AI red-team assessments: run a dev and held-out attack suite against "
        "an app and hand over the breach, exposure and utility numbers.",
        "The interview answer to 'how would you secure a RAG system and its "
        "agent', backed by numbers you produced yourself.",
    ])
    b.para(
        "The selling point is the same as the engineering point. You don't say "
        "'we added AI safety'. You say 'attacks went from {} to {}, normal "
        "questions still answered {}, for a few dollars a month', and you can "
        "reproduce it.".format(
            m.pct("redteam.naive_breach_rate"), m.pct("redteam.gateway_breach_rate"),
            m.pct("utility.answer_rate")))
    b.para(C.CREDIT_LINE + " " + C.RIGHTS_LINE)


# ===========================================================================
def appendix_a(b, m):
    b.appendix("A")
    b.para(
        "Every number in this guide comes from an offline stand-in, and the "
        "guide says so. Here's why the stand-in is honest instead of "
        "flattering.")
    b.h2("The stand-in obeys everything")
    b.para(
        "The model stand-in complies with any instruction in its prompt. That's "
        "the worst case, and it's the right thing to build a defence against. "
        "Because it always obeys, the gateway can't pass by asking the model "
        "nicely. It only passes when the hostile text never reaches the model, "
        "when the tool policy refuses the action, or when the output scan "
        "catches the result.")
    b.h2("The stand-in is wider than the shield")
    b.para(
        "The set of things the model can be talked into is deliberately broader "
        "than the rules the shield knows. If they were kept in step, the red "
        "team would only measure the attacks the rules were built for, and "
        "report a defence that doesn't exist. An earlier project in this series "
        "hit exactly that trap and reported zero breaches that weren't real.")
    b.h2("The held-out set is frozen")
    b.para(
        "The held-out attacks were written before any control existed and their "
        "hash is recorded. A check fails the build if they change, so nobody "
        "can quietly reword an attack to make the defence look better after the "
        "fact. That's what makes the held-out number worth reading.")


def appendix_b(b, m):
    b.appendix("B")
    b.para(
        "{} shares its machinery with AegisAI, the earlier AI security project "
        "in this series, and it's built to be different in the ways that "
        "matter.".format(C.PROJECT_NAME))
    b.table(["", "AegisAI", "{}".format(C.PROJECT_NAME)], [
        ["Story", "secure an insurance claims chatbot", "secure an HR chatbot and its agent"],
        ["Centre of gravity", "nine controls, output focus", "tool-call policy and permission-aware retrieval"],
        ["Agent", "not the focus", "the whole point: an agent that can act"],
        ["Cloud", "Azure", "Cloudflare edge"],
        ["Tools", "Azure services", "open: Prompt Guard, Llama Guard, Presidio"]])
    b.para(
        "If you built AegisAI, the ideas here will feel familiar: a gateway in "
        "front of an app, a seeded corpus, dev and held-out attacks, numbers "
        "you can reproduce. What's new is the agent and the tool policy, which "
        "is where the real risk sits once an AI can do things and not just say "
        "them.")


def appendix_c(b, m):
    b.appendix("C")
    b.para("How the eight controls line up with the OWASP Top 10 for LLM apps.")
    b.table(["OWASP risk", "Controls that address it"], [
        ["LLM01 Prompt injection", "W1, W2, W4, and W8 for the action"],
        ["LLM02 Sensitive information disclosure", "W4, W5, W6, W7"],
        ["LLM06 Excessive agency", "W8, the tool policy"],
        ["LLM07 System prompt leakage", "W7, the canary"],
        ["LLM08 Vector and embedding weaknesses", "W4, W5"],
        ["LLM10 Unbounded consumption", "W6 runaway check, and rate limits"]])


def appendix_d(b, m):
    b.appendix("D")
    b.h2("When {} does not work".format(C.PROJECT_NAME))
    b.bullets([
        "The injection classifier misses reworded attacks. The measured "
        "held-out result depends on the structural controls behind it, not on "
        "the classifier.",
        "The permission model is only as good as the access groups on your "
        "documents. Tag a document with the wrong group and the filter honours "
        "the wrong answer.",
        "The tool policy protects the tools it knows. A new tool with a "
        "dangerous argument and no rule is allowed by default only if you add "
        "it to the read-only list by mistake, so review the policy when you add "
        "a tool.",
        "The offline numbers are measured against a stand-in. A real model will "
        "comply less often, so the naive breach rate is a worst case, and the "
        "gateway numbers should be re-measured on the real backend.",
        "This is a demonstration on synthetic data. Never run these attacks "
        "against a system you do not own.",
    ])


def appendix_e(b, m):
    b.appendix("E")
    b.table(["Term", "Meaning"], [
        ["RAG", "retrieval augmented generation: answer from retrieved documents"],
        ["Agent", "an AI that can call tools, not just produce text"],
        ["Indirect prompt injection", "an instruction hidden in a document the AI reads"],
        ["Canary", "a unique token in the system prompt that reveals a leak"],
        ["acl_group", "the one access group that may read a document"],
        ["Breach", "the attacker achieved their goal"],
        ["Exposure", "hostile text reached the model, but no harm came out"],
        ["Held-out attack", "written and frozen before the controls existed"]])
