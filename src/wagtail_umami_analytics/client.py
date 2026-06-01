from dataclasses import dataclass
from enum import StrEnum
from typing import Self

import requests


class UmamiClientError(Exception):
    pass


class UmamiAPIError(UmamiClientError):
    def __init__(self, status_code: int, response_text: str):
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(f"Umami API error ({status_code}): {response_text}")


class UmamiConfigurationError(UmamiClientError):
    pass


class MetricType(StrEnum):
    PATH = "path"
    ENTRY = "entry"
    EXIT = "exit"
    TITLE = "title"
    QUERY = "query"
    REFERRER = "referrer"
    CHANNEL = "channel"
    DOMAIN = "domain"
    COUNTRY = "country"
    REGION = "region"
    CITY = "city"
    BROWSER = "browser"
    OS = "os"
    DEVICE = "device"
    LANGUAGE = "language"
    SCREEN = "screen"
    EVENT = "event"
    HOSTNAME = "hostname"
    TAG = "tag"
    DISTINCT_ID = "distinctId"


@dataclass(frozen=True, slots=True)
class Metric:
    x: str
    y: int

    @classmethod
    def from_json(cls, value: object) -> Self:
        match value:
            case {"x": str(x), "y": y} if type(y) is int:
                return cls(x=x, y=y)
        raise UmamiClientError(
            "Umami API returned invalid metric response: expected x str and y int"
        )

    def to_dict(self) -> dict[str, str | int]:
        return {"x": self.x, "y": self.y}


@dataclass(frozen=True, slots=True)
class StatsComparison:
    pageviews: int
    visitors: int
    visits: int
    bounces: int
    totaltime: int

    @classmethod
    def from_json(cls, value: object) -> Self:
        match value:
            case {
                "pageviews": pageviews,
                "visitors": visitors,
                "visits": visits,
                "bounces": bounces,
                "totaltime": totaltime,
            } if all(
                type(metric) is int
                for metric in (pageviews, visitors, visits, bounces, totaltime)
            ):
                return cls(
                    pageviews=pageviews,
                    visitors=visitors,
                    visits=visits,
                    bounces=bounces,
                    totaltime=totaltime,
                )
        raise UmamiClientError(
            "Umami API returned invalid stats comparison response: "
            "expected pageviews, visitors, visits, bounces, and totaltime ints"
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "pageviews": self.pageviews,
            "visitors": self.visitors,
            "visits": self.visits,
            "bounces": self.bounces,
            "totaltime": self.totaltime,
        }


@dataclass(frozen=True, slots=True)
class Stats:
    pageviews: int
    visitors: int
    visits: int
    bounces: int
    totaltime: int
    comparison: StatsComparison

    @classmethod
    def from_json(cls, value: object) -> Self:
        match value:
            case {
                "pageviews": pageviews,
                "visitors": visitors,
                "visits": visits,
                "bounces": bounces,
                "totaltime": totaltime,
                "comparison": comparison,
            } if all(
                type(metric) is int
                for metric in (pageviews, visitors, visits, bounces, totaltime)
            ):
                return cls(
                    pageviews=pageviews,
                    visitors=visitors,
                    visits=visits,
                    bounces=bounces,
                    totaltime=totaltime,
                    comparison=StatsComparison.from_json(comparison),
                )
        raise UmamiClientError(
            "Umami API returned invalid stats response: "
            "expected pageviews, visitors, visits, bounces, totaltime ints, "
            "and comparison object"
        )

    def to_dict(self) -> dict[str, int | dict[str, int]]:
        return {
            "pageviews": self.pageviews,
            "visitors": self.visitors,
            "visits": self.visits,
            "bounces": self.bounces,
            "totaltime": self.totaltime,
            "comparison": self.comparison.to_dict(),
        }


class UmamiClient:
    def __init__(
        self,
        base_url: str,
        website_id: str | None = None,
        timeout: int = 10,
    ):
        self.base_url = base_url.strip("/")
        self.website_id = website_id
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["Accept"] = "application/json"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.session.close()

    def _get(self, endpoint: str, **kwargs) -> requests.Response:
        try:
            return self.session.get(
                f"{self.base_url}{endpoint}",
                timeout=self.timeout,
                **kwargs,
            )
        except requests.RequestException as e:
            raise UmamiClientError(f"Umami request failed for {endpoint}") from e

    def _post(self, endpoint: str, **kwargs) -> requests.Response:
        try:
            return self.session.post(
                f"{self.base_url}{endpoint}",
                timeout=self.timeout,
                **kwargs,
            )
        except requests.RequestException as e:
            raise UmamiClientError(f"Umami request failed for {endpoint}") from e

    def _handle_response(self, response: requests.Response):
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            status_code = (
                response.status_code if e.response is None else e.response.status_code
            )
            response_text = response.text if e.response is None else e.response.text
            raise UmamiAPIError(status_code, response_text) from e
        try:
            return response.json()
        except ValueError as e:
            raise UmamiClientError("Umami API returned invalid JSON") from e

    def set_api_key(self, api_key: str):
        self.session.headers["x-umami-api-key"] = api_key

    def login(self, username: str, password: str):
        body = {
            "username": username,
            "password": password,
        }
        response = self._post("/auth/login", json=body)
        json_response = self._handle_response(response)
        if "token" not in json_response or not isinstance(json_response["token"], str):
            raise UmamiClientError(
                "Umami API returned invalid login token, expected token str"
            )
        self.session.headers["Authorization"] = "Bearer " + json_response["token"]
        return json_response["token"]

    def active_users(self, website_id: str | None = None) -> int:
        response = self._get(
            f"/websites/{self._website_id(website_id)}/active",
        )
        json_response = self._handle_response(response)
        match json_response:
            case {"visitors": visitors} if type(visitors) is int:
                return visitors
        raise UmamiClientError(
            "Umami API returned invalid active users response: expected visitors int"
        )

    def _website_id(self, website_id: str | None) -> str:
        selected_website_id = website_id or self.website_id
        if not selected_website_id:
            raise UmamiConfigurationError("Umami website_id is required")
        return selected_website_id

    def metrics(
        self,
        startAt: int,
        endAt: int,
        metric_type: MetricType,
        limit: int | None = None,
        offset: int | None = None,
        website_id: str | None = None,
    ) -> list[Metric]:
        params = {
            "startAt": startAt,
            "endAt": endAt,
            "type": metric_type.value,
        }
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        response = self._get(
            f"/websites/{self._website_id(website_id)}/metrics",
            params=params,
        )
        json_response = self._handle_response(response)
        if not isinstance(json_response, list):
            raise UmamiClientError("Umami API returned invalid metrics response")
        return [Metric.from_json(metric) for metric in json_response]

    def stats(self, startAt: int, endAt: int, website_id: str | None = None) -> Stats:
        response = self._get(
            f"/websites/{self._website_id(website_id)}/stats",
            params={
                "startAt": startAt,
                "endAt": endAt,
            },
        )
        return Stats.from_json(self._handle_response(response))
