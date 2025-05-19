{
 "cells": [
  {
   "cell_type": "code",
   "execution_count": 2,
   "id": "d28c6996",
   "metadata": {},
   "outputs": [],
   "source": [
    "import requests\n",
    "from bs4 import BeautifulSoup\n",
    "import pandas as pd\n",
    "import re\n",
    "\n",
    "def get_voedingswaarden_df(url, max_items=11):\n",
    "    \"\"\"\n",
    "    Scrapes and returns a DataFrame of nutritional data from a Colruyt product URL.\n",
    "\n",
    "    Parameters:\n",
    "        url (str): The URL of the Colruyt product page.\n",
    "        max_items (int): Max number of nutritional items to return.\n",
    "\n",
    "    Returns:\n",
    "        pd.DataFrame: DataFrame with columns [Index, Nutrition, Value].\n",
    "    \"\"\"\n",
    "    try:\n",
    "        response = requests.get(url)\n",
    "        response.raise_for_status()\n",
    "        soup = BeautifulSoup(response.text, 'html.parser')\n",
    "\n",
    "        voedingswaarden = soup.find('div', id='voedingswaarden')\n",
    "        if not voedingswaarden:\n",
    "            print(\"❌ 'VOEDINGSWAARDEN' section not found.\")\n",
    "            return pd.DataFrame(columns=['Nutrition', 'Value'])\n",
    "\n",
    "        details = voedingswaarden.find_all('div', class_='value-detail')[:max_items]\n",
    "\n",
    "        data = []\n",
    "        for detail in details:\n",
    "            name = detail.find('span', class_='val-name')\n",
    "            value = detail.find('span', class_='val-nbr')\n",
    "\n",
    "            if name and value:\n",
    "                raw_nutrient = name.text.strip()\n",
    "                raw_value = value.text.strip()\n",
    "\n",
    "                # Remove the last word from nutrient name\n",
    "                nutrient_parts = raw_nutrient.split()[:-1]\n",
    "                nutrient_clean = ' '.join(nutrient_parts)\n",
    "\n",
    "                # Remove unit (e.g., \"kJ\", \"kcal\", \"g\") using regex\n",
    "                value_clean = re.sub(r'\\s*(kJ|kcal|g)$', '', raw_value).strip()\n",
    "\n",
    "                data.append((nutrient_clean, value_clean))\n",
    "\n",
    "        df = pd.DataFrame(data, columns=['Nutrition', 'Value'])\n",
    "        df.reset_index(inplace=True)\n",
    "        df.rename(columns={'index': 'Index'}, inplace=True)\n",
    "\n",
    "        return df\n",
    "\n",
    "    except Exception as e:\n",
    "        print(f\"❌ Error scraping {url}: {e}\")\n",
    "        return pd.DataFrame(columns=['Nutrition', 'Value'])"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "id": "a3520021",
   "metadata": {},
   "outputs": [],
   "source": []
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "python_course",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.11.11"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 5
}
