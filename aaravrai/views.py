import json

import requests
from django.shortcuts import render

import openmeteo_requests

import pandas as pd
import requests_cache
from retry_requests import retry

# import geocoder
from datetime import datetime

# Create your views here.
def get_weather(request):
	""" Gathering data """
	# Setup the Open-Meteo API client with cache and retry on error
	cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
	retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
	openmeteo = openmeteo_requests.Client(session=retry_session)

	# location = geocoder.ip('me').latlng
	send_url = "http://ip-api.com/json"
	r = requests.get(send_url)
	j = json.loads(r.text)
	lat = j['lat']
	lon = j['lon']

	# Make sure all required weather variables are listed here
	# The order of variables in hourly or daily is important to assign them correctly below
	url = "https://api.open-meteo.com/v1/forecast"
	params = {
		"latitude": lat,
		"longitude": lon,
		"daily": "temperature_2m_mean",
		"hourly": "temperature_2m",
		"current": ["temperature_2m", "weather_code"],
		"timezone": "auto"
	}
	responses = openmeteo.weather_api(url, params=params)

	""" Processing Data """
	# Process first location. Add a for-loop for multiple locations or weather models
	response = responses[0]
	# print(f"Coordinates: {response.Latitude()}°N {response.Longitude()}°E")
	# print(f"Elevation: {response.Elevation()} m asl")
	# print(f"Timezone: {response.Timezone()}{response.TimezoneAbbreviation()}")
	# print(f"Timezone difference to GMT+0: {response.UtcOffsetSeconds()}s")

	# Process current data. The order of variables needs to be the same as requested.
	current = response.Current()
	current_temperature_2m = current.Variables(0).Value()
	current_weather_code = current.Variables(1).Value()

	# print(f"\nCurrent time: {current.Time()}")
	# print(f"Current temperature_2m: {current_temperature_2m}")
	# print(f"Current weather_code: {current_weather_code}")

	# Process hourly data. The order of variables needs to be the same as requested.
	hourly = response.Hourly()
	hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()

	hourly_data = {"date": pd.date_range(
		start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
		end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
		freq=pd.Timedelta(seconds=hourly.Interval()),
		inclusive="left"
	)}

	hourly_data["temperature_2m"] = hourly_temperature_2m

	hourly_dataframe = pd.DataFrame(data=hourly_data)
	# print("\nHourly data\n", hourly_dataframe.to_string())

	# Process daily data. The order of variables needs to be the same as requested.
	daily = response.Daily()
	daily_temperature_2m_mean = daily.Variables(0).ValuesAsNumpy()

	daily_data = {"date": pd.date_range(
		start=pd.to_datetime(daily.Time(), unit="s", utc=True),
		end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
		freq=pd.Timedelta(seconds=daily.Interval()),
		inclusive="left"
	)}

	daily_data["temperature_2m_mean"] = daily_temperature_2m_mean

	daily_dataframe = pd.DataFrame(data=daily_data)
	# print("\nDaily data\n", daily_dataframe.to_string())

	""" Organising data """
	# print("\n ---------------------------------------")

	# Get current datetime object
	now = datetime.now()

	# Get date portion only
	current_date = now.date()

	# Get time portion only
	current_time = now.time()

	# Get weekday
	current_day = now.weekday()
	match current_day:
		case 0:
			current_day = "Monday"
		case 1:
			current_day = "Tuesday"
		case 2:
			current_day = "Wednesday"
		case 3:
			current_day = "Thursday"
		case 4:
			current_day = "Friday"
		case 5:
			current_day = "Saturday"
		case 6:
			current_day = "Sunday"
		
	# Convert weather code to description
	match current_weather_code:
		case 0:
			current_weather_code = "Clear sky"
		case 1 | 2 | 3:
			current_weather_code = "Mainly clear, partly cloudy, or overcast"
		case 45 | 48:
			current_weather_code = "Fog and depositing rime fog"
		case 51 | 53 | 55:
			current_weather_code = "Drizzle: Light, moderate, and dense intensity"
		case 56 | 57:
			current_weather_code = "Freezing Drizzle: Light and dense intensity"
		case 61 | 63 | 65:
			current_weather_code = "Rain: Slight, moderate, and heavy intensity"
		case 66 | 67:
			current_weather_code = "Freezing Rain: Light and heavy intensity"
		case 71 | 73 | 75:
			current_weather_code = "Snow fall: Slight, moderate, and heavy intensity"
		case 77:
			current_weather_code = "Snow grains"
		case 80 | 81 | 82:
			current_weather_code = "Rain showers: Slight, moderate, and violent"
		case 85 | 86:
			current_weather_code = "Snow showers: Slight and heavy"
		case 95:
			current_weather_code = "Thunderstorm: Slight or moderate"
		case 96 | 99:
			current_weather_code = "Thunderstorm with slight or heavy hail"
		case _:
			current_weather_code = "Unknown weather condition"

	city = j["city"]

	# Prepare daily forecast data
	daily_forecast = []
	for i in range(len(daily_dataframe)):
		date_obj = daily_dataframe.iloc[i]["date"].to_pydatetime()
		day_name = date_obj.strftime("%a")  # Short day name (Mon, Tue, etc.)
		temp = int(daily_dataframe.iloc[i]["temperature_2m_mean"])
		daily_forecast.append({
			"day": day_name,
			"temp": temp
		})

	# Prepare hourly forecast data (from current hour to end of day)
	hourly_forecast = []
	current_hour_index = now.hour
	hours_remaining = 24 - current_hour_index  # Hours from current hour to 23:00
	for i in range(hours_remaining):
		hour_time = now.replace(hour=current_hour_index + i, minute=0, second=0, microsecond=0)
		# Get the temperature from hourly dataframe
		temp = int(hourly_dataframe.iloc[current_hour_index + i]["temperature_2m"])
		hourly_forecast.append({
			"time": hour_time.strftime("%H:%M"),
			"temp": temp
		})

	""" Displaying data """
	# print(f"Current Date: {current_date}")
	# print(f"Current Time: {current_time}")
	# print(f"Current day: {current_day}")
	# print(f"Current temperature: {int(current_temperature_2m)}")
	# print(f"Current weather code: {current_weather_code}")
	# print(f"Current city: {city}")

	return render(request, "index.html", {
		"date": current_date,
		"time": current_time,
		"day": current_day,
		"current_temp": int(current_temperature_2m),
		"weather_code": current_weather_code,
		"city": city,
		"daily_forecast": daily_forecast,
		"hourly_forecast": hourly_forecast
	})
