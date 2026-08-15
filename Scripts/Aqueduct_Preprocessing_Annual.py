import pandas as pd
import numpy as np

data = pd.read_csv("/var/TeamPipeline/Raw/Aqueduct40_baseline_annual_y2023m07d05.csv")

# Setting options to display all rows and columns
# Set a reasonable limit to avoid overwhelming output
# Set a reasonable limit for max columns to avoid unreadable output
pd.set_option('display.max_columns', None)
pd.set_option('display.max_columns', None)

# Printing the full list of columns
print(data.columns.tolist())

#checking no of columns and rows
data.shape

#Grouping columns by their suffixes for easier processing
raw_cols = [col for col in data.columns if col.endswith('_raw')]
score_cols = [col for col in data.columns if col.endswith('_score')]
cat_cols = [col for col in data.columns if col.endswith('_cat')]
label_cols = [col for col in data.columns if col.endswith('_label')]

# Checking a few columns from each group
print('Raw columns:', raw_cols[:5])
print('Score columns:', score_cols[:5])
print('Category columns:', cat_cols[:5])
print('Label columns:', label_cols[:5])

import numpy as np
for col in raw_cols + score_cols:
    data[col] = data[col].replace([-9999, 9999, -9999.0, 9999.0], np.nan)

# Count total duplicate rows
print('Total duplicate rows:', data.duplicated().sum())

print(data.isnull().sum())

print(data.describe(include='all').T)  

data.to_csv("/var/TeamPipeline/Preprocessed/baseline_annual_cleaned.csv", index=False)


