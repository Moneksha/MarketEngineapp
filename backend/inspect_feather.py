import pandas as pd

filepath = "/Users/dmoneksh/Desktop/2026 data and codes/NIFTY50_1minute_2000-01-01_to_2026-03-06.feather"

try:
    df = pd.read_feather(filepath)
    print("Feather File Loaded Successfully!")
    print(f"Total rows: {len(df)}")
    
    if "date" in df.columns:
        date_col = "date"
    elif "timestamp" in df.columns:
        date_col = "timestamp"
    else:
        print(f"Columns found: {df.columns.tolist()}")
        date_col = df.columns[0]
        
    print(f"Start Date: {df[date_col].min()}")
    print(f"End Date: {df[date_col].max()}")
    
    print("\nFirst 5 rows:")
    print(df.head())
    
except Exception as e:
    print(f"Error reading feather file: {e}")

