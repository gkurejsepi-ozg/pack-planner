#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Apr 28 13:23:12 2025
@author: gkurejsepi
"""
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

#%%% Meta updates
Title = "Mouse Packer v3.5"

# Changelog
Changelog = """
V3.5 changelog
- Updated to use xlsx instead of CSV
- Removed assign_shippers_v2: Deprecated function that was replaced by assign_shippers_v3
- Changed searching by age from "find nearest" to "find nearest =<7 days apart for age difference in the shipper, otherwise new shipper"
- assign_shippers_v3 updated:
  - Included packing by cohort, so now it can handle multiple cohorts
  - Added ShipperCohortIndex to assist with this and compartments assignments
- assign_compartments updated:
    - Included cohort in the criteria. It will now assign ShipperCompartments by cohort, and reset when it comes to a new cohort
- UI updated:
    - Collapsed Pack Plan into a box
    - Collpased Age Spread in days into a box
    - Added collapsed box that displays this changelog
"""

#%%%

# Functions 
def sort_genotype_gender(df):
    """Sorts dataframe by Genotype and Animal Gender (males first, then females)."""
    df = df.sort_values(by=['Genotype', 'Animal Gender', 'Cage', 'Age in Days'], ascending=[True, True, True, True]).reset_index(drop=True)
    return df

def extract_ear_tag(animal_id):
    """Extracts the ear tag from the Animal ID (3rd and 2nd last characters)."""
    return animal_id[-3:-1] if isinstance(animal_id, str) and len(animal_id) >= 3 else ""
    """Assign animals to shippers by grouping to minimize number of shippers while respecting constraints."""
    shippers = []  # List of shippers, each is a list of animals
    shipper_id = 1

    # Group animals by Genotype, Gender, and Cage, larger groups first
    grouped = df.groupby(['Genotype', 'Animal Gender', 'Cage'])

    # Sort groups largest first
    group_list = sorted(grouped, key=lambda x: len(x[1]), reverse=True)

    for (genotype, gender, cage), group_df in group_list:
        animals = group_df.to_dict('records')

        # Try to fit the whole group into an existing shipper
        assigned = False
        for shipper in shippers:
            if (len(shipper) + len(animals) <= 5 and
                all(a['Animal Gender'] == gender for a in shipper) and
                all(a['Genotype'] == genotype for a in shipper) and
                (gender == 'F' or all(a['Cage'] == cage for a in shipper if a['Animal Gender'] == 'M')) and
                not any(extract_ear_tag(a['Animal Code']) in [extract_ear_tag(b['Animal Code']) for b in shipper] for a in animals)):
                
                # Add animals to this shipper
                for a in animals:
                    a['Ear Tag'] = extract_ear_tag(a['Animal Code'])
                    a['ShipperIndex'] = shippers.index(shipper) + 1
                    shipper.append(a)
                assigned = True
                break

        if not assigned:
            # Start a new shipper
            new_shipper = []
            for a in animals:
                a['Ear Tag'] = extract_ear_tag(a['Animal Code'])
                a['ShipperIndex'] = shipper_id
                new_shipper.append(a)
            shippers.append(new_shipper)
            shipper_id += 1

    # Flatten shippers into a DataFrame
    output_data = [animal for shipper in shippers for animal in shipper]
    return pd.DataFrame(output_data)

def assign_shippers_v4(df):
    """Assign animals to shippers per Sub Project Code (cohort), 
    ensuring no mixing across cohorts and maintaining global ShipperIndex.
    Also assigns ShipperCohortIndex per cohort to help with compartment assignment.
    """
    all_assigned = []
    global_shipper_id = 1  # Global index across cohorts

    for cohort, cohort_df in df.groupby("Sub Project Code"):
        cohort_df = cohort_df.copy()
        shippers = []

        grouped = cohort_df.groupby(['Genotype', 'Animal Gender', 'Cage'])
        group_list = sorted(grouped, key=lambda x: len(x[1]), reverse=True)

        for (genotype, gender, cage), group_df in group_list:
            animals = group_df.to_dict('records')
            candidate_shippers = []

            for shipper in shippers:
                if (len(shipper) + len(animals) <= 5 and
                    all(a['Animal Gender'] == gender for a in shipper) and
                    all(a['Genotype'] == genotype for a in shipper) and
                    (gender == 'F' or all(a['Cage'] == cage for a in shipper if a['Animal Gender'] == 'M')) and
                    not any(extract_ear_tag(a['Animal Code']) in [extract_ear_tag(b['Animal Code']) for b in shipper] for a in animals)):

                    if gender == 'F':
                        existing_ages = [a['Age in Days'] for a in shipper]
                        new_ages = [a['Age in Days'] for a in animals]
                        combined_ages = existing_ages + new_ages
                        age_range = max(combined_ages) - min(combined_ages)
                        if age_range <= 7:
                            candidate_shippers.append((age_range, shipper))
                    else:
                        candidate_shippers.append((0, shipper))

            if candidate_shippers:
                candidate_shippers.sort(key=lambda x: x[0])
                best_shipper = candidate_shippers[0][1]
                for a in animals:
                    a['Ear Tag'] = extract_ear_tag(a['Animal Code'])
                    a['ShipperIndex'] = global_shipper_id + shippers.index(best_shipper)
                    a['ShipperCohortIndex'] = shippers.index(best_shipper) + 1
                    best_shipper.append(a)
            else:
                new_shipper = []
                for a in animals:
                    a['Ear Tag'] = extract_ear_tag(a['Animal Code'])
                    a['ShipperIndex'] = global_shipper_id + len(shippers)
                    a['ShipperCohortIndex'] = len(shippers) + 1
                    new_shipper.append(a)
                shippers.append(new_shipper)

        assigned = [animal for shipper in shippers for animal in shipper]
        all_assigned.extend(assigned)
        global_shipper_id += len(shippers)

    return pd.DataFrame(all_assigned)


def sort_by_shipper(df):
    """Sorts dataframe by Genotype, Animal Gender, and ShipperIndex."""
    df = df.sort_values(by=['Genotype', 'Animal Gender', 'ShipperIndex'], ascending=[True, True, True]).reset_index(drop=True)
    return df

def assign_compartments(df):
    """Assign compartments per cohort, resetting numbering for each cohort. 
    Cohorts are processed starting with the smallest."""
    df = df.copy()
    final_df = []

    # Sort cohorts by size (ascending)
    cohorts_sorted = sorted(df['Sub Project Code'].unique(), key=lambda x: len(df[df['Sub Project Code'] == x]))

    for cohort in cohorts_sorted:
        cohort_df = df[df['Sub Project Code'] == cohort].copy()
        cohort_df = cohort_df.sort_values(by=['Genotype', 'Animal Gender', 'ShipperCohortIndex']).reset_index(drop=True)

        shipper_compartment = []
        current_compartment_number = 1
        current_compartment_letter = 'a'
        previous_shipper = cohort_df.loc[0, 'ShipperCohortIndex']
        current_gender = cohort_df.loc[0, 'Animal Gender']

        for idx, row in cohort_df.iterrows():
            if row['ShipperCohortIndex'] != previous_shipper:
                if row['Animal Gender'] == current_gender:
                    current_compartment_letter = 'b' if current_compartment_letter == 'a' else 'a'
                    if current_compartment_letter == 'a':
                        current_compartment_number += 1
                else:
                    current_compartment_number += 1
                    current_compartment_letter = 'a'

                previous_shipper = row['ShipperCohortIndex']
                current_gender = row['Animal Gender']

            shipper_compartment.append(f"{current_compartment_number}{current_compartment_letter}")

        cohort_df['Shipper Compartment'] = shipper_compartment
        final_df.append(cohort_df)

    return pd.concat(final_df, ignore_index=True)

# Streamlit part to upload and process the file
st.title(Title)

DisplayChangeLog = st.expander("Updates")
DisplayChangeLog.write(Changelog)

uploaded_file = st.file_uploader("Choose a file", type="xlsx")

if uploaded_file is not None:
    # Read the CSV into a DataFrame
    df = pd.read_excel(uploaded_file)
    
    # Call the sort and process functions
    df = sort_genotype_gender(df)
    df["Ear Tag"] = df["Animal Code"].apply(extract_ear_tag)
    
    # Process shippers and assign compartments
    processed_df = assign_shippers_v4(df)
    processed_df = sort_by_shipper(processed_df)
    processed_df = assign_compartments(processed_df)
    
    # Visualise Pack Plan
    DisplayPackPlan = st.expander("Pack Plan")
    DisplayPackPlan.write(processed_df)
  
    # Visualise the Age spread in Shippers

    # Calculate the age spread (max - min) per shipper
    age_spread_df = processed_df.groupby('ShipperIndex')['Age in Days'].agg(lambda x: max(x) - min(x)).reset_index()
    age_spread_df = age_spread_df.rename(columns={'Age in Days': 'Age Spread'})

    # Plot it
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(age_spread_df['ShipperIndex'], age_spread_df['Age Spread'], marker='o')
    ax.set_title('Age Spread per Shipper')
    ax.set_xlabel('Shipper Index')
    ax.set_ylabel('Age Difference (Days)')
    ax.grid(True)
    
    #st.pyplot(fig)
    
    DisplayAgeSpread = st.expander("Age Spread in Shippers")
    DisplayAgeSpread.pyplot(fig)
    
    # Allow the user to download the processed result
    output_csv = processed_df.to_csv(index=False)
    st.download_button(label="Download Pack Plan", data=output_csv, file_name="processed_pack_plan.csv", mime="text/csv")
