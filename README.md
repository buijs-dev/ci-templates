# CI Templates
[![](https://img.shields.io/badge/Buijs-Software-blue)](https://buijs.dev/)
[![GitHub](https://img.shields.io/github/license/buijs-dev/ci-templates?color=black)](https://github.com/buijs-dev/ci-templates/blob/main/LICENSE)

Shared GitHub Actions.

## Contents

| Path                                     | Type              | Purpose                                                                                                   |
|------------------------------------------|-------------------|-----------------------------------------------------------------------------------------------------------|
| `.github/actions/setup-java`             | composite action  | Installs the JDK from `<root-dir>/.sdkmanrc` (temurin) and sets up Gradle                                 |
| `.github/actions/release-changelog`      | composite action  | Moves `## [Unreleased]` of the changelog to `## [X.Y.Z] - <date>` and extracts the release notes          |
| `.github/workflows/coverage.yml`         | reusable workflow | `./gradlew check koverXmlReport` and upload to Codecov                                                    |
| `.github/workflows/dokka.yml`            | reusable workflow | `./gradlew dokkaGenerate` and deploy to GitHub Pages                                                      |
| `.github/workflows/publish-snapshot.yml` | reusable workflow | Publish the `-SNAPSHOT` version to Repsy                                                                  |
| `.github/workflows/publish-release.yml`  | reusable workflow | Publish a tagged release to GitHub Packages, create a GitHub Release and open the changelog pull request  |

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

For `dokka.yml`, enable GitHub Pages with source **GitHub Actions** (Settings → Pages).
`publish-release.yml` only uses the built-in `GITHUB_TOKEN`. It needs a `CHANGELOG.md` in the repository root
in [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format with a non-empty `## [Unreleased]` section,
and **Allow GitHub Actions to create and approve pull requests** enabled (Settings → Actions → General). The Gradle build must define 
two maven repositories named `Repsy` and `GitHubPackages`:

```kotlin
publishing {
    repositories {
        maven {
            name = "GitHubPackages"
            url = uri("https://maven.pkg.github.com/buijs-dev/<repository>")
            credentials {
                username = System.getenv("GITHUB_ACTOR")
                password = System.getenv("GITHUB_TOKEN")
            }
        }
        
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

### Dokka

A reusable workflow cannot grant itself more permissions than the caller has, so the caller declares them.

```yaml
name: Dokka

on:
  push:
    branches: [ main ]
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
  dokka:
    uses: buijs-dev/ci-templates/.github/workflows/dokka.yml@main
    with:
      root-dir: ${{ vars.ROOT_DIR || '.' }}
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

### Publish release

```yaml
name: Publish Release

on:
  push:
    tags: [ 'v*' ]

permissions:
  contents: write
  packages: write
  pull-requests: write

jobs:
  publish:
    uses: buijs-dev/ci-templates/.github/workflows/publish-release.yml@main
    with:
      root-dir: ${{ vars.ROOT_DIR || '.' }}
```

## Publishing

Branch strategy:

```
feature/* ──PR──▶ develop ──PR──▶ main ──tag vX.Y.Z──▶ GitHub Packages
                     │
                     └─ every push: X.Y.Z-SNAPSHOT ─▶ Repsy
```

### Snapshots

Every push to `develop` publishes the version from `gradle.properties` to Repsy.
That version must end with `-SNAPSHOT`, otherwise the workflow fails.

### Releases

1. Merge `feature/*` into `develop` through a pull request.
2. When `develop` is ready to release, merge it into `main` through a pull request.
3. Tag the merge commit on `main` and push the tag:
   ```shell
   git checkout main
   git pull
   git tag v1.2.0
   git push origin v1.2.0
   ```
4. The release workflow then:
   - checks that the tagged commit is on `main` (a tag anywhere else fails the build);
   - checks the changelog: a missing `CHANGELOG.md`, a missing or empty `## [Unreleased]` section, or an existing
     `## [1.2.0]` section fails the build before anything is published;
   - publishes version `1.2.0` (the tag without `v`) to GitHub Packages with `-Pversion=1.2.0`,
     regardless of the version in `gradle.properties`;
   - creates a GitHub Release with the `## [Unreleased]` section as release notes;
   - renames `## [Unreleased]` to `## [1.2.0] - <date>` (UTC) below a new, empty `## [Unreleased]`, and moves an
     `[Unreleased]: .../compare/v1.1.0...HEAD` link, if present, to the new tag;
   - pushes that change to `chore/changelog-v1.2.0` and opens a pull request to `main`.
5. Merge the changelog pull request with a merge commit (no squash or rebase). Pull requests opened with
   `GITHUB_TOKEN` don't trigger other workflows, so required status checks on `main` won't run for it.
6. Merge `main` back into `develop` right away, so both branches share the changelog commit:
   ```shell
   git checkout develop
   git pull
   git merge origin/main
   git push
   ```
   This only conflicts when `develop` got new `## [Unreleased]` entries in the meantime; keep both.
7. Bump `version` in `gradle.properties` on `develop` to the next snapshot, e.g. `1.3.0-SNAPSHOT`.

A published version cannot be overwritten in GitHub Packages. To redo a failed release, fix the problem
and release a new version, or delete the package version in GitHub before re-running the workflow.

### Consuming releases

Reading from GitHub Packages requires authentication, also for public packages. 
Add this repository to `pluginManagement` and build.gradle(.kts) `repositories`:

```kotlin
maven("https://maven.pkg.github.com/buijs-dev/*") {
    credentials {
        username = providers.gradleProperty("gpr.user").orElse(providers.environmentVariable("GITHUB_ACTOR")).orNull
        password = providers.gradleProperty("gpr.key").orElse(providers.environmentVariable("GITHUB_TOKEN")).orNull
    }
    mavenContent {
        releasesOnly()
        includeGroupByRegex("dev\\.buijs.*")
    }
}
```

- **CI**: the templates pass `GITHUB_TOKEN` to Gradle and request `packages: read`; `GITHUB_ACTOR` is set by the
  runner. A caller that declares its own `permissions` (like Dokka) must include `packages: read`.
- **Locally**: create a classic personal access token with the `read:packages` scope and add it to
  `~/.gradle/gradle.properties` (never to the repository):
  ```properties
  gpr.user=<github username>
  gpr.key=<token>
  ```
