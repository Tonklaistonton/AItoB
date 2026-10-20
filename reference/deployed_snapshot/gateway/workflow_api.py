from summarizer import summarize_report
import csv
from workflow import clean_expenses


def run_expenses(identity):
    if (
        identity.get("team") != "Finance"
        or identity.get("role") != "finance_reader"
    ):
        return 403, {"error": "finance_workflow_access_denied"}

    try:
        report = clean_expenses(identity)
    except FileNotFoundError:
        return 500, {"error": "workflow_input_file_missing"}
    except (OSError, ValueError, csv.Error):
        return 500, {"error": "workflow_file_or_format_error"}

    return 200, {
        "workflow": "finance_expenses_cleaning",
        "identity": identity,
        "report": report,
        "ollama_called": False
    }


def run_expenses_with_summary(identity, model, ollama_url):
    status, result = run_expenses(identity)
    if status != 200:
        return status, result

    summary = summarize_report(result["report"], model, ollama_url)
    result["summary"] = summary
    result["ollama_called"] = True
    return 200, result
