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
import streamlit_calendar as st_calendar


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
    story_points: Optional[int]


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


class WorkflowyHistoryManager:
    HISTORY_DIR = ".history"

    def __init__(self, workflowy_service: WorkflowyService):
        self.workflowy_service = workflowy_service

        if not os.path.exists(self.HISTORY_DIR):
            os.makedirs(self.HISTORY_DIR)

    def load_latest_tree_snapshot(self) -> Optional[Dict]:
        dir_path = os.path.join(self.HISTORY_DIR, "tree_data")
        if not os.path.exists(dir_path):
            return None

        snapshot_filenames = os.listdir(dir_path)
        snapshot_filenames.sort(reverse=True)
        latest_snapshot_filename = snapshot_filenames[0]
        snapshot_path = os.path.join(dir_path, latest_snapshot_filename)

        with open(snapshot_path) as f:
            return json.load(f)

    def save_tree_snapshot(self) -> None:
        dir_path = os.path.join(self.HISTORY_DIR, "tree_data")
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        today = datetime.today()
        out_path = os.path.join(dir_path, today.strftime("%Y.%m.%d.%H.%M.%S") + ".json")

        tree_data = self.workflowy_service.fetch_tree_data()

        with open(out_path, "w") as f:
            json.dump(tree_data, f)


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
    def __init__(
        self,
        workflowy_service: WorkflowyService,
        workflowy_history_manager: WorkflowyHistoryManager,
    ):
        self.workflowy_service = workflowy_service
        self.workflowy_history_manager = workflowy_history_manager

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

    def _parse_tasks(self, initialization_data: Dict, tree_data: Dict) -> TaskList:
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
            story_points = None
            for tag in tags:
                if tag.endswith("STP"):
                    story_points = int(tag[1:-3])
            task = Task(
                item["id"],
                parent_id,
                name,
                due_date,
                tags,
                completion_date,
                is_action,
                is_goal,
                story_points
            )
            tasks.append(task)

        return TaskList(tasks)

    def fetch_tasks(self) -> TaskList:
        initialization_data = self.workflowy_service.fetch_initialization_data()
        tree_data = self.workflowy_service.fetch_tree_data()

        return self._parse_tasks(initialization_data, tree_data)

    def load_most_recent_historical_tasks(self) -> Optional[TaskList]:
        initialization_data = self.workflowy_service.fetch_initialization_data()
        tree_data = self.workflowy_history_manager.load_latest_tree_snapshot()

        if not tree_data:
            return None

        return self._parse_tasks(initialization_data, tree_data)


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


def calendar_component(task_list: TaskList) -> None:
    calendar_events = []
    for task in task_list.tasks:
        if not task.completion_date and task.due_date:
            calendar_events.append(
                {
                    "allDay": True,
                    "title": task.name,
                    "start": task.due_date.strftime("%Y-%m-%d"),
                    "end": task.due_date.strftime("%Y-%m-%d"),
                }
            )

    calendar_options = {
        "firstDay": 1,
        "headerToolbar": {
            "left": "",
            "center": "title",
            "right": "prev,next",
        },
        "initialView": "dayGridWeek",
    }
    custom_css = """
        .fc-event-past {
            opacity: 0.8;
        }
        .fc-event-time {
            font-style: italic;
        }
        .fc-event-title {
            font-weight: 700;
        }
        .fc-toolbar-title {
            font-size: 2rem;
        }
    """

    st.subheader("Calendar")
    st_calendar.calendar(
        events=calendar_events, options=calendar_options, custom_css=custom_css
    )


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
    max_weeks = 6
    date_format = "%b %d"
    task_map = task_list.getTaskMap()
    finished_goals_by_week = get_finished_goals_by_week(task_list)

    def get_ancestor_str(task_id):
        return " > ".join([task_map[id].name for id in task_list.getAncestors(task_id)])

    st.subheader("Finished Goals")

    cols = st.columns(min(len(finished_goals_by_week), max_weeks), gap="small")

    i = 0
    for week_str, row in sorted(finished_goals_by_week.items(), key=lambda p: p[0])[
        (-1 * max_weeks) :
    ]:
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


def statistics_component(
    task_list: TaskList, previous_task_list: Optional[TaskList]
) -> None:
    st.header("Statistics")

    st.subheader("Goal Completions")
    col1, col2 = st.columns(2, gap="small")
    with col1:
        goal_completions_by_week_component(task_list)
    with col2:
        goal_completions_by_month_component(task_list)

    st.subheader("Task Completions")
    col1, col2 = st.columns(2, gap="small")
    with col1:
        task_completions_by_week_component(task_list)
    with col2:
        task_completions_by_month_component(task_list)


def task_by_date_component(task_list: TaskList) -> None:
    date_format = "%Y-%m-%d (%a)"
    today = datetime.today()
    trailing_thirty_day_start = today - timedelta(days=30)

    tasks_by_date = {}
    for i in range(31):
        date = today - timedelta(days=i)
        date_str = date.strftime(date_format)
        tasks_by_date[date_str] = [0, 0, 0]

    for task in task_list.tasks:
        if (
            task.due_date
            and task.due_date >= trailing_thirty_day_start
            and task.due_date <= today
        ):
            due_date_str = task.due_date.strftime(date_format)
            idx = 0 if task.is_action else (1 if task.completion_date else 2)
            tasks_by_date[due_date_str][idx] += 1

    table_cols = [[], [], [], []]
    for date, counts in tasks_by_date.items():
        table_cols[0].append(date)
        table_cols[1].append(counts[0])
        table_cols[2].append(counts[1])
        table_cols[3].append(counts[2])

    chart_data = pd.DataFrame(
        {
            "Date": table_cols[0],
            "Completed Actions": table_cols[1],
            "Completed Tasks": table_cols[2],
            "Pending Tasks": table_cols[3],
        }
    )

    st.subheader("Task Counts")
    st.bar_chart(
        chart_data,
        x="Date",
        y=["Completed Actions", "Completed Tasks", "Pending Tasks"],
        color=["#FFAA5A", "#70A0AF", "#A675A1"],
    )


def story_points_by_date_component(task_list: TaskList) -> None:
    date_format = "%Y-%m-%d (%a)"
    today = datetime.today()
    trailing_thirty_day_start = today - timedelta(days=30)

    story_points_by_date = {}
    for i in range(31):
        date = today - timedelta(days=i)
        date_str = date.strftime(date_format)
        story_points_by_date[date_str] = [0, 0]

    for task in task_list.tasks:
        if (
            task.due_date
            and task.due_date >= trailing_thirty_day_start
            and task.due_date <= today
        ):
            due_date_str = task.due_date.strftime(date_format)
            story_points = task.story_points if task.story_points else 0
            idx = 0 if task.completion_date else 1
            story_points_by_date[due_date_str][idx] += story_points

    table_cols = [[], [], []]
    for date, story_points in story_points_by_date.items():
        table_cols[0].append(date)
        table_cols[1].append(story_points[0])
        table_cols[2].append(story_points[1])

    chart_data = pd.DataFrame(
        {
            "Date": table_cols[0],
            "Completed STPs": table_cols[1],
            "Pending STPs": table_cols[2],
        }
    )

    st.subheader("Story Points")
    st.bar_chart(
        chart_data,
        x="Date",
        y=["Completed STPs", "Pending STPs"],
        color=["#CDF7F6", "#347FC4"],
    )


def goal_completions_by_week_component(task_list: TaskList) -> None:
    date_format = "%b %d"
    max_weeks = 8

    goal_completions_by_week = get_finished_goals_by_week(task_list)

    goal_completions_table_cols = [[], []]
    i = 1
    for _, row in sorted(goal_completions_by_week.items(), key=lambda p: p[0])[
        (-1 * max_weeks) :
    ]:
        table_week_str = (
            f"{i}. {row[1].strftime(date_format)} - {row[2].strftime(date_format)}"
        )
        goal_completions_table_cols[0].append(table_week_str)
        goal_completions_table_cols[1].append(len(row[0]))
        i += 1

    chart_data = pd.DataFrame(
        {
            "Week": goal_completions_table_cols[0],
            "Goals": goal_completions_table_cols[1],
        }
    )

    st.bar_chart(chart_data, x="Week", y=["Goals"], color=["#4C9141"])


def task_completions_by_week_component(task_list: TaskList) -> None:
    date_format = "%b %d"
    max_weeks = 8

    task_completions_by_week = get_completed_tasks_by_week(task_list)

    task_completions_table_cols = [[], [], []]
    i = 1
    for _, row in sorted(task_completions_by_week.items(), key=lambda p: p[0])[
        (-1 * max_weeks) :
    ]:
        table_week_str = (
            f"{i}. {row[1].strftime(date_format)} - {row[2].strftime(date_format)}"
        )
        task_completions_table_cols[0].append(table_week_str)
        task_completions_table_cols[1].append(len([_ for t in row[0] if t.is_action]))
        task_completions_table_cols[2].append(
            len([_ for t in row[0] if not t.is_action])
        )
        i += 1

    chart_data = pd.DataFrame(
        {
            "Week": task_completions_table_cols[0],
            "Actions": task_completions_table_cols[1],
            "Other Tasks": task_completions_table_cols[2],
        }
    )

    st.bar_chart(
        chart_data, x="Week", y=["Actions", "Other Tasks"], color=["#FFAA5A", "#70A0AF"]
    )


def goal_completions_by_month_component(task_list: TaskList) -> None:
    goal_completions_by_month = get_finished_goals_by_month(task_list)

    goal_completions_table_cols = [[], []]
    i = 1
    for _, goal_completions_for_month in sorted(
        goal_completions_by_month.items(), key=lambda p: p[0]
    ):
        if not goal_completions_for_month:
            continue

        table_month_str = goal_completions_for_month[0].due_date.strftime("%b")
        goal_completions_table_cols[0].append(f"{i}. {table_month_str}")
        goal_completions_table_cols[1].append(len(goal_completions_for_month))
        i += 1

    chart_data = pd.DataFrame(
        {
            "Month": goal_completions_table_cols[0],
            "Goals": goal_completions_table_cols[1],
        }
    )

    st.bar_chart(chart_data, x="Month", y=["Goals"], color=["#4C9141"])


def task_completions_by_month_component(task_list: TaskList) -> None:
    task_completions_by_month = get_completed_tasks_by_month(task_list)

    task_completions_table_cols = [[], [], []]
    i = 1
    for _, task_completions_for_month in sorted(
        task_completions_by_month.items(), key=lambda p: p[0]
    ):
        if not task_completions_for_month:
            continue

        table_month_str = task_completions_for_month[0].due_date.strftime("%b")
        task_completions_table_cols[0].append(f"{i}. {table_month_str}")
        task_completions_table_cols[1].append(
            len([t for t in task_completions_for_month if t.is_action])
        )
        task_completions_table_cols[2].append(
            len([t for t in task_completions_for_month if not t.is_action])
        )

        i += 1

    chart_data = pd.DataFrame(
        {
            "Month": task_completions_table_cols[0],
            "Actions": task_completions_table_cols[1],
            "Other Tasks": task_completions_table_cols[2],
        }
    )

    st.bar_chart(
        chart_data,
        x="Month",
        y=["Actions", "Other Tasks"],
        color=["#FFAA5A", "#70A0AF"],
    )


def get_finished_goals_by_week(
    task_list: TaskList,
) -> Dict[str, Tuple[List[Task], datetime, datetime]]:
    completed_tasks_by_week = get_completed_tasks_by_week(task_list)

    finished_goals_by_week = {}
    for week_str, t in completed_tasks_by_week.items():
        finished_goals_by_week[week_str] = (
            [task for task in t[0] if task.is_goal],
            t[1],
            t[2],
        )

    return finished_goals_by_week


def get_completed_tasks_by_week(
    task_list: TaskList,
) -> Dict[str, Tuple[List[Task], datetime, datetime]]:
    date_format = "%Y-%m-%d"

    tasks_by_week = {}
    for task in task_list.tasks:
        if not task.completion_date or not task.due_date:
            continue

        week_start = task.due_date - timedelta(days=task.due_date.weekday() + 1)
        week_end = week_start + timedelta(days=7)
        week_str = (
            f"{week_start.strftime(date_format)}-{week_end.strftime(date_format)}"
        )
        if week_str in tasks_by_week:
            tasks_by_week[week_str][0].append(task)
        else:
            tasks_by_week[week_str] = [[task], week_start, week_end]

    return {k: tuple(v) for k, v in tasks_by_week.items()}


def get_finished_goals_by_month(
    task_list: TaskList,
) -> Dict[str, List[Task]]:
    completed_tasks_by_month = get_completed_tasks_by_month(task_list)

    finished_goals_by_month = {}
    for month_key, completed_tasks_for_month in completed_tasks_by_month.items():
        finished_goals_by_month[month_key] = list(
            filter(lambda t: t.is_goal, completed_tasks_for_month)
        )

    return finished_goals_by_month


def get_completed_tasks_by_month(task_list: TaskList) -> Dict[str, List[Task]]:
    tasks_by_month = defaultdict(list)
    for task in task_list.tasks:
        if not task.completion_date or not task.due_date:
            continue

        month_key = task.due_date.strftime("%Y-%m")

        tasks_by_month[month_key].append(task)

    return tasks_by_month


def main():
    st.set_page_config(page_title="Hardik's PTM Dashboard")
    st.title("Hardik's PTM Dashboard")

    is_debug = get_is_debug()
    workflowy_service = WorkflowyService(read_cache=is_debug)
    workflowy_history_manager = WorkflowyHistoryManager(workflowy_service)
    task_store = TaskStore(workflowy_service, workflowy_history_manager)
    task_list = task_store.fetch_tasks()
    most_recent_historical_task_list = task_store.load_most_recent_historical_tasks()

    st.button(
        "Save Snapshot of Workflowy",
        on_click=lambda: workflowy_history_manager.save_tree_snapshot(),
    )

    task_by_date_component(task_list)
    story_points_by_date_component(task_list)
    calendar_component(task_list)
    goals_component(task_list)
    statistics_component(task_list, most_recent_historical_task_list)


if __name__ == "__main__":
    main()
