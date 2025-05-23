# pip install openpyxl
# pip install streamlit

# Importing Libraries
from datetime import date   
import pandas as pd
import math
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "Colruyt_scraping")))

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
    

# Make a class for Ingrdient => Append to IngredientDict on creation
class Ingredient:
    def __init__(self,name, gramPerUnit, url='', Kcal_100g='', Prot_100g='', priceurl=''):
        self.name = name 
        self.gramPerUnit = gramPerUnit 
        self.url = url 
        self.kcal_100g = float(Kcal_100g)
        self.prot_100g = float(Prot_100g)
        name_key = self.name.replace(" ","").upper()
        self.priceurl = priceurl

        # Only add object to IngredientDict if does not already exist
        if name_key in IngredientDict:
            print(f'Ingredient {self.name} already exists')
            return

        # Calculate the unit values
        self.kcal_unit = (gramPerUnit * ( self.kcal_100g/100) ) if self.kcal_100g>0 else 0
        self.prot_unit = (gramPerUnit * ( self.prot_100g/100) ) if self.prot_100g>0 else 0 #return n / d if d else 0
        self.protPer100Kcal = (self.prot_100g / self.kcal_100g*100) if self.kcal_100g>0 else 0
    
        # Add the ingredient to the global dictionary
        IngredientDict[name_key] = self
        
    # Methods for Ingredient Object
    def getLabel(self):
        return self.name

        
# Make a class for Recipe => Append to RecipeDict on creation
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
                key1 = ingredient
                key2 = ingredient.replace(" ", "").upper()
                if key1 not in IngredientDict and key2 not in IngredientDict:
                    print(f"Cannot add recipe {self.name}. Ingredient '{ingredient}' is not in the global ingredient list.")
                    return

        # Only add object to RecipeDict if does not already exist
        if name_key in RecipeDict:
            print(f'Recipe {self.name} already exists')
            return
        
        # Add the ingredient to the global dictionary
        RecipeDict[name_key] = self


    # Methods for Recipe Object
    def getLabel(self):
        return self.name
    
        # Recipe Functions
    def toDataFrameRows(self, portion=1):
        #Returns a list of dicts to create a dataframe
        rows=[]
        for ing_name, values in self.ingredientsRecipe.items():
            amount = values.get('amount',0)*portion
            unit = values.get('unit',"")
            ingr_key = values.get('name_key')
            ingr_obj = IngredientDict.get(ing_name.replace(" ", "").upper())
            label = ingr_obj.getLabel() if ingr_obj else ing_name  # fallback to ing_name if not found
            
            rows.append({
                "Ingredient" : label, #ing_name,
                "IngredientKey" : ing_name.replace(" ","").upper(),
                "Amount": amount,
                "Unit": unit
            })
        # print (rows)
        return rows



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
 
load_data_from_excel("./Excel_files/data.xlsx") #Grocery_list\Excel_files\data.xlsx
