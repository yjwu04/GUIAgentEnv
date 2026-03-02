import argparse
import asyncio
import os

from app.agent.manus import Manus
from app.logger import logger

from record import output_record

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run Manus agent with a prompt")
    parser.add_argument(
        "--prompt", type=str, required=False, help="Input prompt for the agent"
    )
    args = parser.parse_args()

    # Create and initialize Manus agent
    agent = await Manus.create()
    try:
        # Use command line prompt if provided, otherwise ask for input
        prompt = args.prompt if args.prompt else input("Enter your prompt: ")
        if not prompt.strip():
            logger.warning("Empty prompt provided.")
            return

        logger.warning("Processing your request...")
        await agent.run(prompt)
        logger.info("Request processing completed.")
    except KeyboardInterrupt:
        logger.warning("Operation interrupted.")
    finally:
        # Ensure agent resources are cleaned up before exiting
        await agent.cleanup()

async def run(prompt):
    # Create and initialize Manus agent
    agent = await Manus.create()
    try:
        if not prompt.strip():
            logger.warning("Empty prompt provided.")
            return

        logger.warning("Processing your request...")
        await agent.run(prompt)
        logger.info("Request processing completed.")
    except KeyboardInterrupt:
        logger.warning("Operation interrupted.")
    finally:
        # Ensure agent resources are cleaned up before exiting
        await agent.cleanup()

def get_prompt(filename):
    if filename == "Baidu.html":
        return "Task: Summarize the first search result on {}, no need to click links for retrieving details. Record: how many steps you took. Important: you are only allowed to interact inside the given website"
    if filename == "Google.html":
        return "Task: Summarize the first search results on {}, no need to click links for retrieving details. Record: how many steps you took Important: you are only allowed to interact inside the given website"
    if filename == "Yandex.html":
        return "Task: Summarize the first search results on {}, no need to click links for retrieving details, ignore the popups. Record: how many steps you took. Important: you are only allowed to interact inside the given website"
    if filename == "Wikipedia.html":
        return "Task: Summarize the abstract part on {}, no need to click links for retrieving details. Record: how many steps you took. Important: you are only allowed to interact inside the given website"
    if filename == "Trending - YouTube (2025_7_19 23：07：39).html":
        return "Task: find a video about WWE on {}. Record: how many steps you took. Important: you are only allowed to interact inside the given website, and do not use the search bar/box in the given website"
    if filename == "哔哩哔哩 (゜-゜)つロ 干杯～-bilibili (2025_7_19 23：07：14).html":
        return  "Task: find a video about NBA on website: {}. Record: how many steps you took. Important: you are only allowed to interact inside the given website, and do not use the search bar/box in the given website"
    if filename == "CNN.html":
        return "Task: Get the title of the first post on {}. Record: how many steps you took. Important: you are only allowed to interact inside the given website, and do not use the search bar/box in the given website"
    if filename == "The New York Times - Breaking News, US News, World News and Videos (2025_7_19 21：39：00).html":
        return "Task: Show the title of the first news on {}. Important: you are only allowed to interact inside the given website, and do not use the search bar/box in the given website"
    if filename == "Google News (2025_7_19 21：39：50).html":
        return "Task: Show the title of the first news in top stories on {} with the article name, author and time. Important: you are only allowed to interact inside the given website, and do not use the search bar/box in the given website"
    if filename == "BBC.html":
        return "Task: Summarize the first few paragraghs of the article on {}. Important: you are only allowed to interact inside the given website, and do not use the search bar/box in the given website"
    if filename == "Temu Canada ｜ Explore the Latest Clothing, Beauty, Home, Jewelry & More (2025_7_19 21：40：56).html":
        return "Task: Without using the searchbar, order a charger on {}. Important: you are only allowed to interact inside the given website, and do not use the search bar/box in the given website"
    if filename == "Electronics, Cars, Fashion, Collectibles & More ｜ eBay (2025_7_19 21：40：09).html":
        return "Task: Without using the searchbar, order a building toy on {}. Important: you are only allowed to interact inside the given website, and do not use the search bar/box in the given website"
    if filename == "Amazon.html":
        return "Task: Without using the searchbar, order a floral dress on {}. Important: you are only allowed to interact inside the given website, and do not use the search bar/box in the given website"
    if filename == "GoogleFormPre.html":
        return "Task: Fill the form for me with name: alan, email: 1231231@gmail.com, and address: main street, shatin on {}. Important: you are only allowed to interact inside the given website, and do not use the search bar/box in the given website"
    if filename == "VSCodeDownload.html":
        return "Task: Help me download VSCode on {}. Important: you are only allowed to interact inside the given website, and do not use the search bar/box in the given website"
    if filename == "MovieDownloadChinese.html":
        return "Task: Please download the HD Cantonese subtitled version of In Broad Daylight on {} to Xunlei Cloud Drive for me. Important: you are only allowed to interact inside the given website, and do not use the search bar/box in the given website"
    if filename == "吹水台 - 香港高登討論區 (2025_7_19 21：42：58).html":
        return "Task: List one title of a post about football on {}. Important: you are only allowed to interact inside the given website, and do not use the search bar/box in the given website"
    return None

if __name__ == "__main__":
    # asyncio.run(main())

    root_dir = "C:/Users/20145/Desktop/1"
    workspace_dir ="C:/Users/20145/Desktop/2"

    for category in os.listdir(root_dir):
            category_path = os.path.join(root_dir, category)
            if os.path.isdir(category_path):
                for filename in os.listdir(category_path):
                    file_path = os.path.join(category_path, filename)
                    if os.path.isfile(file_path):
                        prompt = get_prompt(filename)
                        if prompt is None:
                            continue
                        url = f"http://localhost:8000/1/{category}/{filename}"
                        prompt = prompt.format(f"website \"{url}\"")
                        print(prompt)
                        asyncio.run(run(prompt))
                        save_path = os.path.join(workspace_dir, f"{category}_{filename}.txt")
                        with open(save_path, "w", encoding="utf-8") as f:
                            for msg in output_record.messages:
                                f.write(str(msg) + "\n")
                                # f.write(prompt + '\n')
                        output_record.clear()
