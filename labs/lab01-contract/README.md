# Lab 01 - The agent contract

You will write a read-only `bug-hunter` agent. It must find a planted bug in a
small repo and answer with a strict JSON report. A harness runs your agent with
`claude -p` on fresh copies of the repo and scores it.

## The agent contract

An agent is a markdown file. A good one spells out six things:

1. **Role** - who the agent is and what it is for.
2. **Input** - what it will be given (here: a bug symptom).
3. **Tools** - what it may use. Keep it minimal; this agent only reads.
4. **Steps** - the procedure to follow, in order.
5. **Output format** - exactly what the final answer looks like.
6. **Stopping rule** - when it is done, so it does not wander.

## The task

The agent receives this prompt:

> The shop gives a 10% bulk discount when you buy 10 or more units of an
> item. Customers who buy exactly 10 units are charged full price: 10 units
> at $2.00 cost $20.00 instead of $18.00. Buying 11 units works ($19.80).
> Find the root cause in this repository and report it.

The repo (`fixture/`) is a tiny shop library. The symptom is in the cart, the
cause is elsewhere. The agent must search and read to find it, and must never
edit anything.

## How your agent is run

Your file is a Claude Code **subagent** definition (not a skill). For each run
the harness:

1. copies the repo into a fresh temp folder,
2. puts your file there as `.claude/agents/bug-hunter.md`,
3. runs `claude -p --agent bug-hunter` and sends the task prompt above as the
   user message.

So your agent file is the **system prompt**: a reusable contract (role, tools,
steps, output, stopping rule). The task prompt is the **user message**, and it is
injected at run time. Don't hard-code this bug into your agent: the variants move
and rename the code.

## Required report

The agent's final answer must be ONLY this JSON object:

    {"file": "<repo-relative path>", "line": <int>, "cause": "<one sentence>", "fix": "<one sentence>"}

No prose around it, no code fence, no extra keys.

## Write your agent

Create your agent file from the starter template, then fill in its TODOs:

    agentplayground start lab01    # creates workspace/.claude/agents/bug-hunter.md

## Run it

    agentplayground check lab01 --quick    # one fast run on the base repo
    agentplayground check lab01            # full run: base + variants, repeated

The full run also tries variants: the bug moved to another line, the code moved
to a renamed file, and a decoy module with a misleading comment.

## Scores

- **Structure** - is the agent file well formed and does the contract cover the
  six parts? (coded checker only; the LLM judge does not grade structure)
- **Behavior** - did it find the right file and line (within 2 lines; `line` is
  1-based), and is the answer exactly the JSON object, with no prose, fence or
  extra keys? (coded checker for file/line/JSON strictness, LLM judge for cause
  and fix quality.) Editing any file does not lower this score directly, but it
  fails the run, which hurts robustness.
- **Speed** - how long a run took against the 90 second budget.
- **Robustness** - does it still succeed on the variants and give consistent
  answers across repeated runs?

## Hints

1. Say what the final message must look like, and say it twice if needed: the
   JSON only, nothing else.
2. Tell the agent how to search: start from the symptom's numbers and words,
   then follow the code from the caller to where the value is computed.
3. Add a stopping rule and a rule about unreachable or "suspicious looking"
   code, so it does not chase decoys or keep exploring after it has the answer.

## Don't peek

`solution/` holds a reference agent. Try on your own first, then compare.
