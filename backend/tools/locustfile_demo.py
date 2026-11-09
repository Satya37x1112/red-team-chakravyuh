"""Operator-authored locustfile for the CHAKRAVYUH DDoS demo.

Drives a simple GET "/" against the --host passed by the Locust adapter
(LOCUST_TARGET_URL). Loopback demo target only. No data is modified; this is a
read-only HTTP load generator used to measure the local demo app under load.
"""
from locust import HttpUser, task, between


class DemoUser(HttpUser):
    # Gradual, realistic pacing between requests per virtual user.
    wait_time = between(0.1, 0.5)

    @task
    def index(self):
        # GET the root page; counts non-2xx as failures in the stats.
        self.client.get("/", name="GET /")
