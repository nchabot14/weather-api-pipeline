import os
import requests
import json
import time
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ["WEATHER_API_KEY"]

api_url = "https://api.weatherapi.com/v1/forecast.json"

params = {
    "key": api_key,
    "q": "90045"
}

response = requests.get(api_url, params=params)

#print(response.status_code)

data = response.json()

#print(json.dumps(data, indent=2))

#print(data["location"]["name"])
#print(data["location"]["region"])
#print(data["current"]["temp_f"])
#print(data["current"]["condition"]["text"])

zip_codes = [
    '90045',  # Los Angeles, CA
    '10001',  # New York, NY
    '60601',  # Chicago, IL
    '98101',  # Seattle, WA
    '33101',  # Miami, FL
    '02108',  # Boston, MA
    '19103',  # Philadelphia, PA
    '75201',  # Dallas, TX
    '77002',  # Houston, TX
    '85001',  # Phoenix, AZ
    '80202',  # Denver, CO
    '30303',  # Atlanta, GA
    '20001',  # Washington, DC
    '94102',  # San Francisco, CA
    '89101',  # Las Vegas, NV
    '97201',  # Portland, OR
    '55401',  # Minneapolis, MN
    '63101',  # St. Louis, MO
    '78701',  # Austin, TX
    '37201',  # Nashville, TN
]

results = []

for zip_code in zip_codes:
    params = {
        "key": api_key,
        "q": zip_code,
        "days": 7
    }
    response = requests.get(api_url, params=params)
    data = response.json()

    city = data["location"]["name"]
    region = data["location"]["region"]

    for forecast_day in data["forecast"]["forecastday"]:
        date = forecast_day["date"]
        max_temp = forecast_day["day"]["maxtemp_f"]
        min_temp = forecast_day["day"]["mintemp_f"]
        condition = forecast_day["day"]["condition"]["text"]

        results.append({
            "zip_code": zip_code,
            "city": city,
            "region": region,
            "date": date,
            "max_temp_f": max_temp,
            "min_temp_f": min_temp,
            "condition": condition,
        })

        print(f"{city}, {region} {date}: {min_temp}F-{max_temp}F, {condition}")

    time.sleep(1)

print(f"\nCollected {len(results)} forecast days across {len(zip_codes)} cities.")

df = pd.DataFrame(results)
print(df)
print(f"\nShape: {df.shape[0]} rows x {df.shape[1]} columns")

csv_path = Path(__file__).parent / "weather_data.csv"
df.to_csv(csv_path, index=False)
print(f"Saved to {csv_path}")