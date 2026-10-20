from urllib.parse import urlsplit, parse_qs
from auth import authenticate
from documents import DOCUMENTS, can_read

KEYWORDS = {
    "hr-leave": ["วันลา", "พักร้อน", "leave"],
    "finance-budget": ["งบ", "budget", "finance", "โครงการ"]
}


def search_documents(identity, question):
    # Filter permissions BEFORE matching or ranking documents.
    allowed = [
        document
        for document in DOCUMENTS.values()
        if can_read(identity, document)
    ]

    query = question.casefold()
    matches = []

    for document in allowed:
        score = sum(
            word in query
            for word in KEYWORDS.get(document["id"], [])
        )
        if score > 0:
            matches.append((score, document))

    matches.sort(key=lambda item: (-item[0], item[1]["id"]))
    return [document for score, document in matches[:2]]


def handle_search(path, authorization):
    identity = authenticate(authorization)
    if identity is None:
        return 401, {"error": "invalid_or_missing_api_key"}

    params = parse_qs(urlsplit(path).query)
    question = params.get("q", [""])[0].strip()
    if not question or len(question) > 1000:
        return 400, {"error": "q_must_be_1_to_1000_characters"}

    results = search_documents(identity, question)
    return 200, {
        "identity": identity,
        "results": results,
        "count": len(results)
    }
