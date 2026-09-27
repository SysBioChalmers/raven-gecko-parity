# RAVEN and GECKO repository family

This repository is one of five that are developed together:

| Repository | Language | Integration branch | Role |
|---|---|---|---|
| SysBioChalmers/RAVEN | MATLAB | `develop3` | Genome-scale model reconstruction and analysis |
| SysBioChalmers/raven-toolbox | Python | `develop` | Python implementation of RAVEN |
| SysBioChalmers/GECKO | MATLAB | `develop4` | Enzyme-constrained models, built on RAVEN |
| SysBioChalmers/geckopy | Python | `main` | Python implementation of GECKO, built on raven-toolbox |
| SysBioChalmers/raven-gecko-parity | Python | `develop` | Parity ledgers and behaviour scenarios for both pairs |

The default branch of RAVEN and GECKO is `main`, which holds releases. Pull requests target
the integration branch in the table.

## Rules for every change

- **Parity.** Each MATLAB/Python pair has a ledger in raven-gecko-parity
  (`ledgers/raven.yml`, `ledgers/gecko.yml`) that gives every public function a status.
  Before finishing a bug fix or feature, look up the functions you changed. A `parity` row
  means the sibling implementation probably needs the same change: say so in your summary
  and open or reference a sibling issue. A new public function needs a ledger row in the
  same change. The `parity-ledger` skill has the statuses and commands.
- **Authorship.** Commit messages, pull request titles and bodies, code, comments, branch
  names and file names contain no reference to AI tools or assistants and no
  `Co-Authored-By` trailer for one. Rename a tool-generated branch (for example `claude/...`)
  before opening a pull request; renaming it afterwards can close the pull request.
- **Merging.** Do not merge a pull request. Report its CI result and leave the merge to a
  maintainer. Within one task, push further commits to the open pull request instead of
  opening a new one, unless the work is in a different repository.
- **Pull request and commit text.** Follow the `pr-text` skill. Write GitHub bodies to a file
  and pass them with `--body-file`; backticks in the body stay unescaped.
- **Links.** A GitHub link into one of the four code repositories uses the integration
  branch name from the table, never a commit SHA.
- **Documentation prose.** Follow the `doc-prose` skill. No em dashes in any file.
- **Code comments.** A comment describes what the code does, or why it is structured this
  way when that is not obvious. No comments about code history ("previously", "changed
  from", "fixed to") and no comments narrating an edit.
- **YAML.** Block sequence entries are indented two spaces past their parent key. A YAML
  writer sets this indentation explicitly instead of relying on a library default.
