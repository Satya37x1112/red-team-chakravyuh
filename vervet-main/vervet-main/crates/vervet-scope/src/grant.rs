//! The unforgeable capability token minted by the gate.

use std::net::Ipv4Addr;

use vervet_core::attack::TechniqueId;

use crate::credentials::Credentials;

/// What an operator asked to do — untrusted until it passes the [`crate::Gate`].
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Request {
    /// The target host.
    pub target: Ipv4Addr,
    /// TCP ports of interest; empty means "use the technique default".
    pub ports: Vec<u16>,
    /// Credential material, for credential-access techniques only.
    pub credentials: Option<Credentials>,
}

impl Request {
    /// A request with no credentials — the common case for discovery.
    pub fn new(target: Ipv4Addr, ports: Vec<u16>) -> Self {
        Self {
            target,
            ports,
            credentials: None,
        }
    }

    /// Attach credential material for a credential-access technique.
    pub fn with_credentials(mut self, credentials: Credentials) -> Self {
        self.credentials = Some(credentials);
        self
    }
}

/// Proof that a [`Request`] passed the authorization gate for one technique.
///
/// `Grant` has no public constructor: it is minted only inside this crate by
/// [`crate::Gate::authorize`]. A technique receives `&Grant` and therefore
/// cannot fabricate authorization it was not given.
#[derive(Debug, PartialEq, Eq)]
pub struct Grant {
    request: Request,
    engagement_id: String,
    technique: TechniqueId,
    _seal: (),
}

impl Grant {
    pub(crate) fn new(request: Request, engagement_id: String, technique: TechniqueId) -> Self {
        Grant {
            request,
            engagement_id,
            technique,
            _seal: (),
        }
    }

    /// The authorized request.
    pub fn request(&self) -> &Request {
        &self.request
    }

    /// The engagement this grant belongs to.
    pub fn engagement_id(&self) -> &str {
        &self.engagement_id
    }

    /// The technique this grant authorizes.
    pub fn technique(&self) -> TechniqueId {
        self.technique
    }
}
