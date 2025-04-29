#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Apr 28 13:23:12 2025

@author: gkurejsepi


"""
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# Your existing functions
def sort_genotype_gender(df):
    """Sorts dataframe by Genotype and Animal Gender (males first, then females)."""
    df = df.sort_values(by=['Genotype', 'Animal Gender', 'Cage', 'Age in Days'], ascending=[True, True, True, True]).reset_index(drop=True)
    return df

def extract_ear_tag(animal_id):
    """Extracts the ear tag from the Animal ID (3rd and 2nd last characters)."""
    return animal_id[-3:-1] if isinstance(animal_id, str) and len(animal_id) >= 3 else ""

def assign_shippers_v2(df):
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

def assign_shippers_v3(df):
    """Assign animals to shippers, minimizing age differences for females."""
    shippers = []  # List of shippers
    shipper_id = 1

    # Group animals by Genotype, Gender, and Cage, larger groups first
    grouped = df.groupby(['Genotype', 'Animal Gender', 'Cage'])
    group_list = sorted(grouped, key=lambda x: len(x[1]), reverse=True)

    for (genotype, gender, cage), group_df in group_list:
        animals = group_df.to_dict('records')

        # Find all candidate shippers
        candidate_shippers = []

        for shipper in shippers:
            if (len(shipper) + len(animals) <= 5 and
                all(a['Animal Gender'] == gender for a in shipper) and
                all(a['Genotype'] == genotype for a in shipper) and
                (gender == 'F' or all(a['Cage'] == cage for a in shipper if a['Animal Gender'] == 'M')) and
                not any(extract_ear_tag(a['Animal Code']) in [extract_ear_tag(b['Animal Code']) for b in shipper] for a in animals)):

                # If female, calculate age difference
                if gender == 'F':
                    existing_ages = [a['Age in Days'] for a in shipper]
                    new_ages = [a['Age in Days'] for a in animals]
                    combined_ages = existing_ages + new_ages
                    age_range = max(combined_ages) - min(combined_ages)
                    candidate_shippers.append((age_range, shipper))
                else:
                    # For males, no age optimization needed
                    candidate_shippers.append((0, shipper))

        if candidate_shippers:
            # Choose the shipper with minimal age range
            candidate_shippers.sort(key=lambda x: x[0])
            best_shipper = candidate_shippers[0][1]
            for a in animals:
                a['Ear Tag'] = extract_ear_tag(a['Animal Code'])
                a['ShipperIndex'] = shippers.index(best_shipper) + 1
                best_shipper.append(a)
        else:
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


def sort_by_shipper(df):
    """Sorts dataframe by Genotype, Animal Gender, and ShipperIndex."""
    df = df.sort_values(by=['Genotype', 'Animal Gender', 'ShipperIndex'], ascending=[True, True, True]).reset_index(drop=True)
    return df

def assign_compartments(df):
    """Assigns shipper compartments based on ShipperIndex change and gender segregation."""
    df = df.sort_values(by=['Genotype', 'Animal Gender', 'ShipperIndex']).reset_index(drop=True)

    shipper_compartment = []
    current_compartment_number = 1
    current_compartment_letter = 'a'
    previous_shipper_index = df.loc[0, 'ShipperIndex']
    current_gender = df.loc[0, 'Animal Gender']

    for idx, row in df.iterrows():
        if row['ShipperIndex'] != previous_shipper_index:
            # If only ShipperIndex changes but the gender does not, flip the compartment letter
            if row['Animal Gender'] == current_gender:
                if current_compartment_letter == 'a':
                    current_compartment_letter = 'b'
                else:
                    current_compartment_number += 1
                    current_compartment_letter = 'a'
            else:
                # If both ShipperIndex and Gender change, increment the compartment number and reset to 'a'
                current_compartment_number += 1
                current_compartment_letter = 'a'
            previous_shipper_index = row['ShipperIndex']
            current_gender = row['Animal Gender']

        shipper_compartment.append(f"{current_compartment_number}{current_compartment_letter}")

    df['Shipper Compartment'] = shipper_compartment
    return df

# Streamlit part to upload and process the file
st.title('Mouse Packer')

uploaded_file = st.file_uploader("Choose a file", type="csv")

if uploaded_file is not None:
    # Read the CSV into a DataFrame
    df = pd.read_csv(uploaded_file)
    
    # Call the sort and process functions
    df = sort_genotype_gender(df)
    df["Ear Tag"] = df["Animal Code"].apply(extract_ear_tag)
    
    # Process shippers and assign compartments
    processed_df = assign_shippers_v3(df)
    processed_df = sort_by_shipper(processed_df)
    processed_df = assign_compartments(processed_df)
    
    st.write("Pack Plan")
    st.write(processed_df)
    
    # Visualise the Age spread in Shippers
    st.write("### Age Range per Shipper (Spread Plot)")

    # Calculate the age spread (max - min) per shipper
    age_spread_df = processed_df.groupby('ShipperIndex')['Age in Days'].agg(lambda x: max(x) - min(x)).reset_index()
    age_spread_df = age_spread_df.rename(columns={'Age in Days': 'Age Spread'})

    # Plot it
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(age_spread_df['ShipperIndex'], age_spread_df['Age Spread'], marker='o', linestyle='-')
    ax.set_title('Age Spread per Shipper')
    ax.set_xlabel('Shipper Index')
    ax.set_ylabel('Age Difference (Days)')
    ax.grid(True)
    
    st.pyplot(fig)
    
    # Allow the user to download the processed result
    output_csv = processed_df.to_csv(index=False)
    st.download_button(label="Download Pack Plan", data=output_csv, file_name="processed_pack_plan.csv", mime="text/csv")
