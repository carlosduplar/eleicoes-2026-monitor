# ADR 006 — Transparency and Methodology Page

## Status
Accepted

## Context
This portal uses AI to generate summaries and sentiment scores on electoral news. Without transparency, users cannot distinguish AI analysis from editorial opinion. The GDPR-adjacent principle of explainability applies, even for public non-personal data.

## Decision
A dedicated /metodologia page is mandatory. MethodologyBadge links to it from every data-driven component. The page discloses: independence, pipeline steps, AI providers, known limitations, and an error reporting channel.

## Consequences
- Users can audit methodology and report errors
- MethodologyBadge acts as a trust signal on all dashboards
- ADR is living documentation — update when new AI providers or sources are added
