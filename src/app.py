from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
import re
from typing import Dict, List, Optional

import browser_cookie3
import requests
import streamlit as st


@dataclass(frozen=True)
class Task:
    id: str
    parent_id: Optional[str]
    name: str
    due_date: Optional[datetime]
    tags: list[str]
    completion_date: Optional[datetime]
    is_goal: bool


class WorkflowyService:
    def __init__(self):
        self.cj = browser_cookie3.chrome(domain_name="workflowy.com")

    def fetch_initialization_data(self) -> Dict:
        r = requests.get(
            "https://workflowy.com/get_initialization_data?client_version=21&client_version_v2=28&no_root_children=1",
            cookies=self.cj,
            headers={"Accept": "application/json"},
        )

        return r.json()

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
        initialization_data = self.workflowy_service.fetch_initialization_data()
        tree_data = self.workflowy_service.fetch_tree_data()

        date_joined_timestamp_in_seconds = initialization_data["projectTreeData"][
            "mainProjectTreeInfo"
        ]["dateJoinedTimestampInSeconds"]

        tasks = []
        for item in tree_data["items"]:
            parent_id = None if item["prnt"] == "None" else item["prnt"]
            due_date = self._extract_due_date(item)
            tags = self._extract_tags(item)
            name = self._extract_task_name(item)
            if "cp" in item:
                completion_date_timestamp_in_seconds = (
                    date_joined_timestamp_in_seconds + item["cp"]
                )
                completion_date = datetime.fromtimestamp(
                    completion_date_timestamp_in_seconds
                )
            else:
                completion_date = None
            is_goal = "#Goal" in tags
            task = Task(
                item["id"], parent_id, name, due_date, tags, completion_date, is_goal
            )
            tasks.append(task)

        return TaskList(tasks)


def calculate_next_sunday(day: datetime) -> datetime:
    if day.weekday() == 6:
        return day + timedelta(days=7)
    else:
        days_to_sunday = 6 - day.weekday()
        return day + timedelta(days=days_to_sunday)


def goals_component(task_list: TaskList) -> None:
    task_map = task_list.getTaskMap()

    def get_ancestor_str(task_id):
        return " > ".join([task_map[id].name for id in task_list.getAncestors(task_id)])

    def format_due_date(due_date):
        return due_date.strftime("%b %d") if due_date else "(none)"

    st.header("Goals")

    filter_this_week = st.toggle("Due this week")
    today = datetime.today()
    next_sunday = calculate_next_sunday(today)

    rows = []
    for task in task_list.tasks:
        if task.is_goal and not task.completion_date:
            if filter_this_week:
                if task.due_date and task.due_date <= next_sunday:
                    rows.append(
                        [
                            task.name,
                            get_ancestor_str(task.id),
                            task.due_date,
                            ", ".join(task.tags),
                        ]
                    )
            else:
                rows.append(
                    [
                        task.name,
                        get_ancestor_str(task.id),
                        task.due_date,
                        ", ".join(task.tags),
                    ]
                )

    rows.sort(key=lambda r: r[2] or datetime(9999, 12, 31))

    for i, r in enumerate(rows):
        due_date_formatted = format_due_date(r[2])
        st.write(
            f"""
                <div>
                    <p style="color: white; font-weight: bold">{i + 1}) {r[0]}</p>
                    <p style="color: gray; font-size: 14px; margin-top: -10px">Due {due_date_formatted} • {r[1]}</p>
                </div>
            """,
            unsafe_allow_html=True,
        )


def statistics_component(task_list: TaskList) -> None:
    date_format = "%Y-%m-%d (%a)"
    today = datetime.today()
    trailing_thirty_day_start = today - timedelta(days=30)

    task_completion_by_date = {}
    for i in range(31):
        date = today - timedelta(days=i)
        date_str = date.strftime(date_format)
        task_completion_by_date[date_str] = 0

    for task in task_list.tasks:
        if task.completion_date and task.completion_date >= trailing_thirty_day_start:
            completion_date_str = task.completion_date.strftime(date_format)
            task_completion_by_date[completion_date_str] += 1

    st.header("Statistics")
    st.subheader("Task Completions")
    st.bar_chart(task_completion_by_date)


def main():
    workflow_service = WorkflowyService()
    task_store = TaskStore(workflow_service)
    task_list = task_store.fetch_tasks()

    st.title("Hardik's PTM")

    goals_component(task_list)
    statistics_component(task_list)


if __name__ == "__main__":
    main()
