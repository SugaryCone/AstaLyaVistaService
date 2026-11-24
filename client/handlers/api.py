from loguru import logger
from os import getenv
from typing import Any
import requests
from requests.exceptions import RequestException

API_URL = getenv("CLIENT_API_URL")

class APIError(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code

def get_tasks() -> Any:
    url = API_URL + "/tasks"
    try:
        response = requests.get(url)
        if not response.ok:
            raise APIError(message=response.json()["detail"], status_code=response.status_code)
        return response.json()
    except RequestException as exc:
        logger.error(f"{url} - Cannot perform request")
        raise exc

def get_task(task_id: str) -> Any:
    logger.info(f"Trying to concatenate: {task_id}")
    url = API_URL + "/tasks" + "/" + task_id
    try:
        response = requests.get(url)
        if not response.ok:
            raise APIError(message=response.json()["detail"], status_code=response.status_code)
        return response.json()
    except RequestException as exc:
        logger.error(f"{url} - Cannot perform request")
        raise exc

def get_linked_tasks(task: dict) -> list:
    try:
        linked_tasks = []
        for task_id in task["linked_task_ids"]:
            linked_tasks.append(get_task(task_id))
        return linked_tasks
    except (APIError, RequestException):
        raise

def get_search_employee(employee_id: str) -> dict:
    url = API_URL + "/employees"
    try:
        response = requests.get(url)
        if not response.ok:
            raise APIError(message=response.json()["detail"], status_code=response.status_code)
        for employee in response.json():
            if employee["id"] == employee_id:
                return employee
        raise APIError(message=f"Employee id={employee_id} not found", status_code=404)
    except RequestException as exc:
        logger.error(f"{url} - Cannot perform request")
        raise exc

def get_search_project(project_id: str) -> dict:
    url = API_URL + "/projects"
    try:
        response = requests.get(url)
        if not response.ok:
            raise APIError(message=response.json()["detail"], status_code=response.status_code)
        for project in response.json():
            if project["id"] == project_id:
                return project
        raise APIError(message=f"Project id={employee_id} not found", status_code=404)
    except RequestException as exc:
        logger.error(f"{url} - Cannot perform request")
        raise exc