# Dependency Policy

1. **Prefer the standard library** before adding a new dependency.
2. **Pin exact or compatible-release versions** in each module's manifest; never depend on a floating `latest`.
3. **One dependency, one purpose.** Don't add a second library that overlaps an existing one's functionality without removing the old one.
4. **License check.** New dependencies must use a license compatible with this
   repository's AGPL-3.0 terms (GPL-compatible, MIT, Apache-2.0, and BSD are
   generally acceptable; proprietary or source-available-only terms require
   an explicit licensing decision).
5. **Security.** Dependabot and the repository security workflow run Python
   dependency audits; high-severity findings block release and should block
   merge unless a documented exception exists.
6. **Major version bumps** get a dedicated PR with a changelog entry, reviewed separately from feature work.
