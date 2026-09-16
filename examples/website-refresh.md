# Example: Website refresh

**Task ID:** `example-website-refresh`  
**Status:** example

## Objective
Refresh a marketing page without changing its information architecture.

## Constraints
- Preserve existing URLs and analytics events.
- Keep the current brand typography.
- Avoid adding runtime dependencies unless necessary.
- Mobile layout must remain usable at 320px width.

## Acceptance criteria
- [ ] Existing navigation and links still work.
- [ ] Core Web Vitals do not regress materially in local checks.
- [ ] No horizontal overflow at 320px, 375px, and 768px widths.
- [ ] Existing automated tests pass.

## Example handoff

```text
Result: Hero and case-study cards updated; navigation untouched.
Evidence/changes: src/Hero.tsx, src/CaseStudies.tsx; responsive checks at 320/375/768.
Risk/blocker: Background video still needs production asset compression.
Next: Reviewer — check reduced-motion behavior and link regressions.
```

This example shows the intended level of detail: enough to preserve decisions and risks, but not a transcript of every intermediate thought.
