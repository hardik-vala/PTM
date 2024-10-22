# PTM

My Personal Task Management System

For organizing and tracking my tasks and projects. It’s supposed to be a system
of keeping track and schedule what I need to do, should do, and consider
doing — While informing me how well I’m doing those activities.

## Principles

* One of the basic assumptions is that I’m dumb — or, rather, that my
subconsciousness is quite dumb when it comes to thinking about things 
I *should* do.
* Another assumption is that I’m afraid — incapable of deciding what I should 
do in the moment because I fear the most important tasks.
* My productivity can be hacked through gamification.

## Goals

* Empty my subconsciousness from keeping track of all the things I need to do 
and constantly reminding me — reducing stress and freeing up precious brain 
time for more productive thinking.
* Make it efficient, and fun, to manipulate tasks so the overhead in managing 
tasks is kept low and there’s nothing interfering with maintaining good task 
hygiene.
* Protect me from getting sucked into busywork, work for work’s sake. Shove 
context, goals, outcomes, ie. the big picture, and the actions that help paint 
that picture, in my face so it permanently influences how I think about
scheduling my time.
* Suppressing laziness and fear from making executive decisions about what I 
should work on, which biases for easy and fun, over hard and significant.
* Calibrate my self-understanding of my productivity, e.g. how many goals, 
actions, tasks I can cross off in a given timeframe. Therefore, giving a 
measurable way to cast sunlight on areas where I can improve my task planning 
(e.g. assigning myself an excessive number of tasks) by reporting my history of 
performance, and guide me towards corrections.
* A system that is flexible enough to adapt to constant change in needs.
* Motivation.

## Features

* Easily add, edit, and delete tasks.
  * Support recurring tasks.
  * Allow organizing tasks through infinite nesting so the full context around a task is captured and simply depicted.
* Treat dates as a first-class annotation and slap editable due dates on work items. 
* Label goals / milestones for a given day, week, month, etc.
  * **\*Make these visible in a way I can’t ignore them.\***
  * Track progress towards goals / milestones.
* Mark tasks as OKRs (either O’s or KR’s) and interleave them with other tasks.
* Label actions to distinguish them from goals and more importantly, work that contributes to motion but in a way that furthers outcomes.
* A “Waiting For” list to aggregate and monitor tasks that are blocked, waiting for something to make progress
* Views
  * Tasks planned and completed on any given day.
  * View work items in a calendar view
* Reporting
  * Track daily, weekly, and monthly counts task completion counts.
  * Track the daily, weekly, and monthly counts of completed actions.
  * Track the weekly and monthly count of completed goals.
  * Track the rate of completions for goals, actions, and tasks, ie. the ratio of work items that are completed relative the amount that’s planned.
  * The rate of unplanned work items.
* Keyboard shortcuts for seamless navigation.
* Track daily task story points against a daily budget.

## System

-> Task Store (Workflowy): As the task entry and storage layer, including metadata.

-> Dashboard (Local Streamlit app): A collection of different task views.

## Processes

### Capturing tasks — Inbox

It starts with an Inbox, which is where all tasks and whims go as they occur to me. The barrier to adding something to my Inbox should be as low as possible and adding something should be as accessible as possible (e.g. when I’m on the go).

My Inbox takes the form of untagged notes added to **Bear**, **emails** to myself, and **stickies** (virtual).

Often, they can be dropped directly into the Task Store.

### Updating tasks

Tasks from the inbox are transferred to the Task Store, paying careful attention to placement of tasks in the hierarchy.

* Each task maybe given a date, indicating the date by which it should be completed (e.g. “Due Jan 1, 2024”)
* Items that represent goals are marked with \#WeeklyGoal, \#MonthlyGoal, \#QuarterlyGoal and items that represent actions are marked with \#Action
* Recurring tasks are identified by \#Daily, \#Weekly, \#Monthly, \#Quarterly, \#Annually, etc.
* Tasks that are queued up for scheduling are tagged with \#OnDeck
* Assign story points (where 1 STP = 15 min.) for tasks that demand effort using the notation, \#4STP (ie. 4 story points).
  * If you can’t predict the duration needed to complete a task (e.g. because it’s novel work), take your initial estimate, and double it.
  * Schedule it for your deep work block. That way, you’re less vulnerable to shying away from the uncertainty because you know you won’t be interrupted.

### “Waiting For”

A “Waiting For” list to aggregate and monitor tasks that are blocked, waiting 
for something to make progress.

### Daily planning

Spend ~15 min. each day, as part of your morning routine,
1. Review your weekly, monthly, quarterly, yearly, 5-year, 10-year, and life goals.
2. Applying the “[Day 1 mentality](obsidian://open?vault=KMS&file=Entrepreneurship%2FDay%201%20Mentality)”, and assign yourself a daily adventure (thinking about it as an adventure makes it more fun) — Before even looking at your tasks — *What are the most important things I need to get done today to maximize progress towards my goals?*
   * Give yourself one, optional, side quest
3. Updating the Task Store and designating tasks that are due today.
4. Estimate the time costs for each task, and if there are too many bite-sized tasks to track, group them under a parent task, and assign story points to that task.
5. Make sure the total story point amount over all the tasks is below your daily budget of 48 STPs.
6. Use time blocking in your calendar for what’s important.
7. Use a stickie to order tasks and keep a mini-backlog, helping you focus on one priority / task.

* Give the PTM dashboard its own window so you’re forced to look at it when you’re interacting with your tasks management system

#### Goals

I’ve have an array of buckets for my life, each activating a different part of the brain. And countless research studies of demonstrated that multi-tasking doesn’t work - The cognitive processes of the brain have to work very hard to switch from lighting up different parts of the brain - Which can be very distressing and de-motivating. Given that constraint, I orient my day around a single (or handful of) challenging goals (ie. my daily adventure), in addition to my purpose-fulfilling time, which coincides with one of my life categories. That allows me the unperturbed focus to getting something meaningful done each day.

### Weekly planning [WIP]



### Heuristics

* Tasks should be **physical, visible** actions to move a project closer to its 
goal. This greatly lowers the resistance to *do* things.
* When adding and organizing a task into the Task Store, consider if it takes 
less than two minutes to do it. If this is the case: do it. Right away. The 
reason for this is simple: if the action takes two minutes or less, the 
overhead of tracking it will be large compared to how long it takes to 
just *do* it. 
* Use contexts as “tags” on the items saying where the action can be done, or what equipment I need to perform it. Examples: @ home, @ computer, and @ office.


## Development

### Streamlit App (DEPRECATED)

Setup:

```
pip3 install -r requirements.txt
```

Run:

```
streamlit run src/app.py
```

### App

Launch:

```
docker compose up
```

Populate:

```
python3 src/populate_db.py
```

Live at http://localhost:3000

Debug:

```
docker exec -it ptm-db psql -U postgres -d ptm-db
```

(You can populate the db and open the dasbhoard with `open.sh`.)

Auto-shutdown:

https://github.com/hardik-vala/misc/tree/main/shutdown
