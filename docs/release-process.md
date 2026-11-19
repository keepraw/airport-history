# Release process

Use Node.js 24 and pnpm 10.14.0 with the locked dependencies. Keep the data
commit referenced by the production manifest available to CI and consumers.

## First publication

Data `0.14.0` in Schema `4.0.0` is the initial production dataset. Validate
the source tree before creating the root commit.

```sh
pnpm install --frozen-lockfile
pnpm typecheck
pnpm validate:data
pnpm test
pnpm build
sha256sum data/airports.json
```

Use the root commit as the immutable data commit. With that commit at `HEAD`,
generate the production manifest and run the release checks.

```sh
pnpm manifest:generate --commit "$(git rev-parse HEAD)"
pnpm manifest:check --release
pnpm check
```

Commit the generated `data/production-manifest.json` in a separate commit on
top of the root commit.

## Release checks

```sh
pnpm install --frozen-lockfile
pnpm check
pnpm manifest:check --release
```

`pnpm check` type-checks, validates the schema and data, runs the tests,
verifies the published manifest against its immutable commit, and builds the
distribution. `pnpm manifest:check --release` also requires the checked-out
data bytes and query horizon to match the production pointer. A newer data
version can pass ordinary CI while awaiting its manifest.

## Publish a subsequent data version

1. Review and validate the data. When publishing new data, advance the dataset
   and package versions together. Land the reviewed data commit on `main`.
2. Start the manifest change from that commit or a descendant. Use the full SHA
   on `main` that contains the reviewed bytes, including after a squash merge.

   ```sh
   git fetch origin main
   pnpm manifest:generate --commit "$(git rev-parse origin/main)"
   pnpm manifest:check --release
   ```

3. Commit the manifest separately and open a publication PR. Verify the
   resulting `main` in GitHub Actions after the PR is merged.

## Release artifacts

For an authorized GitHub release, tag the checked manifest commit with
`data-v<version>` and attach the manifest, the distribution from
`dist/v<version>/`, and release notes with the source SHA-256.

The production manifest at `data/production-manifest.json` records the data
and schema versions, immutable commit, query horizon, and SHA-256 of the
unchanged source bytes at `data/airports.json`. Consumers can download the
file at that commit and compare its digest.

The distribution build sorts keys and stable-ID collections and writes
`airport-history.json`, `dataset.schema.json`, three license and attribution
files, and `manifest.json`. That manifest provides separate checksums for the
five distribution files.
