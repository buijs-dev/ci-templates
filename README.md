# CI Templates
[![](https://img.shields.io/badge/Buijs-Software-blue)](https://buijs.dev/)
[![GitHub](https://img.shields.io/github/license/buijs-dev/ci-templates?color=black)](https://github.com/buijs-dev/ci-templates/blob/main/LICENSE)

Shared GitHub Actions.

## Contents

| Path                                     | Type              | Purpose                                                                                                     |
|------------------------------------------|-------------------|-------------------------------------------------------------------------------------------------------------|
| `.github/actions/setup-java`             | composite action  | Installs the JDK from `<root-dir>/.sdkmanrc` (temurin) and sets up Gradle                                   |
| `.github/actions/release-changelog`      | composite action  | Moves `## [Unreleased]` of the changelog to `## [X.Y.Z] - <date>`, or reads the notes of a released version |
| `.github/actions/notify-repository`      | composite action  | Sends a `repository_dispatch` event to another repository (warns and skips without a token)                 |
| `.github/actions/horizon-check`          | composite action  | Checks a `horizon/` directory: the manifest, the frontmatter and that every relative link resolves          |
| `.github/workflows/astro-pages.yml`      | reusable workflow | Build an Astro (Starlight) site, optionally from other public repositories, and deploy to GitHub Pages      |
| `.github/workflows/coverage.yml`         | reusable workflow | `./gradlew check koverXmlReport` and upload to Codecov                                                      |
| `.github/workflows/horizon-docs.yml`     | reusable workflow | Check `horizon/` (a repository's pages on docs.stratastax.dev) and ask the site to rebuild after a push     |
| `.github/workflows/publish-snapshot.yml` | reusable workflow | Publish the `-SNAPSHOT` version to Repsy                                                                    |
| `.github/workflows/prepare-release.yml`  | reusable workflow | From a `v*` tag on `develop`: open a pull request with the changelog to `develop`; once merged, open the release pull request to `main` |
| `.github/workflows/publish-release.yml`  | reusable workflow | When the release pull request is merged: publish to Maven Central and create the GitHub Release |

Every workflow accepts a `root-dir` input (default `.`). This is the directory that contains
`.sdkmanrc`, `gradle.properties` and the Gradle wrapper; all Gradle commands run as `./gradlew` from there.
Callers pass it through the `ROOT_DIR` repository variable so it can be changed without editing workflows:

```yaml
with:
  root-dir: ${{ vars.ROOT_DIR || '.' }}
```

## Repository setup

| Name             | Kind                | Needed for                     |
|------------------|---------------------|--------------------------------|
| `ROOT_DIR`       | variable (optional) | All workflows, defaults to `.` |
| `CODECOV_TOKEN`  | secret              | `coverage.yml`                 |
| `REPSY_USERNAME` | secret              | `publish-snapshot.yml`         |
| `REPSY_PASSWORD` | secret              | `publish-snapshot.yml`         |
| a dispatch token | secret              | `notify-repository`, `horizon-docs.yml` (`DOCS_DISPATCH_TOKEN`) |
| `DOCS_SOURCES_TOKEN` | secret (optional) | `astro-pages.yml` as `sources-token`: read access to private repositories |
| `MAVEN_CENTRAL_USERNAME`, `MAVEN_CENTRAL_PASSWORD` | secret | `publish-release.yml` (required): a Central Portal user token |
| `SIGNING_KEY`, `SIGNING_PASSWORD` | secret | `publish-release.yml` (required): the ASCII-armored GPG key and its passphrase |

For `astro-pages.yml`, enable GitHub Pages with source **GitHub Actions** (Settings → Pages).
`prepare-release.yml` and `publish-release.yml` use the built-in `GITHUB_TOKEN`, and `publish-release.yml` also the
Maven Central and signing secrets above (pass them with `secrets: inherit`). They need:

- a `CHANGELOG.md` in the repository root in [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format, with
  a non-empty `## [Unreleased]` section when you tag;
- **Allow GitHub Actions to create and approve pull requests** (Settings → Actions → General);
- rulesets on `develop` and `main` that require a pull request may stay as they are, without a bypass: no workflow
  pushes to `develop` or `main`. Every change reaches them through a pull request that you merge. The workflows push
  only tags and `release/*` branches, so leave `release/*` unprotected.

Pull requests opened with `GITHUB_TOKEN` (the one to `develop` and the one to `main`) start no other workflows, so
their required status checks don't run by themselves, and there is no run to re-run. To start the checks, close and
reopen the pull request yourself: the `reopened` event comes from you, so the checks run. After that, a failed check
can be re-run from the Checks tab.

The Gradle build must define a maven repository named `Repsy`, for snapshots:

```kotlin
publishing {
    repositories {
        maven {
            name = "Repsy"
            url = uri("https://repo.repsy.io/mvn/buijs-dev/maven")
            credentials {
                username = System.getenv("REPSY_USERNAME")
                password = System.getenv("REPSY_PASSWORD")
            }
        }
    }
}
```

and apply the [vanniktech maven-publish plugin](https://vanniktech.github.io/gradle-maven-publish-plugin/) for
releases, whose `publishToMavenCentral` task signs and uploads to Maven Central. Central requires a `-sources.jar`
and a `-javadoc.jar`; the plugin builds the latter with Dokka, so Dokka stays in the build. The `buijs.publishing`
plugin of [gradle-conventions](https://github.com/buijs-dev/gradle-conventions) does both.

All snapshots go to one public Repsy repository (`https://repo.repsy.io/mvn/buijs-dev/maven`,
web UI: https://repsy.io/buijs-dev/maven). Reading needs no credentials, so a repository that depends
on another SNAPSHOT adds it to `pluginManagement` and build.gradle(.kts) repositories:

```kotlin
maven("https://repo.repsy.io/mvn/buijs-dev/maven") {
    mavenContent {
        snapshotsOnly()
        includeGroupByRegex("dev\\.buijs.*")
    }
}
```

## Usage

Add the callers below to `.github/workflows/` of a repository.

### Coverage

```yaml
name: Coverage

on:
  push:
    branches: [ main, develop ]
  pull_request:
  workflow_dispatch:

jobs:
  coverage:
    uses: buijs-dev/ci-templates/.github/workflows/coverage.yml@main
    with:
      root-dir: ${{ vars.ROOT_DIR || '.' }}
    secrets: inherit
```

### Astro Pages

Builds the site in `root-dir` with `npm ci`, the optional `prebuild` command and `npm run build`, and deploys
`dist` to GitHub Pages. The Node version comes from `.nvmrc`. A site that is built from other repositories lists
them in `sources` (public repositories only, cloned shallow into the given path); when one of them needs Gradle,
`java-root` installs the JDK from its `.sdkmanrc`. Docker is available on the runner. The optional secret
`sources-token` reaches the prebuild as `STX_SOURCES_TOKEN`, for a sync that reads private repositories too.

```yaml
name: Pages

on:
  push:
    branches: [ main ]
  repository_dispatch:
    types: [ contract-updated ]
  workflow_dispatch:

permissions:
  contents: read
  packages: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

jobs:
  pages:
    uses: buijs-dev/ci-templates/.github/workflows/astro-pages.yml@main
    with:
      sources: |
        buijs-dev/stratastax-contract@main:_sources/stratastax-contract
      java-root: _sources/stratastax-contract
      prebuild: npm run sync
```

For a custom domain, set it under Settings → Pages → Custom domain and add a `CNAME` record for it that points
at `<owner>.github.io` (DNS only, not proxied, or GitHub cannot issue the certificate). With a deployment from
GitHub Actions no `CNAME` file is needed in the site.

### Horizon docs

A repository documents itself on docs.stratastax.dev with a `horizon/` directory (a `horizon.yaml` manifest, an
`index.md` and further pages; see
[Contributing documentation](https://docs.stratastax.dev/technical/contributing-docs/)). This workflow checks it
on every pull request that touches it, and after a push to the default branch sends `docs-updated` to
stratastax-docs so the site rebuilds. Register the repository once in `sources.yaml` of stratastax-docs.

```yaml
name: Horizon docs

on:
  pull_request:
    paths: [ horizon/** ]
  push:
    branches: [ main ]
    paths: [ horizon/** ]

permissions:
  contents: read

jobs:
  horizon:
    uses: buijs-dev/ci-templates/.github/workflows/horizon-docs.yml@main
    secrets:
      docs-dispatch-token: ${{ secrets.DOCS_DISPATCH_TOKEN }}
```

### Notify repository

Triggers a workflow in another repository, for example a rebuild of a documentation site when its sources
change. The target listens with `on: repository_dispatch: types: [<event-type>]`. The token is a fine-grained
personal access token (or GitHub App token) with **Contents: Read and write** on the target repository only;
the built-in `GITHUB_TOKEN` cannot dispatch to another repository. Without the secret the step only warns.

```yaml
      - name: Rebuild the docs
        uses: buijs-dev/ci-templates/.github/actions/notify-repository@main
        with:
          token: ${{ secrets.DOCS_DISPATCH_TOKEN }}
          repository: buijs-dev/stratastax-docs
          event-type: contract-updated
          client-payload: '{"sha": "${{ github.sha }}"}'
```

### Publish snapshot

```yaml
name: Publish Snapshot

on:
  push:
    branches: [ develop ]
  workflow_dispatch:

jobs:
  publish:
    uses: buijs-dev/ci-templates/.github/workflows/publish-snapshot.yml@main
    with:
      root-dir: ${{ vars.ROOT_DIR || '.' }}
    secrets: inherit
```

### Prepare and publish release

Two callers: one starts a release from a tag on `develop`, the other publishes it when the release pull request is
merged into `main`.

```yaml
name: Prepare Release

on:
  push:
    tags: [ 'v*' ]
  pull_request:
    types: [ closed ]
    branches: [ develop ]

permissions:
  contents: write
  pull-requests: write

jobs:
  prepare:
    uses: buijs-dev/ci-templates/.github/workflows/prepare-release.yml@main
    with:
      root-dir: ${{ vars.ROOT_DIR || '.' }}
```

The tag starts the job that opens the pull request from `release/<version>` to `develop`. A merged pull request into
`develop` from a `release/*` branch starts the job that opens the release pull request to `main`; any other closed
pull request runs nothing. The input `next-version` (`minor`, the default; `patch`, `major` or `none`) sets which
next `-SNAPSHOT` goes into `gradle.properties`.

```yaml
name: Publish Release

on:
  pull_request:
    types: [ closed ]
    branches: [ main ]

permissions:
  contents: write

jobs:
  publish:
    uses: buijs-dev/ci-templates/.github/workflows/publish-release.yml@main
    with:
      root-dir: ${{ vars.ROOT_DIR || '.' }}
    secrets: inherit
```

### Upgrading

- `publish-release.yml`: remove `target:` (an unknown input fails the workflow), pass `secrets: inherit`, and drop
  `packages: write` from `permissions`. It always publishes to Maven Central.
- `prepare-release.yml`: add `pull_request: types: [ closed ], branches: [ develop ]` to `on:`, and pass
  `root-dir` when `gradle.properties` is not in the repository root. Without the new trigger the release stops after
  the pull request to `develop` is merged.
- `dokka.yml` is gone: delete a caller of it. Dokka itself stays in the build, for the `-javadoc.jar`.

## Publishing

Branch strategy:

```
feature/* ──PR──▶ develop ──tag vX.Y.Z──▶ release/X.Y.Z ──PR──▶ develop ──PR──▶ main ──merge──▶ Maven Central
                     │                  (changelog, next SNAPSHOT)                              + GitHub Release
                     └─ every push: X.Y.Z-SNAPSHOT ─▶ Repsy
```

`develop` is never merged back from `main`: the changelog commit reaches `main` through `develop`, so both
branches share it.

### Snapshots

Every push to `develop` publishes the version from `gradle.properties` to Repsy.
That version must end with `-SNAPSHOT`, otherwise the workflow fails.

### Releases

1. Merge `feature/*` into `develop` through a pull request, with an entry under `## [Unreleased]` in the changelog.
2. When `develop` is ready to release, tag it and push the tag:
   ```shell
   git checkout develop
   git pull
   git tag v1.2.0
   git push origin v1.2.0
   ```
3. The prepare workflow then:
   - checks the tag: `v*`, `X.Y.Z` or `X.Y.Z-<pre-release>`, not a SNAPSHOT, on `develop`, and not released yet;
     nothing is pushed when a check fails;
   - creates the branch `release/1.2.0` from the tag;
   - on it, renames `## [Unreleased]` to `## [1.2.0] - <date>` (UTC) below a new, empty `## [Unreleased]`, and moves
     an `[Unreleased]: .../compare/v1.1.0...HEAD` link, if present, to the new tag. A missing `CHANGELOG.md`, a
     missing or empty `## [Unreleased]` section, or an existing `## [1.2.0]` section fails the workflow;
   - sets `version` in `<root-dir>/gradle.properties` to the next snapshot, `1.3.0-SNAPSHOT` (`next-version`; a
     pre-release such as `1.0.0-rc.1` is followed by `1.0.0-SNAPSHOT`);
   - commits both, pushes `release/1.2.0`, and moves the tag to that commit;
   - opens the pull request `chore: release v1.2.0` from `release/1.2.0` to `develop`.
4. Review that pull request and merge it **with a merge commit** (no squash or rebase): the tag is on its commit,
   and the release needs it on `develop`.
5. The prepare workflow then checks that the tag is on `develop`, opens the pull request `release: v1.2.0` from
   `develop` to `main` with the release notes (or updates the open one), and deletes `release/1.2.0`.
6. Review the pull request and merge it **with a merge commit** (no squash or rebase, so `main` keeps the commits of
   `develop`). Commits merged into `develop` while the pull request is open are part of the release.
7. The publish workflow then:
   - finds the latest `v*` tag on the merged `develop` commit without a GitHub Release; a merge from `develop`
     without one publishes nothing, so `develop` can also be merged into `main` without a release;
   - publishes version `1.2.0` (the tag without `v`) to Maven Central, signed, with `-Pversion=1.2.0`,
     regardless of the version in `gradle.properties`;
   - moves the tag to the merge commit on `main`, so it marks exactly the published code;
   - creates a GitHub Release with the `## [1.2.0]` section of the changelog as release notes.
8. Update your clone: `git pull && git fetch --tags --force`.

The tag moves twice (to the commit on `release/1.2.0`, then to the merge commit on `main`) and only before the release
exists. Run `git fetch --tags --force` to get its final place.

A release on Maven Central can never be removed or replaced: a failed release is always a new version.

### Consuming releases

Releases are on Maven Central; no authentication is needed. `mavenCentral()` in `pluginManagement` and
build.gradle(.kts) `repositories` is enough.

`coverage.yml`, `publish-snapshot.yml` and `astro-pages.yml` still request `packages: read` and pass `GITHUB_TOKEN`
to the build, for builds that still resolve older releases from GitHub Packages. They go once no caller needs them.

## Documentation

The Stratastax documentation is on [docs.stratastax.dev](https://docs.stratastax.dev/). Its page there is [Gradle and CI](https://docs.stratastax.dev/technical/components/gradle/).
