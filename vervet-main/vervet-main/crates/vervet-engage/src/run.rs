//! The canonical authorize → engage → audit pipeline.

use vervet_core::envelope::Envelope;
use vervet_scope::{AuditEntry, Gate, Manifest, Request};
use vervet_technique::Technique;

use crate::error::EngageError;
use crate::receipt::Receipt;

/// Authorize `request` for `technique` through `gate`, engage it, and return an
/// audited [`Receipt`]. `now` is unix seconds, injected by the caller so the
/// only wall-clock read lives at the CLI boundary.
///
/// The audit chain records two linked actions — the authorization and the
/// engagement — so the receipt carries its own provenance.
pub fn run(
    gate: &Gate,
    manifest: &Manifest,
    technique: &dyn Technique,
    request: Request,
    now: u64,
) -> Result<Receipt, EngageError> {
    let id = technique.meta().id;
    let grant = gate
        .authorize(manifest, id, request, now)
        .map_err(EngageError::Denied)?;
    let engagement = grant.engagement_id().to_string();
    let target = grant.request().target;

    let (authorized, authorized_handle) = AuditEntry::append(
        0,
        &engagement,
        &format!("authorize {id} target={target}"),
        AuditEntry::GENESIS,
    );
    let evidence = technique.engage(&grant);
    let (engaged, _) = AuditEntry::append(
        1,
        &engagement,
        &format!("engage {id} observations={}", evidence.observations.len()),
        authorized_handle.as_str(),
    );

    let envelope = Envelope::from_evidence(&evidence)?;
    Ok(Receipt {
        envelope,
        audit: vec![authorized, engaged],
    })
}
