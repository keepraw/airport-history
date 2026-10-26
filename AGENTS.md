# Agent commit identity

Commits created by coding agents in this repository must use the repository
owner's GitHub identity for both author and committer:

- Name: `keepraw`
- Email: `49091395+keepraw@users.noreply.github.com`

Before committing, configure the current checkout explicitly:

```sh
git config --local user.name keepraw
git config --local user.email 49091395+keepraw@users.noreply.github.com
git config --local user.useConfigOnly true
```

Check `git var GIT_AUTHOR_IDENT` and `git var GIT_COMMITTER_IDENT` before
creating a commit. Both must match the identity above; environment variables can
override Git configuration. Check the resulting commit with
`git log -1 --format=fuller` before pushing. Do not inherit the execution
environment's global identity or add an unrelated co-author trailer.
