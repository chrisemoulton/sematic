import json
import typing
import uuid

# Third-party
import flask.testing

# Glow
from glow.api.tests.fixtures import test_client  # noqa: F401
from glow.db.tests.fixtures import (  # noqa: F401
    test_db,
    pg_mock,
    make_run,
    persisted_run,
    run,
)
from glow.db.queries import save_run
from glow.db.models.run import Run


def test_list_runs_empty(test_client: flask.testing.FlaskClient):  # noqa: F811
    results = test_client.get("/api/v1/runs?limit=3")

    assert results.json == dict(
        current_page_url="http://localhost/api/v1/runs?limit=3",
        next_page_url=None,
        limit=3,
        next_cursor=None,
        after_cursor_count=0,
        content=[],
    )


def test_list_runs(test_client: flask.testing.FlaskClient):  # noqa: F811
    created_runs = [save_run(make_run()) for _ in range(5)]

    # Sort by latest
    created_runs = sorted(created_runs, key=lambda run_: run_.created_at, reverse=True)

    results = test_client.get("/api/v1/runs?limit=3")

    payload = results.json
    payload = typing.cast(typing.Dict[str, typing.Any], payload)

    assert len(payload["next_page_url"]) > 0
    assert len(payload["next_cursor"]) > 0
    assert payload["after_cursor_count"] == len(created_runs)
    assert payload["content"] == [run_.to_json_encodable() for run_ in created_runs[:3]]

    next_page_url = payload["next_page_url"]
    next_page_url = next_page_url.split("localhost")[1]

    results = test_client.get(next_page_url)
    payload = results.json
    payload = typing.cast(typing.Dict[str, typing.Any], payload)

    assert payload["next_page_url"] is None
    assert payload["next_cursor"] is None
    assert payload["after_cursor_count"] == 2
    assert payload["content"] == [run_.to_json_encodable() for run_ in created_runs[3:]]


def test_group_by(test_client: flask.testing.FlaskClient):  # noqa: F811
    runs = {key: [make_run(name=key), make_run(name=key)] for key in ("RUN_A", "RUN_B")}

    for name, runs_ in runs.items():
        for run_ in runs_:
            save_run(run_)

    results = test_client.get("/api/v1/runs?group_by=name")

    payload = results.json
    payload = typing.cast(typing.Dict[str, typing.Any], payload)

    assert len(payload["content"]) == 2
    assert {run_["name"] for run_ in payload["content"]} == set(runs)


def test_filters(test_client: flask.testing.FlaskClient):  # noqa: F811
    runs = make_run(), make_run()
    runs[0].parent_id = uuid.uuid4().hex

    for run_ in runs:
        save_run(run_)

    for run_ in runs:
        filters = json.dumps({"parent_id": {"eq": run_.parent_id}})

        results = test_client.get("/api/v1/runs?filters={}".format(filters))

        payload = results.json
        payload = typing.cast(typing.Dict[str, typing.Any], payload)

        assert len(payload["content"]) == 1
        assert payload["content"][0]["id"] == run_.id


def test_and_filters(test_client: flask.testing.FlaskClient):  # noqa: F811
    run1 = make_run(name="abc", calculator_path="abc")
    run2 = make_run(name="def", calculator_path="abc")
    run3 = make_run(name="abc", calculator_path="def")

    for run_ in [run1, run2, run3]:
        save_run(run_)

    filters = {"AND": [{"name": {"eq": "abc"}}, {"calculator_path": {"eq": "abc"}}]}

    results = test_client.get("/api/v1/runs?filters={}".format(json.dumps(filters)))

    payload = results.json
    payload = typing.cast(typing.Dict[str, typing.Any], payload)

    assert len(payload["content"]) == 1
    assert payload["content"][0]["id"] == run1.id


def test_get_run_endpoint(
    persisted_run: Run, test_client: flask.testing.FlaskClient  # noqa: F811
):
    response = test_client.get("/api/v1/runs/{}".format(persisted_run.id))

    payload = response.json
    payload = typing.cast(typing.Dict[str, typing.Any], payload)

    assert payload["content"]["id"] == persisted_run.id


def test_get_run_404(test_client: flask.testing.FlaskClient):  # noqa: F811
    response = test_client.get("/api/v1/runs/unknownid")

    assert response.status_code == 404

    payload = response.json
    payload = typing.cast(typing.Dict[str, typing.Any], payload)

    assert payload == dict(error="No runs with id 'unknownid'")
