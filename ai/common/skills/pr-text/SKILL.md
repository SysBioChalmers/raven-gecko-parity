---
name: pr-text
description: Style for pull request titles and bodies, commit messages, and issue text in RAVEN, GECKO, raven-toolbox, geckopy and raven-gecko-parity. Use when writing or editing any of these.
---

# Pull request and commit text

The reference example is
[SysBioChalmers/RAVEN#734](https://github.com/SysBioChalmers/RAVEN/pull/734).

## Title

A plain statement of what changed, under about 70 characters. No "This PR..." and no
prefix unless the repository requires one. RAVEN and GECKO use semantic commit prefixes
(`fix:`, `feat:`, `doc:`, `refactor:`, `style:`, `chore:`) for commit subjects. A pull
request that bundles independent fixes states how many: "Fix eight bugs found in develop3
review". When a later commit adds another fix, update the count.

## Body

1. One sentence on why these changes are grouped, then a blank line. No headers.
2. One bullet per change. The bullet starts with the function, file or component in
   backticks, then a colon, then one sentence that states what was wrong: the bug or
   behaviour, with the mechanism if it is not obvious. The bullet does not describe the fix
   or restate the diff; the code and the commit body carry that.
3. No Testing section, no "Still failing" section, no checklist, no preamble, no emoji. When
   verification matters, add one line, for example "Each fix has a regression test."

Example bullet:

> `gapFillFastCore`: a reversible core reaction's forward and reverse copies, both forced to
> carry flux, canceled each other out in the mass balance, so every reversible core reaction
> was reported as network-consistent regardless of actual connectivity.

The RAVEN and GECKO pull request templates ask for a list of main improvements and a merge
target checkbox. Keep the template's checkbox and put the bullets above in its list.

## Posting to GitHub

- Write the body to a file and pass it with `gh pr create --body-file <file>` (or
  `gh issue create --body-file`, `gh pr edit --body-file`).
- Backticks stay plain. A backslash before a backtick appears as a literal backslash on
  GitHub.
- In PowerShell, a double-quoted string treats the backtick as an escape character and
  corrupts inline code. Edit body files with a file editor, not with a PowerShell string
  replacement.
- Link to source in the four code repositories with the integration branch in the URL
  (`blob/develop3/...`, `blob/develop4/...`, `blob/develop/...`, `blob/main/...`), never a
  commit SHA.
- Cross-repository references use the `owner/repo#number` form, for example
  `SysBioChalmers/geckopy#12`.
