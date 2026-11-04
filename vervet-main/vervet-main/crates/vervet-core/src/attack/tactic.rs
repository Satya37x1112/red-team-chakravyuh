//! The ATT&CK tactic a technique advances.

use serde::Serialize;

/// The adversary goal a technique serves, mirroring ATT&CK tactic columns.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Tactic {
    /// Gaining a first foothold on the target.
    InitialAccess,
    /// Mapping the environment — hosts, services, accounts.
    Discovery,
    /// Obtaining or validating account credentials.
    CredentialAccess,
    /// Pivoting from one host to another with held access.
    LateralMovement,
}

impl Tactic {
    /// The snake_case identifier, matching the serialized form.
    pub const fn as_str(&self) -> &'static str {
        match self {
            Tactic::InitialAccess => "initial_access",
            Tactic::Discovery => "discovery",
            Tactic::CredentialAccess => "credential_access",
            Tactic::LateralMovement => "lateral_movement",
        }
    }
}
