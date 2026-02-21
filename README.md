# Autodoist

*Note: v2.0 is a major refactor of Autodoist with a modular architecture and simplified feature set.*

This program adds two major functionalities to Todoist to help automate your workflow:

1) Assign automatic `@next_action` labels for a more GTD-like workflow
   - Flexible options to label tasks sequentially or in parallel
   - Hide future tasks based on the due date
2) Make multiple tasks (un)checkable at the same time

If this tool helped you out, I would really appreciate your support by providing me with some coffee!

<a href=https://ko-fi.com/hoffelhas>
 <img src="https://i.imgur.com/MU1rAPG.png" width="150">
</a>

# Requirements

Autodoist requires Python 3.11+.

To install dependencies using uv (recommended):

```bash
uv sync
```

Or with pip:

```bash
pip install -r requirements.txt
```

# 1. Automatic next action labels

The program looks for pre-defined tags in the name of every project, section, or parentless tasks in your Todoist account to automatically add and remove `@next_action` labels.

Projects, sections, and parentless tasks can be tagged independently of each other to create the required functionality. If this tag is not defined, it will not activate this functionality. The result will be a clear, current and comprehensive list of next actions without the need for further thought.

See the example given at [running Autodoist](#running-autodoist) on how to run this mode. If the label does not exist yet in your Todoist, it will be automatically created.

## Useful filter tip

For a more GTD-like workflow, you can use Todoist filters to create a clean and cohesive list that only contains your actionable tasks. As a simple example, you could use the following filter:

`@next_action & #PROJECT_NAME`

## Sequential processing

If a project, section, or parentless task ends with a dash `-`, the tasks will be treated sequentially in a priority queue, where only the first task that is found is labeled. If a task contains sub-tasks, the first lowest task is labeled instead.

![Sequential task labeling](https://i.imgur.com/ZUKbA8E.gif)

## Parallel processing

If a project, section, or parentless task name ends with an equal sign `=`, all tasks will be treated in parallel. A waterfall processing is applied, where the lowest possible (sub-)tasks are labelled.

![Parallel task labeling](https://i.imgur.com/xZZ0kEM.gif)

## Advanced labelling

Projects, sections, and (parentless) tasks can be used to specify how the levels under them should behave. This means that:

- A project can accept up to three tags, to specify how the sections, parentless tasks, and subtasks should behave.
- A section can accept up to two tags, to specify parentless tasks and subtasks should behave.
- A task at any level can be labelled with one tag, to specify how its sub-tasks should behave.

Tags can be applied on each level simultaneously, where the lower level setting will always override the one specified in the levels above.

### Shorthand notation

If fewer tags then needed are specified, the last one is simply copied. E.g. if a project has the tag `=` this is similar to `===`, or if a project has `=-` this is similar to `=--`. Same for sections, `=` is similar to `==`.

### Project labeling examples
- If a project ends with `---`, only the first section has tasks that are handled sequentially.
- If a project ends with `=--`, all sections have tasks that are handled sequentially.
- If a project ends with `-=-`, only the first section has parallel parentless tasks with sequential sub-tasks.
- If a project ends with `--=`, only the first section and first parentless tasks has parallel sub-tasks.
- If a project ends with `==-`, all sections and all parentless tasks will have sub-tasks are handled sequentially.
- If a project ends with `=-=`, all sections will have parentless tasks that are processed sequentially, but all sub-tasks are handled in parallel.
- If a project ends with `-==`, only the first section has parallel tasks.
- If a project ends with `===`, all tasks are handled in parallel.

### Section labeling examples
- If a section ends with `--`, only the first parentless task will have sub-tasks that are handled sequentially.
- If a section ends with `=-`, all parentless tasks will have sub-tasks that are handled sequentially.
- If a section ends with `-=`, only the first parentless task has sub-tasks that are handled in parallel.
- If a section ends with `==`, all tasks are handled in parallel.

### Tasks labeling examples
- If a task ends with `-`, the sub-tasks are handled sequentially.
- If a task ends with `=`, the sub-tasks are handled in parallel.

### Kanban board labeling
A standard workflow for Kanban boards is to have one actionable task per column/section, which is then moved to the next column when needed. Most often, the most right column is the 'done' section. To ensure that every column only has one labelled task and the last column contains no labelled tasks, you could do either of two things:
- Add the `=--` tag to the project name, and disable labelling for the 'done' section by adding `*` to either the start or end of the section name.
- Add the `--` tag to every section that you want to have labels.


## Due date enhanced experience

You can prevent labels of all tasks if the due date is too far in the future. Define the amount by running with the argument `-hf <NUMBER_OF_DAYS>`.
[See an example of the hide-future functionality](https://i.imgur.com/LzSoRUm.png).

# 2. Make multiple tasks uncheckable / re-checkable at the same time

Todoist allows the asterisk symbol `* ` to be used to ensure tasks can't be checked by turning them into headers. Now you are able to do this en masse!

Simply add `** ` or `-* ` in front of a project, section, or parentless task to automatically turn all the tasks that it includes into respectively headers or checkable tasks.

# Executing Autodoist

You can run Autodoist from any system that supports Python.

## Running Autodoist

Autodoist will read your environment to retrieve your Todoist API key and additional arguments.

Set the API key via environment variable (recommended for containers):

```bash
export TODOIST_API_KEY=<your-api-key>
```

To enable labelling mode, run with the `-l` argument:

```bash
python -m autodoist -l <LABEL_NAME>
```

Or with explicit API key:

```bash
python -m autodoist -a <API_KEY> -l <LABEL_NAME>
```

## Environment Variables

All configuration can be set via environment variables for containerized deployments:

| Variable | Description | Default |
|----------|-------------|---------|
| `TODOIST_API_KEY` | Todoist API key (required) | - |
| `AUTODOIST_LABEL` | Label name for next actions | - |
| `AUTODOIST_DELAY` | Delay between syncs in seconds | 5 |
| `AUTODOIST_P_SUFFIX` | Parallel suffix character | `=` |
| `AUTODOIST_S_SUFFIX` | Sequential suffix character | `-` |
| `AUTODOIST_HIDE_FUTURE` | Days to hide future tasks | 0 |
| `AUTODOIST_FOCUS_LABEL` | Singleton label to enforce (keeps only one active task) | - |
| `AUTODOIST_ONETIME` | Run once and exit | false |
| `AUTODOIST_DEBUG` | Enable debug logging | false |
| `AUTODOIST_DB_PATH` | Path to SQLite database | metadata.sqlite |

## Additional arguments

Several additional arguments can be provided, for example to change the suffix tags for parallel and sequential projects:

```bash
python -m autodoist --p_suffix <tag>
python -m autodoist --s_suffix <tag>
```

Note: Be aware that Todoist sections don't like to have a slash '/' in the name, which will automatically change to an underscore. Detection of the tag will not work.

If you want to hide all tasks due in the future:

```bash
python -m autodoist --hf <NUMBER_OF_DAYS>
```

In addition, if you experience issues with syncing you can increase the api syncing time (default 5 seconds):

```bash
python -m autodoist --delay <time in seconds>
```

To enforce a singleton focus label (`focus`) across all active tasks:

```bash
python -m autodoist --focus-label focus
```

For all arguments, please check out the help:

```bash
python -m autodoist --help
```

## Docker container

To build the docker container:

```bash
docker build . --tag autodoist:latest
```

To run autodoist inside the docker container:

```bash
docker run -e TODOIST_API_KEY=<your-key> -e AUTODOIST_LABEL=next_action autodoist:latest
```

Or with command line arguments:

```bash
docker run autodoist:latest -a <API_KEY> -l next_action
```

# Debug Web UI + JSON API (local)

A lightweight local dashboard is available to inspect Autodoist-relevant task state without using the Todoist UI.

Run it with:

```bash
autodoist-webui --api-key <API_KEY>
```

Or:

```bash
python -m autodoist.webui --api-key <API_KEY>
```

Optional arguments:

```bash
autodoist-webui --host 127.0.0.1 --port 8080 --next-action-label next_action --focus-label focus
autodoist-webui --db-path /path/to/metadata.sqlite
```

Then open:

- `http://127.0.0.1:8080/` (dashboard)

Dashboard includes a **Focus History** panel that defaults to open tasks only and shows the latest 5 items by default (adjustable). Each row includes:
- `Set as focus` (switches singleton focus to that task)
- `Open in Todoist` deep link

Useful API endpoints:

- `GET /api/health` - simple health check
- `GET /api/state` - full snapshot with tasks, labels, counts, and detected `focus` conflicts
- `GET /api/explain` - per-task reason codes for `next_action` and `focus` decisions
- `GET /api/tasks?label=focus` - filter tasks by label
- `GET /api/tasks?contains=foo` - filter tasks by content
- `GET /api/tasks?view=next_action|focus|conflicts|no_labels` - quick triage views
- `POST /api/tasks/<task_id>/labels` - row actions (`set_focus`, `clear_focus`, `remove_next_action`, `make_winner`)
- `GET /api/focus/history` - focus session history (supports `open_only`, `latest_per_task`, and `limit`)
- `GET /api/focus/history/<task_id>` - focus history for one task
- `GET /api/focus/reconcile-preview` - preview winner/losers and exact label diffs before apply
- `POST /api/focus/reconcile` - dry-run or apply singleton reconciliation

Reconcile examples:

Dry-run (no changes):

```bash
curl -X POST http://127.0.0.1:8080/api/focus/reconcile \
  -H 'Content-Type: application/json' \
  -d '{"apply": false}'
```

Apply conflict resolution:

```bash
curl -X POST http://127.0.0.1:8080/api/focus/reconcile \
  -H 'Content-Type: application/json' \
  -d '{"apply": true}'
```

Force a winner task id:

```bash
curl -X POST http://127.0.0.1:8080/api/focus/reconcile \
  -H 'Content-Type: application/json' \
  -d '{"apply": true, "winner_task_id": "1234567890"}'
```

Notes:

- Winner selection defaults to newest `updated_at`, then highest task id as a stable tie-break.
- This UI/API is intentionally standalone and does not modify Autodoist's core labeling loop.
