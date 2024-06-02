from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
import streamlit_calendar as st_calendar

from common import Task, TaskList, TaskStore, WorkflowyService, WorkflowyHistoryManager


def get_is_debug():
    is_debug = False
    query_params = st.query_params
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

    st.subheader("Goal Counts")
    col1, col2 = st.columns(2, gap="small")
    with col1:
        goals_by_week_component(task_list)
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
            if task.completion_date:
                idx = 0 if task.is_action else 1
            else:
                idx = 2
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
    st.markdown("Daily Budget: **48 STPs**")
    st.bar_chart(
        chart_data,
        x="Date",
        y=["Completed STPs", "Pending STPs"],
        color=["#CDF7F6", "#347FC4"],
    )


def goals_by_week_component(task_list: TaskList) -> None:
    date_format = "%b %d"
    max_weeks = 8

    goals_by_week = get_goals_by_week(task_list)

    goals_table_cols = [[], [], []]
    i = 1
    for _, row in sorted(goals_by_week.items(), key=lambda p: p[0])[(-1 * max_weeks) :]:
        table_week_str = (
            f"{i}. {row[1].strftime(date_format)} - {row[2].strftime(date_format)}"
        )
        goals_table_cols[0].append(table_week_str)
        goals_table_cols[1].append(len([t for t in row[0] if t.completion_date]))
        goals_table_cols[2].append(len([t for t in row[0] if not t.completion_date]))
        i += 1

    chart_data = pd.DataFrame(
        {
            "Week": goals_table_cols[0],
            "Completed Goals": goals_table_cols[1],
            "Pending Goals": goals_table_cols[2],
        }
    )

    st.bar_chart(
        chart_data,
        x="Week",
        y=["Completed Goals", "Pending Goals"],
        color=["#4C9141", "#FFA8A9"],
    )


def task_completions_by_week_component(task_list: TaskList) -> None:
    date_format = "%b %d"
    max_weeks = 8

    task_completions_by_week = get_tasks_by_week(task_list, completed_only=True)

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


def get_goals_by_week(
    task_list: TaskList,
) -> Dict[str, Tuple[List[Task], datetime, datetime]]:
    tasks_by_week = get_tasks_by_week(task_list, completed_only=False)

    finished_goals_by_week = {}
    for week_str, t in tasks_by_week.items():
        finished_goals_by_week[week_str] = (
            [task for task in t[0] if task.is_goal],
            t[1],
            t[2],
        )

    return finished_goals_by_week


def get_finished_goals_by_week(
    task_list: TaskList,
) -> Dict[str, Tuple[List[Task], datetime, datetime]]:
    completed_tasks_by_week = get_tasks_by_week(task_list, completed_only=True)

    finished_goals_by_week = {}
    for week_str, t in completed_tasks_by_week.items():
        finished_goals_by_week[week_str] = (
            [task for task in t[0] if task.is_goal],
            t[1],
            t[2],
        )

    return finished_goals_by_week


def get_tasks_by_week(
    task_list: TaskList, completed_only: bool
) -> Dict[str, Tuple[List[Task], datetime, datetime]]:
    date_format = "%Y-%m-%d"
    today = datetime.today()

    tasks_by_week = {}
    for task in task_list.tasks:
        if not task.due_date:
            continue

        if completed_only and not task.completion_date:
            continue

        week_start = task.due_date - timedelta(days=task.due_date.weekday() + 1)
        if week_start > today:
            continue

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
