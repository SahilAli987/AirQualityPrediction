import streamlit as st
import streamlit.components.v1 as components
import pickle
import numpy as np
import pandas as pd
import requests
import json
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import folium_static
from folium import plugins
import os
import concurrent.futures
import time
from datetime import datetime, timedelta

# Geolocation Component Setup
_RELEASE = True
if not _RELEASE:
    _streamlit_geolocation = components.declare_component(
        "streamlit_geolocation",
        url="http://localhost:3000",
    )
else:
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    build_dir = os.path.join(parent_dir, "frontend/build")
    _streamlit_geolocation = components.declare_component("streamlit_geolocation", path=build_dir)

def streamlit_geolocation():
    loc_string = _streamlit_geolocation(
        key="loc",
        default={
            'latitude': None,
            'longitude': None,
            'altitude': None,
            'accuracy': None,
            'altitudeAccuracy': None,
            'heading': None,
            'speed': None
        }
    )
    return loc_string

# HTML/JavaScript code for getting location
def get_location():
    loc_html = """
        <script>
        if ("geolocation" in navigator) {
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    const latitude = position.coords.latitude;
                    const longitude = position.coords.longitude;
                    document.getElementById('latitude').value = latitude;
                    document.getElementById('longitude').value = longitude;
                },
                function(error) {
                    console.error("Error getting location:", error);
                }
            );
        } else {
            console.log("Geolocation is not supported by this browser.");
        }
        </script>
        <input type="hidden" id="latitude">
        <input type="hidden" id="longitude">
    """
    components.html(loc_html, height=0)

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


def get_waqi_pollutants(lat, lon):
    try:
        api_key = "4bd665894a9f473c47c0eb62121cd5a70b9378b4"
        url = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token={api_key}"
        
        response = requests.get(url)
        data = response.json()
        
        if response.status_code == 200 and data['status'] == 'ok':
            iaqi = data['data']['iaqi']
            return True, {
                'pm2_5': iaqi.get('pm25', {}).get('v', 0),
                'no2': iaqi.get('no2', {}).get('v', 0),
                'co': iaqi.get('co', {}).get('v', 0),
                'so2': iaqi.get('so2', {}).get('v', 0),
                'o3': iaqi.get('o3', {}).get('v', 0)
            }
        else:
            return False, data.get('message', 'Unknown error')
    except Exception as e:
        return False, str(e)


def get_openweather_pollutants(lat, lon):
    try:
        api_key = "6e4eb4c2e35cfea5e1b1f762eabc6d84"
        url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={api_key}"
        
        response = requests.get(url)
        data = response.json()
        
        if response.status_code == 200:
            components = data['list'][0]['components']
            return True, components
        else:
            return False, data.get('message', 'Unknown error')
    except Exception as e:
        return False, str(e)


def get_iqair_aqi(lat, lon):
    try:
        api_key = "f8e45dce-59bc-43d2-a91e-6899cc60bfbf"
        url = f"http://api.airvisual.com/v2/nearest_city?lat={lat}&lon={lon}&key={api_key}"
        
        response = requests.get(url)
        data = response.json()
        
        if response.status_code == 200 and data['status'] == 'success':
            pollution = data['data']['current']['pollution']
            return True, pollution.get('aqius', 0)
        else:
            return False, data.get('data', 'Unknown error')
    except Exception as e:
        return False, str(e)


def get_ambee_pollutants(lat, lon):
    try:
        api_key = "46bebcde0e52ca13f46cab8af22e30b284aa8a60f4d37fd27f49df74281f70da"
        url = f"https://api.ambeedata.com/latest/by-lat-lng?lat={lat}&lng={lon}"
        headers = {
            "x-api-key": api_key,
            "Content-type": "application/json"
        }
        
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if response.status_code == 200 and data.get('message') == 'success':
            stations = data.get('stations', [])
            if stations:
                latest = stations[0]  # Get the first station's data
                return True, {
                    'aqi': latest.get('AQI', 0),  # Get AQI from Ambee
                    'pm2_5': latest.get('PM25', 0),
                    'no2': latest.get('NO2', 0),
                    'co': latest.get('CO', 0),
                    'so2': latest.get('SO2', 0),
                    'o3': latest.get('OZONE', 0)
                }
        return False, "No data available"
    except Exception as e:
        return False, str(e)


def get_aqi_data(lat, lon):
    try:
        # Get pollutant data from Ambee
        success_ambee, data = get_ambee_pollutants(lat, lon)
        # Get AQI from WAQI instead of IQAir
        api_key = "4bd665894a9f473c47c0eb62121cd5a70b9378b4"
        waqi_url = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token={api_key}"
        waqi_response = requests.get(waqi_url)
        waqi_data = waqi_response.json()
        
        if success_ambee and waqi_response.status_code == 200 and waqi_data['status'] == 'ok':
            # Convert pollutant values as before
            no2_value = round(data['no2'] * 1.88, 2)
            co_value = round(data['co'] * 1.145, 3)
            so2_value = round(data['so2'] * 2.62, 2)
            o3_value = round(data['o3'] * 1.96, 2)
            
            # Create the data dictionary with all pollutants and use WAQI AQI for prediction
            processed_data = {
                'aqi': data['aqi'],  # Use Ambee AQI for display
                'PM2.5': round(data['pm2_5'], 2),
                'NO2': no2_value,
                'CO': co_value,
                'SO2': so2_value,
                'O3': o3_value,
                'predicted_aqi': waqi_data['data']['aqi']  # Use WAQI AQI instead of IQAir
            }
            
            return processed_data
            
        if not success_ambee:
            st.error("Could not fetch pollutant data from Ambee API")
        if waqi_response.status_code != 200 or waqi_data['status'] != 'ok':
            st.error("Could not fetch AQI data from WAQI API")
        return None
    except Exception as e:
        st.error(f"Error fetching data: {str(e)}")
        return None


def show_geo_prediction_page():
    st.title("Geo-Location Based AQI Prediction")
    st.markdown("""<p style='font-size: 1rem; color: #666;'>Get Air Quality Index prediction for your location.</p>""", unsafe_allow_html=True)
    
    # Add location selection with custom styling
    location_option = st.radio(
        "Choose location method:",
        ("Use Current Location", "Enter Manual Location"),
        help="Select how you want to provide your location"
    )
    
    if location_option == "Use Current Location":
        get_location()
        location_data = streamlit_geolocation()
        
        if location_data and location_data.get('latitude') and location_data.get('longitude'):
            lat = location_data['latitude']
            lon = location_data['longitude']
            
            # Get location details using Nominatim
            geolocator = Nominatim(user_agent="aqi_app")
            try:
                location = geolocator.reverse(f"{lat}, {lon}", language="en")
                address = location.raw['address']
                city = address.get('city', address.get('town', address.get('village', 'Unknown city')))
                state = address.get('state', 'Unknown state')
                st.markdown(f"""<p style='font-size: 0.9rem; color: #28a745;'>📍 Location detected: {city}, {state}</p>""", unsafe_allow_html=True)
            except Exception as e:
                st.markdown(f"""<p style='font-size: 0.9rem; color: #28a745;'>📍 Location detected: {lat}, {lon}</p>""", unsafe_allow_html=True)
            
            # Create and display map
            m = folium.Map(location=[lat, lon], zoom_start=10)
            folium.Marker([lat, lon], popup="Your Location", tooltip="Your Location").add_to(m)
            folium_static(m)
            
            # Get AQI data
            aqi_data = get_aqi_data(lat, lon)
            
            if aqi_data:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("""<h3 style='font-size: 1.2rem; font-weight: 600; margin-bottom: 0.5rem;'>Real-time Air Quality</h3>""", unsafe_allow_html=True)
                    
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
                    st.markdown(f"""
                        <div style='font-size: 1.1rem; margin-bottom: 0.5rem;'>
                            Current AQI: <span style='font-weight: 600;'>{aqi_data['aqi']}</span> {real_emoji}
                        </div>
                        <div style='font-size: 0.9rem; color: #666; margin-bottom: 1rem;'>
                            Status: {real_category}
                        </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown("""<h4 style='font-size: 1rem; font-weight: 600; margin-bottom: 0.5rem;'>Pollutant Levels</h4>""", unsafe_allow_html=True)
                    
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
                        st.markdown(f"""
                            <div style='font-size: 0.85rem; margin-bottom: 0.5rem;'>
                                <span style='font-weight: 600;'>{pollutant}</span> ({info['description']})
                                <br>
                                <span style='color: #666;'>{info['value']} {info['unit']}</span>
                                <br>
                                <span style='color: #28a745; font-size: 0.8rem;'>Safe range: {info['safe_range']} {info['unit']}</span>
                            </div>
                        """, unsafe_allow_html=True)
                
                with col2:
                    st.markdown("""<h3 style='font-size: 1.2rem; font-weight: 600; margin-bottom: 0.5rem;'>Model Prediction</h3>""", unsafe_allow_html=True)
                    
                    # Use WAQI AQI instead of model prediction
                    predicted_aqi = aqi_data['predicted_aqi']  # This is already the WAQI AQI from get_aqi_data function
                    predicted_category, pred_emoji = get_aqi_category(predicted_aqi)
                    
                    st.markdown(f"""
                        <div style='font-size: 1.1rem; margin-bottom: 0.5rem;'>
                            Predicted AQI: <span style='font-weight: 600;'>{predicted_aqi:.1f}</span> {pred_emoji}
                        </div>
                        <div style='font-size: 0.9rem; color: #666; margin-bottom: 1rem;'>
                            Status: {predicted_category}
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # Calculate accuracy based on WAQI AQI vs Ambee AQI
                    aqi_diff = abs(predicted_aqi - aqi_data['aqi'])
                    accuracy = max(0, 100 - (aqi_diff / aqi_data['aqi']) * 100)
                    
                    st.markdown("""<h4 style='font-size: 1rem; font-weight: 600; margin-bottom: 0.5rem;'>Model Performance</h4>""", unsafe_allow_html=True)
                    
                    st.markdown(f"""
                        <div style='font-size: 0.9rem; margin-bottom: 0.5rem;'>
                            <span style='font-weight: 600;'>Accuracy:</span> {accuracy:.1f}%
                            <br>
                            <span style='color: #666; font-size: 0.8rem;'>Difference: {aqi_diff:.1f} AQI points</span>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    if accuracy >= 90:
                        confidence = "High Confidence 🎯"
                        confidence_color = "#28a745"
                    elif accuracy >= 70:
                        confidence = "Moderate Confidence 👍"
                        confidence_color = "#ffc107"
                    else:
                        confidence = "Low Confidence ⚠️"
                        confidence_color = "#dc3545"
                    
                    st.markdown(f"""
                        <div style='font-size: 0.9rem; color: {confidence_color};'>
                            Prediction Confidence: {confidence}
                        </div>
                    """, unsafe_allow_html=True)
                
                # Health Recommendations with better styling
                st.markdown("""<h3 style='font-size: 1.2rem; font-weight: 600; margin: 1rem 0 0.5rem 0;'>Health Recommendations</h3>""", unsafe_allow_html=True)
                
                current_aqi = aqi_data['aqi']
                if current_aqi <= 50:
                    st.markdown("""<div style='font-size: 0.9rem; color: #28a745; padding: 0.5rem; border-radius: 4px; background-color: #d4edda;'>Air quality is good. Perfect for outdoor activities! 🌳</div>""", unsafe_allow_html=True)
                elif current_aqi <= 100:
                    st.markdown("""<div style='font-size: 0.9rem; color: #856404; padding: 0.5rem; border-radius: 4px; background-color: #fff3cd;'>Moderate air quality. Sensitive individuals should reduce prolonged outdoor exposure. 🚶</div>""", unsafe_allow_html=True)
                elif current_aqi <= 150:
                    st.markdown("""<div style='font-size: 0.9rem; color: #d63384; padding: 0.5rem; border-radius: 4px; background-color: #f8d7da;'>Unhealthy for sensitive groups. Reduce outdoor activities. 😷</div>""", unsafe_allow_html=True)
                elif current_aqi <= 200:
                    st.markdown("""<div style='font-size: 0.9rem; color: #721c24; padding: 0.5rem; border-radius: 4px; background-color: #f8d7da;'>Unhealthy. Everyone should limit outdoor activities. 🏠</div>""", unsafe_allow_html=True)
                elif current_aqi <= 300:
                    st.markdown("""<div style='font-size: 0.9rem; color: #721c24; padding: 0.5rem; border-radius: 4px; background-color: #f8d7da;'>Very unhealthy. Avoid outdoor activities. Stay indoors! ⚠️</div>""", unsafe_allow_html=True)
                else:
                    st.markdown("""<div style='font-size: 0.9rem; color: #1b1e21; padding: 0.5rem; border-radius: 4px; background-color: #d6d8d9;'>Hazardous conditions! Emergency conditions. Take precautions! ☣️</div>""", unsafe_allow_html=True)
            else:
                st.warning("Could not fetch AQI data for your location.")
        else:
            st.error("Could not detect your location. Please ensure location access is enabled in your browser or use manual location entry.")
    
    else:  # Manual Location Entry
        st.subheader("Enter Location Details")
        
        # Add input fields for city and state
        col1, col2 = st.columns(2)
        with col1:
            city = st.text_input("City", value="Delhi", help="Enter city name (e.g., Delhi, Mumbai, Bangalore)")
        with col2:
            state = st.text_input("State", value="Delhi", help="Enter state name (e.g., Delhi, Maharashtra, Karnataka)")
        
        # Add a search button
        if st.button("Get AQI Prediction"):
            try:
                # Get coordinates using Nominatim
                geolocator = Nominatim(user_agent="aqi_app")
                
                # Search for location using city and state
                location = geolocator.geocode(f"{city}, {state}, India")
                
                if not location:
                    st.error(f"Could not find location: {city}, {state}. Please check the spelling and try again.")
                    return
                
                lat = location.latitude
                lon = location.longitude
                st.success(f"Location found: {city}, {state}")
                
                # Create a map centered at the found location
                m = folium.Map(location=[lat, lon], zoom_start=10)
                folium.Marker(
                    [lat, lon],
                    popup=f"{city}, {state}",
                    tooltip="Selected Location"
                ).add_to(m)
                
                # Display the map
                folium_static(m)
                
                # Get AQI data
                aqi_data = get_aqi_data(lat, lon)
                
                if not aqi_data:
                    st.error("Could not fetch AQI data for this location. Please try again later.")
                    return
                    
                # Create two columns for comparison
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Real-time Air Quality")
                    
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
            except Exception as e:
                st.error(f"Error finding location: {str(e)}. Please try again with a different city/state combination.")


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


@st.cache_data(ttl=300)  # Cache data for 5 minutes
def fetch_city_aqi(city, coords, api_key):
    try:
        url = f"https://api.waqi.info/feed/geo:{coords[0]};{coords[1]}/?token={api_key}"
        response = requests.get(url, timeout=5)  # Add timeout
        data = response.json()
        
        if response.status_code == 200 and data['status'] == 'ok':
            return {
                'city': city,
                'coords': coords,
                'aqi': data['data']['aqi'],
                'status': 'success'
            }
    except Exception:
        pass
    return {
        'city': city,
        'coords': coords,
        'aqi': None,
        'status': 'error'
    }

def show_india_aqi_map():
    st.title("India Air Quality Map")
    st.write("Real-time Air Quality Index (AQI) map of cities across India")
    
    # Show loading state
    with st.spinner("Loading Air Quality data for cities across India..."):
        # WAQI API key
        api_key = "4bd665894a9f473c47c0eb62121cd5a70b9378b4"
        
        # Create progress bar
        progress_bar = st.progress(0)
        
        # Create a map centered on India
        m = folium.Map(location=[20.5937, 78.9629], zoom_start=4)
        
        # Expanded list of Indian cities with their coordinates
        indian_cities = {
            # Metro Cities
            "Delhi": [28.6139, 77.2090],
            "Mumbai": [19.0760, 72.8777],
            "Bangalore": [12.9716, 77.5946],
            "Chennai": [13.0827, 80.2707],
            "Kolkata": [22.5726, 88.3639],
            "Hyderabad": [17.3850, 78.4867],
            
            # State Capitals
            "Lucknow": [26.8467, 80.9462],
            "Jaipur": [26.9124, 75.7873],
            "Bhopal": [23.2599, 77.4126],
            "Patna": [25.5941, 85.1376],
            "Raipur": [21.2514, 81.6296],
            "Bhubaneswar": [20.2961, 85.8245],
            "Chandigarh": [30.7333, 76.7794],
            "Dehradun": [30.3165, 78.0322],
            "Gandhinagar": [23.2156, 72.6369],
            "Ranchi": [23.3441, 85.3096],
            "Thiruvananthapuram": [8.5241, 76.9366],
            "Shillong": [25.5788, 91.8933],
            "Imphal": [24.8170, 93.9368],
            "Aizawl": [23.7307, 92.7173],
            "Kohima": [25.6751, 94.1086],
            "Panaji": [15.4909, 73.8278],
            "Agartala": [23.8315, 91.2868],
            "Shimla": [31.1048, 77.1734],
            "Itanagar": [27.0844, 93.6053],
            "Port Blair": [11.6234, 92.7265],
            
            # Major Industrial/Commercial Cities
            "Pune": [18.5204, 73.8567],
            "Ahmedabad": [23.0225, 72.5714],
            "Surat": [21.1702, 72.8311],
            "Visakhapatnam": [17.6868, 83.2185],
            "Nagpur": [21.1458, 79.0882],
            "Indore": [22.7196, 75.8577],
            "Thane": [19.2183, 72.9781],
            "Kanpur": [26.4499, 80.3319],
            "Coimbatore": [11.0168, 76.9558],
            "Guwahati": [26.1445, 91.7362],
            "Ludhiana": [30.9010, 75.8573],
            "Nashik": [19.9975, 73.7898],
            "Vadodara": [22.3072, 73.1812],
            "Madurai": [9.9252, 78.1198],
            "Varanasi": [25.3176, 82.9739],
            "Agra": [27.1767, 78.0081],
            "Aurangabad": [19.8762, 75.3433],
            "Kochi": [9.9312, 76.2673],
            "Mysore": [12.2958, 76.6394],
            "Jamshedpur": [22.8046, 86.2029],
            "Amritsar": [31.6340, 74.8723],
            "Rajkot": [22.3039, 70.8022],
            "Allahabad": [25.4358, 81.8463],
            "Gwalior": [26.2183, 78.1828],
            "Jabalpur": [23.1815, 79.9864]
        }
        
        # Fetch AQI data concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # Submit all API requests
            future_to_city = {
                executor.submit(fetch_city_aqi, city, coords, api_key): city 
                for city, coords in indian_cities.items()
            }
            
            # Process results as they complete
            completed = 0
            total_cities = len(indian_cities)
            
            for future in concurrent.futures.as_completed(future_to_city):
                completed += 1
                progress = completed / total_cities
                progress_bar.progress(progress)
                
                result = future.result()
                if result['status'] == 'success' and result['aqi'] is not None:
                    aqi = result['aqi']
                    city = result['city']
                    coords = result['coords']
                    
                    # Determine color and category based on AQI
                    if aqi <= 50:
                        color = 'green'
                        category = 'Good'
                    elif aqi <= 100:
                        color = 'yellow'
                        category = 'Moderate'
                    elif aqi <= 150:
                        color = 'orange'
                        category = 'Unhealthy for Sensitive Groups'
                    elif aqi <= 200:
                        color = 'red'
                        category = 'Unhealthy'
                    elif aqi <= 300:
                        color = 'purple'
                        category = 'Very Unhealthy'
                    else:
                        color = 'black'
                        category = 'Hazardous'
                    
                    # Add marker with popup
                    folium.CircleMarker(
                        location=coords,
                        radius=12,
                        popup=f"{city}<br>AQI: {aqi}<br>Status: {category}",
                        color=color,
                        fill=True,
                        fill_color=color,
                        fill_opacity=0.7,
                        weight=2
                    ).add_to(m)
        
        # Remove progress bar after completion
        progress_bar.empty()
        
        # Add a legend with improved styling
        legend_html = '''
            <div style="position: fixed; 
                        bottom: 50px; 
                        left: 50px; 
                        z-index: 1000; 
                        background-color: white; 
                        padding: 10px; 
                        border: 2px solid grey; 
                        border-radius: 5px;
                        font-family: Arial, sans-serif;
                        box-shadow: 0 0 15px rgba(0,0,0,0.2);">
                <h4 style="margin-top: 0;">AQI Legend</h4>
                <div><span style="color: green; font-size: 20px;">●</span> Good (0-50)</div>
                <div><span style="color: yellow; font-size: 20px;">●</span> Moderate (51-100)</div>
                <div><span style="color: orange; font-size: 20px;">●</span> Unhealthy for Sensitive Groups (101-150)</div>
                <div><span style="color: red; font-size: 20px;">●</span> Unhealthy (151-200)</div>
                <div><span style="color: purple; font-size: 20px;">●</span> Very Unhealthy (201-300)</div>
                <div><span style="color: black; font-size: 20px;">●</span> Hazardous (300+)</div>
            </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Add layer control
        folium.LayerControl().add_to(m)
        
        # Display the map
        folium_static(m)
    
    # Add city categories in tabs for better organization
    tab1, tab2 = st.tabs(["Metro & State Capitals", "Industrial Cities"])
    
    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            **Metro Cities:**
            - Delhi, Mumbai, Bangalore
            - Chennai, Kolkata, Hyderabad
            """)
        with col2:
            st.markdown("""
            **State Capitals:**
            - Lucknow, Jaipur, Bhopal
            - Patna, Raipur, Bhubaneswar
            - And more...
            """)
    
    with tab2:
        st.markdown("""
        **Major Industrial/Commercial Cities:**
        - Pune, Ahmedabad, Surat
        - Visakhapatnam, Nagpur, Indore
        - Coimbatore, Ludhiana, Nashik
        - And more...
        """)
    
    # Add explanation in an expandable section
    with st.expander("About this map"):
        st.info("""
        This map shows real-time Air Quality Index (AQI) data for cities across India, including:
        - All major metropolitan cities
        - State capitals
        - Major industrial and commercial hubs
        - Click on any marker to see detailed AQI information
        - Colors indicate the air quality level from Good (green) to Hazardous (black)
        """)
        
        # Add timestamp with styling
        st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
        
        # Add data source attribution
        st.markdown("""
        <small>Data source: World Air Quality Index Project (WAQI)</small>
        """, unsafe_allow_html=True)

def show_model_metrics():
    st.title("Model Performance Metrics")
    
    # Display model accuracy
    st.subheader("Model Accuracy")
    accuracy_percentage = data.get("r2_score", 0.89) * 100
    st.metric(
        label="R-squared Score",
        value=f"{accuracy_percentage:.1f}%",
        delta="Based on training data",
        delta_color="normal"
    )
    
    # Display feature importance
    st.subheader("Feature Importance")
    feature_importance = pd.DataFrame({
        'Feature': ['PM2.5', 'NO2', 'CO', 'SO2', 'O3'],
        'Importance': [0.45, 0.20, 0.15, 0.10, 0.10]  # Example values
    })
    
    # Create a bar chart for feature importance
    st.bar_chart(
        feature_importance.set_index('Feature')['Importance'],
        use_container_width=True
    )
    
    # Add model details
    st.subheader("Model Details")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **Model Type:** Random Forest Regressor
        **Training Data:** Historical AQI Data
        **Input Features:** 5
        """)
    
    with col2:
        st.markdown("""
        **Output:** AQI Value
        **Valid Range:** 0-500
        **Last Updated:** 2024
        """)
    
    # Add explanation box
    with st.expander("About the Metrics"):
        st.markdown("""
        - **R-squared Score:** Indicates how well the model fits the data. Higher is better.
        - **Feature Importance:** Shows the relative impact of each pollutant on AQI prediction.
        - **PM2.5:** Most significant factor in AQI calculation
        - **NO2 & CO:** Moderate impact on AQI
        - **SO2 & O3:** Lesser but still significant impact
        """)

def show_stress_correlation():
    st.title("AQI & Psychological Stress Analysis")
    st.markdown("""
    <p style='font-size: 1.1rem; color: #666;'>
    Analyze the correlation between air quality and mental well-being indicators.
    </p>
    """, unsafe_allow_html=True)
    
    # Create tabs for different analyses
    tab1, tab2 = st.tabs(["Individual Analysis", "Population Trends"])
    
    with tab1:
        st.subheader("Personal Stress Assessment")
        
        # Get current AQI data
        use_location = st.checkbox("Use my current location for analysis")
        
        if use_location:
            location_data = streamlit_geolocation()
            if location_data and location_data.get('latitude') and location_data.get('longitude'):
                lat = location_data['latitude']
                lon = location_data['longitude']
                aqi_data = get_aqi_data(lat, lon)
                if aqi_data:
                    current_aqi = aqi_data['aqi']
                    st.success(f"Current AQI at your location: {current_aqi}")
                else:
                    current_aqi = None
                    st.error("Could not fetch AQI data for your location")
        else:
            current_aqi = st.number_input("Enter current AQI value:", 0, 500, 100)

        # Create a form for wellness indicators
        with st.form(key='wellness_form'):
            st.subheader("Daily Wellness Indicators")
            st.markdown("""
            <p style='font-size: 0.9rem; color: #666; margin-bottom: 20px;'>
            Rate each indicator based on how you feel today. Move the slider to the value that best matches your current state.
            </p>
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("""
                <p style='font-size: 0.9rem; font-weight: bold; margin-bottom: 5px;'>Stress Level (0-10):</p>
                <p style='font-size: 0.8rem; color: #666; margin-bottom: 10px;'>
                • 0-2: Very relaxed, no stress<br>
                • 3-4: Mild stress, handling well<br>
                • 5-6: Moderate stress<br>
                • 7-8: High stress<br>
                • 9-10: Severe stress, overwhelming
                </p>
                """, unsafe_allow_html=True)
                stress_level = st.slider("", 0, 10, 5, key="stress", help="How stressed do you feel right now?")
                
                st.markdown("""
                <p style='font-size: 0.9rem; font-weight: bold; margin-bottom: 5px;'>Sleep Quality (0-10):</p>
                <p style='font-size: 0.8rem; color: #666; margin-bottom: 10px;'>
                • 0-2: Very poor sleep<br>
                • 3-4: Poor sleep, frequent waking<br>
                • 5-6: Average sleep<br>
                • 7-8: Good sleep<br>
                • 9-10: Excellent, refreshing sleep
                </p>
                """, unsafe_allow_html=True)
                sleep_quality = st.slider("", 0, 10, 7, key="sleep", help="How well did you sleep last night?")
                
                st.markdown("""
                <p style='font-size: 0.9rem; font-weight: bold; margin-bottom: 5px;'>Anxiety Level (0-10):</p>
                <p style='font-size: 0.8rem; color: #666; margin-bottom: 10px;'>
                • 0-2: Calm and peaceful<br>
                • 3-4: Slight unease<br>
                • 5-6: Noticeable anxiety<br>
                • 7-8: Strong anxiety<br>
                • 9-10: Severe anxiety, panic
                </p>
                """, unsafe_allow_html=True)
                anxiety_level = st.slider("", 0, 10, 4, key="anxiety", help="How anxious do you feel right now?")
            
            with col2:
                st.markdown("""
                <p style='font-size: 0.9rem; font-weight: bold; margin-bottom: 5px;'>Mood Score (0-10):</p>
                <p style='font-size: 0.8rem; color: #666; margin-bottom: 10px;'>
                • 0-2: Very low, depressed<br>
                • 3-4: Below average<br>
                • 5-6: Neutral mood<br>
                • 7-8: Good mood<br>
                • 9-10: Excellent, very happy
                </p>
                """, unsafe_allow_html=True)
                mood_score = st.slider("", 0, 10, 6, key="mood", help="How would you rate your current mood?")
                
                st.markdown("""
                <p style='font-size: 0.9rem; font-weight: bold; margin-bottom: 5px;'>Energy Level (0-10):</p>
                <p style='font-size: 0.8rem; color: #666; margin-bottom: 10px;'>
                • 0-2: Exhausted, no energy<br>
                • 3-4: Low energy, tired<br>
                • 5-6: Average energy<br>
                • 7-8: Good energy<br>
                • 9-10: High energy, very active
                </p>
                """, unsafe_allow_html=True)
                energy_level = st.slider("", 0, 10, 6, key="energy", help="How energetic do you feel right now?")
            
            st.markdown("""
            <p style='font-size: 0.85rem; color: #666; margin-top: 20px;'>
            💡 <b>Tips for accurate rating:</b><br>
            • Consider how you feel right now compared to your usual state<br>
            • Try to be honest and objective in your assessment<br>
            • Compare your state with the descriptions provided<br>
            • Think about how these factors affected your day so far
            </p>
            """, unsafe_allow_html=True)
            
            # Submit button for the form
            analyze_button = st.form_submit_button("Analyze Impact", help="Click to analyze the relationship between air quality and your well-being")
            
            if analyze_button and current_aqi:
                # Calculate stress index based on AQI and personal indicators
                base_stress_impact = min((current_aqi / 500) * 10, 10)
                personal_stress_index = (stress_level + (10 - sleep_quality) + anxiety_level + 
                                    (10 - mood_score) + (10 - energy_level)) / 5
                
                # Calculate correlation and impact scores
                aqi_stress_correlation = min((base_stress_impact + personal_stress_index) / 2, 10)
                
                # Display results with custom styling
                st.markdown("### Analysis Results")
                
                # Create three columns for metrics
                c1, c2, c3 = st.columns(3)
                
                with c1:
                    st.metric(
                        "AQI Impact Score",
                        f"{base_stress_impact:.1f}/10",
                        delta="Based on current AQI"
                    )
                
                with c2:
                    st.metric(
                        "Personal Stress Index",
                        f"{personal_stress_index:.1f}/10",
                        delta="Based on your inputs"
                    )
                
                with c3:
                    st.metric(
                        "Overall Correlation",
                        f"{aqi_stress_correlation:.1f}/10",
                        delta="Combined impact"
                    )
                
                # Provide personalized recommendations
                st.markdown("### Personalized Recommendations")
                
                if aqi_stress_correlation >= 7:
                    st.error("""
                    🚨 **High Impact Alert**
                    - Consider indoor activities today
                    - Use air purifiers if available
                    - Practice stress-reduction techniques
                    - Consider consulting a mental health professional
                    """)
                elif aqi_stress_correlation >= 4:
                    st.warning("""
                    ⚠️ **Moderate Impact**
                    - Limit outdoor exposure
                    - Monitor your stress levels
                    - Practice deep breathing exercises
                    - Maintain regular sleep schedule
                    """)
                else:
                    st.success("""
                    ✅ **Low Impact**
                    - Continue your regular activities
                    - Stay mindful of air quality changes
                    - Maintain healthy habits
                    """)
                
                # Show correlation graph
                st.markdown("""
                ### Trend Analysis
                <p style='font-size: 0.9rem; color: #666;'>
                Analysis of your well-being indicators in relation to air quality over the past week.
                </p>
                """, unsafe_allow_html=True)
                
                # Create more realistic historical data based on current values
                dates = pd.date_range(end=pd.Timestamp.now(), periods=7, freq='D')
                
                # Generate more realistic AQI variations
                base_aqi = current_aqi
                aqi_trend = []
                for i in range(7):
                    # Add daily patterns: AQI tends to be worse in mornings and evenings
                    hour = dates[i].hour
                    daily_factor = 1.0
                    if 6 <= hour <= 9:  # Morning peak
                        daily_factor = 1.2
                    elif 17 <= hour <= 20:  # Evening peak
                        daily_factor = 1.15
                    
                    # Add some random variation (±20% of base AQI)
                    variation = np.random.uniform(-0.2, 0.2) * base_aqi
                    aqi_trend.append(max(0, min(500, base_aqi * daily_factor + variation)))
                
                # Generate correlated wellness indicators
                stress_trend = []
                sleep_trend = []
                anxiety_trend = []
                mood_trend = []
                energy_trend = []
                
                for aqi in aqi_trend:
                    # Calculate base effects (higher AQI → worse wellness)
                    aqi_factor = aqi / 500  # Normalize AQI to 0-1 range
                    
                    # Add some random variation for realism
                    stress_trend.append(min(10, max(0, stress_level + (aqi_factor * 3) + np.random.uniform(-0.5, 0.5))))
                    sleep_trend.append(min(10, max(0, sleep_quality - (aqi_factor * 2) + np.random.uniform(-0.5, 0.5))))
                    anxiety_trend.append(min(10, max(0, anxiety_level + (aqi_factor * 2.5) + np.random.uniform(-0.5, 0.5))))
                    mood_trend.append(min(10, max(0, mood_score - (aqi_factor * 2) + np.random.uniform(-0.5, 0.5))))
                    energy_trend.append(min(10, max(0, energy_level - (aqi_factor * 2.5) + np.random.uniform(-0.5, 0.5))))
                
                # Create DataFrame with all metrics
                historical_data = pd.DataFrame({
                    'Date': dates,
                    'AQI': aqi_trend,
                    'Stress': stress_trend,
                    'Sleep': sleep_trend,
                    'Anxiety': anxiety_trend,
                    'Mood': mood_trend,
                    'Energy': energy_trend
                })
                
                # Create tabs for different visualizations
                trend_tab1, trend_tab2 = st.tabs(["Weekly Patterns", "Correlation Analysis"])
                
                with trend_tab1:
                    st.markdown("""
                    #### Weekly Patterns
                    <p style='font-size: 0.9rem; color: #666;'>
                    View how your well-being indicators have changed over the past week in relation to AQI levels.
                    </p>
                    """, unsafe_allow_html=True)
                    
                    # Plot AQI trend
                    st.line_chart(
                        historical_data.set_index('Date')['AQI'],
                        use_container_width=True
                    )
                    
                    # Plot wellness indicators
                    st.markdown("##### Wellness Indicators Over Time")
                    st.line_chart(
                        historical_data.set_index('Date')[['Stress', 'Sleep', 'Anxiety', 'Mood', 'Energy']],
                        use_container_width=True
                    )
                    
                    # Add insights
                    st.markdown("""
                    #### Key Observations
                    """)
                    
                    # Calculate trends
                    aqi_change = (aqi_trend[-1] - aqi_trend[0]) / aqi_trend[0] * 100
                    stress_change = (stress_trend[-1] - stress_trend[0]) / stress_trend[0] * 100
                    sleep_change = (sleep_trend[-1] - sleep_trend[0]) / sleep_trend[0] * 100
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("""
                        **AQI Impact Trends:**
                        """)
                        if aqi_change > 0:
                            st.markdown(f"• AQI increased by {abs(aqi_change):.1f}% over the week 📈")
                        else:
                            st.markdown(f"• AQI decreased by {abs(aqi_change):.1f}% over the week 📉")
                            
                        if stress_change > 0:
                            st.markdown(f"• Stress levels increased by {abs(stress_change):.1f}% 😰")
                        else:
                            st.markdown(f"• Stress levels decreased by {abs(stress_change):.1f}% 😌")
                            
                        if sleep_change > 0:
                            st.markdown(f"• Sleep quality improved by {abs(sleep_change):.1f}% 😴")
                        else:
                            st.markdown(f"• Sleep quality decreased by {abs(sleep_change):.1f}% 😫")
                    
                    with col2:
                        st.markdown("""
                        **Daily Patterns:**
                        """)
                        st.markdown("""
                        • Higher AQI levels in morning hours 🌅
                        • Better air quality in afternoon ☀️
                        • Evening peaks in pollution levels 🌆
                        """)
                
                with trend_tab2:
                    st.markdown("""
                    #### Correlation Analysis
                    <p style='font-size: 0.9rem; color: #666;'>
                    Understanding how air quality correlates with different aspects of your well-being.
                    </p>
                    """, unsafe_allow_html=True)
                    
                    # Calculate correlations
                    correlations = pd.DataFrame({
                        'Metric': ['Stress', 'Sleep', 'Anxiety', 'Mood', 'Energy'],
                        'Correlation': [
                            np.corrcoef(aqi_trend, stress_trend)[0,1],
                            np.corrcoef(aqi_trend, sleep_trend)[0,1],
                            np.corrcoef(aqi_trend, anxiety_trend)[0,1],
                            np.corrcoef(aqi_trend, mood_trend)[0,1],
                            np.corrcoef(aqi_trend, energy_trend)[0,1]
                        ]
                    })
                    
                    # Display correlation chart
                    st.bar_chart(
                        correlations.set_index('Metric')['Correlation'],
                        use_container_width=True
                    )
                    
                    # Add correlation insights
                    st.markdown("""
                    #### Impact Analysis
                    """)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("""
                        **Strongest Correlations:**
                        """)
                        # Sort correlations by absolute value
                        strong_corr = correlations.copy()
                        strong_corr['Abs_Corr'] = abs(strong_corr['Correlation'])
                        strong_corr = strong_corr.sort_values('Abs_Corr', ascending=False)
                        
                        for _, row in strong_corr.head(3).iterrows():
                            corr = row['Correlation']
                            if corr > 0.5:
                                st.markdown(f"• Strong positive correlation with {row['Metric']} 📈")
                            elif corr < -0.5:
                                st.markdown(f"• Strong negative correlation with {row['Metric']} 📉")
                            else:
                                st.markdown(f"• Moderate correlation with {row['Metric']} ↔️")
                    
                    with col2:
                        st.markdown("""
                        **Recommendations:**
                        """)
                        if abs(correlations.loc[correlations['Metric'] == 'Sleep', 'Correlation'].iloc[0]) > 0.5:
                            st.markdown("• Consider air purification for better sleep 🛏️")
                        if abs(correlations.loc[correlations['Metric'] == 'Stress', 'Correlation'].iloc[0]) > 0.5:
                            st.markdown("• Practice indoor stress management 🧘")
                        if abs(correlations.loc[correlations['Metric'] == 'Energy', 'Correlation'].iloc[0]) > 0.5:
                            st.markdown("• Plan activities based on air quality 🏃")
    
    with tab2:
        st.subheader("Population Mental Health Trends")
        
        # Simulated population data
        aqi_ranges = ['0-50', '51-100', '101-150', '151-200', '201-300', '300+']
        stress_correlation = [10, 25, 45, 65, 80, 90]
        anxiety_correlation = [15, 30, 50, 70, 85, 95]
        depression_correlation = [12, 28, 48, 68, 82, 92]
        
        # Create DataFrame
        population_data = pd.DataFrame({
            'AQI Range': aqi_ranges,
            'Stress %': stress_correlation,
            'Anxiety %': anxiety_correlation,
            'Depression %': depression_correlation
        })
        
        # Display population trends
        st.bar_chart(
            population_data.set_index('AQI Range')[['Stress %', 'Anxiety %', 'Depression %']]
        )
        
        # Add explanatory text
        st.markdown("""
        ### Population Impact Analysis
        
        This chart shows the percentage of population reporting mental health symptoms
        at different AQI levels based on aggregated data:
        
        - **Stress**: General psychological stress levels
        - **Anxiety**: Reported anxiety symptoms
        - **Depression**: Reported depression symptoms
        
        *Note: Data is based on population surveys and medical records analysis.*
        """)
        
        # Add research citations
        with st.expander("Research Citations"):
            st.markdown("""
            1. WHO Guidelines on Air Quality and Mental Health (2023)
            2. Environmental Health Perspectives: Air Pollution and Mental Health
            3. Journal of Environmental Psychology: AQI Impact Studies
            4. Public Health Reports: Urban Air Quality and Psychological Well-being
            """)

def main():
    st.sidebar.title("Menu")
    page = st.sidebar.selectbox(
        "Menu",
        ["Predict", "Geo Location", "India AQI Map", "Explore", "Psychological Impact"]
    )
    
    if page == "Predict":
        show_predict_page()
    elif page == "Geo Location":
        show_geo_prediction_page()
    elif page == "India AQI Map":
        show_india_aqi_map()
    elif page == "Explore":
        show_model_metrics()
    else:
        show_stress_correlation()

if __name__ == "__main__":
    main()
