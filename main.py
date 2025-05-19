# pip install openpyxl
# pip install streamlit

# Importing Libraries
from datasets import load_dataset 
from datetime import date   
from collections import defaultdict
import pandas as pd
import math
from pathlib import Path

# Use home made scraper to get nutritional value for a product from a link
from Colruty_scraping.colruyt_scraper import get_nutritional_data
from Colruty_scraping.colruyt_scraper_price import *

BASE_DIR = Path.cwd()
DATA_FILE = BASE_DIR / "Excel_files" / "data.xlsx"


# Global dictionaries
IngredientDict = {}
RecipeDict = {}

# Std variables
today = date.today().isoformat()

# Std functions
def is_number(x):
    try:
        return not math.isnan(float(x))
    except:
        return False
    

# Make a class for Ingrdient 
# Append to IngredientDict on creation
class Ingredient:
    def __init__(self,name, gramPerUnit, url='', Kcal_100g='', Prot_100g='', priceurl=''):
        self.name = name 
        self.gramPerUnit = gramPerUnit 
        self.url = url 
        name_key = self.name.replace(" ","").upper()
        self.priceurl = priceurl
        # IngredientDict[name] = self

        # Only add object to IngredientDict if does not already exist
        if name_key in IngredientDict:
            print(f'Ingredient {self.name} already exists')
            return
        
        # Get data from url
        data = get_nutritional_data(url)

        # URL did not work
        if data.empty:
            # If URL fails, check if manual values are usable
            if not is_number(Kcal_100g) or not is_number(Prot_100g):
                print(f'Ingredient URL for {self.name} cannot be used. Enter data manually')
                return
            #URL didn't work BUT we have manual data
            self.kcal_100g = float(Kcal_100g)
            self.prot_100g = float(Prot_100g)
        #URL works : Get the nutritional data
        else:
            try:
                self.kcal_100g = self.getKcalPer100g(data)
                self.prot_100g = self.getProtPer100g(data)
            except Exception as e:
                print(f'Failed to extract nutritional data from URL for {self.name}: {e}')
                return 

        # If URL gives empty dataframe : Check if kcal_100g and prot_100g are both filled in and numeric  
        if data.empty and (not is_number(Kcal_100g) or not is_number(Prot_100g)): 
            print(f'Ingredient URL for {self.name} cannot be used. Enter data manually')
            return

        # Calculate the unit values
        self.kcal_unit = (gramPerUnit * ( self.kcal_100g/100) ) if self.kcal_100g>0 else 0
        self.prot_unit = (gramPerUnit * ( self.prot_100g/100) ) if self.prot_100g>0 else 0 #return n / d if d else 0
        self.protPer100Kcal = (self.prot_100g / self.kcal_100g*100) if self.kcal_100g>0 else 0
    
        # Add the ingredient to the global dictionary
        IngredientDict[name_key] = self

    def getLabel(self):
        return self.name
    
    def getKey(self):
        return self.name.replace(" ","").upper()
    
    def show(self):
        text =  f'-----------------------------------------------\n'
        text += f'Ingredient {self.name}\n'
        text += f'-----------------------------------------------\n'
        text += f'URL : {self.url}\n'
        text += f'KCal / 100g : {self.kcal_100g}\n'
        text += f'Prot / 100g : {self.prot_100g}\n'
        text += f'Gram / unit : {self.gramPerUnit}\n'
        text += f'KCal / unit : {self.kcal_unit}\n'
        text += f'Prot / unit : {self.prot_unit}\n'
        text += f'Prot / 100KCal : {self.protPer100Kcal}\n'
        text += f'-----------------------------------------------\n'
        print(text)

    def doesIngredientExist(self):
        if self.name.replace(" ","").upper() in IngredientDict:
            return True

    def getProtPer100g(self, data=None):
        # data = data or get_nutritional_data(self.url)
        return float(data.loc[data['Nutrition'] == 'Eiwitten']['Value'].values[0])
    
    def getKJPer100g(self, data=None):
        # data = data or get_nutritional_data(self.url)
        return float(data.loc[data['Nutrition'] == 'Energie kJ']['Value'].values[0])
    
    def getKcalPer100g(self, data=None):
        # data = data or get_nutritional_data(self.url)
        if data[data['Nutrition'] == 'Energie kcal']['Value'].empty:
            return self.getKJPer100g(data)/ 4.184
        else:
            return float(data.loc[data['Nutrition'] == 'Energie kcal']['Value'].values[0])
    def getFatPer100g(self):
        data = get_nutritional_data(self.url)
        return float(data.loc[data['Nutrition'] == 'Totaal vetten']['Value'].values[0])
    def getCarbsPer100g(self):
        data = get_nutritional_data(self.url)
        return float(data.loc[data['Nutrition'] == 'Totaal koolhydraten']['Value'].values[0])
    def getSugarPer100g(self):
        data = get_nutritional_data(self.url)
        return float(data.loc[data['Nutrition'] == 'Suikers']['Value'].values[0])
    def getFiberPer100g(self):
        data = get_nutritional_data(self.url)
        return float(data.loc[data['Nutrition'] == 'Vezels']['Value'].values[0])
    def getSaltPer100g(self):
        data = get_nutritional_data(self.url)
        return float(data.loc[data['Nutrition'] == 'Zout']['Value'].values[0])
    
    def getKcal(self,amount,unit='g'):
        if is_number(amount):
            if unit == 'g':
                return self.kcal_100g * (amount/100)
            if unit == 'u':
                return self.kcal_unit * amount
        else:
            print(f'Amount must be numeric.')
            return 0
    def getProt(self,amount,unit='g'):
        if is_number(amount):
            if unit == 'g':
                return self.prot_100g * (amount/100)
            if unit == 'u':
                return self.prot_unit * amount
        else:
            print(f'Amount must be numeric.')
            return 0
    
    def getGram(self,unitAmount):
        if is_number(unitAmount):
            return unitAmount * self.gramPerUnit
        else:
            print(f'Amount must be numeric.')
    def getUnit(self,gramAmount):
        if is_number(gramAmount):
            return gramAmount / self.gramPerUnit
        else:
            print(f'Amount must be numeric.')
        
# Make a class for Recipe 
# Append to RecipeDict on creation
class Recipe:
    def __init__(self,name,ingredientsRecipe={}):
        self.name = name 
        self.ingredientsRecipe = ingredientsRecipe 
        name_key = self.name.replace(" ","").upper()

        # Does Recipe have ingredients?
        if not ingredientsRecipe:
            print(f"Recipe '{self.name}' must have at least one ingredient.")
            return
        
        for ingredient in ingredientsRecipe:
                if ingredient.replace(" ","").upper() not in IngredientDict:
                    print(f"Cannot add recipe. Ingredient '{ingredient}' is not in the global ingredient list.")
                    return

        # # Only add recipe to RecipeDict if does not already exist
        # if not self.doesRecipeExist():
        #     self.addToRecipeDict()
        # else:
        #     print(f'Recipe {self.name} already exists')
        #     return
        
        # Only add object to RecipeDict if does not already exist
        if name_key in RecipeDict:
            print(f'Recipe {self.name} already exists')
            return
        
        # Add the ingredient to the global dictionary
        RecipeDict[name_key] = self

    def show(self, portion=1):
        text =  f'---------------------------------------------------------\n'
        text += f'Recipe {self.name} ({portion} portion(s)) - Ingredients\n'
        text += f'---------------------------------------------------------\n'
        for ing_name, values in self.ingredientsRecipe.items():
            text += f'Ingredient {ing_name} :  {values.get("amount")*portion} {values.get("unit").replace("u","UNIT")}\n' 
        text += f'---------------------------------------------------------\n'
        print(text)

    def getLabel(self):
        return self.name
    
    def getKey(self):
        return self.name.replace(" ","").upper()

    def showDetails(self, portion=1):
        text =  f'---------------------------------------------------------\n'
        text += f'Recipe {self.name} ({portion} portion(s)) - Ingredients Details\n'
        text += f'---------------------------------------------------------\n'
        for ing_name, values in self.ingredientsRecipe.items():
            text += f'Ingredient {ing_name} :  {values.get("amount")*portion} {values.get("unit").replace("u","UNIT")}\n' 
            amount = values.get('amount')*portion 
            unit = values.get('unit')
            
            #Get my object for this ingredient
            ingredientGlobal = IngredientDict.get(ing_name.replace(" ","").upper()) 
            if ingredientGlobal: 
                text += f'          => Kcal: {round(ingredientGlobal.getKcal(amount, unit),2)}   => Prot: {round(ingredientGlobal.getProt(amount, unit),2)} \n' 
        text += f'---------------------------------------------------------\n'
        text += f'Total => Kcal: {round(self.getTotalKcal(portion),2)}   => Prot: {round(self.getTotalProt(portion),2)}  \n' 
        text += f'---------------------------------------------------------\n'
        print(text)
        
    # def addToRecipeDict(self):
    #     RecipeDict[self.name.upper()] = self
    
    def doesRecipeExist(self):
        if self.name.replace(" ","").upper() in RecipeDict:
            return True
        else:
            return False
    
    # Recipe Functions
    def getTotalKcal(self,portion=1):
        # Loop over each ingredient
        total_kcal = 0
        for ing_name , values in self.ingredientsRecipe.items():
            amount = values.get('amount')*portion 
            unit = values.get('unit')

            #Get my object for this ingredient
            ingredientGlobal = IngredientDict.get(ing_name.replace(" ","").upper()) 
            if ingredientGlobal: 
                #Calculate the kcal for this ingredient
                total_kcal += ingredientGlobal.getKcal(amount, unit)

        return round(total_kcal,2)
    def getTotalProt(self,portion=1):
        # Loop over each ingredient
        total_prot = 0
        for ing_name , values in self.ingredientsRecipe.items():
            amount = values.get('amount')*portion 
            unit = values.get('unit')

            #Get my object for this ingredient
            ingredientGlobal = IngredientDict.get(ing_name.replace(" ","").upper()) 
            if ingredientGlobal: 
                #Calculate the kcal for this ingredient
                total_prot += ingredientGlobal.getProt(amount, unit)

        return round(total_prot,2)
    def getIngrList(self):
        listIngr = []
        for ing_name, values in self.ingredientsRecipe.items():
            listIngr.append(ing_name)
        return listIngr
    def getIngrDetailsList(self,portion=1):
        listIngrDetails = []
        for ing_name, values in self.ingredientsRecipe.items():
            amount = values.get('amount')*portion
            unit = values.get('unit')
            ingr = IngredientDict[ing_name.replace(" ","").upper()]
            kcal = ingr.getKcal(amount,unit)
            prot = ingr.getProt(amount,unit)
            listIngrDetails.append({ing_name.replace(" ","").upper(): {'amount':amount, 
                                                        'unit':unit,
                                                        'kcal': round(kcal,2) ,
                                                        'prot': round(prot,2)
                                                        }
                                    })
            
        return listIngrDetails
        # print(ing_name, amount, unit, kcal, prot)
        # print(IngredientDict[ing_name.upper()] )
    
        # Recipe Functions
    def toDataFrameRows(self, portion=1):
        #Returns a list of dicts to create a dataframe
        rows=[]
        for ing_name, values in self.ingredientsRecipe.items():
            amount = values.get('amount',0)*portion
            unit = values.get('unit',"")
            ingr_key = values.get('name_key')
            rows.append({
                "Ingredient" : ing_name,
                "IngredientKey" : ing_name.replace(" ","").upper(),
                "Amount": amount,
                "Unit": unit
            })
        # print (rows)
        return rows


def searchIngrInIngrList(search_term):
    text =''
    found = False
    times =0
    for key in IngredientDict:
        if search_term.replace(" ","").upper() in key.replace(" ","").upper():
            if not found:
                text += f'{key}'
                times +=1
                found = True
            else:   
                text += f', {key}'
                times+= 1
    text = f'Found "{search_term}" {times} time(s) in ingredient list in: ' + text

    if found:
        print(text)
    else:
        print(f'There are no ingredients yet with {search_term} in the description.')
def searchRecipInRecipList(search_term):
    text =''
    found = False
    times =0
    for key in RecipeDict:
        if search_term.replace(" ","").upper() in key.replace(" ","").upper():
            if not found:
                text += f'{key}'
                times +=1
                found = True
            else:   
                text += f', {key}'
                times+= 1
    text = f'Found "{search_term}" {times} time(s) in recipe list in: ' + text

    if found:
        print(text)
    else:
        print(f'There are no recipes yet with {search_term} in the description.')
def searchIngrInRecipList(search_term):
    text =''
    for key,value in RecipeDict.items():
        textRecipe = ''
        times=0
        found=False
        for ingr_name in RecipeDict[key].getIngrList():
            if search_term.replace(" ","").upper() in ingr_name.replace(" ","").upper():
                if found:
                    textRecipe += f', {ingr_name}'
                    times +=1
                else: 
                    textRecipe += f'{ingr_name}'
                    found = True
                    times +=1
        if found:
            textRecipe = f'For recipe {key}, "{search_term}" has been found {times} time(s) in ingredients: {textRecipe}\n'
        text += textRecipe
    if text:
        print(text)
    else:
        print(f'There are no recipes yet with an ingredient with {search_term} in the description.')
def searchIngrDetailsInRecipList(search_term):
    text =''
    for key,value in RecipeDict.items():
        textRecipe = ''
        times=0
        found=False
        for ingr_name in RecipeDict[key].getIngrList():
            if search_term.replace(" ","").upper() in ingr_name.replace(" ","").upper():
                if found:
                    textRecipe  += f', {ingr_name}'
                    times +=1
                else: 
                    textRecipe += f'{ingr_name}'
                    found = True
                    times +=1

                listDetails = RecipeDict[key].getIngrDetailsList() #Get the details per ingredient found
                for ingrlistDetail in listDetails:
                    for keyIngrListDetail, valueIngrListDetail in ingrlistDetail.items():
                        if keyIngrListDetail.replace(" ","").upper() == ingr_name.replace(" ","").upper():
                            textRecipe += f' ( {valueIngrListDetail.get("amount")} {valueIngrListDetail.get("unit").replace("u","UNIT")} )'

        if found:
            textRecipe = f'For recipe "{key}", "{search_term}" has been found in ingredients {times} time(s): {textRecipe}\n'
        text += textRecipe
    if text:
        print(text)
    else:
        print(f'There are no recipes yet with an ingredient with {search_term} in the description.')


def getGroceryList(combine = 0, recipes = [] ):
    
    all_rows = []  # List of rows to build a DataFrame

    textAll =''
    if combine==0:
        for recipe in recipes:
            textRec =''
            rec_name = recipe.get('name')
            rec_portion = recipe.get('portion')

            # Put all ingredients with details , each a dictionary, into a list for that recipe
            listIngr = RecipeDict[rec_name].getIngrDetailsList(rec_portion)
            textRec  = f'------------------------------------------------------------------------\n'
            textRec += f'Recipe: {rec_name} for {rec_portion} portion(s)\n'
            textRec += f'------------------------------------------------------------------------\n'
            
            # Get each ingredient for recipe
            for ingr in listIngr:
                for ingr_name, ingr_values in ingr.items():
                    row = {
                        'Recipe': rec_name,
                        'Portion': rec_portion,
                        'Ingredient': ingr_name,
                        'IngredientKey': ingr_name.replace(" ","").upper(),
                        'Amount': round(ingr_values.get('amount'), 2),
                        'Unit': ingr_values.get('unit'),
                        'Kcal': round(ingr_values.get('kcal'), 1),
                        'Prot': round(ingr_values.get('prot'), 1)
                    }
                    all_rows.append(row)
                    textAll += (f'Ingredient: {row["Ingredient"]}     Amount: {row["Amount"]} {row["Unit"]}       '
                               f'Kcal: {row["Kcal"]}      Prot: {row["Prot"]}  \n')

        # print(textAll)
        df0 = pd.DataFrame(all_rows)#.sort_values(by='Recipe')
        return df0

    else:
        combined_ingredients = defaultdict(lambda: {'amount': 0, 'unit': '', 'kcal': 0, 'prot': 0})

        for recipe in recipes:
            rec_name = recipe.get('name')
            rec_portion = recipe.get('portion')
            # Put all ingredients with details , each a dictionary, into a list for that recipe
            listIngr = RecipeDict[rec_name].getIngrDetailsList(rec_portion)

            # Get each ingredient for recipe
            for ingr in listIngr:
                for ingr_name, ingr_values in ingr.items():
                    ingr_name_upper = ingr_name.replace(" ","").upper()
                    current_unit = ingr_values['unit']

                    if combined_ingredients[ingr_name_upper]['unit'] in ('', current_unit):
                        combined_ingredients[ingr_name_upper]['amount'] += ingr_values['amount']
                        combined_ingredients[ingr_name_upper]['kcal'] += ingr_values['kcal']
                        combined_ingredients[ingr_name_upper]['prot'] += ingr_values['prot']
                        combined_ingredients[ingr_name_upper]['unit'] = current_unit

        for name, values in combined_ingredients.items():
            all_rows.append({
                'Ingredient': name,
                'Amount': round(values['amount'], 2),
                'Unit': values['unit'],
                'Kcal': round(values['kcal'], 1),
                'Prot': round(values['prot'], 1)
            })
        # Convert to dataframe
        df1 = pd.DataFrame(all_rows).sort_values(by='Ingredient')

        # Print formatted text
        textAll = '------------------------------------------------------------------------\n'
        textAll += 'Combined Grocery List:\n'
        textAll += '------------------------------------------------------------------------\n'
        for _, row in df1.iterrows():
            textAll += (f'Ingredient: {row["Ingredient"]}     Amount: {row["Amount"]} {row["Unit"]}       '
                        f'Kcal: {row["Kcal"]}      Prot: {row["Prot"]}  \n')
        # print(textAll)

        return df1

def exportGroceryListToExcel(recipes):
  # Get the DataFrames
    df_combined = getGroceryList(combine=1, recipes=recipes)     # Combined totals
    df_detailed = getGroceryList(combine=0, recipes=recipes)     # Per recipe
  
    # Export to one Excel file with two sheets
    filename = f'grocery_list_{today}.xlsx'
    

    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        df_combined.to_excel(writer, sheet_name='Combined', index=False)
        df_detailed.to_excel(writer, sheet_name='Per Recipe', index=False)



def makeKey(name):
    return name.replace(' ','').upper()

def getIngr(name):
    if isinstance(name, str):
        key = makeKey(name)
        if key in IngredientDict:
            return IngredientDict[key]
        else:
            print(f"Warning: Ingredient {name} (key={key}) not found in Ingredients")
            return None
    return name


def getIngrKcal100g(ingredient):
    ingredient = getIngr(ingredient)
    return  float(ingredient.kcal_100g)

def getIngrProt100g(ingredient):
    ingredient = getIngr(ingredient)
    return  float(ingredient.prot_100g )

def getIngrGramPerUnit(ingredient):
    ingredient = getIngr(ingredient)
    return  float(ingredient.gramPerUnit)

def getIngrKcalPerUnit(ingredient):
    ingredient = getIngr(ingredient)
    return  float(ingredient.kcal_unit)

def getIngrProtPerUnit(ingredient):
    ingredient = getIngr(ingredient)
    return  float(ingredient.prot_unit)

def getIngrProtPer100kcal(ingredient):
    ingredient = getIngr(ingredient)
    return  float(ingredient.protPer100Kcal)

def getIngrKcal(ingredient, amount=0, unitOrGram='g'):
        if is_number(amount):
            ingredient_obj = getIngr(ingredient)
            if not ingredient_obj:
                return 0
            unitOrGram = unitOrGram.strip().lower()
            if unitOrGram == 'u':
                return float(amount * getIngrKcalPerUnit(ingredient_obj))
            if unitOrGram == 'g':
                return float(amount * (getIngrKcal100g(ingredient_obj)/100))
        else:
            print(f'Amount must be numeric.')
            return 0
    
def getIngrProt(ingredient, amount=0, unitOrGram='g'):
        if is_number(amount):
            ingredient_obj = getIngr(ingredient)
            if not ingredient_obj:
                return 0
            unitOrGram = unitOrGram.strip().lower()
            if unitOrGram == 'u':
                return float(amount * getIngrProtPerUnit(ingredient_obj))
            if unitOrGram == 'g':
                return float(amount * (getIngrProt100g(ingredient_obj)/100))
        else:
            print(f'Amount must be numeric.')
            return 0
        
def getRecipe(name):
    key = makeKey(name)
    if key in RecipeDict and isinstance(name, str):
        return RecipeDict[key]
    else:
        print(f"Warning: Recipe '{name}' not found in RecipeDict.")
    return None


def getRecipeIngr(name):
    recipe = getRecipe(name)
    return recipe.ingredientsRecipe.items()

def getRecipeLabel(recipe_name):
    key = recipe_name.replace(" ", "").upper()
    return RecipeDict[key].getLabel() if key in RecipeDict else recipe_name

# print(getRecipeIngr('baguette') )

def getRecipeKcal(name, portion=1):
    total_kcal = 0
    ingredients = getRecipeIngr(name)
    # Loop over each ingredient in recipe
    for key , values in ingredients:
        ingredient = getIngr(key)
        # Get amount and unit for Ingredient from Recipe
        amount = values.get('amount')*portion 
        unit = values.get('unit')
        if key:
            total_kcal += getIngrKcal(ingredient, amount, unit)
    return round(float(total_kcal),2)

def getRecipeProt(name, portion=1):
    total_prot = 0
    ingredients = getRecipeIngr(name)
    # Loop over each ingredient in recipe
    for key , values in ingredients:
        ingredient = getIngr(key)
        # Get amount and unit for Ingredient from Recipe
        amount = values.get('amount')*portion 
        unit = values.get('unit')
        if key:
            total_prot += getIngrProt(ingredient, amount, unit)
    return round(float(total_prot),2)
      
def getRecipeProtPer100Kcal(name):
    total_kcal = getRecipeKcal(name,1)
    total_prot = getRecipeProt(name,1)
    return round(float( total_prot/total_kcal*100 ),2 )

def convert_to_units(df, unit_col="Unit", amount_col="Amount"):
    """Convert g -> u where needed using getIngrGramPerUnit(ingredient)"""
    df = df.copy()
    df_all_g = df[unit_col] == "g"
    df.loc[df_all_g, "Amount"] = df.loc[df_all_g].apply(
        lambda row: row[amount_col] / getIngrGramPerUnit(row["Ingredient"]), axis=1
    )
    df["Unit"] = "u"
    return df

category_keywords = {
    "Protein": ["KIP", "RUND", "VARKEN","SEITAN", "VIS", "EI", "TOFU", "LINZEN", "BONEN", "KALKOEN", "ZALM", "SCAMPI","MISO"],
    "Vegetable": ["EDAMAME","LENTEUI","KERSTOMATEN","AUBERGINE","COURGETTE","CHAMPIGNONS","BROCCOLI", "SPINAZIE", "WORTEL", "TOMAAT", "AARDAPPEL", "UI", "PAPRIKA", "KOMKOMMER", "SPITSKKOOL", "BLOEMKOOL"],
    "Carbohydrate": ["WRAP","SUIKER","RIJST", "PASTA", "BROOD", "CAVATAPPI", "SPAGHETTI", "BLOEM", "MAÏS", "GIST", "BAGUETTE","KETCHUP","MOSTERD"],
    "Dairy": ["SKYR","FETA","MILK","MOZARELLA", "KAAS", "YOGHURT", "BOTER", "ROOM", "COTTAGE"],
    "Fat": ["PEANUTBUTTER","OLIJFOLIE", "OLIE", "BUTTER", "MARGARINE", "AVOCADO", "NOTEN", "SEED"],
    "Fruit": ["APPEL","AARDBEI", "BANAAN", "SINAASAPPEL", "MANDARIJN", "MANGO", "PEER", "PERZIK", "ANANAS", "DRUIVEN"],
    "Kruiden" : ["OREGANO"],
    "Liquide" : ["MIRIN","RIJSTAZIJN","LIMOENSAP","CITROENSAP","ZOUT","PEPER","SOYASAUS"]
}

veggie_keywords = {
    "Meat" : ["KIP","RUND","BURGER","HAMBURGER","VARKEN","KALKOEN"],
    "Fish" : ["SCAMPI","ZALM","ZALMFILET"]
}
 
seasonal_ingredients = {
    "1":  ["WORTEL","RODEUI","PREI","MANDARIJN"],
    "2":  ["WORTEL","RODEUI","PREI"],
    "3":  ["WORTEL","RODEUI","PREI"],
    "4":  ["APPEL","PREI","LENTEUI"],
    "5":  ["APPEL","SPITSKOOL","LENTEUI","KOMKOMMER"],
    "6":  ["APPEL","WORTEL","TOMAAT","SPITSKOOL","LENTEUI","KOMKOMMER","AARDBEI","BROCCOLI","COURGETTE","KERSTOMATEN"],
    "7":  ["APPEL","WORTEL","TOMAAT","SPITSKOOL","RODEPAPRIKA","KOMKOMMER","AARDBEI","AUBERGINE","BROCCOLI","COURGETTE","KERSTOMATEN","KNOFLOOKTEEN"],
    "8":  ["APPEL","WORTEL","TOMAAT","SPITSKOOL","RODEUI","RODEPAPRIKA","KOMKOMMER","AARDBEI","KNOFLOOKTEEN","AUBERGINE","BROCCOLI","COURGETTE","DRUIVEN","EDAMAME","KERSTOMATEN"],
    "9":  ["APPEL","WORTEL","TOMAAT","SPITSKOOL","RODEUI","RODEPAPRIKA","KOMKOMMER","AUBERGINE","KNOFLOOKTEEN","BROCCOLI","COURGETTE","DRUIVEN","EDAMAME","KERSTOMATEN"],
    "10": ["APPEL","WORTEL","SPITSKOOL","RODEUI","RODEPAPRIKA","PREI","BROCCOLI","KNOFLOOKTEEN","DRUIVEN"],
    "11": ["APPEL","WORTEL","SPITSKOOL","RODEUI","PREI","MANDARIJN","BROCCOLI"],
    "12": ["APPEL","WORTEL","RODEUI","PREI","MANDARIJN"]
}

def categorize_ingredient(ingredient):
    ingredient_upper = ingredient.upper()
    for category, keywords in category_keywords.items():
        if any(keyword in ingredient_upper for keyword in keywords):
            return category
    return "Other"

veggie_keywords = {
    "Meat" : ["KIP","RUND","BURGER","HAMBURGER","VARKEN","KALKOEN"],
    "Fish" : ["SCAMPI","ZALM","ZALMFILET"]
}
 
def is_veggie_ingredient(ingredient):
    ingredient_upper = ingredient.upper()
    for category, keywords in veggie_keywords.items():
        if any(keyword in ingredient_upper for keyword in keywords):
            return category
    return "Other"


def is_veggie_recipe(recipe_name):
    ingredients = getRecipeIngr(recipe_name)
    for key, _ in ingredients:
        category = is_veggie_ingredient(key)
        if category in ["Meat", "Fish"]:
            return False
    return True




#ADD DATA
def load_ingredients_from_excel(filepath):
    IngredientDict.clear()
    df = pd.read_excel(filepath,sheet_name='Ingredients')
    for x, row in df.iterrows():
        name=row['name']
        gramPerUnit=row['gramPerUnit']
        url=row.get('url','')
        kcal_100g=row.get('kcal_100g','') 
        prot_100g=row.get('prot_100g','')
        priceurl=row.get('priceurl','')
        Ingredient(name, gramPerUnit,url,kcal_100g,prot_100g,priceurl)

def load_recipes_from_excel(filepath):
    RecipeDict.clear()
    df = pd.read_excel(filepath, sheet_name='Recipes')
    grouped = df.groupby('recipe_name')

    for recipe_name, group in grouped:
        ingredientsRecipe = {}
        for _, row in group.iterrows():
            ingredient = row['ingredient']
            amount = row['amount']
            unit = row['unit']
            ingredientsRecipe[ingredient] = {'amount': amount, 'unit': unit}
        Recipe(recipe_name, ingredientsRecipe)

def load_data_from_excel(filepath):
    load_ingredients_from_excel(filepath)
    load_recipes_from_excel(filepath)
 
load_data_from_excel("Grocery_list\Excel_files\data.xlsx")

# load_data_from_excel(DATA_FILE) 