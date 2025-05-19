import streamlit as st
import pandas as pd
import os
import io
from main import * #RecipeDict, IngredientDict, get
from datetime import date, datetime
import altair as alt
import plotly.graph_objects as go
import networkx as nx
from itertools import combinations
from collections import Counter
import random  
from Colruty_scraping.colruyt_scraper_price import *

#CMD: streamlit run Grocery_list\streamlit_app.py

# --- Configure page layout ---
st.set_page_config(layout='wide', initial_sidebar_state='expanded')
col_seq=["Ingredient", "Amount", "Unit"] 
# --- Navigation ---
page = st.radio("Navigation", ["Grocery List Maker", "Data Analysis"], horizontal=True)

current_month = str(datetime.now().month)
seasonal_this_month = set(seasonal_ingredients.get(current_month, []))
 
#LOAD DATA FROM LOG FILE
log_file_path = "Grocery_List/Excel_files/Log/Grocery_List_Log.xlsx"


# --- Initialize session state for recipe selections ---
if "selected_recipes" not in st.session_state:
    st.session_state.selected_recipes = {}
if "extra_rows" not in st.session_state:
    st.session_state.extra_rows = []
if "next_extra_id" not in st.session_state:
    st.session_state.next_extra_id = 0
st.sidebar.title("Settings")


# --- GROCERY LIST MAKER ---
if page == "Grocery List Maker":
    st.title("Grocery List Maker! A La Esh!")
    # st.sidebar.title("Settings")

    with st.expander('Choose recipes and portions'):
        for recipe in RecipeDict:
            # st.session_state.pop(f'portion_{recipe}', None)
            default_use = recipe in st.session_state.selected_recipes
            use = st.checkbox(RecipeDict[recipe].getLabel(), key=f'chk_{recipe}', value=default_use)
            if use:
                # default_portion = st.session_state.selected_recipes.get(recipe, 1)
                default_portion = max(st.session_state.selected_recipes.get(recipe, 1),1)
                portion = st.number_input(
                    f"Portion for {RecipeDict[recipe].getLabel()}",
                    min_value=0,
                    max_value=1000,
                    value=default_portion,
                    step=1,
                    key=f'portion_{recipe}'
                )
                st.session_state.selected_recipes[recipe] = portion
            else:
                st.session_state.selected_recipes.pop(recipe, None)

    selected = st.session_state.selected_recipes


    # if selected:
    ingredient_options = {
        ingr_value.getLabel(): (ingr_key, ingr_value)
        for ingr_key, ingr_value in IngredientDict.items()
    }

    suggestion_type = st.sidebar.radio("Need help picking recipes?", [
    "Nope! I'm good!", 
    "For busy evenings",
    "Focus on lighter meals",
    "Go full veggie",
    "Show favorites"
    ], key='sidebar_radio_help_picking')

    if suggestion_type == "Show favorites":
        if not os.path.exists(log_file_path):
            st.warning("Log file not found. No data to analyze yet.")
        else:
            # Load data
            df_log_per_recipe = pd.read_excel(log_file_path, sheet_name="Log Per Recipe")
            # Ensure ExportDate is in date format
            df_log_per_recipe["ExportDate"] = pd.to_datetime(df_log_per_recipe["ExportDate"])
            df_unique_rec_per_date = df_log_per_recipe.drop_duplicates(subset=["Recipe", "ExportDate", "Portion"]).reset_index(drop=True)
            df_sum_portion_per_recipe = df_unique_rec_per_date.groupby("Recipe", as_index=False)["Portion"].sum().sort_values(by="Recipe")
            df_freq_recipe = df_log_per_recipe.groupby("Recipe", as_index=False)["ExportDate"].nunique().rename(columns={"ExportDate":"Frequency"})

            df_fav_recipes = df_sum_portion_per_recipe.merge(df_freq_recipe, on="Recipe")
            df_fav_recipes['AvgPortion'] = df_fav_recipes['Portion'] / df_fav_recipes['Frequency']
            df_fav_recipes = df_fav_recipes.sort_values(by='AvgPortion',ascending=False).head(5)

            st.sidebar.markdown("These recipes have been **logged the most**:")
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
            (name, getRecipeKcal(name) )
            for name in RecipeDict.keys()
        ]
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
        selected_veggie_recipes = random.sample(veggie_recipes, k=min(5, len(veggie_recipes)))

        st.sidebar.markdown("Try these randomly chosen **veggie** recipes:")
        for name in selected_veggie_recipes:
            recipe = getRecipe(name)
            label = recipe.getLabel() if recipe else name
            st.sidebar.markdown(f"- {label}")


    extra_ingredients = []
    st.sidebar.subheader("Add Extra Ingredients")
    if st.sidebar.radio(f"Add extra stuff? _Ingredients with ⭐ are seasonal!_", ["No", "Yes"]) == "Yes":

        def add_extra_row():
            st.session_state.extra_rows.append(st.session_state.next_extra_id)
            st.session_state.next_extra_id += 1

        st.sidebar.button("\u2795 Add Extra Ingredient", on_click=add_extra_row , key="add_extra_sidebar")

        if "row_to_remove" in st.session_state:
            row_id = st.session_state.pop("row_to_remove")
            if row_id in st.session_state.extra_rows:
                st.session_state.extra_rows.remove(row_id)
                st.session_state.pop(f'ing_{row_id}',None)
                st.session_state.pop(f'portion_{row_id}',None)
        

        rows_to_remove = [] 

        rows_to_keep = []
        used_ingredients =[]
        for row_id in st.session_state.extra_rows:
            cols = st.columns([4, 3, 2, 1])

            available_ingredients = sorted(
                [label for label in ingredient_options if label not in used_ingredients]
                )
            
            if not available_ingredients:
                st.warning("No more ingredients to add.")
                break  # or continue to next row

            
            # Build display name map: bold seasonal ingredients
            seasonal_ingr_display = {}
            for ing in available_ingredients:
                ing_upper = ing.replace(" ", "").upper()
                if ing_upper in seasonal_this_month:
                    seasonal_ingr_display[f"{ing} ⭐"] = ing  # bold version
                else:
                    seasonal_ingr_display[ing] = ing

            select_options = ["Select an ingredient..."] + list(seasonal_ingr_display.keys()) #+ available_ingredients
            prev_selection = st.session_state.get(f"ing_{row_id}", "Select an ingredient...")
            # Convert previous selection to bold if needed
            for display, original in seasonal_ingr_display.items():
                if original == prev_selection:
                    prev_selection_display = display
                    break
            else:
                prev_selection_display = "Select an ingredient..."



            unit_options =['u','g']
            # Make sure previous selection is still valid
            if prev_selection in select_options and prev_selection != 'Select an ingredient...':
                default_index = select_options.index(prev_selection)
            else:
                default_index = 0  # fallback to first option

            ingr_name = cols[0].selectbox(
                "Extra Ingredient",
                options=select_options,
                index=default_index,#0,
                key=f"ing_{row_id}"
            )
            
            portion = cols[1].number_input(
                "Amount",
                min_value=0,
                max_value=1000,
                step=1,
                value=1,
                key=f"portion_{row_id}"
            )

            unit = cols[2].selectbox(
                "Type of Units",
                options=unit_options,
                index=0,#default_index,#0,
                key=f"TypeOfUnit_{row_id}"
            )

            if cols[2].button("🗑️", key=f"remove_{row_id}"):
                st.session_state.row_to_remove = row_id
            else: 
                rows_to_keep.append(row_id)

                # if not remove:
                if portion > 0 and ingr_name and ingr_name != "Select an ingredient...":
                    ingr_name = ingr_name.replace(" ⭐", "")  # <- Strip star
                    if ingr_name in ingredient_options: 
                        ingr_key, ingr_obj = ingredient_options[ingr_name]
                        extra_ingredients.append({
                                        "Ingredient": ingr_obj.getLabel(),
                                        "IngredientKey": ingr_key,
                                        "Unit": unit,
                                        "Amount": portion
                                })
                        used_ingredients.append(ingr_name)



        st.session_state.extra_rows = rows_to_keep

        # --- Extra add button (under ingredient inputs) ---
        st.button("➕ Add Extra Ingredient", on_click=add_extra_row, key="add_extra_bottom")


    # priceurls = []
    # price_file = "Grocery_List/Excel_files/Log/Scraping_prices.xlsx"
    # # Extract URLs from your ingredients or load from your data file

    # for ingr in IngredientDict:
    #     priceurls.append( {ingr:IngredientDict[ingr].priceurl})


    # # st.write(priceurls[:3] ) #aardbei ,appel, anjovis
    # # Sidebar UI
    # st.sidebar.subheader("Price Updater")
    # if st.sidebar.button("Update Prices"):
    #     st.sidebar.info("Updating prices... This will take a while.")
    #     # Call your scraping function with all URLs
    #     df_prices = scrape_all_prices(priceurls[:5], "Grocery_List/Excel_files/Log/Scraping_prices.xlsx")
    #     st.sidebar.success("Price update complete! Saved to Scraping_prices.xlsx")

    # # Later in the app, you can read the prices file without scraping again
    # if price_file.exists():
    #     df_prices = pd.read_excel(price_file)
    #     st.write("Prices loaded from file:")
    #     st.dataframe(df_prices)
    # else:
    #     st.warning("Price data not found. Please click 'Update Prices' in the sidebar to scrape prices.")

        # st.write(df_prices )

    st.sidebar.subheader("Display Options")
    tab1, tab2 = st.tabs(["All Ingredients", "Per Recipe"])
    output_mode = st.sidebar.radio("Export the recipes?", ["View Here", "Export to Excel"])


    all_data = []
    concatDF = []

    for recipe, portion in selected.items():
        data = RecipeDict[recipe].toDataFrameRows(portion)
        df = pd.DataFrame(data)

        df_export = df.copy()
        df_export.insert(0, 'Recipe', recipe.ljust(12))
        df_export.insert(1, 'Portion', portion)
        concatDF.append(df_export)


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
                # st.dataframe(df.set_index('Ingredient'), use_container_width=True)



    if output_mode == "Export to Excel":
        buffer = io.BytesIO()
        today = date.today().isoformat()
        file_path = f'Grocery_List\Excel_files\Export\Grocery_List_{today}.xlsx'
        log_file_path = 'Grocery_List\Excel_files\Log\Grocery_List_Log.xlsx'

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            combined.to_excel(writer, index=False, sheet_name="Combined")
            pd.concat(concatDF, ignore_index=True).to_excel(writer, index=False, sheet_name="Per Recipe")

        # Save to disk
        with open(file_path, "wb") as f:
            f.write(buffer.getvalue())

        st.sidebar.download_button(
            label="Download Excel File",
            data=buffer.getvalue(),
            file_name=file_path,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        per_recipe_log = pd.concat(concatDF, ignore_index=True)
        per_recipe_log['ExportDate'] = today
        combined_log = combined.copy()
        combined_log['ExportDate'] = today

        if os.path.exists(log_file_path):
            prev_per_recipe_log = pd.read_excel(log_file_path, sheet_name="Log Per Recipe")
            prev_combined_log = pd.read_excel(log_file_path, sheet_name="Log Combined")

            prev_per_recipe_log = prev_per_recipe_log[prev_per_recipe_log['ExportDate'] != today]
            prev_combined_log = prev_combined_log[prev_combined_log['ExportDate'] != today]

            updated_per_recipe_log = pd.concat([prev_per_recipe_log, per_recipe_log], ignore_index=True)
            updated_combined_log = pd.concat([prev_combined_log, combined_log], ignore_index=True)
        else:
            updated_per_recipe_log = per_recipe_log
            updated_combined_log = combined_log

        with pd.ExcelWriter(log_file_path, engine='openpyxl', mode='w') as log_writer:
            updated_per_recipe_log.to_excel(log_writer, index=False, sheet_name='Log Per Recipe')
            updated_combined_log.to_excel(log_writer, index=False, sheet_name='Log Combined')

# --- DATA ANALYSIS PAGE (to be implemented) ---
elif page == "Data Analysis":
    st.title("Grocery List Analysis")
    st.header("Groceries Analysis")
    
    log_file_path = "Grocery_List/Excel_files/Log/Grocery_List_Log.xlsx"

    if not os.path.exists(log_file_path):
        st.warning("Log file not found. No data to analyze yet.")
    else:
        # Load data
        df_log_combined = pd.read_excel(log_file_path, sheet_name="Log Combined")
        df_log_per_recipe = pd.read_excel(log_file_path, sheet_name="Log Per Recipe")

        # Data Cleanup
        # Make sure ExportDate is in date format
        df_log_combined["ExportDate"] = pd.to_datetime(df_log_combined["ExportDate"])
        df_log_per_recipe["ExportDate"] = pd.to_datetime(df_log_per_recipe["ExportDate"])
        
        # Create Date Columns
        df_log_combined["DateOnly"] = df_log_combined["ExportDate"].dt.date
        df_log_combined["Year"] = df_log_combined["ExportDate"].dt.year
        df_log_combined["MonthNum"] = df_log_combined["ExportDate"].dt.month
        df_log_combined["MonthName"] = df_log_combined["ExportDate"].dt.strftime("%b")

        df_log_per_recipe["DateOnly"] = df_log_per_recipe["ExportDate"].dt.date
        df_log_per_recipe["Year"] = df_log_per_recipe["ExportDate"].dt.year
        df_log_per_recipe["MonthNum"] = df_log_per_recipe["ExportDate"].dt.month
        df_log_per_recipe["MonthName"] = df_log_per_recipe["ExportDate"].dt.strftime("%b")

        # Global Date Filter
        unique_dates = sorted(df_log_combined["DateOnly"].unique(), reverse=True)

        all_years = sorted(df_log_combined["Year"].unique())
        all_months = sorted(df_log_combined["MonthNum"].unique())
        all_month_names = df_log_combined.drop_duplicates("MonthNum")[["MonthNum", "MonthName"]].sort_values("MonthNum")["MonthName"].tolist()
        all_dates = sorted(df_log_combined["DateOnly"].unique())

        st.sidebar.header("Date Filters")

        all_dates_checked = st.sidebar.checkbox("All Dates", value=True)
        if not all_dates_checked:
            selected_years = st.sidebar.multiselect("Year", options=all_years, default=all_years)
            selected_months = st.sidebar.multiselect("MonthNum", options=all_month_names, default=all_month_names)
            
            # Filter dates by selected years and months
            # Map month names back to month numbers for filtering
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
        else:
            selected_years = all_years
            selected_months = all_month_names
            selected_dates = all_dates


        # Copy Dataframes (always keep the original)
        f_df_combined = df_log_combined[df_log_combined["DateOnly"].isin(selected_dates)].copy()
        f_df_per_recipe = df_log_per_recipe[df_log_per_recipe["DateOnly"].isin(selected_dates)].copy()

        f_df_per_recipe["Ingredient_Cat"] = f_df_per_recipe["Ingredient"].apply(categorize_ingredient)

        #Get RecipeLabel & IngredientLabel (first normalize key)
        f_df_per_recipe['IngredientLabel'] = f_df_per_recipe['Ingredient']
        f_df_per_recipe['IngredientKey'] = f_df_per_recipe['IngredientKey'].str.strip().str.upper().str.replace(" ","", regex=False)
        f_df_per_recipe['RecipeKey'] = f_df_per_recipe['Recipe'].str.strip().str.upper()
        f_df_per_recipe['RecipeLabel'] = f_df_per_recipe['Recipe'].map(getRecipeLabel)

        f_df_combined['IngredientKey'] = f_df_combined['Ingredient'].str.strip().str.upper().str.replace(" ","", regex=False)
        f_df_combined['IngredientLabel'] = f_df_combined['Ingredient'].map(lambda r: IngredientDict[r].getLabel() if r in IngredientDict else r)


        # # Filter by Ingredient or Recipe
        # ingredient_filter = st.sidebar.selectbox("Focus on Ingredient", ["All"] + sorted(df_log_combined["Ingredient"].unique()))
        # if ingredient_filter != "All":
        #     f_df_combined = f_df_combined[f_df_combined["Ingredient"] == ingredient_filter]


            # Group and sum
        result_comb_df = (
                f_df_combined.groupby(["IngredientLabel", "Unit"], as_index=False)["Amount"]
                #.sum()
                .agg(['sum','size'])
                .sort_values(by="IngredientLabel")
            )

        result_pr_df = (
                f_df_per_recipe.groupby(["RecipeLabel","Portion", "IngredientLabel","Unit"], as_index=False)["Amount"]
                #.sum()
                .agg(['sum','size'])
                .sort_values(by="RecipeLabel")
            )

        # Combined : Per ingredient
        result_comb_df['IngrKcal'] = result_comb_df.apply(
                lambda row : getIngrKcal( row['IngredientLabel'], row['sum'], row['Unit'] ),
                axis = 1)

        result_comb_df['IngrProt'] = result_comb_df.apply(
                lambda row : getIngrProt( row['IngredientLabel'], row['sum'], row['Unit'] ), #Sum ipv Amount
                axis = 1)
            
        # Per Recipe : Per recipe &  Per ingredient
        result_pr_df['IngrKcal'] = result_pr_df.apply(
                lambda row : getIngrKcal( row['IngredientLabel'], row['sum'], row['Unit'] ),
                axis = 1)

        result_pr_df['IngrProt'] = result_pr_df.apply(
                lambda row : getIngrProt( row['IngredientLabel'], row['sum'], row['Unit'] ),
                axis = 1)

        result_pr_df['RecipeKcal'] = result_pr_df.apply(
                lambda row : getRecipeKcal( row['RecipeLabel'], row['Portion'] ),
                axis = 1)

        result_pr_df['RecipeProt'] = result_pr_df.apply(
                lambda row : getRecipeProt( row['RecipeLabel'], row['Portion'] ),
                axis = 1)
            
        result_pr_df['RecipeKcal1Port'] = result_pr_df.apply(
                lambda row : getRecipeKcal( row['RecipeLabel'], 1 ),
                axis = 1)

        result_pr_df['RecipeProt1Port'] = result_pr_df.apply(
                lambda row : getRecipeProt( row['RecipeLabel'], 1),
                axis = 1)
            
        result_pr_df['RecipeProtPer100Kcal'] = result_pr_df.apply(
                lambda row : getRecipeProtPer100Kcal( row['RecipeLabel'] ),
                axis = 1)
            
        ################################################################
            # VISUALS
        ################################################################
                    
        caption = 'Select ingredients from dropdown above. Hover for details.'
        # Visual 1 : Time Line Chart : Show ingredient quantities in units over time
        with st.expander("Ingredient Usage Over Time"):
            st.markdown(f'This line chart shows how many **units of an ingredient** have been saved over **time**. Each ingredient can have 2 lines (stacked), together they show **total units**:')
            st.markdown(f'- Full line: How many units were saved as part of a recipe')
            st.markdown(f'- Dash line: How many units were saved as an extra ingredient')

            # Step 1: Convert both dataframes to unit 'u'
            f_df_per_recipe_u = convert_to_units(f_df_per_recipe, unit_col="Unit", amount_col="Amount")
            f_df_combined_u = convert_to_units(f_df_combined, unit_col="Unit", amount_col="Amount")

            # Step 2: Group both by ExportDate and Ingredient
            pr_grouped = (
                f_df_per_recipe_u.groupby(["ExportDate", "IngredientLabel"])["Amount"]
                .sum()
                .reset_index()
                .rename(columns={"Amount": "UsageInRecipeCount"})
            )

            comb_grouped = (
                f_df_combined_u.groupby(["ExportDate", "IngredientLabel"])["Amount"]
                .sum()
                .reset_index()
                .rename(columns={"Amount": "TotalCombinedCount"})
            )

            # Step 3: Merge and calculate extra usage
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
                default=[]  # or you could pre-select a few if desired
                )

            # Filter data by selected ingredients
            filtered_data = merged[merged["IngredientLabel"].isin(selected_ingredients)]

            viewTable = st.radio("View data in table?", ["No", "Yes"], key="Visual1")

            base = alt.Chart(filtered_data).encode(
                x=alt.X("ExportDate:T", title="Date"),
                color=alt.Color("IngredientLabel:N", legend=alt.Legend(title="Ingredient"))

            )

            unique_dates = filtered_data["ExportDate"].nunique()

            if unique_dates > 1:
                recipe_line = base.mark_line(strokeWidth=2).encode(
                y=alt.Y("UsageInRecipeCount:Q", title="Ingredient Usage Count"),
                tooltip=["Date", alt.Tooltip("IngredientLabel:N",title='Ingredient'), alt.Tooltip("UsageInRecipeCount:Q", title="Recipe Count")]
                )

                total_line = base.mark_line(strokeDash=[5, 5], strokeWidth=2).encode(
                y=alt.Y("TotalUsage:Q"),
                tooltip=["Date", alt.Tooltip("IngredientLabel:N",title='Ingredient'), alt.Tooltip("TotalUsage:Q", title="Total Count")]
                )
            else:
                recipe_line = base.mark_point(filled=True, size=100).encode(
                y=alt.Y("UsageInRecipeCount:Q", title="Ingredient Usage Count"),
                tooltip=["Date", alt.Tooltip("IngredientLabel:N",title='Ingredient'), alt.Tooltip("UsageInRecipeCount:Q", title="Recipe Count")]
                )

                total_line = base.mark_point(shape="triangle", size=100).encode(
                y=alt.Y("TotalUsage:Q"),
                tooltip=["Date", alt.Tooltip("IngredientLabel:N",title='Ingredient'), alt.Tooltip("TotalUsage:Q", title="Total Count")]
                )


                
            # Show chart and optionally the table
            if viewTable == "Yes":
                col1, col2 = st.columns([3, 2])
                with col1:
                    st.altair_chart(recipe_line + total_line, use_container_width=True)
                    st.write(caption)#st.caption("Select ingredients from dropdown above. Hover for details.")
                with col2:
                    table = filtered_data[["IngredientLabel", "Date", "UsageInRecipeCount", "UsageExtraCount", "TotalUsage"]]
                    table = table.rename(columns={
                    'IngredientLabel': 'Ingredient',
                    'TotalUsage': 'Total Units',
                    'UsageExtraCount': 'Extra Ingredient (u)',
                    'UsageInRecipeCount': 'Part of Recipe (u)'
                })
                    st.dataframe(table.set_index("Ingredient"), use_container_width=True)
            else:
                st.altair_chart(recipe_line + total_line, use_container_width=True)
                st.write(caption)#st.caption("Select ingredients from dropdown above. Hover for details.")

        # Visual 2 : Time Line Chart : Show recipe portions over time
        with st.expander("Recipe Portions Over Time"): 
            st.markdown(f'This chart shows how **portions per recipe**  change over **time**.')

            # Get portion once per recipe per date
            recipe_ts = (
                f_df_per_recipe.groupby(["DateOnly", "RecipeLabel"])["Portion"]
                .first()
                .reset_index()
            )

            # Select All and Multi-Select for Recipes
            select_all_recipes = st.checkbox("Select All Recipes", value=True, key='SelectAll_Visual2')
            all_recipes = sorted(recipe_ts["RecipeLabel"].dropna().unique())
            if select_all_recipes:
                selected_recipes = all_recipes
            else:
                selected_recipes = st.multiselect(
                "Select Recipe(s) to highlight:",
                options=all_recipes,
                default=[]
                )

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
                "Portion": [None, None]
            })

            pad_y_df = pd.DataFrame({
                "DateOnly": [None, None],
                "RecipeLabel": ["_PADDINGY", "_PADDINGY"],
                "Portion": [0, max_y + paddingPortion]
            })

            recipe_ts_padded = pd.concat([recipe_ts_filtered, pad_df], ignore_index=True)
            recipe_ts_padded = pd.concat([recipe_ts_padded, pad_y_df], ignore_index=True)

            recipe_ts_padded["RecipeLegend"] = recipe_ts_padded["RecipeLabel"].where(
                ~recipe_ts_padded["RecipeLabel"].str.startswith("_")
            )

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
                .cumcount()
            )
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
                    st.write(caption)#st.caption(f'Select ingredients from dropdown above. Hover for details.')
                with col2:
                    recipe_ts_filtered["DateOnly"] = pd.to_datetime(recipe_ts_filtered["DateOnly"]).dt.strftime('%B %d, %Y')
                    st.dataframe(recipe_ts_filtered.rename(columns={'RecipeLabel':'Recipe','DateOnly': 'Date'}).set_index("Recipe"), use_container_width=True)

            else:
                st.altair_chart(chart, use_container_width=True)
                st.write(caption)#st.caption(f'Select ingredients from dropdown above. Hover for details.')

        # Visual 4 : Bar chart : Quick overview of Prot / 100kcal for recipes
        with st.expander("Protein per 100 Kcal for Recipes"):
            st.markdown('This bar chart gives a quick overview of which **recipes** have a higher or lower **protein count per 100 kcal**.')
            scatter_data = result_pr_df.drop_duplicates(subset="RecipeLabel")[["RecipeLabel", "RecipeProtPer100Kcal"]]

            # Select All and Multi-Select for Recipes
            select_all = st.checkbox("Select All Recipes", value=True, key='SelectAll_Visual4')
            all_recipes = sorted(scatter_data["RecipeLabel"].dropna().unique())
            if select_all:
                selected_recipes = all_recipes
            else:
                selected_recipes = st.multiselect(
                "Select Recipe(s) to highlight:",
                options=all_recipes,
                default=[]
                )

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
                max_y  = 1 # fallback in case no recipes are selected

            viewTable = st.radio("View data in table?", ["No", "Yes"],key='Visual5')
            if viewTable =='Yes':
                col1, col2 = st.columns([3,2])
                # Visual
                with col1:
                    chart = alt.Chart(filtered_recipes_result).mark_bar().encode(
                        x=alt.X("Recipe:N",
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
                    st.altair_chart(chart, use_container_width=True)
                    st.write(caption)
                # Data table
                with col2:
                    st.dataframe(filtered_recipes_result.rename(columns={'RecipeLabel':'Recipe','RecipeProtPer100Kcal':'Prot / 100 Kcal'}).set_index("Recipe"), use_container_width=True)
            else:
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
                st.altair_chart(chart, use_container_width=True)
                st.write(caption)

        # Visual 8 : Ingredient use over time
        with st.expander("Top Recipes by Number of Unique Ingredients"):
            st.markdown("This bar chart shows which recipes have the highest number of **unique ingredients**, indicating their complexity or variety.")

            # Count unique ingredients per recipe
            unique_ingredients_df = f_df_per_recipe.groupby("RecipeLabel")["IngredientLabel"].nunique().reset_index(name="UniqueIngredients")

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
                default=[]
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
            # portion_df = f_df_per_recipe[["Recipe", "Portion", "ExportDate"]].drop_duplicates()
            portion_df = f_df_per_recipe.groupby(["RecipeLabel", "ExportDate","Portion"]).size().reset_index()
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
                default=[]
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
                max_x, max_y = 1, 1  # fallback in case no recipes are selected

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
            ingredients_df = f_df_per_recipe.groupby("RecipeLabel")["Ingredient"].nunique().reset_index(name="UniqueIngredients")            # Drop duplicates to avoid multiple rows per recipe
            scatter_df = result_pr_df[["RecipeLabel", "RecipeKcal1Port", "RecipeProtPer100Kcal"]].drop_duplicates()

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
                default=[]
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
            unique_ingr_df = f_df_per_recipe.groupby("RecipeLabel")["IngredientLabel"].nunique().reset_index(name="UniqueIngredients")            # Drop duplicates to avoid multiple rows per recipe
            times_logged_df = f_df_per_recipe.drop_duplicates(subset=["RecipeLabel", "ExportDate"])
            times_logged_df = times_logged_df.groupby("RecipeLabel").size().reset_index(name="TimesLogged")
 
            # Step 3: Average portions per save
            portion_df = f_df_per_recipe.groupby(["RecipeLabel", "ExportDate","Portion"]).size().reset_index()#["Portion"].sum().reset_index()
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
                default=[]
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
            unique_ingr_df = f_df_per_recipe.groupby("RecipeLabel")["IngredientLabel"].nunique().reset_index(name="UniqueIngredients")
            
            # Nutrition data
            nutrition_df = result_pr_df[["RecipeLabel", "RecipeKcal1Port", "RecipeProtPer100Kcal"]].drop_duplicates()
            
            # Average portions per save
            portion_df = f_df_per_recipe.groupby(["RecipeLabel", "ExportDate", "Portion"]).size().reset_index()
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
                default=[]
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
                f_df_per_recipe.groupby(["Ingredient_Cat", "IngredientLabel"])
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

            f_df_per_recipe["IngredientLabel"] = f_df_per_recipe["IngredientLabel"].astype(str)

            # --- Step 1: Get top ingredients overall ---
            ingredient_usage = (
                f_df_per_recipe.groupby("IngredientLabel")
                .size()
                .reset_index(name="Count")
                .sort_values("Count", ascending=False)
            )

            ingredient_usage = (
                f_df_per_recipe.groupby("IngredientLabel")
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
                f_df_per_recipe[f_df_per_recipe["IngredientLabel"].isin(ingredients_to_use)]
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
            # for ingredients in recipe_ingredients:
            #     pairs = combinations(set(ingredients), 2)
            #     for pair in pairs:
            #         edge_counter[tuple(sorted(pair))] += 1

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

        # filtered_csv = f_df_combined.to_csv(index=False).encode("utf-8")
        # st.sidebar.download_button(
        #     "Download Filtered Data",
        #     data=filtered_csv,
        #     file_name="filtered_grocery_data.csv",
        #     mime="text/csv"
        # )

        # with st.expander(f"Sum of Ingredients for {len(selected_dates)} Date(s)", expanded=False):
        #      st.dataframe(result_comb_df.set_index("Ingredient"), use_container_width=True)
        
        tab_rec_by_date, tab_comb_by_date, tab_sum_all = st.tabs([
            "Recipes by Date",
            "Combined by Date", 
            "Sum of All Ingredients for All Dates"
        ])

        recipes_by_date = (
            f_df_per_recipe.groupby(["ExportDate", "RecipeLabel", "Portion"])
            .size()
            .reset_index(name="Frequency")  # Frequency can help spot repeated use in logs
        )

        with tab_rec_by_date:
            for export_date in sorted(recipes_by_date["ExportDate"].unique(), reverse=True):
                with st.expander(f"Recipes for {export_date.strftime('%B %d, %Y')}", expanded=False):
                    day_data = recipes_by_date[recipes_by_date["ExportDate"] == export_date][["RecipeLabel", "Portion"]]
                    st.dataframe(day_data.set_index("RecipeLabel"), use_container_width=True)


        with tab_comb_by_date:
            grouped_by_date = f_df_combined.groupby("ExportDate")
            
            for export_date, group in grouped_by_date:
                group_df = (
                group.groupby(["IngredientLabel", "Unit"], as_index=False)["Amount"]
                .sum()
                .sort_values(by="IngredientLabel")
                )
                with st.expander(f"Combined ingredients for {export_date.strftime('%B %d, %Y')}", expanded=False):
                    st.dataframe(group_df[col_seq].set_index("IngredientLabel"), use_container_width=True)

        with tab_sum_all:
            st.dataframe(result_comb_df[["IngredientLabel", "sum", "Unit"]].set_index("IngredientLabel").rename(columns={'sum':'Sum of Amount'}) , use_container_width=True)
