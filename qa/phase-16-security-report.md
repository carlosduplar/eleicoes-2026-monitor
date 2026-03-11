# Phase 16 Security Review Report

## Scope

- `.github/workflows/*.yml`
- `scripts/collect_parties.py`
- `scripts/summarize.py` and `scripts/ai_client.py`
- `site/src/pages/CaseStudyPage.jsx`
- All `target="_blank"` links in `site/src/**/*.jsx`
- `data/*.json`

## Findings

| Risk | Location | Severity | Status | Notes |
|---|---|---|---|---|
| Reverse-tabnabbing via external links | `site/src/pages/CandidatePage.jsx` | Medium | Fixed | Updated links to `rel="noopener noreferrer"` for all `target="_blank"` anchors in candidate page. |
| Potential XSS surface from markdown HTML rendering | `site/src/pages/CaseStudyPage.jsx` | Medium | Fixed | Added output sanitization before `dangerouslySetInnerHTML` to strip `<script>`, inline event handlers, and `javascript:` URLs. |
| Secret exposure in workflows | `.github/workflows/*.yml` | Low | Mitigated | API tokens are sourced from `${{ secrets.* }}`; no hardcoded credentials found. |
| Prompt-injection / malformed AI output propagation | `scripts/summarize.py`, `scripts/ai_client.py` | Low | Mitigated | Responses are parsed as JSON with strict normalization; parse failures fall back safely and are logged. No code execution path from model output. |
| PII leakage in committed data | `data/*.json` | Low | Open (monitor) | No dedicated PII fields found; article bodies can still contain public-person references from source content. Keep periodic redaction checks in pipeline QA. |

## OWASP-focused Notes

- **Injection:** No SQL/command injection paths identified in reviewed code.
- **Security misconfiguration:** Workflows rely on GitHub Secrets; no plaintext keys in repository files.
- **XSS:** Case study rendering path hardened in this phase.

## Conclusion

No **CRITICAL** or **HIGH** unresolved findings remain after Phase 16 changes.
