import requests
import re
from bot.utils import logger

baseUrl = "https://api.bybitcoinsweeper.com/api"

def get_main_js_format(base_url):
    try:
        response = requests.get(base_url)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        content = response.text
        matches = re.findall(r'src="(/.*?/index.*?\.js)"', content)
        if matches:
            # Return all matches, sorted by length (assuming longer is more specific)
            return sorted(set(matches), key=len, reverse=True)
        else:
            return None
    except requests.RequestException as e:
        logger.warning(f"Error fetching the base URL: {e}")
        return None

def get_base_api(url):
    try:
        logger.info("Checking for changes in api...")
        response = requests.get(url)
        response.raise_for_status()
        content = response.text
        match = re.search(r'baseURL:\s*"(.*?)"', content)

        if match:
            # print(match.group(1))
            return match.group(1)
        else:
            logger.info("Could not find 'baseUrl' in the content.")
            return None
    except requests.RequestException as e:
        logger.warning(f"Error fetching the JS file: {e}")
        return None


def check_base_url():
    base_url = "https://bybitcoinsweeper.com/"
    main_js_formats = get_main_js_format(base_url)

    if main_js_formats:
        for format in main_js_formats:
            logger.info(f"Trying format: {format}")
            full_url = f"https://bybitcoinsweeper.com{format}"
            result = get_base_api(full_url)
            # print(f"{result} | {baseUrl}")
            if str(result) == baseUrl:
                logger.success("<green>No change in api!</green>")
                return True
            return False
        else:
            logger.warning("Could not find 'baseURL' in any of the JS files.")
            return False
    else:
        logger.info("Could not find any main.js format. Dumping page content for inspection:")
        try:
            response = requests.get(base_url)
            print(response.text[:1000])  # Print first 1000 characters of the page
            return False
        except requests.RequestException as e:
            logger.warning(f"Error fetching the base URL for content dump: {e}")
            return False
