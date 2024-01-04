from datetime import datetime
import re

import browser_cookie3
import pandas as pd
import requests
import streamlit as st

def extract_due_date(task_nm):
  match = re.search(r'<time startYear="(\d+)" startMonth="(\d+)" startDay="(\d+)">', task_nm)
  if match:
    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))
    return datetime(year, month, day)

  return None

def strip_due_date(text):
  return re.sub(r", Due <time .*?</time>", "", text)

def extract_tags(task_nm):
  return re.findall(r"(#\w+)", task_nm)

def strip_tags(task_nm):
  return re.sub(r"#(\w+)", "", task_nm)

def main():
  cj = browser_cookie3.chrome(domain_name="workflowy.com")

  r = requests.get(
    "https://workflowy.com/get_tree_data",
    cookies=cj,
    headers={"Accept": "application/json"},
  )

  workflowy_tree_data = r.json()

  st.title("Hardik's PTM")
  
  st.header("Goals")

  goals = []
  for task in workflowy_tree_data["items"]:
    if "#Goal" in task["nm"] and "cp" not in task:
      due_date = extract_due_date(task["nm"])
      tags = extract_tags(task["nm"])
      t = strip_tags(strip_due_date(task["nm"]))
      goals.append([t, due_date.strftime("%Y.%m.%d") if due_date else None, ", ".join(tags)])
  
  goals.sort(key=lambda x: x[1] or datetime(9999, 12, 31).strftime("%Y.%m.%d"))
  df = pd.DataFrame(goals, columns=["Task", "Due Date", "Tags"])
  st.table(df)

if __name__ == "__main__":
  main()
