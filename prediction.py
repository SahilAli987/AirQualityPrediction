import streamlit as st
import pickle
import numpy as np
import pandas as pd
import requests
import json
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import folium_static


def load_model():
    with open('./new_model.pkl', 'rb') as file:
        data = pickle.load(file)
    return data


data = load_model()
regressor = data["model"]


def get_location_from_ip():
    try:
        response = requests.get('https://ipinfo.io/json')
        data = response.json()
        return data.get('city'), data.get('region'), data.get('country')
    except Exception as e:
        st.error(f"Error getting location: {e}")
        return None, None, None


def test_openweather_api(lat, lon):
    try:
        api_key = "6e4eb4c2e35cfea5e1b1f762eabc6d84"
        url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={api_key}"
        
        response = requests.get(url)
        data = response.json()
        
        # Debug print the response
        st.write("Debug - OpenWeather API Response:", data)
        
        if response.status_code == 200:
            return True, data
        else:
            return False, data.get('message', 'Unknown error')
    except Exception as e:
        return False, str(e)


def get_waqi_aqi(lat, lon):
    try:
        api_key = "4bd665894a9f473c47c0eb62121cd5a70b9378b4"
        url = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token={api_key}"
        
        response = requests.get(url)
        data = response.json()
        
        if response.status_code == 200 and data['status'] == 'ok':
            return True, data['data']['aqi']
        else:
            return False, data.get('message', 'Unknown error')
    except Exception as e:
        return False, str(e)


def get_aqi_data(lat, lon):
    try:
        # Get pollutant data from OpenWeather
        success_ow, openweather_data = test_openweather_api(lat, lon)
        # Get AQI from WAQI
        success_waqi, waqi_aqi = get_waqi_aqi(lat, lon)
        
        if success_ow and success_waqi:
            st.success("Both APIs are working!")
            components = openweather_data['list'][0]['components']
            
            # Convert OpenWeather data to our format
            # Note: OpenWeather provides CO in μg/m³, we need to convert to mg/m³
            co_in_mgm3 = components.get('co', 0) / 1000.0  # Convert μg/m³ to mg/m³
            
            aqi_data = {
                'PM2.5': components.get('pm2_5', 0),  # μg/m³
                'NO2': components.get('no2', 0),      # μg/m³
                'CO': co_in_mgm3,                     # Converted from μg/m³ to mg/m³
                'SO2': components.get('so2', 0),      # μg/m³
                'O3': components.get('o3', 0),        # μg/m³
                'aqi': waqi_aqi  # Using WAQI's AQI value
            }
            
            # Debug print for processed data
            st.write("Debug - OpenWeather pollutant data:", components)
            st.write("Debug - WAQI AQI value:", waqi_aqi)
            st.write("Debug - Final processed data:", aqi_data)
            
            return aqi_data
        else:
            if not success_ow:
                st.error(f"OpenWeather API Error: Could not fetch pollutant data")
            if not success_waqi:
                st.error(f"WAQI API Error: Could not fetch AQI")
            return None
            
    except Exception as e:
        st.error(f"Error fetching AQI data: {e}")
        return None


def show_geo_prediction_page():
    st.title("Geo-Location Based AQI Prediction")
    st.write("""We'll use your location to predict the Air Quality Index in your area.""")
    
    # Get user's location
    city, region, country = get_location_from_ip()
    
    if city and region and country:
        st.write(f"Detected Location: {city}, {region}, {country}")
        
        # Get coordinates for the map
        geolocator = Nominatim(user_agent="aqi_app")
        location = geolocator.geocode(f"{city}, {region}, {country}")
        
        if location:
            # Create a map centered at the user's location
            m = folium.Map(location=[location.latitude, location.longitude], zoom_start=10)
            folium.Marker(
                [location.latitude, location.longitude],
                popup=f"{city}, {region}",
                tooltip="Your Location"
            ).add_to(m)
            
            # Display the map
            folium_static(m)
            
            # Get AQI data
            aqi_data = get_aqi_data(location.latitude, location.longitude)
            
            if aqi_data:
                # Create two columns for comparison
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Real-time Air Quality")
                    st.write(f"Location: {city}, {region}")
                    
                    # Convert AQI to category
                    def get_aqi_category(aqi):
                        if aqi <= 50:
                            return ("Good", "🟢")
                        elif aqi <= 100:
                            return ("Moderate", "🟡")
                        elif aqi <= 150:
                            return ("Unhealthy for Sensitive Groups", "🟠")
                        elif aqi <= 200:
                            return ("Unhealthy", "🔴")
                        elif aqi <= 300:
                            return ("Very Unhealthy", "🟣")
                        else:
                            return ("Hazardous", "⚫")
                    
                    real_category, real_emoji = get_aqi_category(aqi_data['aqi'])
                    st.write(f"### Current AQI: {aqi_data['aqi']} {real_emoji}")
                    st.write(f"Status: {real_category}")
                    
                    # Display pollutant levels with proper units and ranges
                    st.write("### Pollutant Levels:")
                    metrics = {
                        "PM2.5": {
                            "value": aqi_data['PM2.5'],
                            "unit": "µg/m³",
                            "safe_range": "0-12",
                            "description": "Fine particulate matter"
                        },
                        "NO2": {
                            "value": aqi_data['NO2'],
                            "unit": "µg/m³",
                            "safe_range": "0-40",
                            "description": "Nitrogen dioxide"
                        },
                        "CO": {
                            "value": aqi_data['CO'],
                            "unit": "mg/m³",
                            "safe_range": "0-4",
                            "description": "Carbon monoxide"
                        },
                        "SO2": {
                            "value": aqi_data['SO2'],
                            "unit": "µg/m³",
                            "safe_range": "0-20",
                            "description": "Sulfur dioxide"
                        },
                        "O3": {
                            "value": aqi_data['O3'],
                            "unit": "µg/m³",
                            "safe_range": "0-50",
                            "description": "Ozone"
                        }
                    }
                    
                    for pollutant, info in metrics.items():
                        st.metric(
                            label=f"{pollutant} ({info['description']})",
                            value=f"{info['value']} {info['unit']}",
                            delta=f"Safe range: {info['safe_range']} {info['unit']}"
                        )
                
                with col2:
                    st.subheader("Model Prediction")
                    # Create DataFrame with uppercase feature names
                    model_input = pd.DataFrame([[aqi_data['PM2.5'], 
                                              aqi_data['NO2'],
                                              aqi_data['CO'],
                                              aqi_data['SO2'],
                                              aqi_data['O3']]], 
                                            columns=['PM2.5', 'NO2', 'CO', 'SO2', 'O3'])
                    predicted_aqi = regressor.predict(model_input)[0]
                    predicted_category, pred_emoji = get_aqi_category(predicted_aqi)
                    
                    st.write(f"### Predicted AQI: {predicted_aqi:.1f} {pred_emoji}")
                    st.write(f"Status: {predicted_category}")
                    
                    # Calculate and display model performance metrics
                    aqi_diff = abs(predicted_aqi - aqi_data['aqi'])
                    accuracy = max(0, 100 - (aqi_diff / aqi_data['aqi']) * 100)
                    
                    st.write("### Model Performance")
                    st.metric(
                        label="Prediction Accuracy",
                        value=f"{accuracy:.1f}%",
                        delta=f"{-aqi_diff:.1f} AQI points" if aqi_diff > 0 else "Perfect Match!"
                    )
                    
                    # Add confidence indicator based on accuracy
                    if accuracy >= 90:
                        confidence = "High Confidence 🎯"
                    elif accuracy >= 70:
                        confidence = "Moderate Confidence 👍"
                    else:
                        confidence = "Low Confidence ⚠️"
                    st.write(f"Prediction Confidence: {confidence}")
                
                # Add a time series chart if historical data is available
                st.subheader("Comparison Analysis")
                chart_data = pd.DataFrame({
                    'Metric': ['Real-time AQI', 'Predicted AQI'],
                    'Value': [aqi_data['aqi'], predicted_aqi]
                })
                st.bar_chart(chart_data.set_index('Metric'))
                
                # Add recommendations based on AQI levels
                st.subheader("Health Recommendations")
                current_aqi = aqi_data['aqi']
                if current_aqi <= 50:
                    st.success("Air quality is good. Perfect for outdoor activities! 🌳")
                elif current_aqi <= 100:
                    st.info("Moderate air quality. Sensitive individuals should reduce prolonged outdoor exposure. 🚶")
                elif current_aqi <= 150:
                    st.warning("Unhealthy for sensitive groups. Reduce outdoor activities. 😷")
                elif current_aqi <= 200:
                    st.warning("Unhealthy. Everyone should limit outdoor activities. 🏠")
                elif current_aqi <= 300:
                    st.error("Very unhealthy. Avoid outdoor activities. Stay indoors! ⚠️")
                else:
                    st.error("Hazardous conditions! Emergency conditions. Take precautions! ☣️")
                    
            else:
                st.warning("Could not fetch AQI data for your location.")
        else:
            st.error("Could not determine exact coordinates for your location.")
    else:
        st.error("Could not detect your location. Please try again or use manual prediction.")


def show_predict_page():
    st.title("AQI prediction")
    st.write("""Input info. to predict AQI""")
    
    # Using consistent uppercase feature names
    PM2_5 = st.number_input("PM2.5 (Usually ranges from 0.1 to 120)", min_value=0.0, max_value=950.0, step=0.01, format="%.2f")
    NO2 = st.number_input("NO2 (Usually ranges from 0.01 to 60)", min_value=0.0, max_value=362.0, step=0.01, format="%.2f")
    CO = st.number_input("CO (Usually ranges from 0 to 3)", min_value=0.0, max_value=1756.0, step=0.01, format="%.2f")
    SO2 = st.number_input("SO2 (Usually ranges from 0.01 to 25)", min_value=0.0, max_value=194.0, step=0.01, format="%.2f")
    O3 = st.number_input("O3 (Usually ranges from 0.01 to 65)", min_value=0.0, max_value=258.0, step=0.01, format="%.2f")

    ok = st.button("Calculate AQI")
    if ok:
        # Create DataFrame with uppercase feature names
        X = pd.DataFrame([[PM2_5, NO2, CO, SO2, O3]], columns=['PM2.5', 'NO2', 'CO', 'SO2', 'O3'])
        AQI = regressor.predict(X)[0]
        
        # Display AQI number and category
        st.subheader(f"Predicted AQI: {AQI:.1f}")
        
        # Convert AQI to category with emoji
        def get_aqi_category(aqi):
            if aqi <= 50:
                return ("Good", "🟢")
            elif aqi <= 100:
                return ("Satisfactory", "🟡")
            elif aqi <= 200:
                return ("Moderate", "🟠")
            elif aqi <= 300:
                return ("Poor", "🔴")
            else:
                return ("Severe", "⚫")
        
        category, emoji = get_aqi_category(AQI)
        st.subheader(f"Air Quality Category: {category} {emoji}")
        
        # Add health recommendations based on AQI
        st.subheader("Health Recommendations")
        if AQI <= 50:
            st.success("Air quality is good. Perfect for outdoor activities! 🌳")
        elif AQI <= 100:
            st.info("Moderate air quality. Sensitive individuals should reduce prolonged outdoor exposure. 🚶")
        elif AQI <= 200:
            st.warning("Unhealthy for sensitive groups. Reduce outdoor activities. 😷")
        elif AQI <= 300:
            st.warning("Unhealthy. Everyone should limit outdoor activities. 🏠")
        else:
            st.error("Very unhealthy. Avoid outdoor activities. Stay indoors! ⚠️")
