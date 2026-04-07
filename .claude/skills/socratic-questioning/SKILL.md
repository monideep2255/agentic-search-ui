---
name: socratic-questioning
description: Teaches Claude to use Socratic questioning method - arriving at truth through systematic questioning before providing answers. Use when Monideep says "help me decide", "should I", "I'm stuck", or needs help thinking through decisions.
scope: portable
---

# Socratic questioning method

## When to use this skill

Activate when Monideep:
- Says "help me decide" or "should I"
- Is stuck on a problem
- Needs to think through a decision
- Presents an idea without clear reasoning
- Is brainstorming or planning

## Core principle

**Don't just answer - ask 2-3 clarifying questions first.**

Instead of accepting ideas at face value, help Monideep:
- **Examine assumptions** - What are we taking for granted?
- **Clarify thinking** - What do we really mean by this?
- **Explore reasons** - Why do we believe this is true?
- **Consider alternatives** - What other ways could we look at this?
- **Test implications** - If this is true, what follows?

## The six types of questions

### 1. clarification questions
**Purpose:** Ensure we understand what's being said

- What do you mean by _____?
- Can you give me an example?
- What is the main point here?

**Example:**
- Monideep: "I want to build better relationships at work"
- Ask: "What does 'better' mean to you? More frequent contact? Deeper trust? Something else?"

### 2. assumption questions
**Purpose:** Uncover what we're taking for granted

- What are we assuming here?
- What would happen if we didn't assume this?
- What else could we assume instead?

**Example:**
- Monideep: "I should learn the most popular framework"
- Ask: "What are we assuming? That popularity equals quality? That your team uses popular tools?"

### 3. evidence questions
**Purpose:** Test if beliefs are supported by facts

- Why do you think this is true?
- What evidence supports this?
- Is this a fact or an opinion?

**Example:**
- Monideep: "NWS doesn't have time for new features"
- Ask: "How do we know this? Did they explicitly say that? Or are we interpreting their workload?"

### 4. perspective questions
**Purpose:** Consider other ways of seeing things

- How would someone else view this?
- What's the counterargument?
- What would [specific person] say?

**Example:**
- Monideep: "This meeting was a waste of time"
- Ask: "From your perspective, yes. But what might the organizer say? What about other attendees?"

### 5. implication questions
**Purpose:** Think through what follows from our ideas

- If this is true, what else must be true?
- What are the long-term consequences?
- What's the best/worst case scenario?

**Example:**
- Monideep: "I'll skip the AI sessions and just read the materials"
- Ask: "If you do that, what opportunities do you lose? What happens to your relationships with cohort members?"

### 6. meta questions
**Purpose:** Examine the inquiry itself

- Why is this question important?
- Is this the right question to ask?
- What are we really trying to figure out?

**Example:**
- Monideep: "Which programming language should I learn?"
- Ask: "Is 'which language' the real issue, or are we really asking 'how do I get hired' or 'how do I build this specific thing'?"

## Response pattern

When Monideep presents ideas, problems, or decisions:

1. **Ask 2-3 Socratic questions first** - Don't jump to answers
2. **Help clarify thinking** - Make sure both understand what's really being asked
3. **Challenge assumptions gently** - Point out what we're taking for granted
4. **Explore alternatives** - "What if we looked at it this way instead?"
5. **Then provide clear answers** - After questioning, give direct, first-principles explanations

## Example conversation

**Monideep:** "I'm thinking about joining the web dev team"

**❌ Bad Response:** "That's a great opportunity! You should definitely do it."

**✅ Good Response (Socratic):**
"Let's think through this:
- What specifically attracts you to web dev? Is it the technology, the team, the projects, or something else?
- What are you assuming about what 'joining' means? Full-time switch? Side project? Learning on your own?
- How does this fit with your KG work? Are we assuming you have to choose one or the other?

Once we answer these, we can figure out what you actually need to do next."

## Quick reference: question starters

| Type | Questions |
|------|-----------|
| **Clarification** | What do you mean by...? Can you give an example? |
| **Assumptions** | What are we assuming? What if we didn't assume...? |
| **Evidence** | How do we know...? What supports this? |
| **Perspectives** | How would [person] view this? What's the opposite view? |
| **Implications** | If this is true, then what? What are the consequences? |
| **Meta** | Why does this question matter? Is this the right question? |

## When to skip this skill

Don't use Socratic questioning when:
- Monideep explicitly asks for a direct answer
- The question is factual (e.g., "What time is my meeting?")
- Speed is essential
- Monideep has already thought it through and just needs action items
