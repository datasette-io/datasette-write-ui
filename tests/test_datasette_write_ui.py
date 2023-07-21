from datasette.app import Datasette
import pytest
import sqlite_utils
import json


def get_permission_from_table_html(html):
    """Extracts the datasette-write-ui "permissions" JSON that's injected into every table page"""
    prefix = '<script id="datasette-write-ui-permissions" type="application/json">'
    suffix = "</script>"
    permissions = None
    for line in html.splitlines():
        if line.startswith(prefix):
            permissions = json.loads(line[len(prefix) : -len(suffix)])
    return permissions


@pytest.fixture
def students_db_path(tmpdir):
    path = str(tmpdir / "students.db")
    sqlite_utils.Database(path)["students"].insert_all(
        [
            {"name": "alex", "age": 10},
            {"name": "brian", "age": 20},
            {"name": "craig", "age": 30},
        ]
    )
    return path


students_metadata = {
    "databases": {
        "students": {
            "tables": {"students": {"permissions": {"insert-row": {"id": "apollo"}}}}
        }
    }
}

actor_root = {"a": {"id": "root"}}
actor_apollo = {"a": {"id": "apollo"}}


@pytest.mark.asyncio
async def test_plugin_is_installed():
    datasette = Datasette(memory=True)
    response = await datasette.client.get("/-/plugins.json")
    assert response.status_code == 200
    installed_plugins = {p["name"] for p in response.json()}
    assert "datasette-write-ui" in installed_plugins


@pytest.mark.asyncio
async def test_permissions(students_db_path):
    datasette = Datasette(
        [students_db_path],
        metadata=students_metadata,
    )
    response = await datasette.client.get("/students/students")
    permissions = get_permission_from_table_html(response.text)
    assert permissions["can_delete"] == False
    assert permissions["can_insert"] == False
    assert permissions["can_update"] == False
    assert '<script id="datasette-write-ui" type="module">' not in response.text

    response = await datasette.client.get(
        "/students/students",
        cookies={"ds_actor": datasette.sign(actor_root, "actor")},
    )
    permissions = get_permission_from_table_html(response.text)
    assert permissions["can_delete"] == True
    assert permissions["can_insert"] == True
    assert permissions["can_update"] == True
    assert '<script id="datasette-write-ui" type="module">' in response.text

    response = await datasette.client.get(
        "/students/students",
        cookies={"ds_actor": datasette.sign(actor_apollo, "actor")},
    )
    permissions = get_permission_from_table_html(response.text)
    assert permissions["can_delete"] == False
    assert permissions["can_insert"] == True
    assert permissions["can_update"] == False
    assert '<script id="datasette-write-ui" type="module">' in response.text


@pytest.mark.asyncio
async def test_insert_row_details_route(students_db_path):
    datasette = Datasette([students_db_path])
    response = await datasette.client.get(
        "/-/insert-row-details?db=students&table=students",
        cookies={"ds_actor": datasette.sign(actor_root, "actor")},
    )
    assert response.status_code == 200
    assert response.json() == {
        "fields": [
            {"name": "name", "affinity": "text"},
            {"name": "age", "affinity": "int"},
        ]
    }


@pytest.mark.asyncio
async def test_update_row_details_route(students_db_path):
    datasette = Datasette([students_db_path])

    response = await datasette.client.get(
        "/-/edit-row-details?db=students&table=students&primaryKeys=1",
        cookies={"ds_actor": datasette.sign(actor_root, "actor")},
    )
    assert response.status_code == 200
    assert response.json() == {
        "fields": [
            {
                "key": "name",
                "value": "alex",
                "type": "str",
                "pk": False,
                "editable": True,
            },
            {"key": "age", "value": 10, "type": "int", "pk": False, "editable": True},
        ],
    }

    response = await datasette.client.get(
        "/-/insert-row-details?db=students&table=students",
    )
    assert response.status_code == 403