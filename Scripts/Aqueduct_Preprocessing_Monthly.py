import pandas as pd
import numpy as np

df = pd.read_csv("/var/TeamPipeline/Raw/Aqueduct40_baseline_monthly_y2023m07d05.csv")

# 1. Mapping the  column types
raw_cols = [col for col in df.columns if '_raw' in col]
score_cols = [col for col in df.columns if '_score' in col]
cat_cols = [col for col in df.columns if '_cat' in col]
label_cols = [col for col in df.columns if '_label' in col]

# Setting options to display all rows and columns
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)

# Printing the full list of columns
print(df.columns.tolist())

df.info()

# Print the first few column names in each group
print('Raw columns:', raw_cols[:5])
print('Score columns:', score_cols[:5])
print('Category columns:', cat_cols[:5])
print('Label columns:', label_cols[:5])

import numpy as np
# Replacing the placeholder values with np.nan in numeric columns
for col in raw_cols + score_cols:
    df[col] = df[col].replace([-9999, 9999, -9999.0, 9999.0], np.nan)

#Checking  for Missing Values
print(df[raw_cols].isnull().sum())      # Missing in raw columns
print(df[score_cols].isnull().sum())    # Missing in score columns
print(df[cat_cols].isnull().sum())      # Missing in category columns
print(df[label_cols].isnull().sum())    # Missing in label columns

#Dropping rows with any missing values
df_dropped_rows = df.dropna(axis=0) # axis=0 is the default and means 'row'
# OR
df_dropped_rows = df.dropna()


#Looking for the duplicates:
print(df.duplicated().sum())

#removing the duplicates
df = df.drop_duplicates()

# Numeric columns should be float
for col in raw_cols + score_cols:
    df[col] = pd.to_numeric(df[col], errors='coerce')

# Category columns should be integer
for col in cat_cols:
    df[col] = df[col].astype(int)

# Label columns as string
for col in label_cols:
    df[col] = df[col].astype(str)

# Printing  the dtypes to confirm
print(df[raw_cols + score_cols + cat_cols + label_cols].dtypes)


print(df.isnull().sum())
print((df == '').sum())  # Empty strings
print((df == 'NA').sum())  # 'NA' as string


# Save cleaned dataframe to CSV
df.to_csv("/var/TeamPipeline/Preprocessed/Aqueduct_monthly_cleaned.csv", index=False)
