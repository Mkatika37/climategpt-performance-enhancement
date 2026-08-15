import pandas as pd
df = pd.read_csv("/var/TeamPipeline/Raw/Aqueduct40_baseline_annual_y2023m07d05.csv")
#checking for missing values
print(df.isnull().sum())
#Checking Duplicates
print(f"Duplicate rows: {df.duplicated().sum()}")
import pandas as pd

# 1. Define the names of the two columns you want to keep
#    Replace 'column_A' and 'column_B' with the actual column names from your DataFrame.
columns_to_keep = ['name_0', 'pfaf_id','name_1','area_km2','gid_0']

# 2. Select only those columns to create a new DataFrame
#    The double brackets are necessary for selecting multiple columns.
df_five_columns = df[columns_to_keep]

# Optional: Print the head of the new DataFrame to verify
print("Shape of the new DataFrame:", df_five_columns.shape)
print("\nFirst 5 rows of the new DataFrame:")
print(df_five_columns.head())

print("\nSuccessfully saved the two columns to 'new_file.csv'!")

df_five_columns.head(10)

#checking for missing values
print(df_five_columns.isnull().sum())

#Checking Duplicates
print(f"Duplicate rows: {df_five_columns.duplicated().sum()}")

# 2. Handle duplicates by keeping only the unique rows
df_lookup_table = df_five_columns.drop_duplicates()

#checking for missing values
print(df_lookup_table.isnull().sum())

#Checking Duplicates
print(f"Duplicate rows: {df_lookup_table.duplicated().sum()}")

# --- Step 1: Remove Duplicates
# Keep the first occurrence of each duplicate row.
# This ensures you have one entry for every unique combination of data.
df_lookup_table = df_five_columns.drop_duplicates()

print("\n--- After Dropping Duplicates ---")
print(f"Missing values before cleaning NaNs:\n{df_lookup_table.isnull().sum()}")
# Output will show 10020 NaNs in name_0, name_1, and gid_0

# --- Step 2: Remove Rows with Missing Data (Crucial for a lookup table) ---
# Specify the columns that must have a value (Country Name, Region Name, Country Code).
key_identifier_columns = ['name_0', 'name_1', 'gid_0']

# Drop all rows where any value in the key identifier columns is missing (NaN).
df_lookup_table = df_lookup_table.dropna(subset=key_identifier_columns)

print("\n--- After Dropping Missing Values ---")
print(f"Final shape of the clean lookup table: {df_lookup_table.shape}")
print(f"Final Missing values count (should all be 0 or near 0):\n{df_lookup_table.isnull().sum()}")

# --- Step 3: Save the Final Clean Table ---
# Save the resulting DataFrame to a CSV file.
df_lookup_table.to_csv("/var/TeamPipeline/Preprocessed/final_clean_region_lookup.csv", index=False)

print("\nSuccessfully created and saved the final_clean_region_lookup.csv!")



