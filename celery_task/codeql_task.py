from celery import Celery
import requests
import os
from .codeql_lib import create_database_folder, create_results_folder, create_database, analyze_database, merge_results

celery_app = Celery(
    "celery_codeql",
    broker="redis://127.0.0.1:6379/0",
    backend="redis://127.0.0.1:6379/0",
    broker_connection_retry_on_startup=True
)

@celery_app.task()
def celery_codeql_task(data):
    if not data or not isinstance(data, dict) or "path" not in data or "report_id" not in data:
        print("Sent data is invalid: ", data)
        return

    path_to_source = data["path"]
    report_id = data["report_id"]

    if not os.path.exists(path_to_source) or not os.path.isdir(path_to_source):
        print("Invalid folder path: " + path_to_source)
        return

    database_folder = create_database_folder(path_to_source)
    print("Database folder created at:", database_folder)

    database_path = create_database("database", database_folder, path_to_source)
    if database_path:
        print(f"Database created at: {database_path}")
    else:
        print(f"Failed to create database")

    # for file in os.listdir(path_to_source):
    #     if file.endswith(".py"):
    #         file_path = os.path.join(path_to_source, file)
    #         database_path = create_database(file_path, database_folder, path_to_source)
    #         if database_path:
    #             print(f"Database created at: {database_path}")
    #         else:
    #             print(f"Failed to create database for {file_path}")

    results_folder = create_results_folder(path_to_source)
    print("Results folder created at:", results_folder)

    for file in os.listdir(database_folder):
        if file.endswith(".ql"):
            print("Analyzing database:", file)
            analyze_database(database_folder, results_folder, file)
            print("Analysis completed.")

    merge_results(results_folder)
    print("Results merged into a single file: codeql.csv")

    login_response = requests.post(
        "http://127.0.0.1:3000/auth/login",
        {
            "email": "phammanhhung1@gmail.com",
            "password": "PhamHung"
        }
    )

    if login_response.status_code != 202:
        print("Cannot login to Rails")
        return

    login_response_json = login_response.json()
    token = login_response_json['token']

    collect_codeql_response = requests.post(
        f"http://127.0.0.1:3000/reports/{report_id}/codeql",
        {
            "status": True,
            "result_dir": results_folder
        },
        headers={
            'Authorization': f'Bearer {token}'
        }
    )

    if collect_codeql_response.status_code != 200:
        print("Cannot push codeql result files to Rails. Response: ", collect_codeql_response.status_code, collect_codeql_response.text)
        return

    print("Success")
