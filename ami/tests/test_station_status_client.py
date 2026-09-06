"""
A worked example of a connected device reporting its status to Antenna.

Read this file as the client documentation for ``POST /api/v2/deployments/{id}/status/``.
Everything runs against a real HTTP server, so the requests below are exactly what a
device on the network sends: no test client shortcuts, no serializer internals.

The client is the two functions at the top, ``get_auth_token`` and ``report_status``.
They are about twenty lines together and a device needs nothing else. The tests then
show the four situations a device implementer has to get right:

1. A device with sensors reports readings through the night, and they come back in order.
2. A device with different sensors — or none — reports what it can, and is asked for
   nothing it cannot measure.
3. A report that does not say which unit sent it is refused.
4. A device that was offline uploads its backlog late without clobbering what is current.

Most stations never do any of this. They are configured in Antenna and synced on demand
from an SD card or object storage, and nothing here applies to them.
"""

import datetime

import requests
from rest_framework.test import APILiveServerTestCase

from ami.main.models import Deployment, Project
from ami.users.models import User
from ami.users.roles import ProjectManager, create_roles_for_project

TIMEOUT_SECONDS = 30


def get_auth_token(base_url: str, email: str, password: str) -> str:
    """
    Exchange an account's credentials for a token, once, at first run.

    Store the token on the device and reuse it. A device should not hold a password
    any longer than this call takes.
    """
    response = requests.post(
        f"{base_url}/api/v2/auth/token/login/",
        json={"email": email, "password": password},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    return response.json()["auth_token"]


def report_status(
    base_url: str,
    token: str,
    deployment_id: int,
    status: dict,
    recorded_at: datetime.datetime | None = None,
) -> dict:
    """
    Send one status report for a station.

    ``status`` must carry ``device_id`` and ``software_version``; everything else in it
    is whatever this device can measure, and is stored exactly as sent. Pass
    ``recorded_at`` when the device knows when the reading was taken — which is not the
    same as when it manages to send it. Omit it and the server timestamps the report on
    arrival.

    A device offline in the field should queue reports and send them when it next has a
    network, rather than dropping them: a late report is expected and is kept as
    history. About one report a minute is a sensible ceiling, plus one immediately
    whenever something changes.
    """
    body: dict = {"status": status}
    if recorded_at is not None:
        body["recorded_at"] = recorded_at.isoformat()

    response = requests.post(
        f"{base_url}/api/v2/deployments/{deployment_id}/status/",
        json=body,
        headers={"Authorization": f"Token {token}"},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    return response.json()


class TestStationStatusClient(APILiveServerTestCase):
    """The example above, exercised over HTTP against a running server."""

    def setUp(self):
        super().setUp()
        self.project = Project.objects.create(name="Status Client Example")
        create_roles_for_project(self.project)

        self.password = "example-password"
        self.operator = User.objects.create_user(
            email="status-client@insectai.org",
            password=self.password,
        )
        ProjectManager.assign_user(self.operator, self.project)

        self.deployment = Deployment.objects.create(name="Shed station", project=self.project)
        self.token = get_auth_token(self.live_server_url, self.operator.email, self.password)

    def _history(self) -> list[dict]:
        """Read a station's reports back, newest first — what an operator's tools see."""
        response = requests.get(
            f"{self.live_server_url}/api/v2/deployments/{self.deployment.pk}/status/",
            headers={"Authorization": f"Token {self.token}"},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        return response.json()["results"]

    def test_a_device_reports_through_the_night(self):
        """
        A phone reports every so often while it is capturing. Each report carries the
        two identity fields and whatever this device happens to know about itself.
        """
        night = datetime.datetime(2026, 9, 5, 21, 0)

        for minutes, captures, battery in [(0, 0, 96.0), (60, 58, 88.5), (120, 121, 81.0)]:
            report_status(
                self.live_server_url,
                self.token,
                self.deployment.pk,
                recorded_at=night + datetime.timedelta(minutes=minutes),
                status={
                    "device_id": "AW-0001",
                    "software_version": "1.4.0",
                    "status": "surveying",
                    "session_id": "20260905T210000-7C2A",
                    "captures_count": captures,
                    "battery_percent": battery,
                    "battery_state": "discharging",
                    "storage_free_bytes": 42_000_000_000,
                    "survey_config": {
                        "interval_seconds": 60,
                        "schedule": {"mode": "sun", "start_offset_minutes": -30},
                    },
                },
            )

        history = self._history()

        self.assertEqual([entry["status"]["captures_count"] for entry in history], [121, 58, 0])
        self.assertEqual(history[0]["status"]["survey_config"]["schedule"]["mode"], "sun")

        self.deployment.refresh_from_db()
        self.assertEqual(self.deployment.last_status_at, night + datetime.timedelta(minutes=120))

    def test_a_device_reports_only_what_it_can_measure(self):
        """
        A mains-powered trap has no fuel gauge and no session to talk about. It reports
        the two identity fields and the things it does know, and is asked for nothing
        else. A device that can say nothing at all still proves it is alive by checking
        in with identity alone.
        """
        trap = Deployment.objects.create(name="Mains trap", project=self.project)
        silent_box = Deployment.objects.create(name="Sensorless box", project=self.project)

        report_status(
            self.live_server_url,
            self.token,
            trap.pk,
            status={
                "device_id": "TRAP-77",
                "software_version": "0.9.1",
                "power_source": "mains",
                "lamp_hours": 3.25,
                "sd_card_present": True,
            },
        )
        report_status(
            self.live_server_url,
            self.token,
            silent_box.pk,
            status={"device_id": "BOX-12", "software_version": "0.1.0"},
        )

        trap.refresh_from_db()
        silent_box.refresh_from_db()

        assert trap.last_status is not None
        assert silent_box.last_status is not None
        self.assertEqual(
            trap.last_status.reported(),
            {"power_source": "mains", "lamp_hours": 3.25, "sd_card_present": True},
        )
        self.assertEqual(silent_box.last_status.reported(), {})
        self.assertIsNotNone(silent_box.last_status_at)

    def test_a_report_must_say_which_unit_sent_it(self):
        """
        The one way to get a report rejected. A station's configured device says what
        kind of hardware it is; only the device itself can say which unit is on site and
        what version it is running, so both are required.
        """
        response = requests.post(
            f"{self.live_server_url}/api/v2/deployments/{self.deployment.pk}/status/",
            json={"status": {"battery_percent": 80}},
            headers={"Authorization": f"Token {self.token}"},
            timeout=TIMEOUT_SECONDS,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._history(), [])

    def test_a_backlog_sent_late_does_not_overwrite_what_is_current(self):
        """
        A device offline all night sends its queue the next morning, oldest first. The
        station's latest stays the most recently *recorded* reading, so an operator does
        not see a station go backwards while it catches up.
        """
        current = datetime.datetime(2026, 9, 6, 6, 0)
        report_status(
            self.live_server_url,
            self.token,
            self.deployment.pk,
            recorded_at=current,
            status={"device_id": "AW-0001", "software_version": "1.4.0", "status": "idle"},
        )

        for hour in (1, 2, 3):
            report_status(
                self.live_server_url,
                self.token,
                self.deployment.pk,
                recorded_at=datetime.datetime(2026, 9, 6, hour, 0),
                status={"device_id": "AW-0001", "software_version": "1.4.0", "status": "surveying"},
            )

        self.deployment.refresh_from_db()
        assert self.deployment.last_status is not None
        self.assertEqual(self.deployment.last_status_at, current)
        self.assertEqual(self.deployment.last_status.reported()["status"], "idle")
        self.assertEqual(len(self._history()), 4)

    def test_an_operator_sees_when_each_station_was_last_heard_from(self):
        """
        What the station list shows. A station that reports carries a last-seen time; a
        station synced from an SD card carries none, and that blank is the answer rather
        than a gap.
        """
        offline_station = Deployment.objects.create(name="SD card station", project=self.project)
        report_status(
            self.live_server_url,
            self.token,
            self.deployment.pk,
            status={"device_id": "AW-0001", "software_version": "1.4.0"},
        )

        response = requests.get(
            f"{self.live_server_url}/api/v2/deployments/?project_id={self.project.pk}",
            headers={"Authorization": f"Token {self.token}"},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        stations = {station["id"]: station for station in response.json()["results"]}

        self.assertIsNotNone(stations[self.deployment.pk]["last_status_at"])
        self.assertEqual(stations[self.deployment.pk]["last_status"]["device_id"], "AW-0001")
        self.assertIsNone(stations[offline_station.pk]["last_status_at"])
        self.assertIsNone(stations[offline_station.pk]["last_status"])
