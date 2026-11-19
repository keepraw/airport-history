# Agent instructions

## Commit identity

Use `keepraw <49091395+keepraw@users.noreply.github.com>` for the author and
committer of agent-created commits.

```sh
git config --local user.name keepraw
git config --local user.email 49091395+keepraw@users.noreply.github.com
git config --local user.useConfigOnly true
git var GIT_AUTHOR_IDENT
git var GIT_COMMITTER_IDENT
```

Verify both identities before committing and check `git log -1 --format=fuller`
before pushing. Write commit messages in English.

## Formal data

- Keep the same `airportId` for a physical site when its codes or names change.
  Assign predecessors and replacement airfields separate identities.
- Evaluate IATA and ICAO independently. Preserve uncertain bounds and use
  half-open local-date intervals.
- Review factual changes in the pull request and preserve attribution.
  [Data policy](docs/data-policy.md)
- Run `pnpm check` with Node.js 24 and pnpm 10.14.0. For a data publication,
  record the immutable data commit and verify the production manifest.
  [Release process](docs/release-process.md)
