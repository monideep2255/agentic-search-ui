---
name: npm-security-check
description: Before installing or recommending any npm package, run checks to catch supply chain attacks, malicious versions, and postinstall script exploits.
scope: portable
---

## npm security check

Before installing any npm package or recommending one to the user, run these checks in order. `npm audit` alone is not enough. It only catches CVEs — supply chain attacks like the axios compromise (March 2026) had no CVE when the malicious version was live.

### 1. Check for recent compromise reports

Before recommending a package, search for: `[package-name] npm malware` or `[package-name] npm compromised`. The axios attack (March 31, 2026) showed that even the most downloaded JavaScript library can be hijacked briefly. Brief is enough.

### 2. Verify the exact version before install

```bash
npm view <package> time --json         # check published timestamps for each version
npm view <package>@<version> dist-tags # check dist-tag assignments
```

Suspicious signal: a version published at an unusual hour, with an unexpected version jump, or with a new transitive dependency that wasn't in the prior version.

### 3. Inspect postinstall scripts before install

```bash
npm pack <package>@<version> --dry-run  # see what ships in the tarball
cat node_modules/<package>/package.json | jq '.scripts'
```

Red flag: a postinstall or install script in a package that has no legitimate reason to run code at install time (e.g., a utility library, an HTTP client). Also check transitive dependencies added in the same version bump.

### 4. Run audit after install

```bash
npm audit
npm audit --audit-level=high
```

This catches known CVEs. It does not catch zero-day supply chain attacks. Treat a clean audit as necessary but not sufficient.

### 5. Verify with Socket.dev (for high-trust packages)

socket.dev/npm/[package-name] does supply chain analysis beyond CVE databases. Useful before adding a new package to a production app.

### Reference case: axios March 2026

Malicious versions: axios@1.14.1 and axios@0.30.4
Live window: March 31, 2026, 00:21 to 03:15 UTC (about 2 hours)
Vector: injected fake dependency plain-crypto-js@4.2.1 with a RAT-dropping postinstall script targeting macOS, Windows, and Linux. Malware then self-deleted to evade forensic detection.
Attribution: Sapphire Sleet, a North Korean state actor (also tracked as UNC1069 by Google)
Safe versions: 1.14.0 and 0.30.3

If axios was installed during that window: rotate all secrets and credentials immediately.

### Apply when

- User runs or plans to run `npm install`
- User asks for package recommendations
- User upgrades a package to a new minor or major version
- Reviewing a `package.json` diff that adds new dependencies
- User shares a lockfile showing new packages

### Do NOT apply when

- pip, cargo, gem, go get (separate package managers, separate security tooling)
- This repo: personal-os-work has no npm dependencies whatsoever
