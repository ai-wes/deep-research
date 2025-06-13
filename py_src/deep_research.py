from __future__ import annotations
import os
import time
from dataclasses import dataclass
from typing import Callable, List, Optional
import requests
import openai

from .text_splitter import RecursiveCharacterTextSplitter

openai.api_key = os.getenv("OPENAI_KEY")

@dataclass
class SearchResult:
    url: str
    markdown: str

@dataclass
class SerpQuery:
    query: str
    research_goal: str

@dataclass
class ResearchProgress:
    current_depth: int
    total_depth: int
    current_breadth: int
    total_breadth: int
    current_query: Optional[str]
    total_queries: int
    completed_queries: int

@dataclass
class ResearchResult:
    learnings: List[str]
    visited_urls: List[str]

class FirecrawlClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key
        self.base_url = base_url or "https://api.firecrawl.com"

    def search(self, query: str, limit: int = 5) -> List[SearchResult]:
        # This is a very small stub demonstrating what a request might look like.
        # You may need to adjust the endpoint and parameters for real usage.
        if not self.api_key:
            raise RuntimeError("FIRECRAWL_KEY is required to perform searches")
        url = f"{self.base_url}/search"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        resp = requests.get(url, params={"q": query, "limit": limit}, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        results = []
        for item in data:
            results.append(SearchResult(url=item.get("url", ""), markdown=item.get("markdown", "")))
        return results

_firecrawl_client: Optional[FirecrawlClient] = None


def get_firecrawl_client() -> FirecrawlClient:
    global _firecrawl_client
    if _firecrawl_client is None:
        _firecrawl_client = FirecrawlClient(
            api_key=os.getenv("FIRECRAWL_KEY"),
            base_url=os.getenv("FIRECRAWL_BASE_URL"),
        )
    return _firecrawl_client


def generate_serp_queries(query: str, num_queries: int = 3, learnings: Optional[List[str]] = None) -> List[SerpQuery]:
    prompt = f"Generate up to {num_queries} SERP queries to research the topic."
    if learnings:
        prompt += " Use previous learnings: " + "\n".join(learnings)
    prompt += f"\nTopic: {query}"
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    text = completion["choices"][0]["message"]["content"]
    queries = []
    for line in text.splitlines():
        if line.strip():
            queries.append(SerpQuery(query=line.strip(), research_goal=line.strip()))
    return queries[:num_queries]


def process_serp_result(query: str, result: List[SearchResult], num_learnings: int = 3, num_follow_up_questions: int = 3):
    contents = [r.markdown for r in result if r.markdown]
    text = "\n".join(contents)
    prompt = (
        f"Using the following SERP results for '{query}', generate up to {num_learnings} learnings and {num_follow_up_questions} follow-up questions.\n{text}"
    )
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    output = completion["choices"][0]["message"]["content"]
    learnings = []
    follow_ups = []
    for line in output.splitlines():
        if line.startswith("-"):
            learnings.append(line.lstrip("- "))
        elif line.strip():
            follow_ups.append(line.strip())
    return learnings[:num_learnings], follow_ups[:num_follow_up_questions]


def write_final_report(prompt: str, learnings: List[str], visited_urls: List[str]) -> str:
    joined = "\n".join(f"- {l}" for l in learnings)
    url_section = "\n".join(f"- {u}" for u in visited_urls)
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": f"Write a detailed report on: {prompt}\nLearnings:\n{joined}"}],
        temperature=0.2,
    )
    report = completion["choices"][0]["message"]["content"]
    return report + f"\n\n## Sources\n{url_section}"


def write_final_answer(prompt: str, learnings: List[str]) -> str:
    joined = "\n".join(learnings)
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": f"{prompt}\nUse these learnings:\n{joined}"}],
        temperature=0.2,
    )
    return completion["choices"][0]["message"]["content"].strip()


def deep_research(
    query: str,
    breadth: int,
    depth: int,
    learnings: Optional[List[str]] | None = None,
    visited_urls: Optional[List[str]] | None = None,
    on_progress: Optional[Callable[[ResearchProgress], None]] = None,
) -> ResearchResult:
    learnings = learnings or []
    visited_urls = visited_urls or []
    progress = ResearchProgress(
        current_depth=depth,
        total_depth=depth,
        current_breadth=breadth,
        total_breadth=breadth,
        current_query=None,
        total_queries=0,
        completed_queries=0,
    )

    def report(update: dict):
        for k, v in update.items():
            setattr(progress, k, v)
        if on_progress:
            on_progress(progress)

    serp_queries = generate_serp_queries(query, num_queries=breadth, learnings=learnings)
    report({"total_queries": len(serp_queries), "current_query": serp_queries[0].query if serp_queries else None})

    results: List[ResearchResult] = []
    client = get_firecrawl_client()
    for q in serp_queries:
        try:
            res = client.search(q.query, limit=5)
        except Exception as e:
            print(f"Error searching {q.query}: {e}")
            continue
        urls = [r.url for r in res if r.url]
        new_learnings, follow_ups = process_serp_result(q.query, res, num_follow_up_questions=max(1, breadth//2))
        all_learnings = learnings + new_learnings
        all_urls = visited_urls + urls
        new_depth = depth - 1
        new_breadth = max(1, breadth // 2)
        if new_depth > 0:
            next_query = f"{q.research_goal}\nFollow ups: {' '.join(follow_ups)}"
            sub_result = deep_research(
                query=next_query,
                breadth=new_breadth,
                depth=new_depth,
                learnings=all_learnings,
                visited_urls=all_urls,
                on_progress=on_progress,
            )
            results.append(sub_result)
        else:
            results.append(ResearchResult(learnings=all_learnings, visited_urls=all_urls))
        report({"completed_queries": progress.completed_queries + 1})
    merged = ResearchResult(learnings=[], visited_urls=[])
    for r in results:
        merged.learnings.extend(r.learnings)
        merged.visited_urls.extend(r.visited_urls)
    merged.learnings = list(dict.fromkeys(merged.learnings))
    merged.visited_urls = list(dict.fromkeys(merged.visited_urls))
    return merged

