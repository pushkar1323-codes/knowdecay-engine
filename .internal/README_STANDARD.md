# README.md Documentation Standard

> **Status:** Permanent project rule — applies to all future README updates.

## Core Principle

The README is the project's **public landing page**, not internal documentation.
It must read as a polished, professional GitHub project page at all times.

## Repository Scope Rule

README.md must represent **only the contents of this repository**.

- This repository contains the **KnowDecay Engine** — the backend API and retention intelligence system.
- Do not document components that belong to another repository, service, application, or future project.
- Frontend applications, mobile apps, admin dashboards, LMS plugins, browser extensions, and SDKs — if developed separately — must have their own README files in their own repositories.
- Future platform or client applications may be mentioned **only briefly** under Roadmap or Ecosystem sections and must be **clearly identified as separate projects or planned integrations**.

## Identity

KnowDecay Engine serves two integration models:
1. **Standalone Backend** — Complete backend for an intelligent learning platform
2. **RIaaS API** — Retention Intelligence as a Service for third-party integrations

## Target Readers

Developers, contributors, recruiters, institutions, researchers, open-source users, API consumers, potential customers.

## Core Rule — Update, Never Regenerate

Always modify the EXISTING README.md. Never regenerate from scratch unless explicitly instructed.

Before making changes:
1. Read the existing README.md.
2. Inspect the actual repository.
3. Verify the current implementation.
4. Identify what has changed.
5. Update only the sections affected by those changes.

## Never Include

- Phase numbers, implementation summaries, task counts, prompt names
- Internal planning, development logs, roadmap percentages
- References to PROJECT_SPECIFICATION.md, MASTER_PROJECT_RULES.md, REQUIREMENTS.md
- AI tool names (Claude, Antigravity, ChatGPT, GPT, OpenAI, Anthropic)
- File-level implementation details
- Features, dashboards, or applications that do not exist in this repository
- Internal .internal/ files, implementation plans, or development artifacts
- Real secrets, API keys, or production credentials

## Documentation Links — Minimal Only

Only link documentation that provides substantial information not in README.md.
The three primary documentation links are:

1. **API Reference** — if the project exposes a substantial API
2. **Architecture** — if detailed architecture is useful
3. **Deployment** — if deployment requires detailed instructions

Do NOT create a large documentation table listing every file in `docs/`.

## README Should Not Duplicate Documentation

Do NOT copy large sections from documentation files into README.md. The README provides a concise overview. Detailed architecture, database schema, security procedures, and operations belong in their own dedicated files.

## Accuracy Rule

Never fabricate or assume: API endpoint counts, database table counts, test counts, performance metrics, benchmark results, supported platforms, security capabilities, ML capabilities, deployment capabilities, architectural components, or integrations.

If a number may have changed, verify it before including it. If verification is inconvenient and the number is not important, omit it.

## Product vs Future Features

- **Implemented**: Features that actually exist in the repository.
- **Planned**: Features intended for future development but not implemented.

Never present future architecture as current functionality. Never advertise ML models, MLOps, Redis, Celery, enterprise SSO, OAuth, MFA, API keys, or cloud infrastructure as implemented unless they actually exist.

## Roadmap Style

Use product-oriented categories (e.g., "Machine Learning Augmentation", "Enterprise Integrations"), NOT numbered development phases.

## Quality Checklist

Before finalizing any README update, verify it answers:
1. What is KnowDecay Engine?
2. Why was it built?
3. What problem does it solve?
4. Who is it for?
5. What can it currently do?
6. What is planned for the engine?
7. How do I run it?
8. How do I integrate with it?
9. How do I contribute?
10. Where can I learn more?

### Final Verification

- [ ] Project description is accurate
- [ ] Current features are accurate
- [ ] Architecture summary is accurate
- [ ] Technology stack is accurate
- [ ] Installation instructions work
- [ ] API information is accurate
- [ ] Test commands are accurate
- [ ] License is accurate
- [ ] No phase references
- [ ] No AI tool names
- [ ] No unnecessary documentation links
- [ ] No secrets
- [ ] No fabricated metrics
- [ ] README matches actual implementation

## Reference Projects

Supabase, Appwrite, Cal.com, Plane, Docmost, OpenMRS, Payload CMS, Directus
