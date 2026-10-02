---
name: doc-prose
description: Checks for documentation prose (README, docs pages, CHANGELOG entries, docstrings, ledger reasons) in the RAVEN and GECKO repositories. Use when writing or reviewing any prose a reader sees.
---

# Documentation prose

No em dashes anywhere: not in prose, headings, table cells or generated strings. Use the
punctuation the sentence calls for: a comma where the clause continues, a semicolon where
it is independent, a colon where what follows defines or enumerates what precedes it,
parentheses around an aside.

Apply these five checks to each sentence while writing it:

1. **Can the subject perform the verb?** A file, field, option, table or tool can be,
   contain, return, raise or take precedence. It cannot win, know or want, and it does not
   do anything quietly, silently, loudly or conveniently. A manner adverb on an inanimate
   subject is the most common fault.
2. **Does the sentence tell the reader what is worth doing?** Remove "worth using", "worth
   having", "reach for" and "the usual way". State the behaviour and the condition it holds
   under; the reader makes the choice.
3. **Is the sentence about the document instead of the software?** Remove "this page is
   about", "that is the point of the example" and "as mentioned above".
4. **Does a word minimize something?** Delete "just", "simply", "merely", "only", "of
   course" and "not a bug", then check that the sentence still says what it needs to.
5. **Would a non-native English reader parse the sentence on the first pass?** Remove
   idioms, figures of speech and headline-style fragments that drop the subject or verb.
   Write the complete, literal sentence that a word-by-word translation still gets right.
   Keep the technical precision.

A sentence that would stay true if the software behaved differently is not documentation.
Remove it.

## Where prose goes

- User documentation for both toolboxes is on
  [raven-docs](https://raven-docs.readthedocs.io/). raven-toolbox has no user
  documentation tree of its own.
- Development records (roadmaps, backlogs, benchmarks, design notes for unfinished
  features) are in `raven-gecko-parity/docs/`.
