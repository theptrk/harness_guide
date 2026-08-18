# Infinite Teammates

*Curriculum roadmap · draft v0.2*

15 levels · 5 more, in draf

Start with a single call to a model. Finish with an assistant that has its own computer, logs into your accounts, and asks for your help when it gets stuck.


## What you're building

The target is similar to Grokbot. You open a chat, give an assistant a task, and the agent works until the task is completed or it reaches a roadblock. The agent has access to: a computer with a browser, a terminal, and files, plus proper logged-in connections to accounts like Google Calendar.

Here is one task from start to finish. It's the one that prompted this whole project.

> You say *I've got a $5 charge from Railway every month — what is that, and can we cancel it?* 
> It opens a browser, goes to railway.app, and hits the login page. It doesn't ask you for your password; it stops and tells you it needs you to sign in. 
> You click into its browser window and you're the one typing, on its machine. You log in and tell it you're done.
>
> It takes back over and continues the task. It finds the instances on your account and works out that the $5 is the Hobby plan. Before it touches anything, it tries to establish what a cancelling the plan would break — what you have deployed, whether anything is still calling those deployments, and how long it's been since any of them last did anything. 
> It reports to you the findings, intended action and the consequences - tells you it can't find anything you'd lose, and asks whether to go ahead. 
> You say yes. 
> It does it.
>

> **Worth noticing** — That went well. The same sequence with a slightly less careful confimation takes down production even after realizing a very active instance. The bot is overly careful by default on destructive actions.

Many pieces of software must be built to make the story above sound easy. Taking it from the top, here is where each piece gets built:

| Piece of the story | Built at |
|---|---|
| Holding a conversation | Level 1 |
| Using a provided "tool" | Level 2 |
| Using several tools to finish one request | Level 3 |
| The streaming UX improvment | Level 5 |
| Asking for confirmation for command line actions | Levels 7 |
| A browser it can drive | Level 8 |
| Notifying the human in the loop for assistance | Level 9 |
| Carrying on in the browser you logged into | Level 9 |
| Asking for confirmation for browser actions. | Levels 9 |

The rest of the ladder covers what this story doesn't touch: recovering from its own errors, somewhere to keep files and run them, staying reliable once the conversation gets long, reaching back into things you said weeks ago, and connecting to the accounts that *do* have a proper interface.


## The ladder

Read the right-hand column first. Each level exists because you ran a task on the previous level's code and watched it fail. That's what sets the order — not difficulty, and not what's conventional to teach next.

| Lvl | Build | Because the last one couldn't… |
|---|---|---|
| | **Part I — The Loop** | |
| 0 | Call a model | — |
| 1 | Hold a conversation | …remember what you just said |
| 2 | One tool | …do arithmetic, or know what time it is |
| 3 | The agent loop | …do two things in a row |
| 4 | Harden the loop | …survive a tool that throws |
| 5 | Stream it | …show you anything while it works |
| | **Part II — The Computer** | |
| 6 | Files | …hold more than fits in a chat message |
| 7 | Shell + approval | …run the code it just wrote |
| | **Part III — The Handoff** | |
| 8 | The browser | …use a website |
| 9 | Human takeover | …get past a login page |
| | **Part IV — Reliability** | |
| 10 | Trimming history | …survive its own conversation getting long |
| 11 | Scored test set | …tell you whether a change helped |
| | **Part V — Making it yours** | |
| 12 | Long-term memory | …reach a conversation it isn't in |
| 13 | Gmail access | …read your own mail |
| 14 | Plugin system | …add a second account without copy-paste |
| | **Sketched only — The Fleet** | |
| 15 | Sandbox | …stop running on your real laptop |
| 16 | Cloud computer | …survive a restart, or run more than one |
| 17 | Separate assistants | …keep unrelated concerns from bleeding together |
| 18 | Background work | …keep going when you close the lid |
| 19 | Production | …be trusted with real credentials and real money |


---

## Part I — The Loop

A model answers one question at a time. It can't look anything up, and it doesn't remember what you asked a minute ago. By the end of Part I you can ask for one thing and watch it work through several steps — calling tools you wrote, recovering when one of them fails, and stopping when it's done.


### 00 · Call a model

`main.py "why is the sky blue"` → an answer. One file, one dependency. No framework, no database, no web server.

- **Learn** — Where the API key lives and why it never goes in the code. The two pieces of text you send: the question, and a set of instructions that applies to every question, called the system prompt. How your words become tokens, which is the thing you're billed for.
- **Done when** — You print the answer along with the token count and the cost of the call you just made
- **Effort** — an hour

> **Sidebar** — Read the raw response once, against the documentation. You won't need to again, but two things in it are worth seeing now: the answer is buried a few levels down inside an `output` list, and `model` reports what actually served you, which isn't always what you asked for. The second one is why the cost you calculate can be quietly wrong.


### 01 · Hold a conversation

**Breaks** — "My name is Patrick." → "Hi Patrick." → "What's my name?" → *it has no idea.*

A prompt loop that writes down what happens as it happens: one line appended for every message you send and every one that comes back. Each conversation gets its own file under `chats/`, and starting the program either continues the most recent one or begins a new one. When it's time to call the model, read the current file and build the list of messages from it.

- **Learn** — The model remembers nothing between calls, so keeping the record is your job. A conversation is sent as a list, in full, every single time. Building that list out of the record rather than letting the list *be* the record. And why a conversation needs a boundary: the next four levels are experiments, and without one their leftovers ride along in every call you make afterward.
- **Done when** — You quit mid-conversation, restart, and it picks up where you left off. You start a new conversation and it doesn't know your name, while the old file still does. You delete the last two lines of a file and that conversation rewinds.
- **Effort** — an hour

> **Why not just keep the list in memory** — The obvious version keeps the messages in a Python list and saves it when the program exits. That's enough for this level. At Level 10 you start replacing old messages with a summary to stay under the size limit, and if the list is all you have, those messages are gone for good. Write to the file instead and build the list fresh on every call: then you can send a trimmed list while the file still holds every word. A conversation you keep returning to grows with no upper bound, which is fine — you never send the file, only the list you build from it. Disk is free. The amount you can send is not.


### 02 · Give it one tool

**Breaks** — "What time is it in Tokyo?" → an answer that sounds current, from a model with no clock.

One function — `get_current_time(tz)` — described to the model as a name, a sentence, and a list of arguments. A function offered to a model this way is called a *tool*, and the API parameter you send them in is called `tools`. Keep executable functions in a dictionary keyed by those names. Then the code can notice a tool request, select the function by name, run it, and send the result back.

- **Learn** — How to describe a function so a model can ask for it. What its reply looks like when it wants that tool, how its name selects executable code, and how you hand the result back.
- **Done when** — The model asks for the tool, your code runs the function behind it, and the answer is right because of that
- **Effort** — an evening

> **The whole point** — The model doesn't call your function. It replies with a message saying it wants to, and your code decides whether to run it. Everything the assistant can do, in every later level, works this way.


### 03 · Build the agent loop

**Breaks** — "What time is it in Tokyo and New York?" → your code runs one tool request and stops, because you only wrote it to handle one.

Wrap the whole thing in a `while`: call the model, run whatever tools it asks for, send the results back, and go round again until it stops asking and just answers.

- **Learn** — The loop itself and when to stop going round. One pass is one model call plus whatever tool it asked for, and one request from you can take several passes.
- **Done when** — It calls the time tool for three timezones in a row, choosing the arguments itself, to finish one request
- **Effort** — an evening

> **Milestone** — That loop is what people mean by an agent, and it's about forty lines. Everything you add from here — files, a shell, a browser, your accounts — is another tool it can reach for. The loop itself barely changes again.


### 04 · Harden the loop

**Breaks** — The tool schema and Python registry disagree. A string has the right JSON type but is not a valid timezone. The model keeps requesting tools. A function raises and leaves its `function_call` without an output. A model request succeeds but returns a partial message or tool call.

Check the response before executing it. Catch failures at the tool boundary and send structured error text back to the model, so it can read what went wrong and try something else. Cap executed tool calls. Configure the API client's timeout and retries. Put a timeout inside each future tool that performs blocking I/O; the clock tool does not.

Then handle the truncated response, which looks like success. `status` is `incomplete` and `incomplete_details.reason` is one of exactly two things: `max_output_tokens`, meaning it hit a cap, or `content_filter`, meaning retrying is pointless. Re-sending the identical request is always wrong — same input, same cap, same result, twice the cost. Either raise the cap, or hand back the partial answer and ask it to carry on.

- **Learn** — Letting the model read its own mistakes and correct them. Putting a ceiling on the loop so it can't spin forever. Telling apart a tool that failed from your program that failed, because you handle those two completely differently. And that a successful call can still hand you half an answer.
- **Done when** — You deliberately break a tool and it either works around it or gives up with a clear explanation, without a stack trace. Then you cap the output mid-tool-call and it refuses to run the tool rather than acting on half an argument list.
- **Effort** — an evening


### 05 · Stream it

**Breaks** — Each model call leaves the terminal unchanged until its complete response arrives. If you interrupt a streamed response, partial text is visible but is not a valid message to send back to the API.

Print text deltas as the API emits them. Record those deltas for display, then record the completed API item separately for conversation input. Give every event a turn ID and replay API items only after that turn completes. A second process can follow the JSONL file and render the same progress without calling the model or running a tool.

- **Learn** — Reading typed stream events. Separating display events from canonical API items. Keeping interrupted turns in the record without including them in later model input.
- **Done when** — You can watch text arrive, follow the record from another process, interrupt a turn, and afterward replay what happened from the file alone.
- **Effort** — an evening

> **Why here** — The lines you add now are what the takeover screen reads at Level 9. Change the format after that and you're changing the screen, the replay, and every line already written to the file.


---

## Part II — The Computer

It can work through a problem and call your tools, but it has nowhere to put anything and no way to run what it writes. By the end of Part II it writes files, runs them, and stops to ask you before anything that could do real damage. All of this runs on your laptop, against your real files, and stays that way until Level 15.


### 06 · Give it files

**Breaks** — "Refactor this 400-line file." You paste the file in. It pastes 400 lines back. You paste those into your editor. This isn't software.

An `agent_workspace/` folder and four tools: list, read, write, edit. Every path resolved and confined inside that folder. All four go through one small module that does the actual reading and writing, rather than touching the filesystem themselves.

- **Learn** — How `../` in a path walks straight out of your folder, which is your first security bug. Why replacing a few lines beats rewriting a whole file. How one big file eats the room you had left to send anything else.
- **Done when** — It writes a working Python file whose contents you never saw in the chat
- **Effort** — an evening

> **Why the extra module** — Today it looks like pointless indirection — four tools wrapping four filesystem calls. At Level 15 you point that module at a container instead of your laptop, and none of the four change.


### 07 · Shell access, and asking permission

**Breaks** — It writes `primes.py` and can't run it. So you give it a way to run shell commands. Ten minutes later it runs something you didn't expect and your stomach drops.

A `run_command` tool, going through its own small module the way the file tools do, plus a gate in front of it. The gate sorts commands by what they'd break if the model has misjudged, not by what they do: reading anything is free and runs unasked, writing inside the workspace gets a prompt, and anything reaching the network or the world outside that folder stops and waits. Every command and its outcome goes into a separate audit log.

- **Learn** — The difference between what it's able to do and what it's allowed to do. Sorting actions by whether you can undo them, rather than by what they do. Why listing what's permitted beats listing what's forbidden. Stopping to ask a person without treating it as an error. Keeping an audit log you can read back later.
- **Done when** — It writes code, runs it, reads the stack trace, fixes it, runs it again and succeeds — and you approved exactly the commands you meant to
- **Effort** — a few evenings

> **Foreshadowing** — Stopping, waiting for a person, and carrying on afterward is the same code Level 9 needs. There it waits for a login instead of a yes.


---

## Part III — The Handoff

Most of what you'd want it to do sits behind a website with a login. By the end of Part III it drives a browser, hands you the keyboard when it reaches a page only you can get past, takes it back when you say you're done, and asks before doing anything it can't undo.


### 08 · Give it a browser

**Breaks** — "What's this $5 Railway charge?" Railway has no public interface for programs to call, and neither does your bank, your landlord's portal, or most of the software your life runs on. There's a website and that's it.

Playwright — a library that drives a real Chrome browser — exposed as tools: go to a URL, click, type, read the page, take a screenshot, scroll. Decide deliberately how a page gets described to the model, and keep the browser alive between tasks so it doesn't start cold every time.

- **Learn** — Two ways to show a model a page — a text outline of what's on it, or a screenshot it looks at — and when each is better. Referring to a button in a way that still works after the page redraws. Waiting for pages that aren't ready. The cookies that keep you signed in. Expect this to be the flakiest thing you own.
- **Done when** — It answers a question you didn't give it the steps for, by reading several pages of a public site and putting them together — from a cold start, twice in a row. Point it at Railway and it gets as far as the login page, which is where Level 9 begins.
- **Effort** — a weekend


### 09 · Human takeover  `The Railway task`

**Breaks** — It opens Railway and hits the login page. It can't continue, and the one thing that would let it continue is the one thing it must never be handed.

Five pieces. *One:* it works out that it's stuck on something only you can do, and says so instead of guessing. *Two:* you can see its browser and type into it. *Three:* control passes both ways cleanly, with the loop parked while it waits rather than spinning. *Four:* the signed-in session survives the handover and it picks the task back up. *Five:* before it does the thing that can't be undone, it comes back with what it found *and what it couldn't determine*, then asks. This is the Level 7 gate again, carrying evidence instead of a command — and the hard part is teaching it to report the limits of that evidence rather than the confident summary it would rather give you.

- **Learn** — Treating "needs a person" as an ordinary state rather than a failure. Sending its screen to you and your keystrokes back. Deciding who owns the browser at any moment. Why having you sign in on its machine beats every scheme where you hand over a password.
- **And learn** — Why an agent reporting "no traffic since March, though I can't rule out something that runs monthly" is worth more than one reporting "safe to delete." Naming the specific irreversible thing in the question instead of asking for a general yes. What you do after it acted on an inference that turned out wrong.
- **Done when** — You ask what the $5 monthly charge is, sign in when it asks you to, and it comes back with what the charge is, what it could and couldn't rule out, and a question — then acts when you say yes. On software you wrote, without a password ever going into a chat box.
- **Effort** — a weekend

> **Where you are** — Five levels left after this one. They make it reliable and connect it to your own accounts.


---

## Part IV — Reliability

Two things keep this from being something you rely on. A long conversation eventually exceeds what you can send in a single call, and the task stops halfway. And when you change the system prompt or a tool, you cannot see what the change did, because the model answers differently every run. By the end of Part IV long tasks finish instead of stopping halfway, and you can tell whether a change helped or hurt.


### 10 · Trimming history

**Breaks** — The call fails outright: the conversation is now longer than one request can carry. Reading web pages gets you there fastest — thousands of tokens each — but any long conversation ends here.

You wrote code at Level 1 that reads the current conversation's file and builds the list of messages. Change it to do three more things. Count the tokens in that list before sending it. The limit belongs to the model, not to you, and the reply has to fit inside it as well — so pick a threshold below that limit, and when the list crosses it, ask the model to summarize the oldest messages and append that summary to the same conversation's file as a new line, recording which messages it replaces. Then build the list starting at the newest summary rather than the top of that file. The summarized messages stay on disk — you will want to read them when a summary turns out to have left out something that mattered, and Level 12 searches them. Decide up front what it is never allowed to summarize: the system prompt, the current objective, the last few exchanges, and anything you pinned.

- **Learn** — How much a model can hold, and that going over gets the call rejected rather than slowed. That a long history also makes it answer worse — what you asked for gets buried under old page dumps — so trimming improves the answers as well as making them possible. Summarizing without losing the thread of what you're doing. And the trap that follows: rewriting old messages makes the very next call more expensive, because providers charge less for an opening they have seen before and you just changed it.
- **Done when** — It crosses your threshold in the middle of a task, summarizes, carries on, and finishes — and can still tell you what you originally asked for
- **Effort** — a few evenings

> **Why it all ends up here** — This code becomes the only place that decides what the model sees: trimming now, slipping in a reminder from memory at Level 12, checking permissions once it runs on a machine that isn't yours. Worth keeping it small and worth keeping it in one file.


### 11 · A scored test set

**Breaks** — You rewrite the system prompt to fix how it reads a page, and the Railway task passes. One run can't tell you whether your change did that or whether you got lucky. And either way it says nothing about everything else that prompt affects.

You switch `MODEL` to `gpt-5.6-sol` because the end of the course wants a capable agent. That is not a reason that applies to the tasks you have. Cost goes up. You cannot tell if pass rate moved. You switch to `gpt-5.6-luna` because Sol felt expensive. That is the same decision with the sign flipped.

Twenty to thirty fixed tasks whose outcome a program can check, a runner that puts all of them through one version of your code, and a report: how many passed, what it cost on average, how many passes it took, and how all of that compares to last time.

- **Learn** — Building a test set for something that gives a different answer every run. When a program can check the answer, and when you have to ask a second model to judge it. Catching the thing a prompt or model change quietly broke somewhere else. Treating cost and number of passes as results, not footnotes.
- **Done when** — After changing something you can state what it did to the pass rate and what it did to the cost, and defend both numbers
- **Effort** — a few evenings

> **Note** — Until now a change either felt better or it didn't. From here you run the same twenty tasks before and after and compare the numbers. Luna vs Terra vs Sol is one of those runs.


---

## Part V — Making it yours

Everything you have ever told it is sitting in those conversation files, and it can only see the one it's currently in. By the end of Part V it can go back and find what you told it last week, read your own mail, and take on a new account by adding a folder rather than rewriting anything.


### 12 · Long-term memory

**Breaks** — "Why did we pick Postgres again?" You discussed it three weeks ago, in a different conversation. That file is still on disk. The model has no idea it exists.

Everything ever said is already on disk, spread across the conversation files from Level 1. What's missing is a way to reach into the ones it isn't currently in, and somewhere for the handful of facts that should stay in front of it permanently. So: a `memory.md` it can read and write, and tools to search across old conversations by text or date and pull a stretch of one back into view.

- **Learn** — Why what was said, what it's working on now, and what it knows about you want to be three separate things rather than one. Looking something up as an ordinary tool call, with nothing clever behind it. Deciding *when* a thing is worth writing down, which is the part that stays hard.
- **Done when** — "What did we decide about the database last week?" gets the right answer, long after that stretch of history stopped being sent — and you can open a file and see how it found it
- **Effort** — a few evenings

> **Graduation path** — A markdown file first, then SQLite, then search-by-meaning — each one when the previous visibly stops working. Start with a file you can open, because you'll spend the level debugging what it thinks it remembers.


### 13 · Gmail, and your first real login flow

**Breaks** — "Find the email with my flight details for tomorrow." You could point the Level 8 browser at Gmail, and it's slow, brittle, and breaks whenever Google changes the page. Some things deserve a proper interface.

The full permission handshake: your program opens a Google page, you click approve, Google hands back a short-lived code, and your program trades that code for a key it stores. Then two tools, to search mail and to read it. And one new situation — the tool exists but the account isn't connected yet, so it says so and your screen offers a Connect button instead of failing.

- **Learn** — The handshake, step by step, and why it's built that way. Asking for the narrowest permissions that still do the job. Why the key you get expires in an hour, and how you renew it without clicking approve a second time. Where a key like that is safe to keep.
- **Done when** — It finds a real email in your real inbox, and still works tomorrow after the key it was given has expired
- **Effort** — a weekend

> **Budget warning** — Filling in Google's consent screen configuration will take an afternoon by itself. Plan for it.


### 14 · The plugin system

**Breaks** — You start on Google Calendar and find yourself copying the entire Gmail login module and changing four strings.

A folder layout every account follows — what it's called, how it logs in, what tools it offers — with code that finds them at startup, keeps each one's keys separately, and assembles the list of tools it hands the model. Calendar is the proof: it should take a fraction of the work Gmail did.

- **Learn** — Letting code find what's installed instead of being told about it in a list you maintain by hand. Writing down what an account offers in a form your program can read. Assembling the model's tool list when the program starts, so adding an account is adding a folder.
- **Done when** — A third one — GitHub, Linear, whatever you actually use — needs no changes outside its own folder
- **Effort** — a few evenings


---

## Sketched only — The Fleet

These get designed properly once the fifteen levels above are built and you know what you have. These five are mostly infrastructure rather than anything to do with models, and they cost real money to run.


### 15 · Sandbox it

**Breaks** — You notice that since Level 7 this thing has had shell access to your actual laptop, your actual SSH keys, and your actual browser profile.

It moves into a container — its own filesystem, its own network rules, capped memory and CPU, rebuildable from scratch. Because the file and shell tools each go through one module already, most of this is pointing those two somewhere else.

- **Effort** — a weekend


### 16 · A cloud computer per assistant

**Breaks** — Containers die and take the signed-in Railway session with them, and everything still needs your laptop to be awake.

Something that manages real machines: create, start, stop, snapshot, resume, destroy, with a disk that survives. The starting image, how long boot takes, and what it costs to leave one running.

- **Effort** — several weekends


### 17 · Separate assistants

**Breaks** — One assistant with one memory file knows about your travel plans, your codebase, and your finances at once, and brings up the wrong one every time.

Several of them, each with its own instructions, memory, connected accounts, folder, machine, and history — with many conversations belonging to each, rather than a new assistant every time you open a chat.

- **Effort** — a few evenings


### 18 · Background work

**Breaks** — You give it a twenty-minute job, close your laptop, and it dies along with the web request that started it.

Jobs go into a queue and separate processes pick them up: saving progress as they go, resuming after a crash, reporting they're alive, retrying, and telling you at 11am that the thing you asked for at 9 is done.

- **Effort** — a weekend or more


### 19 · Production

**Breaks** — Someone other than you wants to use it.

Somewhere safe to keep keys, a per-assistant audit log of everything it did, a written policy for what needs approval, rate limits, spending caps, shutting down machines nobody is using, and enough visibility to answer "what did it do at 3am and what did it cost."

- **Effort** — no end — this is the job, not a level


## What's not in the course

Things you'd expect to see in something like this, and why they aren't here.

- **Training a model of your own** *(Out of scope)* — It would roughly double the length, and it isn't the part you're missing. You're building the software around a model somebody else trained.
- **Off-the-shelf agent libraries** *(Deferred to L14)* — You write your own tool registry, loop, and record-keeping first. Then read two things: the Model Context Protocol, which standardizes how tools get described to a model, and DeepSeek Harness, which builds the loop, the tool registry, the conversation log and the approval gate at industrial scale — though not the memory or the account connections. Both read completely differently once you've built the thing they generalize: you recognize the parts instead of decoding them, and you have opinions about the ones you'd have done another way.
- **Assistants delegating to each other** *(Appendix)* — Hard to motivate for something you're the only user of. Most of what's useful at this scale is handing a sub-task to a second loop so the main one's history stays clean, which belongs as a note at Level 10, where keeping the history small is the subject.
- **Search by meaning rather than keyword** *(Part of L12)* — Storing text as vectors so you can find it by similarity. Worth reaching for when a markdown file and plain search stop being enough — nothing else on the ladder depends on it.


## Still open

Assumed so the roadmap could exist. Cheap to change now, expensive later.

### Repo shape: one folder per level, the writing beside the code

`levels/03-loop/` runs on its own, and the lesson beside it explains what changed since Level 2 and why. You can start at any level, and comparing two folders shows exactly what a feature cost. The duplication grows as you go; from Level 12 on the folders share a common package.

**Alternative:** One codebase that grows the whole way. More satisfying to watch, much harder to join partway through.

### Stack: Python throughout  `closed`

The loop and the tool descriptions read cleanest in Python. Playwright has a Python API, including a headed Chrome window (`headless=False`). Level 9's takeover is you typing in that window, on its machine — not a separate web app. Switching languages at the browser would rewrite the loop for no mechanism the lesson needs.

A custom takeover UI in the browser would be a reason to add TypeScript. That is not this course.

### Provider: OpenAI, called directly

No wrapper that lets you swap providers. A wrapper at Level 0 would hide the exact thing Level 0 exists to show. Add one later only if a lesson needs it.

**Needs you:** Whether you already have a key set up.

### How long any of this takes

The effort figures are guesses. Levels 0 through 5 are built; the rest would change with whoever is building them — so they're worth reading as relative weight only: Level 9 is a much bigger piece of work than Level 2. Replace each one with the real figure as the level gets built.

### Audience

Changes the tone, how much hand-holding each lesson gets, and how much code is written out versus left as the exercise.

**Needs you:** You learning in public, or a finished thing strangers follow.

### Where it ends

Levels 0 to 14 stand on their own and finish with the Railway task working. The five after that are sketched far enough that the architecture doesn't paint itself into a corner, and no further.

**Open:** Whether one container per assistant is a fine place to stop, or whether you specifically want a full virtual machine per chat the way Cursor appears to run it.


---

*Draft v0.2 · Levels 0–5 built · Effort figures are guesses until a level has been built*
