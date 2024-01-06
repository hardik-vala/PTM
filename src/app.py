from dataclasses import dataclass
from datetime import datetime, timedelta
import re
from typing import Dict, List, Optional

import browser_cookie3
import pandas as pd
import requests
import streamlit as st


@dataclass(frozen=True)
class Task:
    id: str
    parent_id: Optional[str]
    name: str
    due_date: Optional[datetime]
    tags: list[str]
    is_completed: bool
    is_goal: bool

    @property
    def due_date_str(self) -> Optional[str]:
        return self.due_date.strftime("%Y.%m.%d") if self.due_date else None


class WorkflowyService:
    def __init__(self):
        self.cj = browser_cookie3.chrome(domain_name="workflowy.com")

    def fetch_tree_data(self) -> Dict:
        r = requests.get(
            "https://workflowy.com/get_tree_data",
            cookies=self.cj,
            headers={"Accept": "application/json"},
        )

        return r.json()


class TaskList:
    def __init__(self, tasks: List[Task]):
        self.tasks = tasks
        self.task_map = None

    def getTaskMap(self) -> Dict[str, Task]:
        if not self.task_map:
            self.task_map = {t.id: t for t in self.tasks}

        return self.task_map

    def getAncestors(self, task_id):
        task_map = self.getTaskMap()

        ancestors = []
        ancestor_id = task_map[task_id].parent_id
        while ancestor_id:
            ancestors.append(ancestor_id)
            ancestor_id = task_map[ancestor_id].parent_id

        return ancestors[::-1]


class TaskStore:
    def __init__(self, workflowy_service: WorkflowyService):
        self.workflowy_service = workflowy_service

    def _extract_due_date(self, workflowy_item: Dict) -> Optional[datetime]:
        match = re.search(
            r'<time startYear="(\d+)" startMonth="(\d+)" startDay="(\d+)">',
            workflowy_item["nm"],
        )
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            return datetime(year, month, day)

        return None

    def _extract_tags(self, workflowy_item: Dict) -> List[str]:
        return re.findall(r"(#\w+)", workflowy_item["nm"])

    def _strip_due_date(self, workflowy_item_nm: str) -> str:
        return re.sub(r", Due <time .*?</time>", "", workflowy_item_nm)

    def _strip_html_tags(self, workflowy_item_nm: str) -> str:
        clean = re.compile("<.*?>")
        return re.sub(clean, "", workflowy_item_nm)

    def _strip_hashtags(self, workflowy_item_nm: str) -> str:
        return re.sub(r"#(\w+)", "", workflowy_item_nm)

    def _extract_task_name(self, workflowy_item: Dict) -> str:
        return self._strip_html_tags(
            self._strip_hashtags(self._strip_due_date(workflowy_item["nm"]))
        )

    def fetch_tasks(self) -> TaskList:
        tree_data = self.workflowy_service.fetch_tree_data()

        tasks = []
        for item in tree_data["items"]:
            parent_id = None if item["prnt"] == "None" else item["prnt"]
            due_date = self._extract_due_date(item)
            tags = self._extract_tags(item)
            name = self._extract_task_name(item)
            is_completed = "cp" in item
            is_goal = "#Goal" in tags
            task = Task(
                item["id"], parent_id, name, due_date, tags, is_completed, is_goal
            )
            tasks.append(task)

        return TaskList(tasks)


def calculate_next_sunday(day: datetime) -> datetime:
    if day.weekday() == 6:
        return day + timedelta(days=7)
    else:
        days_to_sunday = 6 - day.weekday()
        return day + timedelta(days=days_to_sunday)


def main():
    workflow_service = WorkflowyService()
    task_store = TaskStore(workflow_service)
    task_list = task_store.fetch_tasks()
    task_map = task_list.getTaskMap()

    def get_ancestor_str(task_id):
        return " > ".join([task_map[id].name for id in task_list.getAncestors(task_id)])

    st.title("Hardik's PTM")

    st.header("Goals")

    filter_this_week = st.toggle("Due this week")
    next_sunday = calculate_next_sunday(datetime.today())

    rows = []
    for task in task_list.tasks:
        if task.is_goal and not task.is_completed:
            if filter_this_week:
                if task.due_date and task.due_date <= next_sunday:
                    rows.append(
                        [
                            task.name,
                            get_ancestor_str(task.id),
                            task.due_date_str,
                            ", ".join(task.tags),
                        ]
                    )
            else:
                rows.append(
                    [
                        task.name,
                        get_ancestor_str(task.id),
                        task.due_date_str,
                        ", ".join(task.tags),
                    ]
                )

    rows.sort(key=lambda r: r[1] or datetime(9999, 12, 31).strftime("%Y.%m.%d"))

    df = pd.DataFrame(rows, columns=["Task", "Ancestors", "Due Date", "Tags"])

    st.table(df)


if __name__ == "__main__":
    main()
