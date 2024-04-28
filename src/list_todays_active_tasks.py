from datetime import datetime

from common import TaskList, TaskStore, WorkflowyService, WorkflowyHistoryManager


def list_todays_active_tasks(task_list: TaskList) -> None:
    task_map = task_list.getTaskMap()

    def get_ancestor_str(task_id):
        return " > ".join([task_map[id].name for id in task_list.getAncestors(task_id)])

    today = datetime.today()

    rows = []
    for task in task_list.tasks:
        if not task.completion_date:
            if task.due_date and task.due_date <= today:
                rows.append(
                    [
                        task.name,
                        get_ancestor_str(task.id),
                        ", ".join(task.tags),
                    ]
                )
    return rows


def main():
    workflowy_service = WorkflowyService(read_cache=False)
    workflowy_history_manager = WorkflowyHistoryManager(workflowy_service)
    task_store = TaskStore(workflowy_service, workflowy_history_manager)
    task_list = task_store.fetch_tasks()

    rows = list_todays_active_tasks(task_list)

    for r in rows:
        print(f"{r[0]} [{r[1]}] {r[2] if r[2] else ''}")


if __name__ == "__main__":
    main()
