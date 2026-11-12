from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str | URL):
    is_sqlite = (
        database_url.startswith("sqlite")
        if isinstance(database_url, str)
        else database_url.drivername.startswith("sqlite")
    )
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    return create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)


def ensure_sqlite_directory(database_url: str | URL) -> None:
    if not isinstance(database_url, str):
        return
    if not database_url.startswith("sqlite:///") or database_url == "sqlite:///:memory:":
        return
    database_path = Path(database_url.removeprefix("sqlite:///"))
    database_path.parent.mkdir(parents=True, exist_ok=True)


def build_session_factory(database_url: str | URL):
    ensure_sqlite_directory(database_url)
    engine = build_engine(database_url)
    return engine, sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def migrate_sqlite_compatibility(engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    if "listings" not in inspect(engine).get_table_names():
        return

    columns = {column["name"] for column in inspect(engine).get_columns("listings")}
    new_columns = {
        "owner_id": "varchar(120) not null default 'legacy'",
        "location": "text",
        "offer_type_id": "integer",
        "house_type_id": "integer",
        "published_at": "datetime",
        "construction_year": "integer",
        "garage": "boolean not null default 0",
        "building_size_m2": "float",
        "land_size_m2": "float",
        "availability_months": "integer",
        "storage_size_m2": "float",
        "updated_at": "datetime",
    }

    with engine.begin() as connection:
        for name, column_type in new_columns.items():
            if name not in columns:
                connection.execute(text(f"alter table listings add column {name} {column_type}"))

        connection.execute(
            text("insert or ignore into offer_types (name) values ('sale'), ('rent'), ('both')")
        )
        connection.execute(
            text("insert or ignore into house_types (name) values ('Unclassified')")
        )
        connection.execute(
            text(
                "update listings set offer_type_id = "
                "(select id from offer_types where offer_types.name = listings.mode) "
                "where offer_type_id is null"
            )
        )
        connection.execute(
            text(
                "update listings set house_type_id = "
                "(select id from house_types where name = 'Unclassified') "
                "where house_type_id is null"
            )
        )
