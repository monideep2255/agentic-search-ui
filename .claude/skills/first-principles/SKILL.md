---
name: first-principles
description: Explains concepts using first-principles thinking - breaks complex topics into fundamental truths with simple language. TRIGGER when user asks "what is X", "explain Y", "how does X work", "teach me about", "I don't understand", or needs a technical concept clarified. Also trigger on "break this down" or "ELI5". DO NOT TRIGGER for career advice (use board) or skill practice (use forge).
scope: portable
---

# First principles & simple explanations

## When to use this skill

Activate when Monideep:
- Asks "what is X" or "how does Y work"
- Needs a technical concept explained
- Is learning something new
- Wants clarity on a complex topic

## Core approach

### 1. first principles thinking

Break down complex topics into their most basic, fundamental truths:

- **Strip away assumptions** - Don't accept "that's how it's always been done"
- **Get to the core** - What is this really about at its essence?
- **Build up from basics** - Start with what we know for certain, then build reasoning from there
- **Ask "why" repeatedly** - Keep digging until you hit bedrock truth
- **Name the axioms** - State what you're treating as foundational truth before reasoning from it
- **Default to skepticism** - The burden of proof is on the belief, not on the challenge to it
- **Distinguish from analogy** - "This is like X" is analogy. "This must be true because of X" is first principles. Both are valid; they're not the same

**What is an axiom?** A statement you accept as true without needing to prove it, because everything else you reason about depends on it. The floor you stand on before building anything  -  you check that it's solid, then you build on it. An axiom is NOT the same as an assumption: an assumption is taken for granted without examining it; an axiom is examined, decided to be solid, and stated out loud so others can challenge it.

**Example axiom:** "People generally act in their own interest." You can't prove this universally. But accepting it as a starting point lets you reason about why incentive structures work, why policies fail when they ignore motivation, why people leave jobs.

**Example:**
- ❌ Bad: "You need to use Django because it's the standard framework"
- ✅ Good: "Django is a tool that helps you build websites. It gives you pre-built components (login systems, databases, forms) so you don't rebuild everything from scratch. You'll learn Django because your team uses it and you'll need to maintain their existing work."

### 2. very simple terms

Use plain language that anyone could understand:

- **No jargon unless necessary** - Avoid technical terms when possible
- **Define terms when used** - If you must use technical language, explain it immediately
- **Short sentences** - One idea per sentence
- **Concrete examples** - Use real-world analogies and specific scenarios
- **Active voice** - "You will do X" not "X should be done"

**Example:**
- ❌ Bad: "Leverage the knowledge graph infrastructure to facilitate cross-functional synergies"
- ✅ Good: "Use the knowledge graph to help different teams share information more easily"

### 3. actionable focus

When giving summaries or recommendations, always include:

- **What was discussed** - The topics covered
- **What it means** - Why it matters in simple terms
- **What YOU need to do** - Clear action items with concrete next steps
- **Who, what, when, where, how** - Specific details, not vague suggestions

**Example:**
- ❌ Bad: "Consider reaching out regarding the project"
- ✅ Good: "Send an email to Tahir by Friday asking: What does web dev onboarding look like? How many hours per week? Can I start in January?"

## Output format

When explaining concepts:

```markdown
## What is [x]?

[1-2 sentence simple definition that anyone could understand]

## Why does it exist?

[The problem it solves, in plain terms]

## How does it work?

[Step-by-step explanation, simple language]

## What this means for you:

[Practical implications, specific action items]
```

## What first-principles thinking actually looks like

Six behavioral criteria (from Aristotle through Bezos):

| Criterion | Means in practice |
|-----------|-------------------|
| **Separate knowledge from assumption** | Can tell the difference between what they verify and what they merely believe |
| **Name the axioms out loud** | Declare the starting point before reasoning from it |
| **Default to skepticism** | Burden of proof is on the belief, not on the challenge |
| **Follow purpose, not process** | Discard a rule when it stops serving its purpose |
| **Identity not tied to conclusion** | Abandon a conclusion when the facts shift |
| **Treat every problem as new** | Don't reach for the template |

**The underlying trait:** A first principles thinker has a disposition toward knowledge, not a domain or a technique. They treat beliefs as things to be earned, not inherited.

When explaining concepts, model these behaviors. When Monideep asks "what is X", your explanation should itself demonstrate first-principles reasoning  -  not just use simple language.

## Limits to be honest about

- **Axiom verification**  -  How do you confirm axioms are truly foundational and not just deeper assumptions?
- **Conflicting first principles**  -  Two people can reason from first principles and reach opposite conclusions
- **Survivorship bias**  -  The method doesn't guarantee the outcome; it guarantees the reasoning is grounded

## Patterns to avoid

- ❌ Corporate buzzwords (synergy, leverage, bandwidth, etc.)
- ❌ Vague language ("look into this", "consider that")
- ❌ Assuming knowledge - explain context
- ❌ Passive voice excessively
- ❌ Making things sound more complicated than they are
- ❌ Justifying with "that's how it's done" or "it worked for [famous person]"

## Quality check

Before responding, verify:
- [ ] Did I break this down to first principles?
- [ ] Did I name the axioms I'm reasoning from?
- [ ] Could a non-expert understand this?
- [ ] Did I avoid unnecessary jargon?
- [ ] Am I explaining *why* something is true, not just *that* it is true?
- [ ] Are my action items specific and clear?
- [ ] Did I use active voice and short sentences?
- [ ] Would I talk this way to a smart friend at coffee?
- [ ] If I can't name the axiom, am I reasoning from habit?

If "no" to any of these, revise.
