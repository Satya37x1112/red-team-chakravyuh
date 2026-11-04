//! End-to-end test harness for vervet.
//!
//! This crate carries no library logic — it is a leaf that exists only to host
//! Docker-backed integration tests under `tests/`. Those tests drive the real
//! `authorize → engage → emit` pipeline against live containerized services
//! (e.g. a real `sshd`) and assert on the resulting receipts.
//!
//! The tests are gated behind the `ssh-auth` feature, so the default build and
//! `cargo test --workspace` need no Docker. Run them with:
//!
//! ```sh
//! cargo test -p vervet-e2e --features ssh-auth   # needs Docker
//! ```
