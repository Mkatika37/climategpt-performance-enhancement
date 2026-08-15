import pandas as pd
import numpy as np

df = pd.read_csv("/var/TeamPipeline/Raw/Aqueduct40_future_annual_y2023m07d05.csv")

 # Setting options to display all rows and columns
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)

# Printing the full list of columns
print(df.columns.tolist())

df.shape

raw_cols = [col for col in df.columns if col.endswith('_x_r')]
score_cols = [col for col in df.columns if col.endswith('_x_s')]
cat_cols = [col for col in df.columns if col.endswith('_x_c')]
label_cols = [col for col in df.columns if col.endswith('_x_l')]

print('Raw columns:', raw_cols[:5])
print('Score columns:', score_cols[:5])
print('Category columns:', cat_cols[:5])
print('Label columns:', label_cols[:5])


import numpy as np
for col in raw_cols + score_cols:
    df[col] = df[col].replace([-9999, 9999, -9999.0, 9999.0], np.nan)


#checking for missing values
print(df.isnull().sum())

# Creating the new DataFrame by dropping rows with ANY NaN
df_rows_dropped = df.dropna(how='any')

# Printing the shape of the original and new DataFrames to see how many rows were lost
print(f"Original shape: {df.shape}")
print(f"New shape (rows dropped): {df_rows_dropped.shape}")

# Checking missing values in the new dataframe
print("\nMissing values in the new DataFrame:")
print(df_rows_dropped.isnull().sum())

#Checking Duplicates
print(f"Duplicate rows: {df.duplicated().sum()}")

#Save to CSV
df_rows_dropped.to_csv("/var/TeamPipeline/Preprocessed/aqueduct_future_annual_cleaned.csv", index=False)


