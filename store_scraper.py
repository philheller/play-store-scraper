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
    parser.add_argument('-p', "--performance", help="Use a more performant process by leveraging beautifulsoup4.\nNeeded modules: requests, beautifulsoup4, lxml (can be installed via pip).\n" + 
                        "Ratings and amount of ratings may suffer in recognition since it is loaded dynamically.", action="store_true")
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

def get_data_from_individual_apps_beautifulsoup(apps_urls):
    # import additional modules to make bs4 work
    from bs4 import BeautifulSoup
    import requests
    import traceback
    
    apps_data = []
    
    for app_url in tqdm(apps_urls, unit="pages", desc="Looking through Apps"):
        response = requests.get(app_url).text
        soup = BeautifulSoup(response, 'lxml')
        
        # extract as much as possible from header
        try:
            app_header = soup.find('div', class_="sIskre")
            app_name = app_header.find("h1", class_="AHFaub").text
            app_age_requirements = app_header.find("div", class_="KmO8jd").text
            app_producer = app_header.find("span", class_="T32cc").text
            app_genre = app_header.find("a", class_="R8zArc", itemprop="genre").text
        except TypeError as error:
            tqdm.write(f"{bcolors.FAIL}There is a TypeError in the header: {bcolors.OKBLUE}{bcolors.UNDERLINE}{app_url}{bcolors.ENDC}, {app_name}\n{error}\n{traceback.print_exc()}")
        except AttributeError as error:
            tqdm.write(f"{bcolors.FAIL}There is an AttributeError in the header: {bcolors.OKBLUE}{bcolors.UNDERLINE}{app_url}{bcolors.ENDC}, {app_name}\n{error}\n{traceback.print_exc()}")
        # separate ratings bc these are expected to be missing on some occassions.
        try:
            app_rating_div = app_header.find("div", class_="pf5lIe").div
            replaced_comma = app_rating_div["aria-label"].replace(",", ".")
            reg_res = re.findall(r"\d+\.?\d+", replaced_comma)
            app_rating = float(reg_res[0])
            app_amount_ratings = int(str(app_header.find("span", class_="AYi5wd").text).replace(".", "").replace(",", "")) 
        except TypeError as error:
            app_rating=0
            app_amount_ratings=0
            tqdm.write(f"{bcolors.WARNING}There is a TypeError in the header: {bcolors.OKBLUE}{bcolors.UNDERLINE}{app_url}{bcolors.ENDC}, {app_name}\n{error}\n{traceback.print_exc()}")
        except AttributeError as error:
            app_rating=0
            app_amount_ratings=0
            tqdm.write(f"{bcolors.WARNING}Attribute Error: Probably Missing Rating:{bcolors.ENDC} {bcolors.OKBLUE}{bcolors.UNDERLINE}{app_url}{bcolors.ENDC}, {app_name}")
        
        # extract rest from the additional information section
        try:
            additional_info = soup.find("div", class_="IxB2fe")
            app_last_update = additional_info.select("div:nth-child(1)>span")[0].text
            app_size = additional_info.select("div:nth-child(2)>span")[0].text
            app_downloads = int(additional_info.select("div:nth-child(3)>span")[0].text.replace(",", "").replace(".", "").replace("+", ""))
            app_current_version = additional_info.select("div:nth-child(4)>span")[0].text
            app_necessary_android_version = additional_info.select("div:nth-child(5)>span")[0].text
        except TypeError as error:
            tqdm.write(f"{bcolors.FAIL}There is a TypeError in the 'more info' section: {bcolors.OKBLUE}{bcolors.UNDERLINE}{app_url}{bcolors.ENDC}, {app_name}\n{error}\n{traceback.print_exc()}")
        except AttributeError as error:
            tqdm.write(f"{bcolors.FAIL}There is a AttributeError in the 'more info' section: {bcolors.OKBLUE}{bcolors.UNDERLINE}{app_url}{bcolors.ENDC}, {app_name}\n{error}\n{traceback.print_exc()}")
        except ValueError as error:
            tqdm.write(f"{bcolors.FAIL}There is a ValueError in the 'more info' section: {bcolors.OKBLUE}{bcolors.UNDERLINE}{app_url}{bcolors.ENDC}, {app_name}\n{error}\n{traceback.print_exc()}")
            app_downloads = 0
            app_current_version = "PLEASE CHECK AGAIN"
            app_necessary_android_version = "PLEASE CHECK AGAIN"

        app_data = produce_app_data_dict(app_name, app_rating, app_amount_ratings,
                                            app_downloads, app_url, app_size, app_last_update, 
                                            app_current_version, app_necessary_android_version, 
                                            app_age_requirements, app_producer, app_genre)
        apps_data.append(app_data)
    return apps_data

def get_data_from_individual_apps_selenium(driver, apps_urls):
    apps_data = []
    for app_url in tqdm(apps_urls, unit="pages", desc="Looking through Apps", position=0, leave=False):
        try:
            driver.get(app_url)
            app_name = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, ".AHFaub"))
            ).text
        except (NoSuchWindowException, WebDriverException) as error:
            print(f"{error}\n{bcolors.FAIL}It seems that the window was closed...{bcolors.ENDC}")
            
        # get info from the additional info section
        try:
            additional_info = driver.find_element_by_css_selector(".IxB2fe")
            app_last_update = additional_info.find_element_by_css_selector("div:nth-child(1)>span").text
            app_size = additional_info.find_element_by_css_selector("div:nth-child(2)>span").text
            app_downloads = int(additional_info.find_element_by_css_selector("div:nth-child(3)>span").text.replace(",", "").replace("+", ""))
            app_current_version = additional_info.find_element_by_css_selector("div:nth-child(4)>span").text
            app_necessary_android_version = additional_info.find_element_by_css_selector("div:nth-child(5)>span").text
        except ValueError:
            tqdm.write(f"{bcolors.FAIL}There is a value error. This probably means a value was assigned to the wrong field: {bcolors.ENDC} {bcolors.OKBLUE}{bcolors.UNDERLINE}{app_url}{bcolors.ENDC}, {app_name}")
        except NoSuchElementException:
            tqdm.write(f"{bcolors.FAIL}Some element is missing. Consider rechecking in the file later (is marked with CHECK AGAIN):{bcolors.ENDC} {bcolors.OKBLUE}{bcolors.UNDERLINE}{app_url}{bcolors.ENDC}, {app_name}")
        except NoSuchWindowException:
            print(f"{bcolors.FAIL}It seems that the window was closed...")

        # get info from the ratings short description
        try:
            app_header = driver.find_element_by_css_selector("div.sIskre")
            app_age_requirements = app_header.find_element_by_css_selector("div.KmO8jd").text
            app_producer = app_header.find_element_by_css_selector("span.T32cc").text
            app_genre = app_header.find_element_by_css_selector("a.R8zArc[itemprop=genre]").text
        except ValueError:
            tqdm.write(f"{bcolors.FAIL}There is a value error. This probably means a value was assigned to the wrong field: {bcolors.ENDC} {bcolors.OKBLUE}{bcolors.UNDERLINE}{app_url}{bcolors.ENDC}, {app_name}")
        except NoSuchElementException:
            tqdm.write(f"{bcolors.FAIL}Some element is missing. Consider rechecking in the file later (is marked with CHECK AGAIN):{bcolors.ENDC} {bcolors.OKBLUE}{bcolors.UNDERLINE}{app_url}{bcolors.ENDC}, {app_name}")
            app_age_requirements = "PLEASE CHECK AGAIN"
            app_genre = "PLEASE CHECK AGAIN"
        except NoSuchWindowException:
            print(f"{bcolors.FAIL}It seems that the window was closed...")

        try:
            app_amount_ratings = int(app_header.find_element_by_css_selector("span.AYi5wd").text.replace(",", ""))
            rsd = app_header.find_element_by_css_selector(".pf5lIe>div")
            app_rating = float(re.findall(r"[-+]?\d*\.\d+|\d+", rsd.get_attribute("aria-label").replace(",", "."))[0])
        except NoSuchElementException:
            tqdm.write(f"{bcolors.WARNING}Missing rating:{bcolors.ENDC} {bcolors.OKBLUE}{bcolors.UNDERLINE}{app_url}{bcolors.ENDC}, {app_name}")
            app_rating = 0
            app_amount_ratings = 0
        except NoSuchWindowException:
            print(f"{bcolors.FAIL}It seems that the window was closed...")
            
        app_data = produce_app_data_dict(app_name, app_rating, app_amount_ratings,
                                         app_downloads, app_url, app_size, app_last_update, 
                                         app_current_version, app_necessary_android_version, 
                                         app_age_requirements, app_producer, app_genre)
        apps_data.append(app_data)
    driver.quit()
    return apps_data

def produce_app_data_dict(app_name, app_rating, app_amount_ratings, 
                          app_downloads, app_url, app_size, 
                          app_last_update, app_current_version,
                          app_necessary_android_version, app_age_requirements, app_producer, app_genre):
    """Used to generate the app_data dictionary that is easily convertable to json and writable to csv"""
    return {
        "app_name" : app_name,
        "app_rating" : app_rating,
        "app_amount_ratings" : app_amount_ratings,
        "app_amount_downloads" : app_downloads,
        "app_url" : app_url,
        "size" : app_size,
        "last_update" : app_last_update,
        "current_version" : app_current_version,
        "necessary_android_version" : app_necessary_android_version,
        "age_requirements" : app_age_requirements,
        "app_producer" : app_producer,
        "app_genre" : app_genre
    }

def write_to_csv_file(filename, data_to_write):
    if len(data_to_write) == 0:
        print(f"{bcolors.WARNING}Nothing to write to file, no data scraped.{bcolors.ENDC}")
        return
    csv_columns = []
    for key, value in data_to_write[0].items():
        csv_columns.append(key)

    print(f"Writing results to {filename}...")
    while True:
        try:
            # writing to csv file
            with open(filename, 'w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=csv_columns)
                writer.writeheader()
                for data in data_to_write:
                    writer.writerow(data)
            print(f"{bcolors.OKGREEN}Data successfully written to {bcolors.OKBLUE}{bcolors.UNDERLINE}{filename}{bcolors.ENDC}{bcolors.OKGREEN}.{bcolors.ENDC}")
            return
        except PermissionError:
            print(f"{bcolors.WARNING}Cannot write to the file... It may be currently open.\n"
                + "Close the file to proceed.\nDo you wish to proceed? [yes/no]")
            userinput = input()
            if re.match(r"^(?:n|o)$", userinput, re.IGNORECASE):
                print(f"{bcolors.OKCYAN}Exiting without writing to file...{bcolors.ENDC}")
                return
            elif re.match(r"^(?:y|yes)$", userinput, re.IGNORECASE):
                print(f"{bcolors.OKCYAN}Attempting to write to file...{bcolors.ENDC}")
         
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
    print(f"Looking through '{bcolors.OKBLUE}{bcolors.UNDERLINE}{specific_target}{bcolors.ENDC}'")
    if os.path.isfile(args.output):
       print(f"{bcolors.WARNING}Watch out, the file already exists. Will be overwritten at the end!{bcolors.ENDC}")
    
    print(f"\n{bcolors.HEADER}[Step 1] {bcolors.UNDERLINE}Accumulating all URLs of Apps to scrub through{bcolors.ENDC}\n")
    driver.get(specific_target)
    urls = get_apps_as_urls(driver, args.quantity, args.scroll)
    print(f"\n{bcolors.HEADER}[Step 2] {bcolors.UNDERLINE}Looking through individual URLs and getting App Data{bcolors.ENDC}\n")
    if not args.performance:
        print(f"{bcolors.OKGREEN}Decided to go with Selenium {bcolors.OKCYAN}(This will reduce speed and performance - consider using beautifulsoup [check menu with -h]){bcolors.ENDC}")
        apps_data = get_data_from_individual_apps_selenium(driver, urls)
    else:
        driver.quit()
        print(f"{bcolors.OKGREEN}Decided to go with BeautifulSoup{bcolors.ENDC}")
        
        apps_data = get_data_from_individual_apps_beautifulsoup(urls)
    
    print(f"\n{bcolors.HEADER}[Step 3] {bcolors.UNDERLINE}Writing results to file{bcolors.ENDC}\n")
    write_to_csv_file(args.output, apps_data)
    # temp_res = get_data_from_individual_apps_beautifulsoup(["https://play.google.com/store/apps/details?id=com.emailYahoo.socialMedia"]) 
    # print(f"Final result:\n {temp_res}")


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