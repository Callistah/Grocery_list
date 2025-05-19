import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

def get_nutritional_data(url):
    """
    Scrapes nutritional information from a Colruyt product page and returns it as a DataFrame.
    
    Parameters:
        url (str): The URL of the product page.
    
    Returns:
        pd.DataFrame: A DataFrame with two columns: 'Nutrition' and 'Value'.
    """
    # Send a GET request to the website
    response = requests.get(url)
    
    # Check if the request was successful
    if response.status_code == 200:
        # Parse the page content
        soup = BeautifulSoup(response.text, 'html.parser')
    else:
        print(f"❌ Error scraping {url}: Unable to fetch data.")
        return pd.DataFrame(columns=['Nutrition', 'Value'])
    
    # Find the section with nutritional info
    voedingswaarden = soup.find('div', id='voedingswaarden')
    
    if voedingswaarden:
        data = []
        # Find all nutrient entries
        details = voedingswaarden.find_all('div', class_='value-detail')[:11]  # Get the first 11 items
        energie_kj_count = 0  # To track the occurrence of "Energie kJ"

        for detail in details:
            name = detail.find('span', class_='val-name')
            value = detail.find('span', class_='val-nbr')

            if name and value:
                raw_value = value.text.strip()

                # Check if the value starts with "< .", and if so, fix it
                if raw_value.startswith("< ."):
                    raw_value = "0" + raw_value[2:]  # Fix the < . to 0.
                if raw_value.startswith("< 0."):
                    raw_value =  raw_value[2:]  # Fix the < 0. to 0.

                # Clean the nutrient name and value
                nutrient_clean = name.text.strip()
                value_clean = re.sub(r'\s*(kJ|kcal|g)$', '', raw_value).strip()  # Remove units (kJ, kcal, g)

                # If we encounter "Energie kJ", increment the counter
                if nutrient_clean == "Energie kJ":
                    energie_kj_count += 1
                    # Skip the second and any subsequent "Energie kJ"
                    if energie_kj_count == 2:
                        break

                # Append cleaned data as a tuple
                data.append((nutrient_clean, value_clean))

        # Convert the cleaned data into a DataFrame
        df = pd.DataFrame(data, columns=['Nutrition', 'Value'])
        return df
    else:
        # print("❌ Could not find the 'VOEDINGSWAARDEN' section.")
        return pd.DataFrame(columns=['Nutrition', 'Value'])