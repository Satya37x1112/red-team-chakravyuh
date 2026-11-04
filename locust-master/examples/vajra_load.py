"""VAJRAPRAHAAR lab load profile — continuous GETs to stress an authorized target.

This is the operator-authored locustfile the DDoS module drives. Unlike the
stock `basic.py` (which used `wait_time = between(2, 5)` and therefore barely
touched the target), each simulated user here issues requests back-to-back, so
the configured -u / -r / -t actually translate into real load.

Authorized, isolated-lab targets only. The number of users, spawn rate, and run
duration are still hard-capped server-side by the Locust integration.
"""
from locust import HttpUser, task, constant


class LoadUser(HttpUser):
    # Zero think-time: generate as much load as the user count allows. The
    # server-side caps (max users / spawn rate / run seconds) bound the total.
    wait_time = constant(0)

    @task(5)
    def root(self):
        # Primary hit — the target's root. `catch_response` isn't needed; any
        # status still counts as a completed request for load purposes.
        self.client.get("/", name="GET /")

    @task(1)
    def health(self):
        # A second path so the load isn't a single cached route. 404 is fine —
        # it still exercises the server.
        self.client.get("/api/health", name="GET /api/health")
