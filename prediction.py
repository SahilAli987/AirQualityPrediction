import streamlit as st
import pickle
import numpy as np
import pandas as pd
import requests
import json
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import folium_static
from folium import plugins


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


def get_aqi_data(lat, lon):
    try:
        # Get pollutant data from OpenWeather
        success_ow, pollutants = get_openweather_pollutants(lat, lon)
        # Get AQI from IQAir
        success_iqair, aqi = get_iqair_aqi(lat, lon)
        
        if success_ow and success_iqair:
            st.success("Successfully fetched data from both APIs!")
            
            # Convert OpenWeather data to our format
            # Note: OpenWeather provides CO in μg/m³, we need to convert to mg/m³
            co_value = round(pollutants.get('co', 0) / 1000.0, 3)  # Convert and round to 3 decimal places
            
            aqi_data = {
                'PM2.5': pollutants.get('pm2_5', 0),  # μg/m³
                'NO2': pollutants.get('no2', 0),      # μg/m³
                'CO': co_value,                       # mg/m³ (3 decimal places)
                'SO2': pollutants.get('so2', 0),      # μg/m³
                'O3': pollutants.get('o3', 0),        # μg/m³
                'aqi': aqi                            # US AQI from IQAir
            }
            
            return aqi_data
        else:
            if not success_ow:
                st.error(f"OpenWeather API Error: Could not fetch pollutant data")
            if not success_iqair:
                st.error(f"IQAir API Error: Could not fetch AQI")
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


def show_india_aqi_map():
    st.title("India Air Quality Map")
    st.write("Real-time Air Quality Index (AQI) map of cities across India")
    
    # WAQI API key
    api_key = "4bd665894a9f473c47c0eb62121cd5a70b9378b4"
    
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
    
    # Create a map centered on India with a slightly lower zoom level
    m = folium.Map(location=[20.5937, 78.9629], zoom_start=4)
    
    # Add city markers with AQI data
    for city, coords in indian_cities.items():
        try:
            # Fetch AQI data for each city
            url = f"https://api.waqi.info/feed/geo:{coords[0]};{coords[1]}/?token={api_key}"
            response = requests.get(url)
            data = response.json()
            
            if response.status_code == 200 and data['status'] == 'ok':
                aqi = data['data']['aqi']
                
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
                    radius=12,  # Slightly smaller radius due to more markers
                    popup=f"{city}<br>AQI: {aqi}<br>Status: {category}",
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.7,
                    weight=2
                ).add_to(m)
                
        except Exception as e:
            st.error(f"Error fetching data for {city}: {str(e)}")
    
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
    
    # Add city categories explanation
    st.subheader("Cities Included:")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **Metro Cities:**
        - Delhi, Mumbai, Bangalore
        - Chennai, Kolkata, Hyderabad
        
        **State Capitals:**
        - Lucknow, Jaipur, Bhopal
        - Patna, Raipur, Bhubaneswar
        - And many more...
        """)
    
    with col2:
        st.markdown("""
        **Major Industrial/Commercial Cities:**
        - Pune, Ahmedabad, Surat
        - Visakhapatnam, Nagpur, Indore
        - Coimbatore, Ludhiana, Nashik
        - And many more...
        """)
    
    # Add explanation
    st.info("""
    This map shows real-time Air Quality Index (AQI) data for cities across India, including:
    - All major metropolitan cities
    - State capitals
    - Major industrial and commercial hubs
    - Click on any marker to see detailed AQI information
    - Colors indicate the air quality level from Good (green) to Hazardous (black)
    """)
    
    # Add timestamp with styling
    st.caption(f"Last updated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
    
    # Add data source attribution
    st.markdown("""
    <small>Data source: World Air Quality Index Project (WAQI)</small>
    """, unsafe_allow_html=True)
