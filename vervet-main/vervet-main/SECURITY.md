# Security Policy

## Authorized use

vervet is an adversary-emulation instrument. Run it **only** against systems you
are explicitly authorized to test. Every state-changing technique requires an
Ed25519-signed scope manifest; acting outside that scope is a hard, typed
refusal by design. You are responsible for holding valid authorization for any
engagement.

## Reporting a vulnerability

If you find a security issue in vervet itself — for example, a way to mint a
`Grant` outside the authorization gate, forge or replay a scope manifest, bypass
the CIDR/technique/time checks, or leak credential material into evidence —
please report it **privately**. Do not open a public issue.

Email **don@codetestcode.io** with:

- a description of the issue and its impact,
- steps or a proof of concept to reproduce it,
- the commit or version affected.

We aim to acknowledge reports within a few days and will coordinate a fix and
disclosure timeline with you.

## Scope

In scope: the authorization spine (`vervet-scope`), the evidence/audit chain
(`vervet-core`, `vervet-engage`), and anything that could cause a technique to
act without a valid `Grant` or to write secrets into a receipt.

Out of scope: misuse of the tool against unauthorized targets (that is on the
operator, not a vulnerability in vervet), and findings that require an attacker
to already hold the signing key.

## Supported versions

vervet is pre-1.0; security fixes land on `main` and the latest release.
