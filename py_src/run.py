import asyncio
from .deep_research import deep_research, write_final_answer, write_final_report

async def async_input(prompt: str) -> str:
    return input(prompt)

async def main():
    query = await async_input("What would you like to research? ")
    breadth = int(await async_input("Enter research breadth (default 4): ") or 4)
    depth = int(await async_input("Enter research depth (default 2): ") or 2)
    mode = await async_input("Generate report or answer? (report/answer, default report): ")
    is_report = mode.strip().lower() != "answer"

    result = deep_research(query=query, breadth=breadth, depth=depth)

    if is_report:
        report = write_final_report(prompt=query, learnings=result.learnings, visited_urls=result.visited_urls)
        with open("report.md", "w", encoding="utf-8") as f:
            f.write(report)
        print(report)
        print("Saved report.md")
    else:
        answer = write_final_answer(prompt=query, learnings=result.learnings)
        with open("answer.md", "w", encoding="utf-8") as f:
            f.write(answer)
        print(answer)
        print("Saved answer.md")

if __name__ == "__main__":
    asyncio.run(main())
