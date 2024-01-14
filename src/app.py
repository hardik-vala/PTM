from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
import json
import os
import re
from typing import Dict, List, Optional, Tuple

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
    completion_date: Optional[datetime]
    is_action: bool
    is_goal: bool


class WorkflowyService:
    CACHE_DIR = ".cache"

    def __init__(self, read_cache: bool = False):
        self.cj = browser_cookie3.chrome(domain_name="workflowy.com")
        self.read_cache = read_cache

        if not os.path.exists(self.CACHE_DIR):
            os.makedirs(self.CACHE_DIR)

    def load_from_cache(self, path: str) -> Optional[Dict]:
        if not os.path.exists(path):
            return None

        with open(path) as f:
            return json.load(f)

    def save_to_cache(self, data: Dict, path: str) -> None:
        with open(path, "w") as f:
            json.dump(data, f)

    def cache_it(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            cache_path = os.path.join(self.CACHE_DIR, f"{func.__name__}.json")

            if self.read_cache:
                data = self.load_from_cache(cache_path)
                if data:
                    return data

            data = func(self, *args, **kwargs)

            self.save_to_cache(data, cache_path)

            return data

        return wrapper

    @cache_it
    def fetch_initialization_data(self) -> Dict:
        r = requests.get(
            "https://workflowy.com/get_initialization_data?client_version=21&client_version_v2=28&no_root_children=1",
            cookies=self.cj,
            headers={"Accept": "application/json"},
        )

        return r.json()

    @cache_it
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
            is_action = "#Action" in tags
            is_goal = "#Goal" in tags
            task = Task(
                item["id"],
                parent_id,
                name,
                due_date,
                tags,
                completion_date,
                is_action,
                is_goal,
            )
            tasks.append(task)

        return TaskList(tasks)


def get_is_debug():
    is_debug = False
    query_params = st.experimental_get_query_params()
    if query_params:
        debug_query_param_value = query_params["debug"][0]
        if debug_query_param_value:
            is_debug = debug_query_param_value.lower() == "true"
    return is_debug


def calculate_next_sunday(day: datetime) -> datetime:
    if day.weekday() == 6:
        return day + timedelta(days=7)
    else:
        days_to_sunday = 6 - day.weekday()
        return day + timedelta(days=days_to_sunday)


def goals_component(task_list: TaskList) -> None:
    st.header("Goals")
    active_goals_component(task_list)
    finished_goals_by_week_component(task_list)


def active_goals_component(task_list: TaskList) -> None:
    task_map = task_list.getTaskMap()

    def get_ancestor_str(task_id):
        return " > ".join([task_map[id].name for id in task_list.getAncestors(task_id)])

    def format_due_date(due_date):
        return due_date.strftime("%b %d") if due_date else "(none)"

    st.subheader("Active Goals")

    filter_this_week = st.toggle("Due this week", value=True)
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

    
def finished_goals_by_week_component(task_list: TaskList) -> None:
    date_format = "%b %d"
    task_map = task_list.getTaskMap()
    finished_goals_by_week = get_finished_goals_by_week(task_list)

    def get_ancestor_str(task_id):
        return " > ".join([task_map[id].name for id in task_list.getAncestors(task_id)])

    st.subheader("Finished Goals")

    cols = st.columns(len(finished_goals_by_week), gap="small")

    i = 0
    for week_str, row in sorted(finished_goals_by_week.items(), key=lambda p: p[0]):
        week_str = f"{row[1].strftime(date_format)} - {row[2].strftime(date_format)}"
        with cols[i]:
            st.markdown(f"#### {week_str}")
            for j, task in enumerate(row[0]):
                st.write(
                    f"""
                        <div>
                            <p style="color: white"; font-size: 18px>{j + 1}) {task.name}</p>
                            <p style="color: gray; font-size: 12px; margin-top: -10px">{get_ancestor_str(task.id)}</p>
                        </div>
                    """,
                    unsafe_allow_html=True,
                )
        i += 1


def statistics_component(task_list: TaskList) -> None:
    st.header("Statistics")
    task_completions_by_date_component(task_list)
    goal_completions_by_week_component(task_list)


def task_completions_by_date_component(task_list: TaskList) -> None:
    date_format = "%Y-%m-%d (%a)"
    today = datetime.today()
    trailing_thirty_day_start = today - timedelta(days=30)

    completions_by_date = {}
    for i in range(31):
        date = today - timedelta(days=i)
        date_str = date.strftime(date_format)
        completions_by_date[date_str] = [0, 0]

    for task in task_list.tasks:
        if task.completion_date and task.completion_date >= trailing_thirty_day_start:
            completion_date_str = task.completion_date.strftime(date_format)
            idx = 0 if task.is_action else 1
            completions_by_date[completion_date_str][idx] += 1

    completions_table_cols = [[], [], []]
    for date, counts in completions_by_date.items():
        completions_table_cols[0].append(date)
        completions_table_cols[1].append(counts[0])
        completions_table_cols[2].append(counts[1])

    chart_data = pd.DataFrame(
        {
            "Date": completions_table_cols[0],
            "Actions": completions_table_cols[1],
            "Non-Actions": completions_table_cols[2],
        }
    )

    st.subheader("Task Completions")
    st.bar_chart(
        chart_data, x="Date", y=["Actions", "Non-Actions"], color=["#FFAA5A", "#70A0AF"]
    )


def goal_completions_by_week_component(task_list: TaskList) -> None:
    date_format = "%b %d"

    goal_completions_by_week = get_finished_goals_by_week(task_list)

    goal_completions_table_cols = [[], []]
    for week_str, row in goal_completions_by_week.items():
        table_week_str = (
            f"{row[1].strftime(date_format)} - {row[2].strftime(date_format)}"
        )
        goal_completions_table_cols[0].append(table_week_str)
        goal_completions_table_cols[1].append(len(row[0]))

    chart_data = pd.DataFrame(
        {
            "Week": goal_completions_table_cols[0],
            "Goals": goal_completions_table_cols[1],
        }
    )

    st.subheader("Goal Completions")
    st.bar_chart(chart_data, x="Week", y=["Goals"], color=["#4C9141"])


def get_finished_goals_by_week(
    task_list: TaskList,
) -> Dict[str, Tuple[List[Task], datetime, datetime]]:
    date_format = "%Y-%m-%d"

    finished_goals_by_week = {}
    for task in task_list.tasks:
        if task.is_goal and task.completion_date:
            week_start = task.due_date - timedelta(days=task.due_date.weekday() + 1)
            week_end = week_start + timedelta(days=7)
            week_str = (
                f"{week_start.strftime(date_format)}-{week_end.strftime(date_format)}"
            )
            if week_str in finished_goals_by_week:
                finished_goals_by_week[week_str][0].append(task)
            else:
                finished_goals_by_week[week_str] = [[task], week_start, week_end]

    return {k: tuple(v) for k, v in finished_goals_by_week.items()}


def main():
    st.set_page_config(page_title="Hardik's PTM Dashboard")
    st.title("Hardik's PTM Dashboard")

    is_debug = get_is_debug()
    workflow_service = WorkflowyService(read_cache=is_debug)
    task_store = TaskStore(workflow_service)
    task_list = task_store.fetch_tasks()

    statistics_component(task_list)
    goals_component(task_list)


if __name__ == "__main__":
    main()
