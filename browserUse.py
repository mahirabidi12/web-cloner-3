from browser_use import Agent, ChatGoogle
from dotenv import load_dotenv
import asyncio

load_dotenv()

async def main():
    llm = ChatGoogle(model="gemini-flash-latest") 
    task = "go to https://www.psyplex.site/ and save a screenshot to screenshot.png"
    agent = Agent(task=task, llm=llm)
    result = await agent.run()
    print(f"\n📸 Result: {result}")

if __name__ == "__main__":
    asyncio.run(main())