import configparser
import logging

from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    Date,
    Engine,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    inspect,
)

from common import TaskList, TaskStore, WorkflowyService, WorkflowyHistoryManager


def init_logging():
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.ERROR)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.ERROR)


def get_table(config, meta):
    return Table(
        config["db"]["tablename"],
        meta,
        Column("id", String, primary_key=True),
        Column("parent_id", String, nullable=True),
        Column("name", String, nullable=False),
        Column("due_date", Date, nullable=True),
        Column("tags", ARRAY(String), nullable=False),
        Column("completion_date", Date, nullable=True),
        Column("is_action", Boolean, nullable=False),
        Column("is_goal", Boolean, nullable=False),
        Column("story_points", Integer, nullable=True),
    )


def clear_and_create_table(engine: Engine, meta: MetaData, table: Table, config):
    inspector = inspect(engine)
    if inspector.has_table(config["db"]["tablename"]):
        table.drop(engine)
        logging.info(f"{config['db']['tablename']} table has been dropped.")
    table.create(engine)


def populate_db(
    engine: Engine,
    meta: MetaData,
    tableSleep: Table,
    config: configparser.ConfigParser,
    task_list: TaskList,
):
    with engine.connect() as connection:
        for task in task_list.tasks:
            in_stmt = tableSleep.insert().values(
                id=task.id,
                parent_id=task.parent_id,
                name=task.name,
                due_date=task.due_date,
                tags=task.tags,
                completion_date=task.completion_date,
                is_action=task.is_action,
                is_goal=task.is_goal,
                story_points=task.story_points,
            )
            connection.execute(in_stmt)
            connection.commit()
        connection.commit()


def main():
    init_logging()

    config_path = "config.ini"
    config = configparser.ConfigParser()
    config.read(config_path)

    engine = create_engine(
        f"{config['db']['dbtype']}://{config['db']['username']}:{config['db']['password']}@{config['db']['host']}:{config['db']['port']}/{config['db']['dbname']}"
    )
    meta = MetaData()

    workflowy_service = WorkflowyService(read_cache=False)
    workflowy_history_manager = WorkflowyHistoryManager(workflowy_service)
    task_store = TaskStore(workflowy_service, workflowy_history_manager)
    task_list = task_store.fetch_tasks()

    table = get_table(config, meta)
    clear_and_create_table(engine, meta, table, config)
    populate_db(engine, meta, table, config, task_list)


if __name__ == "__main__":
    main()
