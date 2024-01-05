from dataclasses import dataclass
from datetime import datetime
import re
from typing import Dict, List, Optional

import browser_cookie3
import pandas as pd
import requests
import streamlit as st


@dataclass(frozen=True)
class Task:
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
    r = requests.get("https://workflowy.com/get_tree_data", 
                     cookies=self.cj,  
                     headers={"Accept": "application/json"})

    return r.json()


class TaskStore:
  def __init__(self, workflowy_service: WorkflowyService):
    self.workflowy_service = workflowy_service

  def _extract_due_date(self, workflowy_item: Dict) -> Optional[datetime]:
    match = re.search(r'<time startYear="(\d+)" startMonth="(\d+)" startDay="(\d+)">', workflowy_item["nm"])
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

  def _strip_tags(self, workflowy_item_nm: str) -> str:
    return re.sub(r"#(\w+)", "", workflowy_item_nm)

  def _extract_task_name(self, workflowy_item: Dict) -> str:
      return self._strip_tags(self._strip_due_date(workflowy_item["nm"]))

  def fetch_tasks(self) -> List[Task]:
    tree_data = self.workflowy_service.fetch_tree_data()

    tasks = []
    for item in tree_data["items"]:
      due_date = self._extract_due_date(item)
      tags = self._extract_tags(item) 
      name = self._extract_task_name(item)
      is_completed = "cp" in item
      is_goal = "#Goal" in tags
      task = Task(name, due_date, tags, is_completed, is_goal)
      tasks.append(task)
              
    return tasks


def main():
  workflow_service = WorkflowyService()
  task_store = TaskStore(workflow_service)
  tasks = task_store.fetch_tasks()

  st.title("Hardik's PTM")
  
  st.header("Goals")
  
  rows = []
  for task in tasks:
    if task.is_goal and not task.is_completed:
      rows.append([task.name, task.due_date_str, ", ".join(task.tags)])
  
  rows.sort(key=lambda r: r[1] or datetime(9999, 12, 31).strftime("%Y.%m.%d"))

  df = pd.DataFrame(rows, columns=["Task", "Due Date", "Tags"])

  st.table(df)


if __name__ == "__main__":
  main()
