"""
Test Todoist API interactions for Autodoist.

These tests verify that the API calls work correctly with the current
SDK version and API endpoints.

Run with: pytest tests/test_api.py -v
Or with token: TODOIST_API_TOKEN=xxx pytest tests/test_api.py -v
"""

import os
import pytest
import requests

# Get token from environment
API_TOKEN = os.environ.get('TODOIST_API_TOKEN')

# Skip all tests if no token
pytestmark = pytest.mark.skipif(
    not API_TOKEN,
    reason="TODOIST_API_TOKEN environment variable not set"
)


class TestRestAPI:
    """Test REST API v2 endpoints directly."""

    def test_rest_api_labels(self):
        """Test that REST API returns labels correctly."""
        response = requests.get(
            "https://api.todoist.com/rest/v2/labels",
            headers={"Authorization": f"Bearer {API_TOKEN}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"

        labels = response.json()
        assert isinstance(labels, list), "Labels should be a list"

        if labels:
            label = labels[0]
            assert 'id' in label, "Label should have 'id'"
            assert 'name' in label, "Label should have 'name'"
            print(f"\nFound {len(labels)} labels")
            print(f"First label: {label}")

    def test_rest_api_projects(self):
        """Test that REST API returns projects correctly."""
        response = requests.get(
            "https://api.todoist.com/rest/v2/projects",
            headers={"Authorization": f"Bearer {API_TOKEN}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"

        projects = response.json()
        assert isinstance(projects, list), "Projects should be a list"

        if projects:
            project = projects[0]
            assert 'id' in project, "Project should have 'id'"
            assert 'name' in project, "Project should have 'name'"
            print(f"\nFound {len(projects)} projects")

    def test_rest_api_tasks(self):
        """Test that REST API returns tasks correctly."""
        response = requests.get(
            "https://api.todoist.com/rest/v2/tasks",
            headers={"Authorization": f"Bearer {API_TOKEN}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"

        tasks = response.json()
        assert isinstance(tasks, list), "Tasks should be a list"
        print(f"\nFound {len(tasks)} tasks")


class TestSyncAPI:
    """Test Sync API v1 endpoints."""

    def test_sync_api_full_sync(self):
        """Test full sync with Sync API v1."""
        response = requests.post(
            "https://api.todoist.com/api/v1/sync",
            headers={
                "Authorization": f"Bearer {API_TOKEN}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data='sync_token=*&resource_types=["all"]'
        )
        assert response.status_code == 200, f"Failed: {response.text}"

        data = response.json()
        assert 'sync_token' in data, "Response should have sync_token"
        assert 'projects' in data, "Response should have projects"
        assert 'items' in data, "Response should have items (tasks)"
        assert 'labels' in data, "Response should have labels"

        print(f"\nSync token: {data['sync_token'][:20]}...")
        print(f"Projects: {len(data.get('projects', []))}")
        print(f"Items (tasks): {len(data.get('items', []))}")
        print(f"Labels: {len(data.get('labels', []))}")
        print(f"Sections: {len(data.get('sections', []))}")

    def test_sync_api_labels_only(self):
        """Test sync with only labels resource."""
        response = requests.post(
            "https://api.todoist.com/api/v1/sync",
            headers={
                "Authorization": f"Bearer {API_TOKEN}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data='sync_token=*&resource_types=["labels"]'
        )
        assert response.status_code == 200, f"Failed: {response.text}"

        data = response.json()
        assert 'labels' in data, "Response should have labels"

        labels = data['labels']
        if labels:
            label = labels[0]
            assert 'id' in label, "Label should have 'id'"
            assert 'name' in label, "Label should have 'name'"
            print(f"\nSync API labels: {[l['name'] for l in labels[:5]]}")


class TestSDK:
    """Test todoist-api-python SDK."""

    def test_sdk_import(self):
        """Test that SDK can be imported."""
        from todoist_api_python.api import TodoistAPI
        assert TodoistAPI is not None

    def test_sdk_init(self):
        """Test SDK initialization."""
        from todoist_api_python.api import TodoistAPI
        api = TodoistAPI(token=API_TOKEN)
        assert api is not None

    def test_sdk_get_labels(self):
        """Test SDK get_labels returns ResultsPaginator (SDK v3.x behavior)."""
        from todoist_api_python.api import TodoistAPI
        api = TodoistAPI(token=API_TOKEN)

        labels = api.get_labels()
        # SDK v3.x returns ResultsPaginator, not a list
        assert hasattr(labels, '__iter__'), "Labels should be iterable"
        print(f"\nLabels type: {type(labels)}")

        # Flatten paginator to get actual items
        all_labels = []
        for page in labels:
            if isinstance(page, list):
                all_labels.extend(page)
            else:
                all_labels.append(page)

        if all_labels:
            label = all_labels[0]
            print(f"Label type: {type(label)}")
            assert hasattr(label, 'name'), "Label should have 'name' attribute"
            assert hasattr(label, 'id'), "Label should have 'id' attribute"
            print(f"Label has .name: {label.name}")
            print(f"Label has .id: {label.id}")

    def test_sdk_get_projects(self):
        """Test SDK get_projects returns ResultsPaginator (SDK v3.x behavior)."""
        from todoist_api_python.api import TodoistAPI
        api = TodoistAPI(token=API_TOKEN)

        projects = api.get_projects()
        # SDK v3.x returns ResultsPaginator, not a list
        assert hasattr(projects, '__iter__'), "Projects should be iterable"
        print(f"\nProjects type: {type(projects)}")

        # Flatten paginator to get actual items
        all_projects = []
        for page in projects:
            if isinstance(page, list):
                all_projects.extend(page)
            else:
                all_projects.append(page)

        if all_projects:
            project = all_projects[0]
            print(f"Project type: {type(project)}")
            assert hasattr(project, 'name'), "Project should have 'name' attribute"
            print(f"Project has .name: {project.name}")
            print(f"Project has .id: {project.id}")

    def test_sdk_get_tasks(self):
        """Test SDK get_tasks returns ResultsPaginator (SDK v3.x behavior)."""
        from todoist_api_python.api import TodoistAPI
        api = TodoistAPI(token=API_TOKEN)

        tasks = api.get_tasks()
        # SDK v3.x returns ResultsPaginator, not a list
        assert hasattr(tasks, '__iter__'), "Tasks should be iterable"
        print(f"\nTasks type: {type(tasks)}")

        # Flatten paginator to get actual items
        all_tasks = []
        for page in tasks:
            if isinstance(page, list):
                all_tasks.extend(page)
            else:
                all_tasks.append(page)

        if all_tasks:
            task = all_tasks[0]
            print(f"Task type: {type(task)}")
            assert hasattr(task, 'content'), "Task should have 'content' attribute"
            print(f"Task has .content: {task.content[:50]}...")
            print(f"Task has .id: {task.id}")
            print(f"Task has .labels: {task.labels}")

    def test_sdk_get_sections(self):
        """Test SDK get_sections returns ResultsPaginator (SDK v3.x behavior)."""
        from todoist_api_python.api import TodoistAPI
        api = TodoistAPI(token=API_TOKEN)

        sections = api.get_sections()
        # SDK v3.x returns ResultsPaginator, not a list
        assert hasattr(sections, '__iter__'), "Sections should be iterable"
        print(f"\nSections type: {type(sections)}")

        # Flatten paginator to get actual items
        all_sections = []
        for page in sections:
            if isinstance(page, list):
                all_sections.extend(page)
            else:
                all_sections.append(page)

        print(f"Found {len(all_sections)} sections")


class TestAutodoist:
    """Test autodoist.py functions directly."""

    def test_initialise_sync_api(self):
        """Test the initialise_sync_api function."""
        import sys
        sys.path.insert(0, '/Users/erauner/git/side/homelab-autodoist')

        from todoist_api_python.api import TodoistAPI
        from autodoist import initialise_sync_api

        api = TodoistAPI(token=API_TOKEN)
        sync_api = initialise_sync_api(api, API_TOKEN)

        assert sync_api is not None, "sync_api should not be None"
        assert 'sync_token' in sync_api, "sync_api should have sync_token"
        assert 'projects' in sync_api, "sync_api should have projects"

        print(f"\nSync successful!")
        print(f"Projects: {len(sync_api.get('projects', []))}")
        print(f"Labels: {len(sync_api.get('labels', []))}")

    def test_label_helper_functions(self):
        """Test the label helper functions handle both formats."""
        import sys
        sys.path.insert(0, '/Users/erauner/git/side/homelab-autodoist')

        from autodoist import get_attr_name, get_attr_id

        # Test with dict format
        dict_label = {'id': '123', 'name': 'test_label'}
        assert get_attr_name(dict_label) == 'test_label'
        assert get_attr_id(dict_label) == '123'

        # Test with object format (mock)
        class MockLabel:
            def __init__(self):
                self.id = '456'
                self.name = 'mock_label'

        obj_label = MockLabel()
        assert get_attr_name(obj_label) == 'mock_label'
        assert get_attr_id(obj_label) == '456'

        print("\nHelper functions work for both formats!")

    def test_flatten_paginator(self):
        """Test the flatten_paginator helper."""
        import sys
        sys.path.insert(0, '/Users/erauner/git/side/homelab-autodoist')

        from autodoist import flatten_paginator

        # Test with already flat list
        flat_list = [1, 2, 3]
        result = flatten_paginator(flat_list)
        assert result == [1, 2, 3], "Should handle flat list"

        # Test with paginated list (list of lists)
        paginated = [[1, 2], [3, 4], [5]]
        result = flatten_paginator(paginated)
        assert result == [1, 2, 3, 4, 5], "Should flatten paginated results"

        print("\nFlatten paginator works!")

    def test_verify_label_existance(self):
        """Test verify_label_existance finds the next_action label."""
        import sys
        sys.path.insert(0, '/Users/erauner/git/side/homelab-autodoist')

        from todoist_api_python.api import TodoistAPI
        from autodoist import verify_label_existance

        # Create a mock args object
        class MockArgs:
            pass

        api = TodoistAPI(token=API_TOKEN)
        labels = verify_label_existance(api, 'next_action', 2)

        assert labels is not None, "Should return labels"
        assert len(labels) > 0, "Should have labels"

        print(f"\nFound {len(labels)} labels")
        print("verify_label_existance works!")

    def test_autodoist_magic_data_fetch(self):
        """Test that autodoist_magic can fetch data correctly."""
        import sys
        sys.path.insert(0, '/Users/erauner/git/side/homelab-autodoist')

        from todoist_api_python.api import TodoistAPI
        from autodoist import flatten_paginator

        api = TodoistAPI(token=API_TOKEN)

        # Test flattening projects
        projects = flatten_paginator(api.get_projects())
        assert isinstance(projects, list), "Projects should be a list"
        assert len(projects) > 0, "Should have projects"
        assert hasattr(projects[0], 'name'), "Project should have name"

        # Test flattening sections
        sections = flatten_paginator(api.get_sections())
        assert isinstance(sections, list), "Sections should be a list"

        # Test flattening tasks
        tasks = flatten_paginator(api.get_tasks())
        assert isinstance(tasks, list), "Tasks should be a list"

        print(f"\nProjects: {len(projects)}")
        print(f"Sections: {len(sections)}")
        print(f"Tasks: {len(tasks)}")
        print("Data fetching works!")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
