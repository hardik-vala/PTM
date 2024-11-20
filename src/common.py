from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import wraps
import json
import os
import re
from typing import Dict, List, Optional

import browser_cookie3
import requests


@dataclass(frozen=True)
class Task:
    id: str
    parent_id: Optional[str]
    name: str
    due_date: Optional[datetime]
    tags: List[str]
    completion_date: Optional[datetime]
    is_action: bool
    is_week_goal: bool
    is_month_goal: bool
    is_quarter_goal: bool
    is_annual_goal: bool
    is_milestone: bool
    is_ondeck: bool
    story_points: Optional[int]

    @property
    def is_goal(self) -> bool:
        return (
            self.is_week_goal
            or self.is_month_goal
            or self.is_quarter_goal
            or self.is_annual_goal
        )


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
            is_week_goal = "#WeekGoal" in tags
            is_month_goal = "#MonthGoal" in tags
            is_quarter_goal = "#QuarterGoal" in tags
            is_annual_goal = "#AnnualGoal" in tags
            is_milestone = "#Milestone" in tags
            is_ondeck = "#OnDeck" in tags
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
                is_week_goal,
                is_month_goal,
                is_quarter_goal,
                is_annual_goal,
                is_milestone,
                is_ondeck,
                story_points,
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
