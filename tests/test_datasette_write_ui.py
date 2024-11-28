from datasette.app import Datasette
import pytest
import sqlite_utils
import json


def get_permission_from_table_html(html):
    """Extracts the datasette-write-ui "permissions" JSON that's injected into every table page"""
    prefix = '<script id="datasette-write-ui-config" type="application/json">'
    suffix = "</script>"
    permissions = None
    for line in html.splitlines():
        if line.startswith(prefix):
            permissions = json.loads(line[len(prefix) : -len(suffix)])
    return permissions


@pytest.fixture
def db_with_dot_in_name(tmpdir):
    path = str(tmpdir / "db.with.dot.in.name.db")
    db = sqlite_utils.Database(path)
    db["students"].insert_all(
        [
            {"name": "alex", "age": 10},
            {"name": "brian", "age": 20},
            {"name": "craig", "age": 30, "[weird (column)]": 1},
        ]
    )
    db.execute("create table courses(name text primary key) without rowid")
    db["courses"].insert_all(
        [
            {"name": "MATH 101"},
            {"name": "MATH 102"},
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


@pytest.fixture
def students_db_path(tmpdir):
    path = str(tmpdir / "students.db")
    db = sqlite_utils.Database(path)
    db["students"].insert_all(
        [
            {"name": "alex", "age": 10},
            {"name": "brian", "age": 20},
            {"name": "craig", "age": 30, "[weird (column)]": 1},
        ]
    )
    db.execute("create table courses(name text primary key) without rowid")
    db["courses"].insert_all(
        [
            {"name": "MATH 101"},
            {"name": "MATH 102"},
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
        config=students_metadata,
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
    assert (
        '<script id="datasette-write-ui" type="module" src="/-/static-plugins/datasette_write_ui/table.min.js"></script>'
        in response.text
    )

    response = await datasette.client.get(
        "/students/students",
        cookies={"ds_actor": datasette.sign(actor_apollo, "actor")},
    )
    permissions = get_permission_from_table_html(response.text)
    assert permissions["can_delete"] == False
    assert permissions["can_insert"] == True
    assert permissions["can_update"] == False
    assert (
        '<script id="datasette-write-ui" type="module" src="/-/static-plugins/datasette_write_ui/table.min.js"></script>'
        in response.text
    )


@pytest.mark.asyncio
async def test_insert_row_details_route(students_db_path):
    datasette = Datasette([students_db_path])

    response = await datasette.client.get(
        "/-/datasette-write-ui/insert-row-details?db=students&table=students",
    )
    assert response.status_code == 403

    response = await datasette.client.get(
        "/-/datasette-write-ui/insert-row-details?db=students&table=students",
        cookies={"ds_actor": datasette.sign(actor_root, "actor")},
    )
    assert response.status_code == 200
    assert response.json() == {
        "fields": [
            {"name": "name", "affinity": "text"},
            {"name": "age", "affinity": "int"},
            {"name": "_weird (column)_", "affinity": "int"},
        ]
    }


@pytest.mark.asyncio
async def test_insert_row_details_route(students_db_path):
    datasette = Datasette([students_db_path])

    response = await datasette.client.get(
        "/-/datasette-write-ui/insert-row-details?db=students&table=students",
    )
    assert response.status_code == 403

    response = await datasette.client.get(
        "/-/datasette-write-ui/insert-row-details?db=students&table=students",
        cookies={"ds_actor": datasette.sign(actor_root, "actor")},
    )
    assert response.status_code == 200
    assert response.json() == {
        "fields": [
            {"name": "name", "affinity": "text"},
            {"name": "age", "affinity": "int"},
            {"name": "_weird (column)_", "affinity": "int"},
        ]
    }

@pytest.mark.asyncio
async def test_update_row_details_route(students_db_path):
    datasette = Datasette([students_db_path])

    response = await datasette.client.get(
        "/-/datasette-write-ui/edit-row-details?db=students&table=students",
    )
    assert response.status_code == 403

    response = await datasette.client.get(
        "/-/datasette-write-ui/edit-row-details?db=students&table=students&primaryKeys=1",
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
            {
                "key": "_weird (column)_",
                "value": None,
                "type": "NoneType",
                "pk": False,
                "editable": True,
            },
        ]
    }

    response = await datasette.client.get(
        "/-/datasette-write-ui/edit-row-details?db=students&table=courses&primaryKeys=MATH+101",
        cookies={"ds_actor": datasette.sign(actor_root, "actor")},
    )
    assert response.status_code == 200
    assert response.json() == {
        "fields": [
            {
                "key": "name",
                "value": "MATH 101",
                "type": "str",
                "pk": True,
                "editable": False,
            },
        ]
    }

    response = await datasette.client.get(
        "/-/datasette-write-ui/edit-row-details?db=students&table=courses&primaryKeys=not_exist",
        cookies={"ds_actor": datasette.sign(actor_root, "actor")},
    )
    assert response.status_code == 400
    assert response.json() == {"ok": False, "message": "No matching row found."}

    response = await datasette.client.get(
        "/-/datasette-write-ui/edit-row-details?db=students&table=courses",
        cookies={"ds_actor": datasette.sign(actor_root, "actor")},
    )
    assert response.status_code == 400
    assert response.json() == {
        "ok": False,
        "message": "primaryKeys parameter is required",
    }

    response = await datasette.client.get(
        "/-/datasette-write-ui/edit-row-details?db=students&primaryKeys=1",
        cookies={"ds_actor": datasette.sign(actor_root, "actor")},
    )
    assert response.status_code == 400
    assert response.json() == {"ok": False, "message": "table parameter is required"}

    response = await datasette.client.get(
        "/-/datasette-write-ui/edit-row-details?table=courses&primaryKeys=1",
        cookies={"ds_actor": datasette.sign(actor_root, "actor")},
    )
    assert response.status_code == 400
    assert response.json() == {"ok": False, "message": "db parameter is required"}


@pytest.mark.asyncio
@pytest.mark.parametrize("base_url", (None, "/abc/"))
async def test_base_url(students_db_path, base_url):
    if base_url:
        datasette = Datasette([students_db_path], settings={"base_url": base_url})
    else:
        datasette = Datasette([students_db_path])
    # Check for correct /-/static path on several pages
    for path in ("/", "/students", "/students/students"):
        # datasette.client.get(path) automatically fixes the URL passed to it
        # to respect base_url, so we don't need to change that here:
        response = await datasette.client.get(path)
        assert response.status_code == 200
        expected_static_path = "/-/static"
        if base_url:
            expected_static_path = base_url.rstrip("/") + expected_static_path
        assert expected_static_path in response.text

@pytest.mark.asyncio
async def test_tildedecode(db_with_dot_in_name):
    datasette = Datasette(
        [db_with_dot_in_name],
        metadata=students_metadata,
    )
    response = await datasette.client.get("/-/datasette-write-ui/insert-row-details?db=db%7E2Ewith%7E2Edot%7E2Ein%7E2Ename&table=courses", 
                                          cookies={"ds_actor": datasette.sign(actor_root, "actor")})
    assert response.status_code == 200

    response = await datasette.client.get("/-/datasette-write-ui/edit-row-details?db=db%7E2Ewith%7E2Edot%7E2Ein%7E2Ename&table=courses&primaryKeys=MATH+101", 
                                          cookies={"ds_actor": datasette.sign(actor_root, "actor")})
    assert response.status_code == 200
