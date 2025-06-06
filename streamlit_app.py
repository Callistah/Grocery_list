import streamlit as st
import pandas as pd
import os
import io
from main import *  # RecipeDict, IngredientDict, get
from datetime import date, datetime
import altair as alt
import plotly.graph_objects as go
import networkx as nx
from itertools import combinations
from collections import Counter
import random
from Colruyt_scraping.colruyt_scraper_price import *
import uuid

# CMD run locally: streamlit run streamlit_app.py

# --- Configure page layout ---
st.set_page_config(layout='wide', initial_sidebar_state='expanded')
col_seq = ["Ingredient", "Amount", "Unit"]
# --- Navigation ---
page = st.radio("Navigation", 
                ["Grocery List Maker", "Data Analysis"], 
                horizontal=True)
current_month = str(datetime.now().month)
seasonal_this_month = set(seasonal_ingredients.get(current_month, []))
 
# LOAD DATA FROM LOG FILE
log_file_path = "./Excel_files/Log/Grocery_List_Log.xlsx"

if not os.path.exists(log_file_path):
    st.warning("Log file not found. No data to analyze yet.")
else:
    # Load data
    df_log_per_recipe = pd.read_excel(log_file_path, sheet_name="Log Per Recipe")
    df_log_combined = pd.read_excel(log_file_path, sheet_name="Log Combined")
    
    # Ensure ExportDate is in date format
    df_log_per_recipe["ExportDate"] = pd.to_datetime(df_log_per_recipe["ExportDate"])
    df_log_combined["ExportDate"] = pd.to_datetime(df_log_combined["ExportDate"])
    
    # Get dataframes containing : Unique Recipes / ExportDate => Sum of portions over all ExportDates  &  how many times recipe was logged => Favorite recipes
    df_uniq_recipe_per_date = df_log_per_recipe.drop_duplicates(subset=["Recipe", "ExportDate", "Portion"]).reset_index(drop=True)
    df_sum_portion_per_recipe = df_uniq_recipe_per_date.groupby("Recipe", as_index=False)["Portion"].sum().sort_values(by="Recipe")
    df_freq_recipe = df_log_per_recipe.groupby("Recipe", as_index=False)["ExportDate"].nunique().rename(columns={"ExportDate":"Frequency"})

    df_fav_recipes = df_sum_portion_per_recipe.merge(df_freq_recipe, on="Recipe")
    df_fav_recipes['AvgPortion'] = df_fav_recipes['Portion'] / df_fav_recipes['Frequency']
    df_fav_recipes = df_fav_recipes.sort_values(by='AvgPortion',ascending=False).head(5)

    # Get dataframe for last log
    last_log_date = df_log_combined["ExportDate"].max()
    df_last_log_combined = df_log_combined[df_log_combined["ExportDate"] == last_log_date].copy()
    df_last_log_per_recipe = df_log_per_recipe[df_log_per_recipe["ExportDate"] == last_log_date].copy()

    # Get dataframe where ingredients are grouped => Difference between combined and per recipe
    df_last_log_combined_grouped = df_last_log_combined.groupby(["Ingredient", "Unit"], as_index=False)["Amount"].sum()
    df_last_log_per_recipe_grouped = df_last_log_per_recipe.groupby(["Ingredient", "Unit"], as_index=False)["Amount"].sum()
    
    # Get dataframe only with the ingredients that were logged as an extra ingredient, not in a recipe last time
    df_extras_only = pd.merge(
                df_last_log_combined_grouped,
                df_last_log_per_recipe_grouped,
                on=["Ingredient", "Unit"],
                how="left",
                suffixes=("_combined", "_recipe"))

    df_extras_only["Amount_recipe"] = df_extras_only["Amount_recipe"].fillna(0)
    df_extras_only["Amount"] = df_extras_only["Amount_combined"] - df_extras_only["Amount_recipe"]
    df_extras_only = df_extras_only[df_extras_only["Amount"] > 0][["Ingredient", "Unit", "Amount"]]
    
    # Get dataframes of all data except today
    all_prev_per_recipe_log = df_log_per_recipe[df_log_per_recipe['ExportDate'] != today]
    all_prev_combined_log = df_log_combined[df_log_combined['ExportDate'] != today]

    # Create Date Columns
    df_log_combined["DateOnly"] = df_log_combined["ExportDate"].dt.date
    df_log_combined["Year"] = df_log_combined["ExportDate"].dt.year
    df_log_combined["MonthNum"] = df_log_combined["ExportDate"].dt.month
    df_log_combined["MonthName"] = df_log_combined["ExportDate"].dt.strftime("%b")

    df_log_per_recipe["DateOnly"] = df_log_per_recipe["ExportDate"].dt.date
    df_log_per_recipe["Year"] = df_log_per_recipe["ExportDate"].dt.year
    df_log_per_recipe["MonthNum"] = df_log_per_recipe["ExportDate"].dt.month
    df_log_per_recipe["MonthName"] = df_log_per_recipe["ExportDate"].dt.strftime("%b")

    # Global Date Filter used in tab Data Analysis
    unique_dates = sorted(df_log_combined["DateOnly"].unique(), reverse=True)

    all_years = sorted(df_log_combined["Year"].unique())
    all_months = sorted(df_log_combined["MonthNum"].unique())
    all_month_names = df_log_combined.drop_duplicates("MonthNum")[["MonthNum", "MonthName"]].sort_values("MonthNum")["MonthName"].tolist()
    all_dates = sorted(df_log_combined["DateOnly"].unique())
    
    # Get RecipeLabel & IngredientLabel (first normalize key)
    df_log_per_recipe['IngredientLabel'] = df_log_per_recipe['Ingredient']
    df_log_per_recipe['IngredientKey'] = df_log_per_recipe['IngredientKey'].str.strip().str.upper().str.replace(" ","", regex=False)
    df_log_per_recipe['RecipeKey'] = df_log_per_recipe['Recipe'].str.strip().str.upper()
    df_log_per_recipe['RecipeLabel'] = df_log_per_recipe['Recipe'].map(getRecipeLabel)
    
    df_log_combined['IngredientKey'] = df_log_combined['Ingredient'].str.strip().str.upper().str.replace(" ","", regex=False)
    df_log_combined['IngredientLabel'] = df_log_combined['Ingredient'].map(lambda r: IngredientDict[r].getLabel() if r in IngredientDict else r)


# --- Initialize session state for recipe selections ---
if "selected_recipes" not in st.session_state:
    st.session_state.selected_recipes = {}
if "extra_rows" not in st.session_state:
    st.session_state.extra_rows = []
if "selected_last_extras" not in st.session_state:
    st.session_state.selected_last_extras = []
if "last_extra_ids" not in st.session_state:
    st.session_state.last_extra_ids = {}
if "reused_extra_ids" not in st.session_state:
    st.session_state.reused_extra_ids = set()
    
# For both "pages"
st.sidebar.title("Settings")

# --- GROCERY LIST MAKER ---
if page == "Grocery List Maker":
    
    # Define functions
    def add_extra_row():
        new_id = str(uuid.uuid4())
        st.session_state.extra_rows.append(new_id)

    # Reload state when extra ingredients from last log are added or removed
    def sync_reused_extras():
        for label in  st.session_state.selected_last_extras:
            if label not in st.session_state.last_extra_ids:
                rid = str(uuid.uuid4())
                st.session_state.last_extra_ids[label] = rid
                st.session_state.extra_rows.append(rid)
                row = last_extra_map[label]
                st.session_state[f"ing_{rid}"] = row["Ingredient"]
                st.session_state[f"portion_{rid}"] = int(row["Amount"])
                st.session_state[f"TypeOfUnit_{rid}"] = row["Unit"]
                st.session_state.reused_extra_ids.add(rid)
        # Also remove any rows in extra_rows that correspond to labels no longer selected
        labels_to_remove = [label for label, rid in st.session_state.last_extra_ids.items()
                            if label not in st.session_state.selected_last_extras]
        for label in labels_to_remove:
            rid = st.session_state.last_extra_ids.pop(label)
            if rid in st.session_state.extra_rows:
                st.session_state.extra_rows.remove(rid)
            for key in [f"ing_{rid}", f"portion_{rid}", f"TypeOfUnit_{rid}"]:
                st.session_state.pop(key, None)
            st.session_state.reused_extra_ids.discard(rid)

    st.title("Grocery List Maker! A La Esh!")
    with st.expander('Choose recipes and portions'):
        # Get all available recipes to select from => enter portion per recipe 
        for recipe in RecipeDict:
            default_use = recipe in st.session_state.selected_recipes
            use = st.checkbox(RecipeDict[recipe].getLabel(), 
                              key=f'chk_{recipe}', 
                              value=default_use)
            if use:
                cols = st.columns([1, 3])  # 1/3 width split (adjust if needed)
                default_portion = max(st.session_state.selected_recipes.get(recipe, 1),1)
                with cols[0]:
                    portion = st.number_input(
                        f"Portion for {RecipeDict[recipe].getLabel()}",
                        min_value=0,
                        max_value=100000,
                        value=default_portion,
                        step=1,
                        key=f'portion_{recipe}'
                    )
                
                with cols[1]:
                    note_key = f'note_{recipe}'
                    st.text_input(
                        "Notes",  # Shorter label to save space
                        value=st.session_state.get(note_key, ""),
                        key=note_key
                    )
              
                st.session_state.selected_recipes[recipe] = portion
            else:
                st.session_state.selected_recipes.pop(recipe, None)

    selected = st.session_state.selected_recipes

    # Get all available Ingredients from IngredientDict
    ingredient_options = {
        ingr_value.getLabel(): (ingr_key, ingr_value)
        for ingr_key, ingr_value in IngredientDict.items() }
    
    # Create radiobutton for suggestions
    suggestion_type = st.sidebar.radio("Need help picking recipes?", 
                                       ["Nope! I'm good!", 
                                        "For busy evenings",
                                        "Focus on lighter meals",
                                        "Go full veggie",
                                        "Show favorites"], 
                                       key='sidebar_radio_help_picking')

    if suggestion_type == "Show favorites":
            st.sidebar.markdown("These recipes have been **logged the most**:")
            # Per recipe get : Key, freq, avg portoin, label
            for _, row in df_fav_recipes.iterrows():
                recipe_key = row["Recipe"].strip().upper()
                frequency = row["Frequency"]
                avg_portion = row["AvgPortion"]
                recipe_label = RecipeDict[recipe_key].getLabel() if recipe_key in RecipeDict else recipe_key
                st.sidebar.markdown(f"- **{recipe_label}**: {frequency} time(s) with an avg of {avg_portion:.1f} portions/logging")
    
    if suggestion_type == "For busy evenings":
        fewest_ingredients = sorted(
                RecipeDict.items(),
                key=lambda item: len(set(ing["IngredientKey"] for ing in item[1].toDataFrameRows(1)))
            )
        st.sidebar.markdown("Try these recipes with the **least amount of unique ingredients**:")
        for key, recipe in fewest_ingredients[:5]:
            st.sidebar.markdown(f"- **{recipe.getLabel()}**: {len(recipe.toDataFrameRows(1))} ingredients")

    if suggestion_type == "Focus on lighter meals":
        kcal_per_recipe = [
            (name, getRecipeKcal(name))
            for name in RecipeDict.keys()]
        lightest_recipes = sorted(kcal_per_recipe, key = lambda x: x[1])[:5]

        st.sidebar.markdown("Try these recipes with the **lowest kcal per portion**:")
        for name, kcal in lightest_recipes:
            recipe = getRecipe(name)
            label = recipe.getLabel() if recipe else name
            st.sidebar.markdown(f"- **{label}**: {kcal} kcal per portion)")

    if suggestion_type == "Go full veggie":
        # Filter for fully vegetarian recipes
        veggie_recipes = [
            name for name in RecipeDict.keys()
            if is_veggie_recipe(name)
        ]
        # Randomly select 5
        selected_veggie_recipes = random.sample(veggie_recipes, 
                                                k=min(5, len(veggie_recipes)))

        st.sidebar.markdown("Try these randomly chosen **veggie** recipes:")
        for name in selected_veggie_recipes:
            recipe = getRecipe(name)
            label = recipe.getLabel() if recipe else name
            st.sidebar.markdown(f"- {label}")

    # Get a dictionary of all extra ingredients of previous log with key= Ingredient (Amount unit) and value row of dataframe
    last_extra_map = {
                f"{row['Ingredient']} ({int(row['Amount'])} {row['Unit']})": row
                for _, row in df_extras_only.iterrows()}
    
    # Get a multiselect list for these prev. extra ingr. and keep track which have already been added
    st.sidebar.subheader("Add extra ingredients from last list")
    all_extra_labels = list(last_extra_map.keys() )
    selected_reused = st.sidebar.multiselect(
        "↺ Reuse previous extra ingredients?",
        options=all_extra_labels,
        key="selected_last_extras",
        default= st.session_state.selected_last_extras)
    
    # Reload state
    sync_reused_extras()
    
    # Initialize necessary variables for the extra ingredients
    extra_ingredients = []
    rows_to_keep = []
    used_ingredients = []
    unit_options = ['u', 'g']

    for row_id in st.session_state.extra_rows:
        # Skip rendering if the row was marked for deletion
        if f"delete_{row_id}" in st.session_state and st.session_state[f"delete_{row_id}"]:
            continue
        
        cols = st.columns([4, 2, 2, 1])  
        current_ingr = st.session_state.get(f"ing_{row_id}", "")
        available_ingredients = sorted([
            label for label in ingredient_options
            if (label not in used_ingredients and 
                label not in [row['Ingredient'] for label, row in last_extra_map.items() if label in st.session_state.selected_last_extras]) 
            or label == current_ingr])

        if not available_ingredients:
            st.warning("No more ingredients to add.")
            break

        # Get all ingredients that have not been added yet displayed
        ingr_display = {}
        for ing in available_ingredients:
            ingr_display[ing] = ing
                
        select_options = ["Select an ingredient..."] + list(ingr_display.keys()) 
        prev_selection = st.session_state.get(f"ing_{row_id}", "Select an ingredient...")

        for display, original in ingr_display.items():
            if original == prev_selection:
                prev_selection_display = display
                break
        else:
            prev_selection_display = "Select an ingredient..."

        # Column[0] = Select Ingredient / column[1] = Input number, integer / column[2] = Select unit, default u
        ingr_name = cols[0].selectbox(
            f"Extra Ingredient",
            options=select_options,
            index=select_options.index(prev_selection_display) if prev_selection_display in select_options else 0,
            key=f"ing_{row_id}"
        )
        
        portion = cols[1].number_input(   
            "Amount",
            min_value=0,
            max_value=100000,
            step=1,
            value=st.session_state.get(f"portion_{row_id}", 1),
            key=f"portion_{row_id}"
        )

        unit = cols[2].selectbox(
            "Type of Units",
            options=unit_options,
            index=unit_options.index(st.session_state.get(f"TypeOfUnit_{row_id}", 'u')),
            key=f"TypeOfUnit_{row_id}"
        )
        
        # How to remove? Trash can or through navigation
        with cols[3]:
            # Check if it's from the sidebar multiselect
            from_sidebar = False

            for label, rid in st.session_state.last_extra_ids.items():
                if rid == row_id:
                    from_sidebar = True
                    break

            if from_sidebar:
                # Instead of delete button, show notice that this ingredient needs to be deleted by unselecting it in sidebar
                st.markdown(
                    f"<span style='color: gray; font-size: 0.6em; font-style: italic;'>Unselect ingredient in sidebar to remove</span>",
                    unsafe_allow_html=True
                )
            else:
                # 🗑️ DELETE BUTTON  
                if st.button("🗑️", key=f"delete_{row_id}"):  
                    st.session_state.extra_rows.remove(row_id)
                    st.session_state.reused_extra_ids.discard(row_id)

                    # Remove associated session state
                    for key in [f"ing_{row_id}", f"portion_{row_id}", f"TypeOfUnit_{row_id}"]:
                        st.session_state.pop(key, None)


        if portion > 0 and ingr_name and ingr_name != "Select an ingredient...":
            if ingr_name in ingredient_options:
                ingr_key, ingr_obj = ingredient_options[ingr_name]
                extra_ingredients.append({
                    "Ingredient": ingr_obj.getLabel(),
                    "IngredientKey": ingr_key,
                    "Unit": unit,
                    "Amount": portion
                })
                # Add to used_ingredients only if not reused to prevent duplicate filtering
                if row_id not in st.session_state.reused_extra_ids:
                    used_ingredients.append(ingr_name)
        rows_to_keep.append(row_id)            
    st.session_state.extra_rows = rows_to_keep

    st.button("➕ Add Extra Ingredient", on_click=add_extra_row, key="add_extra_bottom")

    tab1, tab2 = st.tabs(["All Ingredients", "Per Recipe"])
  
    # output_mode = st.sidebar.radio("Export the recipes?", ["View Here", "Export to Excel"])

    all_data = []
    concatDF = []

    for recipe, portion in selected.items():
        data = RecipeDict[recipe].toDataFrameRows(portion)
        df = pd.DataFrame(data)
        note = st.session_state.get(f'note_{recipe}', "")  # Get the note for this recipe
        df_export = df.copy()
        df_export.insert(0, 'Recipe', recipe.ljust(12))
        df_export.insert(1, 'Portion', portion)
        df_export['Notes'] = note  # This will apply the same note to all rows of this recipe
        concatDF.append(df_export)

    # Tabs
    with tab1:
        if extra_ingredients:
            df_extra = pd.DataFrame(extra_ingredients)

        if concatDF:
            all_data = pd.concat(concatDF, ignore_index=True)
            all_data["IngredientKey"] = all_data["IngredientKey"].str.strip().str.upper()
            all_data["Unit"] = all_data["Unit"].str.strip().str.lower()

        if extra_ingredients and concatDF:
            all_data = pd.concat([all_data, df_extra], ignore_index=True) 
        elif extra_ingredients:
            all_data = df_extra

        if extra_ingredients or concatDF:
            combined = all_data.groupby(["Ingredient", "Unit"], as_index=False).sum()
            combined = combined[col_seq]
            st.dataframe(combined.set_index("Ingredient"), use_container_width=True)

    if selected:
        with tab2:
            for recipe, portion in selected.items():
                df = pd.DataFrame(RecipeDict[recipe].toDataFrameRows(portion))
                df = df[['Ingredient', 'Amount', 'Unit']]
                recipe_label = RecipeDict[recipe].getLabel()

                with st.expander(f"{recipe_label} - {portion} portion(s)", expanded=False):
                    st.dataframe(df.set_index('Ingredient'), use_container_width=True)

    # Export Ingredients and Recipes to one file, separate tabs
    # if output_mode == "Export to Excel":
  # Determine if there's data to export
    has_data = False
    
    if 'all_data' in globals() and isinstance(all_data, pd.DataFrame):
        has_data = True
    if 'concatDF' in globals() and isinstance(concatDF, pd.DataFrame):
        has_data = True

    if has_data:
            st.sidebar.subheader("Display Options")
            buffer = io.BytesIO()
            today = date.today().isoformat()
            file_path = f'.\Excel_files\Export\Grocery_List_{today}.xlsx'
            log_file_path = '.\Excel_files\Log\Grocery_List_Log.xlsx'
    
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                any_written = False
            
                if not combined.empty:
                    combined.to_excel(writer, index=False, sheet_name="Combined")
                    any_written = True
            
                if concatDF:
                    per_recipe_df = pd.concat(concatDF, ignore_index=True)
                    if not per_recipe_df.empty:
                        per_recipe_df.to_excel(writer, index=False, sheet_name="Per Recipe")
                        any_written = True
            
                if not any_written:
                    pd.DataFrame({"Message": ["No data to export"]}).to_excel(writer, index=False, sheet_name="Info")
                    st.warning("No data to export. Please select some recipes or add ingredients.")
    
            buffer.seek(0)

            st.sidebar.download_button(
                    label="Download Excel File",
                    data=buffer.getvalue(),
                    file_name=f"Grocery_List_{today}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            # Save to disk
            with open(file_path, "wb") as f:
                f.write(buffer.getvalue())


            if 'concatDF' in globals() and isinstance(concatDF, pd.DataFrame):
                per_recipe_log = pd.concat(concatDF, ignore_index=True)
                per_recipe_log['ExportDate'] = today
                
                combined_log = combined.copy()
                combined_log['ExportDate'] = today
    
                if os.path.exists(log_file_path):
                    updated_per_recipe_log = pd.concat([all_prev_per_recipe_log, per_recipe_log], ignore_index=True)
                    updated_combined_log = pd.concat([all_prev_combined_log, combined_log], ignore_index=True)
                else:
                    updated_per_recipe_log = per_recipe_log
                    updated_combined_log = combined_log
        
                with pd.ExcelWriter(log_file_path, engine='openpyxl', mode='w') as log_writer:
                    updated_per_recipe_log.to_excel(log_writer, index=False, sheet_name='Log Per Recipe')
                    updated_combined_log.to_excel(log_writer, index=False, sheet_name='Log Combined')
                if not any_written:
                    st.warning("Nothing to export. Please select some recipes or add ingredients.")


# --- DATA ANALYSIS PAGE (to be implemented) ---
elif page == "Data Analysis":
    st.title("Grocery List Analysis")
    st.header("Groceries Analysis")
    st.sidebar.header("Date Filters")

    all_dates_checked = st.sidebar.checkbox("All Dates", value=True)
    if not all_dates_checked:
        selected_years = st.sidebar.multiselect("Year", options=all_years, default=all_years)
        selected_months = st.sidebar.multiselect("MonthNum", options=all_month_names, default=all_month_names)
        
        # Filter dates by selected years and months:  Map month names back to month numbers for filtering
        month_name_to_num = {name: num for num, name in zip(all_months, all_month_names)}
        selected_month_nums = [month_name_to_num[m] for m in selected_months if m in month_name_to_num]

        # Filter df_log_combined for dates matching the selected year and month
        if selected_years and selected_month_nums:
            filtered_dates_df = df_log_combined[
                df_log_combined["Year"].isin(selected_years) & 
                df_log_combined["MonthNum"].isin(selected_month_nums)]

        if selected_years and not selected_month_nums:
            filtered_dates_df = df_log_combined[
                df_log_combined["Year"].isin(selected_years)]
            
        if not selected_years and selected_month_nums:
            filtered_dates_df = df_log_combined[
                df_log_combined["MonthNum"].isin(selected_month_nums)]
        
        if not selected_years and not selected_month_nums:
            filtered_dates_df = df_log_combined

        # From these filtered rows, get the unique dates available
        filtered_dates = sorted(filtered_dates_df["DateOnly"].unique())
        selected_dates = st.sidebar.multiselect("Date", options=filtered_dates, default=filtered_dates)

        if not selected_dates:
            selected_dates = filtered_dates
    # If checkbox is checked : all years, all months, all dates
    else:
        selected_years = all_years
        selected_months = all_month_names
        selected_dates = all_dates

    # Copy Dataframes for Data Analysis (always keep the original)
    da_df_combined = df_log_combined[df_log_combined["DateOnly"].isin(selected_dates)].copy()
    da_df_per_recipe = df_log_per_recipe[df_log_per_recipe["DateOnly"].isin(selected_dates)].copy()
    # Get Ingredient Categories
    da_df_per_recipe["Ingredient_Cat"] = da_df_per_recipe["Ingredient"].apply(categorize_ingredient)
    # Convert to Units
    da_df_per_recipe_u = convert_to_units(da_df_per_recipe, unit_col="Unit", amount_col="Amount")
    da_df_combined_u = convert_to_units(da_df_combined, unit_col="Unit", amount_col="Amount")
    # Group and sum amount per Ingredient or per Recipe and Ingredient
    da_df_combined_group = (
            da_df_combined.groupby(["IngredientLabel", "Unit"], as_index=False)["Amount"]
            .agg(['sum','size'])
            .sort_values(by="IngredientLabel") )

    da_df_per_recipe_group = (
            da_df_per_recipe.groupby(["RecipeLabel","Portion", "IngredientLabel","Unit"], as_index=False)["Amount"]
            .agg(['sum','size'])
            .sort_values(by="RecipeLabel"))
        
    da_df_per_recipe_group['RecipeKcal1Port'] = da_df_per_recipe_group.apply(
            lambda row : getRecipeKcal( row['RecipeLabel'], 1 ), axis = 1)
        
    da_df_per_recipe_group['RecipeProtPer100Kcal'] = da_df_per_recipe_group.apply(
            lambda row : getRecipeProtPer100Kcal( row['RecipeLabel'] ), axis = 1)
        
    ################################################################
        # VISUALS
    ################################################################
                
    caption = 'Select ingredients from dropdown above. Hover for details.'
    # Visual 1 : Time Line Chart : Show ingredient quantities in units over time
    with st.expander("Ingredient Usage Over Time"):
        st.markdown(f'This line chart shows how many **units of an ingredient** have been saved over **time**. Each ingredient can have 2 lines (stacked), together they show **total units**:')
        st.markdown(f'- Full line: How many units were saved as part of a recipe')
        st.markdown(f'- Dash line: How many units were saved as an extra ingredient')

        # Group both by ExportDate and Ingredient
        pr_grouped = (
            da_df_per_recipe_u.groupby(["ExportDate", "IngredientLabel"])["Amount"]
            .sum()
            .reset_index()
            .rename(columns={"Amount": "UsageInRecipeCount"}))

        comb_grouped = (
            da_df_combined_u.groupby(["ExportDate", "IngredientLabel"])["Amount"]
            .sum()
            .reset_index()
            .rename(columns={"Amount": "TotalCombinedCount"}))

        # Merge and calculate extra usage
        merged = pd.merge(comb_grouped, pr_grouped, how="left", on=["ExportDate", "IngredientLabel"])
        merged["UsageInRecipeCount"] = merged["UsageInRecipeCount"].fillna(0)
        merged["UsageExtraCount"] = (merged["TotalCombinedCount"] - merged["UsageInRecipeCount"]).clip(lower=0)
        merged["TotalUsage"] = merged["UsageInRecipeCount"] + merged["UsageExtraCount"]
        merged["Date"] = pd.to_datetime(merged["ExportDate"]).dt.strftime('%B %d, %Y')

        # Dropdown for selecting multiple ingredients
        all_ingredients = sorted(merged["IngredientLabel"].dropna().unique())
        
        # "Select All" checkbox
        select_all = st.checkbox("Select All Ingredients", value=True, key='SelectAll_Visual1')
        
        if select_all:
            selected_ingredients = all_ingredients
        else:
            selected_ingredients = st.multiselect(
            "Select Ingredient(s) to highlight:",
            options=all_ingredients,
            default=[]  )

        # Filter data by selected ingredients
        filtered_data = merged[merged["IngredientLabel"].isin(selected_ingredients)]

        viewTable = st.radio("View data in table?", ["No", "Yes"], key="Visual1")

        base = alt.Chart(filtered_data).encode(
            x=alt.X("ExportDate:T", title="Date"),
            color=alt.Color("IngredientLabel:N", legend=alt.Legend(title="Ingredient")))

        unique_dates = filtered_data["ExportDate"].nunique()

        # If multiple data points => show line
        if unique_dates > 1:
            recipe_line = base.mark_line(strokeWidth=2).encode(
            y=alt.Y("UsageInRecipeCount:Q", title="Ingredient Usage Count"),
            tooltip=["Date", alt.Tooltip("IngredientLabel:N",title='Ingredient'), alt.Tooltip("UsageInRecipeCount:Q", title="Recipe Count")])

            total_line = base.mark_line(strokeDash=[5, 5], strokeWidth=2).encode(
            y=alt.Y("TotalUsage:Q"),
            tooltip=["Date", alt.Tooltip("IngredientLabel:N",title='Ingredient'), alt.Tooltip("TotalUsage:Q", title="Total Count")])
        # If only 1 data point => show point instead of line
        else:
            recipe_line = base.mark_point(filled=True, size=100).encode(
            y=alt.Y("UsageInRecipeCount:Q", title="Ingredient Usage Count"),
            tooltip=["Date", alt.Tooltip("IngredientLabel:N",title='Ingredient'), alt.Tooltip("UsageInRecipeCount:Q", title="Recipe Count")])

            total_line = base.mark_point(shape="triangle", size=100).encode(
            y=alt.Y("TotalUsage:Q"),
            tooltip=["Date", alt.Tooltip("IngredientLabel:N",title='Ingredient'), alt.Tooltip("TotalUsage:Q", title="Total Count")])
   
        # Show chart and optionally the table
        if viewTable == "Yes":
            col1, col2 = st.columns([3, 2])
            with col1:
                st.altair_chart(recipe_line + total_line, use_container_width=True)
                st.write(caption)
            with col2:
                table = filtered_data[["IngredientLabel", "Date", "UsageInRecipeCount", "UsageExtraCount", "TotalUsage"]]
                table = table.rename(columns={
                'IngredientLabel': 'Ingredient',
                'TotalUsage': 'Total Units',
                'UsageExtraCount': 'Extra Ingredient (u)',
                'UsageInRecipeCount': 'Part of Recipe (u)'})
                st.dataframe(table.set_index("Ingredient"), use_container_width=True)
        # Fill container with chart
        else:
            st.altair_chart(recipe_line + total_line, use_container_width=True)
            st.write(caption)

    # Visual 2 : Time Line Chart : Show recipe portions over time
    with st.expander("Recipe Portions Over Time"): 
        st.markdown(f'This chart shows how **portions per recipe**  change over **time**.')

        # Get portion once per recipe per date
        recipe_ts = (
            da_df_per_recipe.groupby(["DateOnly", "RecipeLabel"])["Portion"]
            .first()
            .reset_index())

        # Select All and Multi-Select for Recipes
        select_all_recipes = st.checkbox("Select All Recipes", value=True, key='SelectAll_Visual2')
        all_recipes = sorted(recipe_ts["RecipeLabel"].dropna().unique())
        if select_all_recipes:
            selected_recipes = all_recipes
        else:
            selected_recipes = st.multiselect(
                "Select Recipe(s) to highlight:",
                options=all_recipes,
                default=[],
                key="select_recipe_visual2")

        # Filter recipe_ts by selected recipes
        recipe_ts_filtered = recipe_ts[recipe_ts["RecipeLabel"].isin(selected_recipes)]

        # View table option
        viewTable = st.radio("View data in table?", ["No", "Yes"], key='Visual2')
        
        # Define selection for chart and adjust for multi-selection
        selection = alt.selection_point(fields=["RecipeLabel"])#selection_multi(fields=["RecipeLabel"])
        paddingDays = 5
        paddingPortion = 2
        
        min_date = recipe_ts_filtered["DateOnly"].min()
        max_date = recipe_ts_filtered["DateOnly"].max()
        max_y = recipe_ts_filtered['Portion'].max()

        # Add padding rows to expand the domain implicitly
        pad_df = pd.DataFrame({
            "DateOnly": [min_date - pd.Timedelta(days=paddingDays),
                        max_date + pd.Timedelta(days=paddingDays)],
            "RecipeLabel": ["_PADDING", "_PADDING"],
            "Portion": [None, None]})

        pad_y_df = pd.DataFrame({
            "DateOnly": [None, None],
            "RecipeLabel": ["_PADDINGY", "_PADDINGY"],
            "Portion": [0, max_y + paddingPortion]})

        recipe_ts_padded = pd.concat([recipe_ts_filtered, pad_df], ignore_index=True)
        recipe_ts_padded = pd.concat([recipe_ts_padded, pad_y_df], ignore_index=True)

        recipe_ts_padded["RecipeLegend"] = recipe_ts_padded["RecipeLabel"].where(
            ~recipe_ts_padded["RecipeLabel"].str.startswith("_"))

        # Base chart elements
        base = alt.Chart(recipe_ts_padded).encode(
            x=alt.X("DateOnly:T", title="Date"),
            y=alt.Y("Portion:Q", title="Portion"),
            color=alt.condition(
            selection, 
            alt.Color("RecipeLegend:N", 
                    scale=alt.Scale(domain=recipe_ts_padded["RecipeLegend"].dropna().unique().tolist()),
                    legend=alt.Legend(title="Recipe")), 
            alt.value("lightgray")
            ),
            opacity=alt.condition(selection, alt.value(1), alt.value(0.1))
        ).add_params(selection)

        # Line chart
        lines = base.mark_line().transform_filter(selection)

        # Points
        points = base.mark_point(filled=True, size=80).transform_filter(selection)

        # Create selection for tooltip hover
        hover = alt.selection_point(on="mouseover", 
                            nearest=True, 
                            fields=["DateOnly", "Portion"], 
                            empty="none")

        # Voronoi overlay: transparent selector to show tooltip when hovering overlapping points
        voronoi = alt.Chart(recipe_ts_filtered).mark_circle(opacity=0).encode(
            x=alt.X("DateOnly:T", title="Date"),
            y="Portion:Q"
        ).add_params(hover)

        # Generate an offset for each label so they don't overlap
        tooltip_data = recipe_ts_filtered.copy()
        tooltip_data["RowOffset"] = (
            tooltip_data
            .groupby(["DateOnly", "Portion"])
            .cumcount())
        # Multiply by factor for spacing value
        tooltip_data["dy_offset"] = tooltip_data["RowOffset"] * 15
        tooltips = []

        for offset in tooltip_data["RowOffset"].unique():
            subset = tooltip_data[tooltip_data["RowOffset"] == offset]
            label = alt.Chart(subset).transform_filter(
                hover
                ).transform_filter(selection).mark_text(
                    align="left",
                    dx=10,
                    dy=int(offset * 15)  # STATIC number only
                    ).encode(
                        x=alt.X("DateOnly:T"),
                        y="Portion:Q",
                        text=alt.Text("RecipeLabel:N"),
                        tooltip=[
                            alt.Tooltip("DateOnly:T", title="Date"),
                            alt.Tooltip("RecipeLabel:N", title="Recipe"),
                            alt.Tooltip("Portion:Q", title="Portion")
                        ]
                        )
            tooltips.append(label)

        chart = (lines + points + voronoi + alt.layer(*tooltips)).interactive().properties(height=400)

        # Display chart and optionally the table
        if viewTable == 'Yes':
            col1, col2 = st.columns([3, 2])
            with col1:
                st.altair_chart(chart, use_container_width=True)
                st.write(caption)
            with col2:
                recipe_ts_filtered["DateOnly"] = pd.to_datetime(recipe_ts_filtered["DateOnly"]).dt.strftime('%B %d, %Y')
                st.dataframe(recipe_ts_filtered.rename(columns={'RecipeLabel':'Recipe','DateOnly': 'Date'}).set_index("Recipe"), use_container_width=True)

        else:
            st.altair_chart(chart, use_container_width=True)
            st.write(caption)

    # Visual 4 : Bar chart : Quick overview of Prot / 100kcal for recipes
    with st.expander("Protein per 100 Kcal for Recipes"):
        st.markdown('This bar chart gives a quick overview of which **recipes** have a higher or lower **protein count per 100 kcal**.')
        scatter_data = da_df_per_recipe_group.drop_duplicates(subset="RecipeLabel")[["RecipeLabel", "RecipeProtPer100Kcal"]]

        # Select All and Multi-Select for Recipes
        select_all = st.checkbox("Select All Recipes", value=True, key='SelectAll_Visual4')
        all_recipes = sorted(scatter_data["RecipeLabel"].dropna().unique())
        if select_all:
            selected_recipes = all_recipes
        else:
            selected_recipes = st.multiselect(
            "Select Recipe(s) to highlight:",
            options=all_recipes,
            default=[],
            key="select_recipe_visual4")

        # Filter the top_recipes_result based on selected recipes
        filtered_recipes_result = scatter_data[scatter_data['RecipeLabel'].isin(selected_recipes)]
        filtered_recipes_result = filtered_recipes_result.sort_values(by='RecipeProtPer100Kcal', ascending = False)

        # Optional: limit number of recipes shown
        top_n = st.slider("Select how many top recipes to show", min_value=5, max_value=30, value=10, step=1, key = 'slider_prot_per_100kcal')
        filtered_recipes_result = filtered_recipes_result.head(top_n)

        # Set max y axis
        if not filtered_recipes_result.empty:
            max_y = filtered_recipes_result["RecipeProtPer100Kcal"].dropna().max()
            max_y = 1 if pd.isna(max_y) or max_y == 0 else max_y + 1
        else:
            max_y  = 1

        chart = alt.Chart(filtered_recipes_result).mark_bar().encode(
                x=alt.X("RecipeLabel:N",
                    title='Recipes', 
                    sort='-y',
                    axis=alt.Axis(labelAngle=45)),
                y=alt.Y("RecipeProtPer100Kcal:Q", 
                    title='# Protein / 100 Kcal',
                    scale=alt.Scale(domain=[0, max_y+1])),
                tooltip=[alt.Tooltip("RecipeLabel:N", title="Recipe"),
                        alt.Tooltip("RecipeProtPer100Kcal:Q", title="Protein / 100 kcal")],
                color=alt.Color("RecipeProtPer100Kcal:Q",
                            scale=alt.Scale(scheme='blues'),
                            legend=None)
                ).properties(height=400)
                
        viewTable = st.radio("View data in table?", ["No", "Yes"],key='Visual5')
        if viewTable =='Yes':
            col1, col2 = st.columns([3,2])
            # Visual
            with col1:
                st.altair_chart(chart, use_container_width=True)
                st.write(caption)
            # Data table
            with col2:
                st.dataframe(filtered_recipes_result.rename(columns={'RecipeLabel':'Recipe','RecipeProtPer100Kcal':'Prot / 100 Kcal'}).set_index("Recipe"), use_container_width=True)
        else:
            st.altair_chart(chart, use_container_width=True)
            st.write(caption)

    # Visual 8 : Ingredient use over time
    with st.expander("Top Recipes by Number of Unique Ingredients"):
        st.markdown("This bar chart shows which recipes have the highest number of **unique ingredients**, indicating their complexity or variety.")

        # Count unique ingredients per recipe
        unique_ingredients_df = da_df_per_recipe.groupby("RecipeLabel")["IngredientLabel"].nunique().reset_index(name="UniqueIngredients")

        # Sort descending by unique ingredients
        unique_ingredients_df = unique_ingredients_df.sort_values(by="UniqueIngredients", ascending=False)

        # Select All and Multi-Select for Recipes
        select_all = st.checkbox("Select All Recipes", value=True, key='SelectAll_Visual8')
        all_recipes = sorted(unique_ingredients_df["RecipeLabel"].dropna().unique())
        if select_all:
            selected_recipes = all_recipes
        else:
            selected_recipes = st.multiselect(
            "Select Recipe(s) to highlight:",
            options=all_recipes,
            default=[],
            key="select_recipe_visual8"
            )

        # Filter the top_recipes_result based on selected recipes
        unique_ingredients_df = unique_ingredients_df[unique_ingredients_df['RecipeLabel'].isin(selected_recipes)]

        # Optional: limit number of recipes shown
        top_n = st.slider("Select how many top recipes to show", min_value=5, max_value=30, value=10, step=1, key = 'slider_uniq_ingr_per_recipe')
        top_recipes_df = unique_ingredients_df.head(top_n)

        # Bar chart with Altair
        chart = alt.Chart(top_recipes_df).mark_bar().encode(
            x=alt.X("UniqueIngredients:Q", title="Number of Unique Ingredients"),
            y=alt.Y("RecipeLabel:N", sort='-x', title="Recipe"),
            tooltip=[alt.Tooltip("RecipeLabel:N"), alt.Tooltip("UniqueIngredients:Q")],
            color=alt.Color("UniqueIngredients:Q",
                    scale=alt.Scale(scheme='blues'),
                    legend=None)
        ).properties(
            width=700,
            height=40 * top_n,
            title=f"Top {top_n} Recipes by Unique Ingredients"
        )

        viewTable = st.radio("View data in table?", ["No", "Yes"],key='Visual8')
        if viewTable =='Yes':
            col1, col2 = st.columns([3,2])
            # Visual
            with col1:
                st.altair_chart(chart, use_container_width=True)
                st.write(caption)
            # Data table
            with col2:
                st.dataframe(top_recipes_df.rename(columns={'RecipeLabel':'Recipe','UniqueIngredients':'# Unique Ingredients'}).set_index("Recipe"), use_container_width=True)
        else:
            st.altair_chart(chart, use_container_width=True)
            st.write(caption)

    # Visual 3 : Plot chart : Correlation between portions and frequency of recipes
    with st.expander("Correlation: Frequency of Recipe Logged vs Average Portions per Logging"):
        st.markdown('This plot charts shows the correlation between the **frequency** of how many times a recipe was logged and the **average of portions registered per logging**.')
        st.markdown('This gives an indication of how **popular** a recipe is!')

        # Drop duplicate (same recipe on same date)
        portion_df = da_df_per_recipe.groupby(["RecipeLabel", "ExportDate","Portion"]).size().reset_index()
        avg_portions_df = portion_df.groupby("RecipeLabel")["Portion"].mean().reset_index(name="AvgPortionsPerSave")

        # How many times recipe appears in log
        freq_df = portion_df.drop_duplicates(subset=["RecipeLabel", "ExportDate"])
        freq_df = freq_df.groupby("RecipeLabel").size().reset_index(name='TimesLogged')

        # Merge all together
        visual3_df = avg_portions_df.merge(freq_df, on="RecipeLabel", how="left")

        # Select All and Multi-Select for Recipes
        select_all = st.checkbox("Select All Recipes", value=True, key='SelectAll_Visual3')
        all_recipes = sorted(visual3_df["RecipeLabel"].dropna().unique())
        if select_all:
            selected_recipes = all_recipes
        else:
            selected_recipes = st.multiselect(
            "Select Recipe(s) to highlight:",
            options=all_recipes,
            default=[],
            key="select_recipe_visual3"
            )

        # Filter the top_recipes_result based on selected recipes
        filtered_recipes_result = visual3_df[visual3_df['RecipeLabel'].isin(selected_recipes)]

        # Compute axis bounds
        max_x = filtered_recipes_result["TimesLogged"].dropna().max()
        max_y = filtered_recipes_result["AvgPortionsPerSave"].dropna().max()

        if not filtered_recipes_result.empty:
            max_x = filtered_recipes_result["TimesLogged"].max()
            max_y = filtered_recipes_result["AvgPortionsPerSave"].max()

            max_x = 1 if pd.isna(max_x) or max_x == 0 else max_x + 1
            max_y = 1 if pd.isna(max_y) or max_y == 0 else max_y + 1
        else:
            max_x, max_y = 1, 1 

        chart = alt.Chart(filtered_recipes_result).mark_circle(size=100).encode(
        x=alt.X("TimesLogged:Q", 
            title="Times Recipe Logged",
            scale=alt.Scale(domain=[0, max_x + 1])),
        y=alt.Y("AvgPortionsPerSave:Q", 
            title="Average Amount of Portions per Logging",
            scale=alt.Scale(domain=[0, max_y + 1])),
        tooltip=[   alt.Tooltip("RecipeLabel:N", title="Recipe"),
                alt.Tooltip("TimesLogged:Q", title="# Times Logged"),
                alt.Tooltip("AvgPortionsPerSave:Q", title="Avg Portions / Logging")],
        color=alt.Color("RecipeLabel:N", legend = alt.Legend(title="Recipe")),
        size=alt.Size("TimesLogged:Q", scale=alt.Scale(range=[50, 300]), legend=None)

            ).properties(
        width=700,
        height=400
        ).interactive()
            
        # View table option
        viewTable = st.radio("View data in table?", ["No", "Yes"], key='Visual4')
        if viewTable == 'Yes':
            col1, col2 = st.columns([3, 2])
            # Visual
            with col1:
                st.altair_chart(chart, use_container_width=True)
                st.write(caption)
            # Data table
            with col2:
                filtered_recipes_result.rename(columns={'TimesLogged':'Times Recipe Logged', 'AvgPortionsPerSave':'Average # of Portions / Logging'}, inplace=True)
                st.dataframe(filtered_recipes_result.rename(columns={'RecipeLabel':'Recipe'}).set_index("Recipe"), use_container_width=True)
        else:
            st.altair_chart(chart, use_container_width=True)
            st.write(caption)

    # Visual 6 : Plot chart : Nutritional info : # Ingr => the total kcal of 1 portion of a recipe to its prot/100kcal
    with st.expander("Nutritional Efficiency: 1 Portion Kcal vs. Protein per 100 Kcal vs Amount of Ingredients"):
        st.markdown('This scatter plot shows the **correlation** between how many **kcal are in 1 portion** of a recipe and how much **protein per 100 kcal** it has.')
        st.markdown('Also indicates difficulty of the recipe by the **amount of ingredients are used in 1 portion**.')

        # Count unique ingredients per recipe
        ingredients_df = da_df_per_recipe.groupby("RecipeLabel")["Ingredient"].nunique().reset_index(name="UniqueIngredients")            # Drop duplicates to avoid multiple rows per recipe
        scatter_df = da_df_per_recipe_group[["RecipeLabel", "RecipeKcal1Port", "RecipeProtPer100Kcal"]].drop_duplicates()

        scatter_df = scatter_df.merge(ingredients_df, on="RecipeLabel", how="left")

        # Optional: filter out invalid or NaN values
        scatter_df = scatter_df.dropna(subset=["RecipeKcal1Port", "RecipeProtPer100Kcal"])
        scatter_df = scatter_df[scatter_df["RecipeKcal1Port"] > 0]

        # Select All and Multi-Select for Recipes
        select_all = st.checkbox("Select All Recipes", value=True, key='SelectAll_Visual6')
        all_recipes = sorted(scatter_df["RecipeLabel"].dropna().unique())
        if select_all:
            selected_recipes = all_recipes
        else:
            selected_recipes = st.multiselect(
            "Select Recipe(s) to highlight:",
            options=all_recipes,
            default=[],
            key="select_recipe_visual6"
            )

        # Filter the top_recipes_result based on selected recipes
        filtered_recipes_result = scatter_df[scatter_df['RecipeLabel'].isin(selected_recipes)]
        filtered_recipes_result = filtered_recipes_result.sort_values(by='RecipeProtPer100Kcal', ascending = False)

        # Set max y axis
        if not filtered_recipes_result.empty:
            max_x = filtered_recipes_result["RecipeKcal1Port"].dropna().max()
            max_x = 1 if pd.isna(max_x) or max_x == 0 else max_x + 1
            max_y = filtered_recipes_result["RecipeProtPer100Kcal"].dropna().max()
            max_y = 1 if pd.isna(max_y) or max_y == 0 else max_y + 1
        else:
            max_x,max_y  = 1,1 # fallback in case no recipes are selected


        chart = alt.Chart(filtered_recipes_result).mark_circle(size=100).encode(
        x=alt.X("RecipeKcal1Port:Q", title="Kcal per 1 Portion",scale=alt.Scale(domain=[300, max_x+100])),
        y=alt.Y("RecipeProtPer100Kcal:Q", title="Protein per 100 kcal", scale=alt.Scale(domain=[0, max_y+1])),
        size=alt.Size("UniqueIngredients:Q", title="# Ingredients",scale=alt.Scale(range=[30, 300])),
        color=alt.Color("UniqueIngredients:Q", scale=alt.Scale(scheme="viridis")),
        tooltip=[alt.Tooltip("RecipeLabel:N", title="Recipe"),
            alt.Tooltip("RecipeKcal1Port:Q", title="Kcal / 1 Portion"),
            alt.Tooltip("RecipeProtPer100Kcal:Q", title="Prot / 100 Kcal"),
            alt.Tooltip("UniqueIngredients:Q", title="# Ingredients")]
            ).interactive().properties(
                width=700,
                height=400
            )

        viewTable = st.radio("View data in table?", ["No", "Yes"],key='VisualT6')
        if viewTable =='Yes':
            col1, col2 = st.columns([3,2])
            # Visual
            with col1:
            # Plot using Altair
                st.altair_chart(chart, use_container_width=True)
                st.write(caption)
            # Data table
            with col2:
                st.dataframe(filtered_recipes_result.rename(columns={'RecipeLabel':'Recipe','RecipeKcal1Port':'Kcal 1 portion', 'RecipeProtPer100Kcal':'Prot / 100 Kcal', 'UniqueIngredients':'# Ingredients'}).set_index("Recipe"), use_container_width=True)
        else:
            st.altair_chart(chart, use_container_width=True)
            st.write(caption)

    # Visual 7 : Plot chart : Nutritional info : # Ingr => the total kcal of 1 portion of a recipe to its prot/100kcal
    with st.expander("Recipe Popularity: Frequency of Recipe Saved vs Average amount of Portions per Save vs Amount of Ingredients"):
        st.markdown('This scatter plot shows the **correlation** between how many **times the recipe was saved** and what is the **average amount of portion** it is saved with.')
        st.markdown('Compared to the previous graph this plot gives an indication of popularity of the recipe by the **amount of ingredients are used in 1 portion**.')

        # Count unique ingredients per recipe & Times logged
        unique_ingr_df = da_df_per_recipe.groupby("RecipeLabel")["IngredientLabel"].nunique().reset_index(name="UniqueIngredients")            # Drop duplicates to avoid multiple rows per recipe
        times_logged_df = da_df_per_recipe.drop_duplicates(subset=["RecipeLabel", "ExportDate"])
        times_logged_df = times_logged_df.groupby("RecipeLabel").size().reset_index(name="TimesLogged")
 
        # Step 3: Average portions per save
        portion_df = da_df_per_recipe.groupby(["RecipeLabel", "ExportDate","Portion"]).size().reset_index()#["Portion"].sum().reset_index()
        avg_portions_df = portion_df.groupby("RecipeLabel")["Portion"].mean().reset_index(name="AvgPortionsPerSave")

        # Merge all together
        popularity_df = unique_ingr_df.merge(times_logged_df, on="RecipeLabel", how="left")
        popularity_df = popularity_df.merge(avg_portions_df, on="RecipeLabel", how="left")

        # Select All and Multi-Select for Recipes
        select_all = st.checkbox("Select All Recipes", value=True, key='SelectAll_Visual7')
        all_recipes = sorted(popularity_df["RecipeLabel"].dropna().unique())
        if select_all:
            selected_recipes = all_recipes
        else:
            selected_recipes = st.multiselect(
            "Select Recipe(s) to highlight:",
            options=all_recipes,
            default=[],
            key="select_recipe_visual7"
            )

        # Filter the top_recipes_result based on selected recipes
        filtered_recipes_result = popularity_df[popularity_df['RecipeLabel'].isin(selected_recipes)]

        # Set max y axis
        if not filtered_recipes_result.empty:
            max_x = filtered_recipes_result["UniqueIngredients"].dropna().max()
            max_x = 1 if pd.isna(max_x) or max_x == 0 else max_x + 1
            max_y = filtered_recipes_result["TimesLogged"].dropna().max()
            max_y = 1 if pd.isna(max_y) or max_y == 0 else max_y + 1
        else:
            max_x,max_y  = 1,1 # fallback in case no recipes are selected

        # Plot using Altair
        chart = alt.Chart(filtered_recipes_result).mark_circle(size=100).encode(
            x=alt.X("UniqueIngredients:Q", title="Unique Ingredients",scale=alt.Scale(domain=[0, max_x])),
            y=alt.Y("TimesLogged:Q", title="Times Recipe Saved", scale=alt.Scale(domain=[0, max_y])),
            size=alt.Size("AvgPortionsPerSave:Q", title="Avg Portions per Save",scale=alt.Scale(range=[30, 300])),
            color=alt.Color("AvgPortionsPerSave:Q", scale=alt.Scale(scheme="viridis")),
            tooltip=[alt.Tooltip("RecipeLabel:N", title="Recipe"),
                alt.Tooltip("UniqueIngredients:Q", title="# Unique Ingredients"),
                alt.Tooltip("TimesLogged:Q", title="# Times Saved"),
                alt.Tooltip("AvgPortionsPerSave:Q", title="Avg Portions per Save", format='.2f')]
        ).interactive().properties(
            width=700,
            height=400
        )

        viewTable = st.radio("View data in table?", ["No", "Yes"],key='VisualT7')
        if viewTable =='Yes':
            col1, col2 = st.columns([3,2])
            # Visual
            with col1:
            # Plot using Altair
                st.altair_chart(chart, use_container_width=True)
                st.write(caption)
            # Data table
            with col2:
                st.dataframe(filtered_recipes_result.rename(columns={'RecipeLabel':'Recipe','UniqueIngredients':'# Unique Ingredients','TimesLogged':'# Times Logged','AvgPortionsPerSave':'Average # of Portions per Logging'}).set_index("Recipe"), use_container_width=True)
        else:
            st.altair_chart(chart, use_container_width=True)
            st.write(caption)

    # Visual 9 : Radar chart : Protein per 100 kcal , Calories per portion  ,Number of unique ingredients , Average portions per save
    with st.expander("Nutritional Trade-off Analysis (Radar Chart)"):
        st.markdown("""
        This radar chart compares recipes across **multiple nutritional metrics**:
        - Protein per 100 kcal
        - Calories per portion
        - Number of unique ingredients
        - Average portions per save
        
        It helps to visualize trade-offs and balance among these factors.
        """)

        # Prepare data
        
        # Unique ingredients per recipe
        unique_ingr_df = da_df_per_recipe.groupby("RecipeLabel")["IngredientLabel"].nunique().reset_index(name="UniqueIngredients")
        
        # Nutrition data
        nutrition_df = da_df_per_recipe_group[["RecipeLabel", "RecipeKcal1Port", "RecipeProtPer100Kcal"]].drop_duplicates()
        
        # Average portions per save
        portion_df = da_df_per_recipe.groupby(["RecipeLabel", "ExportDate", "Portion"]).size().reset_index()
        avg_portions_df = portion_df.groupby("RecipeLabel")["Portion"].mean().reset_index(name="AvgPortionsPerSave")
        
        # Merge all
        radar_df = nutrition_df.merge(unique_ingr_df, on="RecipeLabel", how="left")
        radar_df = radar_df.merge(avg_portions_df, on="RecipeLabel", how="left")

        # Labels cleanup
        radar_df["RecipeLabel"] = radar_df["RecipeLabel"].map(lambda r: RecipeDict[r].getLabel() if r in RecipeDict else r)

        # Select All and Multi-Select for Recipes
        select_all = st.checkbox("Select All Recipes", value=True, key='SelectAll_Visual9')
        all_recipes = sorted(radar_df["RecipeLabel"].dropna().unique())
        if select_all:
            selected_recipes = all_recipes
        else:
            selected_recipes = st.multiselect(
            "Select Recipe(s) to highlight:",
            options=all_recipes,
            default=[],
            key="select_recipe_visual9"
            )
        radar_df = radar_df.dropna(subset=["RecipeProtPer100Kcal", "RecipeKcal1Port", "UniqueIngredients", "AvgPortionsPerSave"])
        
        if selected_recipes:
            df_selected = radar_df[radar_df["RecipeLabel"].isin(selected_recipes)]
            
            # Normalize values to 0-1 scale per metric for better radar comparability
            metrics = ["RecipeProtPer100Kcal", "RecipeKcal1Port", "UniqueIngredients", "AvgPortionsPerSave"]
            norm_df = df_selected.copy()
            for col in metrics:
                if col == 'RecipeKcal1Port':
                    min_val = radar_df[col].min()-100
                    max_val = radar_df[col].max()
                    norm_df[col] = (df_selected[col] - min_val) / (max_val - min_val)
                else :
                    min_val = radar_df[col].min()-1
                    max_val = radar_df[col].max()
                    norm_df[col] = (df_selected[col] - min_val) / (max_val - min_val)


            categories = ["Protein / 100 kcal", "Calories / Portion", "Unique Ingredients", "Avg Portions per Save"]


            fig = go.Figure()

            for i, row in norm_df.iterrows():
                values = row[metrics].values.tolist()
                percentages = [f"{round(v * 100)}%" for v in values]
                raw_vals = df_selected[df_selected["RecipeLabel"] == row["RecipeLabel"]][metrics].values.flatten().tolist()
                
                hover_text = [
                    f"{cat}<br>Value: {round(raw_val, 2)}<br>Normalized: {pct}<br>Recipe: {row['RecipeLabel']}"
                    for cat, raw_val, pct in zip(categories, raw_vals, percentages)
                ]
            
                # Close the loop for radar
                fig.add_trace(go.Scatterpolar(
                    r=values + [values[0]],
                    theta=categories + [categories[0]],
                    fill='toself',
                    name=row["RecipeLabel"],
                    text=hover_text + [hover_text[0]],
                    hoverinfo='text'
                ))

            # st.write(norm_df)

            fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 1]
                ) ),
            showlegend=True,
            width=700,
            height=600
            )

            viewTable = st.radio("View data in table?", ["No", "Yes"],key='VisualT9')
            if viewTable =='Yes':
                col1, col2 = st.columns([3,2])
                # Visual
                with col1:
                    st.plotly_chart(fig, use_container_width=True)
                    st.write(caption)
                # Data table
                with col2:

                    st.dataframe(norm_df.rename(columns={'RecipeLabel':'Recipe','UniqueIngredients':'# Unique Ingredients','RecipeKcal1Port':'# Kcal/Portion','RecipeProtPer100Kcal':'# Prot/100 Kcal','AvgPortionsPerSave':'Avg Portion/Logging'}).set_index("Recipe"), use_container_width=True)
            else:
                st.plotly_chart(fig, use_container_width=True)
                st.write(caption)


        else:
            st.info("Select at least one recipe to display the radar chart.")

    # Visual 10
    with st.expander("Ingredient Usage Frequency (Heatmap)"):
        st.markdown("""
        This heatmap shows **how frequently ingredients** are used **across all recipes**.
        
        It gives a quick overview of which ingredients are **most common** and can be expanded further by **grouping into categories** (e.g. protein, carbs, dairy).
        """)

        # Count occurrences of each ingredient in each category
        ingredient_counts = (
            da_df_per_recipe.groupby(["Ingredient_Cat", "IngredientLabel"])
            .size()
            .reset_index(name="Count")
            .sort_values(["Ingredient_Cat", "Count"], ascending=[True, False])
        )
        
        # Optional: limit number of recipes shown
        top_n = st.slider("Select how many top ingredients to show", min_value=5, max_value=30, value=10, step=1, key = 'slider_visual10')
        ingredient_counts = ingredient_counts.head(top_n).reset_index(drop=True)


        # Select All and Multi-Select for Recipes
        select_all = st.checkbox("Select All Ingredients", value=True, key='SelectAll_Visual10')
        all_ingredients = sorted(ingredient_counts["IngredientLabel"].dropna().unique())
        if select_all:
            selected_ingredients = all_ingredients
        else:
            selected_ingredients = st.multiselect(
            "Select Ingredient(s) to highlight:",
            options=all_ingredients,
            default=[]
            )
            
        if selected_ingredients:
            df_selected = ingredient_counts[ingredient_counts["IngredientLabel"].isin(selected_ingredients)]

        # --- Step 5: Altair Heatmap ---
        heatmap = alt.Chart(df_selected).mark_rect().encode(
            x=alt.X("Ingredient_Cat:N", title="Ingredient Category"),
            y=alt.Y("IngredientLabel:N", sort=alt.EncodingSortField(field="Count", order="descending"), title="Ingredient"),
            color=alt.Color("Count:Q", scale=alt.Scale(scheme="greens"), title="Usage Frequency"),
            tooltip=[
            alt.Tooltip("IngredientLabel:N", title="Ingredient"),
            alt.Tooltip("Ingredient_Cat:N", title="Category"),
            alt.Tooltip("Count:Q", title="# Times Used in Recipes")
            ]
        ).properties(
            width=600,
            height=400,
            title="Top Ingredients Usage Heatmap by Category"
        ).interactive()


        viewTable = st.radio("View data in table?", ["No", "Yes"],key='VisualT10')
        if viewTable =='Yes':
            col1, col2 = st.columns([3,2])
            # Visual
            with col1:
                st.altair_chart(heatmap, use_container_width=True)
                st.write(caption)
            # Data table
            with col2:
                st.dataframe(ingredient_counts.rename(columns={'IngredientLabel':'Ingredient','Ingredient_Cat':'Category','Count':'# Times Used in Recipes'}).set_index("Ingredient"), use_container_width=True)
        else:
            st.altair_chart(heatmap, use_container_width=True)
            st.write(caption)

    # Visual 11
    with st.expander("Ingredient Dependency Network"):
        st.markdown("This visual gives a instant indication of how the **ingredients relate to each other**.")
        st.markdown("The **thickness of a line** shows how often 2 ingredients **appear together in one recipe**.")

        da_df_per_recipe["IngredientLabel"] = da_df_per_recipe["IngredientLabel"].astype(str)

        # --- Step 1: Get top ingredients overall ---
        ingredient_usage = (
            da_df_per_recipe.groupby("IngredientLabel")
            .size()
            .reset_index(name="Count")
            .sort_values("Count", ascending=False)
        )

        ingredient_usage = (
            da_df_per_recipe.groupby("IngredientLabel")
            .size()
            .reset_index(name="Count")
            .sort_values("Count", ascending=False)
        )

        ingredient_usage["IngredientLabel"] = ingredient_usage["IngredientLabel"].astype(str)
        all_ingredients = sorted(ingredient_usage["IngredientLabel"].dropna().unique().tolist())

        top_n = st.slider("Top N ingredients by total usage", min_value=5, max_value=50, value=15, step=1, key="slider_topn_v11")

        # Decide ingredients to use
        if selected_ingredients:
            ingredients_to_use = selected_ingredients
        else:
            ingredients_to_use = ingredient_usage.head(top_n)["IngredientLabel"].tolist()

        # Filter to only those ingredients in recipes
        recipe_ingredients = (
            da_df_per_recipe[da_df_per_recipe["IngredientLabel"].isin(ingredients_to_use)]
            .groupby("Recipe")["IngredientLabel"]
            .apply(list)
            .reset_index(name='Ingredients')#(drop=True)
        )
 
        # --- Step 2: Build co-occurrence matrix ---
        edge_counter = Counter()
        for ing_list in recipe_ingredients["Ingredients"]:
            pairs = combinations(set(ing_list), 2 )
            for pair in pairs:
                edge_counter[tuple(sorted(pair) ) ] +=1

        edges_df = pd.DataFrame(
            [(i[0], i[1], count) for i, count in edge_counter.items()],
            columns=['Ingredient1', 'Ingredient2', 'Weight']
        )

        # --- Step 3: Build Network ---
        G = nx.Graph()
        for _, row in edges_df.iterrows():
            G.add_edge(row['Ingredient1'], row['Ingredient2'], weight=row['Weight'])

        pos = nx.spring_layout(G, k=0.5, iterations=50)
        x_nodes = [pos[node][0] for node in G.nodes()]
        y_nodes = [pos[node][1] for node in G.nodes()]

        edge_trace = []
        for edge in G.edges(data=True):
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            weight = edge[2]['weight']
            edge_trace.append(
            go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                mode='lines',
                line=dict(width=weight, color='rgba(0,0,0,0.2)'),
                hoverinfo='none'
            )
            )

        node_trace = go.Scatter(
            x=x_nodes,
            y=y_nodes,
            mode='markers+text',
            text=list(G.nodes()),
            textposition="top center",
            hoverinfo='text',
            marker=dict(
            size=10,
            color='skyblue',
            line=dict(width=1, color='DarkSlateGrey')
            )
        )

        fig = go.Figure(data=edge_trace + [node_trace],
                    layout=go.Layout(
                    # title_x=0.5,
                    title='',
                    showlegend=False,
                    hovermode='closest',
                    margin=dict(b=20, l=5, r=5, t=40),
                    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
                    ))

        # Show results
        viewTable = st.radio("View data in table?", ["No", "Yes"], key='VisualT11')
        if viewTable == 'Yes':
            col1, col2 = st.columns([3, 2])
            with col1:
                st.plotly_chart(fig, use_container_width=True)
                st.write(caption)
            with col2:
                st.dataframe(edges_df.rename(columns={'Ingredient1': 'Ingredient 1', 'Ingredient2': 'Ingredient 2'}), use_container_width=True)
        else:
            st.plotly_chart(fig, use_container_width=True)
            st.write(caption)

###########################################################################################################
# END OF VISUALS
###########################################################################################################

    tab_rec_by_date, tab_comb_by_date, tab_sum_all = st.tabs([
        "Recipes by Date",
        "Combined by Date", 
        "Sum of All Ingredients for All Dates"])

    recipes_by_date = (
        da_df_per_recipe.groupby(["ExportDate", "RecipeLabel", "Portion"])
        .size()
        .reset_index(name="Frequency")  )

    with tab_rec_by_date:
        for export_date in sorted(recipes_by_date["ExportDate"].unique(), reverse=True):
            df_recipe_date = da_df_per_recipe[da_df_per_recipe["ExportDate"]==export_date]
            with st.expander(f"Recipes for {export_date.strftime('%B %d, %Y')}", expanded=False):
                df_table = df_recipe_date[ ["RecipeLabel", "Portion","IngredientLabel","Amount","Unit"] ]
                st.dataframe(df_table.rename(columns={'RecipeLabel':'Recipe','IngredientLabel':'Ingredient'}).set_index("Recipe"), use_container_width=True)

    with tab_comb_by_date:
        grouped_by_date = da_df_combined.groupby("ExportDate")
        
        for export_date, group in sorted(grouped_by_date, reverse=True):
            group_df = (
            group.groupby(["IngredientLabel", "Unit"], as_index=False)["Amount"]
            .sum()
            .sort_values(by="IngredientLabel")
            )
            with st.expander(f"Combined ingredients for {export_date.strftime('%B %d, %Y')}", expanded=False):
                st.dataframe(group_df[["IngredientLabel", "Amount", "Unit"] ].rename(columns={'IngredientLabel':'Ingredient'}).set_index("Ingredient"), use_container_width=True)


    with tab_sum_all:
        st.dataframe(da_df_combined_group[["IngredientLabel", "sum", "Unit"]].rename(columns={'IngredientLabel':'Ingredient'}).set_index("Ingredient").rename(columns={'sum':'Sum of Amount'}) , use_container_width=True)
