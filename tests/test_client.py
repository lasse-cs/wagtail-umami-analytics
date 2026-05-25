import responses
import pytest

from wagtail_umami_analytics.client import Metric, MetricType, UmamiClient
from wagtail_umami_analytics.client import UmamiClientError
from wagtail_umami_analytics.client import UmamiConfigurationError


@responses.activate
def test_active_users(umami_client, umami_api_base, website_id):
    responses.get(f"{umami_api_base}websites/{website_id}/active", json={"visitors": 5})
    assert umami_client.active_users() == 5


@responses.activate
def test_active_users_handles_errors(umami_client, umami_api_base, website_id):
    responses.get(f"{umami_api_base}websites/{website_id}/active", json={}, status=401)
    with pytest.raises(UmamiClientError):
        umami_client.active_users()


@responses.activate
def test_active_users_other_website_id(umami_client, umami_api_base):
    responses.get(
        f"{umami_api_base}websites/other_website_id/active", json={"visitors": 5}
    )
    assert umami_client.active_users(website_id="other_website_id") == 5


@responses.activate
def test_stats(umami_client, umami_api_base, website_id):
    startAt = 200
    endAt = 300
    expected_response = {
        "pageviews": 10,
        "visitors": 10,
        "visits": 10,
        "bounces": 10,
        "totaltime": 10,
        "comparison": {
            "pageviews": 0,
            "visitors": 0,
            "visits": 0,
            "bounces": 0,
            "totaltime": 0,
        },
    }
    responses.get(
        f"{umami_api_base}websites/{website_id}/stats",
        json=expected_response,
        match=[
            responses.matchers.query_param_matcher(
                {"startAt": str(startAt), "endAt": str(endAt)}
            )
        ],
    )
    stats = umami_client.stats(startAt, endAt)
    assert stats.to_dict() == expected_response


@responses.activate
def test_stats_handles_errors(umami_client, umami_api_base, website_id):
    startAt = 200
    endAt = 300
    responses.get(
        f"{umami_api_base}websites/{website_id}/stats",
        json={},
        status=500,
        match=[
            responses.matchers.query_param_matcher(
                {"startAt": str(startAt), "endAt": str(endAt)}
            )
        ],
    )
    with pytest.raises(UmamiClientError):
        umami_client.stats(startAt, endAt)


@responses.activate
def test_metrics(umami_client, umami_api_base, website_id):
    startAt = 200
    endAt = 300
    metric_type = MetricType.PATH
    responses.get(
        f"{umami_api_base}websites/{website_id}/metrics",
        json=[{"x": "abc", "y": 10}],
        match=[
            responses.matchers.query_param_matcher(
                {
                    "startAt": str(startAt),
                    "endAt": str(endAt),
                    "type": str(metric_type),
                }
            )
        ],
    )
    assert umami_client.metrics(startAt, endAt, metric_type) == [Metric(x="abc", y=10)]


@responses.activate
def test_metrics_handles_errors(umami_client, umami_api_base, website_id):
    startAt = 200
    endAt = 300
    metric_type = MetricType.PATH
    responses.get(
        f"{umami_api_base}websites/{website_id}/metrics",
        json={},
        status=500,
        match=[
            responses.matchers.query_param_matcher(
                {
                    "startAt": str(startAt),
                    "endAt": str(endAt),
                    "type": str(metric_type),
                }
            )
        ],
    )
    with pytest.raises(UmamiClientError):
        umami_client.metrics(startAt, endAt, metric_type)


def test_active_users_requires_website_id(umami_api_base, umami_api_key):
    with UmamiClient(umami_api_base, umami_api_key) as client:
        with pytest.raises(UmamiConfigurationError):
            client.active_users()


@responses.activate
def test_stats_handles_invalid_json(umami_client, umami_api_base, website_id):
    startAt = 200
    endAt = 300
    responses.get(
        f"{umami_api_base}websites/{website_id}/stats",
        body="not json",
        status=200,
        content_type="application/json",
        match=[
            responses.matchers.query_param_matcher(
                {"startAt": str(startAt), "endAt": str(endAt)}
            )
        ],
    )
    with pytest.raises(UmamiClientError):
        umami_client.stats(startAt, endAt)


@responses.activate
def test_active_users_handles_invalid_response_shape(
    umami_client, umami_api_base, website_id
):
    responses.get(
        f"{umami_api_base}websites/{website_id}/active", json={"visitors": "5"}
    )
    with pytest.raises(UmamiClientError, match="expected visitors int"):
        umami_client.active_users()


@responses.activate
def test_stats_handles_invalid_response_shape(umami_client, umami_api_base, website_id):
    startAt = 200
    endAt = 300
    responses.get(
        f"{umami_api_base}websites/{website_id}/stats",
        json={"pageviews": 10},
        match=[
            responses.matchers.query_param_matcher(
                {"startAt": str(startAt), "endAt": str(endAt)}
            )
        ],
    )
    with pytest.raises(UmamiClientError, match="invalid stats response"):
        umami_client.stats(startAt, endAt)


@responses.activate
def test_metrics_handles_invalid_response_shape(
    umami_client, umami_api_base, website_id
):
    startAt = 200
    endAt = 300
    metric_type = MetricType.PATH
    responses.get(
        f"{umami_api_base}websites/{website_id}/metrics",
        json=[{"x": "abc", "y": "10"}],
        match=[
            responses.matchers.query_param_matcher(
                {
                    "startAt": str(startAt),
                    "endAt": str(endAt),
                    "type": str(metric_type),
                }
            )
        ],
    )
    with pytest.raises(UmamiClientError, match="expected x str and y int"):
        umami_client.metrics(startAt, endAt, metric_type)
