from selenium import webdriver
import sys
import os
import argparse
from argparse import RawTextHelpFormatter
import datetime
import time
import re
import csv
import math
from tqdm import tqdm
from urllib.parse import urlparse, urlunparse
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, NoSuchWindowException, WebDriverException

# output styling
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# start for time tracking
START=datetime.datetime.now()
print(f"{bcolors.OKGREEN}[Start]{bcolors.ENDC} time: {START}")

# configuration options inside of code:
DEFAULT_QUERY="email"



# init functions
WEBSITE = f"https://play.google.com/store/search?q={DEFAULT_QUERY}&c=apps&hl=de&gl=US"
def init_arg_parse():
    parser = argparse.ArgumentParser(description='This tool is designed to scrape the PlayStore for apps.\
It works in 3 stages:\n1) Aquiring the list of apps to scrub through\n2) Going through that list and get the data\n\
3) Write the data to a csv file (extension name may be custom)', \
                epilog="Examples:\n" + f"python {os.path.basename(__file__)} <FULL_URL>\npython {os.path.basename(__file__)} -q <CUSTOM_QUERY> -o ./path/to/folderXYZ/ -d ./chromedriver/chromedriver.exe",
                formatter_class=RawTextHelpFormatter)
    url_group = parser.add_mutually_exclusive_group()
    url_group.add_argument(
        "URL", help="Supply the full URL containing queries to specify what to look for.", nargs='?', type=str, default=WEBSITE)
    url_group.add_argument(
        "-q", "--query", help="Supply a query to look for which is the same value which that can be looked for in the apps section on the webpage of the PlayStore.", nargs='?', type=str, default=DEFAULT_QUERY)
    parser.add_argument("--scroll", help="Define how long to wait (in sec.) during scroll down on query result page." + \
        " If no dynamically loaded this can be set to 0.", type=int, default=1)
    parser.add_argument("--quantity", help="Set the max amount of apps to scrub (in order proposed by the play store). Default is get all available apps (=-1)", type=int, default=-1)
    parser.add_argument("-d", "--web-driver", help="Set the location of the web-driver. Default assumes, that it is within the same dir as the script.",
                        type=str, default=f"{os.path.join(os.path.dirname(__file__), 'chromedriver.exe')}")
    parser.add_argument("-o", "--output", \
            help="Output result to file in specified location.\
If no location is specified it'll be saved to this directory under name apps_details.csv (.csv, .txt supported)",\
            type=str, default=f"./apps_details.csv")
    return parser


def init_chrome_driver(path):
    """ Set up chrome driver """
    if os.path.isdir(path):
        print(f"Provided path is a directory. Attempting to find 'chromedriver.exe' within {bcolors.OKBLUE}{bcolors.UNDERLINE}{path}{bcolors.ENDC}.")
        path = os.path.join(path, "chromedriver.exe")
    if os.path.isfile(path):
        print(f"{bcolors.OKGREEN}Located web-driver at {bcolors.OKBLUE}{bcolors.UNDERLINE}{path}{bcolors.ENDC}.")
        driver = webdriver.Chrome(path)
        return driver
    else:
        print(f"{bcolors.FAIL}The webdriver could not properly be loaded. Is it really at this location? {bcolors.OKBLUE}{bcolors.UNDERLINE}{path}{bcolors.ENDC}.")
        return None

# TODO offer firefox driver as well
def init_firefox_driver():
    pass

def scroll_down(driver, pause):
    # try scrolling all the way down
    SCROLL_PAUSE_TIME = pause
    # Get scroll height
    last_height = driver.execute_script("return document.body.scrollHeight")
    print("Scrolling to bottom and loading new content")
    while True:
        # Scroll down to bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        # Wait to load new page content (f.e. endless feed like twitter, fb, etc.)
        time.sleep(SCROLL_PAUSE_TIME)
        # Calculate new scroll height and compare with last scroll height
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

def get_apps_as_urls(driver, quantity, scroll):
    urls = []
    try:
        # wait for relevant content to be loaded
        firstLoadedApp = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".Q9MA7b"))
        )
        # scroll down to ensure all dynamically loaded content is there
        scroll_down(driver, scroll)
        all_loaded_apps_links = driver.find_elements_by_css_selector(".Q9MA7b")
        print(f"{bcolors.OKGREEN}Loaded {len(all_loaded_apps_links)} urls{bcolors.ENDC}")
        for index , link in enumerate(all_loaded_apps_links):
            # check if amount of loaded apps is equal to amount asked for
            if index == quantity and quantity != -1:
                print(f"{bcolors.OKGREEN}Done getting the first {quantity} urls.{bcolors.ENDC}")
                break
            url = link.find_element_by_css_selector("a")
            urls.append(url.get_attribute("href"))
    except TypeError:
        print(f"{bcolors.FAIL}This TypeError occured:{bcolors.ENDC} {TypeError}")
    except (NoSuchWindowException, WebDriverException):
        print(f"{bcolors.FAIL}It seems that the window was closed...{bcolors.ENDC}")
    except:
        print(f"{bcolors.FAIL}error:{bcolors.ENDC} {sys.exc_info()[0]}")
    return urls

def get_data_from_individual_apps(driver, apps_urls):
    apps_data = []
    # for count in tqdm(range(8), unit="pages", desc="Looking through pages...", position=0, leave=False):
    for app in tqdm(apps_urls, unit="pages", desc="Looking through Apps", position=0, leave=False):
        try:
            driver.get(app)
            app_name = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, ".AHFaub"))
            )
        except (NoSuchWindowException, WebDriverException) as error:
            print(f"{error}\n{bcolors.FAIL}It seems that the window was closed...{bcolors.ENDC}")
            
        # get info from the additional info section
        try:
            additional_info = driver.find_element_by_css_selector(".IxB2fe")
            last_update = additional_info.find_element_by_css_selector("div:nth-child(1)>span").text
            size = additional_info.find_element_by_css_selector("div:nth-child(2)>span").text
            downloads = int(additional_info.find_element_by_css_selector("div:nth-child(3)>span").text.replace(",", "").replace("+", ""))
            current_version = additional_info.find_element_by_css_selector("div:nth-child(4)>span").text
            necessary_Android_version = additional_info.find_element_by_css_selector("div:nth-child(5)>span").text
            age_requirements = additional_info.find_element_by_css_selector("div:nth-child(6)>span .htlgb>div:nth-child(1)").text
        except ValueError:
            tqdm.write(f"{bcolors.FAIL}There is a value error. This probably means a value was assigned to the wrong field: {bcolors.ENDC} {bcolors.OKBLUE}{bcolors.UNDERLINE}{app}{bcolors.ENDC}, {app_name.text}")
        except NoSuchElementException:
            tqdm.write(f"{bcolors.FAIL}Some element is missing. Consider rechecking in the file later (is marked with CHECK AGAIN):{bcolors.ENDC} {bcolors.OKBLUE}{bcolors.UNDERLINE}{app}{bcolors.ENDC}, {app_name.text}")
            age_requirements = "PLEASE CHECK AGAIN"

        # get info from the ratings short description
        try:
            amount_ratings_shortDescription = int(driver.find_element_by_css_selector("span.AYi5wd").text.replace(",", ""))
            rsd = driver.find_element_by_css_selector(".pf5lIe>div")
            rating_shortDescription = float(re.findall(r"[-+]?\d*\.\d+|\d+", rsd.get_attribute("aria-label").replace(",", "."))[0])
        except NoSuchWindowException:
            print(f"{bcolors.FAIL}It seems that the window was closed...")
        except NoSuchElementException:
            tqdm.write(f"{bcolors.WARNING}Missing rating:{bcolors.ENDC} {bcolors.OKBLUE}{bcolors.UNDERLINE}{app}{bcolors.ENDC}, {app_name.text}")
            rating_shortDescription = 0
            amount_ratings_shortDescription = 0

        app_data ={
                "app_name" : app_name.text,
                "app_rating" : rating_shortDescription,
                "app_amount_ratings" : amount_ratings_shortDescription,
                "app_amount_downloads" : downloads,
                "app_url" : app,
                "size" : size,
                "last_update" : last_update,
                "current_version" : current_version,
                "necessary_android_version" : necessary_Android_version,
                "age_requirements" : age_requirements,
        }
        apps_data.append(app_data)
    driver.quit()
    return apps_data

def write_to_csv_file(filename, data_to_write):
    if len(data_to_write) == 0:
        print(f"{bcolors.WARNING}Nothing to write to file, no data scraped.{bcolors.ENDC}")
        return
    csv_columns = []
    for key, value in data_to_write[0].items():
        csv_columns.append(key)

    print(f"Writing results to {filename}...")
    # writing to csv file
    with open(filename, 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=csv_columns)
        writer.writeheader()
        for data in data_to_write:
            writer.writerow(data)

def evaluate_target_apps_from_args(url_argument, query_argument):
    match = re.findall(r"^([^&]*).*", urlparse(url_argument).query)[0][2:]
    if match != DEFAULT_QUERY:
        return url_argument
    if query_argument != DEFAULT_QUERY:
        # getting structure of website and parsing it into tuple
        parsed_url = urlparse(WEBSITE)
        # changing the query to be the new one from the user input & setting it in tuple
        new_long_query = parsed_url.query.replace(DEFAULT_QUERY, query_argument)
        new_parsed = parsed_url._replace(query=new_long_query)
        # making url out of tuple
        url = urlunparse(new_parsed)
        print(f"Custom query is: {bcolors.OKCYAN}{query_argument}{bcolors.ENDC}")
        return url
    return WEBSITE

class WebDriverNotFound(Exception):
    """Error raised if web-driver cannot properly be loaded"""
    pass

def Main():
    parser = init_arg_parse()
    args = parser.parse_args()
    try:
        driver = init_chrome_driver(args.web_driver)
        if driver is None:
            raise WebDriverNotFound
    except WebDriverNotFound:
        print(f"{bcolors.FAIL}exception.WebDriverNotFound raised. Exiting program.{bcolors.ENDC}")
        return

    specific_target = evaluate_target_apps_from_args(args.URL, args.query)
    print(f"Looking through '{bcolors.OKBLUE}{specific_target}{bcolors.ENDC}'")
    if os.path.isfile(args.output):
       print(f"{bcolors.WARNING}Watch out, the file already exists. Will be overwritten at the end!{bcolors.ENDC}")
    
    print(f"\n{bcolors.HEADER}[Step 1] {bcolors.UNDERLINE}Accumulating all URLs of Apps to scrub through{bcolors.ENDC}\n")
    driver.get(specific_target)
    urls = get_apps_as_urls(driver, args.quantity, args.scroll)
    print(f"\n{bcolors.HEADER}[Step 2] {bcolors.UNDERLINE}Looking through individual URLs and getting App Data{bcolors.ENDC}\n")
    apps_data = get_data_from_individual_apps(driver, urls)
    
    print(f"\n{bcolors.HEADER}[Step 3] {bcolors.UNDERLINE}Writing results to file{bcolors.ENDC}\n")
    write_to_csv_file(args.output, apps_data)



if __name__ == "__main__":
    try:
        Main()
    except KeyboardInterrupt:
        print(f"\n{bcolors.FAIL}[ABORTED] Rage quit...{bcolors.ENDC}\n")


END=datetime.datetime.now()
PROGRAM_TIME=(END-START).total_seconds()

all_seconds = math.floor(PROGRAM_TIME)
minutes = math.floor(all_seconds / 60)
hours = math.floor(minutes / 60)

seconds = all_seconds % 60
print(f"{bcolors.OKGREEN}[Done]{bcolors.ENDC} Duration: {hours}:{minutes}:{seconds}(h:m:s); {all_seconds}(s);")