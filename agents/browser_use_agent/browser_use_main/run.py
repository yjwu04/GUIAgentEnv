from browser_use.llm import ChatDeepSeek
from browser_use import Agent
import asyncio

async def main():
    agent = Agent(
        task="Find the number of stars of the browser-use repo",
        llm=ChatDeepSeek(model="deepseek-chat"),
    )
    await agent.run(max_steps = 10)

asyncio.run(main())