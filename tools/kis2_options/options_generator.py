"""Author: Sunil Ravilla
Date: 10/07/2023
Description: This script takes a CSV file as input and generates a JSON file as output. The CSV file contains three columns: component, sub_component, and params_to_attach. The script reads the CSV file and generates a JSON file with structure required for STAT"""

import json
import pandas as pd

# Prompt user for CSV file path
csv_file = input("Enter the path to the CSV file: ")

# Read CSV file into a data frame
df = pd.read_csv(csv_file, names=[
                 'component', 'sub_component', 'params_to_attach'], header=0)

print(df)

# Processing data frame to JSON
output = {}
for _, row in df.iterrows():
    component = row['component']
    sub_component = row['sub_component']
    param = row['params_to_attach']

    if component not in output:
        output[component] = {
            'sub_component': {}
        }

    if sub_component not in output[component]['sub_component']:
        output[component]['sub_component'][sub_component] = {
            'params_to_attach': {}
        }

    output[component]['sub_component'][sub_component]['params_to_attach'][param] = {}

# Creating final output JSON structure
final_output = {
    'component': output
}

# Saving output to JSON file
output_file = 'output.json'
with open(output_file, 'w') as f:
    json.dump(final_output, f, indent=4)

print(f"Output JSON file '{output_file}' has been generated.")

