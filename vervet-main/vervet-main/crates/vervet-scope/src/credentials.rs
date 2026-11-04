//! Operator-supplied credential material for credential-access techniques.

/// One username/password pair, for per-account validation (T1078).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Credential {
    /// The account name to authenticate as.
    pub username: String,
    /// The secret asserted for that account; never written to evidence.
    pub password: String,
}

/// Credential material. Carries both shapes a technique might need: a spray set
/// (one password across many usernames) and explicit per-account `pairs`. A
/// technique reads whichever it requires; passwords are never written to
/// evidence — techniques redact them.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Credentials {
    /// The usernames to spray a single password across.
    pub usernames: Vec<String>,
    /// The one password tried against every spray username.
    pub password: String,
    /// Explicit username/password pairs for per-account validation.
    pub pairs: Vec<Credential>,
}
