import ast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from analysis import analyze_tree, syntax_issue

app = FastAPI(title="AI Code Reviewer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174"
],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalysisRequest(BaseModel):
    code: str
    language: str = "Python"


SEVERITY_DEDUCTIONS = {"High": 25, "Medium": 15, "Low": 5}


@app.get("/")
def home():
    return {"message": "AI Code Reviewer Backend is Running!"}


@app.post("/analyze")
def analyze_code(request: AnalysisRequest):
    code = request.code
    if not code.strip():
        return {
            "issues": [],
            "score": 0,
            "error": "Please enter some code before running an analysis.",
        }

    if request.language.strip().lower() not in {"python", "py"}:
        return {
            "issues": [],
            "score": 0,
            "error": "AST analysis currently supports Python only.",
        }

    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        issue = syntax_issue(error)
        return {
            "issues": [issue],
            "score": 0,
            "error": issue["description"],
        }

    issues = analyze_tree(tree)
    score = max(
        0,
        100
        - sum(
            SEVERITY_DEDUCTIONS.get(str(issue["severity"]), 0)
            for issue in issues
        ),
    )

    return {
        "issues": issues,
        "score": score,
        "error": "",
    }